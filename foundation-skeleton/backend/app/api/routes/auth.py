from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import create_access_token, verify_password
from app.db.models import Membership, User
from app.db.session import get_db_session
from app.schemas.auth import LoginRequest, LoginResponse, MembershipResponse, UserResponse

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db_session)) -> LoginResponse:
    statement = select(User).where(User.email == payload.email).options(
        selectinload(User.memberships).selectinload(Membership.tenant)
    )
    result = await db.execute(statement)
    user = result.scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    if not user.memberships:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not assigned to a tenant")

    primary_membership = user.memberships[0]
    token = create_access_token(subject=str(user.id), tenant_id=str(primary_membership.tenant_id))

    memberships = [
        MembershipResponse(
            tenant_id=str(membership.tenant_id),
            tenant_name=membership.tenant.name,
            tenant_slug=membership.tenant.slug,
            role=membership.role,
        )
        for membership in user.memberships
    ]

    return LoginResponse(
        access_token=token,
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            memberships=memberships,
        ),
    )
