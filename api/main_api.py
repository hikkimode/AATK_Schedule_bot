from __future__ import annotations

import hashlib
import hmac
import json
import os
import urllib.parse
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncGenerator

from fastapi import Depends, FastAPI, HTTPException, Header, Path
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError, DatabaseError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from database import create_engine_and_sessionmaker
from models import AuditLog, NotificationQueue, NotificationStatus, ScheduleV2, UserProfile
from services.notification_worker import NotificationEnqueuer
from utils.exceptions import setup_logging

setup_logging()

_engine = None
_session_factory = None
_superadmin_ids: set[int] = set()

# Lesson times mapping (lesson_number -> (start_time, end_time))
LESSON_TIMES: dict[int, tuple[str, str]] = {
    1: ("08:30", "09:50"),
    2: ("10:00", "11:20"),
    3: ("11:30", "12:50"),
    4: ("13:00", "14:20"),
    5: ("14:30", "15:50"),
    6: ("16:00", "17:20"),
}


@dataclass
class TelegramUser:
    id: int
    first_name: str
    last_name: str | None = None
    username: str | None = None
    language_code: str | None = None


def init_superadmin_ids(ids: list[int]) -> None:
    global _superadmin_ids
    _superadmin_ids = set(ids)


def verify_telegram_auth(init_data: str) -> TelegramUser | None:
    """Verify Telegram WebApp initData using HMAC-SHA256."""
    bot_token = os.getenv("BOT_TOKEN", "")
    if not bot_token:
        logger.error("BOT_TOKEN not set")
        return None

    try:
        # Parse init_data
        parsed = urllib.parse.parse_qs(init_data)
        hash_value = parsed.get("hash", [""])[0]
        if not hash_value:
            return None

        # Create data_check_string (sorted key=value pairs, separated by \n)
        data_pairs = []
        for key, values in parsed.items():
            if key != "hash":
                data_pairs.append((key, values[0]))
        data_pairs.sort(key=lambda x: x[0])
        data_check_string = "\n".join(f"{k}={v}" for k, v in data_pairs)

        # Generate secret key from bot token
        secret_key = hmac.new(
            key=b"WebAppData",
            msg=bot_token.encode(),
            digestmod=hashlib.sha256
        ).digest()

        # Calculate HMAC
        calculated_hash = hmac.new(
            key=secret_key,
            msg=data_check_string.encode(),
            digestmod=hashlib.sha256
        ).hexdigest()

        if calculated_hash != hash_value:
            logger.warning("Invalid initData hash")
            return None

        # Parse user data
        user_json = parsed.get("user", ["{}"])[0]
        user_data = json.loads(user_json)

        return TelegramUser(
            id=user_data.get("id", 0),
            first_name=user_data.get("first_name", ""),
            last_name=user_data.get("last_name"),
            username=user_data.get("username"),
            language_code=user_data.get("language_code"),
        )
    except Exception as e:
        logger.error("Error verifying Telegram auth: " + str(e))
        return None


