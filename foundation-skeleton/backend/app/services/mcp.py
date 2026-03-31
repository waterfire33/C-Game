import asyncio
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol
from urllib.parse import quote, urljoin

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.mcp_models import MCPAuthConfig, MCPAuthType, MCPServerDescriptor, MCPServerHealthStatus
from app.db.tool_models import TenantToolRegistration, ToolDefinition, ToolExecutionStatus, ToolFailureCategory, ToolSourceType
from app.services.tool_adapter import ToolExecutionError, ToolExecutionRequest, ToolExecutionResult


NORMALIZATION_SCHEMA_NAMES = {
    "knowledge_search": "KnowledgeSearchNormalizedOutput",
    "document_fetch": "DocumentFetchNormalizedOutput",
    "simple_analytics_query": "SimpleAnalyticsNormalizedOutput",
    "outbound_draft_generator": "OutboundDraftNormalizedOutput",
}


class MCPRemoteError(Exception):
    pass


class MCPRemoteTimeoutError(MCPRemoteError):
    pass


class MCPOutboundClient(Protocol):
    async def request_json(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
        timeout_seconds: int = 15,
        max_retries: int = 1,
    ) -> tuple[dict[str, Any], int, int]:
        ...


class HTTPXMCPOutboundClient:
    async def request_json(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
        timeout_seconds: int = 15,
        max_retries: int = 1,
    ) -> tuple[dict[str, Any], int, int]:
        last_error: Exception | None = None
        for attempt in range(1, max(1, max_retries) + 1):
            started = datetime.now(timezone.utc)
            try:
                async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                    response = await client.request(method, url, headers=headers, json=json_body)
                latency_ms = max(0, int((datetime.now(timezone.utc) - started).total_seconds() * 1000))
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise MCPRemoteError("remote MCP response must be a JSON object")
                return payload, response.status_code, latency_ms
            except httpx.TimeoutException as exc:
                last_error = exc
                if attempt >= max(1, max_retries):
                    raise MCPRemoteTimeoutError("remote MCP request timed out") from exc
            except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as exc:
                last_error = exc
                if attempt >= max(1, max_retries):
                    raise MCPRemoteError(str(exc)) from exc
            await asyncio.sleep(min(0.25 * attempt, 1.0))
        raise MCPRemoteError(str(last_error or "remote MCP request failed"))


@dataclass(slots=True)
class DiscoveredMCPTool:
    remote_name: str
    display_name: str
    description: str | None
    scopes: list[str]
    is_read_only: bool
    normalization_target: str | None
    metadata_json: dict[str, Any]


@dataclass(slots=True)
class MCPSyncResult:
    discovered_tool_names: list[str]
    synced_count: int
    disabled_count: int


def build_outbound_client() -> MCPOutboundClient:
    return HTTPXMCPOutboundClient()


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return slug or "tool"


def _canonical_tool_name(server_id: uuid.UUID, remote_name: str) -> str:
    return f"mcp__{server_id.hex[:8]}__{_slugify(remote_name)}"


def _should_include_tool(scope_filter: list[str], scopes: list[str]) -> bool:
    if not scope_filter:
        return True
    if not scopes:
        return False
    return bool(set(scope_filter) & set(scopes))


def _normalize_discovered_tool(raw_tool: dict[str, Any]) -> DiscoveredMCPTool:
    remote_name = str(raw_tool.get("name") or raw_tool.get("tool_name") or "").strip()
    if not remote_name:
        raise MCPRemoteError("discovered MCP tool is missing a name")
    return DiscoveredMCPTool(
        remote_name=remote_name,
        display_name=str(raw_tool.get("display_name") or remote_name),
        description=raw_tool.get("description"),
        scopes=[str(scope) for scope in raw_tool.get("scopes") or []],
        is_read_only=bool(raw_tool.get("is_read_only", True)),
        normalization_target=(
            str(raw_tool.get("normalization_target")).strip() if raw_tool.get("normalization_target") else None
        ),
        metadata_json={k: v for k, v in raw_tool.items() if k not in {"name", "tool_name", "display_name", "description", "scopes", "is_read_only", "normalization_target"}},
    )


