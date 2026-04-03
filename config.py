"""
Application configuration — loaded from environment variables.
"""

from pydantic_settings import BaseSettings
from typing import List
import secrets


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "Unified PHR System"
    APP_ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = secrets.token_urlsafe(32)

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://phr_user:phr_password@localhost:5432/phr_db"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # ── JWT ──────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = secrets.token_urlsafe(64)
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── CORS ─────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "https://phr-system.vercel.app",
    ]

    # ── File Storage ─────────────────────────────────────────────────────────
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_REPORT_TYPES: List[str] = ["application/pdf", "image/png", "image/jpeg", "image/jpg"]

    # ── Redis (for real-time notifications) ──────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379"

    # ── Email ────────────────────────────────────────────────────────────────
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""

    # ── AI / ML ──────────────────────────────────────────────────────────────
    AI_ANOMALY_THRESHOLD: float = 2.0          # std deviations
    AI_TREND_WINDOW_DAYS: int = 90
    AI_MIN_DATA_POINTS: int = 5

    # ── Consent ──────────────────────────────────────────────────────────────
    DEFAULT_CONSENT_DURATION_DAYS: int = 30
    MAX_CONSENT_DURATION_DAYS: int = 365

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
