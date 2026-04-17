from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, Text
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(AsyncAttrs, DeclarativeBase):
    pass


# Telegram identifiers (tg_id, chat_id, user_id) can exceed signed 32-bit range.
# Use BIGINT for these columns in PostgreSQL to avoid out-of-range failures.
class Schedule(Base):
    __tablename__ = "schedule"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    day: Mapped[str | None] = mapped_column(Text, nullable=True)
    lesson_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    teacher: Mapped[str | None] = mapped_column(Text, nullable=True)
    room: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_time: Mapped[str | None] = mapped_column(Text, nullable=True)
    end_time: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_change: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    updated_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class BaseSchedule(Base):
    """Хранит базовое (первичное) расписание - оригинальный импорт 323 записей.

    Эта таблица неизменна при последующих импортах Excel.
    Используется для сброса расписания к исходному состоянию.
    """
    __tablename__ = "base_schedule"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    day: Mapped[str | None] = mapped_column(Text, nullable=True)
    lesson_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    teacher: Mapped[str | None] = mapped_column(Text, nullable=True)
    room: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_time: Mapped[str | None] = mapped_column(Text, nullable=True)
    end_time: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    # Telegram IDs may exceed signed 32-bit range, so use BIGINT for tg_id.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    group_name: Mapped[str] = mapped_column(Text, nullable=False)
    day: Mapped[str] = mapped_column(Text, nullable=False)
    lesson_num: Mapped[int] = mapped_column(Integer, nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)


class UserProfile(Base):
    __tablename__ = "user_profiles"

    tg_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    group_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(Text, nullable=False, default="ru", server_default="ru")
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
