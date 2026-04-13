from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: str = Field(alias="BOT_TOKEN")
    database_url: str = Field(default="sqlite+aiosqlite:///./schedule.db", alias="DATABASE_URL")
    teacher_ids: list[int] = Field(default_factory=list, alias="TEACHER_IDS")
    superadmin_ids: list[int] = Field(default_factory=list, alias="SUPERADMIN_IDS")

    @field_validator("teacher_ids", "superadmin_ids", mode="before")
    @classmethod
    def parse_id_list(cls, value: object) -> list[int]:
        if value in (None, ""):
            return []
        if isinstance(value, str):
            return [int(item.strip()) for item in value.split(",") if item.strip()]
        if isinstance(value, (list, tuple, set)):
            return [int(item) for item in value]
        raise ValueError("ID list must be a comma-separated string or a sequence of integers.")


def load_config() -> Config:
    return Config()