async def get_current_user(
    authorization: str = Header(None, alias="Authorization")
) -> TelegramUser:
    """Dependency to get current authenticated user."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")

    # Expected format: "tma <initData>"
    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0] != "tma":
        raise HTTPException(status_code=401, detail="Invalid authorization format")

    user = verify_telegram_auth(parts[1])
    if not user:
        raise HTTPException(status_code=401, detail="Invalid Telegram authentication")

    return user


def require_admin(user: TelegramUser = Depends(get_current_user)) -> TelegramUser:
    """Dependency to require admin privileges."""
    if user.id not in _superadmin_ids:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def log_audit_action(
    session: AsyncSession,
    user: TelegramUser,
    action: str,
    group_name: str,
    day: str,
    lesson_num: int,
    old_value: str | None = None,
    new_value: str | None = None,
) -> None:
    """Log an audit action to the database."""
    full_name = user.first_name
    if user.last_name:
        full_name = full_name + " " + user.last_name

    audit_log = AuditLog(
        tg_id=user.id,
        full_name=full_name,
        action=action,
        group_name=group_name,
        day=day,
        lesson_num=lesson_num,
        old_value=old_value,
        new_value=new_value,
    )
    session.add(audit_log)
    await session.commit()


from schemas.schedule import ChangeResponse, ChangeCreateRequest, ChangeUpdateRequest


class BotStatsResponse(BaseModel):
    total_users: int
    active_users: int


class StatusResponse(BaseModel):
    status: str


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[Any, None]:
    global _engine, _session_factory, _superadmin_ids
    from config import load_config
    config = load_config()
    _engine, _session_factory = create_engine_and_sessionmaker(config.database_url)
    init_superadmin_ids(config.superadmin_ids)
    yield
    if _engine:
        await _engine.dispose()

from api.dashboard_api import router as dashboard_router

app = FastAPI(title="Schedule Bot API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://aatk-schedule-bot.vercel.app"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Telegram-Init-Data", "X-API-Key"],
)

app.include_router(dashboard_router)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    if _session_factory is None:
        raise RuntimeError("Database not initialized")
    async with _session_factory() as session:
        yield session


@app.get("/", response_model=StatusResponse)
async def get_status() -> StatusResponse:
    return StatusResponse(status="API is running")


@app.get("/schedule/changes", response_model=list[ChangeResponse])
async def get_schedule_changes(
    session: AsyncSession = Depends(get_session),
    authorization: str = Header(None, alias="Authorization")
) -> list[ChangeResponse]:
    # Check if user is admin to show all changes (including drafts)
    is_admin = False
    if authorization:
        parts = authorization.split(" ")
        if len(parts) == 2 and parts[0] == "tma":
            user = verify_telegram_auth(parts[1])
            if user and user.id in _superadmin_ids:
                is_admin = True
    
    # Build query from ScheduleV2 JSONB lessons
    result = await session.execute(select(ScheduleV2))
    schedules = result.scalars().all()

    changes: list[ChangeResponse] = []
    for s in schedules:
        for lesson in s.lessons:
            if not lesson.get("is_change"):
                continue
            if not is_admin and not lesson.get("is_published"):
                continue
            changes.append(
                ChangeResponse(
                    id=s.id,
                    group_name=s.group_name,
                    day=s.day,
                    lesson_number=lesson.get("num"),
                    subject=lesson.get("name"),
                    teacher=lesson.get("teacher"),
                    room=lesson.get("room"),
                    start_time=lesson.get("time_start"),
                    end_time=lesson.get("time_end"),
                    raw_text=None,
                    is_published=lesson.get("is_published", False),
                )
            )
    return changes


@app.get("/bot/stats", response_model=BotStatsResponse)
async def get_bot_stats(session: AsyncSession = Depends(get_session)) -> BotStatsResponse:
    total_query = select(func.count(UserProfile.tg_id))
    active_query = select(func.count(UserProfile.tg_id)).where(UserProfile.is_active == True)

    total_result = await session.execute(total_query)
    active_result = await session.execute(active_query)

    total = total_result.scalar() or 0
    active = active_result.scalar() or 0

    return BotStatsResponse(total_users=total, active_users=active)


def get_lesson_times(lesson_number: int) -> tuple[str | None, str | None]:
    """Get start and end time for a lesson number."""
    if lesson_number in LESSON_TIMES:
        return LESSON_TIMES[lesson_number]
    return None, None


@app.post("/schedule/changes", response_model=ChangeResponse)
async def create_change(
    request: ChangeCreateRequest,
    session: AsyncSession = Depends(get_session),
    user: TelegramUser = Depends(require_admin)
) -> ChangeResponse:
    try:
        # Find or create ScheduleV2 row for this group+day
        sched_q = select(ScheduleV2).where(
            ScheduleV2.group_name == request.group_name,
            ScheduleV2.day == request.day,
        )
        sched_result = await session.execute(sched_q)
        sched = sched_result.scalar_one_or_none()

        start_time, end_time = get_lesson_times(request.lesson_number)
        lesson_dict = {
            "num": request.lesson_number,
            "name": request.subject,
            "teacher": request.teacher,
            "room": request.room,
            "time_start": start_time,
            "time_end": end_time,
            "is_change": True,
            "is_published": False,
            "subgroup": 0,
        }

        if sched:
            lessons = list(sched.lessons)
            # Replace existing lesson with same num or append
            idx = next((i for i, l in enumerate(lessons) if l.get("num") == request.lesson_number), None)
            old_value = str(lessons[idx]) if idx is not None else None
            if idx is not None:
                lessons[idx] = lesson_dict
            else:
                lessons.append(lesson_dict)
            sched.lessons = sorted(lessons, key=lambda x: x.get("num", 0))
        else:
            old_value = None
            sched = ScheduleV2(
                group_name=request.group_name,
                day=request.day,
                lessons=[lesson_dict],
            )
            session.add(sched)

        await session.commit()
        await session.refresh(sched)

        await log_audit_action(
            session, user, "UPSERT",
            request.group_name, request.day, request.lesson_number,
            old_value, str(lesson_dict),
        )

        return ChangeResponse(
            id=sched.id,
            group_name=sched.group_name,
            day=sched.day,
            lesson_number=lesson_dict["num"],
            subject=lesson_dict["name"],
            teacher=lesson_dict["teacher"],
            room=lesson_dict["room"],
            start_time=lesson_dict["time_start"],
            end_time=lesson_dict["time_end"],
            raw_text=None,
            is_published=lesson_dict["is_published"],
        )
    except IntegrityError as e:
        await session.rollback()
        logger.error(f"Database integrity error: {e}")
        raise HTTPException(status_code=400, detail="Ошибка заполнения: проверьте обязательные поля")
    except DatabaseError as e:
        await session.rollback()
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных. Попробуйте позже.")


@app.patch("/schedule/changes/{change_id}", response_model=ChangeResponse)
async def update_change(
    change_id: int = Path(..., ge=1),
    request: ChangeUpdateRequest = Depends(),
    session: AsyncSession = Depends(get_session),
    user: TelegramUser = Depends(require_admin)
) -> ChangeResponse:
    try:
        # Find the ScheduleV2 row containing this lesson
        sched_q = select(ScheduleV2).where(ScheduleV2.id == change_id)
        result = await session.execute(sched_q)
        sched = result.scalar_one_or_none()

        if sched is None:
            raise HTTPException(status_code=404, detail="Change not found")

        update_data = request.model_dump(exclude_unset=True)

        # Auto-fill time if lesson_number updated
        lesson_num = update_data.get("lesson_number")
        if lesson_num:
            start_time, end_time = get_lesson_times(lesson_num)
            if not update_data.get("start_time") and start_time:
                update_data["start_time"] = start_time
            if not update_data.get("end_time") and end_time:
                update_data["end_time"] = end_time

        lessons = list(sched.lessons)
        # Find the first changed lesson to update (or last lesson if none found)
        target_idx = next((i for i, l in enumerate(lessons) if l.get("is_change")), 0)
        old_value = str(lessons[target_idx]) if lessons else None

        field_map = {
            "subject": "name",
            "lesson_number": "num",
            "start_time": "time_start",
            "end_time": "time_end",
        }
        for api_field, value in update_data.items():
            jsonb_field = field_map.get(api_field, api_field)
            if target_idx < len(lessons):
                lessons[target_idx][jsonb_field] = value

        sched.lessons = lessons
        await session.commit()
        await session.refresh(sched)

        lesson = sched.lessons[target_idx] if sched.lessons else {}

        await log_audit_action(
            session, user, "UPDATE",
            sched.group_name, sched.day, lesson.get("num", 0),
            old_value, str(lesson),
        )

        return ChangeResponse(
            id=sched.id,
            group_name=sched.group_name,
            day=sched.day,
            lesson_number=lesson.get("num"),
            subject=lesson.get("name"),
            teacher=lesson.get("teacher"),
            room=lesson.get("room"),
            start_time=lesson.get("time_start"),
            end_time=lesson.get("time_end"),
            raw_text=None,
        )
    except IntegrityError as e:
        await session.rollback()
        logger.error(f"Database integrity error: {e}")
        raise HTTPException(status_code=400, detail="Ошибка заполнения: проверьте обязательные поля")
    except DatabaseError as e:
        await session.rollback()
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных. Попробуйте позже.")


@app.delete("/schedule/changes/{change_id}")
async def delete_change(
    change_id: int = Path(..., ge=1),
    session: AsyncSession = Depends(get_session),
    user: TelegramUser = Depends(require_admin)
) -> dict[str, str]:
    try:
        sched_q = select(ScheduleV2).where(ScheduleV2.id == change_id)
        result = await session.execute(sched_q)
        sched = result.scalar_one_or_none()

        if sched is None:
            raise HTTPException(status_code=404, detail="Change not found")

        group_name = sched.group_name
        day = sched.day
        # Find the changed lesson slot
        lessons = list(sched.lessons)
        target_idx = next((i for i, l in enumerate(lessons) if l.get("is_change")), None)
        if target_idx is not None:
            old_value = str(lessons[target_idx])
            lesson_num = lessons[target_idx].get("num", 0)
            lessons[target_idx]["is_change"] = False  # Soft-delete: mark as resolved
            sched.lessons = lessons
        else:
            old_value = None
            lesson_num = 0

        await session.commit()

        await log_audit_action(
            session, user, "DELETE",
            group_name, day, lesson_num,
            old_value, None,
        )

        return {"message": "Change deleted successfully"}
    except IntegrityError as e:
        await session.rollback()
        logger.error(f"Database integrity error: {e}")
        raise HTTPException(status_code=400, detail="Ошибка удаления: запись используется в других данных")
    except DatabaseError as e:
        await session.rollback()
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных. Попробуйте позже.")


@app.delete("/schedule/changes/clear-all")
async def clear_all_changes(
    session: AsyncSession = Depends(get_session),
    user: TelegramUser = Depends(require_admin)
) -> dict[str, str]:
    try:
        # Clear all 'is_change' flags in ScheduleV2 lessons
        result = await session.execute(select(ScheduleV2))
        schedules = result.scalars().all()
        cleared = 0
        for s in schedules:
            new_lessons = []
            for l in s.lessons:
                if l.get("is_change"):
                    cleared += 1
                    l = {**l, "is_change": False, "is_published": False}
                new_lessons.append(l)
            s.lessons = new_lessons
        await session.commit()

        await log_audit_action(
            session, user, "CLEAR_ALL",
            "ALL", "ALL", 0,
            f"{cleared} changes", "Cleared",
        )

        return {"message": "All changes cleared", "deleted_count": str(cleared)}
    except IntegrityError as e:
        await session.rollback()
        logger.error(f"Database integrity error: {e}")
        raise HTTPException(status_code=400, detail="Ошибка очистки: невозможно удалить некоторые записи")
    except DatabaseError as e:
        await session.rollback()
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных. Попробуйте позже.")


@app.get("/notifications/stats", response_model=dict[str, Any])
async def get_notification_stats(
    session: AsyncSession = Depends(get_session),
    user: TelegramUser = Depends(require_admin)
) -> dict[str, Any]:
    """Get notification queue statistics (admin only)."""
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
    
    # Recent pending notifications (last 24h)
    from datetime import datetime, timedelta
    recent_pending_query = select(func.count(NotificationQueue.id)).where(
        NotificationQueue.status == NotificationStatus.PENDING.value,
        NotificationQueue.created_at >= datetime.now() - timedelta(hours=24)
    )
    
    pending = await session.scalar(pending_query) or 0
    sent = await session.scalar(sent_query) or 0
    failed = await session.scalar(failed_query) or 0
    recent_pending = await session.scalar(recent_pending_query) or 0
    
    # Get per-group breakdown for pending
    group_query = (
        select(NotificationQueue.group_name, func.count(NotificationQueue.id))
        .where(NotificationQueue.status == NotificationStatus.PENDING.value)
        .group_by(NotificationQueue.group_name)
    )
    group_result = await session.execute(group_query)
    per_group = {group or "Unknown": count for group, count in group_result.all()}
    
    return {
        "pending": pending,
        "sent": sent,
        "failed": failed,
        "total": pending + sent + failed,
        "recent_pending_24h": recent_pending,
        "per_group_pending": per_group,
    }


@app.post("/schedule/publish-all")
async def publish_all_changes(
    session: AsyncSession = Depends(get_session),
    user: TelegramUser = Depends(require_admin)
) -> dict[str, Any]:
    """Publish all unpublished schedule changes and enqueue notifications."""
    try:
        # Find all ScheduleV2 rows with unpublished changes
        result_q = await session.execute(select(ScheduleV2))
        schedules = result_q.scalars().all()

        affected_groups: list[str] = []
        published_count = 0
        for s in schedules:
            new_lessons = []
            changed = False
            for l in s.lessons:
                if l.get("is_change") and not l.get("is_published"):
                    l = {**l, "is_published": True}
                    published_count += 1
                    changed = True
                new_lessons.append(l)
            if changed:
                s.lessons = new_lessons
                if s.group_name and s.group_name not in affected_groups:
                    affected_groups.append(s.group_name)
        await session.flush()
        
        # Enqueue notifications for affected groups
        enqueued_count = 0
        if affected_groups and published_count > 0:
            try:
                enqueuer = NotificationEnqueuer(session)
                enqueued_count = await enqueuer.enqueue_schedule_change_notifications(affected_groups)
                logger.info(f"Enqueued {enqueued_count} notifications for groups: {affected_groups}")
            except Exception as e:
                logger.error(f"Failed to enqueue notifications: {e}")
                # Don't fail the publish if notification enqueue fails
                # The worker can be run manually to process missed notifications
        
        await session.commit()

        # Log audit
        await log_audit_action(
            session, user, "PUBLISH_ALL",
            "ALL", "ALL", 0,
            f"{published_count} drafts", f"Published, {enqueued_count} notifications enqueued"
        )

        return {
            "message": "All changes published successfully",
            "published_count": str(published_count),
            "affected_groups": affected_groups,
            "notifications_enqueued": enqueued_count,
        }
    except IntegrityError as e:
        await session.rollback()
        logger.error(f"Database integrity error: {e}")
        raise HTTPException(status_code=400, detail="Ошибка публикации: невозможно опубликовать некоторые записи")
    except DatabaseError as e:
        await session.rollback()
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных. Попробуйте позже.")
