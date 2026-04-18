import asyncio
import os
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from models import ScheduleV2 as Schedule

async def migrate_schedule():
    # 1. Проверка локальной базы
    local_db_path = Path("schedule.db")
    if not local_db_path.exists():
        print("Ошибка: schedule.db не найден в текущей директории.")
        return

    local_engine = create_engine(f"sqlite:///{local_db_path}")

    # 2. Чистые данные для Supabase (БЕЗ скобок и лишних знаков)
    DB_USER = "postgres.cicnrmzqhmpycbnchlnw"
    DB_PASS = "oi0VeaceohNVEXnv"  # Убедись, что это актуальный пароль!
    DB_HOST = "aws-1-ap-northeast-1.pooler.supabase.com"
    DB_PORT = "6543"
    DB_NAME = "postgres"

    # Формируем URL вручную для надежности
    supabase_url = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    
    supabase_engine = create_async_engine(
        supabase_url,
        connect_args={
            "prepared_statement_cache_size": 0,
            "statement_cache_size": 0
        },
        pool_pre_ping=True,
        pool_recycle=300
    )

    try:
        # 3. Чтение данных из SQLite
        with local_engine.connect() as conn:
            result = conn.execute(text("SELECT group_name, day, lesson_number, subject, teacher, room, start_time, end_time, raw_text, is_change FROM schedule"))
            rows = result.fetchall()

        print(f"Найдено {len(rows)} записей. Начинаю загрузку в Supabase...")

        # 4. Загрузка через сессию
        async with AsyncSession(supabase_engine) as session:
            async with session.begin():
                schedules = [
                    Schedule(
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
                    ) for row in rows
                ]
                session.add_all(schedules)
            await session.commit()

        print("✅ Миграция завершена успешно!")

    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
    finally:
        await supabase_engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate_schedule())