import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, CurrentUserId
from app.db.session import get_db_session
from app.schemas.mcp import (
    MCPAuthConfigCreate,
    MCPAuthConfigList,
    MCPAuthConfigResponse,
    MCPHealthCheckResponse,
    MCPServerCreate,
    MCPServerList,
    MCPServerResponse,
    MCPSyncResponse,
)
from app.services.mcp import MCPRemoteError, MCPService
from app.services.tool_adapter import ToolExecutionError

router = APIRouter()


@router.post("/auth-configs", response_model=MCPAuthConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_auth_config(
    payload: MCPAuthConfigCreate,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db_session),
) -> MCPAuthConfigResponse:
    service = MCPService(db)
    # secret_ref validation is now handled by the Pydantic schema validator
    auth_config = await service.create_auth_config(
        tenant_id=tenant_id,
        name=payload.name,
        auth_type=payload.auth_type,
        header_name=payload.header_name,
        secret_ref=payload.secret_ref,
        metadata_json=payload.metadata_json,
    )
    await db.commit()
    await db.refresh(auth_config)
    return auth_config


@router.get("/auth-configs", response_model=MCPAuthConfigList)
async def list_auth_configs(
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db_session),
) -> MCPAuthConfigList:
    service = MCPService(db)
    items = await service.list_auth_configs(tenant_id)
    return MCPAuthConfigList(items=items, total=len(items))


@router.post("/servers", response_model=MCPServerResponse, status_code=status.HTTP_201_CREATED)
async def create_server(
    payload: MCPServerCreate,
    tenant_id: CurrentTenantId,
    user_id: CurrentUserId,
    db: AsyncSession = Depends(get_db_session),
) -> MCPServerResponse:
    service = MCPService(db)
    try:
        server = await service.create_server(
            tenant_id=tenant_id,
            user_id=user_id,
            name=payload.name,
            base_url=str(payload.base_url),
            enabled=payload.enabled,
            auth_config_id=payload.auth_config_id,
            health_path=payload.health_path,
            tools_path=payload.tools_path,
            invoke_path_template=payload.invoke_path_template,
            scope_filter=payload.scope_filter,
            timeout_seconds=payload.timeout_seconds,
            max_retries=payload.max_retries,
            descriptor_metadata_json=payload.descriptor_metadata_json,
        )
    except ToolExecutionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await db.commit()
    await db.refresh(server)
    return server


@router.get("/servers", response_model=MCPServerList)
async def list_servers(
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db_session),
) -> MCPServerList:
    service = MCPService(db)
    items = await service.list_servers(tenant_id)
    return MCPServerList(items=items, total=len(items))


@router.post("/servers/{server_id}/health-check", response_model=MCPHealthCheckResponse)
async def health_check_server(
    server_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db_session),
) -> MCPHealthCheckResponse:
    service = MCPService(db)
    try:
        server = await service.get_server(tenant_id, server_id)
        server = await service.check_health(server)
    except ToolExecutionError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await db.commit()
    await db.refresh(server)
    return MCPHealthCheckResponse(server=server)


@router.post("/servers/{server_id}/sync", response_model=MCPSyncResponse)
async def sync_server_tools(
    server_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db_session),
) -> MCPSyncResponse:
    service = MCPService(db)
    try:
        server = await service.get_server(tenant_id, server_id)
        result = await service.sync_server_tools(server)
    except ToolExecutionError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except MCPRemoteError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    await db.commit()
    await db.refresh(server)
    return MCPSyncResponse(
        server=server,
        discovered_tool_names=result.discovered_tool_names,
        synced_count=result.synced_count,
        disabled_count=result.disabled_count,
    )
