from __future__ import annotations

import html
import logging
from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from locales import get_text
from services.audit_service import ScheduleService
from states import StudentStates

logger = logging.getLogger(__name__)


router = Router()

LOCAL_TZ = timezone(timedelta(hours=5))
DAY_INDEX_TO_RUS = [
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
    "Суббота",
    "Воскресенье",
]

DAY_LABELS_KZ = {
    "Понедельник": "Дүйсенбі",
    "Вторник": "Сейсенбі",
    "Среда": "Сәрсенбі",
    "Четверг": "Бейсенбі",
    "Пятница": "Жұма",
    "Суббота": "Сенбі",
    "Воскресенье": "Жексенбі",
}


def _chunk_buttons(buttons: list[InlineKeyboardButton], width: int) -> list[list[InlineKeyboardButton]]:
    return [buttons[index:index + width] for index in range(0, len(buttons), width)]


def _language_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=get_text("language_ru"), callback_data="student_language:ru"),
        InlineKeyboardButton(text=get_text("language_kz"), callback_data="student_language:kk"),
    ]
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def _groups_keyboard(groups: list[str]) -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(text=group, callback_data=f"student_group:{group}") for group in groups]
    return InlineKeyboardMarkup(inline_keyboard=_chunk_buttons(buttons, 3))


