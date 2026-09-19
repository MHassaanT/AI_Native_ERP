"""Authentication and Multi-Tenant Onboarding API Endpoints."""

import logging
import re
import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from erp.api.deps import CurrentUserDep, DbSessionDep
from erp.auth.provisioning import provision_tenant_blueprint
from erp.auth.security import (
    create_access_token,
    get_password_hash,
    verify_password,
)
from erp.db.models.tenant import Tenant
from erp.db.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Multi-Tenant Authentication"])


class RegisterTenantRequest(BaseModel):
    company_name: str = Field(..., min_length=2, max_length=255)
    tenant_slug: str = Field(..., min_length=2, max_length=64)
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=2, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    password: str
    tenant_slug: str | None = None


class UserProfileResponse(BaseModel):
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    full_name: str
    role: str
    company_name: str
    tenant_slug: str


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfileResponse


@router.post("/register", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
async def register_tenant(req: RegisterTenantRequest, db: DbSessionDep) -> AuthTokenResponse:
    """Registers a new corporate tenant organization, provisions initial ledger & factory, and issues JWT."""
    clean_slug = re.sub(r"[^a-z0-9-]", "-", req.tenant_slug.lower()).strip("-")

    # Check for existing slug
    existing_tenant = (
        await db.execute(select(Tenant).where(Tenant.tenant_slug == clean_slug))
    ).scalar_one_or_none()
    if existing_tenant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tenant slug '{clean_slug}' is already taken. Please choose another organization identifier.",
        )

    # Check for existing email in this tenant
    existing_user = (
        await db.execute(select(User).where(User.email == req.email.lower()))
    ).scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A user with email '{req.email}' is already registered.",
        )

    # 1. Create Tenant
    tenant_id = uuid.uuid4()
    tenant = Tenant(
        tenant_id=tenant_id,
        tenant_slug=clean_slug,
        company_name=req.company_name,
        plan_tier="ENTERPRISE",
        is_active=True,
    )
    db.add(tenant)

    # 2. Create Initial Administrator User
    user_id = uuid.uuid4()
    user = User(
        user_id=user_id,
        tenant_id=tenant_id,
        email=req.email.lower(),
        hashed_password=get_password_hash(req.password),
        full_name=req.full_name,
        role="TENANT_ADMIN",
        is_active=True,
    )
    db.add(user)

    # 3. Autonomous Provisioning of Chart of Accounts, Factory, Items, and Certifications
    await provision_tenant_blueprint(session=db, tenant_id=tenant_id, company_name=req.company_name)

    await db.commit()
    logger.info(
        "New organization '%s' (ID: %s) successfully registered with admin '%s'.",
        req.company_name,
        tenant_id,
        req.email,
    )

    # 4. Issue JWT
    token_data = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "email": user.email,
        "role": user.role,
        "company_name": tenant.company_name,
        "tenant_slug": tenant.tenant_slug,
    }
    access_token = create_access_token(token_data)

    return AuthTokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserProfileResponse(
            user_id=user_id,
            tenant_id=tenant_id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            company_name=tenant.company_name,
            tenant_slug=tenant.tenant_slug,
        ),
    )


@router.post("/login", response_model=AuthTokenResponse)
async def login_user(req: LoginRequest, db: DbSessionDep) -> AuthTokenResponse:
    """Authenticates corporate credentials and returns a cryptographic JWT bearer token."""
    stmt = (
        select(User, Tenant)
        .join(Tenant, User.tenant_id == Tenant.tenant_id)
        .where(User.email == req.email.lower())
    )
    if req.tenant_slug:
        stmt = stmt.where(Tenant.tenant_slug == req.tenant_slug.lower())

    result = (await db.execute(stmt)).first()
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user, tenant = result

    if not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active or not tenant.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account or organization is deactivated. Contact enterprise support.",
        )

    token_data = {
        "sub": str(user.user_id),
        "tenant_id": str(tenant.tenant_id),
        "email": user.email,
        "role": user.role,
        "company_name": tenant.company_name,
        "tenant_slug": tenant.tenant_slug,
    }
    access_token = create_access_token(token_data)

    return AuthTokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserProfileResponse(
            user_id=user.user_id,
            tenant_id=tenant.tenant_id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            company_name=tenant.company_name,
            tenant_slug=tenant.tenant_slug,
        ),
    )


@router.get("/me", response_model=UserProfileResponse)
async def get_current_user_profile(
    current_user: CurrentUserDep,
    db: DbSessionDep,
) -> UserProfileResponse:
    """Returns profile and corporate tenant details for the authenticated session."""
    tenant = (
        await db.execute(select(Tenant).where(Tenant.tenant_id == current_user.tenant_id))
    ).scalar_one()
    return UserProfileResponse(
        user_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        company_name=tenant.company_name,
        tenant_slug=tenant.tenant_slug,
    )
