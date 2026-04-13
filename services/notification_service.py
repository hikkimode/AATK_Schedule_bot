from __future__ import annotations

import asyncio
import html
import logging
from datetime import datetime

from aiogram import Bot

from models import AuditLog


class NotificationService:
    def __init__(self, bot: Bot, superadmin_ids: set[int], logger: logging.Logger | None = None) -> None:
        self._bot = bot
        self._superadmin_ids = superadmin_ids
        self._logger = logger or logging.getLogger(__name__)

    async def notify_audit(self, audit_log: AuditLog) -> None:
        if not self._superadmin_ids:
            return
        text = self._build_audit_message(audit_log)
        for chat_id in self._superadmin_ids:
            await self._send_with_retry(chat_id, text)

    async def _send_with_retry(self, chat_id: int, text: str) -> None:
        for attempt in range(1, 4):
            try:
                await self._bot.send_message(chat_id=chat_id, text=text)
                return
            except Exception as error:
                self._logger.warning(
                    "Failed to send notification to %s on attempt %s: %s",
                    chat_id,
                    attempt,
                    error,
                )
                if attempt < 3:
                    await asyncio.sleep(attempt)

    def _build_audit_message(self, audit_log: AuditLog) -> str:
        timestamp = self._format_timestamp(audit_log.timestamp)
        old_value = html.escape(audit_log.old_value or "—")
        new_value = html.escape(audit_log.new_value or "—")
        return (
            "🔔 <b>Изменение расписания</b>\n"
            f"👤 <b>Кто:</b> {html.escape(audit_log.full_name)} ({audit_log.tg_id})\n"
            f"🛠 <b>Действие:</b> {html.escape(audit_log.action)}\n"
            f"👥 <b>Группа:</b> {html.escape(audit_log.group_name)}\n"
            f"📅 <b>День:</b> {html.escape(audit_log.day)}\n"
            f"🔢 <b>Пара:</b> {audit_log.lesson_num}\n"
            f"📥 <b>Было:</b>\n<code>{old_value}</code>\n"
            f"📤 <b>Стало:</b>\n<code>{new_value}</code>\n"
            f"🕒 <b>Время:</b> {timestamp}"
        )

    @staticmethod
    def _format_timestamp(value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M:%S")
