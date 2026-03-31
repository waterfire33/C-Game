"""Authentication dependencies for protected routes."""
import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import ALGORITHM
from app.db.models import Membership, User
from app.db.session import get_db_session


security = HTTPBearer()


class TokenPayload(BaseModel):
    """JWT token payload."""
    sub: str  # User ID
    tenant_id: str


async def get_current_user_id(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> uuid.UUID:
    """Extract and validate user ID from JWT token."""
    try:
        payload = jwt.decode(
            credentials.credentials,
            get_settings().app_secret_key,
            algorithms=[ALGORITHM],
        )
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )
        return uuid.UUID(user_id)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


async def get_current_tenant_id(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> uuid.UUID:
    """Extract tenant ID from JWT token."""
    try:
        payload = jwt.decode(
            credentials.credentials,
            get_settings().app_secret_key,
            algorithms=[ALGORITHM],
        )
        tenant_id = payload.get("tenant_id")
        if tenant_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )
        return uuid.UUID(tenant_id)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


async def get_current_user(
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    db: AsyncSession = Depends(get_db_session),
) -> User:
    """Get full user object from database."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


# Type aliases for dependency injection
CurrentUserId = Annotated[uuid.UUID, Depends(get_current_user_id)]
CurrentTenantId = Annotated[uuid.UUID, Depends(get_current_tenant_id)]
CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_membership(
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    tenant_id: Annotated[uuid.UUID, Depends(get_current_tenant_id)],
    db: AsyncSession = Depends(get_db_session),
) -> Membership:
    """Get the current user's membership for the tenant in the token."""
    result = await db.execute(
        select(Membership).where(
            Membership.user_id == user_id,
            Membership.tenant_id == tenant_id,
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant membership not found",
        )
    return membership


CurrentMembership = Annotated[Membership, Depends(get_current_membership)]
