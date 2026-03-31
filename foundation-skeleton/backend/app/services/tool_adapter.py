import asyncio
import math
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.tool_models import (
    TenantToolRegistration,
    ToolCall,
    ToolDefinition,
    ToolExecutionStatus,
    ToolFailureCategory,
    ToolSourceType,
)
from app.db.workflow_models import EventType, WorkflowRun, WorkflowRunStep, WorkflowStepDefinition
from app.schemas.tools import (
    DocumentFetchNormalizedOutput,
    KnowledgeSearchNormalizedOutput,
    OutboundDraftNormalizedOutput,
    SimpleAnalyticsNormalizedOutput,
)
from app.services.event_logger import EventLogger


class ToolExecutionError(Exception):
    def __init__(self, message: str, category: ToolFailureCategory, *, retryable: bool = False):
        self.category = category
        self.retryable = retryable
        super().__init__(message)


@dataclass(slots=True)
class ToolExecutionRequest:
    tenant_id: uuid.UUID
    run_id: uuid.UUID
    run_step_id: uuid.UUID | None
    step_index: int | None
    tool_name: str
    input_payload: dict[str, Any]
    run_state: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ToolExecutionResult:
    status: ToolExecutionStatus
    normalized_output: dict[str, Any] | None
    raw_output: dict[str, Any] | None
    state_patch: dict[str, Any]
    failure_category: ToolFailureCategory = ToolFailureCategory.NONE
    error_message: str | None = None
    attempt_count: int = 1
    duration_ms: int | None = None


class InternalTool(Protocol):
    name: str
    display_name: str
    description: str
    is_read_only: bool
    default_timeout_seconds: int
    default_max_retries: int
    metadata_json: dict[str, Any]

    async def execute(self, request: ToolExecutionRequest) -> ToolExecutionResult:
        ...


def _tokenize(value: str) -> set[str]:
    return {token for token in re.split(r"[^a-zA-Z0-9]+", value.lower()) if token}


NORMALIZED_OUTPUT_SCHEMAS = {
    "knowledge_search": KnowledgeSearchNormalizedOutput,
    "document_fetch": DocumentFetchNormalizedOutput,
    "simple_analytics_query": SimpleAnalyticsNormalizedOutput,
    "outbound_draft_generator": OutboundDraftNormalizedOutput,
}

NORMALIZED_OUTPUT_SCHEMAS_BY_NAME = {
    schema.__name__: schema for schema in NORMALIZED_OUTPUT_SCHEMAS.values()
}


def resolve_tool_name(step_type: str, config: dict[str, Any] | None = None) -> str | None:
    config = config or {}
    configured_tool_name = str(config.get("tool_name") or "").strip()
    if configured_tool_name:
        return configured_tool_name
    if step_type in INTERNAL_TOOLS:
        return step_type
    return None


def validate_normalized_output(
    tool_name: str,
    payload: dict[str, Any] | None,
    *,
    schema_name: str | None = None,
) -> dict[str, Any] | None:
    if payload is None:
        return None
    schema = NORMALIZED_OUTPUT_SCHEMAS_BY_NAME.get(schema_name or "") or NORMALIZED_OUTPUT_SCHEMAS.get(tool_name)
    if schema is None:
        return payload
    return schema.model_validate(payload).model_dump()


