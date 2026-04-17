from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from database import create_engine_and_sessionmaker
from models import Schedule, UserProfile
from utils.exceptions import setup_logging


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


def create_api_app(database_url: str) -> FastAPI:
    setup_logging()
    engine, session_factory = create_engine_and_sessionmaker(database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        yield
        await engine.dispose()

    app = FastAPI(title="Schedule Bot API", lifespan=lifespan)

    async def get_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

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

    return app
