from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.tool_models import ToolExecutionStatus, ToolFailureCategory, ToolSourceType


class TenantToolRegistrationCreate(BaseModel):
    tool_name: str
    enabled: bool = True
    override_timeout_seconds: int | None = Field(default=None, ge=1, le=600)
    override_max_retries: int | None = Field(default=None, ge=1, le=10)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class ToolDefinitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    display_name: str
    description: str | None
    source_type: ToolSourceType
    is_read_only: bool
    default_timeout_seconds: int
    default_max_retries: int
    metadata_json: dict[str, Any]


class TenantToolRegistrationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    enabled: bool
    override_timeout_seconds: int | None
    override_max_retries: int | None
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    tool_definition: ToolDefinitionResponse


class TenantToolRegistrationList(BaseModel):
    items: list[TenantToolRegistrationResponse]
    total: int


class ToolCallResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    run_id: UUID
    run_step_id: UUID | None
    tool_definition_id: UUID
    tenant_tool_registration_id: UUID
    tool_name: str
    step_index: int | None
    status: ToolExecutionStatus
    failure_category: ToolFailureCategory
    attempt_count: int
    request_payload: dict[str, Any]
    normalized_output: dict[str, Any] | None
    raw_output: dict[str, Any] | None
    error_message: str | None
    started_at: datetime
    completed_at: datetime | None
    duration_ms: int | None


class ToolCallList(BaseModel):
    items: list[ToolCallResponse]
    total: int


class ToolNormalizedOutputBase(BaseModel):
    tool_name: str


class KnowledgeSearchMatch(BaseModel):
    id: str | None = None
    title: str | None = None
    summary: str
    score: int


class KnowledgeSearchNormalizedOutput(ToolNormalizedOutputBase):
    query: str
    matches: list[KnowledgeSearchMatch]
    match_count: int


class DocumentRecord(BaseModel):
    id: str | None = None
    slug: str | None = None
    title: str | None = None
    content: str | None = None
    summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentFetchNormalizedOutput(ToolNormalizedOutputBase):
    document: DocumentRecord


class SimpleAnalyticsNormalizedOutput(ToolNormalizedOutputBase):
    operation: str
    field: str | None = None
    group_by: str | None = None
    result: int | float | dict[str, int | float | None] | None


class OutboundDraft(BaseModel):
    subject: str
    body: str
    channel: str


class OutboundDraftNormalizedOutput(ToolNormalizedOutputBase):
    draft: OutboundDraft
