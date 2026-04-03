"""
Complete PHR database schema.
All models inherit from Base (UUID PK + timestamps).
"""

import enum
import uuid
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, Float, Date, DateTime,
    ForeignKey, Enum, JSON, func,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship

from app.core.database import Base


# ── Enums ─────────────────────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    PATIENT = "patient"
    DOCTOR  = "doctor"
    LAB     = "lab"
    ADMIN   = "admin"


class Gender(str, enum.Enum):
    MALE        = "male"
    FEMALE      = "female"
    OTHER       = "other"
    PREFER_NOT  = "prefer_not_to_say"


class BloodGroup(str, enum.Enum):
    A_POS  = "A+"
    A_NEG  = "A-"
    B_POS  = "B+"
    B_NEG  = "B-"
    AB_POS = "AB+"
    AB_NEG = "AB-"
    O_POS  = "O+"
    O_NEG  = "O-"


class ReportType(str, enum.Enum):
    LAB_RESULT      = "lab_result"
    RADIOLOGY       = "radiology"
    PRESCRIPTION    = "prescription"
    DISCHARGE       = "discharge_summary"
    VACCINATION     = "vaccination"
    PATHOLOGY       = "pathology"
    ECG             = "ecg"
    OTHER           = "other"


class ConsentStatus(str, enum.Enum):
    PENDING  = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVOKED  = "revoked"
    EXPIRED  = "expired"


class AppointmentStatus(str, enum.Enum):
    SCHEDULED  = "scheduled"
    CONFIRMED  = "confirmed"
    COMPLETED  = "completed"
    CANCELLED  = "cancelled"
    NO_SHOW    = "no_show"


class NotificationType(str, enum.Enum):
    CONSENT_REQUEST   = "consent_request"
    CONSENT_APPROVED  = "consent_approved"
    CONSENT_REJECTED  = "consent_rejected"
    NEW_REPORT        = "new_report"
    NEW_PRESCRIPTION  = "new_prescription"
    APPOINTMENT_REMINDER = "appointment_reminder"
    HEALTH_ALERT      = "health_alert"
    AI_INSIGHT        = "ai_insight"
    SYSTEM            = "system"


class InsightSeverity(str, enum.Enum):
    INFO     = "info"
    WARNING  = "warning"
    CRITICAL = "critical"


class AuditAction(str, enum.Enum):
    CREATE  = "create"
    READ    = "read"
    UPDATE  = "update"
    DELETE  = "delete"
    LOGIN   = "login"
    LOGOUT  = "logout"
    SHARE   = "share"
    REVOKE  = "revoke"
    EXPORT  = "export"


# ── User ──────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    email           = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name       = Column(String(255), nullable=False)
    role            = Column(Enum(UserRole), nullable=False, index=True)
    phone           = Column(String(20))
    avatar_url      = Column(String(500))
    is_active       = Column(Boolean, default=True, nullable=False)
    is_verified     = Column(Boolean, default=False, nullable=False)
    last_login      = Column(DateTime(timezone=True))

    # Relationships
    patient_profile     = relationship("Patient",      back_populates="user", uselist=False, cascade="all, delete-orphan")
    doctor_profile      = relationship("Doctor",       back_populates="user", uselist=False, cascade="all, delete-orphan")
    lab_profile         = relationship("Lab",          back_populates="user", uselist=False, cascade="all, delete-orphan")
    notifications       = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    audit_logs          = relationship("AuditLog",     back_populates="user", cascade="all, delete-orphan")


# ── Patient ───────────────────────────────────────────────────────────────────

class Patient(Base):
    __tablename__ = "patients"

    user_id     = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    date_of_birth = Column(Date)
    gender      = Column(Enum(Gender))
    blood_group = Column(Enum(BloodGroup))
    height_cm   = Column(Float)
    weight_kg   = Column(Float)
    allergies   = Column(ARRAY(String), default=[])
    chronic_conditions = Column(ARRAY(String), default=[])
    emergency_contact_name  = Column(String(255))
    emergency_contact_phone = Column(String(20))
    address     = Column(Text)
    city        = Column(String(100))
    state       = Column(String(100))
    pincode     = Column(String(10))
    abha_id     = Column(String(50), unique=True, index=True)   # ABDM health ID

    # Relationships
    user            = relationship("User",          back_populates="patient_profile")
    reports         = relationship("Report",        back_populates="patient", cascade="all, delete-orphan")
    prescriptions   = relationship("Prescription",  back_populates="patient", cascade="all, delete-orphan")
    appointments    = relationship("Appointment",   back_populates="patient", cascade="all, delete-orphan")
    consent_requests = relationship("ConsentRequest", back_populates="patient", cascade="all, delete-orphan")
    vitals          = relationship("Vital",         back_populates="patient", cascade="all, delete-orphan")
    ai_insights     = relationship("AIInsight",     back_populates="patient", cascade="all, delete-orphan")


