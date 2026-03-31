from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.db.mcp_models import MCPAuthType, MCPServerHealthStatus



from pydantic import field_validator

class MCPAuthConfigCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    auth_type: MCPAuthType = MCPAuthType.NONE
    header_name: str | None = Field(default=None, max_length=120)
    secret_ref: str | None = Field(default=None, max_length=255)
    metadata_json: dict[str, Any] = Field(default_factory=dict)

    @field_validator('secret_ref')
    @classmethod
    def validate_secret_ref(cls, v):
        if v is not None:
            ref = v.strip()
            if not ref:
                raise ValueError("secret_ref must not be empty or whitespace")
            if ref.lower() in {"changeme", "secret", "test", "demo", "password", "123456"}:
                raise ValueError("secret_ref value is not allowed")
            if ref.lower().startswith("env:") and not ref[4:].strip():
                raise ValueError("secret_ref env: reference must specify a variable name")
        return v


class MCPAuthConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    name: str
    auth_type: MCPAuthType
    header_name: str | None
    secret_ref: str | None = Field(default=None, exclude=True, description="Masked in API responses")
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class MCPAuthConfigList(BaseModel):
    items: list[MCPAuthConfigResponse]
    total: int


class MCPServerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    base_url: HttpUrl
    enabled: bool = True
    auth_config_id: UUID | None = None
    health_path: str = Field(default="/health", min_length=1, max_length=255)
    tools_path: str = Field(default="/tools", min_length=1, max_length=255)
    invoke_path_template: str = Field(default="/tools/{tool_name}/invoke", min_length=1, max_length=255)
    scope_filter: list[str] = Field(default_factory=list)
    timeout_seconds: int = Field(default=15, ge=1, le=600)
    max_retries: int = Field(default=2, ge=1, le=10)
    descriptor_metadata_json: dict[str, Any] = Field(default_factory=dict)


class MCPServerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    name: str
    base_url: str
    enabled: bool
    auth_config_id: UUID | None
    health_path: str
    tools_path: str
    invoke_path_template: str
    scope_filter: list[str]
    timeout_seconds: int
    max_retries: int
    descriptor_metadata_json: dict[str, Any]
    health_status: MCPServerHealthStatus
    health_metadata_json: dict[str, Any]
    last_health_checked_at: datetime | None
    last_synced_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class MCPServerList(BaseModel):
    items: list[MCPServerResponse]
    total: int


class MCPHealthCheckResponse(BaseModel):
    server: MCPServerResponse


class MCPSyncResponse(BaseModel):
    server: MCPServerResponse
    discovered_tool_names: list[str]
    synced_count: int
    disabled_count: int
