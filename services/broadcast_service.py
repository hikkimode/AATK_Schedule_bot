"""
Broadcast notification service for schedule changes.
Sends localized notifications to users when their group's schedule changes.
"""

from __future__ import annotations

import asyncio
import html
import logging
from datetime import datetime

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from sqlalchemy.ext.asyncio import AsyncSession

from locales import get_text
from models import Schedule, UserProfile

logger = logging.getLogger(__name__)


class BroadcastService:
    ADMIN_IDS: list[int] = [7748463140]

    def __init__(self, bot: Bot, admin_ids: list[int] | None = None) -> None:
        self._bot = bot
        self._admin_ids = admin_ids if admin_ids is not None else list(self.ADMIN_IDS)

    async def broadcast_schedule_changes(
        self,
        session: AsyncSession,
        group_name: str,
        day: str,
        changes: list[Schedule],
    ) -> dict[str, int]:
        """
        Broadcast notifications about schedule changes to all users in a group.
        
        Args:
            session: AsyncSession for DB queries
            group_name: The group affected by changes
            day: The day of the week with changes
            changes: List of Schedule objects that were changed
        
        Returns:
            dict with keys 'sent' and 'failed' for metrics
        """
        # Fetch all users subscribed to this group
        from sqlalchemy import select
        
        query = select(UserProfile).where(UserProfile.group_name == group_name)
        result = await session.scalars(query)
        users = list(result)
        
        metrics = {"sent": 0, "failed": 0}
        
        # Group changes by language to aggregate messages
        messages_by_language: dict[str, list[dict]] = {}
        for user in users:
            language = user.language or "ru"
            if language not in messages_by_language:
                messages_by_language[language] = []
            messages_by_language[language].append(user)
        
        # Send aggregated message per language group
        for language, language_users in messages_by_language.items():
            message = self._build_change_notification(
                group_name=group_name,
                day=day,
                changes=changes,
                language=language,
            )
            
            for user in language_users:
                try:
                    await self._send_with_retry(user.tg_id, message)
                    metrics["sent"] += 1
                    logger.debug(f"Sent notification to {user.tg_id}")
                except TelegramForbiddenError:
                    metrics["failed"] += 1
                    logger.warning(f"User {user.tg_id} blocked the bot or deleted account")
                except TelegramRetryAfter as e:
                    metrics["failed"] += 1
                    logger.warning(f"Flood limit for {user.tg_id}, retry after {e.retry_after}s")
                    await asyncio.sleep(e.retry_after)
                except Exception as e:
                    metrics["failed"] += 1
                    logger.error(f"Failed to notify {user.tg_id}: {e}")
        
        logger.info(f"Broadcast for group={group_name}, day={day}: Sent={metrics['sent']}, Failed={metrics['failed']}")

        admin_message = self._build_admin_monitor_message(
            group_name=group_name,
            day=day,
            user_count=len(users),
            metrics=metrics,
            preview_text=self._build_change_notification(
                group_name=group_name,
                day=day,
                changes=changes,
                language="ru",
            ),
        )
        asyncio.create_task(self._notify_admins(admin_message))

        return metrics

    async def _notify_admins(self, message: str) -> None:
        if not self._admin_ids:
            return
        for admin_id in self._admin_ids:
            try:
                await self._bot.send_message(chat_id=admin_id, text=message)
            except Exception as exc:
                logger.warning(f"Failed to notify admin {admin_id}: {exc}")

    async def _send_with_retry(self, chat_id: int, text: str, max_attempts: int = 3) -> None:
        """Send message with exponential backoff retry."""
        for attempt in range(1, max_attempts + 1):
            try:
                await self._bot.send_message(chat_id=chat_id, text=text)
                return
            except Exception as error:
                if attempt >= max_attempts:
                    raise
                logger.debug(f"Send attempt {attempt}/{max_attempts} failed for {chat_id}: {error}")
                await asyncio.sleep(attempt)  # Exponential backoff

    def _build_admin_monitor_message(
        self,
        group_name: str,
        day: str,
        user_count: int,
        metrics: dict[str, int],
        preview_text: str,
    ) -> str:
        lines = [
            "📢 [ADMIN MONITOR] Выполнена рассылка изменений.",
            f"Группа: {html.escape(group_name)}",
            f"День: {html.escape(day)}",
        ]
        if user_count == 0:
            lines.append("Изменения импортированы, но подписчиков у группы нет.")
        else:
            lines.extend([
                f"Подписчиков: {user_count}",
                f"Отправлено: {metrics.get('sent', 0)}",
                f"Ошибок: {metrics.get('failed', 0)}",
            ])
        lines.extend([
            "",
            "📌 Превью сообщения студентам:",
            preview_text,
        ])
        return "\n".join(lines)

    def _build_change_notification(
        self,
        group_name: str,
        day: str,
        changes: list[Schedule],
        language: str,
    ) -> str:
        """Build a localized notification message for schedule changes."""
        title = get_text("notification_title", language)
        day_text = get_text("notification_day", language)
        group_text = get_text("notification_group", language)
        subject_text = get_text("notification_subject", language)
        teacher_text = get_text("notification_teacher", language)
        room_text = get_text("notification_room", language)
        time_text = get_text("notification_time", language)
        
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        updated_text = get_text("last_updated", language)
        
        lines = [
            f"🔔 <b>{title}</b>",
            f"👥 <b>{group_text}:</b> {html.escape(group_name)}",
            f"📅 <b>{day_text}:</b> {html.escape(day)}",
            "",
            "📋 <b>Изменения:</b>" if language == "ru" else "📋 <b>Өзгерістер:</b>",
        ]
        
        for idx, lesson in enumerate(changes, start=1):
            start_time = lesson.start_time or "—"
            end_time = lesson.end_time or "—"
            lines.extend([
                f"{idx}. <b>Пара {lesson.lesson_number}</b> ({start_time} - {end_time})",
                f"   {subject_text}: {html.escape(lesson.subject or '—')}",
                f"   {teacher_text}: {html.escape(lesson.teacher or '—')}",
                f"   {room_text}: {html.escape(lesson.room or '—')}",
            ])
        
        lines.extend([
            "",
            f"🕒 <b>{updated_text}:</b> {timestamp}",
        ])
        
        return "\n".join(lines)