# ── Doctor ────────────────────────────────────────────────────────────────────

class Doctor(Base):
    __tablename__ = "doctors"

    user_id         = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    registration_no = Column(String(100), unique=True, index=True)
    specialization  = Column(String(255))
    hospital        = Column(String(255))
    department      = Column(String(255))
    experience_years = Column(Integer, default=0)
    qualifications  = Column(ARRAY(String), default=[])
    consultation_fee = Column(Float, default=0.0)
    is_verified     = Column(Boolean, default=False)

    # Relationships
    user            = relationship("User",          back_populates="doctor_profile")
    prescriptions   = relationship("Prescription",  back_populates="doctor")
    appointments    = relationship("Appointment",   back_populates="doctor")
    consent_requests = relationship("ConsentRequest", back_populates="doctor")


# ── Lab ───────────────────────────────────────────────────────────────────────

class Lab(Base):
    __tablename__ = "labs"

    user_id         = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    lab_name        = Column(String(255), nullable=False)
    license_no      = Column(String(100), unique=True)
    accreditation   = Column(String(100))
    address         = Column(Text)
    city            = Column(String(100))
    state           = Column(String(100))
    is_verified     = Column(Boolean, default=False)

    # Relationships
    user    = relationship("User",   back_populates="lab_profile")
    reports = relationship("Report", back_populates="lab")


# ── Report ────────────────────────────────────────────────────────────────────

class Report(Base):
    __tablename__ = "reports"

    patient_id      = Column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    lab_id          = Column(UUID(as_uuid=True), ForeignKey("labs.id",     ondelete="SET NULL"), nullable=True)
    uploaded_by     = Column(UUID(as_uuid=True), ForeignKey("users.id"),   nullable=False)

    title           = Column(String(500), nullable=False)
    report_type     = Column(Enum(ReportType), nullable=False, index=True)
    description     = Column(Text)
    file_url        = Column(String(1000), nullable=False)
    file_name       = Column(String(500), nullable=False)
    file_size_bytes = Column(Integer)
    mime_type       = Column(String(100))
    report_date     = Column(Date, nullable=False, index=True)
    tags            = Column(ARRAY(String), default=[])
    extracted_data  = Column(JSON, default={})  # AI-extracted key-value pairs
    is_abnormal     = Column(Boolean, default=False)

    # Relationships
    patient = relationship("Patient", back_populates="reports")
    lab     = relationship("Lab",     back_populates="reports")


# ── Vital Signs ───────────────────────────────────────────────────────────────

class Vital(Base):
    __tablename__ = "vitals"

    patient_id        = Column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    recorded_by       = Column(UUID(as_uuid=True), ForeignKey("users.id"),   nullable=True)
    recorded_at       = Column(DateTime(timezone=True), nullable=False, index=True)

    # Core vitals
    heart_rate        = Column(Float)        # bpm
    systolic_bp       = Column(Float)        # mmHg
    diastolic_bp      = Column(Float)        # mmHg
    temperature       = Column(Float)        # °C
    oxygen_saturation = Column(Float)        # %
    respiratory_rate  = Column(Float)        # breaths/min
    blood_glucose     = Column(Float)        # mg/dL
    weight_kg         = Column(Float)
    bmi               = Column(Float)
    notes             = Column(Text)
    source            = Column(String(100), default="manual")  # manual | device | wearable

    # Relationship
    patient = relationship("Patient", back_populates="vitals")


# ── Prescription ──────────────────────────────────────────────────────────────

