import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.security import create_access_token, hash_password
from app.db.models import Membership, Tenant, User
from app.db.tool_models import ToolCall
from app.db.workflow_models import WorkflowDefinition, WorkflowStepDefinition
from app.services.state_machine import RunStateMachine
from app.worker.runner import WorkflowWorker


async def _create_and_execute_tool_run(
    db_session: AsyncSession,
    db_engine,
    tenant: Tenant,
    user: User,
    *,
    tool_name: str,
    tool_input: dict,
) -> str:
    definition = WorkflowDefinition(
        tenant_id=tenant.id,
        name=f"{tool_name}-api-workflow",
        description="api test workflow",
        version=1,
        is_active=True,
        created_by_user_id=user.id,
    )
    db_session.add(definition)
    await db_session.flush()

    db_session.add(
        WorkflowStepDefinition(
            workflow_definition_id=definition.id,
            name=f"Run {tool_name}",
            step_type=tool_name,
            order=0,
            config={"tool_name": tool_name, "input": tool_input},
            max_retries=1,
        )
    )
    await db_session.commit()

    state_machine = RunStateMachine(db_session)
    run = await state_machine.create_run(
        workflow_definition_id=definition.id,
        tenant_id=tenant.id,
        idempotency_key=f"api-{tool_name}-run",
        triggered_by_user_id=user.id,
    )
    run = await state_machine.start_run(run, "api-test-worker")
    await db_session.commit()

    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    worker = WorkflowWorker(session_factory=session_factory, poll_interval=0.01)
    await worker._execute_run(db_session, run)
    return str(run.id)


