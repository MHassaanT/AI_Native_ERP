"""API Dependencies for Multi-Tenancy, Database Sessions, and JWT Authentication."""

import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.auth.security import decode_access_token
from erp.config import settings
from erp.db.models.user import User
from erp.db.session import async_session_factory

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yields a transactional database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


DbSessionDep = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: DbSessionDep,
) -> User:
    """Authenticates the incoming request via JWT bearer token."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(token)
        user_id_str: str = payload.get("sub")
        if not user_id_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Malformed token: missing user subject claim.",
            )
        user_id = uuid.UUID(user_id_str)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {e!s}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    stmt = select(User).where(User.user_id == user_id, User.is_active.is_(True))
    user = (await db.execute(stmt)).scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with this token no longer exists or is deactivated.",
        )

    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


async def get_current_tenant_id(
    db: DbSessionDep,
    token: Annotated[str | None, Depends(oauth2_scheme)] = None,
    x_tenant_id: Annotated[str | None, Header()] = None,
) -> uuid.UUID:
    """Enforces strict multi-tenancy isolation.

    If JWT is present, tenant ID is derived from the authenticated user token.
    If X-Tenant-ID is also passed, it must match the authenticated tenant.
    Unauthenticated requests with arbitrary X-Tenant-ID headers are strictly rejected.
    """
    if token:
        try:
            payload = decode_access_token(token)
            t_id_str = payload.get("tenant_id")
            if t_id_str:
                token_tenant_id = uuid.UUID(t_id_str)
                if x_tenant_id:
                    try:
                        header_tenant_id = uuid.UUID(x_tenant_id)
                        if token_tenant_id != header_tenant_id:
                            raise HTTPException(
                                status_code=status.HTTP_403_FORBIDDEN,
                                detail="Tenant mismatch: authenticated token does not match X-Tenant-ID header.",
                            )
                    except ValueError as err:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Invalid tenant UUID: {x_tenant_id}",
                        ) from err
                return token_tenant_id
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Could not validate credentials: {e!s}",
            )

    if x_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: raw X-Tenant-ID headers cannot be used without valid authorization token.",
        )

    # In development/test with no explicit headers, fallback to default tenant for internal tests
    if settings.DEBUG and settings.ENVIRONMENT != "production":
        return settings.DEFAULT_TENANT_ID

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Tenant context required. Please log in or provide authentication.",
    )



TenantIdDep = Annotated[uuid.UUID, Depends(get_current_tenant_id)]


def require_roles(*roles: str):
    """Dependency factory enforcing Role-Based Access Control (RBAC)."""
    def role_checker(user: CurrentUserDep) -> User:
        if user.role == "TENANT_ADMIN" or user.role in roles:
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: User role '{user.role}' lacks required permissions ({list(roles)}).",
        )
    return Depends(role_checker)

