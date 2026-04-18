"""
Debounce middleware to prevent accidental double-clicks and spam.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from cachetools import TTLCache
from loguru import logger


class DebounceMiddleware(BaseMiddleware):
    """
    Middleware that prevents processing duplicate requests from the same user.
    Useful for preventing accidental double-clicks or spam.
    """
    
    def __init__(self, ttl_seconds: float = 1.0, maxsize: int = 1000):
        """
        Initialize debounce middleware.
        
        Args:
            ttl_seconds: Time window to ignore duplicate requests (default: 1 second)
            maxsize: Maximum number of entries in the cache
        """
        self.cache = TTLCache(maxsize=maxsize, ttl=ttl_seconds)
        self.ttl = ttl_seconds
        super().__init__()
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any]
    ) -> Any:
        """
        Check for duplicate requests and ignore if within debounce window.
        """
        # Get user ID from event
        user_id = self._get_user_id(event)
        event_type = event.__class__.__name__
        
        if user_id is None:
            # Can't identify user, proceed with handler
            return await handler(event, data)
        
        # Generate cache key based on event content
        cache_key = self._generate_cache_key(event, user_id, event_type)
        
        # Check if this is a duplicate request
        if cache_key in self.cache:
            logger.debug(f"Debounce: Ignoring duplicate request from user {user_id}")
            
            # For callbacks, answer to prevent "loading" state
            if isinstance(event, CallbackQuery):
                try:
                    await event.answer("⏳ Пожалуйста, подождите...", show_alert=False)
                except Exception:
                    pass
            
            return None  # Ignore this request
        
        # Mark this request as processed
        self.cache[cache_key] = True
        
        # Proceed with handler
        return await handler(event, data)
    
    def _get_user_id(self, event: TelegramObject) -> int | None:
        """Extract user ID from event."""
        if isinstance(event, Message):
            return event.from_user.id if event.from_user else None
        elif isinstance(event, CallbackQuery):
            return event.from_user.id if event.from_user else None
        return None
    
    def _generate_cache_key(
        self,
        event: TelegramObject,
        user_id: int,
        event_type: str
    ) -> str:
        """Generate unique cache key for the event."""
        # For text messages, include message text in key
        if isinstance(event, Message) and event.text:
            return f"{user_id}:{event_type}:{event.text[:50]}"
        
        # For callback queries, include callback data
        elif isinstance(event, CallbackQuery) and event.data:
            return f"{user_id}:{event_type}:{event.data}"
        
        # Default key for other events
        return f"{user_id}:{event_type}:{id(event)}"


class RateLimitMiddleware(BaseMiddleware):
    """
    Rate limiting middleware to prevent abuse.
    Tracks requests per user and enforces limits.
    """
    
    def __init__(
        self,
        max_requests: int = 30,
        window_seconds: float = 60.0,
        block_duration: float = 300.0
    ):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum requests per window
            window_seconds: Time window for counting requests
            block_duration: How long to block if limit exceeded
        """
        self.max_requests = max_requests
        self.window = window_seconds
        self.block_duration = block_duration
        
        # Separate caches for counting and blocking
        self.request_counts = TTLCache(maxsize=1000, ttl=window_seconds)
        self.blocked_users = TTLCache(maxsize=100, ttl=block_duration)
        
        super().__init__()
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any]
    ) -> Any:
        """Check rate limits before processing."""
        user_id = self._get_user_id(event)
        
        if user_id is None:
            return await handler(event, data)
        
        # Check if user is blocked
        if user_id in self.blocked_users:
            logger.warning(f"Rate limit: Blocked user {user_id} attempted request")
            
            if isinstance(event, Message):
                await event.answer(
                    "⛔ Вы превысили лимит запросов. Пожалуйста, подождите 5 минут."
                )
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    "⛔ Лимит запросов превышен", show_alert=True
                )
            
            return None
        
        # Count requests
        current_count = self.request_counts.get(user_id, 0) + 1
        self.request_counts[user_id] = current_count
        
        # Check if limit exceeded
        if current_count > self.max_requests:
            self.blocked_users[user_id] = True
            logger.warning(f"Rate limit: User {user_id} blocked for exceeding {self.max_requests} requests")
            
            if isinstance(event, Message):
                await event.answer(
                    f"⛔ Превышен лимит запросов ({self.max_requests} в минуту). "
                    f"Доступ заблокирован на 5 минут."
                )
            
            return None
        
        return await handler(event, data)
    
    def _get_user_id(self, event: TelegramObject) -> int | None:
        """Extract user ID from event."""
        if isinstance(event, Message):
            return event.from_user.id if event.from_user else None
        elif isinstance(event, CallbackQuery):
            return event.from_user.id if event.from_user else None
        return None
