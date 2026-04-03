"""
/api/v1/labs — Lab profile management.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import require_role
from app.models.models import Lab, UserRole
from app.schemas.schemas import LabProfileCreate, LabResponse

router = APIRouter()


@router.post("/profile", response_model=LabResponse, status_code=201)
async def create_lab_profile(
    data: LabProfileCreate,
    token_payload: dict = Depends(require_role(UserRole.LAB)),
    db: AsyncSession = Depends(get_db),
):
    user_id = token_payload["sub"]
    result = await db.execute(select(Lab).where(Lab.user_id == user_id))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Lab profile already exists")

    lab = Lab(user_id=user_id, **data.model_dump())
    db.add(lab)
    await db.flush()
    return lab


@router.get("/me", response_model=LabResponse)
async def get_my_profile(
    token_payload: dict = Depends(require_role(UserRole.LAB)),
    db: AsyncSession = Depends(get_db),
):
    user_id = token_payload["sub"]
    result = await db.execute(select(Lab).where(Lab.user_id == user_id))
    lab = result.scalar_one_or_none()
    if not lab:
        raise HTTPException(status_code=404, detail="Lab profile not found")
    return lab


@router.put("/me", response_model=LabResponse)
async def update_lab_profile(
    data: LabProfileCreate,
    token_payload: dict = Depends(require_role(UserRole.LAB)),
    db: AsyncSession = Depends(get_db),
):
    user_id = token_payload["sub"]
    result = await db.execute(select(Lab).where(Lab.user_id == user_id))
    lab = result.scalar_one_or_none()
    if not lab:
        raise HTTPException(status_code=404, detail="Lab profile not found")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(lab, field, value)
    return lab