class KnowledgeSearchTool:
    name = "knowledge_search"
    display_name = "Knowledge Search"
    description = "Searches tenant-provided knowledge items using token overlap ranking."
    is_read_only = True
    default_timeout_seconds = 15
    default_max_retries = 1
    metadata_json = {"capabilities": ["search", "read_only"], "normalized_output_schema": "KnowledgeSearchNormalizedOutput"}

    async def execute(self, request: ToolExecutionRequest) -> ToolExecutionResult:
        query = str(request.input_payload.get("query", "")).strip()
        if not query:
            raise ToolExecutionError("query is required", ToolFailureCategory.VALIDATION)

        items = request.input_payload.get("knowledge_items") or request.run_state.get("knowledge_items") or []
        query_tokens = _tokenize(query)

        scored_matches: list[dict[str, Any]] = []
        for item in items:
            text = " ".join(
                str(item.get(field, "")) for field in ("title", "text", "summary")
            )
            text_tokens = _tokenize(text)
            overlap = len(query_tokens & text_tokens)
            if overlap == 0:
                continue
            scored_matches.append(
                {
                    "id": item.get("id"),
                    "title": item.get("title"),
                    "summary": item.get("summary") or item.get("text", "")[:240],
                    "score": overlap,
                }
            )

        scored_matches.sort(key=lambda item: item["score"], reverse=True)
        limit = int(request.input_payload.get("limit", 5))
        matches = scored_matches[:limit]
        normalized_output = {
            "tool_name": self.name,
            "query": query,
            "matches": matches,
            "match_count": len(matches),
        }
        return ToolExecutionResult(
            status=ToolExecutionStatus.SUCCEEDED,
            normalized_output=normalized_output,
            raw_output={"matches": matches},
            state_patch={"knowledge_search_results": matches},
        )


class DocumentFetchTool:
    name = "document_fetch"
    display_name = "Document Fetch"
    description = "Fetches a document from run state or payload by id or slug."
    is_read_only = True
    default_timeout_seconds = 10
    default_max_retries = 1
    metadata_json = {"capabilities": ["document_lookup", "read_only"], "normalized_output_schema": "DocumentFetchNormalizedOutput"}

    async def execute(self, request: ToolExecutionRequest) -> ToolExecutionResult:
        documents = request.input_payload.get("documents") or request.run_state.get("documents") or []
        document_id = request.input_payload.get("document_id")
        document_slug = request.input_payload.get("document_slug")
        if document_id is None and document_slug is None:
            raise ToolExecutionError(
                "document_id or document_slug is required",
                ToolFailureCategory.VALIDATION,
            )

        match = None
        for document in documents:
            if document_id is not None and document.get("id") == document_id:
                match = document
                break
            if document_slug is not None and document.get("slug") == document_slug:
                match = document
                break

        if match is None:
            raise ToolExecutionError("document not found", ToolFailureCategory.NOT_FOUND)

        normalized_output = {
            "tool_name": self.name,
            "document": match,
        }
        return ToolExecutionResult(
            status=ToolExecutionStatus.SUCCEEDED,
            normalized_output=normalized_output,
            raw_output=match,
            state_patch={"fetched_document": match},
        )


class SimpleAnalyticsQueryTool:
    name = "simple_analytics_query"
    display_name = "Simple Analytics Query"
    description = "Runs count, sum, avg, min, or max over tenant-provided rows."
    is_read_only = True
    default_timeout_seconds = 20
    default_max_retries = 1
    metadata_json = {"capabilities": ["aggregation", "read_only"], "normalized_output_schema": "SimpleAnalyticsNormalizedOutput"}

    async def execute(self, request: ToolExecutionRequest) -> ToolExecutionResult:
        rows = request.input_payload.get("rows") or request.run_state.get("analytics_rows") or []
        operation = str(request.input_payload.get("operation", "count")).lower()
        field_name = request.input_payload.get("field")
        group_by = request.input_payload.get("group_by")

        if operation not in {"count", "sum", "avg", "min", "max"}:
            raise ToolExecutionError("unsupported analytics operation", ToolFailureCategory.VALIDATION)

        if operation != "count" and not field_name:
            raise ToolExecutionError("field is required for this analytics operation", ToolFailureCategory.VALIDATION)

        def compute(values: list[float]) -> float | int | None:
            if operation == "count":
                return len(values)
            if not values:
                return None
            if operation == "sum":
                return sum(values)
            if operation == "avg":
                return sum(values) / len(values)
            if operation == "min":
                return min(values)
            return max(values)

        if group_by:
            grouped: dict[str, list[float]] = {}
            for row in rows:
                group_value = str(row.get(group_by, "unknown"))
                grouped.setdefault(group_value, [])
                if operation == "count":
                    grouped[group_value].append(1.0)
                else:
                    raw_value = row.get(field_name)
                    if raw_value is None:
                        continue
                    grouped[group_value].append(float(raw_value))
            result = {key: compute(values) for key, values in grouped.items()}
        else:
            values = [1.0 for _ in rows] if operation == "count" else [float(row[field_name]) for row in rows if row.get(field_name) is not None]
            result = compute(values)

        normalized_output = {
            "tool_name": self.name,
            "operation": operation,
            "field": field_name,
            "group_by": group_by,
            "result": result,
        }
        return ToolExecutionResult(
            status=ToolExecutionStatus.SUCCEEDED,
            normalized_output=normalized_output,
            raw_output={"result": result},
            state_patch={"analytics_result": result},
        )


