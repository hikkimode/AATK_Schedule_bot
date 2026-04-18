
import asyncio
import json
from datetime import datetime
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from models import Base, UserProfile, ScheduleV2, NotificationQueue, NotificationStatus
from services.notification_worker import NotificationEnqueuer

async def test_notifications():
    # Setup test DB (SQLite in-memory or file)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    async with session_factory() as session:
        # 1. Create Test Users
        users = [
            UserProfile(tg_id=1, group_name="TEST-1", subgroup=0, is_active=True, language="ru"),  # Starosta
            UserProfile(tg_id=2, group_name="TEST-1", subgroup=1, is_active=True, language="ru"),  # Subgroup 1
            UserProfile(tg_id=3, group_name="TEST-1", subgroup=2, is_active=True, language="ru"),  # Subgroup 2
            UserProfile(tg_id=4, group_name="TEST-2", subgroup=1, is_active=True, language="ru"),  # Other group
        ]
        session.add_all(users)
        
        # 2. Create ScheduleV2 with changes
        # Lessons for Monday:
        # 1. Common (is_change=True)
        # 2. Subgroup 1 (is_change=True)
        # 3. Subgroup 2 (is_change=False) -> Should not show up
        # 4. Subgroup 2 (is_change=True)
        lessons = [
            {"num": 1, "name": "Common Lesson", "subgroup": 0, "is_change": True, "time_start": "08:00", "time_end": "09:30"},
            {"num": 2, "name": "Sub 1 Lesson", "subgroup": 1, "is_change": True, "time_start": "09:40", "time_end": "11:10"},
            {"num": 3, "name": "Sub 2 Stable", "subgroup": 2, "is_change": False, "time_start": "11:20", "time_end": "12:50"},
            {"num": 4, "name": "Sub 2 Lesson", "subgroup": 2, "is_change": True, "time_start": "13:00", "time_end": "14:30"},
        ]
        
        s_v2 = ScheduleV2(
            group_name="TEST-1",
            day="Пн",
            lessons=lessons
        )
        session.add(s_v2)
        await session.commit()
        
        # 3. Run Enqueuer
        print("\n--- Running Enqueuer ---")
        enqueuer = NotificationEnqueuer(session)
        count = await enqueuer.enqueue_schedule_change_notifications(group_names=["TEST-1"], day="Пн")
        print(f"Total notifications enqueued: {count}")
        await session.commit()
        
        # 4. Verify Queue
        result = await session.execute(select(NotificationQueue).order_by(NotificationQueue.user_id))
        queue = result.scalars().all()
        
        print("\n--- Queue Results ---")
        for item in queue:
            print(f"\n[User {item.user_id}]")
            print(f"Message:\n{item.message_text}")
            
            if item.user_id == 1: # Starosta
                # Should see 1, 2, 4
                assert "Common Lesson" in item.message_text
                assert "Sub 1 Lesson" in item.message_text
                assert "Sub 2 Lesson" in item.message_text
                assert "Sub 2 Stable" not in item.message_text
                print("✅ Starosta sees all changes.")
            
            elif item.user_id == 2: # Sub 1
                # Should see 1, 2
                assert "Common Lesson" in item.message_text
                assert "Sub 1 Lesson" in item.message_text
                assert "Sub 2 Lesson" not in item.message_text
                print("✅ Subgroup 1 sees common + own.")
                
            elif item.user_id == 3: # Sub 2
                # Should see 1, 4
                assert "Common Lesson" in item.message_text
                assert "Sub 1 Lesson" not in item.message_text
                assert "Sub 2 Lesson" in item.message_text
                print("✅ Subgroup 2 sees common + own.")

    print("\n[SUCCESS] Notification logic verified!")

if __name__ == "__main__":
    asyncio.run(test_notifications())
