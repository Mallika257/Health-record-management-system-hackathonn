"""
/api/v1/notifications — In-app notification management.
"""

from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.models import Notification
from app.schemas.schemas import NotificationResponse, PaginatedResponse
from datetime import datetime, timezone

router = APIRouter()


@router.get("/", response_model=PaginatedResponse)
async def list_notifications(
    page: int = Query(1, ge=1),
    size: int = Query(30, ge=1, le=100),
    unread_only: bool = Query(False),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    query = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        query = query.where(Notification.is_read == False)
    query = query.order_by(Notification.created_at.desc())

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar()
    result = await db.execute(query.offset((page - 1) * size).limit(size))
    items = result.scalars().all()

    return {"items": items, "total": total, "page": page, "size": size, "pages": -(-total // size)}


@router.get("/unread-count")
async def unread_count(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(func.count()).where(
            Notification.user_id == user_id,
            Notification.is_read == False,
        )
    )
    return {"count": result.scalar()}


@router.post("/{notif_id}/read", response_model=NotificationResponse)
async def mark_as_read(
    notif_id: UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification).where(
            Notification.id == notif_id,
            Notification.user_id == user_id,
        )
    )
    notif = result.scalar_one_or_none()
    if notif and not notif.is_read:
        notif.is_read = True
        notif.read_at = datetime.now(timezone.utc)
    return notif


@router.post("/mark-all-read")
async def mark_all_read(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read == False)
        .values(is_read=True, read_at=datetime.now(timezone.utc))
    )
    return {"message": "All notifications marked as read"}