class OutboundDraftGeneratorTool:
    name = "outbound_draft_generator"
    display_name = "Outbound Draft Generator"
    description = "Generates a structured outbound draft from provided context without sending it."
    is_read_only = True
    default_timeout_seconds = 15
    default_max_retries = 1
    metadata_json = {"capabilities": ["draft_generation", "read_only"], "normalized_output_schema": "OutboundDraftNormalizedOutput"}

    async def execute(self, request: ToolExecutionRequest) -> ToolExecutionResult:
        audience = str(request.input_payload.get("audience", "customer")).strip()
        objective = str(request.input_payload.get("objective", "follow up")).strip()
        tone = str(request.input_payload.get("tone", "clear and direct")).strip()
        facts = request.input_payload.get("facts") or []
        if not objective:
            raise ToolExecutionError("objective is required", ToolFailureCategory.VALIDATION)

        bullet_lines = "\n".join(f"- {fact}" for fact in facts)
        subject = f"{objective.title()} for {audience.title()}"
        body = (
            f"Hello {audience},\n\n"
            f"I am reaching out to {objective}. The tone should stay {tone}.\n\n"
            f"Key points:\n{bullet_lines if bullet_lines else '- No additional facts provided'}\n\n"
            "Please let me know if you would like a revised version tailored for a different channel."
        )
        draft = {
            "subject": subject,
            "body": body,
            "channel": request.input_payload.get("channel", "email"),
        }
        normalized_output = {
            "tool_name": self.name,
            "draft": draft,
        }
        return ToolExecutionResult(
            status=ToolExecutionStatus.SUCCEEDED,
            normalized_output=normalized_output,
            raw_output=draft,
            state_patch={"outbound_draft": draft},
        )


INTERNAL_TOOLS: dict[str, InternalTool] = {
    tool.name: tool
    for tool in (
        KnowledgeSearchTool(),
        DocumentFetchTool(),
        SimpleAnalyticsQueryTool(),
        OutboundDraftGeneratorTool(),
    )
}


