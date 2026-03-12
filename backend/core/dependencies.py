"""
FastAPI dependency injection: authentication + tenant scoping middleware.
All protected routes must declare these dependencies.
"""
from typing import Annotated
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.database import get_db
from core.security import decode_token
from models.user import User
from models.audit import AuditLog

security = HTTPBearer()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> User:
    """
    Validate JWT access token and return the authenticated user.
    Raises 401 if token is invalid, expired, or user not found.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise credentials_exception

    user_id = payload.get("sub")
    if not user_id:
        raise credentials_exception

    result = await db.execute(
        select(User).where(User.id == user_id, User.is_active == True)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise credentials_exception

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email address not verified. Please check your inbox."
        )

    return user


async def get_current_active_teacher(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Require teacher role or above."""
    if current_user.role not in ("teacher", "school_admin", "super_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    return current_user


async def get_current_school_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Require school_admin or super_admin role."""
    if current_user.role not in ("school_admin", "super_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="School admin privileges required"
        )
    return current_user


async def get_current_super_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Require super_admin role."""
    if current_user.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin privileges required"
        )
    return current_user


async def log_audit_event(
    db: AsyncSession,
    user: User,
    action: str,
    resource: str = None,
    resource_id: str = None,
    ip_address: str = None,
    metadata: dict = None,
):
    """Write an audit log entry. Call this from any sensitive operation."""
    log_entry = AuditLog(
        school_id=user.school_id,
        user_id=user.id,
        action=action,
        resource=resource,
        resource_id=str(resource_id) if resource_id else None,
        ip_address=ip_address,
        metadata=metadata or {},
    )
    db.add(log_entry)
    # Note: session is committed by the get_db dependency after the request completes
