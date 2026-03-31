import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Tenant, User
from app.db.tool_models import ToolCall, ToolExecutionStatus, ToolFailureCategory
from app.db.workflow_models import RunStatus, StepStatus, WorkflowDefinition, WorkflowRunStep, WorkflowStepDefinition
from app.services.state_machine import RunStateMachine
from app.services.tool_adapter import ToolRegistryService
from app.worker.runner import WorkflowWorker


async def _create_tool_workflow(
    db_session: AsyncSession,
    *,
    tenant_id,
    user_id,
    tool_name: str,
    tool_input: dict,
    max_retries: int = 1,
) -> WorkflowDefinition:
    definition = WorkflowDefinition(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=f"{tool_name}-workflow",
        description="tool-backed workflow",
        version=1,
        is_active=True,
        created_by_user_id=user_id,
    )
    db_session.add(definition)
    await db_session.flush()

    step = WorkflowStepDefinition(
        id=uuid.uuid4(),
        workflow_definition_id=definition.id,
        name=f"Run {tool_name}",
        step_type=tool_name,
        order=0,
        config={"tool_name": tool_name, "input": tool_input},
        max_retries=max_retries,
    )
    db_session.add(step)
    await db_session.commit()
    return definition


class TestToolRegistry:
    @pytest.mark.asyncio
    async def test_registers_tools_per_tenant(
        self,
        db_session: AsyncSession,
        test_tenant: Tenant,
    ):
        registry = ToolRegistryService(db_session)

        registration = await registry.register_tool_for_tenant(
            tenant_id=test_tenant.id,
            tool_name="knowledge_search",
            override_timeout_seconds=25,
            override_max_retries=2,
            metadata_json={"purpose": "discovery"},
        )
        await db_session.commit()

        allowed_tools = await registry.list_allowed_tools(test_tenant.id)

        assert registration.tool_definition.name == "knowledge_search"
        assert len(allowed_tools) == 1
        assert allowed_tools[0].tool_definition.name == "knowledge_search"
        assert allowed_tools[0].override_timeout_seconds == 25
        assert allowed_tools[0].override_max_retries == 2


class TestToolExecution:
    @pytest.mark.asyncio
    async def test_tool_execution_updates_run_state_and_logs_call(
        self,
        db_session: AsyncSession,
        db_engine,
        test_tenant: Tenant,
        test_user: User,
    ):
        registry = ToolRegistryService(db_session)
        await registry.register_tool_for_tenant(test_tenant.id, "knowledge_search")

        definition = await _create_tool_workflow(
            db_session,
            tenant_id=test_tenant.id,
            user_id=test_user.id,
            tool_name="knowledge_search",
            tool_input={
                "query": "shipping policy",
                "knowledge_items": [
                    {"id": "doc-1", "title": "Shipping Policy", "text": "Shipping policy and delivery timelines"},
                    {"id": "doc-2", "title": "Refund Terms", "text": "Refund policy and billing rules"},
                ],
            },
        )

        state_machine = RunStateMachine(db_session)
        run = await state_machine.create_run(
            workflow_definition_id=definition.id,
            tenant_id=test_tenant.id,
            idempotency_key="tool-success",
            triggered_by_user_id=test_user.id,
        )
        run = await state_machine.start_run(run, "test-worker")
        await db_session.commit()

        session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
        worker = WorkflowWorker(session_factory=session_factory, poll_interval=0.01)
        await worker._execute_run(db_session, run)

        run = await state_machine.get_run(run.id)
        tool_call_result = await db_session.execute(select(ToolCall).where(ToolCall.run_id == run.id))
        tool_call = tool_call_result.scalar_one()

        assert run.status == RunStatus.COMPLETED
        assert run.steps[0].status == StepStatus.COMPLETED
        assert "tool_outputs" in run.state
        assert run.state["tool_outputs"]["step_0"]["tool_name"] == "knowledge_search"
        assert run.state["knowledge_search_results"][0]["id"] == "doc-1"
        assert tool_call.status == ToolExecutionStatus.SUCCEEDED
        assert tool_call.failure_category == ToolFailureCategory.NONE

    @pytest.mark.asyncio
    async def test_tool_failures_are_categorized_consistently(
        self,
        db_session: AsyncSession,
        db_engine,
        test_tenant: Tenant,
        test_user: User,
    ):
        registry = ToolRegistryService(db_session)
        await registry.register_tool_for_tenant(test_tenant.id, "simple_analytics_query")

        definition = await _create_tool_workflow(
            db_session,
            tenant_id=test_tenant.id,
            user_id=test_user.id,
            tool_name="simple_analytics_query",
            tool_input={
                "operation": "median",
                "rows": [{"value": 10}, {"value": 20}],
            },
            max_retries=1,
        )

        state_machine = RunStateMachine(db_session)
        run = await state_machine.create_run(
            workflow_definition_id=definition.id,
            tenant_id=test_tenant.id,
            idempotency_key="tool-failure",
            triggered_by_user_id=test_user.id,
        )
        run = await state_machine.start_run(run, "test-worker")
        await db_session.commit()

        session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
        worker = WorkflowWorker(session_factory=session_factory, poll_interval=0.01)
        await worker._execute_run(db_session, run)

        run = await state_machine.get_run(run.id)
        tool_call_result = await db_session.execute(select(ToolCall).where(ToolCall.run_id == run.id))
        tool_call = tool_call_result.scalar_one()

        assert run.status == RunStatus.FAILED
        assert run.steps[0].status == StepStatus.FAILED
        assert run.steps[0].error_details["failure_category"] == ToolFailureCategory.VALIDATION.value
        assert tool_call.status == ToolExecutionStatus.FAILED
        assert tool_call.failure_category == ToolFailureCategory.VALIDATION