class Prescription(Base):
    __tablename__ = "prescriptions"

    patient_id    = Column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    doctor_id     = Column(UUID(as_uuid=True), ForeignKey("doctors.id",  ondelete="SET NULL"), nullable=True)

    diagnosis     = Column(String(500), nullable=False)
    medications   = Column(JSON, nullable=False, default=[])
    # JSON structure: [{ name, dosage, frequency, duration, instructions }]
    instructions  = Column(Text)
    follow_up_date = Column(Date)
    is_active     = Column(Boolean, default=True)
    prescription_date = Column(Date, nullable=False)

    # Relationships
    patient = relationship("Patient", back_populates="prescriptions")
    doctor  = relationship("Doctor",  back_populates="prescriptions")


# ── Appointment ───────────────────────────────────────────────────────────────

class Appointment(Base):
    __tablename__ = "appointments"

    patient_id    = Column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    doctor_id     = Column(UUID(as_uuid=True), ForeignKey("doctors.id",  ondelete="CASCADE"), nullable=False, index=True)

    scheduled_at  = Column(DateTime(timezone=True), nullable=False, index=True)
    duration_mins = Column(Integer, default=30)
    status        = Column(Enum(AppointmentStatus), default=AppointmentStatus.SCHEDULED, index=True)
    reason        = Column(Text)
    notes         = Column(Text)
    meeting_link  = Column(String(500))         # for telemedicine
    is_telemedicine = Column(Boolean, default=False)

    # Relationships
    patient = relationship("Patient", back_populates="appointments")
    doctor  = relationship("Doctor",  back_populates="appointments")


# ── Consent Request (ABDM-style) ──────────────────────────────────────────────

class ConsentRequest(Base):
    __tablename__ = "consent_requests"

    patient_id    = Column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    doctor_id     = Column(UUID(as_uuid=True), ForeignKey("doctors.id",  ondelete="CASCADE"), nullable=False, index=True)

    purpose       = Column(Text, nullable=False)
    data_types    = Column(ARRAY(String), nullable=False)  # ["reports", "vitals", "prescriptions"]
    status        = Column(Enum(ConsentStatus), default=ConsentStatus.PENDING, index=True)
    requested_at  = Column(DateTime(timezone=True), server_default=func.now())
    responded_at  = Column(DateTime(timezone=True))
    expires_at    = Column(DateTime(timezone=True), nullable=False)
    access_from   = Column(DateTime(timezone=True))        # date range for data access
    access_to     = Column(DateTime(timezone=True))
    rejection_reason = Column(Text)
    token         = Column(String(255), unique=True, index=True)   # consent artifact token

    # Relationships
    patient = relationship("Patient", back_populates="consent_requests")
    doctor  = relationship("Doctor",  back_populates="consent_requests")


# ── Notification ──────────────────────────────────────────────────────────────

class Notification(Base):
    __tablename__ = "notifications"

    user_id       = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type          = Column(Enum(NotificationType), nullable=False, index=True)
    title         = Column(String(255), nullable=False)
    message       = Column(Text, nullable=False)
    is_read       = Column(Boolean, default=False, index=True)
    metadata      = Column(JSON, default={})   # flexible payload (e.g., related_id, link)
    read_at       = Column(DateTime(timezone=True))

    # Relationship
    user = relationship("User", back_populates="notifications")


# ── AI Insight ────────────────────────────────────────────────────────────────

class AIInsight(Base):
    __tablename__ = "ai_insights"

    patient_id    = Column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    title         = Column(String(500), nullable=False)
    description   = Column(Text, nullable=False)
    severity      = Column(Enum(InsightSeverity), nullable=False, index=True)
    category      = Column(String(100))   # e.g., "cardiovascular", "metabolic"
    metric        = Column(String(100))   # e.g., "heart_rate", "blood_glucose"
    data_points   = Column(JSON, default=[])
    recommendation = Column(Text)
    is_acknowledged = Column(Boolean, default=False)
    generated_at  = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    patient = relationship("Patient", back_populates="ai_insights")


# ── Audit Log ─────────────────────────────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_logs"

    user_id       = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action        = Column(Enum(AuditAction), nullable=False, index=True)
    resource_type = Column(String(100), nullable=False, index=True)
    resource_id   = Column(String(255))
    description   = Column(Text)
    ip_address    = Column(String(50))
    user_agent    = Column(String(500))
    metadata      = Column(JSON, default={})
    timestamp     = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationship
    user = relationship("User", back_populates="audit_logs")
