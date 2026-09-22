"""Unit & Integration Tests for Gmail OAuth 2.0 Persistence & Reload Resilience."""

import time
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from erp.db.engine import async_engine
from erp.db.models.tenant import Tenant, TenantOAuthConnection
from erp.db.session import async_session_factory
from erp.events.gmail_integration import GmailConnectionState, gmail_service


@pytest.fixture(autouse=True)
async def cleanup_engine():
    yield
    await async_engine.dispose()


@pytest.mark.asyncio
async def test_gmail_connection_persists_across_memory_clears():
    """Verifies that Gmail OAuth connection saved to PostgreSQL survives memory wipe (server restart/reload)."""
    tenant_id = uuid.uuid4()
    str_tid = str(tenant_id)

    # 1. Create tenant in DB
    async with async_session_factory() as session:
        tenant = Tenant(
            tenant_id=tenant_id,
            tenant_slug=f"tenant-{str_tid[:8]}",
            company_name="Acme Corp",
            currency="USD",
        )
        session.add(tenant)
        await session.commit()

    # 2. Simulate successful OAuth token exchange
    conn = GmailConnectionState(
        is_connected=True,
        connected_email="sales-lead@acme-corp.com",
        tenant_id=str_tid,
        access_token="ya29.initial_access_token_12345",
        refresh_token="1//refresh_token_permanent_67890",
        expires_at=time.time() + 3600,
        last_synced_at=datetime.now(UTC),
        synced_messages_count=5,
        is_configured=True,
    )
    await gmail_service.save_connection_to_db(str_tid, conn)

    # Verify record in PostgreSQL
    async with async_session_factory() as session:
        stmt = select(TenantOAuthConnection).where(
            TenantOAuthConnection.tenant_id == tenant_id,
            TenantOAuthConnection.provider == "google_gmail",
        )
        record = (await session.execute(stmt)).scalar_one_or_none()
        assert record is not None
        assert record.is_connected is True
        assert record.connected_email == "sales-lead@acme-corp.com"
        assert record.access_token == "ya29.initial_access_token_12345"
        assert record.refresh_token == "1//refresh_token_permanent_67890"

    # 3. Simulate process restart / page reload: completely wipe memory cache
    gmail_service.connections.clear()
    assert str_tid not in gmail_service.connections

    # 4. Load from DB via get_connection_async
    restored_conn = await gmail_service.get_connection_async(str_tid)
    assert restored_conn.is_connected is True
    assert restored_conn.connected_email == "sales-lead@acme-corp.com"
    assert restored_conn.access_token == "ya29.initial_access_token_12345"
    assert restored_conn.refresh_token == "1//refresh_token_permanent_67890"
    assert restored_conn.synced_messages_count == 5


@pytest.mark.asyncio
async def test_code_replay_does_not_wipe_active_session():
    """Verifies that an invalid/duplicate code exchange (e.g. from StrictMode or F5 reload)

    does not destroy an already active, valid Gmail OAuth connection.
    """
    tenant_id = uuid.uuid4()
    str_tid = str(tenant_id)

    async with async_session_factory() as session:
        tenant = Tenant(
            tenant_id=tenant_id,
            tenant_slug=f"tenant-{str_tid[:8]}",
            company_name="Beta Logistics",
            currency="USD",
        )
        session.add(tenant)
        await session.commit()

    # Setup active connection in DB & memory
    active_conn = GmailConnectionState(
        is_connected=True,
        connected_email="orders@betalogistics.com",
        tenant_id=str_tid,
        access_token="ya29.active_valid_token",
        refresh_token="1//active_refresh_token",
        expires_at=time.time() + 3600,
        is_configured=True,
    )
    await gmail_service.save_connection_to_db(str_tid, active_conn)
    gmail_service.connections[str_tid] = active_conn

    # Configure credentials so get_credentials passes
    gmail_service.save_credentials("dummy_client_id.apps.googleusercontent.com", "dummy_secret")

    # Simulate code replay: Google token endpoint responds with 400 invalid_grant
    mock_resp = AsyncMock()
    mock_resp.is_success = False
    mock_resp.status_code = 400
    mock_resp.headers = {"content-type": "application/json"}
    mock_resp.json = lambda: {"error": "invalid_grant", "error_description": "Bad Request"}
    mock_resp.text = "invalid_grant"

    with patch("httpx.AsyncClient.post", return_value=mock_resp):
        res = await gmail_service.exchange_code_for_tokens(
            tenant_id=str_tid,
            code="already_spent_authorization_code",
            redirect_uri="http://localhost:3000/inbox",
        )

        # Connection should STILL be connected, not destroyed
        assert res.is_connected is True
        assert res.connected_email == "orders@betalogistics.com"
        assert res.access_token == "ya29.active_valid_token"