class ToolRegistryService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def sync_internal_tool_definitions(self) -> None:
        result = await self.session.execute(select(ToolDefinition))
        existing = {tool.name: tool for tool in result.scalars().all()}

        for tool in INTERNAL_TOOLS.values():
            record = existing.get(tool.name)
            if record is None:
                self.session.add(
                    ToolDefinition(
                        id=uuid.uuid4(),
                        name=tool.name,
                        display_name=tool.display_name,
                        description=tool.description,
                        is_read_only=tool.is_read_only,
                        default_timeout_seconds=tool.default_timeout_seconds,
                        default_max_retries=tool.default_max_retries,
                        metadata_json=tool.metadata_json,
                    )
                )
                continue

            record.display_name = tool.display_name
            record.description = tool.description
            record.is_read_only = tool.is_read_only
            record.default_timeout_seconds = tool.default_timeout_seconds
            record.default_max_retries = tool.default_max_retries
            record.metadata_json = tool.metadata_json

        await self.session.flush()

    async def register_tool_for_tenant(
        self,
        tenant_id: uuid.UUID,
        tool_name: str,
        *,
        enabled: bool = True,
        override_timeout_seconds: int | None = None,
        override_max_retries: int | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> TenantToolRegistration:
        await self.sync_internal_tool_definitions()

        result = await self.session.execute(
            select(TenantToolRegistration)
            .join(TenantToolRegistration.tool_definition)
            .where(
                TenantToolRegistration.tenant_id == tenant_id,
                ToolDefinition.name == tool_name,
            )
            .options(selectinload(TenantToolRegistration.tool_definition))
        )
        registration = result.scalar_one_or_none()

        if registration is None:
            tool_result = await self.session.execute(
                select(ToolDefinition).where(ToolDefinition.name == tool_name)
            )
            tool_definition = tool_result.scalar_one_or_none()
            if tool_definition is None:
                raise ToolExecutionError("tool definition not found", ToolFailureCategory.NOT_FOUND)

            registration = TenantToolRegistration(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                tool_definition_id=tool_definition.id,
                enabled=enabled,
                override_timeout_seconds=override_timeout_seconds,
                override_max_retries=override_max_retries,
                metadata_json=metadata_json or {},
            )
            self.session.add(registration)
            await self.session.flush()
            await self.session.refresh(registration, ["tool_definition"])
            return registration

        registration.enabled = enabled
        registration.override_timeout_seconds = override_timeout_seconds
        registration.override_max_retries = override_max_retries
        registration.metadata_json = metadata_json or registration.metadata_json
        await self.session.flush()
        return registration

    async def list_allowed_tools(self, tenant_id: uuid.UUID) -> list[TenantToolRegistration]:
        await self.sync_internal_tool_definitions()
        result = await self.session.execute(
            select(TenantToolRegistration)
            .where(
                TenantToolRegistration.tenant_id == tenant_id,
                TenantToolRegistration.enabled.is_(True),
            )
            .options(selectinload(TenantToolRegistration.tool_definition))
            .order_by(TenantToolRegistration.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_registration_for_execution(
        self, tenant_id: uuid.UUID, tool_name: str
    ) -> TenantToolRegistration:
        await self.sync_internal_tool_definitions()
        result = await self.session.execute(
            select(TenantToolRegistration)
            .join(TenantToolRegistration.tool_definition)
            .where(
                TenantToolRegistration.tenant_id == tenant_id,
                TenantToolRegistration.enabled.is_(True),
                ToolDefinition.name == tool_name,
            )
            .options(selectinload(TenantToolRegistration.tool_definition))
        )
        registration = result.scalar_one_or_none()
        if registration is None:
            raise ToolExecutionError(
                f"tool '{tool_name}' is not registered for this tenant",
                ToolFailureCategory.NOT_ALLOWED,
            )
        return registration

    async def ensure_tool_steps_allowed(self, tenant_id: uuid.UUID, steps: list[dict[str, Any]]) -> None:
        tool_names = {
            tool_name
            for step in steps
            if (tool_name := resolve_tool_name(str(step.get("step_type", "")), step.get("config") or {})) is not None
        }
        for tool_name in sorted(tool_names):
            await self.get_registration_for_execution(tenant_id, tool_name)


class ToolExecutor:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.registry = ToolRegistryService(session)
        self.event_logger = EventLogger(session)

    async def execute_step_tool(
        self,
        run: WorkflowRun,
        run_step: WorkflowRunStep,
        step_def: WorkflowStepDefinition,
    ) -> ToolExecutionResult:
        tool_name = resolve_tool_name(step_def.step_type, step_def.config)
        if not tool_name:
            raise ToolExecutionError("tool_name is required for tool-backed steps", ToolFailureCategory.VALIDATION)

        registration = await self.registry.get_registration_for_execution(run.tenant_id, tool_name)

        timeout_seconds = registration.override_timeout_seconds or step_def.timeout_seconds or registration.tool_definition.default_timeout_seconds
        max_attempts = registration.override_max_retries or step_def.max_retries or registration.tool_definition.default_max_retries

        request = ToolExecutionRequest(
            tenant_id=run.tenant_id,
            run_id=run.id,
            run_step_id=run_step.id,
            step_index=run_step.step_index,
            tool_name=tool_name,
            input_payload=dict(step_def.config.get("input", {})),
            run_state=dict(run.state or {}),
            metadata={"step_name": step_def.name},
        )

        started_at = datetime.now(timezone.utc)
        result: ToolExecutionResult | None = None

        if registration.tool_definition.source_type == ToolSourceType.MCP:
            from app.services.mcp import MCPService

            mcp_service = MCPService(self.session)
            result = await mcp_service.execute_remote_tool(
                registration,
                request,
                timeout_seconds=timeout_seconds,
                max_retries=max_attempts,
            )
            result.normalized_output = validate_normalized_output(
                tool_name,
                result.normalized_output,
                schema_name=registration.tool_definition.metadata_json.get("normalized_output_schema"),
            )
        else:
            tool = INTERNAL_TOOLS.get(tool_name)
            if tool is None:
                raise ToolExecutionError(f"internal tool '{tool_name}' is not available", ToolFailureCategory.NOT_FOUND)

            last_error: ToolExecutionError | None = None

            for attempt in range(1, max(1, max_attempts) + 1):
                try:
                    execution_result = await asyncio.wait_for(tool.execute(request), timeout=timeout_seconds)
                    execution_result.normalized_output = validate_normalized_output(
                        tool_name,
                        execution_result.normalized_output,
                        schema_name=registration.tool_definition.metadata_json.get("normalized_output_schema"),
                    )
                    execution_result.attempt_count = attempt
                    result = execution_result
                    break
                except asyncio.TimeoutError:
                    last_error = ToolExecutionError("tool execution timed out", ToolFailureCategory.TIMEOUT, retryable=False)
                except ToolExecutionError as exc:
                    last_error = exc
                    if not exc.retryable:
                        break
                except ValueError as exc:
                    last_error = ToolExecutionError(str(exc), ToolFailureCategory.INTERNAL, retryable=False)
                    break
                except Exception as exc:
                    last_error = ToolExecutionError(str(exc), ToolFailureCategory.INTERNAL, retryable=False)
                    break

            if result is None:
                if last_error is None:
                    last_error = ToolExecutionError("tool execution failed", ToolFailureCategory.INTERNAL)
                status = ToolExecutionStatus.TIMED_OUT if last_error.category == ToolFailureCategory.TIMEOUT else ToolExecutionStatus.FAILED
                result = ToolExecutionResult(
                    status=status,
                    normalized_output=None,
                    raw_output=None,
                    state_patch={},
                    failure_category=last_error.category,
                    error_message=str(last_error),
                    attempt_count=max(1, max_attempts),
                )

        completed_at = datetime.now(timezone.utc)
        duration_ms = max(0, math.floor((completed_at - started_at).total_seconds() * 1000))

        if result.duration_ms is None:
            result.duration_ms = duration_ms

        tool_call = ToolCall(
            id=uuid.uuid4(),
            tenant_id=run.tenant_id,
            run_id=run.id,
            run_step_id=run_step.id,
            tool_definition_id=registration.tool_definition_id,
            tenant_tool_registration_id=registration.id,
            tool_name=tool_name,
            step_index=run_step.step_index,
            status=result.status,
            failure_category=result.failure_category,
            attempt_count=result.attempt_count,
            request_payload=request.input_payload,
            normalized_output=result.normalized_output,
            raw_output=result.raw_output,
            error_message=result.error_message,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=result.duration_ms,
        )
        self.session.add(tool_call)

        if result.status == ToolExecutionStatus.SUCCEEDED:
            tool_outputs = dict((run.state or {}).get("tool_outputs") or {})
            tool_outputs[f"step_{run_step.step_index}"] = result.normalized_output
            run.state = {
                **(run.state or {}),
                **result.state_patch,
                "tool_outputs": tool_outputs,
            }
            await self.event_logger.log_event(
                run.id,
                EventType.STATE_UPDATED,
                step_index=run_step.step_index,
                actor_type="worker",
                payload={
                    "tool_name": tool_name,
                    "tool_call_id": str(tool_call.id),
                    "merged_state_keys": sorted(result.state_patch.keys()),
                },
            )

        return result
