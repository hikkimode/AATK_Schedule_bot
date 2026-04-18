from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class StudentStates(StatesGroup):
    language = State()
    group = State()
    subgroup = State()
    day = State()


class TeacherStates(StatesGroup):
    group = State()
    day = State()
    lesson = State()
    action = State()
    import_file = State()
    subject = State()
    teacher = State()
    room = State()
    start_time = State()
    end_time = State()
