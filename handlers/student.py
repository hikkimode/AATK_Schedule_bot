from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from services.audit_service import ScheduleService
from states import StudentStates


router = Router()

NO_SCHEDULE_MESSAGE = "Ошибка: Расписание еще не загружено в систему"


DAY_LABELS = {
    "ru": {
        "Понедельник": "Понедельник",
        "Вторник": "Вторник",
        "Среда": "Среда",
        "Четверг": "Четверг",
        "Пятница": "Пятница",
        "Суббота": "Суббота",
    },
    "kz": {
        "Понедельник": "Дүйсенбі",
        "Вторник": "Сейсенбі",
        "Среда": "Сәрсенбі",
        "Четверг": "Бейсенбі",
        "Пятница": "Жұма",
        "Суббота": "Сенбі",
    },
}


TEXTS = {
    "ru": {
        "welcome": "Выберите язык интерфейса.",
        "welcome_teacher": "Выберите язык интерфейса.\nДля панели преподавателя используйте команду /teacher.",
        "choose_group": "Выберите группу.",
        "choose_day": "Выберите день недели.",
        "empty_schedule": "На этот день расписание не найдено.",
        "back_groups": "К группам",
        "back_days": "К дням",
        "language_ru": "Русский",
        "language_kz": "Қазақша",
        "group": "Группа",
        "day": "День",
        "schedule_title": "Расписание",
        "changed": "Есть изменение",
        "subject": "Предмет",
        "teacher": "Преподаватель",
        "room": "Кабинет",
    },
    "kz": {
        "welcome": "Интерфейс тілін таңдаңыз.",
        "welcome_teacher": "Интерфейс тілін таңдаңыз.\nОқытушы панелі үшін /teacher пәрменін пайдаланыңыз.",
        "choose_group": "Топты таңдаңыз.",
        "choose_day": "Апта күнін таңдаңыз.",
        "empty_schedule": "Бұл күнге сабақ кестесі табылмады.",
        "back_groups": "Топтарға",
        "back_days": "Күндерге",
        "language_ru": "Русский",
        "language_kz": "Қазақша",
        "group": "Топ",
        "day": "Күн",
        "schedule_title": "Сабақ кестесі",
        "changed": "Өзгеріс бар",
        "subject": "Пән",
        "teacher": "Оқытушы",
        "room": "Кабинет",
    },
}


def _chunk_buttons(buttons: list[InlineKeyboardButton], width: int) -> list[list[InlineKeyboardButton]]:
    return [buttons[index:index + width] for index in range(0, len(buttons), width)]


def _language_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=TEXTS["ru"]["language_ru"], callback_data="student_language:ru"),
        InlineKeyboardButton(text=TEXTS["ru"]["language_kz"], callback_data="student_language:kz"),
    ]
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def _groups_keyboard(groups: list[str]) -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(text=group, callback_data=f"student_group:{group}") for group in groups]
    return InlineKeyboardMarkup(inline_keyboard=_chunk_buttons(buttons, 3))


