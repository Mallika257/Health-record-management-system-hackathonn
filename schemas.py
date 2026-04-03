"""
Pydantic v2 schemas — request bodies, response models, and internal types.
"""

from __future__ import annotations
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.models.models import (
    UserRole, Gender, BloodGroup, ReportType,
    ConsentStatus, AppointmentStatus, NotificationType,
    InsightSeverity, AuditAction,
)


# ── Shared ────────────────────────────────────────────────────────────────────

class TimestampMixin(BaseModel):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Auth ──────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email:     EmailStr
    password:  str = Field(min_length=8, max_length=100)
    full_name: str = Field(min_length=2, max_length=255)
    role:      UserRole
    phone:     Optional[str] = None

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class LoginRequest(BaseModel):
    email:    EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token:  str
    refresh_token: str
    token_type:    str = "bearer"
    expires_in:    int
    role:          UserRole
    user_id:       UUID


class RefreshRequest(BaseModel):
    refresh_token: str


# ── User ──────────────────────────────────────────────────────────────────────

class UserBase(BaseModel):
    email:     EmailStr
    full_name: str
    role:      UserRole
    phone:     Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool = True


class UserResponse(UserBase, TimestampMixin):
    is_verified: bool
    last_login:  Optional[datetime] = None


class UserUpdateRequest(BaseModel):
    full_name:  Optional[str] = Field(None, min_length=2, max_length=255)
    phone:      Optional[str] = None
    avatar_url: Optional[str] = None


# ── Patient ───────────────────────────────────────────────────────────────────

class PatientProfileCreate(BaseModel):
    date_of_birth:           Optional[date] = None
    gender:                  Optional[Gender] = None
    blood_group:             Optional[BloodGroup] = None
    height_cm:               Optional[float] = Field(None, gt=0, lt=300)
    weight_kg:               Optional[float] = Field(None, gt=0, lt=700)
    allergies:               Optional[List[str]] = []
    chronic_conditions:      Optional[List[str]] = []
    emergency_contact_name:  Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    address:                 Optional[str] = None
    city:                    Optional[str] = None
    state:                   Optional[str] = None
    pincode:                 Optional[str] = None
    abha_id:                 Optional[str] = None


class PatientProfileUpdate(PatientProfileCreate):
    pass


class PatientResponse(TimestampMixin):
    user_id:                 UUID
    date_of_birth:           Optional[date]    = None
    gender:                  Optional[Gender]  = None
    blood_group:             Optional[BloodGroup] = None
    height_cm:               Optional[float]   = None
    weight_kg:               Optional[float]   = None
    allergies:               List[str]         = []
    chronic_conditions:      List[str]         = []
    emergency_contact_name:  Optional[str]     = None
    emergency_contact_phone: Optional[str]     = None
    address:                 Optional[str]     = None
    city:                    Optional[str]     = None
    state:                   Optional[str]     = None
    pincode:                 Optional[str]     = None
    abha_id:                 Optional[str]     = None
    user:                    Optional[UserResponse] = None


class PatientSummaryResponse(BaseModel):
    """Lightweight patient card for doctor/lab views."""
    id:         UUID
    user_id:    UUID
    full_name:  str
    email:      str
    blood_group: Optional[BloodGroup] = None
    chronic_conditions: List[str] = []
    age:        Optional[int] = None

    model_config = {"from_attributes": True}


# ── Doctor ────────────────────────────────────────────────────────────────────

class DoctorProfileCreate(BaseModel):
    registration_no: str = Field(min_length=3, max_length=100)
    specialization:  Optional[str] = None
    hospital:        Optional[str] = None
    department:      Optional[str] = None
    experience_years: Optional[int] = Field(None, ge=0, le=70)
    qualifications:  Optional[List[str]] = []
    consultation_fee: Optional[float] = Field(None, ge=0)


class DoctorProfileUpdate(DoctorProfileCreate):
    registration_no: Optional[str] = None


class DoctorResponse(TimestampMixin):
    user_id:          UUID
    registration_no:  str
    specialization:   Optional[str]       = None
    hospital:         Optional[str]       = None
    department:       Optional[str]       = None
    experience_years: Optional[int]       = None
    qualifications:   List[str]           = []
    consultation_fee: Optional[float]     = None
    is_verified:      bool                = False
    user:             Optional[UserResponse] = None


# ── Lab ───────────────────────────────────────────────────────────────────────

class LabProfileCreate(BaseModel):
    lab_name:      str = Field(min_length=2, max_length=255)
    license_no:    Optional[str] = None
    accreditation: Optional[str] = None
    address:       Optional[str] = None
    city:          Optional[str] = None
    state:         Optional[str] = None


class LabResponse(TimestampMixin):
    user_id:       UUID
    lab_name:      str
    license_no:    Optional[str]  = None
    accreditation: Optional[str]  = None
    address:       Optional[str]  = None
    city:          Optional[str]  = None
    state:         Optional[str]  = None
    is_verified:   bool           = False
    user:          Optional[UserResponse] = None


# ── Report ────────────────────────────────────────────────────────────────────

class ReportCreate(BaseModel):
    title:       str = Field(min_length=2, max_length=500)
    report_type: ReportType
    description: Optional[str] = None
    report_date: date
    tags:        Optional[List[str]] = []
    patient_id:  Optional[UUID] = None   # required when lab uploads for a patient


class ReportResponse(TimestampMixin):
    patient_id:      UUID
    lab_id:          Optional[UUID]       = None
    uploaded_by:     UUID
    title:           str
    report_type:     ReportType
    description:     Optional[str]        = None
    file_url:        str
    file_name:       str
    file_size_bytes: Optional[int]        = None
    mime_type:       Optional[str]        = None
    report_date:     date
    tags:            List[str]            = []
    extracted_data:  Dict[str, Any]       = {}
    is_abnormal:     bool                 = False


