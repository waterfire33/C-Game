from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class MembershipResponse(BaseModel):
    tenant_id: str
    tenant_name: str
    tenant_slug: str
    role: str


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    memberships: list[MembershipResponse]


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
