"""
Admin Alert Service for real-time error notifications from audit_logs.
"""

from __future__ import annotations

from datetime import timedelta

from aiogram import Bot
from loguru import logger
from sqlalchemy import func, select

from database import AsyncSessionLocal
from models import AuditLog


class AdminAlertService:
    """Service for alerting admin about critical errors in audit_logs."""
    
    def __init__(self, bot: Bot, admin_id: int):
        self.bot = bot
        self.admin_id = admin_id
        self._last_check_time = None
    
    async def check_and_alert(self) -> None:
        """Check audit_logs for recent ERROR entries and send alert to admin."""
        try:
            async with AsyncSessionLocal() as session:
                # Find recent ERROR entries (last 5 minutes)
                result = await session.execute(
                    select(AuditLog)
                    .where(AuditLog.action.ilike("%ERROR%"))
                    .where(AuditLog.timestamp > func.now() - timedelta(minutes=5))
                    .order_by(AuditLog.timestamp.desc())
                    .limit(1)
                )
                error_log = result.scalar_one_or_none()
                
                if error_log:
                    # Avoid duplicate alerts for same error
                    if self._last_check_time and error_log.timestamp <= self._last_check_time:
                        return
                    
                    self._last_check_time = error_log.timestamp
                    
                    # Format and send alert
                    alert_message = (
                        f"🚨 <b>КРИТИЧЕСКАЯ ОШИБКА В СИСТЕМЕ</b>\n\n"
                        f"<b>Действие:</b> {self._escape_html(error_log.action)}\n"
                        f"<b>Пользователь:</b> {self._escape_html(error_log.full_name)} (ID: {error_log.tg_id})\n"
                        f"<b>Группа:</b> {self._escape_html(error_log.group_name)}\n"
                        f"<b>День:</b> {self._escape_html(error_log.day)}\n"
                        f"<b>Пара:</b> {error_log.lesson_num}\n"
                        f"<b>Время:</b> {error_log.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    )
                    
                    if error_log.old_value:
                        alert_message += f"\n<b>Старое значение:</b> <code>{self._escape_html(error_log.old_value)}</code>"
                    if error_log.new_value:
                        alert_message += f"\n<b>Новое значение:</b> <code>{self._escape_html(error_log.new_value)}</code>"
                    
                    await self.bot.send_message(
                        chat_id=self.admin_id,
                        text=alert_message,
                        parse_mode="HTML"
                    )
                    logger.warning(f"Admin alerted about error: {error_log.action}")
                    
        except Exception as e:
            logger.exception("Failed to check audit_logs and send alert")
    
    @staticmethod
    def _escape_html(text: str | None) -> str:
        """Escape HTML special characters."""
        if not text:
            return "—"
        return (
            text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
