"""
/api/v1/prescriptions — Prescription management.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.security import get_current_user_id, get_current_user_role, require_role
from app.models.models import Prescription, Patient, Doctor, UserRole, Notification, NotificationType
from app.schemas.schemas import PrescriptionCreate, PrescriptionResponse, PaginatedResponse

router = APIRouter()


@router.post("/", response_model=PrescriptionResponse, status_code=201)
async def create_prescription(
    data: PrescriptionCreate,
    token_payload: dict = Depends(require_role(UserRole.DOCTOR)),
    db: AsyncSession = Depends(get_db),
):
    doctor_user_id = token_payload["sub"]
    result = await db.execute(select(Doctor).where(Doctor.user_id == doctor_user_id))
    doctor = result.scalar_one_or_none()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")

    # Verify patient
    result = await db.execute(select(Patient).where(Patient.id == data.patient_id))
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    rx = Prescription(
        patient_id=data.patient_id,
        doctor_id=doctor.id,
        diagnosis=data.diagnosis,
        medications=[m.model_dump() for m in data.medications],
        instructions=data.instructions,
        follow_up_date=data.follow_up_date,
        prescription_date=data.prescription_date,
    )
    db.add(rx)
    await db.flush()

    # Notify patient
    db.add(Notification(
        user_id=patient.user_id,
        type=NotificationType.NEW_PRESCRIPTION,
        title="New Prescription",
        message=f"A new prescription for '{data.diagnosis}' has been added.",
        metadata={"prescription_id": str(rx.id)},
    ))

    return rx


@router.get("/my", response_model=PaginatedResponse)
async def list_my_prescriptions(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    active_only: bool = Query(False),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Patient).where(Patient.user_id == user_id))
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")

    query = select(Prescription).where(Prescription.patient_id == patient.id)
    if active_only:
        query = query.where(Prescription.is_active == True)
    query = query.order_by(Prescription.prescription_date.desc())

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar()
    result = await db.execute(query.offset((page - 1) * size).limit(size))
    items = result.scalars().all()

    return {"items": items, "total": total, "page": page, "size": size, "pages": -(-total // size)}


@router.get("/{rx_id}", response_model=PrescriptionResponse)
async def get_prescription(
    rx_id: UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Prescription).where(Prescription.id == rx_id))
    rx = result.scalar_one_or_none()
    if not rx:
        raise HTTPException(status_code=404, detail="Prescription not found")
    return rx
