from __future__ import annotations

import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, KeyboardButton, ReplyKeyboardMarkup
from loguru import logger
from uvicorn import Config, Server

from api.main_api import app as api_app
from config import load_config
from database import create_engine_and_sessionmaker, init_database
from handlers.student import router as student_router
from handlers.teacher import router as teacher_router
from middlewares.activity_middleware import ActivityMiddleware
from middlewares.role_middleware import RoleMiddleware, ServiceMiddleware
from models import AuditLog, Schedule, UserProfile
from utils.exceptions import setup_exception_handlers, setup_logging


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


async def run_bot(config, session_factory, engine) -> None:
    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    storage = MemoryStorage()
    dispatcher = Dispatcher(storage=storage)

    error_handler = setup_exception_handlers(bot, set(config.superadmin_ids))
    dispatcher.errors.register(error_handler)

    dispatcher.update.outer_middleware(ActivityMiddleware())
    dispatcher.update.outer_middleware(RoleMiddleware(config))
    dispatcher.update.outer_middleware(ServiceMiddleware(session_factory, config))

    dispatcher.include_router(student_router)
    dispatcher.include_router(teacher_router)

    await set_commands(bot)
    logger.info("Bot started successfully")

    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()


async def run_api() -> None:
    port = int(os.getenv("PORT", "10000"))
    config_uvicorn = Config(app=api_app, host="0.0.0.0", port=port, log_level="info")
    server = Server(config_uvicorn)
    logger.info("API server started on port " + str(port))
    await server.serve()


async def main() -> None:
    setup_logging()
    logger.info("Starting application...")

    config = load_config()
    _ = (Schedule, AuditLog, UserProfile)

    engine, session_factory = create_engine_and_sessionmaker(config.database_url)
    await init_database(engine)
    logger.info("Database initialized")

    try:
        await asyncio.gather(
            run_bot(config, session_factory, engine),
            run_api(),
        )
    except Exception as e:
        logger.exception("Fatal error in main loop")
        raise
    finally:
        await engine.dispose()
        logger.info("Application stopped")


if __name__ == "__main__":
    asyncio.run(main())
