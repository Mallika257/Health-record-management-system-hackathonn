"""
Authentication service — register, login, token refresh.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status

from app.models.models import User, Patient, Doctor, Lab, UserRole, AuditAction
from app.schemas.schemas import RegisterRequest, LoginRequest, TokenResponse
from app.core.security import (
    verify_password, get_password_hash,
    create_access_token, create_refresh_token, decode_token,
)
from app.core.config import settings
from app.services.audit_service import log_action


class AuthService:

    @staticmethod
    async def register(db: AsyncSession, data: RegisterRequest, ip: str = None) -> User:
        # Check duplicate email
        result = await db.execute(select(User).where(User.email == data.email))
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )

        user = User(
            email=data.email,
            hashed_password=get_password_hash(data.password),
            full_name=data.full_name,
            role=data.role,
            phone=data.phone,
        )
        db.add(user)
        await db.flush()  # get user.id without committing

        # Auto-create role-specific empty profile
        if data.role == UserRole.PATIENT:
            db.add(Patient(user_id=user.id))
        elif data.role == UserRole.DOCTOR:
            pass  # Doctor profile created separately via /doctors/profile
        elif data.role == UserRole.LAB:
            pass  # Lab profile created separately via /labs/profile

        await db.flush()
        await log_action(
            db, user.id, AuditAction.CREATE,
            "user", str(user.id), "User registered",
            ip_address=ip,
        )
        return user

    @staticmethod
    async def login(db: AsyncSession, data: LoginRequest, ip: str = None) -> TokenResponse:
        result = await db.execute(select(User).where(User.email == data.email))
        user: Optional[User] = result.scalar_one_or_none()

        if not user or not verify_password(data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is disabled",
            )

        # Update last login
        user.last_login = datetime.now(timezone.utc)
        await db.flush()

        access_token  = create_access_token(user.id, user.role.value)
        refresh_token = create_refresh_token(user.id)

        await log_action(
            db, user.id, AuditAction.LOGIN,
            "user", str(user.id), f"Login from {ip or 'unknown'}",
            ip_address=ip,
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            role=user.role,
            user_id=user.id,
        )

    @staticmethod
    async def refresh_token(db: AsyncSession, refresh_token: str) -> TokenResponse:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        user_id = payload.get("sub")
        result  = await db.execute(select(User).where(User.id == user_id))
        user: Optional[User] = result.scalar_one_or_none()

        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found or inactive")

        access_token  = create_access_token(user.id, user.role.value)
        new_refresh   = create_refresh_token(user.id)

        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            role=user.role,
            user_id=user.id,
        )

    @staticmethod
    async def get_me(db: AsyncSession, user_id: str) -> User:
        result = await db.execute(select(User).where(User.id == user_id))
        user   = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
