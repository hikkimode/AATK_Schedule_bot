from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from sqlalchemy import Select, func, select, delete, case
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models import AuditLog, BaseSchedule, ScheduleV2, UserProfile
from schemas.schedule import LessonItem
from services.notification_service import NotificationService
from services.notification_worker import NotificationEnqueuer


logger = logging.getLogger(__name__)
DAY_ORDER = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота"]


@dataclass(slots=True)
class LessonPayload:
    group_name: str
    day: str
    lesson_number: int
    subject: str | None
    teacher: str | None
    room: str | None
    start_time: str
    end_time: str
    is_change: bool = False


@dataclass(slots=True)
class ImportReport:
    updated_rows: int
    updated_groups: list[str]
    skipped_rows: int
    errors: list[str]
    changes_by_group: dict[str, list[dict]] = field(default_factory=dict)


class ScheduleService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_groups(self) -> list[str]:
        query = select(ScheduleV2.group_name).distinct().where(ScheduleV2.group_name.is_not(None))
        values = await self._session.scalars(query.order_by(ScheduleV2.group_name))
        return [item for item in values if item]

    async def list_days(self, group_name: str | None = None) -> list[str]:
        query = select(ScheduleV2.day).distinct().where(ScheduleV2.day.is_not(None))
        if group_name:
            query = query.where(ScheduleV2.group_name == group_name)
        values = [item for item in await self._session.scalars(query) if item]
        order_map = {day: index for index, day in enumerate(DAY_ORDER)}
        return sorted(values, key=lambda item: order_map.get(item, len(order_map)))

    async def get_lessons(self, group_name: str, day: str, subgroup: int = 0) -> list[LessonItem]:
        query = select(ScheduleV2).where(
            ScheduleV2.group_name == group_name,
            ScheduleV2.day == day
        )
        result = await self._session.execute(query)
        schedule_obj = result.scalar_one_or_none()
        
        if not schedule_obj:
            return []
            
        lessons_data = schedule_obj.lessons or []
        lessons = [LessonItem.model_validate(item) for item in lessons_data]
        
        # Filter by subgroup: 0 (all) + user's specific subgroup
        if subgroup != 0:
            lessons = [l for l in lessons if l.subgroup == 0 or l.subgroup == subgroup]
        
        return sorted(lessons, key=lambda x: x.num)

    async def get_lesson(self, group_name: str, day: str, lesson_number: int) -> LessonItem | None:
        query = select(ScheduleV2).where(
            func.lower(func.trim(ScheduleV2.group_name)) == group_name.lower().strip(),
            func.lower(func.trim(ScheduleV2.day)) == day.lower().strip(),
        )
        result = await self._session.execute(query)
        schedule_obj = result.scalar_one_or_none()
        
        if not schedule_obj or not schedule_obj.lessons:
            return None
            
        for item in schedule_obj.lessons:
            if item.get("num") == lesson_number:
                return LessonItem.model_validate(item)
        return None

    async def get_user_profile(self, tg_id: int) -> UserProfile | None:
        # Telegram IDs are stored as BIGINT in the DB to support values above int32 range.
        query = select(UserProfile).where(UserProfile.tg_id == tg_id)
        result = await self._session.scalar(query)
        logger.debug(f"get_user_profile({tg_id}): found={result is not None}")
        return result

    async def save_user_profile(
        self,
        tg_id: int,
        group_name: str | None = None,
        subgroup: int | None = None,
        language: str | None = None,
    ) -> UserProfile:
        # Always persist Telegram identifiers as 64-bit integers.
        profile = await self.get_user_profile(tg_id)
        if profile is None:
            profile = UserProfile(
                tg_id=tg_id,
                group_name=group_name,
                subgroup=subgroup or 0,
                language=language or "ru",
            )
            self._session.add(profile)
            logger.debug(f"save_user_profile({tg_id}): created new profile with subgroup={profile.subgroup}")
        else:
            if group_name is not None:
                profile.group_name = group_name
            if subgroup is not None:
                profile.subgroup = subgroup
            if language is not None:
                profile.language = language
            profile.updated_at = datetime.utcnow()
            logger.debug(f"save_user_profile({tg_id}): updated existing profile")
        try:
            await self._session.commit()
            logger.info(f"save_user_profile({tg_id}): committed to DB")
        except Exception as e:
            await self._session.rollback()
            logger.error(f"save_user_profile({tg_id}): DB commit failed: {e}")
            raise
        return profile

    async def get_max_lesson_number(self) -> int:
        query: Select[tuple[int | None]] = select(func.max(Schedule.lesson_number))
        result = await self._session.execute(query)
        value = result.scalar_one_or_none()
        return value or 4

    async def import_changes_from_excel(self, excel_path: Path) -> ImportReport:
        import pandas as pd

        # Oбeрнуто в to_thread, чтoбы избeжaть блoкирoвки event loop'а
        dataframe = await asyncio.to_thread(pd.read_excel, excel_path, dtype=object)
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
        changes_by_group: dict[str, list[dict]] = {}
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

            subject_raw = self._normalize_cell(row.get("subject"))
            teacher = self._normalize_cell(row.get("teacher"))
            room = self._normalize_cell(row.get("room"))
            start_time_raw = self._normalize_cell(row.get("start_time"))
            end_time_raw = self._normalize_cell(row.get("end_time"))

            # Subgroup detection from subject
            subgroup = 0
            subject = subject_raw
            if subject_raw:
                # Regex for: (1 подгр), 2 подгруппа, (1), 2гр etc.
                match = re.search(r"\(?\s*([12])\s*(?:подгр|гр|п)[а-яё]*\.?\s*\)?", subject_raw, re.IGNORECASE)
                if match:
                    subgroup = int(match.group(1))
                    # Clean name: "Physics (1 подгр)" -> "Physics"
                    subject = re.sub(r"\(?\s*[12]\s*(?:подгр|гр|п)[а-яё]*\.?\s*\)?", "", subject_raw, flags=re.IGNORECASE).strip()
                else:
                    # Alternative: just a single digit in parens
                    match_simple = re.search(r"\(\s*([12])\s*\)", subject_raw)
                    if match_simple:
                        subgroup = int(match_simple.group(1))
                        subject = re.sub(r"\(\s*[12]\s*\)", "", subject_raw).strip()

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

            # Check if lesson exists and detect changes
            existing_lesson = await self.get_lesson(group_name, day, lesson_number)
            is_changed = False
            if existing_lesson:
                # Compare key fields for changes
                if (
                    existing_lesson.subject != subject
                    or existing_lesson.teacher != teacher
                    or existing_lesson.room != room
                    or existing_lesson.start_time != start_time
                    or existing_lesson.end_time != end_time
                ):
                    is_changed = True
                    # Record change for broadcast
                    if group_name not in changes_by_group:
                        changes_by_group[group_name] = []
                    changes_by_group[group_name].append({
                        "day": day,
                        "lesson_number": lesson_number,
                        "old": {
                            "subject": existing_lesson.subject,
                            "teacher": existing_lesson.teacher,
                            "room": existing_lesson.room,
                            "start_time": existing_lesson.start_time,
                            "end_time": existing_lesson.end_time,
                        },
                        "new": {
                            "subject": subject,
                            "teacher": teacher,
                            "room": room,
                            "start_time": start_time,
                            "end_time": end_time,
                        },
                    })
            else:
                # New lesson - not marked as change
                is_changed = False

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
                "subgroup": subgroup,
                "is_change": is_changed,
            }
            data_list.append(data)

        if data_list:
            logger.info(f"Импорт: {len(data_list)} строк, изменений: {len(changes_by_group)} групп")

            # Проверяем, есть ли базовое расписание (первичный импорт)
            base_count_result = await self._session.execute(select(func.count(BaseSchedule.id)))
            base_count = base_count_result.scalar() or 0
            is_first_import = base_count == 0

            if is_first_import:
                logger.info(f"Первичный импорт: сохраняем {len(data_list)} записей в base_schedule")
                # Подготовка данных для base_schedule (без is_change)
                base_data = [
                    {
                        "group_name": d["group_name"],
                        "day": d["day"],
                        "lesson_number": d["lesson_number"],
                        "subject": d["subject"],
                        "teacher": d["teacher"],
                        "room": d["room"],
                        "start_time": d["start_time"],
                        "end_time": d["end_time"],
                        "raw_text": d["raw_text"],
                    }
                    for d in data_list
                ]
                await self._session.execute(insert(BaseSchedule).values(base_data))

            # Обновляем текущее расписание (ScheduleV2)
            affected_groups = {d["group_name"] for d in data_list}
            existing_schedules = await self._session.scalars(
                select(ScheduleV2).where(ScheduleV2.group_name.in_(affected_groups))
            )
            schedules_map = {(s.group_name, s.day): s for s in existing_schedules}

            # Группируем новые данные
            import collections
            grouped_new_data = collections.defaultdict(list)
            for d in data_list:
                grouped_new_data[(d["group_name"], d["day"])].append(d)

            for key, new_lessons in grouped_new_data.items():
                group_name, day = key
                if key in schedules_map:
                    # Обновляем существующий массив уроков
                    s = schedules_map[key]
                    existing_lessons = {item.get("num"): item for item in s.lessons}
                    for new_d in new_lessons:
                        num = new_d["lesson_number"]
                        # Priority: existing is_change=True > new is_change=True > False
                        old_is_change = False
                        if num in existing_lessons:
                            old_is_change = existing_lessons[num].get("is_change", False)
                            
                        existing_lessons[num] = {
                            "num": num,
                            "name": new_d["subject"],
                            "teacher": new_d["teacher"],
                            "room": new_d["room"],
                            "time_start": new_d["start_time"],
                            "time_end": new_d["end_time"],
                            "is_change": old_is_change or new_d["is_change"],
                            "subgroup": new_d["subgroup"],
                            "is_published": True
                        }
                    s.lessons = list(existing_lessons.values())
                    s.lessons.sort(key=lambda x: x.get("num", 0))
                else:
                    # Создаем новую запись для группы и дня
                    lessons = [{
                        "num": new_d["lesson_number"],
                        "name": new_d["subject"],
                        "teacher": new_d["teacher"],
                        "room": new_d["room"],
                        "time_start": new_d["start_time"],
                        "time_end": new_d["end_time"],
                        "is_change": new_d["is_change"],
                        "subgroup": new_d["subgroup"],
                        "is_published": True
                    } for new_d in new_lessons]
                    lessons.sort(key=lambda x: x.get("num", 0))
                    
                    new_sched = ScheduleV2(
                        group_name=group_name,
                        day=day,
                        lessons=lessons
                    )
                    self._session.add(new_sched)

            try:

                # Log imported changes to audit trail (до commit, для атомарности)
                for group_name, changes in changes_by_group.items():
                    for change in changes:
                        audit_log = AuditLog(
                            tg_id=0,  # System import
                            full_name="System Import",
                            action="import_lesson_change",
                            group_name=group_name,
                            day=change["day"],
                            lesson_num=change["lesson_number"],
                            old_value=json.dumps(change["old"], ensure_ascii=False),
                            new_value=json.dumps(change["new"], ensure_ascii=False),
                            timestamp=datetime.now(),
                        )
                        self._session.add(audit_log)

                # Единый commit для всех изменений (атомарная операция)
                await self._session.commit()

                if changes_by_group:
                    logger.info(f"Audit logged {sum(len(v) for v in changes_by_group.values())} changes")
                    
                    # C3: Reactive Notifications Enqueue
                    try:
                        enqueuer = NotificationEnqueuer(self._session)
                        enqueued = await enqueuer.enqueue_schedule_change_notifications(
                            group_names=list(changes_by_group.keys())
                        )
                        logger.info(f"Reactive notifications enqueued: {enqueued}")
                    except Exception as ne:
                        logger.error(f"Failed to enqueue reactive notifications: {ne}")
            except Exception:
                await self._session.rollback()
                raise

        updated_rows = len(data_list)
        updated_groups = sorted(set(d["group_name"] for d in data_list))

        return ImportReport(
            updated_rows=updated_rows,
            updated_groups=updated_groups,
            skipped_rows=skipped_rows,
            errors=errors,
            changes_by_group=changes_by_group,
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
    def _build_raw_text(subject: str | None, teacher: str | None, room: str | None) -> str:
        subj = subject or ""
        teach = teacher or ""
        rm = room or ""
        return f"{subj}\n({teach})   {rm}"


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

    async def reset_all_changes(self, tg_id: int, full_name: str) -> int:
        """
        Сброс расписания к базовому (первичному) состоянию.

        Удаляет ВСЕ записи из schedule (всех групп) и копирует ВСЕ данные из base_schedule.
        Возвращает количество восстановленных записей.

        Raises:
            ValueError: Если base_schedule пуст (базовое расписание не загружено).
        """
        from sqlalchemy import delete

        # Проверяем, есть ли базовое расписание
        base_count_query = select(func.count(BaseSchedule.id))
        base_count_result = await self._session.scalar(base_count_query)
        base_count = base_count_result or 0

        if base_count == 0:
            raise ValueError("Базовое расписание не найдено. Сначала загрузите первичный Excel файл.")

        # Получаем текущее количество записей в schedule для логирования
        current_count_query = select(func.count(Schedule.id))
        current_count = await self._session.scalar(current_count_query) or 0

        try:
            # Удаляем ВСЕ записи из текущего расписания (без фильтров - все группы)
            await self._session.execute(delete(Schedule))

            # Получаем все записи из base_schedule (все группы, все дни)
            base_records_result = await self._session.execute(select(BaseSchedule))
            base_records = base_records_result.scalars().all()

            # Восстанавливаем все записи из base_schedule
            restored_count = 0
            for base in base_records:
                schedule_record = Schedule(
                    group_name=base.group_name,
                    day=base.day,
                    lesson_number=base.lesson_number,
                    subject=base.subject,
                    teacher=base.teacher,
                    room=base.room,
                    start_time=base.start_time,
                    end_time=base.end_time,
                    raw_text=base.raw_text,
                    is_change=False,  # Базовое расписание - не изменения
                )
                self._session.add(schedule_record)
                restored_count += 1

            # Логируем действие
            audit_log = self._build_audit_log(
                tg_id=tg_id,
                full_name=full_name,
                action="reset_to_base",
                group_name="*",
                day="*",
                lesson_num=0,
                old_value=f"Schedule had {current_count} records before reset",
                new_value=f"Restored {restored_count} records from base_schedule",
            )
            self._session.add(audit_log)

            await self._session.commit()
            logger.info(f"Reset to base: removed {current_count} records, restored {restored_count} from base_schedule")

            return restored_count
        except Exception:
            await self._session.rollback()
            raise

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
    def _build_raw_text(subject: str | None, teacher: str | None, room: str | None) -> str:
        subj = subject or ""
        teach = teacher or ""
        rm = room or ""
        return f"{subj}\n({teach})   {rm}"