@pytest.mark.asyncio
async def test_token_refresh_flow():
    """Verifies that expired access tokens are automatically renewed using refresh_token."""
    tenant_id = uuid.uuid4()
    str_tid = str(tenant_id)

    async with async_session_factory() as session:
        tenant = Tenant(
            tenant_id=tenant_id,
            tenant_slug=f"tenant-{str_tid[:8]}",
            company_name="Gamma Industries",
            currency="USD",
        )
        session.add(tenant)
        await session.commit()

    # Expired token (expires_at in past)
    expired_conn = GmailConnectionState(
        is_connected=True,
        connected_email="dispatch@gamma.com",
        tenant_id=str_tid,
        access_token="ya29.stale_expired_token",
        refresh_token="1//gamma_refresh_token",
        expires_at=time.time() - 300,  # Expired 5 mins ago
        is_configured=True,
    )
    await gmail_service.save_connection_to_db(str_tid, expired_conn)
    gmail_service.connections[str_tid] = expired_conn

    gmail_service.save_credentials("client_id_gamma", "client_secret_gamma")

    # Mock token refresh response
    mock_resp = AsyncMock()
    mock_resp.is_success = True
    mock_resp.json = lambda: {
        "access_token": "ya29.fresh_newly_refreshed_token",
        "expires_in": 3600,
        "token_type": "Bearer",
    }

    with patch("httpx.AsyncClient.post", return_value=mock_resp):
        refreshed = await gmail_service.ensure_valid_token(str_tid)
        assert refreshed.access_token == "ya29.fresh_newly_refreshed_token"
        assert refreshed.expires_at > time.time() + 3000

        # Verify persisted in PostgreSQL
        async with async_session_factory() as session:
            stmt = select(TenantOAuthConnection).where(
                TenantOAuthConnection.tenant_id == tenant_id,
                TenantOAuthConnection.provider == "google_gmail",
            )
            record = (await session.execute(stmt)).scalar_one_or_none()
            assert record is not None
            assert record.access_token == "ya29.fresh_newly_refreshed_token"


@pytest.mark.asyncio
async def test_disconnect_clears_db_and_memory():
    """Verifies that disconnecting revokes state in PostgreSQL and clears memory."""
    tenant_id = uuid.uuid4()
    str_tid = str(tenant_id)

    async with async_session_factory() as session:
        tenant = Tenant(
            tenant_id=tenant_id,
            tenant_slug=f"tenant-{str_tid[:8]}",
            company_name="Delta Aerospace",
            currency="USD",
        )
        session.add(tenant)
        await session.commit()

    conn = GmailConnectionState(
        is_connected=True,
        connected_email="admin@delta.com",
        tenant_id=str_tid,
        access_token="ya29.delta_token",
        refresh_token="1//delta_refresh",
        expires_at=time.time() + 3600,
        is_configured=True,
    )
    await gmail_service.save_connection_to_db(str_tid, conn)
    gmail_service.connections[str_tid] = conn

    # Disconnect
    await gmail_service.disconnect_async(str_tid)

    # Check memory
    assert gmail_service.get_connection(str_tid).is_connected is False

    # Check DB
    async with async_session_factory() as session:
        stmt = select(TenantOAuthConnection).where(
            TenantOAuthConnection.tenant_id == tenant_id,
            TenantOAuthConnection.provider == "google_gmail",
        )
        record = (await session.execute(stmt)).scalar_one_or_none()
        assert record is not None
        assert record.is_connected is False
        assert record.access_token is None
        assert record.refresh_token is None


