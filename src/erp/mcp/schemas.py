"""Model Context Protocol (MCP) JSON-RPC 2.0 Schemas."""

from typing import Any

from pydantic import BaseModel, Field


class MCPToolDefinition(BaseModel):
    name: str
    description: str
    inputSchema: dict[str, Any]


class MCPRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: str | int
    method: str
    params: dict[str, Any] = Field(default_factory=dict)


class MCPTextContent(BaseModel):
    type: str = "text"
    text: str


class MCPResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: str | int
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
