"""
Inline keyboards for schedule navigation.
"""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Day abbreviations and full names
DAYS_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб"]
DAYS_FULL = {
    "Пн": "Понедельник",
    "Вт": "Вторник", 
    "Ср": "Среда",
    "Чт": "Четверг",
    "Пт": "Пятница",
    "Сб": "Суббота"
}


def schedule_navigation_kb(
    current_day: str | None = None,
    group: str | None = None,
    week_view: bool = False
) -> InlineKeyboardMarkup:
    """
    Create inline keyboard for schedule navigation.
    
    Args:
        current_day: Currently selected day (e.g., "Пн")
        group: Current group name
        week_view: Whether showing full week view
    """
    builder = InlineKeyboardBuilder()
    
    # Day selection buttons (2 rows)
    day_buttons_row1 = []
    day_buttons_row2 = []
    
    for i, day in enumerate(DAYS_SHORT[:3]):
        text = f"📌 {day}" if day == current_day and not week_view else day
        callback = f"schedule:day:{day}:{group or ''}"
        day_buttons_row1.append(
            InlineKeyboardButton(text=text, callback_data=callback)
        )
    
    for i, day in enumerate(DAYS_SHORT[3:]):
        text = f"📌 {day}" if day == current_day and not week_view else day
        callback = f"schedule:day:{day}:{group or ''}"
        day_buttons_row2.append(
            InlineKeyboardButton(text=text, callback_data=callback)
        )
    
    builder.row(*day_buttons_row1)
    builder.row(*day_buttons_row2)
    
    # Week view and changes buttons
    week_text = "📅 На неделю (выбрано)" if week_view else "📅 На неделю"
    week_callback = f"schedule:week:{group or ''}"
    
    builder.row(
        InlineKeyboardButton(text=week_text, callback_data=week_callback),
        InlineKeyboardButton(text="⚡ Замены", callback_data=f"schedule:changes:{group or ''}")
    )
    
    # Group selection if no group specified
    if not group:
        builder.row(
            InlineKeyboardButton(text="👥 Выбрать группу", callback_data="schedule:select_group")
        )
    
    # Back to main menu
    builder.row(
        InlineKeyboardButton(text="⬅️ Главное меню", callback_data="main_menu")
    )
    
    return builder.as_markup()


def group_selection_kb(groups: list[str], action: str = "schedule") -> InlineKeyboardMarkup:
    """
    Create keyboard for group selection.
    
    Args:
        groups: List of available group names
        action: Action prefix for callback data
    """
    builder = InlineKeyboardBuilder()
    
    # Create buttons for each group (2 per row)
    for i in range(0, len(groups), 2):
        row_buttons = []
        for group in groups[i:i+2]:
            row_buttons.append(
                InlineKeyboardButton(
                    text=f"👥 {group}",
                    callback_data=f"{action}:select:{group}"
                )
            )
        builder.row(*row_buttons)
    
    # Back button
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="schedule:back")
    )
    
    return builder.as_markup()


def lesson_detail_kb(lesson_id: int, is_admin: bool = False) -> InlineKeyboardMarkup:
    """
    Create keyboard for lesson details.
    
    Args:
        lesson_id: ID of the lesson
        is_admin: Whether to show admin actions
    """
    builder = InlineKeyboardBuilder()
    
    if is_admin:
        builder.row(
            InlineKeyboardButton(text="✏️ Изменить", callback_data=f"lesson:edit:{lesson_id}"),
            InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"lesson:delete:{lesson_id}")
        )
    
    builder.row(
        InlineKeyboardButton(text="📍 Показать на карте", callback_data=f"lesson:map:{lesson_id}")
    )
    
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад к расписанию", callback_data="schedule:back")
    )
    
    return builder.as_markup()


def broadcast_confirmation_kb() -> InlineKeyboardMarkup:
    """Keyboard for broadcast message confirmation."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="✅ Отправить", callback_data="broadcast:confirm"),
        InlineKeyboardButton(text="❌ Отменить", callback_data="broadcast:cancel")
    )
    
    builder.row(
        InlineKeyboardButton(text="👁️ Предпросмотр", callback_data="broadcast:preview")
    )
    
    return builder.as_markup()


def admin_actions_kb() -> InlineKeyboardMarkup:
    """Admin panel action keyboard."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="📤 Загрузить расписание", callback_data="admin:upload"),
        InlineKeyboardButton(text="✏️ Редактировать", callback_data="admin:edit")
    )
    
    builder.row(
        InlineKeyboardButton(text="📢 Рассылка", callback_data="admin:broadcast"),
        InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")
    )
    
    builder.row(
        InlineKeyboardButton(text="🗑️ Очистить кэш", callback_data="admin:clear_cache")
    )
    
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")
    )
    
    return builder.as_markup()


def pagination_kb(
    current_page: int,
    total_pages: int,
    callback_prefix: str = "page"
) -> InlineKeyboardMarkup:
    """Pagination keyboard for long lists."""
    builder = InlineKeyboardBuilder()
    
    buttons = []
    
    if current_page > 1:
        buttons.append(
            InlineKeyboardButton(text="⬅️", callback_data=f"{callback_prefix}:{current_page - 1}")
        )
    
    buttons.append(
        InlineKeyboardButton(text=f"{current_page} / {total_pages}", callback_data="noop")
    )
    
    if current_page < total_pages:
        buttons.append(
            InlineKeyboardButton(text="➡️", callback_data=f"{callback_prefix}:{current_page + 1}")
        )
    
    builder.row(*buttons)
    
    return builder.as_markup()
