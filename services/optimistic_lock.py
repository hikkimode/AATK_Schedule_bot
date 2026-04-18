"""
Optimistic locking service for handling concurrent edits.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import ScheduleV2

T = TypeVar("T")


class ConflictError(Exception):
    """Raised when optimistic locking detects a conflict."""
    
    def __init__(self, message: str = "Данные были изменены другим пользователем"):
        self.message = message
        super().__init__(self.message)


@dataclass
class LockResult:
    """Result of optimistic locking check."""
    success: bool
    current_version: int
    message: str = ""


async def update_schedule_with_optimistic_lock(
    session: AsyncSession,
    schedule_id: int,
    expected_version: int,
    update_data: dict
) -> LockResult:
    """
    Update schedule with optimistic locking check.
    
    Args:
        session: Database session
        schedule_id: ID of schedule to update
        expected_version: Version that user expects (from when they read the data)
        update_data: Dict of fields to update
        
    Returns:
        LockResult with success status and current version
        
    Raises:
        ConflictError: If version mismatch detected
    """
    # Fetch current record with version check
    result = await session.execute(
        select(ScheduleV2).where(
            ScheduleV2.id == schedule_id
        )
    )
    schedule = result.scalar_one_or_none()
    
    if schedule is None:
        return LockResult(
            success=False,
            current_version=0,
            message="Запись не найдена"
        )
    
    if schedule.version != expected_version:
        logger.warning(
            f"Optimistic lock conflict: expected v{expected_version}, "
            f"found v{schedule.version} for schedule {schedule_id}"
        )
        raise ConflictError(
            f"Данные были изменены другим пользователем. "
            f"Ваша версия: {expected_version}, текущая: {schedule.version}. "
            f"Пожалуйста, обновите страницу и попробуйте снова."
        )
    
    # Apply updates
    for field, value in update_data.items():
        if hasattr(schedule, field):
            setattr(schedule, field, value)
    
    # Increment version
    schedule.version += 1
    
    await session.commit()
    
    return LockResult(
        success=True,
        current_version=schedule.version,
        message="Обновление успешно применено"
    )


async def get_schedule_with_version(
    session: AsyncSession,
    schedule_id: int
) -> tuple[ScheduleV2 | None, int]:
    """
    Get schedule record with its current version.

    Returns:
        Tuple of (schedule_record, version)
    """
    result = await session.execute(
        select(ScheduleV2).where(ScheduleV2.id == schedule_id)
    )
    schedule = result.scalar_one_or_none()

    if schedule is None:
        return None, 0

    return schedule, schedule.version
