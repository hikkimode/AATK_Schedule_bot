from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, KeyboardButton, ReplyKeyboardMarkup

from config import load_config
from database import create_engine_and_sessionmaker, init_database
from handlers.student import router as student_router
from handlers.teacher import router as teacher_router
from middlewares.role_middleware import RoleMiddleware, ServiceMiddleware


def build_main_menu(role: str) -> ReplyKeyboardMarkup:
    buttons: list[list[KeyboardButton]] = [
        [KeyboardButton(text="📚 Посмотреть расписание")],
    ]
    if role == "teacher":
        buttons.append([KeyboardButton(text="🛠 Управление расписанием")])
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        input_field_placeholder="Выберите действие",
    )


async def set_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Открыть главное меню"),
            BotCommand(command="cancel", description="Сбросить текущее действие"),
            BotCommand(command="teacher", description="Открыть панель преподавателя"),
        ]
    )


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    config = load_config()
    engine, session_factory = create_engine_and_sessionmaker(config.database_url)
    await init_database(engine)
    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.update.outer_middleware(RoleMiddleware(config))
    dispatcher.update.outer_middleware(ServiceMiddleware(session_factory, config))
    dispatcher.include_router(student_router)
    dispatcher.include_router(teacher_router)
    await set_commands(bot)
    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
