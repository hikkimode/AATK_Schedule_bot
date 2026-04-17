from __future__ import annotations

from datetime import datetime
from typing import Any

from loguru import logger
from sqlalchemy import delete, select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from models import AuditLog, BaseSchedule, Schedule


class ResetService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def full_reset(
        self,
        tg_id: int,
        full_name: str,
    ) -> dict[str, int]:
        base_count = await self._session.scalar(
            select(func.count(BaseSchedule.id))
        ) or 0

        if base_count == 0:
            raise ValueError("Base schedule not found. Import primary Excel first.")

        current_count = await self._session.scalar(
            select(func.count(Schedule.id))
        ) or 0

        try:
            await self._session.execute(delete(Schedule))

            await self._session.execute(
                text("""
                    INSERT INTO schedule (
                        group_name, day, lesson_number, subject, teacher,
                        room, start_time, end_time, raw_text, is_change
                    )
                    SELECT
                        group_name, day, lesson_number, subject, teacher,
                        room, start_time, end_time, raw_text, 0
                    FROM base_schedule
                """)
            )

            audit_log = AuditLog(
                tg_id=tg_id,
                full_name=full_name,
                action="reset_to_base",
                group_name="*",
                day="*",
                lesson_num=0,
                old_value=f"Deleted {current_count} records",
                new_value=f"Restored {base_count} records from base_schedule",
                timestamp=datetime.now(),
            )
            self._session.add(audit_log)

            await self._session.commit()

            logger.info(
                f"Reset completed: deleted {current_count} records, "
                f"restored {base_count} from base_schedule"
            )

            return {"deleted": current_count, "restored": base_count}

        except Exception:
            await self._session.rollback()
            raise
