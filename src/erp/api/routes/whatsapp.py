"""Tenant administration and private message processing for WhatsApp support."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import logging
import re
import secrets
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any
from urllib.parse import urlencode

import httpx
from fastapi import (
    APIRouter,
    Depends,
    File,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, desc, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from erp.ai.whatsapp_support_agent import (
    DEFAULT_TOOLS,
    TOOL_DEFINITIONS,
    WhatsAppAgentConfigurationError,
    WhatsAppAgentProviderError,
    run_whatsapp_support_turn,
)
from erp.api.deps import CurrentUserDep, DbSessionDep, TenantIdDep, require_roles
from erp.config import settings
from erp.db.models.support import Issue
from erp.db.models.user import User
from erp.db.models.whatsapp import (
    WhatsAppAirtableConnection,
    WhatsAppConnection,
    WhatsAppConversation,
    WhatsAppMessage,
    WhatsAppSupportKnowledge,
    WhatsAppSupportKnowledgeSource,
    WhatsAppSupportToolBinding,
)
from erp.workflows.support import issue_service
from erp.workflows.support.whatsapp_knowledge import (
    MAX_UPLOAD_BYTES,
    KnowledgeImportError,
    airtable_access_token,
    airtable_request,
    airtable_token_expiry,
    chunk_knowledge,
    crawl_with_crawl4ai,
    encrypt_secret,
    exchange_airtable_code,
    extract_support_text,
    fetch_airtable_records,
    format_airtable_records,
    make_airtable_oauth_state,
    read_airtable_oauth_state,
    validate_public_web_url,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp Support"])
internal_router = APIRouter(prefix="/internal/whatsapp", tags=["Internal WhatsApp"])
tenant_admin_dep = require_roles("TENANT_ADMIN")


class WhatsAppToolBindingsRequest(BaseModel):
    enabled_tools: list[str] = Field(max_length=len(DEFAULT_TOOLS))


class WhatsAppInboundRequest(BaseModel):
    tenant_id: uuid.UUID
    provider_message_id: str = Field(min_length=1, max_length=255)
    phone_number: str = Field(min_length=1, max_length=32)
    text: str = Field(min_length=1, max_length=8000)
    contact_name: str | None = Field(default=None, max_length=255)


class WhatsAppDeliveryRequest(BaseModel):
    tenant_id: uuid.UUID
    message_id: uuid.UUID
    status: str = Field(pattern="^(SENT|FAILED)$")
    provider_message_id: str | None = Field(default=None, max_length=255)
    error: str | None = Field(default=None, max_length=1000)


class WhatsAppConnectionStatusRequest(BaseModel):
    tenant_id: uuid.UUID
    status: str = Field(pattern="^(DISCONNECTED|CONNECTING|QR_PENDING|CONNECTED|ERROR)$")
    phone_number: str | None = Field(default=None, max_length=32)
    last_error: str | None = Field(default=None, max_length=1000)


class WhatsAppReplyRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class WhatsAppKnowledgeRequest(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    content: str = Field(min_length=10, max_length=20000)


class WhatsAppKnowledgeLinkRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2048)


class WhatsAppAirtableImportRequest(BaseModel):
    base_id: str = Field(min_length=4, max_length=64, pattern=r"^app[A-Za-z0-9]+$")
    table_id: str = Field(min_length=4, max_length=64, pattern=r"^tbl[A-Za-z0-9]+$")
    fields: list[str] = Field(min_length=1, max_length=50)


def _serialize_knowledge_source(source: WhatsAppSupportKnowledgeSource) -> dict[str, Any]:
    return {
        "source_id": str(source.source_id),
        "source_type": source.source_type,
        "name": source.name,
        "status": source.status,
        "source_url": source.source_url,
        "airtable_base_id": source.airtable_base_id,
        "airtable_table_id": source.airtable_table_id,
        "airtable_table_name": source.airtable_table_name,
        "airtable_fields": source.airtable_fields,
        "chunk_count": source.chunk_count,
        "error_message": source.error_message,
        "created_at": source.created_at.isoformat(),
        "updated_at": source.updated_at.isoformat(),
    }


async def _airtable_connection(db: DbSessionDep, tenant_id: uuid.UUID):
    connection = (
        await db.execute(
            select(WhatsAppAirtableConnection).where(
                WhatsAppAirtableConnection.tenant_id == tenant_id,
                WhatsAppAirtableConnection.is_connected.is_(True),
            )
        )
    ).scalar_one_or_none()
    if connection is None:
        raise HTTPException(status_code=409, detail="Connect Airtable before importing a table.")
    try:
        token = await airtable_access_token(db, connection)
    except KnowledgeImportError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return connection, token


async def _import_airtable_table(
    *,
    db: DbSessionDep,
    tenant_id: uuid.UUID,
    base_id: str,
    table_id: str,
    selected_fields: list[str],
    source: WhatsAppSupportKnowledgeSource | None = None,
) -> WhatsAppSupportKnowledgeSource:
    _, access_token = await _airtable_connection(db, tenant_id)
    try:
        metadata = await airtable_request(
            access_token, f"/v0/meta/bases/{base_id}/tables"
        )
        tables = metadata.get("tables", [])
        table = next((item for item in tables if item.get("id") == table_id), None)
        if table is None:
            raise KnowledgeImportError("The selected table does not belong to the connected base.")
        available_fields = {
            field.get("name")
            for field in table.get("fields", [])
            if isinstance(field, dict) and field.get("name")
        }
        if not set(selected_fields) <= available_fields:
            raise KnowledgeImportError("One or more selected Airtable fields are no longer available.")
        records = await fetch_airtable_records(
            access_token, base_id, table_id, selected_fields
        )
        text = format_airtable_records(table["name"], records, selected_fields)
        chunks = chunk_knowledge(text)
    except KnowledgeImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if source is None:
        source = WhatsAppSupportKnowledgeSource(
            tenant_id=tenant_id,
            source_type="AIRTABLE",
            name=f"Airtable · {table['name']}",
        )
        db.add(source)
        await db.flush()
    else:
        await db.execute(
            delete(WhatsAppSupportKnowledge).where(
                WhatsAppSupportKnowledge.tenant_id == tenant_id,
                WhatsAppSupportKnowledge.source_id == source.source_id,
            )
        )

    source.name = f"Airtable · {table['name']}"
    source.status = "READY"
    source.error_message = None
    source.airtable_base_id = base_id
    source.airtable_table_id = table_id
    source.airtable_table_name = table["name"]
    source.airtable_fields = selected_fields
    source.chunk_count = len(chunks)
    for index, chunk in enumerate(chunks, start=1):
        db.add(
            WhatsAppSupportKnowledge(
                tenant_id=tenant_id,
                source_id=source.source_id,
                source_chunk=index,
                title=f"{source.name} · {index}",
                content=chunk,
            )
        )
    await db.flush()
    return source


async def _require_internal_token(
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
) -> None:
    expected = settings.WHATSAPP_INTERNAL_TOKEN
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WhatsApp internal service authentication is not configured.",
        )
    if not x_internal_token or not hmac.compare_digest(x_internal_token, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized.")


async def _call_whatsapp_service(
    method: str, path: str, *, json_body: dict[str, Any] | None = None
) -> dict[str, Any]:
    if not settings.WHATSAPP_SERVICE_URL or not settings.WHATSAPP_INTERNAL_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Baileys WhatsApp service is not configured.",
        )
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=5.0)) as client:
            response = await client.request(
                method,
                f"{settings.WHATSAPP_SERVICE_URL.rstrip('/')}{path}",
                headers={"X-Internal-Token": settings.WHATSAPP_INTERNAL_TOKEN},
                json=json_body,
            )
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError("WhatsApp service returned an invalid response.")
        return result
    except httpx.HTTPStatusError as exc:
        logger.warning("Baileys service returned HTTP %s.", exc.response.status_code)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Baileys WhatsApp service error ({exc.response.status_code}).",
        ) from exc
    except (httpx.HTTPError, ValueError) as exc:
        logger.exception("Baileys WhatsApp service request failed.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not reach the Baileys WhatsApp service.",
        ) from exc


def _serialize_conversation(conversation: WhatsAppConversation) -> dict[str, Any]:
    return {
        "conversation_id": str(conversation.conversation_id),
        "phone_number": conversation.phone_number,
        "contact_name": conversation.contact_name,
        "status": conversation.status,
        "issue_id": str(conversation.issue_id) if conversation.issue_id else None,
        "last_message_at": conversation.last_message_at.isoformat()
        if conversation.last_message_at
        else None,
        "created_at": conversation.created_at.isoformat(),
    }


def _serialize_message(message: WhatsAppMessage) -> dict[str, Any]:
    return {
        "message_id": str(message.message_id),
        "provider_message_id": message.provider_message_id,
        "direction": message.direction,
        "content": message.content,
        "delivery_status": message.delivery_status,
        "created_at": message.created_at.isoformat(),
        "sent_at": message.sent_at.isoformat() if message.sent_at else None,
    }


@router.post("/connect")
async def connect_whatsapp(tenant_id: TenantIdDep, _admin: User = tenant_admin_dep):
    return await _call_whatsapp_service("POST", f"/tenants/{tenant_id}/connect", json_body={})


@router.delete("/connect")
async def disconnect_whatsapp(tenant_id: TenantIdDep, _admin: User = tenant_admin_dep):
    return await _call_whatsapp_service("DELETE", f"/tenants/{tenant_id}/connect")


@router.get("/status")
async def get_whatsapp_status(tenant_id: TenantIdDep, _user: CurrentUserDep):
    status_response = await _call_whatsapp_service("GET", f"/tenants/{tenant_id}/status")
    return status_response


@router.get("/conversations")
async def list_whatsapp_conversations(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    _user: CurrentUserDep,
    limit: int = Query(50, ge=1, le=200),
):
    rows = list(
        (
            await db.execute(
                select(WhatsAppConversation)
                .where(WhatsAppConversation.tenant_id == tenant_id)
                .order_by(desc(WhatsAppConversation.last_message_at))
                .limit(limit)
            )
        ).scalars().all()
    )
    return {"conversations": [_serialize_conversation(row) for row in rows]}


@router.get("/conversations/{conversation_id}")
async def get_whatsapp_conversation(
    conversation_id: uuid.UUID,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    _user: CurrentUserDep,
):
    conversation = (
        await db.execute(
            select(WhatsAppConversation).where(
                WhatsAppConversation.conversation_id == conversation_id,
                WhatsAppConversation.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="WhatsApp conversation not found.")
    messages = list(
        (
            await db.execute(
                select(WhatsAppMessage)
                .where(
                    WhatsAppMessage.tenant_id == tenant_id,
                    WhatsAppMessage.conversation_id == conversation_id,
                )
                .order_by(WhatsAppMessage.created_at.asc())
            )
        ).scalars().all()
    )
    issue = None
    if conversation.issue_id:
        issue = (
            await db.execute(
                select(Issue).where(
                    Issue.issue_id == conversation.issue_id, Issue.tenant_id == tenant_id
                )
            )
        ).scalar_one_or_none()
    return {
        "conversation": _serialize_conversation(conversation),
        "messages": [_serialize_message(row) for row in messages],
        "issue": (
            {
                "issue_id": str(issue.issue_id),
                "issue_number": issue.issue_number,
                "subject": issue.subject,
                "status": issue.status,
                "priority": issue.priority,
            }
            if issue
            else None
        ),
    }


@router.post("/conversations/{conversation_id}/reply", status_code=status.HTTP_201_CREATED)
async def reply_to_whatsapp_conversation(
    conversation_id: uuid.UUID,
    payload: WhatsAppReplyRequest,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    _admin: User = tenant_admin_dep,
):
    conversation = (
        await db.execute(
            select(WhatsAppConversation).where(
                WhatsAppConversation.conversation_id == conversation_id,
                WhatsAppConversation.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="WhatsApp conversation not found.")
    sent = await _call_whatsapp_service(
        "POST",
        f"/tenants/{tenant_id}/send",
        json_body={"to": conversation.phone_number, "message": payload.text},
    )
    message = WhatsAppMessage(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        provider_message_id=sent.get("message_id"),
        direction="OUTBOUND",
        content=payload.text,
        delivery_status="SENT",
        sent_at=datetime.now(UTC),
        metadata_json={"sender": "human_support"},
    )
    db.add(message)
    conversation.status = "ACTIVE"
    conversation.last_message_at = datetime.now(UTC)
    if conversation.issue_id:
        await issue_service.add_communication(
            session=db,
            tenant_id=tenant_id,
            issue_id=conversation.issue_id,
            sender_type="AGENT",
            sender_name="Human Support",
            message=payload.text,
        )
    await db.flush()
    return _serialize_message(message)


@router.get("/tools")
async def list_whatsapp_tools(
    tenant_id: TenantIdDep, db: DbSessionDep, _user: CurrentUserDep
):
    rows = list(
        (
            await db.execute(
                select(WhatsAppSupportToolBinding).where(
                    WhatsAppSupportToolBinding.tenant_id == tenant_id
                )
            )
        ).scalars().all()
    )
    enabled = {row.tool_name for row in rows if row.is_enabled} if rows else set(DEFAULT_TOOLS)
    return {
        "tools": [
            {"name": name, "description": item["description"], "enabled": name in enabled}
            for name, item in TOOL_DEFINITIONS.items()
        ]
    }


@router.put("/tools")
async def update_whatsapp_tools(
    payload: WhatsAppToolBindingsRequest,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    _admin: User = tenant_admin_dep,
):
    enabled = set(payload.enabled_tools)
    unknown = enabled - set(TOOL_DEFINITIONS)
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown WhatsApp support tools: {', '.join(sorted(unknown))}.",
        )
    for name in TOOL_DEFINITIONS:
        stmt = pg_insert(WhatsAppSupportToolBinding).values(
            tenant_id=tenant_id, tool_name=name, is_enabled=name in enabled, config={}
        )
        await db.execute(
            stmt.on_conflict_do_update(
                constraint="uq_whatsapp_support_tool_tenant",
                set_={"is_enabled": stmt.excluded.is_enabled},
            )
        )
    return {"enabled_tools": sorted(enabled)}


@router.get("/knowledge")
async def list_whatsapp_knowledge(
    tenant_id: TenantIdDep, db: DbSessionDep, _user: CurrentUserDep
):
    entries = list(
        (
            await db.execute(
                select(WhatsAppSupportKnowledge)
                .where(WhatsAppSupportKnowledge.tenant_id == tenant_id)
                .where(WhatsAppSupportKnowledge.source_id.is_(None))
                .order_by(WhatsAppSupportKnowledge.updated_at.desc())
            )
        ).scalars().all()
    )
    return {
        "entries": [
            {
                "knowledge_id": str(entry.knowledge_id),
                "title": entry.title,
                "content": entry.content,
                "updated_at": entry.updated_at.isoformat(),
            }
            for entry in entries
        ]
    }


@router.post("/knowledge", status_code=status.HTTP_201_CREATED)
async def create_whatsapp_knowledge(
    payload: WhatsAppKnowledgeRequest,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    _admin: User = tenant_admin_dep,
):
    entry = WhatsAppSupportKnowledge(
        tenant_id=tenant_id,
        title=payload.title.strip(),
        content=payload.content.strip(),
    )
    db.add(entry)
    await db.flush()
    return {
        "knowledge_id": str(entry.knowledge_id),
        "title": entry.title,
        "content": entry.content,
        "updated_at": entry.updated_at.isoformat(),
    }


@router.delete("/knowledge/{knowledge_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_whatsapp_knowledge(
    knowledge_id: uuid.UUID,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    _admin: User = tenant_admin_dep,
):
    entry = (
        await db.execute(
            select(WhatsAppSupportKnowledge).where(
                WhatsAppSupportKnowledge.knowledge_id == knowledge_id,
                WhatsAppSupportKnowledge.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="WhatsApp support knowledge entry not found.")
    await db.delete(entry)


@router.get("/knowledge/sources")
async def list_whatsapp_knowledge_sources(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    _user: CurrentUserDep,
):
    rows = list(
        (
            await db.execute(
                select(WhatsAppSupportKnowledgeSource)
                .where(WhatsAppSupportKnowledgeSource.tenant_id == tenant_id)
                .order_by(WhatsAppSupportKnowledgeSource.created_at.desc())
                .limit(200)
            )
        ).scalars().all()
    )
    return {"sources": [_serialize_knowledge_source(source) for source in rows]}


@router.post("/knowledge/files", status_code=status.HTTP_201_CREATED)
async def upload_whatsapp_knowledge_file(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    file: Annotated[UploadFile, File()],
    _admin: User = tenant_admin_dep,
):
    filename = (file.filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not filename or len(filename) > 255:
        raise HTTPException(status_code=400, detail="Choose a file with a valid filename.")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    await file.close()
    try:
        extracted = await asyncio.to_thread(extract_support_text, filename, data)
        chunks = chunk_knowledge(extracted)
    except KnowledgeImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    source = WhatsAppSupportKnowledgeSource(
        tenant_id=tenant_id,
        source_type="FILE",
        name=filename,
        status="READY",
        chunk_count=len(chunks),
    )
    db.add(source)
    await db.flush()
    for index, chunk in enumerate(chunks, start=1):
        db.add(
            WhatsAppSupportKnowledge(
                tenant_id=tenant_id,
                source_id=source.source_id,
                source_chunk=index,
                title=f"{filename} · {index}",
                content=chunk,
            )
        )
    await db.flush()
    return {"source": _serialize_knowledge_source(source)}


@router.post("/knowledge/links", status_code=status.HTTP_201_CREATED)
async def import_whatsapp_knowledge_link(
    payload: WhatsAppKnowledgeLinkRequest,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    _admin: User = tenant_admin_dep,
):
    raw_url = payload.url.strip()
    try:
        safe_url = await validate_public_web_url(raw_url)
        content = await crawl_with_crawl4ai(safe_url)
        chunks = chunk_knowledge(content)
    except KnowledgeImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    source = WhatsAppSupportKnowledgeSource(
        tenant_id=tenant_id,
        source_type="WEB",
        name=safe_url[:512],
        status="READY",
        source_url=safe_url,
        chunk_count=len(chunks),
    )
    db.add(source)
    await db.flush()
    for index, chunk in enumerate(chunks, start=1):
        db.add(
            WhatsAppSupportKnowledge(
                tenant_id=tenant_id,
                source_id=source.source_id,
                source_chunk=index,
                title=f"Web page · {safe_url[:180]} · {index}",
                content=chunk,
            )
        )
    await db.flush()
    return {"source": _serialize_knowledge_source(source)}


@router.delete("/knowledge/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_whatsapp_knowledge_source(
    source_id: uuid.UUID,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    _admin: User = tenant_admin_dep,
):
    source = (
        await db.execute(
            select(WhatsAppSupportKnowledgeSource).where(
                WhatsAppSupportKnowledgeSource.source_id == source_id,
                WhatsAppSupportKnowledgeSource.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=404, detail="WhatsApp knowledge source not found.")
    await db.delete(source)


@router.get("/airtable/status")
async def get_whatsapp_airtable_status(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    _user: CurrentUserDep,
):
    connection = (
        await db.execute(
            select(WhatsAppAirtableConnection).where(
                WhatsAppAirtableConnection.tenant_id == tenant_id,
                WhatsAppAirtableConnection.is_connected.is_(True),
            )
        )
    ).scalar_one_or_none()
    return {"connected": connection is not None}


@router.get("/airtable/connect")
async def connect_whatsapp_airtable(
    request: Request,
    tenant_id: TenantIdDep,
    _admin: User = tenant_admin_dep,
):
    if not settings.AIRTABLE_CLIENT_ID or not settings.AIRTABLE_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="Airtable OAuth is not configured.")
    if not settings.AIRTABLE_REDIRECT_URI:
        raise HTTPException(status_code=503, detail="AIRTABLE_REDIRECT_URI is not configured.")
    frontend_origin = request.headers.get("origin", "").rstrip("/")
    allowed_origins = {origin.rstrip("/") for origin in settings.CORS_ALLOWED_ORIGINS}
    if not frontend_origin or frontend_origin not in allowed_origins:
        raise HTTPException(status_code=400, detail="The frontend origin is not allowed for OAuth.")
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
    try:
        state = make_airtable_oauth_state(str(tenant_id), frontend_origin, verifier)
    except KnowledgeImportError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).decode().rstrip("=")
    query = urlencode(
        {
            "client_id": settings.AIRTABLE_CLIENT_ID,
            "redirect_uri": settings.AIRTABLE_REDIRECT_URI,
            "response_type": "code",
            "scope": "data.records:read schema.bases:read",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    return {"authorization_url": f"https://airtable.com/oauth2/v1/authorize?{query}"}


@router.get("/airtable/callback", include_in_schema=False)
async def whatsapp_airtable_oauth_callback(
    db: DbSessionDep,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    if not state:
        raise HTTPException(status_code=400, detail="Airtable authorization state is missing.")
    try:
        payload = read_airtable_oauth_state(
            state, [origin.rstrip("/") for origin in settings.CORS_ALLOWED_ORIGINS]
        )
    except KnowledgeImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return_url = f"{payload['frontend_origin']}/whatsapp"
    if error or not code:
        return RedirectResponse(f"{return_url}?airtable=error", status_code=303)
    if not settings.AIRTABLE_CLIENT_ID or not settings.AIRTABLE_CLIENT_SECRET:
        return RedirectResponse(f"{return_url}?airtable=not-configured", status_code=303)
    try:
        tokens = await exchange_airtable_code(code, payload["verifier"])
        if not isinstance(tokens.get("access_token"), str) or not tokens["access_token"]:
            raise KnowledgeImportError("Airtable did not return an access token.")
        connection = (
            await db.execute(
                select(WhatsAppAirtableConnection).where(
                    WhatsAppAirtableConnection.tenant_id == uuid.UUID(payload["tenant_id"])
                )
            )
        ).scalar_one_or_none()
        encrypted_tokens = encrypt_secret(tokens)
        expires_at = airtable_token_expiry(tokens)
        if connection is None:
            connection = WhatsAppAirtableConnection(
                tenant_id=uuid.UUID(payload["tenant_id"]),
                encrypted_tokens=encrypted_tokens,
                token_expires_at=expires_at,
                is_connected=True,
            )
            db.add(connection)
        else:
            connection.encrypted_tokens = encrypted_tokens
            connection.token_expires_at = expires_at
            connection.is_connected = True
            connection.connected_at = datetime.now(UTC)
        await db.flush()
        return RedirectResponse(f"{return_url}?airtable=connected", status_code=303)
    except KnowledgeImportError:
        logger.warning("Airtable OAuth callback failed to complete token exchange.")
        return RedirectResponse(f"{return_url}?airtable=error", status_code=303)


@router.delete("/airtable/connect", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_whatsapp_airtable(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    _admin: User = tenant_admin_dep,
):
    await db.execute(
        delete(WhatsAppAirtableConnection).where(
            WhatsAppAirtableConnection.tenant_id == tenant_id
        )
    )


@router.get("/airtable/bases")
async def list_whatsapp_airtable_bases(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    _admin: User = tenant_admin_dep,
):
    _, access_token = await _airtable_connection(db, tenant_id)
    bases: list[dict] = []
    offset: str | None = None
    try:
        while True:
            params = {"offset": offset} if offset else None
            result = await airtable_request(
                access_token, "/v0/meta/bases", params=params
            )
            bases.extend(
                {"id": base["id"], "name": base.get("name", base["id"])}
                for base in result.get("bases", [])
                if isinstance(base, dict) and base.get("id")
            )
            if len(bases) > 500:
                raise KnowledgeImportError(
                    "This Airtable account exposes too many bases to list at once."
                )
            offset = result.get("offset")
            if not offset:
                break
    except KnowledgeImportError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"bases": bases}


@router.get("/airtable/bases/{base_id}/tables")
async def list_whatsapp_airtable_tables(
    base_id: str,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    _admin: User = tenant_admin_dep,
):
    if not re.fullmatch(r"app[A-Za-z0-9]+", base_id):
        raise HTTPException(status_code=422, detail="Invalid Airtable base identifier.")
    _, access_token = await _airtable_connection(db, tenant_id)
    try:
        result = await airtable_request(
            access_token, f"/v0/meta/bases/{base_id}/tables"
        )
    except KnowledgeImportError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "tables": [
            {
                "id": table["id"],
                "name": table.get("name", table["id"]),
                "fields": [
                    field["name"]
                    for field in table.get("fields", [])
                    if isinstance(field, dict) and field.get("name")
                ],
            }
            for table in result.get("tables", [])
            if isinstance(table, dict) and table.get("id")
        ]
    }


@router.post("/airtable/import", status_code=status.HTTP_201_CREATED)
async def import_whatsapp_airtable_table(
    payload: WhatsAppAirtableImportRequest,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    _admin: User = tenant_admin_dep,
):
    fields = list(dict.fromkeys(field.strip() for field in payload.fields if field.strip()))
    if not fields:
        raise HTTPException(status_code=422, detail="Select at least one Airtable field to import.")
    source = await _import_airtable_table(
        db=db,
        tenant_id=tenant_id,
        base_id=payload.base_id,
        table_id=payload.table_id,
        selected_fields=fields,
    )
    return {"source": _serialize_knowledge_source(source)}


@router.post("/airtable/sources/{source_id}/sync")
async def sync_whatsapp_airtable_source(
    source_id: uuid.UUID,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    _admin: User = tenant_admin_dep,
):
    source = (
        await db.execute(
            select(WhatsAppSupportKnowledgeSource).where(
                WhatsAppSupportKnowledgeSource.source_id == source_id,
                WhatsAppSupportKnowledgeSource.tenant_id == tenant_id,
                WhatsAppSupportKnowledgeSource.source_type == "AIRTABLE",
            )
        )
    ).scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=404, detail="Airtable knowledge source not found.")
    source = await _import_airtable_table(
        db=db,
        tenant_id=tenant_id,
        base_id=source.airtable_base_id or "",
        table_id=source.airtable_table_id or "",
        selected_fields=source.airtable_fields or [],
        source=source,
    )
    return {"source": _serialize_knowledge_source(source)}


@internal_router.post("/inbound", dependencies=[Depends(_require_internal_token)])
async def process_whatsapp_inbound(payload: WhatsAppInboundRequest, db: DbSessionDep):
    if payload.phone_number.startswith("lid:"):
        phone = payload.phone_number
        if not re.fullmatch(r"lid:\d{1,20}", phone):
            raise HTTPException(status_code=400, detail="Invalid WhatsApp LID.")
    else:
        phone = re.sub(r"\D", "", payload.phone_number)
        if not 7 <= len(phone) <= 15:
            raise HTTPException(status_code=400, detail="Invalid WhatsApp phone number.")
    await db.execute(
        pg_insert(WhatsAppConversation)
        .values(
            tenant_id=payload.tenant_id,
            phone_number=phone,
            contact_name=payload.contact_name,
            status="ACTIVE",
            last_message_at=datetime.now(UTC),
        )
        .on_conflict_do_nothing(constraint="uq_whatsapp_conversation_phone")
    )
    conversation = (
        await db.execute(
            select(WhatsAppConversation)
            .where(
                WhatsAppConversation.tenant_id == payload.tenant_id,
                WhatsAppConversation.phone_number == phone,
            )
            .with_for_update()
        )
    ).scalar_one()
    if payload.contact_name and not conversation.contact_name:
        conversation.contact_name = payload.contact_name

    duplicate = (
        await db.execute(
            select(WhatsAppMessage).where(
                WhatsAppMessage.tenant_id == payload.tenant_id,
                WhatsAppMessage.provider_message_id == payload.provider_message_id,
                WhatsAppMessage.direction == "INBOUND",
            )
        )
    ).scalar_one_or_none()
    if duplicate:
        reply = (
            await db.execute(
                select(WhatsAppMessage)
                .where(
                    WhatsAppMessage.tenant_id == payload.tenant_id,
                    WhatsAppMessage.conversation_id == conversation.conversation_id,
                    WhatsAppMessage.direction == "OUTBOUND",
                    WhatsAppMessage.metadata_json["reply_to_provider_message_id"].astext
                    == payload.provider_message_id,
                )
                .order_by(WhatsAppMessage.created_at.asc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if reply:
            return {
                "message_id": str(reply.message_id),
                "answer": reply.content,
                "should_send": reply.delivery_status != "SENT",
                "human_handoff": conversation.status == "HUMAN_HANDOFF",
            }
        inbound = duplicate
    else:
        inbound = WhatsAppMessage(
            tenant_id=payload.tenant_id,
            conversation_id=conversation.conversation_id,
            provider_message_id=payload.provider_message_id,
            direction="INBOUND",
            content=payload.text.strip(),
            delivery_status="RECEIVED",
        )
        db.add(inbound)

    prior_messages = list(
        (
            await db.execute(
                select(WhatsAppMessage)
                .where(
                    WhatsAppMessage.tenant_id == payload.tenant_id,
                    WhatsAppMessage.conversation_id == conversation.conversation_id,
                )
                .order_by(WhatsAppMessage.created_at.desc())
                .limit(20)
            )
        ).scalars().all()
    )
    prior_messages = [row for row in prior_messages if row.message_id != inbound.message_id]
    conversation.last_message_at = datetime.now(UTC)
    await db.flush()

    if conversation.status == "HUMAN_HANDOFF":
        if conversation.issue_id:
            await issue_service.add_communication(
                session=db,
                tenant_id=payload.tenant_id,
                issue_id=conversation.issue_id,
                sender_type="CUSTOMER",
                sender_name=conversation.contact_name or phone,
                message=payload.text.strip(),
            )
        return {
            "message_id": None,
            "answer": None,
            "should_send": False,
            "human_handoff": True,
        }

    history = [
        {
            "role": "user" if row.direction == "INBOUND" else "assistant",
            "content": row.content,
        }
        for row in reversed(prior_messages)
    ]
    try:
        answer, handoff = await run_whatsapp_support_turn(
            db=db,
            tenant_id=payload.tenant_id,
            conversation=conversation,
            inbound_text=payload.text.strip(),
            history=history,
        )
    except WhatsAppAgentConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except WhatsAppAgentProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    outbound = WhatsAppMessage(
        tenant_id=payload.tenant_id,
        conversation_id=conversation.conversation_id,
        direction="OUTBOUND",
        content=answer,
        delivery_status="PENDING",
        metadata_json={"reply_to_provider_message_id": payload.provider_message_id},
    )
    db.add(outbound)
    await db.flush()
    return {
        "message_id": str(outbound.message_id),
        "conversation_id": str(conversation.conversation_id),
        "answer": answer,
        "should_send": True,
        "human_handoff": handoff,
    }


@internal_router.post("/delivery", dependencies=[Depends(_require_internal_token)])
async def update_whatsapp_delivery(payload: WhatsAppDeliveryRequest, db: DbSessionDep):
    values: dict[str, Any] = {"delivery_status": payload.status}
    if payload.status == "SENT":
        values["provider_message_id"] = payload.provider_message_id
        values["sent_at"] = datetime.now(UTC)
    if payload.error:
        values["metadata_json"] = {"delivery_error": payload.error[:500]}
    result = await db.execute(
        update(WhatsAppMessage)
        .where(
            WhatsAppMessage.message_id == payload.message_id,
            WhatsAppMessage.tenant_id == payload.tenant_id,
            WhatsAppMessage.direction == "OUTBOUND",
        )
        .values(**values)
    )
    if not result.rowcount:
        raise HTTPException(status_code=404, detail="Outbound WhatsApp message not found.")
    return {"status": payload.status}


@internal_router.post("/connection-status", dependencies=[Depends(_require_internal_token)])
async def update_whatsapp_connection_status(
    payload: WhatsAppConnectionStatusRequest,
    db: DbSessionDep,
):
    now = datetime.now(UTC)
    stmt = pg_insert(WhatsAppConnection).values(
        tenant_id=payload.tenant_id,
        status=payload.status,
        phone_number=payload.phone_number,
        connected_at=now if payload.status == "CONNECTED" else None,
        last_error=payload.last_error,
    )
    await db.execute(
        stmt.on_conflict_do_update(
            index_elements=["tenant_id"],
            set_={
                "status": stmt.excluded.status,
                "phone_number": stmt.excluded.phone_number,
                "connected_at": (
                    stmt.excluded.connected_at
                    if payload.status == "CONNECTED"
                    else WhatsAppConnection.connected_at
                ),
                "last_error": stmt.excluded.last_error,
                "updated_at": now,
            },
        )
    )
    return {"status": payload.status}