class MCPService:
    def __init__(self, session: AsyncSession, outbound_client: MCPOutboundClient | None = None):
        self.session = session
        self.outbound_client = outbound_client or build_outbound_client()

    async def create_auth_config(
        self,
        *,
        tenant_id: uuid.UUID,
        name: str,
        auth_type: MCPAuthType,
        header_name: str | None,
        secret_ref: str | None,
        metadata_json: dict[str, Any],
    ) -> MCPAuthConfig:
        auth_config = MCPAuthConfig(
            tenant_id=tenant_id,
            name=name,
            auth_type=auth_type,
            header_name=header_name,
            secret_ref=secret_ref,
            metadata_json=metadata_json,
        )
        self.session.add(auth_config)
        await self.session.flush()
        return auth_config

    async def list_auth_configs(self, tenant_id: uuid.UUID) -> list[MCPAuthConfig]:
        result = await self.session.execute(
            select(MCPAuthConfig)
            .where(MCPAuthConfig.tenant_id == tenant_id)
            .order_by(MCPAuthConfig.created_at.desc())
        )
        return list(result.scalars().all())

    async def create_server(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID | None,
        name: str,
        base_url: str,
        enabled: bool,
        auth_config_id: uuid.UUID | None,
        health_path: str,
        tools_path: str,
        invoke_path_template: str,
        scope_filter: list[str],
        timeout_seconds: int,
        max_retries: int,
        descriptor_metadata_json: dict[str, Any],
    ) -> MCPServerDescriptor:
        if auth_config_id is not None:
            auth_result = await self.session.execute(
                select(MCPAuthConfig).where(
                    MCPAuthConfig.id == auth_config_id,
                    MCPAuthConfig.tenant_id == tenant_id,
                )
            )
            auth_config = auth_result.scalar_one_or_none()
            if auth_config is None:
                raise ToolExecutionError("MCP auth config not found", ToolFailureCategory.NOT_FOUND)

        server = MCPServerDescriptor(
            tenant_id=tenant_id,
            name=name,
            base_url=str(base_url).rstrip("/"),
            enabled=enabled,
            auth_config_id=auth_config_id,
            health_path=health_path,
            tools_path=tools_path,
            invoke_path_template=invoke_path_template,
            scope_filter=scope_filter,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            descriptor_metadata_json=descriptor_metadata_json,
            created_by_user_id=user_id,
        )
        self.session.add(server)
        await self.session.flush()
        return server

    async def list_servers(self, tenant_id: uuid.UUID) -> list[MCPServerDescriptor]:
        result = await self.session.execute(
            select(MCPServerDescriptor)
            .where(MCPServerDescriptor.tenant_id == tenant_id)
            .order_by(MCPServerDescriptor.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_server(self, tenant_id: uuid.UUID, server_id: uuid.UUID) -> MCPServerDescriptor:
        result = await self.session.execute(
            select(MCPServerDescriptor)
            .where(MCPServerDescriptor.id == server_id, MCPServerDescriptor.tenant_id == tenant_id)
            .options(selectinload(MCPServerDescriptor.auth_config))
        )
        server = result.scalar_one_or_none()
        if server is None:
            raise ToolExecutionError("MCP server not found", ToolFailureCategory.NOT_FOUND)
        return server

    def _resolve_secret(self, secret_ref: str | None) -> str | None:
        """
        Resolves a secret reference. Supports:
        - Literal value (default)
        - Environment variable indirection: env:MY_ENV_VAR
        """
        import os
        if not secret_ref:
            return None
        secret_ref = secret_ref.strip()
        if secret_ref.lower().startswith("env:"):
            env_var = secret_ref[4:].strip()
            if not env_var:
                raise ToolExecutionError("Empty environment variable name in secret_ref", ToolFailureCategory.INVALID_INPUT)
            value = os.getenv(env_var)
            if value is None:
                raise ToolExecutionError(f"Environment variable '{env_var}' not set for secret_ref", ToolFailureCategory.NOT_FOUND)
            return value
        return secret_ref

    def _build_headers(self, server: MCPServerDescriptor) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        auth_config = server.auth_config
        if auth_config is None or auth_config.auth_type == MCPAuthType.NONE:
            return headers
        secret = self._resolve_secret(auth_config.secret_ref)
        if auth_config.auth_type == MCPAuthType.BEARER_TOKEN and secret:
            headers["Authorization"] = f"Bearer {secret}"
        elif auth_config.auth_type == MCPAuthType.STATIC_HEADER and auth_config.header_name and secret:
            headers[auth_config.header_name] = secret
        return headers

    async def check_health(self, server: MCPServerDescriptor) -> MCPServerDescriptor:
        try:
            payload, status_code, latency_ms = await self.outbound_client.request_json(
                method="GET",
                url=urljoin(f"{server.base_url}/", server.health_path.lstrip("/")),
                headers=self._build_headers(server),
                timeout_seconds=server.timeout_seconds,
                max_retries=server.max_retries,
            )
            status_value = str(payload.get("status") or "").lower()
            server.health_status = (
                MCPServerHealthStatus.HEALTHY if status_value in {"ok", "healthy", "ready"} else MCPServerHealthStatus.DEGRADED
            )
            server.health_metadata_json = {"status_code": status_code, "latency_ms": latency_ms, "payload": payload}
            server.last_error = None
        except MCPRemoteTimeoutError as exc:
            server.health_status = MCPServerHealthStatus.UNREACHABLE
            server.health_metadata_json = {"reason": "timeout"}
            server.last_error = str(exc)
        except MCPRemoteError as exc:
            server.health_status = MCPServerHealthStatus.UNREACHABLE
            server.health_metadata_json = {"reason": "request_error"}
            server.last_error = str(exc)
        server.last_health_checked_at = datetime.now(timezone.utc)
        await self.session.flush()
        return server

    async def sync_server_tools(self, server: MCPServerDescriptor) -> MCPSyncResult:
        headers = self._build_headers(server)
        payload, _, _ = await self.outbound_client.request_json(
            method="GET",
            url=urljoin(f"{server.base_url}/", server.tools_path.lstrip("/")),
            headers=headers,
            timeout_seconds=server.timeout_seconds,
            max_retries=server.max_retries,
        )
        raw_tools = payload.get("tools") if isinstance(payload.get("tools"), list) else payload
        if not isinstance(raw_tools, list):
            raise MCPRemoteError("MCP tools endpoint must return {'tools': [...]} or a JSON list")

        current_result = await self.session.execute(
            select(TenantToolRegistration)
            .join(TenantToolRegistration.tool_definition)
            .where(
                TenantToolRegistration.tenant_id == server.tenant_id,
                ToolDefinition.source_type == ToolSourceType.MCP,
            )
            .options(selectinload(TenantToolRegistration.tool_definition))
        )
        existing_regs = [
            reg for reg in current_result.scalars().all()
            if str(reg.tool_definition.metadata_json.get("mcp_server_id")) == str(server.id)
        ]
        existing_by_name = {reg.tool_definition.name: reg for reg in existing_regs}

        synced_count = 0
        discovered_names: list[str] = []
        seen_names: set[str] = set()

        for raw_tool in raw_tools:
            if not isinstance(raw_tool, dict):
                continue
            discovered_tool = _normalize_discovered_tool(raw_tool)
            if not _should_include_tool(server.scope_filter, discovered_tool.scopes):
                continue
            canonical_name = _canonical_tool_name(server.id, discovered_tool.remote_name)
            seen_names.add(canonical_name)
            discovered_names.append(canonical_name)

            tool_result = await self.session.execute(
                select(ToolDefinition).where(ToolDefinition.name == canonical_name)
            )
            tool_definition = tool_result.scalar_one_or_none()
            schema_name = NORMALIZATION_SCHEMA_NAMES.get(discovered_tool.normalization_target or "")
            metadata_json = {
                "mcp_server_id": str(server.id),
                "remote_tool_name": discovered_tool.remote_name,
                "remote_scopes": discovered_tool.scopes,
                "normalization_target": discovered_tool.normalization_target,
                "normalized_output_schema": schema_name,
                **discovered_tool.metadata_json,
            }
            if tool_definition is None:
                tool_definition = ToolDefinition(
                    id=uuid.uuid4(),
                    name=canonical_name,
                    display_name=discovered_tool.display_name,
                    description=discovered_tool.description,
                    source_type=ToolSourceType.MCP,
                    is_read_only=discovered_tool.is_read_only,
                    default_timeout_seconds=server.timeout_seconds,
                    default_max_retries=server.max_retries,
                    metadata_json=metadata_json,
                )
                self.session.add(tool_definition)
                await self.session.flush()
            else:
                tool_definition.display_name = discovered_tool.display_name
                tool_definition.description = discovered_tool.description
                tool_definition.source_type = ToolSourceType.MCP
                tool_definition.is_read_only = discovered_tool.is_read_only
                tool_definition.default_timeout_seconds = server.timeout_seconds
                tool_definition.default_max_retries = server.max_retries
                tool_definition.metadata_json = metadata_json

            registration = existing_by_name.get(canonical_name)
            if registration is None:
                registration = TenantToolRegistration(
                    id=uuid.uuid4(),
                    tenant_id=server.tenant_id,
                    tool_definition_id=tool_definition.id,
                    enabled=server.enabled,
                    override_timeout_seconds=server.timeout_seconds,
                    override_max_retries=server.max_retries,
                    metadata_json={"mcp_server_id": str(server.id)},
                )
                self.session.add(registration)
            else:
                registration.enabled = server.enabled
                registration.override_timeout_seconds = server.timeout_seconds
                registration.override_max_retries = server.max_retries
                registration.metadata_json = {**(registration.metadata_json or {}), "mcp_server_id": str(server.id)}
            synced_count += 1

        disabled_count = 0
        for registration in existing_regs:
            if registration.tool_definition.name not in seen_names:
                registration.enabled = False
                disabled_count += 1

        server.last_synced_at = datetime.now(timezone.utc)
        server.last_error = None
        await self.session.flush()
        return MCPSyncResult(
            discovered_tool_names=sorted(discovered_names),
            synced_count=synced_count,
            disabled_count=disabled_count,
        )

    async def execute_remote_tool(
        self,
        registration: TenantToolRegistration,
        request: ToolExecutionRequest,
        *,
        timeout_seconds: int,
        max_retries: int,
    ) -> ToolExecutionResult:
        tool_definition = registration.tool_definition
        server_id = tool_definition.metadata_json.get("mcp_server_id")
        remote_tool_name = tool_definition.metadata_json.get("remote_tool_name")
        if not server_id or not remote_tool_name:
            raise ToolExecutionError("MCP tool metadata is incomplete", ToolFailureCategory.INTERNAL)

        server_result = await self.session.execute(
            select(MCPServerDescriptor)
            .where(MCPServerDescriptor.id == uuid.UUID(str(server_id)), MCPServerDescriptor.tenant_id == request.tenant_id)
            .options(selectinload(MCPServerDescriptor.auth_config))
        )
        server = server_result.scalar_one_or_none()
        if server is None or not server.enabled:
            raise ToolExecutionError("MCP server is unavailable for this tenant", ToolFailureCategory.NOT_ALLOWED)

        try:
            response_payload, _, latency_ms = await self.outbound_client.request_json(
                method="POST",
                url=urljoin(
                    f"{server.base_url}/",
                    server.invoke_path_template.format(tool_name=quote(str(remote_tool_name), safe="")).lstrip("/"),
                ),
                headers=self._build_headers(server),
                json_body={
                    "tool_name": remote_tool_name,
                    "input": request.input_payload,
                    "context": {
                        "run_id": str(request.run_id),
                        "step_index": request.step_index,
                        "metadata": request.metadata,
                    },
                },
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
            )
        except MCPRemoteTimeoutError as exc:
            return ToolExecutionResult(
                status=ToolExecutionStatus.TIMED_OUT,
                normalized_output=None,
                raw_output=None,
                state_patch={},
                failure_category=ToolFailureCategory.TIMEOUT,
                error_message=str(exc),
                attempt_count=max(1, max_retries),
            )
        except MCPRemoteError as exc:
            return ToolExecutionResult(
                status=ToolExecutionStatus.FAILED,
                normalized_output=None,
                raw_output=None,
                state_patch={},
                failure_category=ToolFailureCategory.TRANSIENT,
                error_message=str(exc),
                attempt_count=max(1, max_retries),
            )

        normalized_output = self.normalize_execution_output(tool_definition, response_payload)
        return ToolExecutionResult(
            status=ToolExecutionStatus.SUCCEEDED,
            normalized_output=normalized_output,
            raw_output=response_payload,
            state_patch={"mcp_tool_output": normalized_output},
            attempt_count=max(1, max_retries),
            duration_ms=latency_ms,
        )

    def normalize_execution_output(self, tool_definition: ToolDefinition, payload: dict[str, Any]) -> dict[str, Any]:
        target = str(tool_definition.metadata_json.get("normalization_target") or "").strip()
        tool_name = tool_definition.name
        if target == "knowledge_search":
            matches = list(payload.get("matches") or [])
            return {
                "tool_name": tool_name,
                "query": payload.get("query") or "",
                "matches": matches,
                "match_count": payload.get("match_count") or len(matches),
            }
        if target == "document_fetch":
            return {
                "tool_name": tool_name,
                "document": payload.get("document") or {},
            }
        if target == "simple_analytics_query":
            return {
                "tool_name": tool_name,
                "operation": payload.get("operation") or "count",
                "field": payload.get("field"),
                "group_by": payload.get("group_by"),
                "result": payload.get("result"),
            }
        if target == "outbound_draft_generator":
            return {
                "tool_name": tool_name,
                "draft": payload.get("draft") or {},
            }
        if "tool_name" not in payload:
            return {"tool_name": tool_name, **payload}
        return payload