@pytest.mark.asyncio
async def test_gmail_sync_deduplication_and_mark_read():
    """Verifies that calling sync_inbox multiple times never duplicates messages or re-triggers workflows."""
    from erp.events.email_gateway import mailbox

    tenant_id = uuid.uuid4()
    str_tid = str(tenant_id)

    async with async_session_factory() as session:
        tenant = Tenant(
            tenant_id=tenant_id,
            tenant_slug=f"tenant-{str_tid[:8]}",
            company_name="Echo Tech",
            currency="USD",
        )
        session.add(tenant)
        await session.commit()

    conn = GmailConnectionState(
        is_connected=True,
        connected_email="orders@echotech.com",
        tenant_id=str_tid,
        access_token="ya29.echo_valid_token",
        refresh_token="1//echo_refresh",
        expires_at=time.time() + 3600,
        is_configured=True,
    )
    await gmail_service.save_connection_to_db(str_tid, conn)
    gmail_service.connections[str_tid] = conn

    # Mock Gmail API HTTP responses
    mock_messages_list = {
        "messages": [
            {"id": "msg_echo_001", "threadId": "t_001"},
            {"id": "msg_echo_002", "threadId": "t_002"},
        ]
    }

    def make_msg_detail(msg_id: str):
        return {
            "id": msg_id,
            "snippet": f"Order inquiry for {msg_id}",
            "payload": {
                "headers": [
                    {"name": "From", "value": "Customer <client@test.com>"},
                    {"name": "To", "value": "orders@echotech.com"},
                    {"name": "Subject", "value": f"Order Subject {msg_id}"},
                ],
                "parts": [],
            },
        }

    modified_message_ids = []

    async def mock_get(url, headers=None, **kwargs):
        resp = AsyncMock()
        resp.is_success = True
        resp.status_code = 200
        if "messages?q=" in url:
            resp.json = lambda: mock_messages_list
        elif "messages/msg_echo_001" in url:
            resp.json = lambda: make_msg_detail("msg_echo_001")
        elif "messages/msg_echo_002" in url:
            resp.json = lambda: make_msg_detail("msg_echo_002")
        else:
            resp.json = lambda: {}
        return resp

    async def mock_post(url, headers=None, json=None, **kwargs):
        resp = AsyncMock()
        resp.is_success = True
        resp.status_code = 200
        resp.json = lambda: {"id": "modified"}
        if "modify" in url:
            for mid in ["msg_echo_001", "msg_echo_002"]:
                if mid in url:
                    modified_message_ids.append(mid)
        return resp

    with patch("httpx.AsyncClient.get", side_effect=mock_get), \
         patch("httpx.AsyncClient.post", side_effect=mock_post):

        # First sync: processes 2 messages
        sync_1 = await gmail_service.sync_inbox(str_tid)
        assert len(sync_1) == 2
        assert {m.message_id for m in sync_1} == {"msg_echo_001", "msg_echo_002"}
        assert "msg_echo_001" in gmail_service.processed_message_ids[str_tid]
        assert "msg_echo_002" in gmail_service.processed_message_ids[str_tid]
        assert "msg_echo_001" in modified_message_ids
        assert "msg_echo_002" in modified_message_ids

        # Second sync: Gmail still returns the same list, but deduplication drops them completely!
        sync_2 = await gmail_service.sync_inbox(str_tid)
        assert len(sync_2) == 0
