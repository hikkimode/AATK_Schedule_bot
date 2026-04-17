from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import Depends, FastAPI, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from database import create_engine_and_sessionmaker
from models import Schedule, UserProfile
from utils.exceptions import setup_logging

setup_logging()

_engine = None
_session_factory = None


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
    global _engine, _session_factory
    from config import load_config
    config = load_config()
    _engine, _session_factory = create_engine_and_sessionmaker(config.database_url)
    yield
    if _engine:
        await _engine.dispose()


app = FastAPI(title="Schedule Bot API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://aatk-schedule-bot.vercel.app"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
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
async def get_schedule_changes(session: AsyncSession = Depends(get_session)) -> list[ChangeResponse]:
    query = select(Schedule).where(Schedule.is_change == True)
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


@app.post("/schedule/changes", response_model=ChangeResponse)
async def create_change(
    request: ChangeCreateRequest,
    session: AsyncSession = Depends(get_session)
) -> ChangeResponse:
    raw_text = request.group_name + " | " + request.day + " | " + str(request.lesson_number) + " | " + request.subject
    if request.teacher:
        raw_text = raw_text + " | " + request.teacher
    if request.room:
        raw_text = raw_text + " | " + request.room

    new_change = Schedule(
        group_name=request.group_name,
        subject=request.subject,
        day=request.day,
        lesson_number=request.lesson_number,
        teacher=request.teacher,
        room=request.room,
        raw_text=raw_text,
        is_change=True,
    )
    session.add(new_change)
    await session.commit()
    await session.refresh(new_change)

    return ChangeResponse(
        id=new_change.id,
        group_name=new_change.group_name,
        day=new_change.day,
        lesson_number=new_change.lesson_number,
        subject=new_change.subject,
        teacher=new_change.teacher,
        room=new_change.room,
        start_time=new_change.start_time,
        end_time=new_change.end_time,
        raw_text=new_change.raw_text,
    )


@app.patch("/schedule/changes/{change_id}", response_model=ChangeResponse)
async def update_change(
    change_id: int = Path(..., ge=1),
    request: ChangeUpdateRequest = Depends(),
    session: AsyncSession = Depends(get_session)
) -> ChangeResponse:
    query = select(Schedule).where(Schedule.id == change_id, Schedule.is_change == True)
    result = await session.execute(query)
    change = result.scalar_one_or_none()

    if change is None:
        raise HTTPException(status_code=404, detail="Change not found")

    update_data = request.model_dump(exclude_unset=True)

    if update_data:
        stmt = update(Schedule).where(Schedule.id == change_id).values(**update_data)
        await session.execute(stmt)
        await session.commit()
        await session.refresh(change)

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


@app.delete("/schedule/changes/{change_id}")
async def delete_change(
    change_id: int = Path(..., ge=1),
    session: AsyncSession = Depends(get_session)
) -> dict[str, str]:
    query = select(Schedule).where(Schedule.id == change_id, Schedule.is_change == True)
    result = await session.execute(query)
    change = result.scalar_one_or_none()

    if change is None:
        raise HTTPException(status_code=404, detail="Change not found")

    await session.delete(change)
    await session.commit()

    return {"message": "Change deleted successfully"}


@app.delete("/schedule/changes/clear-all")
async def clear_all_changes(session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    stmt = delete(Schedule).where(Schedule.is_change == True)
    result = await session.execute(stmt)
    await session.commit()

    return {"message": "All changes cleared", "deleted_count": str(result.rowcount)}
