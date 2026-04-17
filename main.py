from __future__ import annotations

import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, KeyboardButton, ReplyKeyboardMarkup
from aiohttp import web
from loguru import logger

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


async def healthcheck(_: web.Request) -> web.Response:
    return web.Response(text="ok")


async def start_healthcheck_server() -> tuple[web.AppRunner, web.TCPSite]:
    app = web.Application()
    app.router.add_get("/", healthcheck)
    app.router.add_get("/health", healthcheck)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", "10000"))
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()
    return runner, site


async def main() -> None:
    # Настройка структурированного логирования
    setup_logging()
    logger.info("Starting bot...")

    config = load_config()
    _ = (Schedule, AuditLog, UserProfile)

    engine, session_factory = create_engine_and_sessionmaker(config.database_url)
    await init_database(engine)
    logger.info("Database initialized")

    healthcheck_runner, _ = await start_healthcheck_server()

    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    storage = MemoryStorage()
    dispatcher = Dispatcher(storage=storage)

    # Глобальный обработчик ошибок
    error_handler = setup_exception_handlers(bot, set(config.superadmin_ids))
    dispatcher.errors.register(error_handler)

    # Middleware
    dispatcher.update.outer_middleware(ActivityMiddleware())
    dispatcher.update.outer_middleware(RoleMiddleware(config))
    dispatcher.update.outer_middleware(ServiceMiddleware(session_factory, config))

    dispatcher.include_router(student_router)
    dispatcher.include_router(teacher_router)

    await set_commands(bot)
    logger.info("Bot started successfully")

    try:
        await dispatcher.start_polling(bot)
    except Exception as e:
        logger.exception("Fatal error in main loop")
        raise
    finally:
        await bot.session.close()
        await healthcheck_runner.cleanup()
        await engine.dispose()
        logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
