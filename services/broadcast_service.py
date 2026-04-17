from __future__ import annotations

import asyncio
import html
from datetime import datetime
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from locales import get_text
from models import Schedule, UserProfile


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
    ) -> dict[str, Any]:
        query = select(UserProfile).where(
            UserProfile.group_name == group_name,
            UserProfile.is_active == True,
        )
        result = await session.scalars(query)
        users = list(result)

        metrics: dict[str, Any] = {"sent": 0, "failed": 0, "deactivated": 0}

        messages_by_language: dict[str, list[UserProfile]] = {}
        for user in users:
            language = user.language or "ru"
            if language not in messages_by_language:
                messages_by_language[language] = []
            messages_by_language[language].append(user)

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
                    logger.debug("Sent notification to " + str(user.tg_id))
                except TelegramForbiddenError:
                    metrics["failed"] += 1
                    metrics["deactivated"] += 1
                    user.is_active = False
                    await session.flush()
                    logger.warning("User " + str(user.tg_id) + " blocked the bot, deactivated")
                except TelegramRetryAfter as e:
                    metrics["failed"] += 1
                    logger.warning("Flood limit for " + str(user.tg_id) + ", retry after " + str(e.retry_after) + "s")
                    await asyncio.sleep(e.retry_after)
                except Exception as e:
                    metrics["failed"] += 1
                    logger.error("Failed to notify " + str(user.tg_id) + ": " + str(e))

        await session.commit()
        logger.info("Broadcast for group=" + group_name + ", day=" + day + ": Sent=" + str(metrics["sent"]) + ", Failed=" + str(metrics["failed"]) + ", Deactivated=" + str(metrics["deactivated"]))

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
        for attempt in range(1, max_attempts + 1):
            try:
                await self._bot.send_message(chat_id=chat_id, text=text)
                return
            except TelegramForbiddenError:
                raise
            except Exception as error:
                if attempt >= max_attempts:
                    raise
                logger.debug("Send attempt " + str(attempt) + "/" + str(max_attempts) + " failed for " + str(chat_id) + ": " + str(error))
                await asyncio.sleep(attempt)

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
