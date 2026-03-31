"""Agent router and planner API routes."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentTenantId, CurrentUserId
from app.db.planner_models import AgentRequest, PlanRecord
from app.db.session import get_db_session
from app.schemas.planner import (
    AgentRequestCreate,
    AgentRequestResponse,
    PlanList,
    PlanResponse,
)
from app.services.planner import PlannerService

router = APIRouter()


# =====================
# Intake
# =====================


@router.post("/intake", response_model=AgentRequestResponse, status_code=status.HTTP_201_CREATED)
async def intake_request(
    payload: AgentRequestCreate,
    tenant_id: CurrentTenantId,
    user_id: CurrentUserId,
    db: AsyncSession = Depends(get_db_session),
) -> AgentRequest:
    """Accept a new agent request, plan it, and route to a workflow."""
    svc = PlannerService(db)

    request = await svc.create_request(
        tenant_id=tenant_id,
        user_id=user_id,
        body=payload.body,
        context=payload.context,
        idempotency_key=payload.idempotency_key,
    )

    await svc.plan_and_route(request)
    await db.commit()

    # Reload with plan eagerly loaded
    refreshed = await svc.get_request_with_plan(request.id)
    if refreshed is None:
        raise HTTPException(status_code=500, detail="Failed to reload request after planning")
    return refreshed


# =====================
# Plans
# =====================


@router.get("/plans", response_model=PlanList)
async def list_plans(
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db_session),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> PlanList:
    """List plan records for the current tenant."""
    count_q = select(func.count(PlanRecord.id)).where(PlanRecord.tenant_id == tenant_id)
    total = (await db.execute(count_q)).scalar_one()

    items_q = (
        select(PlanRecord)
        .where(PlanRecord.tenant_id == tenant_id)
        .order_by(PlanRecord.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    items = (await db.execute(items_q)).scalars().all()

    return PlanList(items=items, total=total)


@router.get("/plans/{plan_id}", response_model=PlanResponse)
async def get_plan(
    plan_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db_session),
) -> PlanRecord:
    """Get a single plan record."""
    result = await db.execute(
        select(PlanRecord).where(
            PlanRecord.id == plan_id,
            PlanRecord.tenant_id == tenant_id,
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return record


# =====================
# Requests
# =====================


@router.get("/requests/{request_id}", response_model=AgentRequestResponse)
async def get_request(
    request_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db_session),
) -> AgentRequest:
    """Get a single agent request with its plan."""
    result = await db.execute(
        select(AgentRequest)
        .where(
            AgentRequest.id == request_id,
            AgentRequest.tenant_id == tenant_id,
        )
        .options(selectinload(AgentRequest.plan))
    )
    request = result.scalar_one_or_none()
    if request is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return request
