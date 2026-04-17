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
from models import AuditLog, Schedule, UserProfile
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


class ChangeResponse(BaseModel):
    id: int
    group_name: str | None
    day: str | None
    lesson_number: int | None
    subject: str | None
    teacher: str | None
    room: str | None
    start_time: str | None
    end_time: str | None
    raw_text: str | None
    is_published: bool = False


class ChangeCreateRequest(BaseModel):
    group_name: str = Field(..., min_length=1)
    subject: str = Field(..., min_length=1)
    day: str = Field(..., min_length=1)
    lesson_number: int = Field(..., ge=1, le=10)
    teacher: str | None = None
    room: str | None = None


class ChangeUpdateRequest(BaseModel):
    group_name: str | None = None
    subject: str | None = None
    day: str | None = None
    lesson_number: int | None = Field(None, ge=1, le=10)
    teacher: str | None = None
    room: str | None = None


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


app = FastAPI(title="Schedule Bot API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://aatk-schedule-bot.vercel.app"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Telegram-Init-Data"],
)


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
    
    # Build query: admins see all, regular users see only published
    if is_admin:
        query = select(Schedule).where(Schedule.is_change == True)
    else:
        query = select(Schedule).where(
            Schedule.is_change == True,
            Schedule.is_published == True
        )
    
    result = await session.execute(query)
    changes = result.scalars().all()
    return [
        ChangeResponse(
            id=c.id,
            group_name=c.group_name,
            day=c.day,
            lesson_number=c.lesson_number,
            subject=c.subject,
            teacher=c.teacher,
            room=c.room,
            start_time=c.start_time,
            end_time=c.end_time,
            raw_text=c.raw_text,
            is_published=c.is_published,
        )
        for c in changes
    ]


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
        raw_text = request.group_name + " | " + request.day + " | " + str(request.lesson_number) + " | " + request.subject
        if request.teacher:
            raw_text = raw_text + " | " + request.teacher
        if request.room:
            raw_text = raw_text + " | " + request.room

        # Auto-fill time based on lesson number
        start_time, end_time = get_lesson_times(request.lesson_number)

        # Build insert statement with upsert on conflict
        # If unique_lesson_idx conflict (group_name, day, lesson_number), update existing record
        insert_stmt = pg_insert(Schedule).values(
            group_name=request.group_name,
            subject=request.subject,
            day=request.day,
            lesson_number=request.lesson_number,
            teacher=request.teacher,
            room=request.room,
            start_time=start_time,
            end_time=end_time,
            raw_text=raw_text,
            is_change=True,
            is_published=False,  # Reset to draft on conflict
            updated_by=user.id,
        ).on_conflict_do_update(
            index_elements=["group_name", "day", "lesson_number"],  # Matches unique_lesson_idx
            set_={
                "subject": request.subject,
                "teacher": request.teacher,
                "room": request.room,
                "start_time": start_time,
                "end_time": end_time,
                "raw_text": raw_text,
                "is_change": True,
                "is_published": False,  # Reset to draft on update
                "updated_by": user.id,
            }
        )

        result = await session.execute(insert_stmt)
        await session.commit()

        # Get the inserted/updated record
        # Fetch the record by unique key to return it
        query = select(Schedule).where(
            Schedule.group_name == request.group_name,
            Schedule.day == request.day,
            Schedule.lesson_number == request.lesson_number
        )
        result = await session.execute(query)
        change = result.scalar_one()

        # Log audit (differentiate between create and update)
        action = "UPSERT"  # Could be CREATE or UPDATE depending on conflict
        await log_audit_action(
            session, user, action,
            request.group_name, request.day, request.lesson_number,
            None, raw_text
        )

        return ChangeResponse(
            id=change.id,
            group_name=change.group_name,
            day=change.day,
            lesson_number=change.lesson_number,
            subject=change.subject,
            teacher=change.teacher,
            room=change.room,
            start_time=change.start_time,
            end_time=change.end_time,
            raw_text=change.raw_text,
            is_published=change.is_published,
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
        query = select(Schedule).where(Schedule.id == change_id, Schedule.is_change == True)
        result = await session.execute(query)
        change = result.scalar_one_or_none()

        if change is None:
            raise HTTPException(status_code=404, detail="Change not found")

        # Store old value for audit
        old_value = change.raw_text

        update_data = request.model_dump(exclude_unset=True)

        # Auto-fill time if lesson_number is being updated
        if "lesson_number" in update_data and update_data["lesson_number"]:
            lesson_num = update_data["lesson_number"]
            start_time, end_time = get_lesson_times(lesson_num)
            # Only update time if current time is empty or we're explicitly changing it
            if not update_data.get("start_time") and start_time:
                update_data["start_time"] = start_time
            if not update_data.get("end_time") and end_time:
                update_data["end_time"] = end_time

        # Always set updated_by
        update_data["updated_by"] = user.id

        if update_data:
            stmt = update(Schedule).where(Schedule.id == change_id).values(**update_data)
            await session.execute(stmt)
            await session.commit()
            await session.refresh(change)

            # Log audit
            await log_audit_action(
                session, user, "UPDATE",
                change.group_name or "", change.day or "", change.lesson_number or 0,
                old_value, change.raw_text
            )

        return ChangeResponse(
            id=change.id,
            group_name=change.group_name,
            day=change.day,
            lesson_number=change.lesson_number,
            subject=change.subject,
            teacher=change.teacher,
            room=change.room,
            start_time=change.start_time,
            end_time=change.end_time,
            raw_text=change.raw_text,
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
        query = select(Schedule).where(Schedule.id == change_id, Schedule.is_change == True)
        result = await session.execute(query)
        change = result.scalar_one_or_none()

        if change is None:
            raise HTTPException(status_code=404, detail="Change not found")

        # Store data for audit
        group_name = change.group_name or ""
        day = change.day or ""
        lesson_num = change.lesson_number or 0
        old_value = change.raw_text

        await session.delete(change)
        await session.commit()

        # Log audit
        await log_audit_action(
            session, user, "DELETE",
            group_name, day, lesson_num,
            old_value, None
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
        stmt = delete(Schedule).where(Schedule.is_change == True)
        result = await session.execute(stmt)
        await session.commit()

        # Log audit
        await log_audit_action(
            session, user, "CLEAR_ALL",
            "ALL", "ALL", 0,
            "All changes", "Cleared"
        )

        return {"message": "All changes cleared", "deleted_count": str(result.rowcount)}
    except IntegrityError as e:
        await session.rollback()
        logger.error(f"Database integrity error: {e}")
        raise HTTPException(status_code=400, detail="Ошибка очистки: невозможно удалить некоторые записи")
    except DatabaseError as e:
        await session.rollback()
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных. Попробуйте позже.")


@app.post("/schedule/publish-all")
async def publish_all_changes(
    session: AsyncSession = Depends(get_session),
    user: TelegramUser = Depends(require_admin)
) -> dict[str, str]:
    """Publish all unpublished schedule changes."""
    try:
        stmt = (
            update(Schedule)
            .where(Schedule.is_change == True, Schedule.is_published == False)
            .values(is_published=True, updated_by=user.id)
        )
        result = await session.execute(stmt)
        await session.commit()

        published_count = result.rowcount

        # Log audit
        await log_audit_action(
            session, user, "PUBLISH_ALL",
            "ALL", "ALL", 0,
            f"{published_count} drafts", "Published"
        )

        return {
            "message": "All changes published successfully",
            "published_count": str(published_count)
        }
    except IntegrityError as e:
        await session.rollback()
        logger.error(f"Database integrity error: {e}")
        raise HTTPException(status_code=400, detail="Ошибка публикации: невозможно опубликовать некоторые записи")
    except DatabaseError as e:
        await session.rollback()
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных. Попробуйте позже.")
