"""
/api/v1/patients — Patient profile + health data endpoints.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.core.database import get_db
from app.core.security import get_current_user_id, require_role
from app.models.models import Patient, User, Vital, UserRole
from app.schemas.schemas import (
    PatientProfileCreate, PatientProfileUpdate, PatientResponse,
    PatientSummaryResponse, VitalCreate, VitalResponse, PaginatedResponse,
)
from app.services.ai_service import AIInsightEngine

router = APIRouter()


# ── Profile ───────────────────────────────────────────────────────────────────

@router.get("/me", response_model=PatientResponse)
async def get_my_profile(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Patient).where(Patient.user_id == user_id)
    )
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")
    return patient


@router.put("/me", response_model=PatientResponse)
async def update_my_profile(
    data: PatientProfileUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Patient).where(Patient.user_id == user_id)
    )
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(patient, field, value)

    return patient


@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient(
    patient_id: UUID,
    token_payload: dict = Depends(require_role(UserRole.DOCTOR, UserRole.ADMIN, UserRole.LAB)),
    db: AsyncSession = Depends(get_db),
):
    """Doctors/Labs can view patient profiles (consent checked at data level)."""
    result = await db.execute(select(Patient).where(Patient.id == patient_id))
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@router.get("/", response_model=PaginatedResponse)
async def list_patients(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    token_payload: dict = Depends(require_role(UserRole.DOCTOR, UserRole.ADMIN, UserRole.LAB)),
    db: AsyncSession = Depends(get_db),
):
    """List all patients (doctor/admin/lab only)."""
    from sqlalchemy import func, or_

    query = select(Patient).join(User, Patient.user_id == User.id)
    if search:
        query = query.where(
            or_(
                User.full_name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
            )
        )

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar()

    result = await db.execute(
        query.offset((page - 1) * size).limit(size)
    )
    patients = result.scalars().all()

    return {
        "items": patients,
        "total": total,
        "page": page,
        "size": size,
        "pages": -(-total // size),
    }


# ── Vitals ────────────────────────────────────────────────────────────────────

@router.post("/me/vitals", response_model=VitalResponse, status_code=201)
async def add_vital(
    data: VitalCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Patient).where(Patient.user_id == user_id))
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")

    # Compute BMI if both values present
    bmi = None
    if data.weight_kg and patient.height_cm:
        height_m = patient.height_cm / 100
        bmi = round(data.weight_kg / (height_m ** 2), 2)

    vital = Vital(
        patient_id=patient.id,
        bmi=bmi,
        **data.model_dump(),
    )
    db.add(vital)
    await db.flush()

    # Trigger async AI analysis (fire-and-forget pattern)
    engine = AIInsightEngine(db)
    await engine.run_analysis_for_patient(patient.id)

    return vital


@router.get("/me/vitals", response_model=PaginatedResponse)
async def list_vitals(
    page: int = Query(1, ge=1),
    size: int = Query(30, ge=1, le=200),
    metric: Optional[str] = Query(None),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import func

    result = await db.execute(select(Patient).where(Patient.user_id == user_id))
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")

    query = select(Vital).where(Vital.patient_id == patient.id).order_by(Vital.recorded_at.desc())

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar()

    result = await db.execute(query.offset((page - 1) * size).limit(size))
    vitals = result.scalars().all()

    return {"items": vitals, "total": total, "page": page, "size": size, "pages": -(-total // size)}


@router.get("/me/health-score")
async def get_health_score(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Patient).where(Patient.user_id == user_id))
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")

    engine = AIInsightEngine(db)
    return await engine.get_health_score(patient.id)
