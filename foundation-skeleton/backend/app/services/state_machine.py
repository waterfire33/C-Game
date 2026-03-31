"""
Workflow state machine with explicit, validated transitions.

All state changes must go through this module to ensure:
1. Only valid transitions are allowed
2. Every transition is logged to the event log
3. Approval gates are enforced
"""
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Membership
from app.db.workflow_models import (
    ActionRiskClass,
    ApprovalRequestRecord,
    ApprovalRequestStatus,
    EventType,
    RunStatus,
    StepStatus,
    VALID_RUN_TRANSITIONS,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowRunStep,
    WorkflowStepDefinition,
)
from app.services.approval_policy import get_step_approval_policy
from app.services.event_logger import EventLogger


class InvalidTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""

    def __init__(self, current_status: RunStatus, target_status: RunStatus):
        self.current_status = current_status
        self.target_status = target_status
        super().__init__(
            f"Invalid transition from {current_status.value} to {target_status.value}"
        )


class RunNotFoundError(Exception):
    """Raised when a run cannot be found."""
    pass


class WorkflowNotFoundError(Exception):
    """Raised when a workflow definition cannot be found."""
    pass


class ApprovalRequiredError(Exception):
    """Raised when a step requires approval before continuing."""

    def __init__(self, run_id: uuid.UUID, step_index: int, step_name: str):
        self.run_id = run_id
        self.step_index = step_index
        self.step_name = step_name
        super().__init__(f"Step {step_index} ({step_name}) requires approval")


