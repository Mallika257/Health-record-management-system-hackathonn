"""
/api/v1/insights — AI-generated health insights.
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.models import AIInsight, Patient, InsightSeverity
from app.schemas.schemas import AIInsightResponse, PaginatedResponse
from app.services.ai_service import AIInsightEngine
from typing import Optional

router = APIRouter()


@router.get("/my", response_model=PaginatedResponse)
async def list_my_insights(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    severity: Optional[InsightSeverity] = Query(None),
    unacknowledged_only: bool = Query(False),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Patient).where(Patient.user_id == user_id))
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")

    query = select(AIInsight).where(AIInsight.patient_id == patient.id)
    if severity:
        query = query.where(AIInsight.severity == severity)
    if unacknowledged_only:
        query = query.where(AIInsight.is_acknowledged == False)

    query = query.order_by(AIInsight.generated_at.desc())

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar()
    result = await db.execute(query.offset((page - 1) * size).limit(size))
    items = result.scalars().all()

    return {"items": items, "total": total, "page": page, "size": size, "pages": -(-total // size)}


@router.post("/run-analysis")
async def run_analysis(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Trigger AI analysis on current user's vitals."""
    result = await db.execute(select(Patient).where(Patient.user_id == user_id))
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")

    engine = AIInsightEngine(db)
    insights = await engine.run_analysis_for_patient(patient.id)
    return {"generated": len(insights), "message": f"{len(insights)} new insight(s) generated"}


@router.post("/{insight_id}/acknowledge")
async def acknowledge_insight(
    insight_id: UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Patient).where(Patient.user_id == user_id))
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    result = await db.execute(
        select(AIInsight).where(
            AIInsight.id == insight_id,
            AIInsight.patient_id == patient.id,
        )
    )
    insight = result.scalar_one_or_none()
    if not insight:
        raise HTTPException(status_code=404, detail="Insight not found")

    insight.is_acknowledged = True
    return {"message": "Insight acknowledged"}


@router.get("/health-score")
async def health_score(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Patient).where(Patient.user_id == user_id))
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    engine = AIInsightEngine(db)
    return await engine.get_health_score(patient.id)
