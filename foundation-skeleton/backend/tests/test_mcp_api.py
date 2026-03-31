import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.mcp_models import MCPServerHealthStatus
from app.db.tool_models import ToolCall, ToolSourceType
from app.db.workflow_models import RunStatus, WorkflowDefinition, WorkflowStepDefinition
from app.services.mcp import MCPRemoteError
from app.services.state_machine import RunStateMachine
from app.worker.runner import WorkflowWorker


class FakeMCPOutboundClient:
    def __init__(self):
        self.calls: list[dict[str, object]] = []
        self.exposed_tools = [
            {
                "name": "knowledge_lookup",
                "display_name": "Knowledge Lookup",
                "description": "Remote knowledge search",
                "scopes": ["knowledge", "read"],
                "is_read_only": True,
                "normalization_target": "knowledge_search",
            },
            {
                "name": "draft_writer",
                "display_name": "Draft Writer",
                "description": "Remote draft generator",
                "scopes": ["draft"],
                "is_read_only": True,
                "normalization_target": "outbound_draft_generator",
            },
            {
                "name": "admin_only_tool",
                "display_name": "Admin Only Tool",
                "description": "Should be filtered out",
                "scopes": ["admin"],
                "is_read_only": True,
                "normalization_target": "knowledge_search",
            },
        ]

    async def request_json(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        json_body: dict[str, object] | None = None,
        timeout_seconds: int = 15,
        max_retries: int = 1,
    ) -> tuple[dict[str, object], int, int]:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers or {},
                "json_body": json_body or {},
                "timeout_seconds": timeout_seconds,
                "max_retries": max_retries,
            }
        )
        if url.endswith("/health"):
            return {"status": "ok", "service": "fake-mcp"}, 200, 7
        if url.endswith("/tools"):
            return {"tools": list(self.exposed_tools)}, 200, 9
        if url.endswith("/tools/knowledge_lookup/invoke"):
            query = str((json_body or {}).get("input", {}).get("query", ""))
            return {
                "query": query,
                "matches": [
                    {
                        "id": "doc-remote-1",
                        "title": "Remote Policy",
                        "summary": "Remote match",
                        "score": 3,
                    }
                ],
            }, 200, 11
        if url.endswith("/tools/draft_writer/invoke"):
            return {
                "draft": {
                    "subject": "Remote Draft",
                    "body": "Draft body",
                    "channel": "email",
                }
            }, 200, 10
        raise MCPRemoteError(f"unexpected fake MCP request: {method} {url}")


@pytest.fixture
def fake_mcp_client(monkeypatch) -> FakeMCPOutboundClient:
    client = FakeMCPOutboundClient()
    monkeypatch.setattr("app.services.mcp.build_outbound_client", lambda: client)
    return client


async def _create_and_execute_remote_tool_run(
    db_session: AsyncSession,
    db_engine,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    tool_name: str,
    risk_class: str = "A",
    required_role: str | None = None,
) -> str:
    definition = WorkflowDefinition(
        tenant_id=tenant_id,
        name=f"remote-{tool_name}",
        description="remote tool workflow",
        version=1,
        is_active=True,
        created_by_user_id=user_id,
    )
    db_session.add(definition)
    await db_session.flush()

    db_session.add(
        WorkflowStepDefinition(
            workflow_definition_id=definition.id,
            name=f"Run {tool_name}",
            step_type="tool",
            order=0,
            config={"tool_name": tool_name, "input": {"query": "returns policy"}},
            max_retries=1,
            action_risk_class=risk_class,
            required_approver_role=required_role,
        )
    )
    await db_session.commit()

    state_machine = RunStateMachine(db_session)
    run = await state_machine.create_run(
        workflow_definition_id=definition.id,
        tenant_id=tenant_id,
        idempotency_key=f"remote-{tool_name}-{risk_class}",
        triggered_by_user_id=user_id,
    )
    run = await state_machine.start_run(run, "mcp-test-worker")
    await db_session.commit()

    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    worker = WorkflowWorker(session_factory=session_factory, poll_interval=0.01)
    await worker._execute_run(db_session, run)
    return str(run.id)


