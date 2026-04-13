from __future__ import annotations

import html
import re

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from services.audit_service import AuditService, LessonPayload, ScheduleService
from states import TeacherStates


router = Router()

TIME_PATTERN = re.compile(r"^\d{2}:\d{2}$")


def _chunk_buttons(buttons: list[InlineKeyboardButton], width: int) -> list[list[InlineKeyboardButton]]:
    return [buttons[index:index + width] for index in range(0, len(buttons), width)]


def _access_denied_text() -> str:
    return "Команда доступна только преподавателям и superadmin."


def _groups_keyboard(groups: list[str]) -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(text=group, callback_data=f"teacher_group:{group}") for group in groups]
    return InlineKeyboardMarkup(inline_keyboard=_chunk_buttons(buttons, 3))


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
