"""Tests for Section 3: Agent router and planning contract."""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.db.models import Tenant, User
from app.db.planner_models import (
    AgentRequest,
    PlannerFailureCategory,
    PlannerStrategy,
    PlanRecord,
    PlanStatus,
    WorkflowType,
)
from app.services.planner import LLMBackend, LLMResponse, PlannerService, _deterministic_classify
from app.schemas.planner import PlannedStep, PlannerOutput


def _auth_headers(user_id: uuid.UUID, tenant_id: uuid.UUID) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {create_access_token(subject=str(user_id), tenant_id=str(tenant_id))}"
    }


# =====================
# Deterministic classifier unit tests
# =====================


def test_deterministic_classify_information_request():
    result = _deterministic_classify("Find the latest sales figures")
    assert result is not None
    assert result.workflow_type == WorkflowType.INFORMATION_REQUEST
    assert result.confidence > 0


def test_deterministic_classify_draft_action():
    result = _deterministic_classify("Draft an email to the finance team about Q3 results")
    assert result is not None
    assert result.workflow_type == WorkflowType.DRAFT_ACTION
    assert len(result.steps) >= 1


def test_deterministic_classify_executable_tool():
    result = _deterministic_classify("Run the monthly analytics report for October")
    assert result is not None
    assert result.workflow_type == WorkflowType.EXECUTABLE_TOOL


def test_deterministic_classify_no_match():
    result = _deterministic_classify("The sky is blue and the grass is green")
    assert result is None


def test_deterministic_priority_executable_over_information():
    # "execute" appears in the request alongside "search" — should hit executable first
    result = _deterministic_classify("execute a search query for this week's numbers")
    assert result is not None
    assert result.workflow_type == WorkflowType.EXECUTABLE_TOOL


# =====================
# PlannerService unit tests (with DB)
# =====================


@pytest.mark.asyncio
async def test_create_request_stores_in_db(db_session: AsyncSession, test_tenant: Tenant, test_user: User):
    svc = PlannerService(db_session)
    req = await svc.create_request(
        tenant_id=test_tenant.id,
        user_id=test_user.id,
        body="Find the top customers by revenue",
        context={"region": "US"},
        idempotency_key="test-key-001",
    )
    assert req.id is not None
    assert req.body == "Find the top customers by revenue"
    assert req.context == {"region": "US"}


@pytest.mark.asyncio
async def test_create_request_idempotent(db_session: AsyncSession, test_tenant: Tenant, test_user: User):
    svc = PlannerService(db_session)
    key = "idempotency-test-002"
    first = await svc.create_request(
        tenant_id=test_tenant.id,
        user_id=test_user.id,
        body="Find duplicates",
        context={},
        idempotency_key=key,
    )
    second = await svc.create_request(
        tenant_id=test_tenant.id,
        user_id=test_user.id,
        body="Find duplicates",
        context={},
        idempotency_key=key,
    )
    assert first.id == second.id


@pytest.mark.asyncio
async def test_plan_and_route_deterministic(db_session: AsyncSession, test_tenant: Tenant, test_user: User):
    svc = PlannerService(db_session)
    req = await svc.create_request(
        tenant_id=test_tenant.id,
        user_id=test_user.id,
        body="Search for open support tickets",
        context={},
        idempotency_key="plan-test-003",
    )
    plan = await svc.plan_and_route(req)
    await db_session.commit()

    assert plan.status == PlanStatus.ROUTED
    assert plan.strategy == PlannerStrategy.DETERMINISTIC
    assert plan.workflow_type == WorkflowType.INFORMATION_REQUEST
    assert plan.failure_category == PlannerFailureCategory.NONE
    assert plan.run_id is not None
    assert plan.selected_workflow_definition_id is not None
    assert len(plan.planned_steps) >= 1


@pytest.mark.asyncio
async def test_plan_and_route_llm_fallback(db_session: AsyncSession, test_tenant: Tenant, test_user: User):
    """When deterministic routing has no match, the LLM stub should produce a plan."""
    svc = PlannerService(db_session)
    req = await svc.create_request(
        tenant_id=test_tenant.id,
        user_id=test_user.id,
        body="Help me with my project",
        context={},
        idempotency_key="plan-test-004",
    )
    plan = await svc.plan_and_route(req)
    await db_session.commit()

    # The LLM stub returns a valid plan so it should succeed
    assert plan.status == PlanStatus.ROUTED
    assert plan.strategy == PlannerStrategy.LLM
    assert plan.run_id is not None


@pytest.mark.asyncio
async def test_plan_failure_unparseable_output(
    db_session: AsyncSession, test_tenant: Tenant, test_user: User
):
    """An LLM backend that returns garbage triggers UNPARSEABLE_OUTPUT."""

    class BrokenLLM(LLMBackend):
        async def complete(self, system, user) -> LLMResponse:
            return LLMResponse(text="not json at all $$$$", latency_ms=5)

    svc = PlannerService(db_session, llm=BrokenLLM())
    req = await svc.create_request(
        tenant_id=test_tenant.id,
        user_id=test_user.id,
        body="The grass is green and trees are tall",  # no keyword match
        context={},
        idempotency_key="plan-test-005",
    )
    plan = await svc.plan_and_route(req)
    await db_session.commit()

    assert plan.status == PlanStatus.FAILED
    assert plan.failure_category == PlannerFailureCategory.UNPARSEABLE_OUTPUT