class TestToolsApi:
    @pytest.mark.asyncio
    async def test_register_and_list_tools_endpoints(
        self,
        api_client: AsyncClient,
        auth_headers: dict[str, str],
    ):
        register_response = await api_client.post(
            "/tools/registrations",
            headers=auth_headers,
            json={
                "tool_name": "knowledge_search",
                "override_timeout_seconds": 22,
                "override_max_retries": 2,
                "metadata_json": {"owner": "routing"},
            },
        )

        assert register_response.status_code == 201
        registration = register_response.json()
        assert registration["tool_definition"]["name"] == "knowledge_search"
        assert registration["tool_definition"]["metadata_json"]["normalized_output_schema"] == "KnowledgeSearchNormalizedOutput"
        assert registration["override_timeout_seconds"] == 22

        list_response = await api_client.get("/tools", headers=auth_headers)

        assert list_response.status_code == 200
        payload = list_response.json()
        assert payload["total"] == 1
        assert payload["items"][0]["tool_definition"]["name"] == "knowledge_search"

    @pytest.mark.asyncio
    async def test_workflow_definition_rejects_unregistered_tool(
        self,
        api_client: AsyncClient,
        auth_headers: dict[str, str],
    ):
        response = await api_client.post(
            "/workflows/definitions",
            headers=auth_headers,
            json={
                "name": "Unregistered Tool Workflow",
                "description": "should be rejected",
                "steps": [
                    {
                        "name": "Lookup knowledge",
                        "step_type": "knowledge_search",
                        "config": {
                            "input": {
                                "query": "returns policy",
                                "knowledge_items": [],
                            }
                        },
                    }
                ],
            },
        )

        assert response.status_code == 400
        assert "not registered for this tenant" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_workflow_definition_allows_registered_tool_reference(
        self,
        api_client: AsyncClient,
        auth_headers: dict[str, str],
    ):
        register_response = await api_client.post(
            "/tools/registrations",
            headers=auth_headers,
            json={"tool_name": "document_fetch"},
        )
        assert register_response.status_code == 201

        response = await api_client.post(
            "/workflows/definitions",
            headers=auth_headers,
            json={
                "name": "Document Tool Workflow",
                "description": "registered tool should be allowed",
                "steps": [
                    {
                        "name": "Fetch document",
                        "step_type": "tool",
                        "config": {
                            "tool_name": "document_fetch",
                            "input": {
                                "document_slug": "terms",
                                "documents": [
                                    {
                                        "id": "doc-1",
                                        "slug": "terms",
                                        "title": "Terms",
                                        "summary": "Terms summary",
                                        "metadata": {"source": "kb"},
                                    }
                                ],
                            },
                        },
                    }
                ],
            },
        )

        assert response.status_code == 201
        payload = response.json()
        assert payload["steps"][0]["step_type"] == "tool"
        assert payload["steps"][0]["config"]["tool_name"] == "document_fetch"

    @pytest.mark.asyncio
    async def test_list_tool_calls_endpoint(
        self,
        api_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        db_engine,
        test_tenant: Tenant,
        test_user: User,
    ):
        register_response = await api_client.post(
            "/tools/registrations",
            headers=auth_headers,
            json={"tool_name": "knowledge_search"},
        )
        assert register_response.status_code == 201

        run_id = await _create_and_execute_tool_run(
            db_session,
            db_engine,
            test_tenant,
            test_user,
            tool_name="knowledge_search",
            tool_input={
                "query": "shipping policy",
                "knowledge_items": [
                    {"id": "doc-1", "title": "Shipping Policy", "text": "shipping policy details"},
                ],
            },
        )

        response = await api_client.get("/tools/calls", headers=auth_headers)

        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 1
        assert payload["items"][0]["run_id"] == run_id
        assert payload["items"][0]["tool_name"] == "knowledge_search"
        assert payload["items"][0]["status"] == "succeeded"
        assert payload["items"][0]["normalized_output"]["match_count"] == 1

    @pytest.mark.asyncio
    async def test_get_tool_call_endpoint(
        self,
        api_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        db_engine,
        test_tenant: Tenant,
        test_user: User,
    ):
        register_response = await api_client.post(
            "/tools/registrations",
            headers=auth_headers,
            json={"tool_name": "knowledge_search"},
        )
        assert register_response.status_code == 201

        await _create_and_execute_tool_run(
            db_session,
            db_engine,
            test_tenant,
            test_user,
            tool_name="knowledge_search",
            tool_input={
                "query": "shipping policy",
                "knowledge_items": [
                    {"id": "doc-1", "title": "Shipping Policy", "text": "shipping policy details"},
                ],
            },
        )

        tool_call_result = await db_session.execute(select(ToolCall))
        tool_call = tool_call_result.scalar_one()

        response = await api_client.get(f"/tools/calls/{tool_call.id}", headers=auth_headers)

        assert response.status_code == 200
        payload = response.json()
        assert payload["id"] == str(tool_call.id)
        assert payload["tool_name"] == "knowledge_search"
        assert payload["status"] == "succeeded"
        assert payload["normalized_output"]["query"] == "shipping policy"

    @pytest.mark.asyncio
    async def test_get_tool_call_endpoint_is_tenant_scoped(
        self,
        api_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        db_engine,
        test_tenant: Tenant,
        test_user: User,
    ):
        register_response = await api_client.post(
            "/tools/registrations",
            headers=auth_headers,
            json={"tool_name": "knowledge_search"},
        )
        assert register_response.status_code == 201

        await _create_and_execute_tool_run(
            db_session,
            db_engine,
            test_tenant,
            test_user,
            tool_name="knowledge_search",
            tool_input={
                "query": "shipping policy",
                "knowledge_items": [
                    {"id": "doc-1", "title": "Shipping Policy", "text": "shipping policy details"},
                ],
            },
        )

        tool_call_result = await db_session.execute(select(ToolCall))
        tool_call = tool_call_result.scalar_one()

        other_tenant = Tenant(
            id=uuid.uuid4(),
            name="Other Tenant",
            slug="other-tenant",
        )
        other_user = User(
            id=uuid.uuid4(),
            email="other@example.com",
            full_name="Other User",
            hashed_password=hash_password("password123"),
            is_active=True,
        )
        db_session.add(other_tenant)
        db_session.add(other_user)
        await db_session.flush()
        db_session.add(
            Membership(
                id=uuid.uuid4(),
                tenant_id=other_tenant.id,
                user_id=other_user.id,
                role="admin",
            )
        )
        await db_session.commit()

        other_headers = {
            "Authorization": f"Bearer {create_access_token(subject=str(other_user.id), tenant_id=str(other_tenant.id))}"
        }

        response = await api_client.get(f"/tools/calls/{tool_call.id}", headers=other_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Tool call not found"

    @pytest.mark.asyncio
    async def test_list_run_tool_calls_endpoint(
        self,
        api_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        db_engine,
        test_tenant: Tenant,
        test_user: User,
    ):
        register_response = await api_client.post(
            "/tools/registrations",
            headers=auth_headers,
            json={"tool_name": "document_fetch"},
        )
        assert register_response.status_code == 201

        run_id = await _create_and_execute_tool_run(
            db_session,
            db_engine,
            test_tenant,
            test_user,
            tool_name="document_fetch",
            tool_input={
                "document_slug": "terms",
                "documents": [
                    {"id": "doc-1", "slug": "terms", "title": "Terms", "summary": "Terms summary"},
                ],
            },
        )

        response = await api_client.get(f"/tools/runs/{run_id}/calls", headers=auth_headers)

        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 1
        assert payload["items"][0]["run_id"] == run_id
        assert payload["items"][0]["tool_name"] == "document_fetch"
        assert payload["items"][0]["normalized_output"]["document"]["slug"] == "terms"

    @pytest.mark.asyncio
    async def test_workflow_run_detail_includes_tool_call_summaries(
        self,
        api_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        db_engine,
        test_tenant: Tenant,
        test_user: User,
    ):
        register_response = await api_client.post(
            "/tools/registrations",
            headers=auth_headers,
            json={"tool_name": "knowledge_search"},
        )
        assert register_response.status_code == 201

        run_id = await _create_and_execute_tool_run(
            db_session,
            db_engine,
            test_tenant,
            test_user,
            tool_name="knowledge_search",
            tool_input={
                "query": "shipping policy",
                "knowledge_items": [
                    {"id": "doc-1", "title": "Shipping Policy", "text": "shipping policy details"},
                ],
            },
        )

        response = await api_client.get(f"/workflows/runs/{run_id}", headers=auth_headers)

        assert response.status_code == 200
        payload = response.json()
        assert payload["id"] == run_id
        assert len(payload["tool_calls"]) == 1
        assert payload["tool_calls"][0]["tool_name"] == "knowledge_search"
        assert payload["tool_calls"][0]["status"] == "succeeded"