import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId
from app.db.session import get_db_session
from app.db.tool_models import ToolCall
from app.db.workflow_models import WorkflowRun
from app.schemas.tools import (
    ToolCallResponse,
    ToolCallList,
    TenantToolRegistrationCreate,
    TenantToolRegistrationList,
    TenantToolRegistrationResponse,
)
from app.services.tool_adapter import ToolExecutionError, ToolRegistryService

router = APIRouter()


@router.get("", response_model=TenantToolRegistrationList)
async def list_allowed_tools(
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db_session),
) -> TenantToolRegistrationList:
    registry = ToolRegistryService(db)
    await registry.sync_internal_tool_definitions()
    items = await registry.list_allowed_tools(tenant_id)
    return TenantToolRegistrationList(items=items, total=len(items))


@router.get("/calls", response_model=ToolCallList)
async def list_tool_calls(
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db_session),
    run_id: uuid.UUID | None = None,
    tool_name: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> ToolCallList:
    query = select(ToolCall).where(ToolCall.tenant_id == tenant_id)

    if run_id is not None:
        query = query.where(ToolCall.run_id == run_id)
    if tool_name is not None:
        query = query.where(ToolCall.tool_name == tool_name)
    if status_filter is not None:
        query = query.where(ToolCall.status == status_filter)

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    result = await db.execute(
        query.order_by(ToolCall.started_at.desc()).offset(skip).limit(limit)
    )
    items = result.scalars().all()
    return ToolCallList(items=list(items), total=total)


@router.get("/calls/{tool_call_id}", response_model=ToolCallResponse)
async def get_tool_call(
    tool_call_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db_session),
) -> ToolCall:
    result = await db.execute(
        select(ToolCall).where(
            ToolCall.id == tool_call_id,
            ToolCall.tenant_id == tenant_id,
        )
    )
    tool_call = result.scalar_one_or_none()
    if tool_call is None:
        raise HTTPException(status_code=404, detail="Tool call not found")
    return tool_call


@router.get("/runs/{run_id}/calls", response_model=ToolCallList)
async def list_run_tool_calls(
    run_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db_session),
) -> ToolCallList:
    run_result = await db.execute(
        select(WorkflowRun).where(
            WorkflowRun.id == run_id,
            WorkflowRun.tenant_id == tenant_id,
        )
    )
    run = run_result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    result = await db.execute(
        select(ToolCall)
        .where(
            ToolCall.tenant_id == tenant_id,
            ToolCall.run_id == run_id,
        )
        .order_by(ToolCall.started_at.desc())
    )
    items = result.scalars().all()
    return ToolCallList(items=list(items), total=len(items))


@router.post(
    "/registrations",
    response_model=TenantToolRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_tool_for_tenant(
    payload: TenantToolRegistrationCreate,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db_session),
) -> TenantToolRegistrationResponse:
    registry = ToolRegistryService(db)
    try:
        registration = await registry.register_tool_for_tenant(
            tenant_id=tenant_id,
            tool_name=payload.tool_name,
            enabled=payload.enabled,
            override_timeout_seconds=payload.override_timeout_seconds,
            override_max_retries=payload.override_max_retries,
            metadata_json=payload.metadata_json,
        )
    except ToolExecutionError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await db.commit()
    await db.refresh(registration, ["tool_definition"])
    return registration