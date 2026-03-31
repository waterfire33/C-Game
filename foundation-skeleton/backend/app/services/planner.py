"""Agent router and planner service.

Handles:
- Request intake and canonical request creation
- Deterministic routing (keyword-based)
- LLM-based planning (with structured output parsing)
- Plan persistence and failure classification
- Workflow definition selection and run creation
"""
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.planner_models import (
    AgentRequest,
    PlannerFailureCategory,
    PlannerStrategy,
    PlanRecord,
    PlanStatus,
    WorkflowType,
)
from app.db.workflow_models import WorkflowDefinition, WorkflowStepDefinition
from app.schemas.planner import PlannedStep, PlannerOutput
from app.services.prompt_templates import SYSTEM_PROMPT, build_user_prompt
from app.services.state_machine import RunStateMachine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Deterministic keyword rules
# ---------------------------------------------------------------------------

_KEYWORD_RULES: list[tuple[WorkflowType, list[str]]] = [
    (WorkflowType.EXECUTABLE_TOOL, [
        "run", "execute", "trigger", "query", "analytics", "compute", "calculate",
    ]),
    (WorkflowType.DRAFT_ACTION, [
        "draft", "compose", "write", "email", "message", "report", "generate document",
    ]),
    (WorkflowType.INFORMATION_REQUEST, [
        "find", "look up", "search", "what is", "who is", "summarise", "summarize",
        "explain", "tell me", "show me", "how do", "fetch",
    ]),
]

_DEFAULT_STEPS_BY_TYPE: dict[WorkflowType, list[PlannedStep]] = {
    WorkflowType.INFORMATION_REQUEST: [
        PlannedStep(
            name="Search knowledge base",
            step_type="knowledge_search",
            config={"query_source": "request_body"},
            reasoning="Look up relevant information for the user",
        ),
    ],
    WorkflowType.DRAFT_ACTION: [
        PlannedStep(
            name="Search for context",
            step_type="knowledge_search",
            config={"query_source": "request_body"},
            reasoning="Gather context before drafting",
        ),
        PlannedStep(
            name="Generate draft",
            step_type="outbound_draft_generator",
            config={"draft_kind": "email"},
            reasoning="Produce the draft artefact",
        ),
    ],
    WorkflowType.EXECUTABLE_TOOL: [
        PlannedStep(
            name="Run analytics query",
            step_type="simple_analytics_query",
            config={"query_source": "request_body"},
            reasoning="Execute the requested tool action",
        ),
    ],
}


def _deterministic_classify(body: str) -> PlannerOutput | None:
    """Attempt keyword-based classification.  Returns None if no match."""
    lower = body.lower()
    for wf_type, keywords in _KEYWORD_RULES:
        for kw in keywords:
            if kw in lower:
                steps = _DEFAULT_STEPS_BY_TYPE[wf_type]
                return PlannerOutput(
                    workflow_type=wf_type,
                    confidence=0.85,
                    reasoning=f"Deterministic match on keyword '{kw}'",
                    steps=steps,
                )
    return None


# ---------------------------------------------------------------------------
# LLM planner (pluggable backend)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class LLMResponse:
    text: str
    latency_ms: int


class LLMBackend:
    """Abstract interface for an LLM completion call.

    The default implementation is a *stub* that echoes a deterministic
    JSON plan derived from simple heuristics, so the full pipeline can be
    tested without external API keys.  Replace `complete()` with a real
    provider call in production.
    """

    async def complete(self, system: str, user: str) -> LLMResponse:
        """Return structured JSON from the LLM."""
        start = time.monotonic()

        # Stub: derive a plan from the user prompt using basic heuristics
        plan = _deterministic_classify(user)
        if plan is None:
            plan = PlannerOutput(
                workflow_type=WorkflowType.INFORMATION_REQUEST,
                confidence=0.5,
                reasoning="LLM stub fallback — no strong signal detected",
                steps=_DEFAULT_STEPS_BY_TYPE[WorkflowType.INFORMATION_REQUEST],
            )

        elapsed_ms = int((time.monotonic() - start) * 1000)
        return LLMResponse(
            text=plan.model_dump_json(),
            latency_ms=elapsed_ms,
        )


