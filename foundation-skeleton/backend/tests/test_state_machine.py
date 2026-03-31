"""Tests for workflow state machine transitions and idempotency."""
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Tenant, User
from app.db.workflow_models import (
    RunStatus,
    StepStatus,
    WorkflowDefinition,
    WorkflowStepDefinition,
    VALID_RUN_TRANSITIONS,
)
from app.services.state_machine import (
    InvalidTransitionError,
    RunStateMachine,
    WorkflowNotFoundError,
)


@pytest_asyncio.fixture
async def workflow_definition(
    db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> WorkflowDefinition:
    """Create a test workflow definition with steps."""
    definition = WorkflowDefinition(
        id=uuid.uuid4(),
        tenant_id=test_tenant.id,
        name="Test Workflow",
        description="A workflow for testing",
        version=1,
        is_active=True,
        created_by_user_id=test_user.id,
    )
    db_session.add(definition)
    await db_session.flush()

    # Add steps: one normal, one requiring approval
    step1 = WorkflowStepDefinition(
        id=uuid.uuid4(),
        workflow_definition_id=definition.id,
        name="Step 1",
        step_type="test_step",
        order=0,
        config={},
        requires_approval=False,
        max_retries=3,
    )
    step2 = WorkflowStepDefinition(
        id=uuid.uuid4(),
        workflow_definition_id=definition.id,
        name="Approval Step",
        step_type="approval_step",
        order=1,
        config={},
        requires_approval=True,
        max_retries=1,
    )
    step3 = WorkflowStepDefinition(
        id=uuid.uuid4(),
        workflow_definition_id=definition.id,
        name="Final Step",
        step_type="test_step",
        order=2,
        config={},
        requires_approval=False,
        max_retries=3,
    )
    db_session.add_all([step1, step2, step3])
    await db_session.commit()

    return definition


class TestValidTransitions:
    """Test the VALID_RUN_TRANSITIONS map is correct."""

    def test_pending_can_transition_to_running(self):
        """PENDING -> RUNNING is allowed."""
        assert RunStatus.RUNNING in VALID_RUN_TRANSITIONS[RunStatus.PENDING]

    def test_pending_can_transition_to_cancelled(self):
        """PENDING -> CANCELLED is allowed."""
        assert RunStatus.CANCELLED in VALID_RUN_TRANSITIONS[RunStatus.PENDING]

    def test_running_can_transition_to_completed(self):
        """RUNNING -> COMPLETED is allowed."""
        assert RunStatus.COMPLETED in VALID_RUN_TRANSITIONS[RunStatus.RUNNING]

    def test_running_can_transition_to_failed(self):
        """RUNNING -> FAILED is allowed."""
        assert RunStatus.FAILED in VALID_RUN_TRANSITIONS[RunStatus.RUNNING]

    def test_running_can_transition_to_awaiting_approval(self):
        """RUNNING -> AWAITING_APPROVAL is allowed."""
        assert RunStatus.AWAITING_APPROVAL in VALID_RUN_TRANSITIONS[RunStatus.RUNNING]

    def test_awaiting_approval_can_transition_to_running(self):
        """AWAITING_APPROVAL -> RUNNING is allowed (approval granted)."""
        assert RunStatus.RUNNING in VALID_RUN_TRANSITIONS[RunStatus.AWAITING_APPROVAL]

    def test_awaiting_approval_can_transition_to_cancelled(self):
        """AWAITING_APPROVAL -> CANCELLED is allowed (approval denied)."""
        assert RunStatus.CANCELLED in VALID_RUN_TRANSITIONS[RunStatus.AWAITING_APPROVAL]

    def test_failed_can_transition_to_pending(self):
        """FAILED -> PENDING is allowed (retry)."""
        assert RunStatus.PENDING in VALID_RUN_TRANSITIONS[RunStatus.FAILED]

    def test_completed_is_terminal(self):
        """COMPLETED has no valid outgoing transitions."""
        assert RunStatus.COMPLETED not in VALID_RUN_TRANSITIONS
        # Or if it exists, it should be empty
        assert VALID_RUN_TRANSITIONS.get(RunStatus.COMPLETED, set()) == set()


class TestStateMachineTransitions:
    """Test state machine transition validation."""

    @pytest.mark.asyncio
    async def test_validates_valid_transition(
        self, db_session: AsyncSession, workflow_definition: WorkflowDefinition, test_tenant: Tenant
    ):
        """Valid transitions should succeed."""
        state_machine = RunStateMachine(db_session)

        run = await state_machine.create_run(
            workflow_definition_id=workflow_definition.id,
            tenant_id=test_tenant.id,
            idempotency_key="test-valid-transition",
        )
        assert run.status == RunStatus.PENDING

        # PENDING -> RUNNING is valid
        run = await state_machine.start_run(run, "test-worker")
        assert run.status == RunStatus.RUNNING

    @pytest.mark.asyncio
    async def test_rejects_invalid_transition(
        self, db_session: AsyncSession, workflow_definition: WorkflowDefinition, test_tenant: Tenant
    ):
        """Invalid transitions should raise InvalidTransitionError."""
        state_machine = RunStateMachine(db_session)

        run = await state_machine.create_run(
            workflow_definition_id=workflow_definition.id,
            tenant_id=test_tenant.id,
            idempotency_key="test-invalid-transition",
        )
        assert run.status == RunStatus.PENDING

        # PENDING -> COMPLETED is invalid (must go through RUNNING)
        with pytest.raises(InvalidTransitionError) as exc_info:
            await state_machine.transition_to(run, RunStatus.COMPLETED)

        assert exc_info.value.current_status == RunStatus.PENDING
        assert exc_info.value.target_status == RunStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_awaiting_approval_blocks_progression(
        self, db_session: AsyncSession, workflow_definition: WorkflowDefinition, test_tenant: Tenant
    ):
        """Run should block at AWAITING_APPROVAL until approved."""
        state_machine = RunStateMachine(db_session)

        run = await state_machine.create_run(
            workflow_definition_id=workflow_definition.id,
            tenant_id=test_tenant.id,
            idempotency_key="test-approval-block",
        )

        # Start the run
        run = await state_machine.start_run(run, "test-worker")
        
        # Request approval
        run = await state_machine.request_approval(run, step_index=1)
        assert run.status == RunStatus.AWAITING_APPROVAL

        # Cannot transition to completed while awaiting approval
        with pytest.raises(InvalidTransitionError):
            await state_machine.transition_to(run, RunStatus.COMPLETED)

    @pytest.mark.asyncio
    async def test_approval_grants_resume_to_running(
        self, db_session: AsyncSession, workflow_definition: WorkflowDefinition, test_tenant: Tenant, test_user: User
    ):
        """Granting approval should transition from AWAITING_APPROVAL to RUNNING."""
        state_machine = RunStateMachine(db_session)

        run = await state_machine.create_run(
            workflow_definition_id=workflow_definition.id,
            tenant_id=test_tenant.id,
            idempotency_key="test-approval-grant",
        )
        run = await state_machine.start_run(run, "test-worker")
        run = await state_machine.request_approval(run, step_index=1)
        assert run.status == RunStatus.AWAITING_APPROVAL

        # Grant approval
        run = await state_machine.grant_approval(run, step_index=1, actor_user_id=test_user.id)
        assert run.status == RunStatus.RUNNING


class TestIdempotency:
    """Test idempotency key behavior."""

    @pytest.mark.asyncio
    async def test_create_run_is_idempotent(
        self, db_session: AsyncSession, workflow_definition: WorkflowDefinition, test_tenant: Tenant
    ):
        """Creating a run with the same idempotency key returns the existing run."""
        state_machine = RunStateMachine(db_session)
        idempotency_key = "idempotent-run-123"

        # Create first run
        run1 = await state_machine.create_run(
            workflow_definition_id=workflow_definition.id,
            tenant_id=test_tenant.id,
            idempotency_key=idempotency_key,
            input_data={"key": "value1"},
        )
        await db_session.commit()

        # Try to create again with same key
        run2 = await state_machine.create_run(
            workflow_definition_id=workflow_definition.id,
            tenant_id=test_tenant.id,
            idempotency_key=idempotency_key,
            input_data={"key": "value2"},  # Different input
        )

        # Should return the same run
        assert run1.id == run2.id
        # Original input should be preserved
        assert run2.input_data == {"key": "value1"}

    @pytest.mark.asyncio
    async def test_different_idempotency_keys_create_different_runs(
        self, db_session: AsyncSession, workflow_definition: WorkflowDefinition, test_tenant: Tenant
    ):
        """Different idempotency keys should create different runs."""
        state_machine = RunStateMachine(db_session)

        run1 = await state_machine.create_run(
            workflow_definition_id=workflow_definition.id,
            tenant_id=test_tenant.id,
            idempotency_key="key-1",
        )
        await db_session.commit()

        run2 = await state_machine.create_run(
            workflow_definition_id=workflow_definition.id,
            tenant_id=test_tenant.id,
            idempotency_key="key-2",
        )

        assert run1.id != run2.id

    @pytest.mark.asyncio
    async def test_run_steps_have_idempotency_keys(
        self, db_session: AsyncSession, workflow_definition: WorkflowDefinition, test_tenant: Tenant
    ):
        """Each run step should have an idempotency key derived from run + step order."""
        state_machine = RunStateMachine(db_session)

        run = await state_machine.create_run(
            workflow_definition_id=workflow_definition.id,
            tenant_id=test_tenant.id,
            idempotency_key="parent-key",
        )
        await db_session.commit()

        # Reload with steps
        run = await state_machine.get_run(run.id)

        # Each step should have a predictable idempotency key
        for step in run.steps:
            expected_key = f"parent-key:step:{step.step_index}"
            assert step.idempotency_key == expected_key


class TestRunLifecycle:
    """Test full run lifecycle scenarios."""

    @pytest.mark.asyncio
    async def test_run_creation_creates_steps(
        self, db_session: AsyncSession, workflow_definition: WorkflowDefinition, test_tenant: Tenant
    ):
        """Creating a run should create all step instances."""
        state_machine = RunStateMachine(db_session)

        run = await state_machine.create_run(
            workflow_definition_id=workflow_definition.id,
            tenant_id=test_tenant.id,
            idempotency_key="lifecycle-test",
        )
        await db_session.commit()

        run = await state_machine.get_run(run.id)
        
        # Should have 3 steps (matching workflow definition)
        assert len(run.steps) == 3
        
        # All steps should start as PENDING
        for step in run.steps:
            assert step.status == StepStatus.PENDING

    @pytest.mark.asyncio
    async def test_fail_run_stores_error_info(
        self, db_session: AsyncSession, workflow_definition: WorkflowDefinition, test_tenant: Tenant
    ):
        """Failing a run should store error message and details."""
        state_machine = RunStateMachine(db_session)

        run = await state_machine.create_run(
            workflow_definition_id=workflow_definition.id,
            tenant_id=test_tenant.id,
            idempotency_key="fail-test",
        )
        run = await state_machine.start_run(run, "test-worker")

        error_details = {"traceback": "...", "step": 1}
        run = await state_machine.fail_run(
            run,
            error_message="Something went wrong",
            error_details=error_details,
            step_index=1,
        )

        assert run.status == RunStatus.FAILED
        assert run.error_message == "Something went wrong"
        assert run.error_details == error_details
        assert run.completed_at is not None

    @pytest.mark.asyncio
    async def test_retry_resets_run_state(
        self, db_session: AsyncSession, workflow_definition: WorkflowDefinition, test_tenant: Tenant, test_user: User
    ):
        """Retrying a failed run should reset it to PENDING."""
        state_machine = RunStateMachine(db_session)

        run = await state_machine.create_run(
            workflow_definition_id=workflow_definition.id,
            tenant_id=test_tenant.id,
            idempotency_key="retry-test",
        )
        run = await state_machine.start_run(run, "test-worker")
        run = await state_machine.fail_run(run, error_message="Failed")
        assert run.status == RunStatus.FAILED

        # Retry
        run = await state_machine.retry_run(run, test_user.id)
        
        assert run.status == RunStatus.PENDING
        assert run.retry_count == 1
        assert run.error_message is None
        assert run.current_step_index == 0
        assert run.started_at is None
        assert run.claimed_by is None

    @pytest.mark.asyncio
    async def test_workflow_not_found_raises(
        self, db_session: AsyncSession, test_tenant: Tenant
    ):
        """Creating a run with non-existent workflow should raise."""
        state_machine = RunStateMachine(db_session)

        with pytest.raises(WorkflowNotFoundError):
            await state_machine.create_run(
                workflow_definition_id=uuid.uuid4(),
                tenant_id=test_tenant.id,
                idempotency_key="not-found-test",
            )
