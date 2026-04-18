"""
Analytics service for the AATK Schedule Bot dashboard.

Aggregates data from audit_logs and user_profiles to produce:
  - Hourly activity heatmap (when students check schedules)
  - Top-N active groups by request volume
  - Subgroup distribution
  - Language distribution
  - Notification queue statistics

All heavy queries are memoized for 1 hour to protect the DB.
"""

from __future__ import annotations

import time
from typing import Any

from cachetools import TTLCache
from loguru import logger
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import AuditLog, NotificationQueue, NotificationStatus, UserProfile

# Analytics cache: max 10 distinct result sets, 1-hour TTL
_analytics_cache: TTLCache = TTLCache(maxsize=10, ttl=3600)

_ACTION_READ = "get_lessons"  # action name for student schedule reads


async def get_activity_heatmap(
    session: AsyncSession,
    days: int = 7,
    action: str = _ACTION_READ,
) -> list[dict[str, int]]:
    """
    Returns hourly view counts over the last N days, formatted for a heatmap/bar chart.

    Shape: [{"hour": 0, "count": 12}, ..., {"hour": 23, "count": 45}]
    """
    cache_key = f"heatmap:{days}:{action}"
    if cache_key in _analytics_cache:
        logger.debug("Analytics cache hit: %s", cache_key)
        return _analytics_cache[cache_key]

    from datetime import datetime, timedelta
    cutoff = datetime.now() - timedelta(days=days)

    hour_expr = func.strftime("%H", AuditLog.timestamp)  # SQLite
    # For PostgreSQL: func.extract("hour", AuditLog.timestamp)

    result = await session.execute(
        select(
            hour_expr.label("hour"),
            func.count(AuditLog.id).label("count"),
        )
        .where(AuditLog.timestamp >= cutoff, AuditLog.action == action)
        .group_by(hour_expr)
        .order_by(hour_expr)
    )
    rows = result.all()

    # Ensure all 24 hours are represented even if no data
    counts: dict[int, int] = {h: 0 for h in range(24)}
    for row in rows:
        try:
            counts[int(row.hour)] = row.count
        except (TypeError, ValueError):
            pass

    heatmap = [{"hour": h, "count": counts[h]} for h in range(24)]
    _analytics_cache[cache_key] = heatmap
    return heatmap


async def get_top_groups(
    session: AsyncSession,
    top_n: int = 5,
    days: int = 7,
) -> list[dict[str, Any]]:
    """
    Returns the top N groups by number of audit log events in the last N days.

    Shape: [{"group_name": "ВТ-22", "count": 130}, ...]
    """
    cache_key = f"top_groups:{top_n}:{days}"
    if cache_key in _analytics_cache:
        return _analytics_cache[cache_key]

    from datetime import datetime, timedelta
    cutoff = datetime.now() - timedelta(days=days)

    result = await session.execute(
        select(
            AuditLog.group_name,
            func.count(AuditLog.id).label("count"),
        )
        .where(AuditLog.timestamp >= cutoff, AuditLog.group_name.is_not(None))
        .group_by(AuditLog.group_name)
        .order_by(func.count(AuditLog.id).desc())
        .limit(top_n)
    )
    data = [{"group_name": row.group_name, "count": row.count} for row in result.all()]
    _analytics_cache[cache_key] = data
    return data


