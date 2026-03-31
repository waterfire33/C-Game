"""Workflow API routes."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentMembership, CurrentTenantId, CurrentUserId
from app.db.models import Membership
from app.db.session import get_db_session
from app.db.tool_models import ToolCall
from app.db.workflow_models import (
    ApprovalRequestRecord,
    ApprovalRequestStatus,
    ActionRiskClass,
    RunStatus,
    WorkflowDefinition,
    WorkflowEvent,
    WorkflowRun,
    WorkflowStepDefinition,
)
from app.schemas.workflows import (
    ApprovalDecisionRequest,
    ApprovalRequestList,
    ApprovalRequestResponse,
    ApprovalDenyRequest,
    ApprovalRequest,
    EventResponse,
    RunCreate,
    RunList,
    RunResponse,
    TimelineResponse,
    WorkflowDefinitionCreate,
    WorkflowDefinitionList,
    WorkflowDefinitionResponse,
)
from app.services.approval_policy import get_step_approval_policy, role_satisfies_requirement
from app.services.event_logger import get_run_events
from app.services.state_machine import (
    InvalidTransitionError,
    RunNotFoundError,
    RunStateMachine,
    WorkflowNotFoundError,
)
from app.services.tool_adapter import ToolExecutionError, ToolRegistryService

router = APIRouter()


def _resolve_step_approval_fields(step) -> tuple[ActionRiskClass, str | None, bool]:
    policy = get_step_approval_policy(step)
    return policy.risk_class, policy.required_role, policy.requires_approval


def _raise_if_role_insufficient(membership: Membership, approval_request: ApprovalRequestRecord) -> None:
    if not role_satisfies_requirement(membership.role, approval_request.required_role):
        raise HTTPException(
            status_code=403,
            detail=(
                f"Approval requires role {approval_request.required_role}; current role is {membership.role}"
            ),
        )


# =====================
# Workflow Definition Endpoints
# =====================


@router.post("/definitions", response_model=WorkflowDefinitionResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow_definition(
    payload: WorkflowDefinitionCreate,
    tenant_id: CurrentTenantId,
    user_id: CurrentUserId,
    db: AsyncSession = Depends(get_db_session),
) -> WorkflowDefinition:
    """Create a new workflow definition."""
    tool_registry = ToolRegistryService(db)
    try:
        await tool_registry.ensure_tool_steps_allowed(
            tenant_id,
            [
                {
                    "step_type": step.step_type,
                    "config": step.config,
                }
                for step in payload.steps
            ],
        )
    except ToolExecutionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Create the definition
    definition = WorkflowDefinition(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=payload.name,
        description=payload.description,
        version=1,
        is_active=True,
        created_by_user_id=user_id,
    )
    db.add(definition)
    await db.flush()

    # Create step definitions
    for order, step_data in enumerate(payload.steps):
        risk_class = step_data.action_risk_class
        if risk_class is None:
            risk_class = ActionRiskClass.C if step_data.requires_approval else ActionRiskClass.A

        normalized_requires_approval = step_data.requires_approval
        normalized_required_role = step_data.required_approver_role
        if risk_class == ActionRiskClass.A:
            normalized_requires_approval = False
            normalized_required_role = None
        elif risk_class in {ActionRiskClass.C, ActionRiskClass.D}:
            normalized_requires_approval = True

        step = WorkflowStepDefinition(
            id=uuid.uuid4(),
            workflow_definition_id=definition.id,
            name=step_data.name,
            step_type=step_data.step_type,
            order=order,
            config=step_data.config,
            requires_approval=normalized_requires_approval,
            action_risk_class=risk_class,
            required_approver_role=normalized_required_role,
            timeout_seconds=step_data.timeout_seconds,
            max_retries=step_data.max_retries,
        )
        db.add(step)

    await db.commit()

    # Reload with relationships
    result = await db.execute(
        select(WorkflowDefinition)
        .where(WorkflowDefinition.id == definition.id)
        .options(selectinload(WorkflowDefinition.steps))
    )
    return result.scalar_one()


@router.get("/definitions", response_model=WorkflowDefinitionList)
async def list_workflow_definitions(
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> WorkflowDefinitionList:
    """List workflow definitions for the current tenant."""
    # Count total
    count_result = await db.execute(
        select(func.count(WorkflowDefinition.id)).where(
            WorkflowDefinition.tenant_id == tenant_id
        )
    )
    total = count_result.scalar_one()

    # Get definitions
    result = await db.execute(
        select(WorkflowDefinition)
        .where(WorkflowDefinition.tenant_id == tenant_id)
        .options(selectinload(WorkflowDefinition.steps))
        .order_by(WorkflowDefinition.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    definitions = result.scalars().all()

    return WorkflowDefinitionList(items=list(definitions), total=total)


@router.get("/definitions/{definition_id}", response_model=WorkflowDefinitionResponse)
async def get_workflow_definition(
    definition_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db_session),
) -> WorkflowDefinition:
    """Get a workflow definition by ID."""
    result = await db.execute(
        select(WorkflowDefinition)
        .where(
            WorkflowDefinition.id == definition_id,
            WorkflowDefinition.tenant_id == tenant_id,
        )
        .options(selectinload(WorkflowDefinition.steps))
    )
    definition = result.scalar_one_or_none()

    if definition is None:
        raise HTTPException(status_code=404, detail="Workflow definition not found")

    return definition


# =====================
# Workflow Run Endpoints
# =====================


@router.post("/runs", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
async def create_run(
    payload: RunCreate,
    tenant_id: CurrentTenantId,
    user_id: CurrentUserId,
    db: AsyncSession = Depends(get_db_session),
) -> WorkflowRun:
    """
    Create a new workflow run.
    
    Idempotent: if a run with the same idempotency_key exists, returns it.
    """
    state_machine = RunStateMachine(db)

    try:
        run = await state_machine.create_run(
            workflow_definition_id=payload.workflow_definition_id,
            tenant_id=tenant_id,
            idempotency_key=payload.idempotency_key,
            input_data=payload.input_data,
            triggered_by_user_id=user_id,
        )
        await db.commit()

        # Reload with relationships
        return await state_machine.get_run(run.id)

    except WorkflowNotFoundError:
        raise HTTPException(status_code=404, detail="Workflow definition not found")


@router.get("/runs", response_model=RunList)
async def list_runs(
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db_session),
    workflow_definition_id: uuid.UUID | None = None,
    status: RunStatus | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> RunList:
    """List workflow runs for the current tenant with optional filters."""
    # Build query
    query = select(WorkflowRun).where(WorkflowRun.tenant_id == tenant_id)

    if workflow_definition_id is not None:
        query = query.where(WorkflowRun.workflow_definition_id == workflow_definition_id)
    if status is not None:
        query = query.where(WorkflowRun.status == status)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    # Get runs
    result = await db.execute(
        query.options(selectinload(WorkflowRun.steps))
        .options(selectinload(WorkflowRun.tool_calls))
        .options(selectinload(WorkflowRun.approval_requests))
        .order_by(WorkflowRun.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    runs = result.scalars().all()

    return RunList(items=list(runs), total=total)


@router.get("/runs/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db_session),
) -> WorkflowRun:
    """Get a workflow run by ID with full details."""
    state_machine = RunStateMachine(db)

    try:
        run = await state_machine.get_run(run_id)
    except RunNotFoundError:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Run not found")

    tool_calls_result = await db.execute(
        select(ToolCall)
        .where(
            ToolCall.tenant_id == tenant_id,
            ToolCall.run_id == run.id,
        )
        .order_by(ToolCall.started_at.desc())
    )
    run.tool_calls = list(tool_calls_result.scalars().all())

    approval_requests_result = await db.execute(
        select(ApprovalRequestRecord)
        .where(
            ApprovalRequestRecord.tenant_id == tenant_id,
            ApprovalRequestRecord.run_id == run.id,
        )
        .order_by(ApprovalRequestRecord.requested_at.desc())
    )
    run.approval_requests = list(approval_requests_result.scalars().all())

    return run


@router.get("/runs/{run_id}/timeline", response_model=TimelineResponse)
async def get_run_timeline(
    run_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db_session),
) -> TimelineResponse:
    """Get the event timeline for a workflow run."""
    # Verify run exists and belongs to tenant
    result = await db.execute(
        select(WorkflowRun).where(
            WorkflowRun.id == run_id,
            WorkflowRun.tenant_id == tenant_id,
        )
    )
    run = result.scalar_one_or_none()

    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    # Get all events for the run
    events = await get_run_events(db, run_id)

    return TimelineResponse(run_id=run_id, events=events)


# =====================
# Run Actions
# =====================


@router.post("/runs/{run_id}/approve", response_model=RunResponse)
async def approve_step(
    run_id: uuid.UUID,
    payload: ApprovalRequest,
    tenant_id: CurrentTenantId,
    user_id: CurrentUserId,
    membership: CurrentMembership,
    db: AsyncSession = Depends(get_db_session),
) -> WorkflowRun:
    """Approve a step that is awaiting approval."""
    state_machine = RunStateMachine(db)

    try:
        run = await state_machine.get_run(run_id)
    except RunNotFoundError:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.status != RunStatus.AWAITING_APPROVAL:
        raise HTTPException(
            status_code=400,
            detail=f"Run is not awaiting approval (status: {run.status.value})",
        )

    try:
        approval_request = await state_machine.get_pending_approval_request(
            run.id,
            step_index=payload.step_index,
        )
        if approval_request is None:
            raise HTTPException(status_code=404, detail="Pending approval request not found")

        _raise_if_role_insufficient(membership, approval_request)
        run = await state_machine.grant_approval(
            run,
            payload.step_index,
            user_id,
            payload.reason,
            approval_request,
        )
        await db.commit()
        return await state_machine.get_run(run.id)
    except InvalidTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/runs/{run_id}/deny", response_model=RunResponse)
async def deny_step(
    run_id: uuid.UUID,
    payload: ApprovalDenyRequest,
    tenant_id: CurrentTenantId,
    user_id: CurrentUserId,
    membership: CurrentMembership,
    db: AsyncSession = Depends(get_db_session),
) -> WorkflowRun:
    """Deny approval for a step, cancelling the run."""
    state_machine = RunStateMachine(db)

    try:
        run = await state_machine.get_run(run_id)
    except RunNotFoundError:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.status != RunStatus.AWAITING_APPROVAL:
        raise HTTPException(
            status_code=400,
            detail=f"Run is not awaiting approval (status: {run.status.value})",
        )

    try:
        approval_request = await state_machine.get_pending_approval_request(
            run.id,
            step_index=payload.step_index,
        )
        if approval_request is None:
            raise HTTPException(status_code=404, detail="Pending approval request not found")

        _raise_if_role_insufficient(membership, approval_request)
        run = await state_machine.deny_approval(
            run,
            payload.step_index,
            user_id,
            payload.reason,
            approval_request,
        )
        await db.commit()
        return await state_machine.get_run(run.id)
    except InvalidTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/approvals", response_model=ApprovalRequestList)
async def list_approval_requests(
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db_session),
    run_id: uuid.UUID | None = None,
    status_filter: ApprovalRequestStatus | None = Query(default=ApprovalRequestStatus.PENDING, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> ApprovalRequestList:
    query = select(ApprovalRequestRecord).where(ApprovalRequestRecord.tenant_id == tenant_id)
    if run_id is not None:
        query = query.where(ApprovalRequestRecord.run_id == run_id)
    if status_filter is not None:
        query = query.where(ApprovalRequestRecord.status == status_filter)

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar_one()
    result = await db.execute(
        query.order_by(ApprovalRequestRecord.requested_at.desc()).offset(skip).limit(limit)
    )
    return ApprovalRequestList(items=list(result.scalars().all()), total=total)


@router.get("/approvals/{approval_request_id}", response_model=ApprovalRequestResponse)
async def get_approval_request(
    approval_request_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db_session),
) -> ApprovalRequestRecord:
    result = await db.execute(
        select(ApprovalRequestRecord).where(
            ApprovalRequestRecord.id == approval_request_id,
            ApprovalRequestRecord.tenant_id == tenant_id,
        )
    )
    approval_request = result.scalar_one_or_none()
    if approval_request is None:
        raise HTTPException(status_code=404, detail="Approval request not found")
    return approval_request


@router.post("/approvals/{approval_request_id}/approve", response_model=RunResponse)
async def approve_request(
    approval_request_id: uuid.UUID,
    payload: ApprovalDecisionRequest,
    tenant_id: CurrentTenantId,
    user_id: CurrentUserId,
    membership: CurrentMembership,
    db: AsyncSession = Depends(get_db_session),
) -> WorkflowRun:
    state_machine = RunStateMachine(db)
    approval_request = await get_approval_request(approval_request_id, tenant_id, db)
    if approval_request.status != ApprovalRequestStatus.PENDING:
        raise HTTPException(status_code=400, detail="Approval request is no longer pending")

    _raise_if_role_insufficient(membership, approval_request)

    run = await state_machine.get_run(approval_request.run_id)
    if run.status != RunStatus.AWAITING_APPROVAL:
        raise HTTPException(status_code=400, detail="Run is not awaiting approval")

    run = await state_machine.grant_approval(
        run,
        approval_request.step_index,
        user_id,
        payload.reason,
        approval_request,
    )
    await db.commit()
    return await state_machine.get_run(run.id)


@router.post("/approvals/{approval_request_id}/reject", response_model=RunResponse)
async def reject_request(
    approval_request_id: uuid.UUID,
    payload: ApprovalDecisionRequest,
    tenant_id: CurrentTenantId,
    user_id: CurrentUserId,
    membership: CurrentMembership,
    db: AsyncSession = Depends(get_db_session),
) -> WorkflowRun:
    state_machine = RunStateMachine(db)
    approval_request = await get_approval_request(approval_request_id, tenant_id, db)
    if approval_request.status != ApprovalRequestStatus.PENDING:
        raise HTTPException(status_code=400, detail="Approval request is no longer pending")

    _raise_if_role_insufficient(membership, approval_request)

    run = await state_machine.get_run(approval_request.run_id)
    if run.status != RunStatus.AWAITING_APPROVAL:
        raise HTTPException(status_code=400, detail="Run is not awaiting approval")

    run = await state_machine.deny_approval(
        run,
        approval_request.step_index,
        user_id,
        payload.reason,
        approval_request,
    )
    await db.commit()
    return await state_machine.get_run(run.id)


@router.post("/runs/{run_id}/cancel", response_model=RunResponse)
async def cancel_run(
    run_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    user_id: CurrentUserId,
    db: AsyncSession = Depends(get_db_session),
) -> WorkflowRun:
    """Cancel a workflow run."""
    state_machine = RunStateMachine(db)

    try:
        run = await state_machine.get_run(run_id)
    except RunNotFoundError:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Run not found")

    try:
        run = await state_machine.cancel_run(run, user_id)
        await db.commit()
        return run
    except InvalidTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/runs/{run_id}/retry", response_model=RunResponse)
async def retry_run(
    run_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    user_id: CurrentUserId,
    db: AsyncSession = Depends(get_db_session),
) -> WorkflowRun:
    """Retry a failed workflow run."""
    state_machine = RunStateMachine(db)

    try:
        run = await state_machine.get_run(run_id)
    except RunNotFoundError:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Run not found")

    try:
        run = await state_machine.retry_run(run, user_id)
        await db.commit()
        return run
    except InvalidTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
