import asyncio
import os
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from models import Schedule


async def migrate_schedule():
    # Local SQLite database path
    local_db_path = "schedule.db"
    local_engine = create_engine(f"sqlite:///{local_db_path}")

    # Supabase database URL from environment or config
    supabase_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres.cicnrmzqhmpycbnchlnw:[oi0VeaceohNVEXnv]@aws-1-ap-northeast-1.pooler.supabase.com:6543/postgres")
    supabase_engine = create_async_engine(
        supabase_url,
        connect_args={
            "prepared_statement_cache_size": 0,
            "statement_cache_size": 0
        },
        pool_pre_ping=True,
        pool_recycle=300
    )

    # Read all records from local SQLite
    with local_engine.connect() as conn:
        result = conn.execute(text("SELECT group_name, day, lesson_number, subject, teacher, room, start_time, end_time, raw_text, is_change FROM schedule"))
        rows = result.fetchall()

    print(f"Found {len(rows)} records in local database.")

    # Create Schedule objects
    schedules = []
    for row in rows:
        schedule = Schedule(
            group_name=row[0],
            day=row[1],
            lesson_number=row[2],
            subject=row[3],
            teacher=row[4],
            room=row[5],
            start_time=row[6],
            end_time=row[7],
            raw_text=row[8],
            is_change=row[9]
        )
        schedules.append(schedule)

    # Insert into Supabase using AsyncSession
    async with AsyncSession(supabase_engine) as session:
        session.add_all(schedules)
        await session.commit()

    print("Migration completed successfully.")

    await supabase_engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate_schedule())