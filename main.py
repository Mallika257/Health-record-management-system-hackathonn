"""
Unified Personal Health Record (PHR) System
Production-ready FastAPI Backend
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.core.database import engine, Base
from app.middleware.logging_middleware import LoggingMiddleware
from app.routes import (
    auth,
    users,
    patients,
    doctors,
    labs,
    reports,
    prescriptions,
    appointments,
    consent,
    notifications,
    ai_insights,
    audit,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("🚀 PHR System starting up...")
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ Database tables initialized")
    yield
    logger.info("⛔ PHR System shutting down...")
    await engine.dispose()


app = FastAPI(
    title="Unified PHR System API",
    description="""
    ## Unified Personal Health Record System
    
    A production-grade healthcare platform for aggregating, normalizing, 
    and securely sharing personal health records.
    
    ### Roles
    - **Patient**: Manage health data, consent requests, view insights
    - **Doctor**: Request patient data, add prescriptions, manage appointments
    - **Lab**: Upload reports, notify patients
    
    ### Security
    - JWT Bearer Token Authentication
    - Role-Based Access Control (RBAC)
    - End-to-end data validation
    - Audit logging for all sensitive operations
    """,
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(LoggingMiddleware)

# ── Routes ────────────────────────────────────────────────────────────────────

API_PREFIX = "/api/v1"

app.include_router(auth.router,          prefix=f"{API_PREFIX}/auth",          tags=["🔐 Authentication"])
app.include_router(users.router,         prefix=f"{API_PREFIX}/users",         tags=["👤 Users"])
app.include_router(patients.router,      prefix=f"{API_PREFIX}/patients",      tags=["🩺 Patients"])
app.include_router(doctors.router,       prefix=f"{API_PREFIX}/doctors",       tags=["👨‍⚕️ Doctors"])
app.include_router(labs.router,          prefix=f"{API_PREFIX}/labs",          tags=["🧪 Labs"])
app.include_router(reports.router,       prefix=f"{API_PREFIX}/reports",       tags=["📄 Reports"])
app.include_router(prescriptions.router, prefix=f"{API_PREFIX}/prescriptions", tags=["💊 Prescriptions"])
app.include_router(appointments.router,  prefix=f"{API_PREFIX}/appointments",  tags=["📅 Appointments"])
app.include_router(consent.router,       prefix=f"{API_PREFIX}/consent",       tags=["🔗 Consent"])
app.include_router(notifications.router, prefix=f"{API_PREFIX}/notifications", tags=["🔔 Notifications"])
app.include_router(ai_insights.router,   prefix=f"{API_PREFIX}/insights",      tags=["🧠 AI Insights"])
app.include_router(audit.router,         prefix=f"{API_PREFIX}/audit",         tags=["📋 Audit Logs"])


@app.get("/", tags=["Health"])
async def root():
    return {
        "service": "Unified PHR System",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/api/docs",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "service": "phr-backend"}
