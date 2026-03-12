"""
Authentication router: signup, login, token refresh, email verification,
password reset, logout, and current user.
"""
from datetime import datetime, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Cookie
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel, EmailStr, field_validator
import re

from core.database import get_db
from core.config import settings
from core.security import (
    hash_password, verify_password, needs_rehash,
    create_access_token, create_refresh_token, decode_token, hash_token,
    encrypt_field, decrypt_field, hmac_hash_email,
    create_signed_token, verify_signed_token,
)
from core.dependencies import get_current_user, log_audit_event
from models.user import User
from models.school import School
from models.refresh_token import RefreshToken

router = APIRouter()

PASSWORD_PATTERN = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&^#])[A-Za-z\d@$!%*?&^#]{12,}$"
)


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    school_code: str  # Schools are pre-registered; teachers join via code

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if not PASSWORD_PATTERN.match(v):
            raise ValueError(
                "Password must be at least 12 characters and include uppercase, "
                "lowercase, number, and special character (@$!%*?&^#)"
            )
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class PasswordResetRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v):
        if not PASSWORD_PATTERN.match(v):
            raise ValueError("Password does not meet complexity requirements")
        return v


@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(request: SignupRequest, db: AsyncSession = Depends(get_db)):
    """Create a new teacher account. Sends verification email."""
    # Validate school code
    school_result = await db.execute(
        select(School).where(School.join_code == request.school_code, School.is_active == True)
    )
    school = school_result.scalar_one_or_none()
    if not school:
        raise HTTPException(status_code=400, detail="Invalid school code")

    # Check for duplicate email
    email_hash = hmac_hash_email(request.email)
    existing = await db.execute(select(User).where(User.email_hash == email_hash))
    if existing.scalar_one_or_none():
        # Return 201 to prevent email enumeration
        return {"message": "If this email is not registered, a verification link has been sent."}

    # Create user
    user = User(
        school_id=school.id,
        email=encrypt_field(request.email),
        email_hash=email_hash,
        password_hash=hash_password(request.password),
        full_name=encrypt_field(request.full_name),
        role="teacher",
        is_verified=False,
    )
    db.add(user)
    await db.flush()  # Get the user ID before commit

    # Create verification token
    token = create_signed_token(
        {"sub": str(user.id), "purpose": "email_verify"},
        settings.email_verify_expire_hours
    )

    # TODO: Send verification email
    # await send_verification_email(request.email, token)

    return {"message": "Account created. Please check your email to verify your address."}


@router.post("/login")
async def login(
    request: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    req: Request = None,
):
    """Authenticate with email/password. Returns access JWT; sets refresh cookie."""
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password"
    )

    email_hash = hmac_hash_email(request.email)
    result = await db.execute(
        select(User).where(User.email_hash == email_hash, User.is_active == True)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise credentials_error

    # Check lockout
    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Account locked due to repeated failed attempts. Try again after {user.locked_until.isoformat()}"
        )

    # Verify password
    if not verify_password(request.password, user.password_hash):
        # Increment failed attempts
        new_attempts = user.failed_attempts + 1
        locked_until = None
        if new_attempts >= 5:
            from datetime import timedelta
            locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)

        await db.execute(
            update(User)
            .where(User.id == user.id)
            .values(failed_attempts=new_attempts, locked_until=locked_until)
        )
        raise credentials_error

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please check your inbox."
        )

    # Reset failed attempts
    await db.execute(
        update(User).where(User.id == user.id).values(failed_attempts=0, locked_until=None)
    )

    # Rehash password if needed (Argon2id parameter upgrade)
    if needs_rehash(user.password_hash):
        await db.execute(
            update(User).where(User.id == user.id)
            .values(password_hash=hash_password(request.password))
        )

    # Generate tokens
    token_data = {"sub": str(user.id), "school_id": str(user.school_id), "role": user.role}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    # Store refresh token hash
    rt = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(refresh_token),
        expires_at=datetime.now(timezone.utc).replace(microsecond=0),  # TODO: proper expiry
    )
    db.add(rt)

    # Set refresh token as HttpOnly Secure cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="strict",
        max_age=settings.refresh_token_expire_days * 86400,
        path="/auth/refresh",
    )

    ip = req.client.host if req else None
    await log_audit_event(db, user, "LOGIN", ip_address=ip)

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/refresh")
async def refresh_token(
    response: Response,
    refresh_token: str = Cookie(None),
    db: AsyncSession = Depends(get_db),
):
    """Rotate refresh token and return new access token."""
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")

    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    token_hash = hash_token(refresh_token)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked == False,
        )
    )
    rt = result.scalar_one_or_none()
    if not rt:
        raise HTTPException(status_code=401, detail="Refresh token revoked or not found")

    # Revoke old token
    rt.revoked = True

    # Issue new tokens
    user_id = payload.get("sub")
    user_result = await db.execute(select(User).where(User.id == user_id, User.is_active == True))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    token_data = {"sub": str(user.id), "school_id": str(user.school_id), "role": user.role}
    new_access = create_access_token(token_data)
    new_refresh = create_refresh_token(token_data)

    new_rt = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(new_refresh),
        expires_at=datetime.now(timezone.utc),
    )
    db.add(new_rt)

    response.set_cookie(
        key="refresh_token",
        value=new_refresh,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="strict",
        max_age=settings.refresh_token_expire_days * 86400,
        path="/auth/refresh",
    )

    return {"access_token": new_access, "token_type": "bearer"}


@router.post("/logout")
async def logout(
    response: Response,
    refresh_token: str = Cookie(None),
    db: AsyncSession = Depends(get_db),
):
    """Revoke refresh token and clear cookie."""
    if refresh_token:
        token_hash = hash_token(refresh_token)
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.token_hash == token_hash)
            .values(revoked=True)
        )
    response.delete_cookie("refresh_token", path="/auth/refresh")
    return {"message": "Logged out"}


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    """Return current authenticated user profile."""
    return {
        "id": str(current_user.id),
        "role": current_user.role,
        "school_id": str(current_user.school_id),
        "is_verified": current_user.is_verified,
    }