class RunStateMachine:
    """
    Manages workflow run state transitions with validation and logging.
    
    All transitions are:
    1. Validated against VALID_RUN_TRANSITIONS
    2. Logged to the append-only event log
    3. Atomic within the session transaction
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.event_logger = EventLogger(session)

    def _validate_transition(self, current: RunStatus, target: RunStatus) -> None:
        """Validate that a transition is allowed."""
        valid_targets = VALID_RUN_TRANSITIONS.get(current, set())
        if target not in valid_targets:
            raise InvalidTransitionError(current, target)

    async def get_run(self, run_id: uuid.UUID) -> WorkflowRun:
        """Get a run by ID with steps and definition loaded."""
        result = await self.session.execute(
            select(WorkflowRun)
            .where(WorkflowRun.id == run_id)
            .options(
                selectinload(WorkflowRun.steps),
                selectinload(WorkflowRun.tool_calls),
                selectinload(WorkflowRun.approval_requests),
                selectinload(WorkflowRun.workflow_definition).selectinload(
                    WorkflowDefinition.steps
                ),
            )
            .execution_options(populate_existing=True)
        )
        run = result.scalar_one_or_none()
        if run is None:
            raise RunNotFoundError(f"Run {run_id} not found")
        return run

    async def create_run(
        self,
        workflow_definition_id: uuid.UUID,
        tenant_id: uuid.UUID,
        idempotency_key: str,
        *,
        input_data: dict[str, Any] | None = None,
        triggered_by_user_id: uuid.UUID | None = None,
    ) -> WorkflowRun:
        """
        Create a new workflow run.
        
        Idempotency: If a run with the same idempotency_key exists, return it.
        """
        # Check for existing run with same idempotency key
        existing = await self.session.execute(
            select(WorkflowRun).where(WorkflowRun.idempotency_key == idempotency_key)
        )
        existing_run = existing.scalar_one_or_none()
        if existing_run is not None:
            return existing_run

        # Verify workflow exists
        workflow_result = await self.session.execute(
            select(WorkflowDefinition)
            .where(WorkflowDefinition.id == workflow_definition_id)
            .options(selectinload(WorkflowDefinition.steps))
        )
        workflow = workflow_result.scalar_one_or_none()
        if workflow is None:
            raise WorkflowNotFoundError(f"Workflow {workflow_definition_id} not found")

        # Create run
        run = WorkflowRun(
            id=uuid.uuid4(),
            workflow_definition_id=workflow_definition_id,
            tenant_id=tenant_id,
            idempotency_key=idempotency_key,
            status=RunStatus.PENDING,
            current_step_index=0,
            state={},
            input_data=input_data,
            triggered_by_user_id=triggered_by_user_id,
        )
        self.session.add(run)
        await self.session.flush()

        # Create run steps from definition
        for step_def in workflow.steps:
            step_idempotency_key = f"{idempotency_key}:step:{step_def.order}"
            run_step = WorkflowRunStep(
                id=uuid.uuid4(),
                run_id=run.id,
                step_definition_id=step_def.id,
                step_index=step_def.order,
                idempotency_key=step_idempotency_key,
                status=StepStatus.PENDING,
            )
            self.session.add(run_step)

        # Log creation event
        await self.event_logger.log_run_created(
            run.id,
            actor_user_id=triggered_by_user_id,
            payload={
                "workflow_definition_id": str(workflow_definition_id),
                "workflow_name": workflow.name,
                "input_data_keys": list(input_data.keys()) if input_data else [],
            },
        )

        return run

    async def transition_to(
        self,
        run: WorkflowRun,
        target_status: RunStatus,
        *,
        actor_user_id: uuid.UUID | None = None,
        error_message: str | None = None,
        error_details: dict[str, Any] | None = None,
        step_index: int | None = None,
    ) -> WorkflowRun:
        """
        Transition a run to a new status with validation and logging.
        
        Raises InvalidTransitionError if the transition is not allowed.
        """
        current_status = run.status
        self._validate_transition(current_status, target_status)

        # Perform the transition
        run.status = target_status
        now = datetime.now(timezone.utc)

        # Update timestamps based on status
        if target_status == RunStatus.RUNNING and run.started_at is None:
            run.started_at = now
        elif target_status in (RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED):
            run.completed_at = now

        # Store error info on failure
        if target_status == RunStatus.FAILED:
            run.error_message = error_message
            run.error_details = error_details

        # Log the appropriate event
        await self._log_transition_event(
            run,
            current_status,
            target_status,
            actor_user_id=actor_user_id,
            error_message=error_message,
            error_details=error_details,
            step_index=step_index,
        )

        return run

    async def _log_transition_event(
        self,
        run: WorkflowRun,
        previous_status: RunStatus,
        new_status: RunStatus,
        *,
        actor_user_id: uuid.UUID | None = None,
        error_message: str | None = None,
        error_details: dict[str, Any] | None = None,
        step_index: int | None = None,
    ) -> None:
        """Log the appropriate event for a status transition."""
        if new_status == RunStatus.RUNNING and previous_status == RunStatus.PENDING:
            await self.event_logger.log_run_started(run.id, previous_status)
        elif new_status == RunStatus.RUNNING and previous_status == RunStatus.PAUSED:
            await self.event_logger.log_run_resumed(run.id, previous_status, actor_user_id)
        elif new_status == RunStatus.RUNNING and previous_status == RunStatus.AWAITING_APPROVAL:
            await self.event_logger.log_approval_granted(run.id, step_index or run.current_step_index, actor_user_id)
        elif new_status == RunStatus.PAUSED:
            await self.event_logger.log_run_paused(run.id, previous_status)
        elif new_status == RunStatus.AWAITING_APPROVAL:
            await self.event_logger.log_approval_requested(run.id, step_index or run.current_step_index)
        elif new_status == RunStatus.COMPLETED:
            await self.event_logger.log_run_completed(run.id, previous_status, run.output_data)
        elif new_status == RunStatus.FAILED:
            await self.event_logger.log_run_failed(
                run.id, previous_status, error_message or "Unknown error", error_details, step_index
            )
        elif new_status == RunStatus.CANCELLED:
            await self.event_logger.log_run_cancelled(run.id, previous_status, actor_user_id)

    async def start_run(self, run: WorkflowRun, worker_id: str) -> WorkflowRun:
        """Start a pending run, claiming it for a worker."""
        run.claimed_by = worker_id
        run.claimed_at = datetime.now(timezone.utc)
        return await self.transition_to(run, RunStatus.RUNNING)

    async def pause_run(self, run: WorkflowRun) -> WorkflowRun:
        """Pause a running run."""
        return await self.transition_to(run, RunStatus.PAUSED)

    async def resume_run(
        self, run: WorkflowRun, actor_user_id: uuid.UUID | None = None
    ) -> WorkflowRun:
        """Resume a paused run."""
        return await self.transition_to(run, RunStatus.RUNNING, actor_user_id=actor_user_id)

    async def complete_run(self, run: WorkflowRun, output_data: dict[str, Any] | None = None) -> WorkflowRun:
        """Mark a run as completed."""
        run.output_data = output_data
        return await self.transition_to(run, RunStatus.COMPLETED)

    async def fail_run(
        self,
        run: WorkflowRun,
        error_message: str,
        error_details: dict[str, Any] | None = None,
        step_index: int | None = None,
    ) -> WorkflowRun:
        """Mark a run as failed with error information."""
        return await self.transition_to(
            run,
            RunStatus.FAILED,
            error_message=error_message,
            error_details=error_details,
            step_index=step_index,
        )

    async def cancel_run(self, run: WorkflowRun, actor_user_id: uuid.UUID | None = None) -> WorkflowRun:
        """Cancel a run."""
        return await self.transition_to(run, RunStatus.CANCELLED, actor_user_id=actor_user_id)

    async def request_approval(self, run: WorkflowRun, step_index: int) -> WorkflowRun:
        """Transition run to awaiting approval for a step."""
        run.claimed_by = None
        run.claimed_at = None
        return await self.transition_to(run, RunStatus.AWAITING_APPROVAL, step_index=step_index)

    async def ensure_approval_request(
        self,
        run: WorkflowRun,
        run_step: WorkflowRunStep,
        step_definition: WorkflowStepDefinition,
    ) -> ApprovalRequestRecord:
        """Create or reuse a pending approval request for a risky step."""
        existing_result = await self.session.execute(
            select(ApprovalRequestRecord)
            .where(
                ApprovalRequestRecord.run_step_id == run_step.id,
                ApprovalRequestRecord.status == ApprovalRequestStatus.PENDING,
            )
            .order_by(ApprovalRequestRecord.requested_at.desc())
            .limit(1)
        )
        existing_request = existing_result.scalar_one_or_none()
        if existing_request is not None:
            return existing_request

        policy = get_step_approval_policy(step_definition)
        approval_request = ApprovalRequestRecord(
            id=uuid.uuid4(),
            tenant_id=run.tenant_id,
            run_id=run.id,
            run_step_id=run_step.id,
            step_definition_id=step_definition.id,
            step_index=step_definition.order,
            step_name=step_definition.name,
            status=ApprovalRequestStatus.PENDING,
            action_risk_class=policy.risk_class,
            required_role=policy.required_role,
            requested_by_user_id=run.triggered_by_user_id,
            request_context={
                "step_type": step_definition.step_type,
                "config": step_definition.config,
            },
        )
        self.session.add(approval_request)
        await self.event_logger.log_approval_requested(
            run.id,
            step_definition.order,
            step_name=step_definition.name,
            payload={
                "approval_request_id": str(approval_request.id),
                "risk_class": policy.risk_class.value,
                "required_role": policy.required_role,
            },
        )
        return approval_request

    async def get_pending_approval_request(
        self,
        run_id: uuid.UUID,
        step_index: int | None = None,
        approval_request_id: uuid.UUID | None = None,
    ) -> ApprovalRequestRecord | None:
        query = select(ApprovalRequestRecord).where(
            ApprovalRequestRecord.run_id == run_id,
            ApprovalRequestRecord.status == ApprovalRequestStatus.PENDING,
        )
        if step_index is not None:
            query = query.where(ApprovalRequestRecord.step_index == step_index)
        if approval_request_id is not None:
            query = query.where(ApprovalRequestRecord.id == approval_request_id)

        result = await self.session.execute(
            query.order_by(ApprovalRequestRecord.requested_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def get_membership_role(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> str | None:
        result = await self.session.execute(
            select(Membership.role).where(
                Membership.tenant_id == tenant_id,
                Membership.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def grant_approval(
        self,
        run: WorkflowRun,
        step_index: int,
        actor_user_id: uuid.UUID,
        reason: str | None = None,
        approval_request: ApprovalRequestRecord | None = None,
    ) -> WorkflowRun:
        """Grant approval for a step and resume the run."""
        if approval_request is None:
            approval_request = await self.get_pending_approval_request(run.id, step_index=step_index)

        # Eagerly load steps to avoid lazy-load in async context
        await self.session.refresh(run, ["steps"])
        # Update the step's approval info
        for step in run.steps:
            if step.step_index == step_index:
                step.approved_by_user_id = actor_user_id
                step.approved_at = datetime.now(timezone.utc)
                step.status = StepStatus.PENDING
                step.error_message = None
                step.error_details = None
                break

        if approval_request is not None:
            approval_request.status = ApprovalRequestStatus.APPROVED
            approval_request.decision_by_user_id = actor_user_id
            approval_request.decided_at = datetime.now(timezone.utc)
            approval_request.decision_reason = reason

        run.claimed_by = None
        run.claimed_at = None

        payload: dict[str, Any] = {"reason": reason}
        if approval_request is not None:
            payload.update({
                "approval_request_id": str(approval_request.id),
                "risk_class": approval_request.action_risk_class.value,
                "required_role": approval_request.required_role,
            })

        await self.event_logger.log_approval_granted(
            run.id,
            step_index,
            actor_user_id,
            payload=payload,
        )

        current_status = run.status
        if current_status != RunStatus.AWAITING_APPROVAL:
            raise InvalidTransitionError(current_status, RunStatus.RUNNING)
        run.status = RunStatus.RUNNING
        return run

    async def deny_approval(
        self,
        run: WorkflowRun,
        step_index: int,
        actor_user_id: uuid.UUID,
        reason: str | None = None,
        approval_request: ApprovalRequestRecord | None = None,
    ) -> WorkflowRun:
        """Deny approval for a step and cancel the run."""
        if approval_request is None:
            approval_request = await self.get_pending_approval_request(run.id, step_index=step_index)

        payload: dict[str, Any] = {"reason": reason}
        if approval_request is not None:
            payload.update({
                "approval_request_id": str(approval_request.id),
                "risk_class": approval_request.action_risk_class.value,
                "required_role": approval_request.required_role,
            })

        # Log denial event
        await self.event_logger.log_approval_denied(
            run.id,
            step_index,
            actor_user_id,
            reason,
            payload=payload,
        )

        if approval_request is not None:
            approval_request.status = ApprovalRequestStatus.REJECTED
            approval_request.decision_by_user_id = actor_user_id
            approval_request.decided_at = datetime.now(timezone.utc)
            approval_request.decision_reason = reason
        
        # Eagerly load steps to avoid lazy-load in async context
        await self.session.refresh(run, ["steps"])
        # Update the step's status
        for step in run.steps:
            if step.step_index == step_index:
                step.status = StepStatus.FAILED
                step.error_message = f"Approval denied: {reason}" if reason else "Approval denied"
                break

        run.claimed_by = None
        run.claimed_at = None

        return await self.transition_to(
            run,
            RunStatus.CANCELLED,
            actor_user_id=actor_user_id,
        )

    async def retry_run(self, run: WorkflowRun, actor_user_id: uuid.UUID | None = None) -> WorkflowRun:
        """Retry a failed run from the beginning."""
        if run.status != RunStatus.FAILED:
            raise InvalidTransitionError(run.status, RunStatus.PENDING)

        run.retry_count += 1
        if run.retry_count > run.max_retries:
            raise ValueError(f"Maximum retries ({run.max_retries}) exceeded")

        # Reset run state
        run.current_step_index = 0
        run.error_message = None
        run.error_details = None
        run.started_at = None
        run.completed_at = None
        run.claimed_by = None
        run.claimed_at = None

        # Eagerly load steps to avoid lazy-load in async context
        await self.session.refresh(run, ["steps"])
        # Reset all steps
        for step in run.steps:
            step.status = StepStatus.PENDING
            step.started_at = None
            step.completed_at = None
            step.error_message = None
            step.error_details = None
            step.attempt_number = 1

        # Log retry event
        await self.event_logger.log_run_retry_requested(
            run.id, RunStatus.FAILED, actor_user_id, run.retry_count
        )

        run.status = RunStatus.PENDING
        return run
