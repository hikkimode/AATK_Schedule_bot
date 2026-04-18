"""
Verification test for the C4 Analytics Service.
Creates a small in-memory DB with sample data and asserts every endpoint shape.
"""

import asyncio
import time
from datetime import datetime, timedelta
import random

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from models import Base, UserProfile, AuditLog, NotificationQueue, NotificationStatus
from services.analytics_service import (
    get_activity_heatmap,
    get_top_groups,
    get_subgroup_distribution,
    get_language_distribution,
    get_notification_stats,
    get_full_analytics,
    _analytics_cache,
)

GROUPS = ["ВТ-22", "ВТ-23", "ТМ-21", "ПВ-22", "КС-23"]
ACTION = "get_lessons"


async def seed_db(session):
    """Populate test data."""
    # Users
    users = []
    uid = 1
    for g in GROUPS:
        for sg in [0, 1, 1, 2, 2]:  # realistic subgroup ratio
            lang = "ru" if random.random() > 0.3 else "kk"
            users.append(UserProfile(tg_id=uid, group_name=g, subgroup=sg, language=lang, is_active=True))
            uid += 1
    session.add_all(users)

    # AuditLogs spread over 7 days with hour bias (morning peak)
    now = datetime.now()
    logs = []
    for i in range(300):
        hour = random.choices(range(24), weights=[
            1,1,1,1,2,3,10,15,12,8,6,5,4,6,8,7,5,4,3,2,2,1,1,1
        ])[0]
        ts = now - timedelta(days=random.randint(0, 6)) + timedelta(hours=hour - now.hour)
        grp = random.choice(GROUPS)
        logs.append(AuditLog(
            tg_id=random.randint(1, uid),
            full_name="Test User",
            action=ACTION,
            group_name=grp,
            day="Пн",
            lesson_num=1,
            timestamp=ts,
        ))
    session.add_all(logs)

    # Notification queue entries
    for st in [NotificationStatus.SENT]*50 + [NotificationStatus.FAILED]*3 + [NotificationStatus.PENDING]*2:
        session.add(NotificationQueue(
            user_id=random.randint(1, uid),
            message_text="Test",
            status=st.value,
            created_at=now,
        ))

    await session.commit()


async def run():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with factory() as session:
        await seed_db(session)

    # Clear any cached state from module import
    _analytics_cache.clear()

    async with factory() as session:
        print("\n=== C4 Analytics Verification ===\n")

        # 1. Heatmap
        heatmap = await get_activity_heatmap(session, days=7, action=ACTION)
        assert len(heatmap) == 24, "Heatmap must have 24 buckets"
        peek = max(heatmap, key=lambda x: x["count"])
        print(f"[Heatmap] 24 buckets OK. Peak hour: {peek['hour']}:00 → {peek['count']} requests")

        # 2. Top groups
        top = await get_top_groups(session, top_n=3, days=7)
        assert len(top) <= 3
        print(f"[Top Groups] Top-3: {[(r['group_name'], r['count']) for r in top]}")

        # 3. Subgroup distribution
        sg = await get_subgroup_distribution(session)
        total = sg["total"]
        assert total == sum(d["count"] for d in sg["distribution"])
        dist_str = ", ".join(f"{d['label']}: {d['pct']}%" for d in sg["distribution"])
        print(f"[Subgroup] Total active: {total}. Distribution: {dist_str}")

        # 4. Language distribution
        ld = await get_language_distribution(session)
        print(f"[Language] Distribution: {[(d['language'], d['pct']) for d in ld['distribution']]}")

        # 5. Notifications
        ns = await get_notification_stats(session)
        assert ns["sent"] == 50
        assert ns["failed"] == 3
        print(f"[Notifications] Sent={ns['sent']}, Failed={ns['failed']}, Rate={ns['success_rate_pct']}%")

        # 6. Full payload
        t0 = time.perf_counter()
        full = await get_full_analytics(session, days=7, top_n=5)
        t1 = time.perf_counter()
        assert "meta" in full and "activity_heatmap" in full
        print(f"[Full analytics] Keys: {list(full.keys())}")
        print(f"[Cache] First call took {(t1-t0)*1000:.1f}ms")

        # 7. Second call should be instant (cache hit)
        t0 = time.perf_counter()
        await get_full_analytics(session, days=7, top_n=5)
        t1 = time.perf_counter()
        print(f"[Cache] Cached call took {(t1-t0)*1000:.2f}ms (should be <1ms)")

    print("\n[SUCCESS] All analytics checks passed ✅")


if __name__ == "__main__":
    asyncio.run(run())
