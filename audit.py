"""
/api/v1/audit — Audit log access (admin + self).
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.security import get_current_user_id, require_role
from app.models.models import AuditLog, UserRole
from app.schemas.schemas import AuditLogResponse, PaginatedResponse

router = APIRouter()


@router.get("/my", response_model=PaginatedResponse)
async def list_my_audit_logs(
    page: int = Query(1, ge=1),
    size: int = Query(30, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Any user can view their own audit trail."""
    query = (
        select(AuditLog)
        .where(AuditLog.user_id == user_id)
        .order_by(AuditLog.timestamp.desc())
    )
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar()
    result = await db.execute(query.offset((page - 1) * size).limit(size))
    items = result.scalars().all()
    return {"items": items, "total": total, "page": page, "size": size, "pages": -(-total // size)}


@router.get("/all", response_model=PaginatedResponse)
async def list_all_audit_logs(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    token_payload: dict = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Admin-only: full audit log."""
    query = select(AuditLog).order_by(AuditLog.timestamp.desc())
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar()
    result = await db.execute(query.offset((page - 1) * size).limit(size))
    items = result.scalars().all()
    return {"items": items, "total": total, "page": page, "size": size, "pages": -(-total // size)}
