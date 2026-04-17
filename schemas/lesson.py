from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class LessonImportSchema(BaseModel):
    group_name: str = Field(..., min_length=1)
    day: str = Field(..., min_length=1)
    lesson_number: int = Field(..., ge=1, le=10)
    subject: str | None = None
    teacher: str | None = None
    room: str | None = None
    start_time: str = Field(..., pattern=r"^\d{1,2}:\d{2}$")
    end_time: str = Field(..., pattern=r"^\d{1,2}:\d{2}$")
    raw_text: str = ""

    @field_validator("group_name", "day", "subject", "teacher", "room", mode="before")
    @classmethod
    def clean_string(cls, v: Any) -> str | None:
        if v is None:
            return None
        text = str(v).strip()
        if not text or text.lower() == "nan":
            return None
        return text

    @field_validator("lesson_number", mode="before")
    @classmethod
    def parse_lesson_number(cls, v: Any) -> int:
        if isinstance(v, int):
            return v
        if isinstance(v, float):
            return int(v)
        text = str(v).strip()
        return int(float(text))

    @model_validator(mode="after")
    def build_raw_text(self) -> "LessonImportSchema":
        subj = self.subject or ""
        teach = self.teacher or ""
        rm = self.room or ""
        self.raw_text = f"{subj}\n({teach})   {rm}"
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "group_name": self.group_name,
            "day": self.day,
            "lesson_number": self.lesson_number,
            "subject": self.subject,
            "teacher": self.teacher,
            "room": self.room,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "raw_text": self.raw_text,
        }


class LessonChangeSchema(BaseModel):
    day: str
    lesson_number: int
    old: dict[str, Any]
    new: dict[str, Any]


class ImportResultSchema(BaseModel):
    updated_rows: int
    updated_groups: list[str]
    skipped_rows: int
    errors: list[str]
    changes_by_group: dict[str, list[LessonChangeSchema]]
