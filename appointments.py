"""
/api/v1/appointments — Appointment scheduling and management.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_

from app.core.database import get_db
from app.core.security import get_current_user_id, get_current_user_role, require_role
from app.models.models import (
    Appointment, Patient, Doctor, UserRole,
    Notification, NotificationType, AppointmentStatus,
)
from app.schemas.schemas import (
    AppointmentCreate, AppointmentUpdate, AppointmentResponse, PaginatedResponse,
)

router = APIRouter()


@router.post("/", response_model=AppointmentResponse, status_code=201)
async def create_appointment(
    data: AppointmentCreate,
    user_id: str = Depends(get_current_user_id),
    user_role: str = Depends(get_current_user_role),
    db: AsyncSession = Depends(get_db),
):
    """Patient or Doctor can create an appointment."""
    # Verify patient
    result = await db.execute(select(Patient).where(Patient.id == data.patient_id))
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    # Verify doctor
    result = await db.execute(select(Doctor).where(Doctor.id == data.doctor_id))
    doctor = result.scalar_one_or_none()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    appt = Appointment(
        patient_id=data.patient_id,
        doctor_id=data.doctor_id,
        scheduled_at=data.scheduled_at,
        duration_mins=data.duration_mins,
        reason=data.reason,
        is_telemedicine=data.is_telemedicine,
    )
    db.add(appt)
    await db.flush()

    # Notify both parties
    db.add(Notification(
        user_id=patient.user_id,
        type=NotificationType.APPOINTMENT_REMINDER,
        title="Appointment Scheduled",
        message=f"Your appointment has been scheduled for {data.scheduled_at.strftime('%b %d, %Y at %H:%M')}.",
        metadata={"appointment_id": str(appt.id)},
    ))
    db.add(Notification(
        user_id=doctor.user_id,
        type=NotificationType.APPOINTMENT_REMINDER,
        title="New Appointment",
        message=f"A new appointment has been scheduled for {data.scheduled_at.strftime('%b %d, %Y at %H:%M')}.",
        metadata={"appointment_id": str(appt.id)},
    ))

    return appt


@router.get("/my", response_model=PaginatedResponse)
async def list_my_appointments(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: Optional[AppointmentStatus] = Query(None),
    upcoming: bool = Query(False),
    user_id: str = Depends(get_current_user_id),
    user_role: str = Depends(get_current_user_role),
    db: AsyncSession = Depends(get_db),
):
    from datetime import datetime, timezone

    if user_role == UserRole.PATIENT:
        result = await db.execute(select(Patient).where(Patient.user_id == user_id))
        patient = result.scalar_one_or_none()
        if not patient:
            raise HTTPException(status_code=404, detail="Patient profile not found")
        query = select(Appointment).where(Appointment.patient_id == patient.id)
    elif user_role == UserRole.DOCTOR:
        result = await db.execute(select(Doctor).where(Doctor.user_id == user_id))
        doctor = result.scalar_one_or_none()
        if not doctor:
            raise HTTPException(status_code=404, detail="Doctor profile not found")
        query = select(Appointment).where(Appointment.doctor_id == doctor.id)
    else:
        raise HTTPException(status_code=403, detail="Not authorized")

    if status:
        query = query.where(Appointment.status == status)
    if upcoming:
        query = query.where(
            and_(
                Appointment.scheduled_at >= datetime.now(timezone.utc),
                Appointment.status.in_([AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED]),
            )
        )

    query = query.order_by(Appointment.scheduled_at.desc())
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar()
    result = await db.execute(query.offset((page - 1) * size).limit(size))
    items = result.scalars().all()

    return {"items": items, "total": total, "page": page, "size": size, "pages": -(-total // size)}


@router.patch("/{appt_id}", response_model=AppointmentResponse)
async def update_appointment(
    appt_id: UUID,
    data: AppointmentUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Appointment).where(Appointment.id == appt_id))
    appt = result.scalar_one_or_none()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(appt, field, value)

    return appt


@router.delete("/{appt_id}", status_code=204)
async def cancel_appointment(
    appt_id: UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Appointment).where(Appointment.id == appt_id))
    appt = result.scalar_one_or_none()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    appt.status = AppointmentStatus.CANCELLED
