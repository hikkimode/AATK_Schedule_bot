from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import json
import pandas as pd
from loguru import logger
from pydantic import ValidationError
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from models import AuditLog, BaseSchedule, ScheduleV2
from schemas.lesson import ImportResultSchema, LessonChangeSchema, LessonImportSchema


class BulkImportService:
    BATCH_SIZE = 100

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def import_from_excel(
        self,
        excel_path: Path,
        tg_id: int = 0,
        full_name: str = "System Import",
    ) -> ImportResultSchema:
        errors: list[str] = []
        changes_by_group: dict[str, list[LessonChangeSchema]] = {}

        try:
            df = pd.read_excel(excel_path, dtype=object)
        except Exception as e:
            raise ImportError(f"Failed to read Excel: {e}")

        required = {"group_name", "day", "lesson_number", "start_time", "end_time"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Missing columns: {', '.join(sorted(missing))}")

        valid_lessons: list[LessonImportSchema] = []
        for row_num, row in enumerate(df.to_dict(orient="records"), start=2):
            try:
                lesson = LessonImportSchema.model_validate(row)
                valid_lessons.append(lesson)
            except ValidationError as e:
                for err in e.errors():
                    loc = ", ".join(str(x) for x in err["loc"])
                    errors.append(f"Row {row_num}, column {loc}: {err['msg']}")

        if not valid_lessons:
            return ImportResultSchema(
                updated_rows=0,
                updated_groups=[],
                skipped_rows=len(errors),
                errors=errors,
                changes_by_group={},
            )

        base_count = await self._session.scalar(select(func.count(BaseSchedule.id))) or 0
        is_first_import = base_count == 0

        existing_map = await self._get_existing_lessons(valid_lessons)

        data_list: list[dict[str, Any]] = []
        for lesson in valid_lessons:
            key = (lesson.group_name, lesson.day, lesson.lesson_number)
            existing = existing_map.get(key)

            is_changed = False
            if existing:
                is_changed = self._detect_changes(lesson, existing)
                if is_changed:
                    changes = LessonChangeSchema(
                        day=lesson.day,
                        lesson_number=lesson.lesson_number,
                        old=existing,
                        new=lesson.to_dict(),
                    )
                    if lesson.group_name not in changes_by_group:
                        changes_by_group[lesson.group_name] = []
                    changes_by_group[lesson.group_name].append(changes)

            lesson_dict = lesson.to_dict()
            lesson_dict["is_change"] = is_changed
            data_list.append(lesson_dict)

        try:
            if is_first_import:
                await self._bulk_insert_base_schedule(data_list)
                logger.info(f"First import: saved {len(data_list)} records to base_schedule")

            await self._bulk_upsert_schedule(data_list)

            if changes_by_group:
                await self._log_changes(changes_by_group, tg_id, full_name)

            await self._session.commit()

            logger.info(
                f"Import completed: {len(data_list)} rows, "
                f"{sum(len(v) for v in changes_by_group.values())} changes"
            )

        except Exception:
            await self._session.rollback()
            raise

        updated_groups = sorted(set(lesson.group_name for lesson in valid_lessons))

        return ImportResultSchema(
            updated_rows=len(data_list),
            updated_groups=updated_groups,
            skipped_rows=len(errors),
            errors=errors,
            changes_by_group={
                k: [c.model_dump() for c in v] for k, v in changes_by_group.items()
            },
        )

    async def _get_existing_lessons(
        self, lessons: list[LessonImportSchema]
    ) -> dict[tuple[str, str, int], dict[str, Any]]:
        if not lessons:
            return {}

        keys = [(l.group_name, l.day, l.lesson_number) for l in lessons]

        query = select(Schedule).where(
            (Schedule.group_name, Schedule.day, Schedule.lesson_number).in_(keys)
        )
        result = await self._session.execute(query)

        return {
            (s.group_name, s.day, s.lesson_number): {
                "subject": s.subject,
                "teacher": s.teacher,
                "room": s.room,
                "start_time": s.start_time,
                "end_time": s.end_time,
            }
            for s in result.scalars()
        }

    def _detect_changes(
        self, new: LessonImportSchema, old: dict[str, Any]
    ) -> bool:
        return any(
            [
                new.subject != old.get("subject"),
                new.teacher != old.get("teacher"),
                new.room != old.get("room"),
                new.start_time != old.get("start_time"),
                new.end_time != old.get("end_time"),
            ]
        )

    async def _bulk_insert_base_schedule(self, data_list: list[dict[str, Any]]) -> None:
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

        for i in range(0, len(base_data), self.BATCH_SIZE):
            batch = base_data[i : i + self.BATCH_SIZE]
            await self._session.execute(pg_insert(BaseSchedule).values(batch))

    async def _bulk_upsert_schedule(self, data_list: list[dict[str, Any]]) -> None:
        for i in range(0, len(data_list), self.BATCH_SIZE):
            batch = data_list[i : i + self.BATCH_SIZE]

            stmt = pg_insert(Schedule).values(batch)
            stmt = stmt.on_conflict_do_update(
                index_elements=["group_name", "day", "lesson_number"],
                set_={
                    "subject": stmt.excluded.subject,
                    "teacher": stmt.excluded.teacher,
                    "room": stmt.excluded.room,
                    "start_time": stmt.excluded.start_time,
                    "end_time": stmt.excluded.end_time,
                    "raw_text": stmt.excluded.raw_text,
                    "is_change": stmt.excluded.is_change | Schedule.is_change,
                },
            )
            await self._session.execute(stmt)

    async def _log_changes(
        self,
        changes_by_group: dict[str, list[LessonChangeSchema]],
        tg_id: int,
        full_name: str,
    ) -> None:
        for group_name, changes in changes_by_group.items():
            for change in changes:
                audit_log = AuditLog(
                    tg_id=tg_id,
                    full_name=full_name,
                    action="import_lesson_change",
                    group_name=group_name,
                    day=change.day,
                    lesson_num=change.lesson_number,
                    old_value=json.dumps(change.old, ensure_ascii=False),
                    new_value=json.dumps(change.new, ensure_ascii=False),
                    timestamp=datetime.now(),
                )
                self._session.add(audit_log)
