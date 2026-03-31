"""Append-only event logging service for workflow audit trail."""
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.workflow_models import EventType, RunStatus, WorkflowEvent


class EventLogger:
    """
    Append-only event logger for workflow runs.
    
    All state transitions and significant actions are recorded here.
    Events are immutable once written.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _get_next_sequence_number(self, run_id: uuid.UUID) -> int:
        """Get the next sequence number for a run's events."""
        result = await self.session.execute(
            select(func.coalesce(func.max(WorkflowEvent.sequence_number), 0))
            .where(WorkflowEvent.run_id == run_id)
        )
        current_max = result.scalar_one()
        return current_max + 1

    async def log_event(
        self,
        run_id: uuid.UUID,
        event_type: EventType,
        *,
        step_index: int | None = None,
        actor_user_id: uuid.UUID | None = None,
        actor_type: str = "system",
        previous_status: str | None = None,
        new_status: str | None = None,
        payload: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> WorkflowEvent:
        """
        Append an immutable event to the run's event log.
        
        Events are ordered by sequence_number within a run.
        """
        sequence_number = await self._get_next_sequence_number(run_id)
        
        event = WorkflowEvent(
            id=uuid.uuid4(),
            run_id=run_id,
            sequence_number=sequence_number,
            event_type=event_type,
            created_at=datetime.now(timezone.utc),
            step_index=step_index,
            actor_user_id=actor_user_id,
            actor_type=actor_type,
            previous_status=previous_status,
            new_status=new_status,
            payload=payload or {},
            error_message=error_message,
        )
        
        self.session.add(event)
        return event

    # Convenience methods for common events

    async def log_run_created(
        self,
        run_id: uuid.UUID,
        actor_user_id: uuid.UUID | None = None,
        payload: dict[str, Any] | None = None,
    ) -> WorkflowEvent:
        """Log run creation event."""
        return await self.log_event(
            run_id,
            EventType.RUN_CREATED,
            actor_user_id=actor_user_id,
            actor_type="user" if actor_user_id else "system",
            new_status=RunStatus.PENDING.value,
            payload=payload,
        )

    async def log_run_started(
        self,
        run_id: uuid.UUID,
        previous_status: RunStatus,
    ) -> WorkflowEvent:
        """Log run started event."""
        return await self.log_event(
            run_id,
            EventType.RUN_STARTED,
            actor_type="worker",
            previous_status=previous_status.value,
            new_status=RunStatus.RUNNING.value,
        )

    async def log_run_paused(
        self,
        run_id: uuid.UUID,
        previous_status: RunStatus,
        reason: str | None = None,
    ) -> WorkflowEvent:
        """Log run paused event."""
        return await self.log_event(
            run_id,
            EventType.RUN_PAUSED,
            actor_type="system",
            previous_status=previous_status.value,
            new_status=RunStatus.PAUSED.value,
            payload={"reason": reason} if reason else None,
        )

    async def log_run_resumed(
        self,
        run_id: uuid.UUID,
        previous_status: RunStatus,
        actor_user_id: uuid.UUID | None = None,
    ) -> WorkflowEvent:
        """Log run resumed event."""
        return await self.log_event(
            run_id,
            EventType.RUN_RESUMED,
            actor_user_id=actor_user_id,
            actor_type="user" if actor_user_id else "system",
            previous_status=previous_status.value,
            new_status=RunStatus.RUNNING.value,
        )

    async def log_run_completed(
        self,
        run_id: uuid.UUID,
        previous_status: RunStatus,
        output_data: dict[str, Any] | None = None,
    ) -> WorkflowEvent:
        """Log run completion event."""
        return await self.log_event(
            run_id,
            EventType.RUN_COMPLETED,
            actor_type="worker",
            previous_status=previous_status.value,
            new_status=RunStatus.COMPLETED.value,
            payload={"output_summary": bool(output_data)} if output_data else None,
        )

    async def log_run_failed(
        self,
        run_id: uuid.UUID,
        previous_status: RunStatus,
        error_message: str,
        error_details: dict[str, Any] | None = None,
        step_index: int | None = None,
    ) -> WorkflowEvent:
        """Log run failure event."""
        return await self.log_event(
            run_id,
            EventType.RUN_FAILED,
            step_index=step_index,
            actor_type="worker",
            previous_status=previous_status.value,
            new_status=RunStatus.FAILED.value,
            payload=error_details,
            error_message=error_message,
        )

    async def log_run_cancelled(
        self,
        run_id: uuid.UUID,
        previous_status: RunStatus,
        actor_user_id: uuid.UUID | None = None,
        reason: str | None = None,
    ) -> WorkflowEvent:
        """Log run cancellation event."""
        return await self.log_event(
            run_id,
            EventType.RUN_CANCELLED,
            actor_user_id=actor_user_id,
            actor_type="user" if actor_user_id else "system",
            previous_status=previous_status.value,
            new_status=RunStatus.CANCELLED.value,
            payload={"reason": reason} if reason else None,
        )

    async def log_run_retry_requested(
        self,
        run_id: uuid.UUID,
        previous_status: RunStatus,
        actor_user_id: uuid.UUID | None = None,
        retry_count: int = 0,
    ) -> WorkflowEvent:
        """Log retry request event."""
        return await self.log_event(
            run_id,
            EventType.RUN_RETRY_REQUESTED,
            actor_user_id=actor_user_id,
            actor_type="user" if actor_user_id else "system",
            previous_status=previous_status.value,
            new_status=RunStatus.PENDING.value,
            payload={"retry_count": retry_count},
        )

    async def log_approval_requested(
        self,
        run_id: uuid.UUID,
        step_index: int,
        step_name: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> WorkflowEvent:
        """Log approval request event."""
        event_payload = payload.copy() if payload else {}
        if step_name:
            event_payload.setdefault("step_name", step_name)
        return await self.log_event(
            run_id,
            EventType.APPROVAL_REQUESTED,
            step_index=step_index,
            actor_type="worker",
            previous_status=RunStatus.RUNNING.value,
            new_status=RunStatus.AWAITING_APPROVAL.value,
            payload=event_payload or None,
        )

    async def log_approval_granted(
        self,
        run_id: uuid.UUID,
        step_index: int,
        actor_user_id: uuid.UUID,
        payload: dict[str, Any] | None = None,
    ) -> WorkflowEvent:
        """Log approval granted event."""
        return await self.log_event(
            run_id,
            EventType.APPROVAL_GRANTED,
            step_index=step_index,
            actor_user_id=actor_user_id,
            actor_type="user",
            previous_status=RunStatus.AWAITING_APPROVAL.value,
            new_status=RunStatus.RUNNING.value,
            payload=payload,
        )

    async def log_approval_denied(
        self,
        run_id: uuid.UUID,
        step_index: int,
        actor_user_id: uuid.UUID,
        reason: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> WorkflowEvent:
        """Log approval denied event."""
        event_payload = payload.copy() if payload else {}
        if reason:
            event_payload["reason"] = reason
        return await self.log_event(
            run_id,
            EventType.APPROVAL_DENIED,
            step_index=step_index,
            actor_user_id=actor_user_id,
            actor_type="user",
            previous_status=RunStatus.AWAITING_APPROVAL.value,
            new_status=RunStatus.CANCELLED.value,
            payload=event_payload or None,
        )

    async def log_step_started(
        self,
        run_id: uuid.UUID,
        step_index: int,
        step_name: str | None = None,
        attempt_number: int = 1,
    ) -> WorkflowEvent:
        """Log step started event."""
        return await self.log_event(
            run_id,
            EventType.STEP_STARTED,
            step_index=step_index,
            actor_type="worker",
            payload={"step_name": step_name, "attempt_number": attempt_number},
        )

    async def log_step_completed(
        self,
        run_id: uuid.UUID,
        step_index: int,
        step_name: str | None = None,
        output_summary: dict[str, Any] | None = None,
    ) -> WorkflowEvent:
        """Log step completion event."""
        return await self.log_event(
            run_id,
            EventType.STEP_COMPLETED,
            step_index=step_index,
            actor_type="worker",
            payload={"step_name": step_name, "has_output": bool(output_summary)},
        )

    async def log_step_failed(
        self,
        run_id: uuid.UUID,
        step_index: int,
        error_message: str,
        step_name: str | None = None,
        error_details: dict[str, Any] | None = None,
    ) -> WorkflowEvent:
        """Log step failure event."""
        return await self.log_event(
            run_id,
            EventType.STEP_FAILED,
            step_index=step_index,
            actor_type="worker",
            payload={"step_name": step_name, **(error_details or {})},
            error_message=error_message,
        )

    async def log_step_retry_scheduled(
        self,
        run_id: uuid.UUID,
        step_index: int,
        attempt_number: int = 1,
        reason: str | None = None,
    ) -> WorkflowEvent:
        """Log step retry event."""
        return await self.log_event(
            run_id,
            EventType.STEP_RETRY_SCHEDULED,
            step_index=step_index,
            actor_type="worker",
            payload={"attempt_number": attempt_number, "reason": reason},
        )


async def get_run_events(
    session: AsyncSession,
    run_id: uuid.UUID,
    *,
    limit: int | None = None,
    offset: int | None = None,
) -> list[WorkflowEvent]:
    """Retrieve events for a run, ordered by sequence number."""
    query = (
        select(WorkflowEvent)
        .where(WorkflowEvent.run_id == run_id)
        .order_by(WorkflowEvent.sequence_number)
    )
    
    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)
    
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_events_since(
    session: AsyncSession,
    run_id: uuid.UUID,
    since_sequence: int,
) -> list[WorkflowEvent]:
    """Get events after a specific sequence number (for polling)."""
    result = await session.execute(
        select(WorkflowEvent)
        .where(WorkflowEvent.run_id == run_id)
        .where(WorkflowEvent.sequence_number > since_sequence)
        .order_by(WorkflowEvent.sequence_number)
    )
    return list(result.scalars().all())
