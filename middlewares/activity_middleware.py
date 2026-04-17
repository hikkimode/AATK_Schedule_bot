from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

logger = logging.getLogger(__name__)


class ActivityMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        user_id = getattr(user, "id", None)
        payload = ''
        if hasattr(event, "text"):
            payload = event.text
        elif hasattr(event, "data"):
            payload = event.data
        logger.info("user_id=%s event=%s payload=%s", user_id, type(event).__name__, payload)
        return await handler(event, data)
