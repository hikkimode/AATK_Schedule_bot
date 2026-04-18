"""
Centralized localization module for RU and KK languages.
Provides a single source of truth for all UI strings, messages, and notifications.
"""

from __future__ import annotations

from typing import Literal

SUPPORTED_LANGUAGES = {"ru", "kk"}
DEFAULT_LANGUAGE: Literal["ru", "kk"] = "ru"


TRANSLATIONS = {
    "ru": {
        # Welcome & Navigation
        "welcome": "Выберите язык интерфейса.",
        "welcome_teacher": "Выберите язык интерфейса.\nДля панели преподавателя используйте команду /teacher.",
        "language_ru": "Русский",
        "language_kz": "Қазақша",
        
        # Main Menu
        "main_menu_schedule": "📚 Посмотреть расписание",
        "main_menu_manage": "🛠 Управление расписанием",
        
        # Group & Day Selection
        "choose_group": "Выберите группу.",
        "choose_day": "Выберите день недели.",
        "choose_day_button": "Выбрать день",
        "change_group": "Сменить группу",
        "choose_group_button": "Выбрать группу",
        "choose_subgroup": "Выберите подгруппу.",
        "subgroup_all": "Весь поток (общие)",
        "subgroup_1": "1 подгруппа",
        "subgroup_2": "2 подгруппа",
        "subgroup_prefix": "Подгруппа",
        "subgroup_none": "Не выбрана",
        
        # Quick Actions
        "today": "Сегодня",
        "tomorrow": "Завтра",
        
        # Navigation
        "back_groups": "К группам",
        "back_days": "К дням",
        
        # Schedule Display
        "schedule_title": "Расписание",
        "group": "Группа",
        "day": "День",
        "subject": "Предмет",
        "teacher": "Преподаватель",
        "room": "Кабинет",
        "time": "Время",
        "changed": "Есть изменение",
        "last_updated": "Последнее обновление",
        
        # Empty States
        "empty_schedule": "На этот день расписание не найдено.",
        "no_schedule_loaded": "Ошибка: Расписание еще не загружено в систему",
        "no_lessons_today": "😴 Нет пар на сегодня — отдыхаем!",
        "no_lessons_tomorrow": "😴 Нет пар на завтра — отдыхаем!",
        "no_lessons": "😴 На этот день нет пар.",
        
        # Notifications
        "notification_title": "🔔 Изменение расписания",
        "notification_group": "👥 Группа",
        "notification_day": "📅 День",
        "notification_lesson": "🔢 Пара",
        "notification_subject": "📘 Предмет",
        "notification_teacher": "👩‍🏫 Преподаватель",
        "notification_room": "🏫 Кабинет",
        "notification_time": "🕒 Время",
        
        # System Messages
        "action_saved": "✅ Сохранено.",
        "action_cancelled": "❌ Отменено.",
        "current_action_reset": "Текущее действие сброшено. Используйте /start или /teacher.",
        "database_error": "❌ Ошибка при обработке. Обратитесь администратору.",
        
        # Import & File Operations
        "import_title": "📥 Импорт изменений из Excel",
        "import_instructions": "Отправьте файл <b>.xlsx</b> прямо в этот чат.",
        "import_expected_columns": "Ожидаемые колонки:",
        "import_success": "📥 Импорт изменений завершён",
        "import_updated_rows": "✅ Обновлено строк",
        "import_updated_groups": "📚 Группы с изменениями",
        "import_skipped_rows": "⚠️ Пропущено строк",
        "import_errors": "📝 Что не удалось обработать",
    },
    "kz": {
        # Welcome & Navigation
        "welcome": "Интерфейс тілін таңдаңыз.",
        "welcome_teacher": "Интерфейс тілін таңдаңыз.\nОқытушы панелі үшін /teacher пәрменін пайдаланыңыз.",
        "language_ru": "Русский",
        "language_kz": "Қазақша",
        
        # Main Menu
        "main_menu_schedule": "📚 Сабақ кестесін қарау",
        "main_menu_manage": "🛠 Кестені басқару",
        
        # Group & Day Selection
        "choose_group": "Топты таңдаңыз.",
        "choose_day": "Апта күнін таңдаңыз.",
        "choose_day_button": "Күнді таңдау",
        "change_group": "Топты өзгерту",
        "choose_group_button": "Топты таңдау",
        "choose_subgroup": "Топшаны таңдаңыз.",
        "subgroup_all": "Жалпы топ",
        "subgroup_1": "1 топша",
        "subgroup_2": "2 топша",
        "subgroup_prefix": "Топша",
        "subgroup_none": "Таңдалмаған",
        
        # Quick Actions
        "today": "Бүгін",
        "tomorrow": "Ертең",
        
        # Navigation
        "back_groups": "Топтарға",
        "back_days": "Күндерге",
        
        # Schedule Display
        "schedule_title": "Сабақ кестесі",
        "group": "Топ",
        "day": "Күн",
        "subject": "Пән",
        "teacher": "Оқытушы",
        "room": "Кабинет",
        "time": "Уақыт",
        "changed": "Өзгеріс бар",
        "last_updated": "Соңғы жаңарту",
        
        # Empty States
        "empty_schedule": "Бұл күнге сабақ кестесі табылмады.",
        "no_schedule_loaded": "Қате: Сабақ кестесі әлі жүктелмеген",
        "no_lessons_today": "😴 Бүгін сабақ жоқ — демалыңыз!",
        "no_lessons_tomorrow": "😴 Ертең сабақ жоқ — демалыңыз!",
        "no_lessons": "😴 Бұл күнге сабақ жоқ.",
        
        # Notifications
        "notification_title": "🔔 Кестеде өзгеріс",
        "notification_group": "👥 Топ",
        "notification_day": "📅 Күн",
        "notification_lesson": "🔢 Сабақ нөмері",
        "notification_subject": "📘 Пән",
        "notification_teacher": "👩‍🏫 Оқытушы",
        "notification_room": "🏫 Кабинет",
        "notification_time": "🕒 Уақыт",
        
        # System Messages
        "action_saved": "✅ Сохранено.",
        "action_cancelled": "❌ Бас тартылды.",
        "current_action_reset": "Ағымды әрекет сброшено. /start немесе /teacher пайдаланыңыз.",
        "database_error": "❌ Өңдеу кезінде қате. Әкімшіге хабарлаңыз.",
        
        # Import & File Operations
        "import_title": "📥 Excel-ден өзгерістер импорты",
        "import_instructions": "<b>.xlsx</b> файлын осы чатқа жібіңіз.",
        "import_expected_columns": "Күтілетін бағандар:",
        "import_success": "📥 Өзгерістер импорты аяқталды",
        "import_updated_rows": "✅ Жаңартылған жолдар",
        "import_updated_groups": "📚 Өзгерті бар топтар",
        "import_skipped_rows": "⚠️ Өткізіп салынған жолдар",
        "import_errors": "📝 Өңделмеген ішіндіктер",
    },
}


def get_text(key: str, language: str | None = None) -> str:
    """
    Get localized text by key and language.
    Falls back to DEFAULT_LANGUAGE if not found.
    
    Args:
        key: Translation key
        language: Language code (ru/kk). Defaults to DEFAULT_LANGUAGE if None or invalid.
    
    Returns:
        Translated string or the key itself if not found.
    """
    if language is None or language not in SUPPORTED_LANGUAGES:
        language = DEFAULT_LANGUAGE
    
    return TRANSLATIONS.get(language, {}).get(key, TRANSLATIONS.get(DEFAULT_LANGUAGE, {}).get(key, key))


def get_all_translations(language: str | None = None) -> dict[str, str]:
    """Get all translations for a given language."""
    if language is None or language not in SUPPORTED_LANGUAGES:
        language = DEFAULT_LANGUAGE
    return TRANSLATIONS.get(language, TRANSLATIONS[DEFAULT_LANGUAGE])
