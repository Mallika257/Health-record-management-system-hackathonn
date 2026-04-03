"""
/api/v1/consent — Consent request lifecycle.
"""

from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from app.core.database import get_db
from app.core.security import get_current_user_id, require_role
from app.models.models import ConsentRequest, ConsentStatus, Patient, Doctor, UserRole
from app.schemas.schemas import ConsentRequestCreate, ConsentAction, ConsentResponse, PaginatedResponse
from app.services.consent_service import ConsentService

router = APIRouter()


@router.post("/request", response_model=ConsentResponse, status_code=201)
async def create_consent_request(
    data: ConsentRequestCreate,
    token_payload: dict = Depends(require_role(UserRole.DOCTOR)),
    db: AsyncSession = Depends(get_db),
):
    """Doctor creates a consent request for patient data access."""
    doctor_user_id = token_payload["sub"]
    return await ConsentService.create_request(db, doctor_user_id, data)


@router.post("/{consent_id}/respond", response_model=ConsentResponse)
async def respond_to_consent(
    consent_id: UUID,
    action: ConsentAction,
    token_payload: dict = Depends(require_role(UserRole.PATIENT)),
    db: AsyncSession = Depends(get_db),
):
    """Patient approves or rejects a consent request."""
    patient_user_id = token_payload["sub"]
    return await ConsentService.respond_to_request(db, consent_id, patient_user_id, action)


@router.post("/{consent_id}/revoke", response_model=ConsentResponse)
async def revoke_consent(
    consent_id: UUID,
    token_payload: dict = Depends(require_role(UserRole.PATIENT)),
    db: AsyncSession = Depends(get_db),
):
    """Patient revokes a previously approved consent."""
    patient_user_id = token_payload["sub"]
    return await ConsentService.revoke_consent(db, consent_id, patient_user_id)


@router.get("/my", response_model=PaginatedResponse)
async def list_my_consents(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: Optional[ConsentStatus] = Query(None),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List consent requests relevant to the current user (patient or doctor)."""
    from app.models.models import User
    result = await db.execute(select(User).where(User.id == user_id))  # type: ignore
    user = result.scalar_one_or_none()

    if user and user.role == UserRole.PATIENT:
        patient_result = await db.execute(select(Patient).where(Patient.user_id == user_id))
        patient = patient_result.scalar_one_or_none()
        query = select(ConsentRequest).where(ConsentRequest.patient_id == patient.id)
    else:
        doctor_result = await db.execute(select(Doctor).where(Doctor.user_id == user_id))
        doctor = doctor_result.scalar_one_or_none()
        query = select(ConsentRequest).where(ConsentRequest.doctor_id == doctor.id)

    if status:
        query = query.where(ConsentRequest.status == status)

    query = query.order_by(ConsentRequest.created_at.desc())

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar()

    result = await db.execute(query.offset((page - 1) * size).limit(size))
    items = result.scalars().all()

    return {"items": items, "total": total, "page": page, "size": size, "pages": -(-total // size)}
