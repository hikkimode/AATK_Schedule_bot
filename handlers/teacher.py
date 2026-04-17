from __future__ import annotations

import html
import re
import tempfile
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from services.audit_service import AuditService, ImportReport, LessonPayload, ScheduleService
from states import TeacherStates


router = Router()

TIME_PATTERN = re.compile(r"^\d{2}:\d{2}$")


def _chunk_buttons(buttons: list[InlineKeyboardButton], width: int) -> list[list[InlineKeyboardButton]]:
    return [buttons[index:index + width] for index in range(0, len(buttons), width)]


def _access_denied_text() -> str:
    return "Команда доступна только преподавателям и superadmin."


def _groups_keyboard(groups: list[str]) -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(text=group, callback_data=f"teacher_group:{group}") for group in groups]
    rows = _chunk_buttons(buttons, 3)
    rows.append([InlineKeyboardButton(text="📥 Импорт изменений из Excel", callback_data="teacher_import_excel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _days_keyboard(days: list[str]) -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(text=day, callback_data=f"teacher_day:{day}") for day in days]
    rows = _chunk_buttons(buttons, 2)
    rows.append([InlineKeyboardButton(text="К группам", callback_data="teacher_back:groups")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _lessons_keyboard(max_lesson_number: int) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=f"{number}-пара", callback_data=f"teacher_lesson:{number}")
        for number in range(1, max_lesson_number + 1)
    ]
    rows = _chunk_buttons(buttons, 2)
    rows.append([InlineKeyboardButton(text="К дням", callback_data="teacher_back:days")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _action_keyboard(has_lesson: bool, is_change: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if has_lesson:
        rows.append([InlineKeyboardButton(text="Обновить", callback_data="teacher_action:update")])
        rows.append([InlineKeyboardButton(text="Удалить", callback_data="teacher_action:delete")])
        label = "Снять изменение" if is_change else "Отметить изменение"
        rows.append([InlineKeyboardButton(text=label, callback_data="teacher_action:toggle_change")])
    else:
        rows.append([InlineKeyboardButton(text="Создать", callback_data="teacher_action:create")])
    rows.append([InlineKeyboardButton(text="К парам", callback_data="teacher_back:lessons")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _teacher_menu_text(group_name: str, day: str, lesson_number: int, lesson) -> str:
    lines = [
        "🛠 <b>Редактирование расписания</b>",
        f"👥 <b>Группа:</b> {html.escape(group_name)}",
        f"📅 <b>День:</b> {html.escape(day)}",
        f"🔢 <b>Пара:</b> {lesson_number}",
        "",
    ]
    if lesson is None:
        lines.append("Слот пуст. Можно создать новую запись.")
        return "\n".join(lines)
    lines.extend(
        [
            f"📘 <b>Предмет:</b> {html.escape(lesson.subject or '—')}",
            f"👩‍🏫 <b>Преподаватель:</b> {html.escape(lesson.teacher or '—')}",
            f"🏫 <b>Кабинет:</b> {html.escape(lesson.room or '—')}",
            f"🕒 <b>Время:</b> {html.escape(lesson.start_time or '—')} - {html.escape(lesson.end_time or '—')}",
            f"⚠️ <b>Изменение:</b> {'Да' if lesson.is_change else 'Нет'}",
        ]
    )
    return "\n".join(lines)


def _import_report_text(report: ImportReport) -> str:
    groups = ", ".join(report.updated_groups) if report.updated_groups else "—"
    lines = [
        "📥 <b>Импорт изменений завершён</b>",
        "",
        f"✅ Обновлено строк: <b>{report.updated_rows}</b>",
        f"📚 Группы с изменениями: <b>{html.escape(groups)}</b>",
        f"⚠️ Пропущено строк: <b>{report.skipped_rows}</b>",
    ]
    if report.errors:
        lines.extend(["", "📝 Что не удалось обработать:"])
        lines.extend(f"• {html.escape(error)}" for error in report.errors[:10])
        if len(report.errors) > 10:
            lines.append(f"• И ещё {len(report.errors) - 10} строк(и)")
    return "\n".join(lines)


async def _show_groups(message: Message, schedule_service: ScheduleService) -> None:
    groups = await schedule_service.list_groups()
    await message.answer("Выберите группу для редактирования.", reply_markup=_groups_keyboard(groups))


async def _show_days(callback: CallbackQuery, schedule_service: ScheduleService) -> None:
    days = await schedule_service.list_days()
    await callback.message.edit_text("Выберите день недели.", reply_markup=_days_keyboard(days))


async def _show_lessons(callback: CallbackQuery, schedule_service: ScheduleService) -> None:
    max_lesson_number = await schedule_service.get_max_lesson_number()
    await callback.message.edit_text("Выберите номер пары.", reply_markup=_lessons_keyboard(max_lesson_number))


async def _show_actions(callback: CallbackQuery, state: FSMContext, schedule_service: ScheduleService) -> None:
    data = await state.get_data()
    group_name = data["group_name"]
    day = data["day"]
    lesson_number = data["lesson_number"]
    lesson = await schedule_service.get_lesson(group_name, day, lesson_number)
    await callback.message.edit_text(
        _teacher_menu_text(group_name, day, lesson_number, lesson),
        reply_markup=_action_keyboard(has_lesson=lesson is not None, is_change=bool(lesson and lesson.is_change)),
    )


@router.message(Command("teacher"))
async def teacher_panel(
    message: Message,
    state: FSMContext,
    role: str,
    schedule_service: ScheduleService,
) -> None:
    if role not in {"teacher", "superadmin"}:
        await message.answer(_access_denied_text())
        return
    await state.clear()
    await state.set_state(TeacherStates.group)
    await _show_groups(message, schedule_service)


@router.callback_query(F.data == "teacher_import_excel")
async def teacher_import_excel(
    callback: CallbackQuery,
    state: FSMContext,
    role: str,
) -> None:
    if role not in {"teacher", "superadmin"}:
        await callback.answer(_access_denied_text(), show_alert=True)
        return
    await state.set_state(TeacherStates.import_file)
    await callback.message.edit_text(
        "📥 <b>Импорт изменений из Excel</b>\n\n"
        "Отправьте файл <b>.xlsx</b> прямо в этот чат.\n"
        "Ожидаемые колонки:\n"
        "<code>group_name, day, lesson_number, subject, teacher, room, start_time, end_time</code>"
    )
    await callback.answer()


@router.callback_query(F.data == "teacher_back:groups")
async def teacher_back_groups(
    callback: CallbackQuery,
    state: FSMContext,
    schedule_service: ScheduleService,
    role: str,
) -> None:
    if role not in {"teacher", "superadmin"}:
        await callback.answer(_access_denied_text(), show_alert=True)
        return
    groups = await schedule_service.list_groups()
    await state.set_state(TeacherStates.group)
    await callback.message.edit_text("Выберите группу для редактирования.", reply_markup=_groups_keyboard(groups))
    await callback.answer()


@router.callback_query(F.data.startswith("teacher_group:"))
async def teacher_select_group(
    callback: CallbackQuery,
    state: FSMContext,
    role: str,
    schedule_service: ScheduleService,
) -> None:
    if role not in {"teacher", "superadmin"}:
        await callback.answer(_access_denied_text(), show_alert=True)
        return
    group_name = callback.data.split(":", maxsplit=1)[1]
    await state.update_data(group_name=group_name)
    await state.set_state(TeacherStates.day)
    await _show_days(callback, schedule_service)
    await callback.answer()


@router.callback_query(F.data == "teacher_back:days")
async def teacher_back_days(
    callback: CallbackQuery,
    state: FSMContext,
    schedule_service: ScheduleService,
) -> None:
    await state.set_state(TeacherStates.day)
    await _show_days(callback, schedule_service)
    await callback.answer()


@router.callback_query(F.data.startswith("teacher_day:"))
async def teacher_select_day(
    callback: CallbackQuery,
    state: FSMContext,
    role: str,
    schedule_service: ScheduleService,
) -> None:
    if role not in {"teacher", "superadmin"}:
        await callback.answer(_access_denied_text(), show_alert=True)
        return
    day = callback.data.split(":", maxsplit=1)[1]
    await state.update_data(day=day)
    await state.set_state(TeacherStates.lesson)
    await _show_lessons(callback, schedule_service)
    await callback.answer()


@router.callback_query(F.data == "teacher_back:lessons")
async def teacher_back_lessons(
    callback: CallbackQuery,
    state: FSMContext,
    schedule_service: ScheduleService,
) -> None:
    await state.set_state(TeacherStates.lesson)
    await _show_lessons(callback, schedule_service)
    await callback.answer()


@router.callback_query(F.data.startswith("teacher_lesson:"))
async def teacher_select_lesson(
    callback: CallbackQuery,
    state: FSMContext,
    role: str,
    schedule_service: ScheduleService,
) -> None:
    if role not in {"teacher", "superadmin"}:
        await callback.answer(_access_denied_text(), show_alert=True)
        return
    lesson_number = int(callback.data.split(":", maxsplit=1)[1])
    await state.update_data(lesson_number=lesson_number)
    await state.set_state(TeacherStates.action)
    await _show_actions(callback, state, schedule_service)
    await callback.answer()


@router.callback_query(F.data == "teacher_action:create")
@router.callback_query(F.data == "teacher_action:update")
async def teacher_prepare_form(
    callback: CallbackQuery,
    state: FSMContext,
    role: str,
) -> None:
    if role not in {"teacher", "superadmin"}:
        await callback.answer(_access_denied_text(), show_alert=True)
        return
    action = callback.data.split(":", maxsplit=1)[1]
    await state.update_data(action=action)
    await state.set_state(TeacherStates.subject)
    await callback.message.edit_text("Введите предмет.")
    await callback.answer()


@router.callback_query(F.data == "teacher_action:delete")
async def teacher_delete_lesson(
    callback: CallbackQuery,
    state: FSMContext,
    role: str,
    audit_service: AuditService,
    schedule_service: ScheduleService,
) -> None:
    if role not in {"teacher", "superadmin"}:
        await callback.answer(_access_denied_text(), show_alert=True)
        return
    data = await state.get_data()
    try:
        await audit_service.delete_lesson(
            tg_id=callback.from_user.id,
            full_name=callback.from_user.full_name,
            group_name=data["group_name"],
            day=data["day"],
            lesson_number=data["lesson_number"],
        )
        await _show_actions(callback, state, schedule_service)
        await callback.answer("Запись удалена.")
    except ValueError as error:
        await callback.answer(str(error), show_alert=True)


@router.callback_query(F.data == "teacher_action:toggle_change")
async def teacher_toggle_change(
    callback: CallbackQuery,
    state: FSMContext,
    role: str,
    audit_service: AuditService,
    schedule_service: ScheduleService,
) -> None:
    if role not in {"teacher", "superadmin"}:
        await callback.answer(_access_denied_text(), show_alert=True)
        return
    data = await state.get_data()
    lesson = await schedule_service.get_lesson(data["group_name"], data["day"], data["lesson_number"])
    if lesson is None:
        await callback.answer("Запись не найдена.", show_alert=True)
        return
    await audit_service.set_change(
        tg_id=callback.from_user.id,
        full_name=callback.from_user.full_name,
        group_name=data["group_name"],
        day=data["day"],
        lesson_number=data["lesson_number"],
        is_change=not lesson.is_change,
    )
    await _show_actions(callback, state, schedule_service)
    await callback.answer("Статус изменения обновлён.")


@router.message(TeacherStates.subject)
async def teacher_set_subject(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Введите предмет текстом.")
        return
    await state.update_data(subject=message.text.strip())
    await state.set_state(TeacherStates.teacher)
    await message.answer("Введите ФИО преподавателя.")


@router.message(TeacherStates.teacher)
async def teacher_set_teacher(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Введите ФИО преподавателя текстом.")
        return
    await state.update_data(teacher_name=message.text.strip())
    await state.set_state(TeacherStates.room)
    await message.answer("Введите кабинет.")


@router.message(TeacherStates.room)
async def teacher_set_room(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Введите кабинет текстом.")
        return
    await state.update_data(room=message.text.strip())
    await state.set_state(TeacherStates.start_time)
    await message.answer("Введите время начала в формате HH:MM.")


@router.message(TeacherStates.start_time)
async def teacher_set_start_time(message: Message, state: FSMContext) -> None:
    if not message.text or not TIME_PATTERN.fullmatch(message.text.strip()):
        await message.answer("Время начала должно быть в формате HH:MM.")
        return
    await state.update_data(start_time=message.text.strip())
    await state.set_state(TeacherStates.end_time)
    await message.answer("Введите время окончания в формате HH:MM.")


@router.message(TeacherStates.end_time)
async def teacher_set_end_time(
    message: Message,
    state: FSMContext,
    audit_service: AuditService,
    schedule_service: ScheduleService,
) -> None:
    if not message.text or not TIME_PATTERN.fullmatch(message.text.strip()):
        await message.answer("Время окончания должно быть в формате HH:MM.")
        return
    data = await state.get_data()
    payload = LessonPayload(
        group_name=data["group_name"],
        day=data["day"],
        lesson_number=data["lesson_number"],
        subject=data["subject"],
        teacher=data["teacher_name"],
        room=data["room"],
        start_time=data["start_time"],
        end_time=message.text.strip(),
        is_change=False,
    )
    action = data["action"]
    try:
        if action == "create":
            await audit_service.create_lesson(
                tg_id=message.from_user.id,
                full_name=message.from_user.full_name,
                payload=payload,
            )
            result_text = "Запись создана."
        else:
            current_lesson = await schedule_service.get_lesson(payload.group_name, payload.day, payload.lesson_number)
            payload.is_change = bool(current_lesson and current_lesson.is_change)
            await audit_service.update_lesson(
                tg_id=message.from_user.id,
                full_name=message.from_user.full_name,
                payload=payload,
            )
            result_text = "Запись обновлена."
    except ValueError as error:
        await message.answer(str(error))
        return
    await state.set_state(TeacherStates.lesson)
    max_lesson_number = await schedule_service.get_max_lesson_number()
    await message.answer(result_text, reply_markup=_lessons_keyboard(max_lesson_number))


@router.message(TeacherStates.import_file, F.document)
async def teacher_process_import_file(
    message: Message,
    state: FSMContext,
    role: str,
    bot: Bot,
    schedule_service: ScheduleService,
    broadcast_service,
    session,
) -> None:
    if role not in {"teacher", "superadmin"}:
        await message.answer("❌ Ой, кажется, у вас нет доступа к этому разделу")
        return

    document = message.document
    if not document:
        await message.answer("❌ Файл не найден")
        return

    file_name = document.file_name or ""
    if not file_name.lower().endswith(".xlsx"):
        await message.answer("❌ Пришлите файл Excel в формате .xlsx")
        return

    temp_path = Path(tempfile.gettempdir()) / f"{document.file_unique_id}.xlsx"
    try:
        await bot.download(document, destination=temp_path)
        report = await schedule_service.import_changes_from_excel(temp_path)
    except ValueError as error:
        await message.answer(f"❌ Ошибка в данных: {html.escape(str(error))}")
        await state.clear()
        return
    except Exception as error:
        error_msg = str(error)
        await message.answer(f"❌ Ошибка базы данных:\n<code>{html.escape(error_msg[:200])}</code>")
        await state.clear()
        return
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)

    await state.clear()
    if report.updated_rows > 0:
        groups_text = ", ".join(report.updated_groups) if report.updated_groups else "—"
        await message.answer(
            f"✅ <b>Импорт успешен</b>\n\n"
            f"📝 Обновлено/добавлено строк: <b>{report.updated_rows}</b>\n"
            f"👥 Группы: <b>{html.escape(groups_text)}</b>\n"
            f"⚠️ Пропущено: <b>{report.skipped_rows}</b>"
        )
        
        # Broadcast notifications for each group that has changes
        import asyncio
        broadcast_tasks = []
        for group_name in report.updated_groups:
            # Query all days for this group and get lessons marked as changed
            days = await schedule_service.list_days(group_name=group_name)
            for day in days:
                lessons = await schedule_service.get_lessons(group_name, day)
                changed_lessons = [l for l in lessons if l.is_change]
                if changed_lessons:
                    task = broadcast_service.broadcast_schedule_changes(
                        session=session,
                        group_name=group_name,
                        day=day,
                        changes=changed_lessons,
                    )
                    broadcast_tasks.append(task)
        
        if broadcast_tasks:
            results = await asyncio.gather(*broadcast_tasks, return_exceptions=True)
            sent_total = 0
            failed_total = 0
            for result in results:
                if isinstance(result, dict):
                    sent_total += result.get('sent', 0)
                    failed_total += result.get('failed', 0)
            if sent_total > 0 or failed_total > 0:
                await message.answer(f"🔔 <b>Уведомления:</b> Отправлено {sent_total}, ошибок {failed_total}")
    else:
        await message.answer("⚠️ Не было обновлено ни одной записи. Проверьте данные в Excel.")

    if report.errors:
        error_text = "\n".join(f"• {html.escape(e)}" for e in report.errors[:5])
        if len(report.errors) > 5:
            error_text += f"\n• ...и ещё {len(report.errors) - 5}"
        await message.answer(f"📋 <b>Ошибки при импорте:</b>\n{error_text}")


@router.message(TeacherStates.import_file)
async def teacher_waiting_import_file(message: Message) -> None:
    await message.answer("📎 Пожалуйста, отправьте Excel-файл в формате .xlsx")