_default_llm = LLMBackend()


def _parse_llm_output(raw: str) -> PlannerOutput:
    """Parse raw LLM text into a validated PlannerOutput."""
    # Strip markdown fences if present
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    cleaned = re.sub(r"\s*```$", "", cleaned)
    data = json.loads(cleaned)
    return PlannerOutput.model_validate(data)


# ---------------------------------------------------------------------------
# Router: select or create a matching WorkflowDefinition
# ---------------------------------------------------------------------------

async def _find_or_create_workflow_definition(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID | None,
    plan: PlannerOutput,
) -> WorkflowDefinition:
    """Find an existing active definition that matches the plan's workflow_type,
    or create a new one from the planned steps."""

    # Try to find a definition whose name starts with the workflow_type label
    prefix = plan.workflow_type.value
    result = await session.execute(
        select(WorkflowDefinition)
        .where(
            WorkflowDefinition.tenant_id == tenant_id,
            WorkflowDefinition.is_active.is_(True),
            WorkflowDefinition.name.ilike(f"{prefix}%"),
        )
        .options(selectinload(WorkflowDefinition.steps))
        .order_by(WorkflowDefinition.created_at.desc())
        .limit(1)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing

    # Create on the fly
    definition = WorkflowDefinition(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=f"{prefix}_auto_{uuid.uuid4().hex[:8]}",
        description=plan.reasoning,
        version=1,
        is_active=True,
        created_by_user_id=user_id,
    )
    session.add(definition)
    await session.flush()

    for order, step in enumerate(plan.steps):
        session.add(
            WorkflowStepDefinition(
                id=uuid.uuid4(),
                workflow_definition_id=definition.id,
                name=step.name,
                step_type=step.step_type,
                order=order,
                config=step.config,
                requires_approval=False,
                max_retries=3,
            )
        )

    return definition


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class PlannerService:
    """Orchestrates intake → plan → route → run for a single request."""

    def __init__(self, session: AsyncSession, *, llm: LLMBackend | None = None):
        self.session = session
        self.llm = llm or _default_llm

    # -- intake ---------------------------------------------------------------

    async def create_request(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID | None,
        body: str,
        context: dict[str, Any],
        idempotency_key: str,
    ) -> AgentRequest:
        existing = await self.session.execute(
            select(AgentRequest).where(AgentRequest.idempotency_key == idempotency_key)
        )
        found = existing.scalar_one_or_none()
        if found is not None:
            return found

        request = AgentRequest(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            submitted_by_user_id=user_id,
            body=body,
            context=context,
            idempotency_key=idempotency_key,
        )
        self.session.add(request)
        await self.session.flush()
        return request

    # -- plan + route ---------------------------------------------------------

    async def plan_and_route(
        self,
        request: AgentRequest,
    ) -> PlanRecord:
        """Run the planner, persist the plan, select a workflow, and create a run."""
        # Idempotency: return existing plan if one was already created for this request
        existing_plan = await self.session.execute(
            select(PlanRecord).where(PlanRecord.agent_request_id == request.id)
        )
        found_plan = existing_plan.scalar_one_or_none()
        if found_plan is not None:
            return found_plan

        plan_id = uuid.uuid4()
        start = time.monotonic()

        # 1. Deterministic attempt
        deterministic_result = _deterministic_classify(request.body)
        if deterministic_result is not None:
            return await self._persist_and_route(
                plan_id=plan_id,
                request=request,
                output=deterministic_result,
                strategy=PlannerStrategy.DETERMINISTIC,
                latency_ms=int((time.monotonic() - start) * 1000),
            )

        # 2. LLM fallback
        try:
            llm_response = await self.llm.complete(
                SYSTEM_PROMPT,
                build_user_prompt(request.body, request.context),
            )
        except Exception as exc:
            return await self._persist_failure(
                plan_id=plan_id,
                request=request,
                strategy=PlannerStrategy.LLM,
                category=PlannerFailureCategory.LLM_TIMEOUT,
                error=str(exc),
                latency_ms=int((time.monotonic() - start) * 1000),
            )

        try:
            output = _parse_llm_output(llm_response.text)
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            return await self._persist_failure(
                plan_id=plan_id,
                request=request,
                strategy=PlannerStrategy.LLM,
                category=PlannerFailureCategory.UNPARSEABLE_OUTPUT,
                error=str(exc),
                raw_llm=llm_response.text,
                latency_ms=llm_response.latency_ms,
            )

        return await self._persist_and_route(
            plan_id=plan_id,
            request=request,
            output=output,
            strategy=PlannerStrategy.LLM,
            raw_llm=llm_response.text,
            latency_ms=llm_response.latency_ms,
        )

    # -- internals -----------------------------------------------------------

    async def _persist_and_route(
        self,
        *,
        plan_id: uuid.UUID,
        request: AgentRequest,
        output: PlannerOutput,
        strategy: PlannerStrategy,
        raw_llm: str | None = None,
        latency_ms: int = 0,
    ) -> PlanRecord:
        definition = await _find_or_create_workflow_definition(
            self.session,
            request.tenant_id,
            request.submitted_by_user_id,
            output,
        )

        state_machine = RunStateMachine(self.session)
        run = await state_machine.create_run(
            workflow_definition_id=definition.id,
            tenant_id=request.tenant_id,
            idempotency_key=f"plan:{request.idempotency_key}",
            input_data={"body": request.body, **(request.context or {})},
            triggered_by_user_id=request.submitted_by_user_id,
        )

        record = PlanRecord(
            id=plan_id,
            tenant_id=request.tenant_id,
            agent_request_id=request.id,
            workflow_type=output.workflow_type,
            strategy=strategy,
            status=PlanStatus.ROUTED,
            confidence=output.confidence,
            reasoning=output.reasoning,
            planned_steps=[s.model_dump() for s in output.steps],
            selected_workflow_definition_id=definition.id,
            run_id=run.id,
            failure_category=PlannerFailureCategory.NONE,
            prompt_snapshot=(
                {"system": SYSTEM_PROMPT, "user": build_user_prompt(request.body, request.context)}
                if strategy == PlannerStrategy.LLM
                else None
            ),
            raw_llm_output=raw_llm,
            latency_ms=latency_ms,
        )
        self.session.add(record)
        return record

    async def _persist_failure(
        self,
        *,
        plan_id: uuid.UUID,
        request: AgentRequest,
        strategy: PlannerStrategy,
        category: PlannerFailureCategory,
        error: str,
        raw_llm: str | None = None,
        latency_ms: int = 0,
    ) -> PlanRecord:
        record = PlanRecord(
            id=plan_id,
            tenant_id=request.tenant_id,
            agent_request_id=request.id,
            workflow_type=WorkflowType.INFORMATION_REQUEST,
            strategy=strategy,
            status=PlanStatus.FAILED,
            confidence=None,
            reasoning=None,
            planned_steps=[],
            failure_category=category,
            error_message=error,
            prompt_snapshot=(
                {"system": SYSTEM_PROMPT, "user": build_user_prompt(request.body, request.context)}
                if strategy == PlannerStrategy.LLM
                else None
            ),
            raw_llm_output=raw_llm,
            latency_ms=latency_ms,
        )
        self.session.add(record)
        return record

    # -- read helpers --------------------------------------------------------

    async def get_plan(self, plan_id: uuid.UUID) -> PlanRecord | None:
        result = await self.session.execute(
            select(PlanRecord)
            .where(PlanRecord.id == plan_id)
            .options(selectinload(PlanRecord.agent_request))
        )
        return result.scalar_one_or_none()

    async def get_request_with_plan(self, request_id: uuid.UUID) -> AgentRequest | None:
        result = await self.session.execute(
            select(AgentRequest)
            .where(AgentRequest.id == request_id)
            .options(selectinload(AgentRequest.plan))
        )
        return result.scalar_one_or_none()