async def get_subgroup_distribution(
    session: AsyncSession,
) -> dict[str, Any]:
    """
    Returns the count and percentage of active users per subgroup (0, 1, 2).

    Shape: {
        "total": 320,
        "distribution": [
            {"subgroup": 0, "label": "Whole group", "count": 45, "pct": 14.1},
            {"subgroup": 1, "label": "Subgroup 1", "count": 150, "pct": 46.9},
            {"subgroup": 2, "label": "Subgroup 2", "count": 125, "pct": 39.0},
        ]
    }
    """
    cache_key = "subgroup_dist"
    if cache_key in _analytics_cache:
        return _analytics_cache[cache_key]

    result = await session.execute(
        select(
            UserProfile.subgroup,
            func.count(UserProfile.tg_id).label("count"),
        )
        .where(UserProfile.is_active == True)
        .group_by(UserProfile.subgroup)
        .order_by(UserProfile.subgroup)
    )
    rows = result.all()

    total = sum(row.count for row in rows)
    labels = {0: "Whole group (Starosta)", 1: "Subgroup 1", 2: "Subgroup 2"}
    distribution = [
        {
            "subgroup": row.subgroup,
            "label": labels.get(row.subgroup, f"Subgroup {row.subgroup}"),
            "count": row.count,
            "pct": round(row.count / total * 100, 1) if total else 0.0,
        }
        for row in rows
    ]

    data: dict[str, Any] = {"total": total, "distribution": distribution}
    _analytics_cache[cache_key] = data
    return data


async def get_language_distribution(
    session: AsyncSession,
) -> dict[str, Any]:
    """
    Returns the count and percentage of active users per language.

    Shape: {"total": 320, "distribution": [{"language": "ru", "count": 280, "pct": 87.5}, ...]}
    """
    cache_key = "lang_dist"
    if cache_key in _analytics_cache:
        return _analytics_cache[cache_key]

    result = await session.execute(
        select(
            UserProfile.language,
            func.count(UserProfile.tg_id).label("count"),
        )
        .where(UserProfile.is_active == True)
        .group_by(UserProfile.language)
        .order_by(func.count(UserProfile.tg_id).desc())
    )
    rows = result.all()

    total = sum(row.count for row in rows)
    distribution = [
        {
            "language": row.language,
            "count": row.count,
            "pct": round(row.count / total * 100, 1) if total else 0.0,
        }
        for row in rows
    ]

    data: dict[str, Any] = {"total": total, "distribution": distribution}
    _analytics_cache[cache_key] = data
    return data


async def get_notification_stats(
    session: AsyncSession,
) -> dict[str, Any]:
    """
    Returns counts of notifications in each status bucket,
    plus the delivery success rate over all time.

    Shape: {"pending": 5, "sent": 1200, "failed": 22, "success_rate_pct": 98.2}
    """
    cache_key = "notif_stats"
    if cache_key in _analytics_cache:
        return _analytics_cache[cache_key]

    result = await session.execute(
        select(
            NotificationQueue.status,
            func.count(NotificationQueue.id).label("count"),
        )
        .group_by(NotificationQueue.status)
    )
    rows = {row.status: row.count for row in result.all()}

    pending = rows.get(NotificationStatus.PENDING.value, 0)
    sent = rows.get(NotificationStatus.SENT.value, 0)
    failed = rows.get(NotificationStatus.FAILED.value, 0)
    delivered = sent + failed
    success_rate = round(sent / delivered * 100, 1) if delivered else 0.0

    data: dict[str, Any] = {
        "pending": pending,
        "sent": sent,
        "failed": failed,
        "success_rate_pct": success_rate,
    }
    _analytics_cache[cache_key] = data
    return data


async def get_full_analytics(
    session: AsyncSession,
    days: int = 7,
    top_n: int = 5,
) -> dict[str, Any]:
    """
    Convenience wrapper — returns all analytics in a single response.
    All individual queries use the shared TTL cache, so repeated calls are free.
    """
    heatmap, top_groups, subgroups, langs, notifs = (
        await get_activity_heatmap(session, days=days),
        await get_top_groups(session, top_n=top_n, days=days),
        await get_subgroup_distribution(session),
        await get_language_distribution(session),
        await get_notification_stats(session),
    )
    return {
        "meta": {
            "period_days": days,
            "cache_ttl_seconds": _analytics_cache.ttl,
            "generated_at": int(time.time()),
        },
        "activity_heatmap": heatmap,
        "top_groups": top_groups,
        "subgroup_distribution": subgroups,
        "language_distribution": langs,
        "notification_stats": notifs,
    }
