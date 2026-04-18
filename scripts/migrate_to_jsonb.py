import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, text
from loguru import logger
from database import AsyncSessionLocal, create_engine_and_sessionmaker
from config import load_config
from models import ScheduleLegacy, ScheduleV2
from utils.exceptions import setup_logging

setup_logging()

async def run_migration():
    logger.info("Starting data migration to JSONB...")
    config = load_config()
    engine, _ = create_engine_and_sessionmaker(config.database_url)
    
    async with AsyncSessionLocal() as session:
        try:
            # 1. Fetch all items from schedule_legacy using raw SQL
            query = text("SELECT * FROM schedule_legacy ORDER BY group_name, day, lesson_number")
            result = await session.execute(query)
            old_records = list(result.mappings().all())

            logger.info(f"Loaded {len(old_records)} records from schedule_legacy")

            if not old_records:
                logger.info("No records to migrate.")
                return

            grouped_data = {}
            # Group by (group_name, day)
            for r in old_records:
                group_name = r.get("group_name")
                day = r.get("day")
                key = (group_name, day)
                if key not in grouped_data:
                    grouped_data[key] = []
                
                lesson_obj = {
                    "num": r.get("lesson_number"),
                    "name": r.get("subject"),
                    "room": r.get("room"),
                    "teacher": r.get("teacher"),
                    "time_start": r.get("start_time"),
                    "time_end": r.get("end_time"),
                    "is_change": r.get("is_change", 0) == 1,
                    "is_published": r.get("is_published", 1) == 1,
                }
                grouped_data[key].append(lesson_obj)

            # Insert into schedule_v2
            inserted_count = 0
            for (group_name, day), lessons in grouped_data.items():
                if not group_name or not day:
                    continue  # skip invalid rows if any
                
                new_schedule = ScheduleV2(
                    group_name=group_name,
                    day=day,
                    lessons=lessons
                )
                session.add(new_schedule)
                inserted_count += 1

            await session.commit()
            logger.info(f"Successfully migrated {len(old_records)} old records into {inserted_count} JSONB rows in schedule_v2.")
        
        except Exception as e:
            await session.rollback()
            logger.error(f"Migration failed! Rolled back. Error: {e}")
            raise

if __name__ == "__main__":
    asyncio.run(run_migration())
