"""
/api/v1/doctors — Doctor profile management.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user_id, require_role
from app.models.models import Doctor, UserRole
from app.schemas.schemas import DoctorProfileCreate, DoctorProfileUpdate, DoctorResponse

router = APIRouter()


@router.post("/profile", response_model=DoctorResponse, status_code=201)
async def create_doctor_profile(
    data: DoctorProfileCreate,
    token_payload: dict = Depends(require_role(UserRole.DOCTOR)),
    db: AsyncSession = Depends(get_db),
):
    user_id = token_payload["sub"]
    result = await db.execute(select(Doctor).where(Doctor.user_id == user_id))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Doctor profile already exists")

    doctor = Doctor(user_id=user_id, **data.model_dump())
    db.add(doctor)
    await db.flush()
    return doctor


@router.get("/me", response_model=DoctorResponse)
async def get_my_profile(
    token_payload: dict = Depends(require_role(UserRole.DOCTOR)),
    db: AsyncSession = Depends(get_db),
):
    user_id = token_payload["sub"]
    result = await db.execute(select(Doctor).where(Doctor.user_id == user_id))
    doctor = result.scalar_one_or_none()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
    return doctor


@router.put("/me", response_model=DoctorResponse)
async def update_my_profile(
    data: DoctorProfileUpdate,
    token_payload: dict = Depends(require_role(UserRole.DOCTOR)),
    db: AsyncSession = Depends(get_db),
):
    user_id = token_payload["sub"]
    result = await db.execute(select(Doctor).where(Doctor.user_id == user_id))
    doctor = result.scalar_one_or_none()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(doctor, field, value)
    return doctor
