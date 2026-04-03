"""
Consent service — ABDM-style consent request lifecycle.
"""

import secrets
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update
from fastapi import HTTPException, status

from app.models.models import (
    ConsentRequest, ConsentStatus, Notification, NotificationType,
    AuditAction, Patient, Doctor, User,
)
from app.schemas.schemas import ConsentRequestCreate, ConsentAction
from app.services.audit_service import log_action
from app.core.config import settings


class ConsentService:

    @staticmethod
    async def create_request(
        db: AsyncSession,
        doctor_user_id: str,
        data: ConsentRequestCreate,
    ) -> ConsentRequest:
        # Verify doctor exists
        result = await db.execute(
            select(Doctor).where(Doctor.user_id == doctor_user_id)
        )
        doctor = result.scalar_one_or_none()
        if not doctor:
            raise HTTPException(status_code=404, detail="Doctor profile not found")

        # Verify patient exists
        result = await db.execute(
            select(Patient).where(Patient.id == data.patient_id)
        )
        patient = result.scalar_one_or_none()
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")

        # Validate expiry
        now = datetime.now(timezone.utc)
        if data.expires_at <= now:
            raise HTTPException(status_code=400, detail="expires_at must be in the future")

        max_expiry = now.replace(tzinfo=None) + \
            __import__('datetime').timedelta(days=settings.MAX_CONSENT_DURATION_DAYS)
        
        consent = ConsentRequest(
            patient_id=data.patient_id,
            doctor_id=doctor.id,
            purpose=data.purpose,
            data_types=data.data_types,
            expires_at=data.expires_at,
            access_from=data.access_from,
            access_to=data.access_to,
            token=secrets.token_urlsafe(32),
        )
        db.add(consent)
        await db.flush()

        # Notify patient
        patient_user_result = await db.execute(
            select(User).where(User.id == patient.user_id)
        )
        patient_user = patient_user_result.scalar_one_or_none()
        doctor_user_result = await db.execute(
            select(User).where(User.id == doctor.user_id)
        )
        doctor_user = doctor_user_result.scalar_one_or_none()

        db.add(Notification(
            user_id=patient.user_id,
            type=NotificationType.CONSENT_REQUEST,
            title="New Data Access Request",
            message=f"Dr. {doctor_user.full_name if doctor_user else 'Unknown'} has requested access to your health records.",
            metadata={
                "consent_id": str(consent.id),
                "doctor_id": str(doctor.id),
                "data_types": data.data_types,
            },
        ))

        await log_action(
            db, UUID(doctor_user_id), AuditAction.SHARE,
            "consent_request", str(consent.id),
            f"Doctor requested consent from patient {data.patient_id}",
        )

        return consent

    @staticmethod
    async def respond_to_request(
        db: AsyncSession,
        consent_id: UUID,
        patient_user_id: str,
        action: ConsentAction,
    ) -> ConsentRequest:
        result = await db.execute(
            select(ConsentRequest)
            .join(Patient, ConsentRequest.patient_id == Patient.id)
            .where(
                and_(
                    ConsentRequest.id == consent_id,
                    Patient.user_id == patient_user_id,
                )
            )
        )
        consent = result.scalar_one_or_none()
        if not consent:
            raise HTTPException(status_code=404, detail="Consent request not found")

        if consent.status != ConsentStatus.PENDING:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot respond to a consent in '{consent.status}' state",
            )

        now = datetime.now(timezone.utc)
        if consent.expires_at.replace(tzinfo=timezone.utc) < now:
            consent.status = ConsentStatus.EXPIRED
            raise HTTPException(status_code=400, detail="Consent request has expired")

        if action.action == "approve":
            consent.status = ConsentStatus.APPROVED
            notif_type  = NotificationType.CONSENT_APPROVED
            notif_title = "Consent Request Approved"
            notif_msg   = "Your data access request has been approved by the patient."
        elif action.action == "reject":
            consent.status = ConsentStatus.REJECTED
            consent.rejection_reason = action.rejection_reason
            notif_type  = NotificationType.CONSENT_REJECTED
            notif_title = "Consent Request Rejected"
            notif_msg   = "The patient has declined your data access request."
        else:
            raise HTTPException(status_code=400, detail="action must be 'approve' or 'reject'")

        consent.responded_at = now

        # Notify doctor
        doctor_result = await db.execute(
            select(Doctor).where(Doctor.id == consent.doctor_id)
        )
        doctor = doctor_result.scalar_one_or_none()
        if doctor:
            db.add(Notification(
                user_id=doctor.user_id,
                type=notif_type,
                title=notif_title,
                message=notif_msg,
                metadata={"consent_id": str(consent.id)},
            ))

        await log_action(
            db, UUID(patient_user_id), AuditAction.UPDATE,
            "consent_request", str(consent_id),
            f"Patient {action.action}d consent request",
        )

        return consent

    @staticmethod
    async def revoke_consent(
        db: AsyncSession,
        consent_id: UUID,
        patient_user_id: str,
    ) -> ConsentRequest:
        result = await db.execute(
            select(ConsentRequest)
            .join(Patient, ConsentRequest.patient_id == Patient.id)
            .where(
                and_(
                    ConsentRequest.id == consent_id,
                    Patient.user_id == patient_user_id,
                    ConsentRequest.status == ConsentStatus.APPROVED,
                )
            )
        )
        consent = result.scalar_one_or_none()
        if not consent:
            raise HTTPException(status_code=404, detail="Active consent not found")

        consent.status = ConsentStatus.REVOKED
        consent.responded_at = datetime.now(timezone.utc)

        await log_action(
            db, UUID(patient_user_id), AuditAction.REVOKE,
            "consent_request", str(consent_id), "Patient revoked consent",
        )

        return consent

    @staticmethod
    async def check_access(
        db: AsyncSession,
        doctor_user_id: str,
        patient_id: UUID,
        data_type: str,
    ) -> bool:
        """Verify doctor has valid consent to access a patient's data type."""
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(ConsentRequest)
            .join(Doctor, ConsentRequest.doctor_id == Doctor.id)
            .where(
                and_(
                    Doctor.user_id == doctor_user_id,
                    ConsentRequest.patient_id == patient_id,
                    ConsentRequest.status == ConsentStatus.APPROVED,
                    ConsentRequest.expires_at > now,
                )
            )
        )
        consents = result.scalars().all()
        return any(data_type in c.data_types for c in consents)
