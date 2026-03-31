import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.security import create_access_token, hash_password
from app.db.models import Membership, Tenant, User
from app.db.workflow_models import (
    ApprovalRequestRecord,
    ApprovalRequestStatus,
    RunStatus,
    StepStatus,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowStepDefinition,
)
from app.services.state_machine import RunStateMachine
from app.worker.runner import WorkflowWorker


def _auth_headers(user_id: uuid.UUID, tenant_id: uuid.UUID) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {create_access_token(subject=str(user_id), tenant_id=str(tenant_id))}"
    }


async def _create_user_with_role(
    db_session: AsyncSession,
    tenant: Tenant,
    *,
    email: str,
    role: str,
) -> User:
    user = User(
        id=uuid.uuid4(),
        email=email,
        full_name=email.split("@")[0].title(),
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        Membership(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            user_id=user.id,
            role=role,
        )
    )
    await db_session.commit()
    return user


async def _create_definition(
    db_session: AsyncSession,
    tenant: Tenant,
    user: User,
    *,
    risk_class: str = "C",
    required_role: str | None = None,
) -> WorkflowDefinition:
    definition = WorkflowDefinition(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name="Approval Workflow",
        description="approval test workflow",
        version=1,
        is_active=True,
        created_by_user_id=user.id,
    )
    db_session.add(definition)
    await db_session.flush()

    db_session.add(
        WorkflowStepDefinition(
            id=uuid.uuid4(),
            workflow_definition_id=definition.id,
            name="Sensitive Action",
            step_type="test_step",
            order=0,
            config={"side_effect": "send_email"},
            requires_approval=risk_class in {"B", "C", "D"},
            action_risk_class=risk_class,
            required_approver_role=required_role,
            max_retries=1,
        )
    )
    await db_session.commit()
    return definition


async def _create_running_run(
    db_session: AsyncSession,
    tenant: Tenant,
    definition: WorkflowDefinition,
    user: User,
    *,
    idempotency_key: str,
) -> WorkflowRun:
    state_machine = RunStateMachine(db_session)
    run = await state_machine.create_run(
        workflow_definition_id=definition.id,
        tenant_id=tenant.id,
        idempotency_key=idempotency_key,
        triggered_by_user_id=user.id,
    )
    run = await state_machine.start_run(run, "approval-test-worker")
    await db_session.commit()
    return run


class TestApprovalEngine:
    @pytest.mark.asyncio
    async def test_risky_step_creates_pending_approval_and_blocks_execution(
        self,
        db_session: AsyncSession,
        db_engine,
        test_tenant: Tenant,
        test_user: User,
    ):
        definition = await _create_definition(db_session, test_tenant, test_user)
        run = await _create_running_run(
            db_session,
            test_tenant,
            definition,
            test_user,
            idempotency_key="approval-block-test",
        )

        session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
        worker = WorkflowWorker(session_factory=session_factory, poll_interval=0.01)

        handler_calls: list[str] = []

        async def test_handler(step, state, session):
            handler_calls.append("called")
            return {"executed": True}

        worker.register_step_handler("test_step", test_handler)
        await worker._execute_run(db_session, run)

        refreshed_run = await RunStateMachine(db_session).get_run(run.id)
        assert refreshed_run.status == RunStatus.AWAITING_APPROVAL
        assert handler_calls == []
        assert refreshed_run.steps[0].status == StepStatus.AWAITING_APPROVAL
        assert len(refreshed_run.approval_requests) == 1
        assert refreshed_run.approval_requests[0].status == ApprovalRequestStatus.PENDING
        assert refreshed_run.approval_requests[0].action_risk_class.value == "C"

    @pytest.mark.asyncio
    async def test_approved_run_can_be_claimed_and_completed(
        self,
        db_session: AsyncSession,
        db_engine,
        test_tenant: Tenant,
        test_user: User,
    ):
        definition = await _create_definition(db_session, test_tenant, test_user)
        run = await _create_running_run(
            db_session,
            test_tenant,
            definition,
            test_user,
            idempotency_key="approval-resume-test",
        )

        session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
        worker = WorkflowWorker(session_factory=session_factory, poll_interval=0.01)

        async def test_handler(step, state, session):
            return {"executed": True}

        worker.register_step_handler("test_step", test_handler)

        await worker._execute_run(db_session, run)

        state_machine = RunStateMachine(db_session)
        paused_run = await state_machine.get_run(run.id)
        approval_request = paused_run.approval_requests[0]
        await state_machine.grant_approval(
            paused_run,
            approval_request.step_index,
            test_user.id,
            "looks good",
            approval_request,
        )
        await db_session.commit()

        claimed_run = await worker._claim_next_run(db_session)
        assert claimed_run is not None
        await worker._execute_run(db_session, claimed_run)

        completed_run = await state_machine.get_run(run.id)
        assert completed_run.status == RunStatus.COMPLETED
        assert completed_run.steps[0].status == StepStatus.COMPLETED
        assert completed_run.approval_requests[0].status == ApprovalRequestStatus.APPROVED