def _subgroups_keyboard(language: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=get_text("subgroup_all", language), callback_data="student_subgroup:0")],
        [InlineKeyboardButton(text=get_text("subgroup_1", language), callback_data="student_subgroup:1")],
        [InlineKeyboardButton(text=get_text("subgroup_2", language), callback_data="student_subgroup:2")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _days_keyboard(days: list[str], language: str) -> InlineKeyboardMarkup:
    labels = {day: (DAY_LABELS_KZ.get(day, day) if language == "kk" else day) for day in days}
    buttons = [InlineKeyboardButton(text=labels.get(day, day), callback_data=f"student_day:{day}") for day in days]
    rows = _chunk_buttons(buttons, 2)
    rows.append([InlineKeyboardButton(text=get_text("back_groups", language), callback_data="student_back:groups")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _schedule_keyboard(days: list[str], language: str) -> InlineKeyboardMarkup:
    rows = _days_keyboard(days, language).inline_keyboard
    rows.append([InlineKeyboardButton(text=get_text("back_days", language), callback_data="student_back:days")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _resolve_language(data: dict[str, str]) -> str:
    return data.get("language", "ru")


def _format_time(value: str | None) -> str:
    if not value:
        return "—"
    if hasattr(value, "strftime"):
        try:
            return value.strftime("%H:%M")
        except Exception:
            pass
    text = str(value).strip()
    if not text:
        return "—"
    parts = text.split(":")
    if len(parts) >= 2:
        return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}"
    return text


def _render_schedule(group_name: str, day: str, lessons: list, language: str) -> str:
    """Render schedule with metadata and friendly empty state messages."""
    day_label = DAY_LABELS_KZ.get(day, day) if language == "kk" else day
    
    lines = [
        f"📚 <b>{get_text('schedule_title', language)}</b>",
        f"👥 <b>{get_text('group', language)}:</b> {html.escape(group_name)}",
        f"🗓 <b>{get_text('day', language)}:</b> {html.escape(day_label)}",
    ]
    
    # Track which subgroup we are displaying
    subgroups_seen = {l.subgroup for l in lessons if hasattr(l, 'subgroup')}
    if 1 in subgroups_seen and 2 not in subgroups_seen:
        lines.append(f"🔢 <b>{get_text('subgroup_prefix', language)}:</b> 1")
    elif 2 in subgroups_seen and 1 not in subgroups_seen:
        lines.append(f"🔢 <b>{get_text('subgroup_prefix', language)}:</b> 2")
    
    lines.append("")
    
    if not lessons:
        # Friendly empty state message
        if day.lower() == "воскресенье" or (language == "kk" and day.lower() == "жексенбі"):
            empty_msg = get_text("no_lessons", language)
        else:
            empty_msg = get_text("empty_schedule", language)
        lines.append(f"😴 {empty_msg}")
        lines.append("")
        timestamp = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"🕒 <b>{get_text('last_updated', language)}:</b> {timestamp}")
        return "\n".join(lines)
    
    # Display lessons
    for lesson in lessons:
        status = f"\n⚠️ <b>{get_text('changed', language)}</b>" if lesson.is_change else ""
        start_time = _format_time(lesson.start_time)
        end_time = _format_time(lesson.end_time)
        subgroup_label = ""
        if hasattr(lesson, 'subgroup') and lesson.subgroup != 0:
            subgroup_label = f" ({lesson.subgroup} {get_text('subgroup_prefix', language).lower()})"
            
        lines.extend([
            f"🔹 <b>{lesson.num}{get_text('schedule_title', language).split()[-1] if language == 'kk' else '-пара'}</b>  {html.escape(start_time)} - {html.escape(end_time)}{subgroup_label}",
            f"📘 <b>{get_text('subject', language)}:</b> {html.escape(lesson.name or '—')}",
            f"👩‍🏫 <b>{get_text('teacher', language)}:</b> {html.escape(lesson.teacher or '—')}",
            f"🏫 <b>{get_text('room', language)}:</b> {html.escape(lesson.room or '—')}{status}",
            "",
        ])
    
    # Add metadata
    timestamp = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S")
    lines.append(f"🕒 <b>{get_text('last_updated', language)}:</b> {timestamp}")
    
    return "\n".join(lines).strip()


def _student_home_keyboard(language: str, has_group: bool) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=get_text("today", language), callback_data="student_today")],
        [InlineKeyboardButton(text=get_text("tomorrow", language), callback_data="student_tomorrow")],
    ]
    if has_group:
        buttons.append([InlineKeyboardButton(text=get_text("choose_day_button", language), callback_data="student_choose_day")])
        buttons.append([InlineKeyboardButton(text=get_text("change_group", language), callback_data="student_change_group")])
    else:
        buttons.append([InlineKeyboardButton(text=get_text("choose_group_button", language), callback_data="student_choose_group")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _student_home_text(language: str, group_name: str | None = None) -> str:
    if group_name:
        return (
            f"👥 <b>{get_text('group', language)}:</b> {html.escape(group_name)}\n\n"
            f"{get_text('choose_group', language)}"
        )
    return get_text("choose_group", language)


def _compute_day_by_offset(offset: int = 0) -> str:
    now = datetime.now(LOCAL_TZ)
    day_index = (now.weekday() + offset) % len(DAY_INDEX_TO_RUS)
    return DAY_INDEX_TO_RUS[day_index]


@router.message(Command("start"))
async def start_student(message: Message, state: FSMContext, role: str, schedule_service: ScheduleService) -> None:
    await state.clear()
    profile = await schedule_service.get_user_profile(message.from_user.id)
    if profile and profile.group_name:
        await state.update_data(language=profile.language, group_name=profile.group_name)
        await message.answer(
            _student_home_text(profile.language, profile.group_name),
            reply_markup=_student_home_keyboard(profile.language, True),
        )
        return

    await state.set_state(StudentStates.language)
    key = "welcome_teacher" if role in {"teacher", "superadmin"} else "welcome"
    await message.answer(get_text(key), reply_markup=_language_keyboard())


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
    await schedule_service.save_user_profile(callback.from_user.id, language=language)
    groups = await schedule_service.list_groups()
    if not groups:
        await callback.message.edit_text(get_text("no_schedule_loaded", language))
        await callback.answer()
        return
    await state.update_data(language=language)
    await state.set_state(StudentStates.group)
    await callback.message.edit_text(get_text("choose_group", language), reply_markup=_groups_keyboard(groups))
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
        await callback.message.edit_text(get_text("no_schedule_loaded", language))
        await callback.answer()
        return
    await state.set_state(StudentStates.group)
    await callback.message.edit_text(get_text("choose_group", language), reply_markup=_groups_keyboard(groups))
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
    tg_id = callback.from_user.id
    logger.info(f"Saving profile for {tg_id}: group_name={group_name}")
    await schedule_service.save_user_profile(tg_id, group_name=group_name)
    logger.info(f"Retrieved profile to verify: {profile}")
    await state.update_data(group_name=group_name)
    await state.set_state(StudentStates.subgroup)
    await callback.message.edit_text(
        get_text("choose_subgroup", language),
        reply_markup=_subgroups_keyboard(language),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("student_subgroup:"))
async def select_subgroup(
    callback: CallbackQuery,
    state: FSMContext,
    schedule_service: ScheduleService,
) -> None:
    subgroup = int(callback.data.split(":", maxsplit=1)[1])
    data = await state.get_data()
    language = _resolve_language(data)
    group_name = data.get("group_name")
    
    await schedule_service.save_user_profile(callback.from_user.id, subgroup=subgroup)
    await state.update_data(subgroup=subgroup)
    
    await state.set_state(StudentStates.day)
    await callback.message.edit_text(
        _student_home_text(language, group_name),
        reply_markup=_student_home_keyboard(language, True),
    )
    await callback.answer()


@router.callback_query(F.data == "student_choose_group")
async def choose_group_callback(
    callback: CallbackQuery,
    state: FSMContext,
    schedule_service: ScheduleService,
) -> None:
    data = await state.get_data()
    language = _resolve_language(data)
    groups = await schedule_service.list_groups()
    if not groups:
        await callback.message.edit_text(get_text("no_schedule_loaded", language))
        await callback.answer()
        return
    await state.set_state(StudentStates.group)
    await callback.message.edit_text(get_text("choose_group", language), reply_markup=_groups_keyboard(groups))
    await callback.answer()


@router.callback_query(F.data == "student_change_group")
async def change_group_callback(
    callback: CallbackQuery,
    state: FSMContext,
    schedule_service: ScheduleService,
) -> None:
    data = await state.get_data()
    language = _resolve_language(data)
    await schedule_service.save_user_profile(callback.from_user.id, group_name=None)
    groups = await schedule_service.list_groups()
    if not groups:
        await callback.message.edit_text(get_text("no_schedule_loaded", language))
        await callback.answer()
        return
    await state.set_state(StudentStates.group)
    await callback.message.edit_text(get_text("choose_group", language), reply_markup=_groups_keyboard(groups))
    await callback.answer()


@router.callback_query(F.data == "student_choose_day")
async def choose_day_callback(
    callback: CallbackQuery,
    state: FSMContext,
    schedule_service: ScheduleService,
) -> None:
    data = await state.get_data()
    language = _resolve_language(data)
    group_name = data.get("group_name")
    if not group_name:
        await choose_group_callback(callback, state, schedule_service)
        return
    days = await schedule_service.list_days(group_name=group_name)
    await state.set_state(StudentStates.day)
    await callback.message.edit_text(get_text("choose_day", language), reply_markup=_days_keyboard(days, language))
    await callback.answer()


@router.callback_query(F.data == "student_today")
async def student_today(
    callback: CallbackQuery,
    state: FSMContext,
    schedule_service: ScheduleService,
) -> None:
    tg_id = callback.from_user.id
    logger.info(f"student_today: fetching profile for {tg_id}")
    profile = await schedule_service.get_user_profile(tg_id)
    if profile is None or not profile.group_name:
        logger.info(f"student_today: profile not found or no group, asking to choose")
        await choose_group_callback(callback, state, schedule_service)
        return
    language = profile.language or "ru"
    logger.info(f"student_today: found profile with group={profile.group_name}, lang={language}")
    day = _compute_day_by_offset(0)
    user_subgroup = profile.subgroup if profile else 0
    lessons = await schedule_service.get_lessons(profile.group_name, day=day, subgroup=user_subgroup)
    text = _render_schedule(profile.group_name, day=day, lessons=lessons, language=language)
    await callback.message.edit_text(text, reply_markup=_student_home_keyboard(language, True))
    await callback.answer()


@router.callback_query(F.data == "student_tomorrow")
async def student_tomorrow(
    callback: CallbackQuery,
    state: FSMContext,
    schedule_service: ScheduleService,
) -> None:
    tg_id = callback.from_user.id
    logger.info(f"student_tomorrow: fetching profile for {tg_id}")
    profile = await schedule_service.get_user_profile(tg_id)
    if profile is None or not profile.group_name:
        logger.info(f"student_tomorrow: profile not found or no group, asking to choose")
        await choose_group_callback(callback, state, schedule_service)
        return
    language = profile.language or "ru"
    logger.info(f"student_tomorrow: found profile with group={profile.group_name}, lang={language}")
    day = _compute_day_by_offset(1)
    user_subgroup = profile.subgroup if profile else 0
    lessons = await schedule_service.get_lessons(profile.group_name, day=day, subgroup=user_subgroup)
    text = _render_schedule(profile.group_name, day=day, lessons=lessons, language=language)
    await callback.message.edit_text(text, reply_markup=_student_home_keyboard(language, True))
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
    await callback.message.edit_text(get_text("choose_day", language), reply_markup=_days_keyboard(days, language))
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
            await callback.message.edit_text(get_text("no_schedule_loaded", language))
            await callback.answer()
            return
        await state.set_state(StudentStates.group)
        await callback.message.edit_text(get_text("choose_group", language), reply_markup=_groups_keyboard(groups))
        await callback.answer()
        return
    profile = await schedule_service.get_user_profile(callback.from_user.id)
    user_subgroup = profile.subgroup if profile else 0
    lessons = await schedule_service.get_lessons(group_name=group_name, day=day, subgroup=user_subgroup)
    text = _render_schedule(group_name=group_name, day=day, lessons=lessons, language=language)
    await callback.message.edit_text(text, reply_markup=_student_home_keyboard(language, True))
    await callback.answer()
