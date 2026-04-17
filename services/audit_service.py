from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import Select, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models import AuditLog, Schedule
from services.notification_service import NotificationService


logger = logging.getLogger(__name__)
DAY_ORDER = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота"]


@dataclass(slots=True)
class LessonPayload:
    group_name: str
    day: str
    lesson_number: int
    subject: str
    teacher: str
    room: str
    start_time: str
    end_time: str
    is_change: bool = False


@dataclass(slots=True)
class ImportReport:
    updated_rows: int
    updated_groups: list[str]
    skipped_rows: int
    errors: list[str]


class ScheduleService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_groups(self) -> list[str]:
        query = select(Schedule.group_name).distinct().where(Schedule.group_name.is_not(None))
        values = await self._session.scalars(query.order_by(Schedule.group_name))
        return [item for item in values if item]

    async def list_days(self, group_name: str | None = None) -> list[str]:
        query = select(Schedule.day).distinct().where(Schedule.day.is_not(None))
        if group_name:
            query = query.where(Schedule.group_name == group_name)
        values = [item for item in await self._session.scalars(query) if item]
        order_map = {day: index for index, day in enumerate(DAY_ORDER)}
        return sorted(values, key=lambda item: order_map.get(item, len(order_map)))

    async def get_lessons(self, group_name: str, day: str) -> list[Schedule]:
        query = (
            select(Schedule)
            .where(Schedule.group_name == group_name, Schedule.day == day)
            .order_by(Schedule.lesson_number)
        )
        result = await self._session.scalars(query)
        return list(result)

    async def get_lesson(self, group_name: str, day: str, lesson_number: int) -> Schedule | None:
        query = select(Schedule).where(
            func.lower(func.trim(Schedule.group_name)) == group_name.lower().strip(),
            func.lower(func.trim(Schedule.day)) == day.lower().strip(),
            Schedule.lesson_number == lesson_number,
        )
        return await self._session.scalar(query)

    async def get_max_lesson_number(self) -> int:
        query: Select[tuple[int | None]] = select(func.max(Schedule.lesson_number))
        result = await self._session.execute(query)
        value = result.scalar_one_or_none()
        return value or 4

    async def import_changes_from_excel(self, excel_path: Path) -> ImportReport:
        import pandas as pd

        dataframe = pd.read_excel(excel_path, dtype=object)
        required_columns = {
            "group_name",
            "day",
            "lesson_number",
            "subject",
            "teacher",
            "room",
            "start_time",
            "end_time",
        }
        missing_columns = required_columns.difference(dataframe.columns)
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(f"В Excel отсутствуют обязательные колонки: {missing}.")

        data_list = []
        skipped_rows = 0
        errors: list[str] = []

        for row_number, row in enumerate(dataframe.to_dict(orient="records"), start=2):
            group_name = self._normalize_cell(row.get("group_name"))
            day = self._normalize_cell(row.get("day"))
            lesson_number = self._parse_lesson_number(row.get("lesson_number"))

            if not group_name or not day or lesson_number is None:
                skipped_rows += 1
                errors.append(f"Строка {row_number}: заполните group_name, day и lesson_number.")
                continue

            subject = self._normalize_cell(row.get("subject")) or ""
            teacher = self._normalize_cell(row.get("teacher")) or ""
            room = self._normalize_cell(row.get("room")) or ""
            start_time_raw = self._normalize_cell(row.get("start_time"))
            end_time_raw = self._normalize_cell(row.get("end_time"))

            start_time = self._normalize_time(start_time_raw) if start_time_raw else "00:00:00"
            end_time = self._normalize_time(end_time_raw) if end_time_raw else "00:00:00"

            if start_time_raw and not start_time:
                skipped_rows += 1
                errors.append(f"Строка {row_number}: неверный формат start_time.")
                continue
            if end_time_raw and not end_time:
                skipped_rows += 1
                errors.append(f"Строка {row_number}: неверный формат end_time.")
                continue

            raw_text = self._build_raw_text(subject, teacher, room)

            data = {
                "group_name": group_name,
                "day": day,
                "lesson_number": lesson_number,
                "subject": subject,
                "teacher": teacher,
                "room": room,
                "start_time": start_time,
                "end_time": end_time,
                "raw_text": raw_text,
                "is_change": True,
            }
            data_list.append(data)

        if data_list:
            logger.info(f"Импорт: {len(data_list)} строк")
            stmt = insert(Schedule).values(data_list)
            stmt = stmt.on_conflict_do_update(
                index_elements=["group_name", "day", "lesson_number"],
                set_={
                    "subject": stmt.excluded.subject,
                    "teacher": stmt.excluded.teacher,
                    "room": stmt.excluded.room,
                    "start_time": stmt.excluded.start_time,
                    "end_time": stmt.excluded.end_time,
                    "raw_text": stmt.excluded.raw_text,
                    "is_change": stmt.excluded.is_change,
                }
            )
            await self._session.execute(stmt)
            await self._session.commit()

        updated_rows = len(data_list)
        updated_groups = sorted(set(d["group_name"] for d in data_list))

        return ImportReport(
            updated_rows=updated_rows,
            updated_groups=updated_groups,
            skipped_rows=skipped_rows,
            errors=errors,
        )

    @staticmethod
    def _normalize_cell(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text or text.lower() == "nan":
            return None
        return text

    @staticmethod
    def _parse_lesson_number(value: object) -> int | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text or text.lower() == "nan":
            return None
        try:
            return int(float(text))
        except ValueError:
            return None

    @staticmethod
    def _normalize_time(value: str) -> str | None:
        import re
        match = re.match(r'^(\d{1,2}):(\d{2})(?::(\d{2}))?$', value)
        if not match:
            return None
        hours, minutes, seconds = match.groups()
        hours = hours.zfill(2)
        seconds = seconds or '00'
        return f"{hours}:{minutes}:{seconds}"

    @staticmethod
    def _build_raw_text(subject: str, teacher: str, room: str) -> str:
        return f"{subject}\n({teacher})   {room}"


class AuditService:
    def __init__(self, session: AsyncSession, notification_service: NotificationService) -> None:
        self._session = session
        self._notification_service = notification_service

    async def create_lesson(self, tg_id: int, full_name: str, payload: LessonPayload) -> AuditLog:
        existing = await self._get_lesson(payload.group_name, payload.day, payload.lesson_number)
        if existing is not None:
            raise ValueError("Для этой группы, дня и пары запись уже существует.")
        new_value = self._serialize_payload(payload)
        audit_log = self._build_audit_log(
            tg_id=tg_id,
            full_name=full_name,
            action="create_lesson",
            group_name=payload.group_name,
            day=payload.day,
            lesson_num=payload.lesson_number,
            old_value=None,
            new_value=new_value,
        )
        self._session.add(audit_log)
        await self._session.flush()
        lesson = Schedule(
            group_name=payload.group_name,
            day=payload.day,
            lesson_number=payload.lesson_number,
            subject=payload.subject,
            teacher=payload.teacher,
            room=payload.room,
            start_time=payload.start_time,
            end_time=payload.end_time,
            raw_text=self._build_raw_text(payload.subject, payload.teacher, payload.room),
            is_change=payload.is_change,
        )
        self._session.add(lesson)
        return await self._commit_and_notify(audit_log)

    async def update_lesson(self, tg_id: int, full_name: str, payload: LessonPayload) -> AuditLog:
        lesson = await self._get_lesson(payload.group_name, payload.day, payload.lesson_number)
        if lesson is None:
            raise ValueError("Запись для обновления не найдена.")
        old_value = self._serialize_lesson(lesson)
        new_value = self._serialize_payload(payload)
        audit_log = self._build_audit_log(
            tg_id=tg_id,
            full_name=full_name,
            action="update_lesson",
            group_name=payload.group_name,
            day=payload.day,
            lesson_num=payload.lesson_number,
            old_value=old_value,
            new_value=new_value,
        )
        self._session.add(audit_log)
        await self._session.flush()
        lesson.subject = payload.subject
        lesson.teacher = payload.teacher
        lesson.room = payload.room
        lesson.start_time = payload.start_time
        lesson.end_time = payload.end_time
        lesson.raw_text = self._build_raw_text(payload.subject, payload.teacher, payload.room)
        lesson.is_change = payload.is_change
        return await self._commit_and_notify(audit_log)

    async def delete_lesson(self, tg_id: int, full_name: str, group_name: str, day: str, lesson_number: int) -> AuditLog:
        lesson = await self._get_lesson(group_name, day, lesson_number)
        if lesson is None:
            raise ValueError("Запись для удаления не найдена.")
        old_value = self._serialize_lesson(lesson)
        audit_log = self._build_audit_log(
            tg_id=tg_id,
            full_name=full_name,
            action="delete_lesson",
            group_name=group_name,
            day=day,
            lesson_num=lesson_number,
            old_value=old_value,
            new_value=None,
        )
        self._session.add(audit_log)
        await self._session.flush()
        await self._session.delete(lesson)
        return await self._commit_and_notify(audit_log)

    async def set_change(
        self,
        tg_id: int,
        full_name: str,
        group_name: str,
        day: str,
        lesson_number: int,
        is_change: bool,
    ) -> AuditLog:
        lesson = await self._get_lesson(group_name, day, lesson_number)
        if lesson is None:
            raise ValueError("Запись для изменения статуса не найдена.")
        old_value = self._serialize_lesson(lesson)
        lesson.is_change = is_change
        new_value = self._serialize_lesson(lesson)
        audit_log = self._build_audit_log(
            tg_id=tg_id,
            full_name=full_name,
            action="set_change",
            group_name=group_name,
            day=day,
            lesson_num=lesson_number,
            old_value=old_value,
            new_value=new_value,
        )
        self._session.add(audit_log)
        await self._session.flush()
        return await self._commit_and_notify(audit_log)

    async def _get_lesson(self, group_name: str, day: str, lesson_number: int) -> Schedule | None:
        query = select(Schedule).where(
            Schedule.group_name == group_name,
            Schedule.day == day,
            Schedule.lesson_number == lesson_number,
        )
        return await self._session.scalar(query)

    async def _commit_and_notify(self, audit_log: AuditLog) -> AuditLog:
        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        await self._session.refresh(audit_log)
        await self._notification_service.notify_audit(audit_log)
        return audit_log

    def _build_audit_log(
        self,
        tg_id: int,
        full_name: str,
        action: str,
        group_name: str,
        day: str,
        lesson_num: int,
        old_value: str | None,
        new_value: str | None,
    ) -> AuditLog:
        return AuditLog(
            tg_id=tg_id,
            full_name=full_name,
            action=action,
            group_name=group_name,
            day=day,
            lesson_num=lesson_num,
            old_value=old_value,
            new_value=new_value,
            timestamp=datetime.now(),
        )

    @staticmethod
    def _serialize_lesson(lesson: Schedule) -> str:
        payload = {
            "id": lesson.id,
            "group_name": lesson.group_name,
            "day": lesson.day,
            "lesson_number": lesson.lesson_number,
            "subject": lesson.subject,
            "teacher": lesson.teacher,
            "room": lesson.room,
            "start_time": lesson.start_time,
            "end_time": lesson.end_time,
            "raw_text": lesson.raw_text,
            "is_change": lesson.is_change,
        }
        return json.dumps(payload, ensure_ascii=False)

    @staticmethod
    def _serialize_payload(payload: LessonPayload) -> str:
        data = {
            "group_name": payload.group_name,
            "day": payload.day,
            "lesson_number": payload.lesson_number,
            "subject": payload.subject,
            "teacher": payload.teacher,
            "room": payload.room,
            "start_time": payload.start_time,
            "end_time": payload.end_time,
            "raw_text": AuditService._build_raw_text(payload.subject, payload.teacher, payload.room),
            "is_change": payload.is_change,
        }
        return json.dumps(data, ensure_ascii=False)

    @staticmethod
    def _build_raw_text(subject: str, teacher: str, room: str) -> str:
        return f"{subject}\n({teacher})   {room}"
