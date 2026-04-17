from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from config import Config
from services.audit_service import AuditService, ScheduleService
from services.broadcast_service import BroadcastService
from services.notification_service import NotificationService


class RoleMiddleware(BaseMiddleware):
    def __init__(self, config: Config) -> None:
        self._teacher_ids = set(config.teacher_ids)
        self._superadmin_ids = set(config.superadmin_ids)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        user_id = getattr(user, "id", None)
        is_superadmin = isinstance(user_id, int) and user_id in self._superadmin_ids
        is_teacher = isinstance(user_id, int) and (user_id in self._teacher_ids or is_superadmin)
        data["role"] = "teacher" if is_teacher else "student"
        data["is_teacher"] = is_teacher
        data["is_superadmin"] = is_superadmin
        return await handler(event, data)


class ServiceMiddleware(BaseMiddleware):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], config: Config) -> None:
        self._session_factory = session_factory
        self._config = config

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        bot: Bot = data["bot"]
        async with self._session_factory() as session:
            # Initialize all services
            notification_service = NotificationService(bot=bot, superadmin_ids=set(self._config.superadmin_ids))
            broadcast_service = BroadcastService(bot=bot)
            schedule_service = ScheduleService(session)
            audit_service = AuditService(session, notification_service)
            
            # Try to load user language from database (for existing profiles)
            user = data.get("event_from_user")
            user_id = getattr(user, "id", None)
            user_language = "ru"  # Default language
            if isinstance(user_id, int):
                profile = await schedule_service.get_user_profile(user_id)
                if profile and profile.language:
                    user_language = profile.language
            
            # Inject services into data dictionary for handlers
            data["session"] = session
            data["schedule_service"] = schedule_service
            data["audit_service"] = audit_service
            data["notification_service"] = notification_service
            data["broadcast_service"] = broadcast_service
            data["config"] = self._config
            data["user_language"] = user_language
            
            return await handler(event, data)
