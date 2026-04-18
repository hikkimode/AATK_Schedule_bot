from __future__ import annotations

from typing import Any, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Header, Query, BackgroundTasks
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from config import load_config
from database import _session_factory
from models import AuditLog, UserProfile
from schemas.schedule import AuditLogSchema, BroadcastRequestSchema, ScheduleUpdatePayloadSchema
from services.analytics_service import _analytics_cache, get_full_analytics
from services.broadcast_service import BroadcastService
from services.cache_service import invalidate_schedule_cache
from services.notification_worker import NotificationEnqueuer

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Load config once for API key verification
_config = load_config()


async def get_dashboard_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for DB session."""
    if _session_factory is None:
        raise RuntimeError("Database not initialized")
    async with _session_factory() as session:
        yield session


def verify_api_key(x_api_key: str | None = Header(None)) -> str:
    """Dependency to verify dashboard API key from headers."""
    expected_key = _config.dashboard_api_key
    if not expected_key:
        raise HTTPException(
            status_code=500, detail="DASHBOARD_API_KEY is not configured on the server"
        )
    if not x_api_key or x_api_key != expected_key:
        raise HTTPException(status_code=403, detail="Invalid or missing API Key")
    return x_api_key


@router.post("/broadcast")
async def trigger_broadcast(
    request: BroadcastRequestSchema,
    api_key: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_dashboard_session),
) -> dict[str, Any]:
    """Creates a broadcast task and pushes logic to NotificationWorker."""
    broadcast_service = BroadcastService()
    job_id = await broadcast_service.schedule_broadcast(
        session=session,
        message=request.message,
        groups=request.target_groups,
    )
    return {"status": "scheduled", "queued_messages": job_id}


@router.get("/audit-logs", response_model=dict[str, Any])
async def get_audit_logs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    action_filter: str | None = Query(None, description="Optional action filter like 'ERROR'"),
    api_key: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_dashboard_session),
) -> dict[str, Any]:
    """Retrieve audit logs with pagination and optional action filtering."""
    query = select(AuditLog)
    count_query = select(func.count(AuditLog.id))

    if action_filter:
        action_pattern = f"%{action_filter}%"
        query = query.where(AuditLog.action.ilike(action_pattern))
        count_query = count_query.where(AuditLog.action.ilike(action_pattern))

    # Calculate total count
    total_result = await session.execute(count_query)
    total_count = total_result.scalar_one()

    # Get logs
    query = query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit)
    result = await session.execute(query)
    logs = result.scalars().all()

    items = [AuditLogSchema.model_validate(log).model_dump() for log in logs]

    return {
        "items": items,
        "total": total_count,
        "limit": limit,
        "offset": offset,
    }


@router.get("/stats")
async def get_stats(
    api_key: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_dashboard_session),
) -> dict[str, Any]:
    """Provides high-level statistics for the dashboard."""
    # 1. Total and Active Users
    total_users = await session.scalar(select(func.count(UserProfile.tg_id))) or 0
    active_users = (
        await session.scalar(select(func.count(UserProfile.tg_id)).where(UserProfile.is_active == True))
        or 0
    )

    # 2. Number of active groups
    active_groups = (
        await session.scalar(
            select(func.count(func.distinct(UserProfile.group_name))).where(
                UserProfile.is_active == True, UserProfile.group_name.is_not(None)
            )
        )
        or 0
    )

    # 3. Errors in the last 24h
    time_threshold = datetime.now() - timedelta(hours=24)
    errors_24h = (
        await session.scalar(
            select(func.count(AuditLog.id)).where(
                AuditLog.action.ilike("%ERROR%"), AuditLog.timestamp >= time_threshold
            )
        )
        or 0
    )

    return {
        "total_users": total_users,
        "active_users": active_users,
        "active_groups": active_groups,
        "errors_24h": errors_24h,
    }


@router.post("/webhook/schedule-updated")
async def handle_schedule_update(
    payload: ScheduleUpdatePayloadSchema,
    api_key: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_dashboard_session),
) -> dict[str, Any]:
    """Handles real-time schedule updates."""
    # 1. Сброс кэша
    invalidate_schedule_cache(payload.group_name)
    
    # 2. Умная рассылка уведомлений через NotificationEnqueuer
    enqueuer = NotificationEnqueuer(session)
    enqueued_count = await enqueuer.enqueue_schedule_change_notifications(
        group_names=[payload.group_name],
        day=payload.day
    )
    
    return {
        "status": "ok", 
        "action": "cache_invalidated_and_notified",
        "enqueued": enqueued_count
    }


@router.get("/analytics")
async def get_analytics(
    days: int = Query(7, ge=1, le=90, description="Look-back window in days"),
    top_n: int = Query(5, ge=1, le=20, description="Top-N groups to return"),
    api_key: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_dashboard_session),
) -> dict[str, Any]:
    """
    Returns aggregated analytics payload for the Dashboard.

    All sub-queries are cached for 1 hour (TTL=3600s) to protect the DB.
    Recharts / Chart.js ready JSON format.

    Sections:
    - **activity_heatmap**: hourly request counts (0-23h) for a bar/area chart.
    - **top_groups**: top-N groups ranked by number of schedule reads.
    - **subgroup_distribution**: pie-chart data for subgroup split.
    - **language_distribution**: RU vs KK user split.
    - **notification_stats**: pending / sent / failed counts + success rate.
    """
    return await get_full_analytics(session, days=days, top_n=top_n)


@router.post("/analytics/cache-clear")
async def clear_analytics_cache(
    api_key: str = Depends(verify_api_key),
) -> dict[str, Any]:
    """Force-invalidates the analytics cache (e.g. after a large import)."""
    size_before = len(_analytics_cache)
    _analytics_cache.clear()
    return {"status": "cleared", "entries_removed": size_before}