@pytest.mark.asyncio
async def test_plan_failure_llm_timeout(
    db_session: AsyncSession, test_tenant: Tenant, test_user: User
):
    """An LLM backend that raises an exception triggers LLM_TIMEOUT."""

    class TimingOutLLM(LLMBackend):
        async def complete(self, system, user) -> LLMResponse:
            raise TimeoutError("connection timed out")

    svc = PlannerService(db_session, llm=TimingOutLLM())
    req = await svc.create_request(
        tenant_id=test_tenant.id,
        user_id=test_user.id,
        body="Quarterly review data points",  # no keyword match
        context={},
        idempotency_key="plan-test-006",
    )
    plan = await svc.plan_and_route(req)
    await db_session.commit()

    assert plan.status == PlanStatus.FAILED
    assert plan.failure_category == PlannerFailureCategory.LLM_TIMEOUT


@pytest.mark.asyncio
async def test_get_request_with_plan(db_session: AsyncSession, test_tenant: Tenant, test_user: User):
    svc = PlannerService(db_session)
    req = await svc.create_request(
        tenant_id=test_tenant.id,
        user_id=test_user.id,
        body="Look up employee data",
        context={},
        idempotency_key="plan-test-007",
    )
    await svc.plan_and_route(req)
    await db_session.commit()

    loaded = await svc.get_request_with_plan(req.id)
    assert loaded is not None
    assert loaded.plan is not None
    assert loaded.plan.agent_request_id == req.id


# =====================
# API endpoint tests
# =====================


@pytest.mark.asyncio
async def test_intake_endpoint_creates_plan(
    api_client: AsyncClient, test_tenant: Tenant, test_user: User
):
    headers = _auth_headers(test_user.id, test_tenant.id)
    resp = await api_client.post(
        "/agent/intake",
        json={
            "body": "Find all overdue invoices for this quarter",
            "context": {"region": "APAC"},
            "idempotency_key": "api-test-001",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["body"] == "Find all overdue invoices for this quarter"
    assert data["plan"] is not None
    assert data["plan"]["status"] in ("routed", "failed")
    assert data["plan"]["workflow_type"] == "information_request"


@pytest.mark.asyncio
async def test_intake_endpoint_idempotent(
    api_client: AsyncClient, test_tenant: Tenant, test_user: User
):
    headers = _auth_headers(test_user.id, test_tenant.id)
    body = {
        "body": "Summarize the weekly team report",
        "context": {},
        "idempotency_key": "api-test-002",
    }
    r1 = await api_client.post("/agent/intake", json=body, headers=headers)
    r2 = await api_client.post("/agent/intake", json=body, headers=headers)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]


@pytest.mark.asyncio
async def test_intake_rejects_empty_body(
    api_client: AsyncClient, test_tenant: Tenant, test_user: User
):
    headers = _auth_headers(test_user.id, test_tenant.id)
    resp = await api_client.post(
        "/agent/intake",
        json={"body": "", "context": {}, "idempotency_key": "api-test-003"},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_plans_empty(
    api_client: AsyncClient, test_tenant: Tenant, test_user: User
):
    headers = _auth_headers(test_user.id, test_tenant.id)
    resp = await api_client.get("/agent/plans", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_plans_after_intake(
    api_client: AsyncClient, test_tenant: Tenant, test_user: User
):
    headers = _auth_headers(test_user.id, test_tenant.id)
    await api_client.post(
        "/agent/intake",
        json={"body": "Run a performance report", "context": {}, "idempotency_key": "list-test-001"},
        headers=headers,
    )
    resp = await api_client.get("/agent/plans", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_get_plan_by_id(
    api_client: AsyncClient, test_tenant: Tenant, test_user: User
):
    headers = _auth_headers(test_user.id, test_tenant.id)
    intake = await api_client.post(
        "/agent/intake",
        json={"body": "Execute the monthly billing job", "context": {}, "idempotency_key": "get-plan-001"},
        headers=headers,
    )
    plan_id = intake.json()["plan"]["id"]
    resp = await api_client.get(f"/agent/plans/{plan_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == plan_id


@pytest.mark.asyncio
async def test_get_plan_not_found(
    api_client: AsyncClient, test_tenant: Tenant, test_user: User
):
    headers = _auth_headers(test_user.id, test_tenant.id)
    resp = await api_client.get(f"/agent/plans/{uuid.uuid4()}", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_request_by_id(
    api_client: AsyncClient, test_tenant: Tenant, test_user: User
):
    headers = _auth_headers(test_user.id, test_tenant.id)
    intake = await api_client.post(
        "/agent/intake",
        json={"body": "Write a summary of last month's performance", "context": {}, "idempotency_key": "req-detail-001"},
        headers=headers,
    )
    request_id = intake.json()["id"]
    resp = await api_client.get(f"/agent/requests/{request_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == request_id
    assert data["plan"] is not None


@pytest.mark.asyncio
async def test_requires_auth(api_client: AsyncClient):
    resp = await api_client.post(
        "/agent/intake",
        json={"body": "Find something", "context": {}, "idempotency_key": "auth-test"},
    )
    assert resp.status_code == 401
