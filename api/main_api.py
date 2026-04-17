from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import func, select
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
    allow_methods=["GET", "POST", "OPTIONS"],
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
