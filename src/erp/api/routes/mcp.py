"""Model Context Protocol (MCP) JSON-RPC 2.0 Transport Endpoint."""

from fastapi import APIRouter

from erp.api.deps import DbSessionDep, TenantIdDep
from erp.mcp.schemas import MCPRequest, MCPResponse
from erp.mcp.server import mcp_server

router = APIRouter(prefix="/mcp", tags=["Model Context Protocol"])


@router.post("", response_model=MCPResponse, summary="MCP JSON-RPC 2.0 Transport")
async def mcp_transport_endpoint(
    req: MCPRequest,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Processes standardized MCP JSON-RPC 2.0 tool requests (tools/list, tools/call)."""
    return await mcp_server.handle_request(
        request=req,
        session=db,
        tenant_id=tenant_id,
    )
