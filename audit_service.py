"""
Audit logging service — record every sensitive action.
"""

from typing import Optional, Any, Dict
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import AuditLog, AuditAction


async def log_action(
    db: AsyncSession,
    user_id: Optional[UUID],
    action: AuditAction,
    resource_type: str,
    resource_id: Optional[str] = None,
    description: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> AuditLog:
    """
    Create an audit log entry.
    Designed to be called with db.flush() — not commit() — 
    so it's part of the same transaction.
    """
    log = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id else None,
        description=description,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata=metadata or {},
    )
    db.add(log)
    await db.flush()
    return log