class TestApprovalApi:
    @pytest.mark.asyncio
    async def test_list_approvals_and_run_detail_include_pending_request(
        self,
        api_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        db_engine,
        test_tenant: Tenant,
        test_user: User,
    ):
        definition = await _create_definition(db_session, test_tenant, test_user)
        run = await _create_running_run(
            db_session,
            test_tenant,
            definition,
            test_user,
            idempotency_key="approval-api-list",
        )

        session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
        worker = WorkflowWorker(session_factory=session_factory, poll_interval=0.01)

        async def test_handler(step, state, session):
            return {"executed": True}

        worker.register_step_handler("test_step", test_handler)
        await worker._execute_run(db_session, run)

        approvals_response = await api_client.get("/workflows/approvals", headers=auth_headers)
        assert approvals_response.status_code == 200
        approvals_payload = approvals_response.json()
        assert approvals_payload["total"] == 1
        assert approvals_payload["items"][0]["status"] == "pending"

        run_response = await api_client.get(f"/workflows/runs/{run.id}", headers=auth_headers)
        assert run_response.status_code == 200
        run_payload = run_response.json()
        assert len(run_payload["approval_requests"]) == 1
        assert run_payload["approval_requests"][0]["status"] == "pending"
        assert run_payload["approval_requests"][0]["step_name"] == "Sensitive Action"

    @pytest.mark.asyncio
    async def test_class_d_approval_requires_owner_role(
        self,
        api_client: AsyncClient,
        db_session: AsyncSession,
        db_engine,
        test_tenant: Tenant,
    ):
        owner_user = await _create_user_with_role(
            db_session,
            test_tenant,
            email="owner-approval@example.com",
            role="owner",
        )
        member_user = await _create_user_with_role(
            db_session,
            test_tenant,
            email="member-approval@example.com",
            role="member",
        )
        definition = await _create_definition(
            db_session,
            test_tenant,
            owner_user,
            risk_class="D",
            required_role="owner",
        )
        run = await _create_running_run(
            db_session,
            test_tenant,
            definition,
            owner_user,
            idempotency_key="approval-owner-only",
        )

        session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
        worker = WorkflowWorker(session_factory=session_factory, poll_interval=0.01)

        async def test_handler(step, state, session):
            return {"executed": True}

        worker.register_step_handler("test_step", test_handler)
        await worker._execute_run(db_session, run)

        approval_result = await db_session.execute(
            select(ApprovalRequestRecord).where(ApprovalRequestRecord.run_id == run.id)
        )
        approval_request = approval_result.scalar_one()

        member_response = await api_client.post(
            f"/workflows/approvals/{approval_request.id}/approve",
            headers=_auth_headers(member_user.id, test_tenant.id),
            json={"reason": "member attempted approval"},
        )
        assert member_response.status_code == 403
        assert "requires role owner" in member_response.json()["detail"]

        owner_response = await api_client.post(
            f"/workflows/approvals/{approval_request.id}/approve",
            headers=_auth_headers(owner_user.id, test_tenant.id),
            json={"reason": "owner approved"},
        )
        assert owner_response.status_code == 200
        payload = owner_response.json()
        assert payload["status"] == "running"

        refreshed_approval = await db_session.get(ApprovalRequestRecord, approval_request.id)
        assert refreshed_approval is not None
        assert refreshed_approval.status == ApprovalRequestStatus.APPROVED