class ReportListResponse(BaseModel):
    items:   List[ReportResponse]
    total:   int
    page:    int
    size:    int
    pages:   int


# ── Vital ─────────────────────────────────────────────────────────────────────

class VitalCreate(BaseModel):
    recorded_at:       datetime
    heart_rate:        Optional[float] = Field(None, gt=0, lt=300)
    systolic_bp:       Optional[float] = Field(None, gt=0, lt=400)
    diastolic_bp:      Optional[float] = Field(None, gt=0, lt=300)
    temperature:       Optional[float] = Field(None, gt=30, lt=50)
    oxygen_saturation: Optional[float] = Field(None, ge=0, le=100)
    respiratory_rate:  Optional[float] = Field(None, gt=0, lt=100)
    blood_glucose:     Optional[float] = Field(None, gt=0)
    weight_kg:         Optional[float] = Field(None, gt=0, lt=700)
    notes:             Optional[str]   = None
    source:            Optional[str]   = "manual"


class VitalResponse(TimestampMixin):
    patient_id:        UUID
    recorded_at:       datetime
    heart_rate:        Optional[float] = None
    systolic_bp:       Optional[float] = None
    diastolic_bp:      Optional[float] = None
    temperature:       Optional[float] = None
    oxygen_saturation: Optional[float] = None
    respiratory_rate:  Optional[float] = None
    blood_glucose:     Optional[float] = None
    weight_kg:         Optional[float] = None
    bmi:               Optional[float] = None
    notes:             Optional[str]   = None
    source:            str             = "manual"


# ── Prescription ──────────────────────────────────────────────────────────────

class MedicationItem(BaseModel):
    name:         str
    dosage:       str
    frequency:    str
    duration:     str
    instructions: Optional[str] = None


class PrescriptionCreate(BaseModel):
    patient_id:        UUID
    diagnosis:         str = Field(min_length=2, max_length=500)
    medications:       List[MedicationItem]
    instructions:      Optional[str] = None
    follow_up_date:    Optional[date] = None
    prescription_date: date


class PrescriptionResponse(TimestampMixin):
    patient_id:        UUID
    doctor_id:         Optional[UUID]         = None
    diagnosis:         str
    medications:       List[Dict[str, Any]]
    instructions:      Optional[str]          = None
    follow_up_date:    Optional[date]         = None
    is_active:         bool
    prescription_date: date


# ── Appointment ───────────────────────────────────────────────────────────────

class AppointmentCreate(BaseModel):
    patient_id:     UUID
    doctor_id:      UUID
    scheduled_at:   datetime
    duration_mins:  Optional[int]  = 30
    reason:         Optional[str]  = None
    is_telemedicine: Optional[bool] = False


class AppointmentUpdate(BaseModel):
    scheduled_at:  Optional[datetime]           = None
    status:        Optional[AppointmentStatus]  = None
    notes:         Optional[str]                = None
    meeting_link:  Optional[str]                = None


class AppointmentResponse(TimestampMixin):
    patient_id:     UUID
    doctor_id:      UUID
    scheduled_at:   datetime
    duration_mins:  int
    status:         AppointmentStatus
    reason:         Optional[str]  = None
    notes:          Optional[str]  = None
    meeting_link:   Optional[str]  = None
    is_telemedicine: bool


# ── Consent ───────────────────────────────────────────────────────────────────

class ConsentRequestCreate(BaseModel):
    patient_id:  UUID
    purpose:     str = Field(min_length=10, max_length=1000)
    data_types:  List[str] = Field(min_length=1)
    expires_at:  datetime
    access_from: Optional[datetime] = None
    access_to:   Optional[datetime] = None


class ConsentAction(BaseModel):
    action:           str   # "approve" | "reject"
    rejection_reason: Optional[str] = None


class ConsentResponse(TimestampMixin):
    patient_id:       UUID
    doctor_id:        UUID
    purpose:          str
    data_types:       List[str]
    status:           ConsentStatus
    requested_at:     datetime
    responded_at:     Optional[datetime] = None
    expires_at:       datetime
    access_from:      Optional[datetime] = None
    access_to:        Optional[datetime] = None
    rejection_reason: Optional[str]      = None
    token:            Optional[str]      = None


# ── Notification ──────────────────────────────────────────────────────────────

class NotificationCreate(BaseModel):
    user_id:  UUID
    type:     NotificationType
    title:    str
    message:  str
    metadata: Optional[Dict[str, Any]] = {}


class NotificationResponse(TimestampMixin):
    user_id:  UUID
    type:     NotificationType
    title:    str
    message:  str
    is_read:  bool
    metadata: Dict[str, Any] = {}
    read_at:  Optional[datetime] = None


# ── AI Insight ────────────────────────────────────────────────────────────────

class AIInsightResponse(TimestampMixin):
    patient_id:      UUID
    title:           str
    description:     str
    severity:        InsightSeverity
    category:        Optional[str]     = None
    metric:          Optional[str]     = None
    data_points:     List[Any]         = []
    recommendation:  Optional[str]     = None
    is_acknowledged: bool              = False
    generated_at:    datetime


# ── Audit Log ─────────────────────────────────────────────────────────────────

class AuditLogResponse(TimestampMixin):
    user_id:       Optional[UUID]  = None
    action:        AuditAction
    resource_type: str
    resource_id:   Optional[str]   = None
    description:   Optional[str]   = None
    ip_address:    Optional[str]   = None
    metadata:      Dict[str, Any]  = {}
    timestamp:     datetime


# ── Paginated Wrapper ─────────────────────────────────────────────────────────

class PaginatedResponse(BaseModel):
    items:  List[Any]
    total:  int
    page:   int
    size:   int
    pages:  int
