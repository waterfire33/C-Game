"""
Background worker for executing workflow runs.

Key features:
- SELECT ... FOR UPDATE SKIP LOCKED for safe concurrent claiming
- Idempotent step execution via idempotency keys
- Exponential backoff for retries
- Graceful shutdown handling
"""
import asyncio
import logging
import signal
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Coroutine

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.approval_policy import get_step_approval_policy
from app.db.workflow_models import (
    RunStatus,
    StepStatus,
    WorkflowRun,
    WorkflowRunStep,
    WorkflowStepDefinition,
)
from app.services.event_logger import EventLogger
from app.services.state_machine import (
    ApprovalRequiredError,
    RunStateMachine,
)
from app.services.tool_adapter import INTERNAL_TOOLS, ToolExecutionError, ToolExecutor
from app.db.tool_models import ToolExecutionStatus

logger = logging.getLogger(__name__)


# Type alias for step handlers
StepHandler = Callable[
    [WorkflowRunStep, dict[str, Any], AsyncSession],
    Coroutine[Any, Any, dict[str, Any] | None],
]


class WorkflowWorker:
    """
    Background worker that processes pending workflow runs.
    
    Uses SELECT ... FOR UPDATE SKIP LOCKED for safe concurrent processing
    across multiple worker instances.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        worker_id: str | None = None,
        poll_interval: float = 2.0,
        claim_timeout: timedelta = timedelta(minutes=5),
        max_concurrent_runs: int = 5,
    ):
        self.session_factory = session_factory
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.poll_interval = poll_interval
        self.claim_timeout = claim_timeout
        self.max_concurrent_runs = max_concurrent_runs
        
        self._shutdown_event = asyncio.Event()
        self._active_runs: set[uuid.UUID] = set()
        self._step_handlers: dict[str, StepHandler] = {}

    def register_step_handler(self, step_type: str, handler: StepHandler) -> None:
        """Register a handler for a step type."""
        self._step_handlers[step_type] = handler

    async def start(self) -> None:
        """Start the worker loop."""
        logger.info(f"Worker {self.worker_id} starting")

        # Setup signal handlers for graceful shutdown
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._signal_shutdown)

        try:
            await self._run_loop()
        finally:
            logger.info(f"Worker {self.worker_id} shutting down")

    def _signal_shutdown(self) -> None:
        """Handle shutdown signal."""
        logger.info(f"Worker {self.worker_id} received shutdown signal")
        self._shutdown_event.set()

    async def _run_loop(self) -> None:
        """Main worker loop."""
        while not self._shutdown_event.is_set():
            try:
                # Clean up stale claims from crashed workers
                await self._release_stale_claims()

                # Process pending runs
                if len(self._active_runs) < self.max_concurrent_runs:
                    await self._process_next_run()

                # Wait before next poll
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=self.poll_interval,
                    )
                except asyncio.TimeoutError:
                    pass

            except Exception as e:
                logger.exception(f"Worker loop error: {e}")
                await asyncio.sleep(self.poll_interval)

    async def _release_stale_claims(self) -> None:
        """Release runs claimed by workers that appear to have crashed."""
        async with self.session_factory() as session:
            stale_cutoff = datetime.now(timezone.utc) - self.claim_timeout

            await session.execute(
                update(WorkflowRun)
                .where(
                    WorkflowRun.status == RunStatus.RUNNING,
                    WorkflowRun.claimed_at < stale_cutoff,
                    WorkflowRun.claimed_by.is_not(None),
                )
                .values(
                    status=RunStatus.PENDING,
                    claimed_by=None,
                    claimed_at=None,
                )
            )
            await session.commit()

    async def _process_next_run(self) -> None:
        """
        Claim and process the next available run.
        
        Uses SELECT ... FOR UPDATE SKIP LOCKED for safe concurrent claiming.
        """
        async with self.session_factory() as session:
            # Claim a pending run atomically
            run = await self._claim_next_run(session)
            if run is None:
                return

            self._active_runs.add(run.id)
            try:
                await self._execute_run(session, run)
            finally:
                self._active_runs.discard(run.id)

    async def _claim_next_run(
        self, session: AsyncSession
    ) -> WorkflowRun | None:
        """
        Claim the next pending run using SELECT ... FOR UPDATE SKIP LOCKED.
        
        This ensures only one worker can claim a run even with concurrent workers.
        """
        # Find and lock a pending run
        result = await session.execute(
            select(WorkflowRun)
            .where(
                WorkflowRun.claimed_by.is_(None),
                WorkflowRun.status.in_([RunStatus.PENDING, RunStatus.RUNNING]),
            )
            .order_by(WorkflowRun.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        run = result.scalar_one_or_none()

        if run is None:
            return None

        state_machine = RunStateMachine(session)
        if run.status == RunStatus.PENDING:
            run = await state_machine.start_run(run, self.worker_id)
        else:
            run.claimed_by = self.worker_id
            run.claimed_at = datetime.now(timezone.utc)
        await session.commit()

        logger.info(f"Worker {self.worker_id} claimed run {run.id}")
        return run

    async def _execute_run(
        self, session: AsyncSession, run: WorkflowRun
    ) -> None:
        """Execute all steps of a run."""
        state_machine = RunStateMachine(session)
        event_logger = EventLogger(session)

        try:
            # Load full run with relationships
            run = await state_machine.get_run(run.id)

            # Get ordered step definitions
            step_defs = sorted(
                run.workflow_definition.steps, key=lambda s: s.order
            )

            # Execute each step starting from current index
            for step_def in step_defs[run.current_step_index :]:
                if self._shutdown_event.is_set():
                    logger.info(f"Shutdown requested, pausing run {run.id}")
                    await state_machine.pause_run(run)
                    await session.commit()
                    return

                # Find the corresponding run step
                run_step = next(
                    (s for s in run.steps if s.step_definition_id == step_def.id),
                    None,
                )
                if run_step is None:
                    continue

                # Execute the step
                success = await self._execute_step(
                    session, run, run_step, step_def, state_machine, event_logger
                )

                if not success:
                    # Step failed or requires approval - stop execution
                    return

                # Advance to next step
                run.current_step_index = step_def.order + 1
                await session.commit()

            # All steps completed
            await state_machine.complete_run(run)
            await session.commit()
            logger.info(f"Run {run.id} completed successfully")

        except ApprovalRequiredError as e:
            # Run is now awaiting approval - this is handled in _execute_step
            logger.info(f"Run {run.id} awaiting approval for step {e.step_index}")
            await session.commit()

        except Exception as e:
            logger.exception(f"Run {run.id} failed with error: {e}")
            await state_machine.fail_run(
                run,
                error_message=str(e),
                error_details={"exception_type": type(e).__name__},
                step_index=run.current_step_index,
            )
            await session.commit()

    async def _execute_step(
        self,
        session: AsyncSession,
        run: WorkflowRun,
        run_step: WorkflowRunStep,
        step_def: WorkflowStepDefinition,
        state_machine: RunStateMachine,
        event_logger: EventLogger,
    ) -> bool:
        """
        Execute a single step with idempotency and approval checking.
        
        Returns True if step succeeded, False if it failed or needs approval.
        """
        # Skip already completed steps (idempotency)
        if run_step.status == StepStatus.COMPLETED:
            logger.debug(f"Step {step_def.order} already completed, skipping")
            return True

        # Check for approval requirement
        approval_policy = get_step_approval_policy(step_def)
        if approval_policy.requires_approval and run_step.approved_by_user_id is None:
            # Need approval - transition run to AWAITING_APPROVAL
            run_step.status = StepStatus.AWAITING_APPROVAL
            await state_machine.ensure_approval_request(run, run_step, step_def)
            await state_machine.request_approval(run, step_def.order)
            await session.commit()
            raise ApprovalRequiredError(run.id, step_def.order, step_def.name)

        # Mark step as running
        run_step.status = StepStatus.RUNNING
        run_step.started_at = datetime.now(timezone.utc)
        await event_logger.log_step_started(run.id, step_def.order)
        await session.commit()

        try:
            is_tool_step = bool(step_def.config.get("tool_name")) or step_def.step_type in INTERNAL_TOOLS
            if is_tool_step:
                tool_executor = ToolExecutor(session)
                tool_result = await tool_executor.execute_step_tool(run, run_step, step_def)
                run_step.attempt_number = tool_result.attempt_count
                if tool_result.status != ToolExecutionStatus.SUCCEEDED:
                    raise ToolExecutionError(
                        tool_result.error_message or "tool execution failed",
                        tool_result.failure_category,
                    )
                step_output = tool_result.normalized_output
            else:
                handler = self._step_handlers.get(step_def.step_type)
                if handler is None:
                    raise ValueError(f"No handler for step type: {step_def.step_type}")

                step_output = await handler(run_step, run.state or {}, session)

                if step_output:
                    run.state = {**(run.state or {}), **step_output}

            # Mark step completed
            run_step.status = StepStatus.COMPLETED
            run_step.completed_at = datetime.now(timezone.utc)
            run_step.output_data = step_output
            await event_logger.log_step_completed(
                run.id,
                step_def.order,
                output_summary=step_output,
            )

            return True

        except Exception as e:
            # Handle step failure with retry logic
            run_step.attempt_number += 1
            error_details = {"exception_type": type(e).__name__}
            if isinstance(e, ToolExecutionError):
                error_details["failure_category"] = e.category.value
            max_attempts = 1 if isinstance(e, ToolExecutionError) else step_def.max_retries
            
            if run_step.attempt_number < max_attempts:
                # Schedule retry
                run_step.status = StepStatus.PENDING
                run_step.error_message = str(e)
                await event_logger.log_step_retry_scheduled(
                    run.id,
                    step_def.order,
                    run_step.attempt_number,
                    reason=str(e),
                )
                
                # Exponential backoff delay
                delay = self._calculate_backoff(run_step.attempt_number)
                await asyncio.sleep(delay)
                
                # Retry the step recursively
                return await self._execute_step(
                    session, run, run_step, step_def, state_machine, event_logger
                )
            else:
                # Max retries exceeded
                run_step.status = StepStatus.FAILED
                run_step.error_message = str(e)
                run_step.error_details = error_details
                await event_logger.log_step_failed(
                    run.id,
                    step_def.order,
                    str(e),
                    error_details=error_details,
                )
                
                # Fail the entire run
                await state_machine.fail_run(
                    run,
                    error_message=f"Step {step_def.order} failed: {e}",
                    error_details={"step_index": step_def.order, **error_details},
                    step_index=step_def.order,
                )
                return False

    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff delay with jitter."""
        import random
        
        base_delay = 1.0  # 1 second
        max_delay = 60.0  # 1 minute
        
        delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
        jitter = delay * 0.1 * random.random()
        
        return delay + jitter


async def create_worker(
    session_factory: async_sessionmaker[AsyncSession],
    step_handlers: dict[str, StepHandler] | None = None,
    **kwargs: Any,
) -> WorkflowWorker:
    """Factory function to create a configured worker."""
    worker = WorkflowWorker(session_factory, **kwargs)
    
    if step_handlers:
        for step_type, handler in step_handlers.items():
            worker.register_step_handler(step_type, handler)
    
    return worker