def _days_keyboard(days: list[str], language: str) -> InlineKeyboardMarkup:
    labels = DAY_LABELS[language]
    buttons = [InlineKeyboardButton(text=labels.get(day, day), callback_data=f"student_day:{day}") for day in days]
    rows = _chunk_buttons(buttons, 2)
    rows.append([InlineKeyboardButton(text=TEXTS[language]["back_groups"], callback_data="student_back:groups")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _schedule_keyboard(days: list[str], language: str) -> InlineKeyboardMarkup:
    rows = _days_keyboard(days, language).inline_keyboard
    rows.append([InlineKeyboardButton(text=TEXTS[language]["back_days"], callback_data="student_back:days")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _resolve_language(data: dict[str, str]) -> str:
    return data.get("language", "ru")


def _format_time(value: str | None) -> str:
    if not value:
        return "—"
    text = str(value).strip()
    if not text:
        return "—"
    parts = text.split(":")
    if len(parts) >= 2:
        return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}"
    return text


def _render_schedule(group_name: str, day: str, lessons: list, language: str) -> str:
    texts = TEXTS[language]
    day_label = DAY_LABELS[language].get(day, day)
    lines = [
        f"📚 <b>{texts['schedule_title']}</b>",
        f"👥 <b>{texts['group']}:</b> {html.escape(group_name)}",
        f"🗓 <b>{texts['day']}:</b> {html.escape(day_label)}",
        "",
    ]
    if not lessons:
        lines.append(f"😴 {texts['empty_schedule']}")
        return "\n".join(lines)
    for lesson in lessons:
        status = f"\n⚠️ <b>{texts['changed']}</b>" if lesson.is_change else ""
        start_time = _format_time(lesson.start_time)
        end_time = _format_time(lesson.end_time)
        lines.extend(
            [
                f"🔹 <b>{lesson.lesson_number}-пара</b>  {html.escape(start_time)} - {html.escape(end_time)}",
                f"📘 <b>{texts['subject']}:</b> {html.escape(lesson.subject or '—')}",
                f"👩‍🏫 <b>{texts['teacher']}:</b> {html.escape(lesson.teacher or '—')}",
                f"🏫 <b>{texts['room']}:</b> {html.escape(lesson.room or '—')}{status}",
                "",
            ]
        )
    return "\n".join(lines).strip()


@router.message(Command("start"))
async def start_student(message: Message, state: FSMContext, role: str) -> None:
    await state.clear()
    await state.set_state(StudentStates.language)
    key = "welcome_teacher" if role in {"teacher", "superadmin"} else "welcome"
    await message.answer(TEXTS["ru"][key], reply_markup=_language_keyboard())


@router.message(Command("cancel"))
async def cancel_action(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Текущее действие сброшено. Используйте /start или /teacher.")


@router.callback_query(F.data.startswith("student_language:"))
async def select_language(
    callback: CallbackQuery,
    state: FSMContext,
    schedule_service: ScheduleService,
) -> None:
    language = callback.data.split(":", maxsplit=1)[1]
    groups = await schedule_service.list_groups()
    if not groups:
        await callback.message.edit_text(NO_SCHEDULE_MESSAGE)
        await callback.answer()
        return
    await state.update_data(language=language)
    await state.set_state(StudentStates.group)
    await callback.message.edit_text(TEXTS[language]["choose_group"], reply_markup=_groups_keyboard(groups))
    await callback.answer()


@router.callback_query(F.data == "student_back:groups")
async def back_to_groups(
    callback: CallbackQuery,
    state: FSMContext,
    schedule_service: ScheduleService,
) -> None:
    data = await state.get_data()
    language = _resolve_language(data)
    groups = await schedule_service.list_groups()
    if not groups:
        await callback.message.edit_text(NO_SCHEDULE_MESSAGE)
        await callback.answer()
        return
    await state.set_state(StudentStates.group)
    await callback.message.edit_text(TEXTS[language]["choose_group"], reply_markup=_groups_keyboard(groups))
    await callback.answer()


@router.callback_query(F.data.startswith("student_group:"))
async def select_group(
    callback: CallbackQuery,
    state: FSMContext,
    schedule_service: ScheduleService,
) -> None:
    group_name = callback.data.split(":", maxsplit=1)[1]
    data = await state.get_data()
    language = _resolve_language(data)
    days = await schedule_service.list_days(group_name=group_name)
    await state.update_data(group_name=group_name)
    await state.set_state(StudentStates.day)
    await callback.message.edit_text(TEXTS[language]["choose_day"], reply_markup=_days_keyboard(days, language))
    await callback.answer()


@router.callback_query(F.data == "student_back:days")
async def back_to_days(
    callback: CallbackQuery,
    state: FSMContext,
    schedule_service: ScheduleService,
) -> None:
    data = await state.get_data()
    language = _resolve_language(data)
    group_name = data.get("group_name")
    days = await schedule_service.list_days(group_name=group_name)
    await state.set_state(StudentStates.day)
    await callback.message.edit_text(TEXTS[language]["choose_day"], reply_markup=_days_keyboard(days, language))
    await callback.answer()


@router.callback_query(F.data.startswith("student_day:"))
async def show_day_schedule(
    callback: CallbackQuery,
    state: FSMContext,
    schedule_service: ScheduleService,
) -> None:
    day = callback.data.split(":", maxsplit=1)[1]
    data = await state.get_data()
    language = _resolve_language(data)
    group_name = data.get("group_name")
    if group_name is None:
        groups = await schedule_service.list_groups()
        if not groups:
            await callback.message.edit_text(NO_SCHEDULE_MESSAGE)
            await callback.answer()
            return
        await state.set_state(StudentStates.group)
        await callback.message.edit_text(TEXTS[language]["choose_group"], reply_markup=_groups_keyboard(groups))
        await callback.answer()
        return
    lessons = await schedule_service.get_lessons(group_name=group_name, day=day)
    days = await schedule_service.list_days(group_name=group_name)
    text = _render_schedule(group_name=group_name, day=day, lessons=lessons, language=language)
    await callback.message.edit_text(text, reply_markup=_schedule_keyboard(days, language))
    await callback.answer()
