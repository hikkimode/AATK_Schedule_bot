"""
Finite State Machine (FSM) states for complex admin workflows.
"""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class BroadcastState(StatesGroup):
    """
    States for broadcast message workflow.
    
    Flow:
    1. waiting_for_message -> User enters broadcast text
    2. waiting_for_target_groups -> User selects target groups
    3. waiting_for_confirmation -> User confirms or edits
    4. (optional) waiting_for_schedule -> User schedules for later
    """
    waiting_for_message = State()
    waiting_for_target_groups = State()
    waiting_for_confirmation = State()
    waiting_for_schedule = State()


class ScheduleEditState(StatesGroup):
    """
    States for editing schedule workflow.
    
    Flow:
    1. selecting_group -> Select which group's schedule
    2. selecting_day -> Select day of week
    3. selecting_lesson -> Select lesson number
    4. editing_field -> Edit specific field (subject/teacher/room)
    5. confirming_changes -> Confirm or discard changes
    """
    selecting_group = State()
    selecting_day = State()
    selecting_lesson = State()
    editing_field = State()
    entering_value = State()
    confirming_changes = State()


class ScheduleUploadState(StatesGroup):
    """
    States for uploading schedule workflow.
    
    Flow:
    1. selecting_upload_type -> Excel file or manual entry
    2. waiting_for_file -> Upload Excel file (if Excel selected)
    3. parsing_confirmation -> Confirm parsed data
    4. applying_changes -> Apply or discard
    """
    selecting_upload_type = State()
    waiting_for_file = State()
    parsing_confirmation = State()
    applying_changes = State()


class GroupManagementState(StatesGroup):
    """
    States for managing groups workflow.
    
    Flow:
    1. selecting_action -> Add, remove, or list groups
    2. entering_group_name -> Enter new group name
    3. confirming_deletion -> Confirm group removal
    """
    selecting_action = State()
    entering_group_name = State()
    confirming_deletion = State()


class UserSearchState(StatesGroup):
    """
    States for searching and managing users.
    
    Flow:
    1. entering_search_query -> Search by name, group, or ID
    2. viewing_results -> Select user from results
    3. managing_user -> View details, block/unblock, change group
    """
    entering_search_query = State()
    viewing_results = State()
    managing_user = State()


class SettingsState(StatesGroup):
    """
    States for bot settings configuration.
    """
    main_menu = State()
    editing_notification_time = State()
    editing_language = State()
    confirming_reset = State()


# Helper function to get state name for logging
def get_state_name(state: State) -> str:
    """Get human-readable state name."""
    state_map = {
        BroadcastState.waiting_for_message: "Ввод сообщения для рассылки",
        BroadcastState.waiting_for_target_groups: "Выбор групп для рассылки",
        BroadcastState.waiting_for_confirmation: "Подтверждение рассылки",
        BroadcastState.waiting_for_schedule: "Запланированная рассылка",
        
        ScheduleEditState.selecting_group: "Выбор группы",
        ScheduleEditState.selecting_day: "Выбор дня",
        ScheduleEditState.selecting_lesson: "Выбор пары",
        ScheduleEditState.editing_field: "Редактирование поля",
        ScheduleEditState.entering_value: "Ввод значения",
        ScheduleEditState.confirming_changes: "Подтверждение изменений",
        
        ScheduleUploadState.selecting_upload_type: "Выбор типа загрузки",
        ScheduleUploadState.waiting_for_file: "Ожидание файла",
        ScheduleUploadState.parsing_confirmation: "Подтверждение парсинга",
        ScheduleUploadState.applying_changes: "Применение изменений",
        
        GroupManagementState.selecting_action: "Выбор действия с группой",
        GroupManagementState.entering_group_name: "Ввод названия группы",
        GroupManagementState.confirming_deletion: "Подтверждение удаления",
        
        UserSearchState.entering_search_query: "Поиск пользователя",
        UserSearchState.viewing_results: "Просмотр результатов",
        UserSearchState.managing_user: "Управление пользователем",
        
        SettingsState.main_menu: "Настройки",
        SettingsState.editing_notification_time: "Настройка времени уведомлений",
        SettingsState.editing_language: "Выбор языка",
        SettingsState.confirming_reset: "Подтверждение сброса",
    }
    
    return state_map.get(state, str(state))