class TestMcpIntegration:
    @pytest.mark.asyncio
    async def test_attach_server_and_health_check(
        self,
        api_client: AsyncClient,
        auth_headers: dict[str, str],
        fake_mcp_client: FakeMCPOutboundClient,
    ):
        auth_response = await api_client.post(
            "/mcp/auth-configs",
            headers=auth_headers,
            json={
                "name": "demo-token",
                "auth_type": "bearer_token",
                "secret_ref": "live-demo-token",
            },
        )
        assert auth_response.status_code == 201
        auth_config_id = auth_response.json()["id"]

        create_response = await api_client.post(
            "/mcp/servers",
            headers=auth_headers,
            json={
                "name": "Remote MCP",
                "base_url": "https://mcp.example.test",
                "auth_config_id": auth_config_id,
                "scope_filter": ["knowledge"],
                "timeout_seconds": 12,
                "max_retries": 3,
            },
        )
        assert create_response.status_code == 201
        server_id = create_response.json()["id"]

        health_response = await api_client.post(f"/mcp/servers/{server_id}/health-check", headers=auth_headers)
        assert health_response.status_code == 200
        payload = health_response.json()
        assert payload["server"]["health_status"] == MCPServerHealthStatus.HEALTHY.value
        assert fake_mcp_client.calls[-1]["headers"]["Authorization"] == "Bearer live-demo-token"

    @pytest.mark.asyncio
    async def test_sync_discovers_tools_and_exposes_them_in_registry(
        self,
        api_client: AsyncClient,
        auth_headers: dict[str, str],
        fake_mcp_client: FakeMCPOutboundClient,
    ):
        create_response = await api_client.post(
            "/mcp/servers",
            headers=auth_headers,
            json={
                "name": "Scoped MCP",
                "base_url": "https://mcp.example.test",
                "scope_filter": ["knowledge"],
            },
        )
        assert create_response.status_code == 201
        server_id = create_response.json()["id"]

        sync_response = await api_client.post(f"/mcp/servers/{server_id}/sync", headers=auth_headers)
        assert sync_response.status_code == 200
        sync_payload = sync_response.json()
        assert sync_payload["synced_count"] == 1
        assert sync_payload["disabled_count"] == 0
        assert sync_payload["discovered_tool_names"][0].startswith("mcp__")

        tools_response = await api_client.get("/tools", headers=auth_headers)
        assert tools_response.status_code == 200
        tools_payload = tools_response.json()
        assert tools_payload["total"] == 1
        assert tools_payload["items"][0]["tool_definition"]["source_type"] == ToolSourceType.MCP.value
        assert tools_payload["items"][0]["tool_definition"]["metadata_json"]["remote_tool_name"] == "knowledge_lookup"

    @pytest.mark.asyncio
    async def test_remote_mcp_tool_executes_through_worker(
        self,
        api_client: AsyncClient,
        auth_headers: dict[str, str],
        fake_mcp_client: FakeMCPOutboundClient,
        db_session: AsyncSession,
        db_engine,
        test_tenant,
        test_user,
    ):
        create_response = await api_client.post(
            "/mcp/servers",
            headers=auth_headers,
            json={
                "name": "Execution MCP",
                "base_url": "https://mcp.example.test",
                "scope_filter": ["knowledge"],
            },
        )
        server_id = create_response.json()["id"]
        sync_response = await api_client.post(f"/mcp/servers/{server_id}/sync", headers=auth_headers)
        tool_name = sync_response.json()["discovered_tool_names"][0]

        run_id = await _create_and_execute_remote_tool_run(
            db_session,
            db_engine,
            test_tenant.id,
            test_user.id,
            tool_name=tool_name,
        )

        tool_call_result = await db_session.execute(select(ToolCall).where(ToolCall.run_id == uuid.UUID(run_id)))
        tool_call = tool_call_result.scalar_one()
        assert tool_call.tool_name == tool_name
        assert tool_call.status.value == "succeeded"
        assert tool_call.normalized_output["match_count"] == 1
        assert any(str(call["url"]).endswith("/tools/knowledge_lookup/invoke") for call in fake_mcp_client.calls)

    @pytest.mark.asyncio
    async def test_policy_gate_blocks_mcp_execution_until_approved(
        self,
        api_client: AsyncClient,
        auth_headers: dict[str, str],
        fake_mcp_client: FakeMCPOutboundClient,
        db_session: AsyncSession,
        db_engine,
        test_tenant,
        test_user,
    ):
        create_response = await api_client.post(
            "/mcp/servers",
            headers=auth_headers,
            json={
                "name": "Approval MCP",
                "base_url": "https://mcp.example.test",
                "scope_filter": ["knowledge"],
            },
        )
        server_id = create_response.json()["id"]
        sync_response = await api_client.post(f"/mcp/servers/{server_id}/sync", headers=auth_headers)
        tool_name = sync_response.json()["discovered_tool_names"][0]

        run_id = await _create_and_execute_remote_tool_run(
            db_session,
            db_engine,
            test_tenant.id,
            test_user.id,
            tool_name=tool_name,
            risk_class="D",
            required_role="owner",
        )

        tool_call_result = await db_session.execute(select(ToolCall).where(ToolCall.run_id == uuid.UUID(run_id)))
        assert tool_call_result.scalar_one_or_none() is None

        runs_response = await api_client.get(f"/workflows/runs/{run_id}", headers=auth_headers)
        assert runs_response.status_code == 200
        assert runs_response.json()["status"] == RunStatus.AWAITING_APPROVAL.value

    @pytest.mark.asyncio
    async def test_sync_disables_removed_tools(
        self,
        api_client: AsyncClient,
        auth_headers: dict[str, str],
        fake_mcp_client: FakeMCPOutboundClient,
    ):
        create_response = await api_client.post(
            "/mcp/servers",
            headers=auth_headers,
            json={
                "name": "Mutable MCP",
                "base_url": "https://mcp.example.test",
                "scope_filter": ["knowledge", "draft"],
            },
        )
        server_id = create_response.json()["id"]
        first_sync = await api_client.post(f"/mcp/servers/{server_id}/sync", headers=auth_headers)
        assert first_sync.status_code == 200
        assert first_sync.json()["synced_count"] == 2

        fake_mcp_client.exposed_tools = [fake_mcp_client.exposed_tools[0]]
        second_sync = await api_client.post(f"/mcp/servers/{server_id}/sync", headers=auth_headers)
        assert second_sync.status_code == 200
        assert second_sync.json()["disabled_count"] == 1

        tools_response = await api_client.get("/tools", headers=auth_headers)
        assert tools_response.status_code == 200
        assert tools_response.json()["total"] == 1

    @pytest.mark.asyncio
    async def test_secret_ref_env_resolution_and_masking(
        self,
        api_client: AsyncClient,
        auth_headers: dict[str, str],
        fake_mcp_client: FakeMCPOutboundClient,
        monkeypatch,
    ):
        # Set an environment variable for secret resolution
        monkeypatch.setenv("MCP_TEST_SECRET", "env-secret-value")
        # Create auth config with env: reference
        auth_response = await api_client.post(
            "/mcp/auth-configs",
            headers=auth_headers,
            json={
                "name": "env-secret",
                "auth_type": "bearer_token",
                "secret_ref": "env:MCP_TEST_SECRET",
            },
        )
        assert auth_response.status_code == 201
        auth_config = auth_response.json()
        # secret_ref should be masked/omitted in response
        assert "secret_ref" not in auth_config or not auth_config["secret_ref"]

        # Attach server using this auth config
        create_response = await api_client.post(
            "/mcp/servers",
            headers=auth_headers,
            json={
                "name": "Env Secret MCP",
                "base_url": "https://mcp.example.test",
                "auth_config_id": auth_config["id"],
                "scope_filter": ["knowledge"],
                "timeout_seconds": 10,
                "max_retries": 1,
            },
        )
        assert create_response.status_code == 201
        server_id = create_response.json()["id"]

        # Health check should use resolved secret
        health_response = await api_client.post(f"/mcp/servers/{server_id}/health-check", headers=auth_headers)
        assert health_response.status_code == 200
        assert fake_mcp_client.calls[-1]["headers"]["Authorization"] == "Bearer env-secret-value"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "bad_secret",
        ["", "   ", "changeme", "secret", "test", "demo", "password", "123456", "env:", "env:   "]
    )
    async def test_secret_ref_validation_blocks_unsafe(
        self,
        api_client: AsyncClient,
        auth_headers: dict[str, str],
        bad_secret: str,
    ):
        resp = await api_client.post(
            "/mcp/auth-configs",
            headers=auth_headers,
            json={
                "name": "bad-secret",
                "auth_type": "bearer_token",
                "secret_ref": bad_secret,
            },
        )
        assert resp.status_code == 422
        assert "secret_ref" in resp.text or "env:" in resp.text
