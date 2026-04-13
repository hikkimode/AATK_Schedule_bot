from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import AuditLog, Schedule
from services.notification_service import NotificationService


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


class ScheduleService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_groups(self) -> list[str]:
        query = select(Schedule.group_name).distinct().where(Schedule.group_name.is_not(None))
        values = await self._session.scalars(query.order_by(Schedule.group_name))
        return [item for item in values if item]

    async def list_days(self) -> list[str]:
        query = select(Schedule.day).distinct().where(Schedule.day.is_not(None))
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
            Schedule.group_name == group_name,
            Schedule.day == day,
            Schedule.lesson_number == lesson_number,
        )
        return await self._session.scalar(query)

    async def get_max_lesson_number(self) -> int:
        query: Select[tuple[int | None]] = select(func.max(Schedule.lesson_number))
        result = await self._session.execute(query)
        value = result.scalar_one_or_none()
        return value or 4


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
