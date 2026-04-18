"""
Pydantic schemas for schedule data validation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LessonSchema(BaseModel):
    """Schema for a single lesson."""
    model_config = ConfigDict(from_attributes=True)
    
    number: int = Field(..., ge=1, le=10, description="Номер пары (1-10)")
    subject: Optional[str] = Field(None, max_length=200, description="Название предмета")
    teacher: Optional[str] = Field(None, max_length=100, description="ФИО преподавателя")
    room: Optional[str] = Field(None, max_length=20, description="Номер аудитории")
    start_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$", description="Время начала (HH:MM)")
    end_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$", description="Время окончания (HH:MM)")
    
    @field_validator("subject", "teacher", "room")
    @classmethod
    def strip_whitespace(cls, v: Optional[str]) -> Optional[str]:
        """Strip whitespace from string fields."""
        if v is not None:
            return v.strip() or None
        return v


class ScheduleSchema(BaseModel):
    """Schema for schedule record validation."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    group_name: Optional[str] = Field(None, max_length=50, description="Название группы")
    day: Optional[str] = Field(None, pattern=r"^(Пн|Вт|Ср|Чт|Пт|Сб|Пн|Вт|Ср|Чт|Пт|Сб)$", description="День недели")
    lesson_number: Optional[int] = Field(None, ge=1, le=10, description="Номер пары")
    subject: Optional[str] = Field(None, max_length=200)
    teacher: Optional[str] = Field(None, max_length=100)
    room: Optional[str] = Field(None, max_length=20)
    start_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    end_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    is_change: bool = Field(default=False, description="Является ли заменой")
    is_published: bool = Field(default=False, description="Опубликовано ли")
    updated_by: Optional[int] = Field(None, description="ID пользователя, внесшего изменения")
    
    @field_validator("group_name", "subject", "teacher", "room", "day")
    @classmethod
    def strip_whitespace(cls, v: Optional[str]) -> Optional[str]:
        """Strip whitespace from string fields."""
        if v is not None:
            return v.strip() or None
        return v


class AuditLogSchema(BaseModel):
    """Schema for audit log validation."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    tg_id: int = Field(..., gt=0, description="Telegram ID пользователя")
    full_name: str = Field(..., max_length=200, min_length=1)
    action: str = Field(..., max_length=100, min_length=1)
    group_name: str = Field(..., max_length=50, min_length=1)
    day: str = Field(..., max_length=20, min_length=1)
    lesson_num: int = Field(..., ge=1, le=10)
    old_value: Optional[str] = Field(None, max_length=500)
    new_value: Optional[str] = Field(None, max_length=500)
    timestamp: datetime


class UserProfileSchema(BaseModel):
    """Schema for user profile validation."""
    model_config = ConfigDict(from_attributes=True)
    
    tg_id: int = Field(..., gt=0)
    group_name: Optional[str] = Field(None, max_length=50)
    language: str = Field(default="ru", pattern=r"^(ru|en)$")
    is_active: bool = Field(default=True)
    updated_at: datetime
    
    @field_validator("group_name")
    @classmethod
    def strip_whitespace(cls, v: Optional[str]) -> Optional[str]:
        """Strip whitespace from group name."""
        if v is not None:
            return v.strip() or None
        return v


class BroadcastRequestSchema(BaseModel):
    """Schema for broadcast request from dashboard."""
    message: str = Field(..., min_length=1, max_length=4000, description="Текст сообщения")
    target_groups: list[str] = Field(..., min_length=1, description="Целевые группы")
    scheduled_at: Optional[datetime] = Field(None, description="Время запланированной отправки")
    
    @field_validator("target_groups")
    @classmethod
    def validate_groups(cls, v: list[str]) -> list[str]:
        """Validate and clean group names."""
        cleaned = [g.strip() for g in v if g.strip()]
        if not cleaned:
            raise ValueError("Необходимо указать хотя бы одну группу")
        return cleaned
    
    @field_validator("message")
    @classmethod
    def strip_message(cls, v: str) -> str:
        """Strip message text."""
        v = v.strip()
        if not v:
            raise ValueError("Сообщение не может быть пустым")
        return v


class ScheduleUpdatePayloadSchema(BaseModel):
    """Schema for schedule update webhook payload."""
    group_name: str = Field(..., min_length=1, max_length=50)
    day: Optional[str] = Field(None, pattern=r"^(Пн|Вт|Ср|Чт|Пт|Сб)$")
    changes: list[dict] = Field(default_factory=list, description="Список изменений")
    updated_by: Optional[int] = Field(None, gt=0)
    timestamp: datetime = Field(default_factory=datetime.now)
