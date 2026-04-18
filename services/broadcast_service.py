from __future__ import annotations

from datetime import datetime

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import NotificationQueue, NotificationStatus, UserProfile


class BroadcastService:
    """Service to handle mass broadcast messaging from the Dashboard."""

    async def schedule_broadcast(
        self, session: AsyncSession, message: str, groups: list[str], subgroup: int | None = None
    ) -> int:
        """
        Schedule a broadcast message for all users in the target groups.
        We do this by inserting records into notification_queue. The NotificationWorker
        will process them, respecting rate limits and handling blocked bots gracefully.
        
        Args:
            session: SQLAlchemy async session
            message: Text of the message to broadcast
            groups: List of target group names
            
        Returns:
            Number of notification messages queued
        """
        if not groups:
            return 0

        # Fetch all active users for the requested groups
        query = select(UserProfile.tg_id, UserProfile.group_name).where(
            UserProfile.group_name.in_(groups),
            UserProfile.is_active == True,
        )
        
        # Apply subgroup filter if provided
        # 0 (target) -> only those with 0? 
        # Usually broadcast with subgroup X means ONLY those in X.
        if subgroup is not None:
            query = query.where(UserProfile.subgroup == subgroup)
            
        result = await session.execute(query)
        users = result.fetchall()

        if not users:
            logger.info("No active users found for broadcast in groups: %s", groups)
            return 0

        # Build notification queue items
        queued_count = 0
        now = datetime.now()
        for tg_id, user_group in users:
            notification = NotificationQueue(
                user_id=tg_id,
                message_text=message,
                status=NotificationStatus.PENDING.value,
                group_name=user_group,
                created_at=now,
            )
            session.add(notification)
            queued_count += 1

        await session.commit()
        logger.info(
            "Successfully scheduled broadcast for %s users across %s groups",
            queued_count,
            len(groups),
        )
        return queued_count

    async def notify_update(self, group: str, text: str, subgroup: int | None = None) -> None:
        """
        Background task helper to create an update broadcast.
        """
        from database import AsyncSessionLocal
        try:
            async with AsyncSessionLocal() as session:
                await self.schedule_broadcast(session, text, [group], subgroup=subgroup)
        except Exception as e:
            logger.error(f"Failed to notify update for {group}: {e}")
