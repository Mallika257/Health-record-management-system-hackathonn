"""
/api/v1/reports — Upload, list, and retrieve health reports.
"""

from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from app.core.database import get_db
from app.core.security import get_current_user_id, get_current_user_role
from app.models.models import Report, Patient, Lab, User, UserRole, ReportType
from app.schemas.schemas import ReportResponse, ReportListResponse
from app.services.file_service import FileService
import json

router = APIRouter()


@router.post("/upload", response_model=ReportResponse, status_code=201)
async def upload_report(
    file: UploadFile = File(...),
    title: str = Form(...),
    report_type: ReportType = Form(...),
    report_date: str = Form(...),       # ISO date string
    description: Optional[str] = Form(None),
    tags: Optional[str] = Form("[]"),  # JSON array as string
    patient_id: Optional[str] = Form(None),  # required for lab uploads
    user_id: str = Depends(get_current_user_id),
    user_role: str = Depends(get_current_user_role),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a health report (PDF or image).
    - Patients upload for themselves.
    - Labs must provide patient_id.
    """
    from datetime import date as date_type

    # Resolve patient
    if user_role == UserRole.PATIENT:
        result = await db.execute(select(Patient).where(Patient.user_id == user_id))
        patient = result.scalar_one_or_none()
        if not patient:
            raise HTTPException(status_code=404, detail="Patient profile not found")
        resolved_patient_id = patient.id
        lab_id = None
    elif user_role in (UserRole.LAB, UserRole.DOCTOR):
        if not patient_id:
            raise HTTPException(status_code=400, detail="patient_id required for lab/doctor uploads")
        result = await db.execute(select(Patient).where(Patient.id == patient_id))
        patient = result.scalar_one_or_none()
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        resolved_patient_id = patient.id

        lab_id = None
        if user_role == UserRole.LAB:
            result = await db.execute(select(Lab).where(Lab.user_id == user_id))
            lab = result.scalar_one_or_none()
            if lab:
                lab_id = lab.id
    else:
        raise HTTPException(status_code=403, detail="Unauthorized role for uploads")

    # Save file
    file_url, file_name, size, mime = await FileService.upload_report(
        file, str(resolved_patient_id)
    )

    # Parse tags
    try:
        parsed_tags = json.loads(tags) if tags else []
    except Exception:
        parsed_tags = []

    report = Report(
        patient_id=resolved_patient_id,
        lab_id=lab_id,
        uploaded_by=user_id,
        title=title,
        report_type=report_type,
        description=description,
        file_url=file_url,
        file_name=file_name,
        file_size_bytes=size,
        mime_type=mime,
        report_date=date_type.fromisoformat(report_date),
        tags=parsed_tags,
    )
    db.add(report)
    await db.flush()
    return report


@router.get("/my", response_model=ReportListResponse)
async def list_my_reports(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    report_type: Optional[ReportType] = Query(None),
    search: Optional[str] = Query(None),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List reports for the authenticated patient."""
    result = await db.execute(select(Patient).where(Patient.user_id == user_id))
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")

    query = select(Report).where(Report.patient_id == patient.id)
    if report_type:
        query = query.where(Report.report_type == report_type)
    if search:
        query = query.where(Report.title.ilike(f"%{search}%"))

    query = query.order_by(Report.report_date.desc())

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar()

    result = await db.execute(query.offset((page - 1) * size).limit(size))
    reports = result.scalars().all()

    return {
        "items": reports,
        "total": total,
        "page": page,
        "size": size,
        "pages": -(-total // size),
    }


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: UUID,
    user_id: str = Depends(get_current_user_id),
    user_role: str = Depends(get_current_user_role),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # Patients can only view their own
    if user_role == UserRole.PATIENT:
        patient_result = await db.execute(select(Patient).where(Patient.user_id == user_id))
        patient = patient_result.scalar_one_or_none()
        if not patient or patient.id != report.patient_id:
            raise HTTPException(status_code=403, detail="Access denied")

    return report


@router.delete("/{report_id}", status_code=204)
async def delete_report(
    report_id: UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # Only owner or admin can delete
    patient_result = await db.execute(select(Patient).where(Patient.user_id == user_id))
    patient = patient_result.scalar_one_or_none()
    if not patient or patient.id != report.patient_id:
        raise HTTPException(status_code=403, detail="Access denied")

    FileService.delete_file(report.file_url)
    await db.delete(report)
