from __future__ import annotations

import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, KeyboardButton, ReplyKeyboardMarkup
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger
from uvicorn import Config, Server

from api.main_api import app as api_app
from config import load_config
from database import create_engine_and_sessionmaker, dispose_engine, health_check, init_database
from handlers.admin import router as admin_router
from handlers.student import router as student_router
from handlers.teacher import router as teacher_router
from middlewares.activity_middleware import ActivityMiddleware
from middlewares.debounce import DebounceMiddleware, RateLimitMiddleware
from middlewares.role_middleware import RoleMiddleware, ServiceMiddleware
from models import AuditLog, NotificationQueue, ScheduleV2, UserProfile
from services.alert_service import AdminAlertService
from services.notification_worker import NotificationWorker
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


async def run_bot(
    config,
    session_factory,
    engine,
    notification_worker: NotificationWorker,
) -> None:
    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    storage = MemoryStorage()
    dispatcher = Dispatcher(storage=storage)

    # ── Error handler ──────────────────────────────────────────────────────────
    error_handler = setup_exception_handlers(bot, set(config.superadmin_ids))
    dispatcher.errors.register(error_handler)

    # ── Outer middleware (applied to every update) ─────────────────────────────
    dispatcher.update.outer_middleware(ActivityMiddleware())
    dispatcher.update.outer_middleware(RoleMiddleware(config))
    dispatcher.update.outer_middleware(ServiceMiddleware(session_factory, config))

    # ── Inner middleware: RateLimit then Debounce ──────────────────────────────
    # RateLimitMiddleware is registered first so hard-blocked users are dropped
    # immediately.  DebounceMiddleware runs second for softer dedup protection.
    dispatcher.message.middleware(RateLimitMiddleware(max_requests=30, window_seconds=60))
    dispatcher.message.middleware(DebounceMiddleware(ttl_seconds=0.5))
    dispatcher.callback_query.middleware(DebounceMiddleware(ttl_seconds=0.3))

    # ── Routers ────────────────────────────────────────────────────────────────
    dispatcher.include_router(student_router)
    dispatcher.include_router(teacher_router)
    dispatcher.include_router(admin_router)

    # ── Admin alert + APScheduler ──────────────────────────────────────────────
    # Resolve the first superadmin ID for alerts; fall back gracefully.
    admin_id: int | None = config.superadmin_ids[0] if config.superadmin_ids else None
    alert_service: AdminAlertService | None = None
    scheduler = AsyncIOScheduler(timezone="Asia/Almaty")

    if admin_id:
        alert_service = AdminAlertService(bot=bot, admin_id=admin_id)
        # check_errors_job runs every 5 minutes
        scheduler.add_job(
            alert_service.check_and_alert,
            trigger="interval",
            minutes=5,
            id="check_errors_job",
            replace_existing=True,
        )
        logger.info(f"AdminAlertService initialized for admin_id={admin_id}")
    else:
        logger.warning("No superadmin_ids configured — AdminAlertService disabled")

    # ── Startup / Shutdown hooks ───────────────────────────────────────────────
    @dispatcher.startup()
    async def on_startup() -> None:
        # Verify DB is reachable before accepting updates
        if not await health_check():
            logger.error("Database health check FAILED on startup!")
        else:
            logger.info("Database health check passed ✓")

        scheduler.start()
        logger.info("APScheduler started ✓")

        await set_commands(bot)
        logger.info("Bot commands registered ✓")
        logger.info("Bot started successfully 🚀")

    @dispatcher.shutdown()
    async def on_shutdown() -> None:
        logger.info("Shutting down scheduler...")
        scheduler.shutdown(wait=False)

        logger.info("Disposing database engine...")
        await dispose_engine()

        logger.info("Closing bot session...")
        await bot.session.close()

        logger.info("Graceful shutdown complete ✓")

    try:
        await dispatcher.start_polling(bot)
    finally:
        # Fallback in case shutdown hook didn't fire
        if scheduler.running:
            scheduler.shutdown(wait=False)
        await bot.session.close()


async def run_api() -> None:
    port = int(os.getenv("PORT", "10000"))
    config_uvicorn = Config(app=api_app, host="0.0.0.0", port=port, log_level="info")
    server = Server(config_uvicorn)
    logger.info("API server started on port " + str(port))
    await server.serve()


async def monitor_worker(worker: NotificationWorker) -> None:
    """Monitor notification worker and log statistics periodically."""
    while True:
        await asyncio.sleep(300)  # Log stats every 5 minutes
        try:
            stats = await worker.get_stats()
            logger.info(f"Notification queue stats: {stats}")
        except Exception as e:
            logger.error(f"Failed to get notification stats: {e}")


async def main() -> None:
    setup_logging()
    logger.info("Starting application...")

    config = load_config()

    # Import all models so SQLAlchemy can discover them before create_all
    _ = (ScheduleV2, AuditLog, UserProfile, NotificationQueue)

    # Initialize DB (sets global _engine and _session_factory)
    engine, session_factory = create_engine_and_sessionmaker(config.database_url)
    await init_database(engine)
    logger.info("Database initialized ✓")

    # Shared Bot instance for the notification worker (polling creates its own)
    worker_bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    notification_worker = NotificationWorker(bot=worker_bot, session_factory=session_factory)
    await notification_worker.start()
    logger.info("Notification worker started ✓")

    try:
        await asyncio.gather(
            run_bot(config, session_factory, engine, notification_worker),
            run_api(),
            monitor_worker(notification_worker),
        )
    except Exception:
        logger.exception("Fatal error in main loop")
        raise
    finally:
        await notification_worker.stop()
        await worker_bot.session.close()
        # dispose_engine is also called inside on_shutdown hook; calling it
        # here is a no-op if _engine is already None.
        await dispose_engine()
        logger.info("Application stopped")


if __name__ == "__main__":
    asyncio.run(main())
