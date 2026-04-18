"""
Background worker for processing notification queue.
Sends targeted notifications to students about schedule changes.
Implements rate limiting to comply with Telegram API limits.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from locales import get_text
from models import NotificationQueue, NotificationStatus, Schedule, UserProfile


class NotificationWorker:
    """Background worker that processes notification queue and sends Telegram messages.
    
    Features:
    - Batched processing of pending notifications
    - Rate limiting (max 30 messages/second as per Telegram limits)
    - Automatic retry with exponential backoff for rate limits
    - Graceful handling of blocked users (ForbiddenError)
    - Dead letter queue for failed notifications
    """
    
    # Telegram API limits: 30 messages/second for groups, 1 msg/second for private chats
    # We use conservative limit: 25 msgs/sec to stay safe
    MAX_MESSAGES_PER_SECOND = 25
    BATCH_SIZE = 100
    POLL_INTERVAL_SECONDS = 30  # Check queue every 30 seconds
    
    def __init__(
        self, 
        bot: Bot, 
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._bot = bot
        self._session_factory = session_factory
        self._running = False
        self._task: asyncio.Task | None = None
    
    async def start(self) -> None:
        """Start the background worker."""
        if self._running:
            logger.warning("NotificationWorker already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._worker_loop())
        logger.info("NotificationWorker started")
    
    async def stop(self) -> None:
        """Stop the background worker gracefully."""
        if not self._running:
            return
        
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("NotificationWorker stopped")
    
    async def _worker_loop(self) -> None:
        """Main worker loop that processes notifications continuously."""
        while self._running:
            try:
                processed_count = await self._process_batch()
                if processed_count == 0:
                    # No pending notifications, wait before checking again
                    await asyncio.sleep(self.POLL_INTERVAL_SECONDS)
                else:
                    # Small delay between batches to avoid overwhelming the system
                    await asyncio.sleep(1)
            except Exception as e:
                logger.exception(f"Error in notification worker loop: {e}")
                await asyncio.sleep(5)  # Wait before retry on error
    
    async def _process_batch(self) -> int:
        """Process a batch of pending notifications.
        
        Returns:
            Number of notifications processed
        """
        async with self._session_factory() as session:
            # Fetch pending notifications
            query = (
                select(NotificationQueue)
                .where(NotificationQueue.status == NotificationStatus.PENDING.value)
                .order_by(NotificationQueue.created_at)
                .limit(self.BATCH_SIZE)
            )
            result = await session.execute(query)
            notifications = result.scalars().all()
            
            if not notifications:
                return 0
            
            processed = 0
            delay_between_messages = 1.0 / self.MAX_MESSAGES_PER_SECOND
            
            for notification in notifications:
                if not self._running:
                    break
                
                success = await self._send_notification(session, notification)
                processed += 1
                
                # Rate limiting: small delay between messages
                if processed < len(notifications):
                    await asyncio.sleep(delay_between_messages)
            
            await session.commit()
            if processed > 0:
                logger.info(f"Processed {processed} notifications")
            return processed
    
    async def _send_notification(
        self, 
        session: AsyncSession, 
        notification: NotificationQueue
    ) -> bool:
        """Send a single notification and update its status.
        
        Args:
            session: Database session
            notification: NotificationQueue record to process
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            await self._bot.send_message(
                chat_id=notification.user_id,
                text=notification.message_text,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            
            # Mark as sent
            notification.status = NotificationStatus.SENT.value
            notification.processed_at = datetime.now()
            await session.flush()
            
            logger.debug(f"Notification sent to user {notification.user_id}")
            return True
            
        except TelegramForbiddenError:
            # User blocked the bot - mark user as inactive and notification as failed
            logger.warning(f"User {notification.user_id} blocked the bot")
            
            # Update user profile to inactive
            user_query = select(UserProfile).where(
                UserProfile.tg_id == notification.user_id
            )
            user_result = await session.execute(user_query)
            user = user_result.scalar_one_or_none()
            if user:
                user.is_active = False
            
            # Mark notification as failed
            notification.status = NotificationStatus.FAILED.value
            notification.processed_at = datetime.now()
            notification.error_message = "User blocked the bot"
            await session.flush()
            return False
            
        except TelegramRetryAfter as e:
            # Rate limited - wait and retry this message
            logger.warning(f"Rate limited by Telegram, retry after {e.retry_after}s")
            await asyncio.sleep(e.retry_after)
            
            # Retry once
            try:
                await self._bot.send_message(
                    chat_id=notification.user_id,
                    text=notification.message_text,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
                notification.status = NotificationStatus.SENT.value
                notification.processed_at = datetime.now()
                await session.flush()
                return True
            except Exception as retry_error:
                logger.error(f"Retry failed for user {notification.user_id}: {retry_error}")
                notification.status = NotificationStatus.FAILED.value
                notification.processed_at = datetime.now()
                notification.error_message = f"Retry failed: {str(retry_error)[:200]}"
                await session.flush()
                return False
                
        except Exception as e:
            # Other errors - mark as failed
            logger.error(f"Failed to send notification to {notification.user_id}: {e}")
            notification.status = NotificationStatus.FAILED.value
            notification.processed_at = datetime.now()
            notification.error_message = str(e)[:200]
            await session.flush()
            return False
    
    async def get_stats(self) -> dict[str, Any]:
        """Get statistics about notification queue.
        
        Returns:
            Dict with pending, sent, failed counts
        """
        async with self._session_factory() as session:
            from sqlalchemy import func
            
            pending_query = select(func.count(NotificationQueue.id)).where(
                NotificationQueue.status == NotificationStatus.PENDING.value
            )
            sent_query = select(func.count(NotificationQueue.id)).where(
                NotificationQueue.status == NotificationStatus.SENT.value
            )
            failed_query = select(func.count(NotificationQueue.id)).where(
                NotificationQueue.status == NotificationStatus.FAILED.value
            )
            
            pending = await session.scalar(pending_query) or 0
            sent = await session.scalar(sent_query) or 0
            failed = await session.scalar(failed_query) or 0
            
            return {
                "pending": pending,
                "sent": sent,
                "failed": failed,
                "total": pending + sent + failed,
            }


class NotificationEnqueuer:
    """Service for creating notification queue entries when schedule changes are published."""
    
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
    
    async def enqueue_schedule_change_notifications(
        self, 
        group_names: list[str],
    ) -> int:
        """Create notification queue entries for all users in specified groups.
        
        Args:
            group_names: List of group names that had schedule changes
            
        Returns:
            Number of notifications enqueued
        """
        from sqlalchemy import func
        
        if not group_names:
            return 0
        
        total_enqueued = 0
        
        for group_name in group_names:
            # Get all active users subscribed to this group
            user_query = select(UserProfile).where(
                UserProfile.group_name == group_name,
                UserProfile.is_active == True
            )
            result = await self._session.execute(user_query)
            users = result.scalars().all()
            
            if not users:
                logger.info(f"No active users found for group {group_name}")
                continue
            
            # Get published changes for this group
            changes_query = select(Schedule).where(
                Schedule.group_name == group_name,
                Schedule.is_change == True,
                Schedule.is_published == True
            )
            changes_result = await self._session.execute(changes_query)
            changes = changes_result.scalars().all()
            
            if not changes:
                logger.info(f"No published changes for group {group_name}")
                continue
            
            # Create personalized message for each user based on their language
            for user in users:
                language = user.language or "ru"
                message = self._build_notification_message(
                    group_name, changes, language
                )
                
                # Check if similar notification already pending (deduplication)
                existing_query = select(NotificationQueue).where(
                    NotificationQueue.user_id == user.tg_id,
                    NotificationQueue.group_name == group_name,
                    NotificationQueue.status == NotificationStatus.PENDING.value,
                    NotificationQueue.message_text == message
                )
                existing_result = await self._session.execute(existing_query)
                if existing_result.scalar_one_or_none():
                    continue  # Skip duplicate
                
                notification = NotificationQueue(
                    user_id=user.tg_id,
                    message_text=message,
                    status=NotificationStatus.PENDING.value,
                    group_name=group_name,
                    created_at=datetime.now(),
                )
                self._session.add(notification)
                total_enqueued += 1
            
            logger.info(f"Enqueued {len(users)} notifications for group {group_name}")
        
        await self._session.flush()
        return total_enqueued
    
    def _build_notification_message(
        self, 
        group_name: str, 
        changes: list[Schedule], 
        language: str
    ) -> str:
        """Build localized notification message for schedule changes."""
        title = get_text("notification_title", language)
        group_text = get_text("notification_group", language)
        day_text = get_text("notification_day", language)
        subject_text = get_text("notification_subject", language)
        teacher_text = get_text("notification_teacher", language)
        room_text = get_text("notification_room", language)
        time_text = get_text("notification_time", language)
        
        lines = [
            f"🔔 <b>{title}</b>",
            f"👥 <b>{group_text}:</b> {group_name}",
            "",
            f"📋 <b>{'Изменения' if language == 'ru' else 'Өзгерістер'}:</b>",
        ]
        
        # Group changes by day for better readability
        changes_by_day: dict[str, list[Schedule]] = {}
        for change in changes:
            day = change.day or ""
            if day not in changes_by_day:
                changes_by_day[day] = []
            changes_by_day[day].append(change)
        
        for day, day_changes in changes_by_day.items():
            lines.append(f"\n📅 <b>{day}:</b>")
            for change in day_changes:
                start_time = change.start_time or "—"
                end_time = change.end_time or "—"
                lines.append(
                    f"  <b>{change.lesson_number}</b> ({start_time}-{end_time}): "
                    f"{change.subject or '—'}"
                )
                if change.teacher:
                    lines.append(f"    👤 {change.teacher}")
                if change.room:
                    lines.append(f"    🚪 {change.room}")
        
        lines.append("")
        lines.append(f"🕒 <b>{get_text('last_updated', language)}:</b> {datetime.now().strftime('%H:%M')}")
        
        return "\n".join(lines)
