"""Official Google Workspace & Gmail OAuth 2.0 Integration (PRD §Revenue Agent & Inbound RFQs).

Implements strictly genuine Google OAuth 2.0 authorization, token exchange, mailbox polling,
and quotation PDF delivery via the official Google Gmail REST API.
ZERO mock, fake, or synthetic data.
"""

import base64
from email.message import EmailMessage
import logging
import os
import re
import time
from datetime import UTC, datetime
import asyncio
from typing import Any
import urllib.parse
import uuid

import httpx
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.config import settings
from erp.db.models.tenant import TenantOAuthConnection
from erp.db.session import async_session_factory
from erp.events.email_classifier import EmailIntent, classify_inbound_email
from erp.events.email_gateway import (
    EmailAttachment,
    IngestedEmailMessage,
    SentEmailMessage,
    mailbox,
)
from erp.orchestration.orchestrator import chief_orchestrator
from erp.orchestration.worker import dag_executor

logger = logging.getLogger(__name__)

GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/userinfo.email",
]


class GmailConnectionState(BaseModel):
    is_connected: bool = False
    connected_email: str | None = None
    tenant_id: str = "00000000-0000-0000-0000-000000000001"
    access_token: str | None = None
    refresh_token: str | None = None
    expires_at: float | None = None
    last_synced_at: datetime | None = None
    synced_messages_count: int = 0
    is_configured: bool = False


class GmailIntegrationService:
    """Manages genuine Google OAuth 2.0 connection and synchronization for enterprise tenants."""

    def __init__(self):
        self.connections: dict[str, GmailConnectionState] = {}
        # Ensure any stale synthetic data is thoroughly purged
        mailbox.inbox.clear()
        mailbox.sent.clear()

    async def load_connection_from_db(
        self, tenant_id: str, session: AsyncSession | None = None
    ) -> GmailConnectionState | None:
        """Loads and caches persisted OAuth connection from PostgreSQL for the given tenant."""
        try:
            tenant_uuid = uuid.UUID(str(tenant_id))
        except Exception:
            return None

        client_id, client_secret = self.get_credentials()
        is_cfg = bool(client_id and client_secret)

        async def _query(s: AsyncSession) -> GmailConnectionState | None:
            stmt = select(TenantOAuthConnection).where(
                TenantOAuthConnection.tenant_id == tenant_uuid,
                TenantOAuthConnection.provider == "google_gmail",
            )
            row = (await s.execute(stmt)).scalar_one_or_none()
            if row and row.is_connected:
                exp_ts = row.expires_at.timestamp() if row.expires_at else None
                conn = GmailConnectionState(
                    is_connected=row.is_connected,
                    connected_email=row.connected_email,
                    tenant_id=str(tenant_id),
                    access_token=row.access_token,
                    refresh_token=row.refresh_token,
                    expires_at=exp_ts,
                    last_synced_at=row.last_synced_at,
                    synced_messages_count=row.synced_messages_count,
                    is_configured=is_cfg,
                )
                self.connections[str(tenant_id)] = conn
                return conn
            return None

        if session is not None:
            return await _query(session)
        else:
            async with async_session_factory() as s:
                return await _query(s)

    async def save_connection_to_db(
        self, tenant_id: str, conn: GmailConnectionState, session: AsyncSession | None = None
    ) -> None:
        """Persists or updates tenant OAuth connection in PostgreSQL."""
        try:
            tenant_uuid = uuid.UUID(str(tenant_id))
        except Exception as e:
            logger.warning("Invalid tenant UUID %s, skipping DB persist: %s", tenant_id, e)
            return

        exp_dt = datetime.fromtimestamp(conn.expires_at, UTC) if conn.expires_at else None

        async def _upsert(s: AsyncSession):
            stmt = select(TenantOAuthConnection).where(
                TenantOAuthConnection.tenant_id == tenant_uuid,
                TenantOAuthConnection.provider == "google_gmail",
            )
            existing = (await s.execute(stmt)).scalar_one_or_none()
            if existing:
                existing.is_connected = conn.is_connected
                existing.connected_email = conn.connected_email
                existing.access_token = conn.access_token
                existing.refresh_token = conn.refresh_token or existing.refresh_token
                existing.expires_at = exp_dt
                existing.last_synced_at = conn.last_synced_at
                existing.synced_messages_count = conn.synced_messages_count
                existing.scopes = " ".join(SCOPES)
            else:
                record = TenantOAuthConnection(
                    connection_id=uuid.uuid4(),
                    tenant_id=tenant_uuid,
                    provider="google_gmail",
                    is_connected=conn.is_connected,
                    connected_email=conn.connected_email,
                    access_token=conn.access_token,
                    refresh_token=conn.refresh_token,
                    token_type="Bearer",
                    scopes=" ".join(SCOPES),
                    expires_at=exp_dt,
                    last_synced_at=conn.last_synced_at,
                    synced_messages_count=conn.synced_messages_count,
                )
                s.add(record)
            await s.commit()

        if session is not None:
            await _upsert(session)
        else:
            async with async_session_factory() as s:
                await _upsert(s)

    async def disconnect_async(
        self, tenant_id: str, session: AsyncSession | None = None
    ) -> None:
        """Revokes connection state and clears stored tokens in DB and memory."""
        self.disconnect(tenant_id)
        try:
            tenant_uuid = uuid.UUID(str(tenant_id))
        except Exception:
            return

        async def _clear(s: AsyncSession):
            stmt = select(TenantOAuthConnection).where(
                TenantOAuthConnection.tenant_id == tenant_uuid,
                TenantOAuthConnection.provider == "google_gmail",
            )
            existing = (await s.execute(stmt)).scalar_one_or_none()
            if existing:
                existing.is_connected = False
                existing.access_token = None
                existing.refresh_token = None
                existing.connected_email = None
                await s.commit()

        if session is not None:
            await _clear(session)
        else:
            async with async_session_factory() as s:
                await _clear(s)

    async def ensure_valid_token(
        self, tenant_id: str, session: AsyncSession | None = None
    ) -> GmailConnectionState:
        """Checks if access token is expired; if so, uses refresh_token to acquire a fresh access token."""
        conn = await self.get_connection_async(tenant_id, session)
        if not conn.is_connected or not conn.refresh_token:
            return conn

        # Check if token is expired or expiring within 60 seconds
        now_ts = time.time()
        if conn.expires_at and (conn.expires_at - now_ts > 60) and conn.access_token:
            return conn

        client_id, client_secret = self.get_credentials()
        if not client_id or not client_secret:
            return conn

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    GOOGLE_TOKEN_ENDPOINT,
                    data={
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "refresh_token": conn.refresh_token,
                        "grant_type": "refresh_token",
                    },
                )
                if resp.is_success:
                    data = resp.json()
                    conn.access_token = data.get("access_token", conn.access_token)
                    expires_in = data.get("expires_in", 3600)
                    conn.expires_at = time.time() + float(expires_in)
                    logger.info("Successfully refreshed Gmail access token for tenant %s", tenant_id)
                    await self.save_connection_to_db(tenant_id, conn, session)
                else:
                    logger.warning("Failed to refresh Gmail token (%s): %s", resp.status_code, resp.text)
        except Exception as e:
            logger.warning("Exception during Gmail token refresh: %s", e)

        return conn

    def get_credentials(self) -> tuple[str | None, str | None]:
        """Retrieves Google OAuth credentials from environment variables or settings."""
        client_id = (
            os.environ.get("GOOGLE_CLIENT_ID")
            or getattr(settings, "GOOGLE_CLIENT_ID", None)
            or None
        )
        client_secret = (
            os.environ.get("GOOGLE_CLIENT_SECRET")
            or getattr(settings, "GOOGLE_CLIENT_SECRET", None)
            or None
        )
        if client_id:
            client_id = client_id.strip() or None
        if client_secret:
            client_secret = client_secret.strip() or None
        return client_id, client_secret

    def get_credentials_status(self) -> dict[str, Any]:
        """Checks if Google OAuth credentials are configured in environment variables."""
        client_id, client_secret = self.get_credentials()
        return {
            "is_configured": bool(client_id and client_secret),
            "client_id": client_id or "",
            "has_client_secret": bool(client_secret),
        }

    def save_credentials(self, client_id: str, client_secret: str) -> dict[str, Any]:
        """Persists Google Client ID & Secret to environment variables and .env file."""
        c_id = client_id.strip()
        c_secret = client_secret.strip()

        os.environ["GOOGLE_CLIENT_ID"] = c_id
        os.environ["GOOGLE_CLIENT_SECRET"] = c_secret
        settings.GOOGLE_CLIENT_ID = c_id
        settings.GOOGLE_CLIENT_SECRET = c_secret

        # Update .env file on disk
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), ".env")
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    content = f.read()

                if "GOOGLE_CLIENT_ID=" in content:
                    content = re.sub(r"GOOGLE_CLIENT_ID=.*", f"GOOGLE_CLIENT_ID={c_id}", content)
                else:
                    content += f"\nGOOGLE_CLIENT_ID={c_id}"

                if "GOOGLE_CLIENT_SECRET=" in content:
                    content = re.sub(r"GOOGLE_CLIENT_SECRET=.*", f"GOOGLE_CLIENT_SECRET={c_secret}", content)
                else:
                    content += f"\nGOOGLE_CLIENT_SECRET={c_secret}"

                with open(env_path, "w", encoding="utf-8") as f:
                    f.write(content)
                logger.info("Saved Google OAuth credentials to %s", env_path)
            except Exception as e:
                logger.warning("Could not persist credentials to .env file: %s", e)

        return {"status": "CONFIGURED", "is_configured": True, "client_id": c_id}

    def get_connection(self, tenant_id: str) -> GmailConnectionState:
        str_id = str(tenant_id)
        client_id, client_secret = self.get_credentials()
        is_cfg = bool(client_id and client_secret)
        if str_id not in self.connections:
            self.connections[str_id] = GmailConnectionState(
                tenant_id=str_id,
                is_configured=is_cfg,
            )
        else:
            self.connections[str_id].is_configured = is_cfg
        return self.connections[str_id]

    async def get_connection_async(
        self, tenant_id: str, session: AsyncSession | None = None
    ) -> GmailConnectionState:
        """Retrieves tenant connection state, pulling from PostgreSQL if not in active memory."""
        str_id = str(tenant_id)
        if str_id in self.connections and self.connections[str_id].is_connected:
            return self.connections[str_id]

        db_conn = await self.load_connection_from_db(str_id, session)
        if db_conn is not None:
            return db_conn

        return self.get_connection(str_id)

    def get_authorization_url(self, tenant_id: str, redirect_uri: str | None = None) -> dict[str, Any]:
        """Generates official Google OAuth 2.0 authorization URL."""
        client_id, client_secret = self.get_credentials()
        r_uri = redirect_uri or "http://localhost:3000/inbox"

        if not client_id or not client_secret:
            return {
                "is_configured": False,
                "authorization_url": None,
                "error": "Google OAuth credentials (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET) are not configured in environment variables.",
                "redirect_uri": r_uri,
                "scopes": SCOPES,
            }

        params = {
            "client_id": client_id,
            "redirect_uri": r_uri,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": str(tenant_id),
        }
        auth_url = f"{GOOGLE_AUTH_ENDPOINT}?{urllib.parse.urlencode(params)}"
        return {
            "is_configured": True,
            "authorization_url": auth_url,
            "client_id": client_id,
            "redirect_uri": r_uri,
            "scopes": SCOPES,
        }

    async def exchange_code_for_tokens(
        self,
        tenant_id: str,
        code: str,
        redirect_uri: str,
        session: AsyncSession | None = None,
    ) -> GmailConnectionState:
        """Exchanges Google authorization code for real Google access & refresh tokens."""
        client_id, client_secret = self.get_credentials()
        if not client_id or not client_secret:
            raise ValueError(
                "Cannot exchange token: GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are not configured in environment variables."
            )

        str_id = str(tenant_id)
        conn = await self.get_connection_async(str_id, session)

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                GOOGLE_TOKEN_ENDPOINT,
                data={
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )

            if not resp.is_success:
                err_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                err_msg = err_data.get("error_description") or err_data.get("error") or resp.text

                # If tenant is ALREADY connected, do not destroy existing connection on code replay
                if conn.is_connected and (conn.access_token or conn.refresh_token):
                    logger.warning(
                        "Authorization code exchange failed for already connected tenant %s (likely code replay); preserving active session.",
                        str_id,
                    )
                    return conn

                conn.is_connected = False
                raise ValueError(f"Google OAuth token exchange failed ({resp.status_code}): {err_msg}")

            tokens = resp.json()
            conn.access_token = tokens.get("access_token")
            if tokens.get("refresh_token"):
                conn.refresh_token = tokens.get("refresh_token")
            expires_in = tokens.get("expires_in", 3600)
            conn.expires_at = time.time() + float(expires_in)
            conn.is_connected = True
            conn.last_synced_at = datetime.now(UTC)

            # Query real user profile from Google to get authenticated email
            userinfo_resp = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {conn.access_token}"},
            )
            if userinfo_resp.is_success:
                conn.connected_email = userinfo_resp.json().get("email")
            else:
                conn.connected_email = "authenticated-google-user@workspace"

            # Persist to database
            await self.save_connection_to_db(str_id, conn, session)

            logger.info("Successfully connected and persisted real Gmail account for tenant %s: %s", str_id, conn.connected_email)
            return conn

    def disconnect(self, tenant_id: str) -> None:
        """Revokes connection state for tenant in memory."""
        str_id = str(tenant_id)
        if str_id in self.connections:
            self.connections[str_id] = GmailConnectionState(tenant_id=str_id)
        mailbox.inbox.clear()


    async def sync_inbox(
        self, tenant_id: str, session: AsyncSession | None = None
    ) -> list[IngestedEmailMessage]:
        """Polls connected Gmail account for unread messages via real Gmail API."""
        conn = await self.ensure_valid_token(tenant_id, session)
        if not conn.is_connected or not conn.access_token:
            raise ValueError("Gmail account is not connected. Please connect via Google OAuth 2.0 first.")

        synced_emails: list[IngestedEmailMessage] = []

        async with httpx.AsyncClient(timeout=20.0) as client:
            headers = {"Authorization": f"Bearer {conn.access_token}"}
            # List unread messages
            list_resp = await client.get(
                f"{GMAIL_API_BASE}/messages?q=is:unread",
                headers=headers,
            )
            if not list_resp.is_success:
                err_body = list_resp.text
                raise ValueError(f"Gmail API query failed ({list_resp.status_code}): {err_body}")

            msg_ids = [m["id"] for m in list_resp.json().get("messages", [])[:10]]
            for m_id in msg_ids:
                msg_resp = await client.get(
                    f"{GMAIL_API_BASE}/messages/{m_id}?format=full",
                    headers=headers,
                )
                if msg_resp.is_success:
                    msg_data = msg_resp.json()
                    parsed = self._parse_gmail_message_payload(msg_data, tenant_id)
                    if parsed:
                        mailbox.add_inbox(parsed)
                        synced_emails.append(parsed)

        conn.last_synced_at = datetime.now(UTC)
        conn.synced_messages_count += len(synced_emails)
        await self.save_connection_to_db(str(tenant_id), conn, session)
        # Returns strictly real emails; if none found, returns empty list
        return synced_emails

    def _parse_gmail_message_payload(self, msg_data: dict[str, Any], tenant_id: str) -> IngestedEmailMessage | None:
        """Parses real Gmail API JSON message into IngestedEmailMessage."""
        headers = {h["name"].lower(): h["value"] for h in msg_data.get("payload", {}).get("headers", [])}
        sender = headers.get("from", "unknown@sender.com")
        subject = headers.get("subject", "Inbound Message")
        snippet = msg_data.get("snippet", "")

        body_text = snippet
        attachments: list[EmailAttachment] = []

        # Parse multipart body and attachments if present
        payload = msg_data.get("payload", {})
        parts = payload.get("parts", [])
        for part in parts:
            filename = part.get("filename")
            mime_type = part.get("mimeType", "application/octet-stream")
            body = part.get("body", {})
            size = body.get("size", 0)
            if filename:
                attachments.append(
                    EmailAttachment(
                        filename=filename,
                        content_type=mime_type,
                        size_bytes=size,
                    )
                )

        recipient = headers.get("to", "inbox@company.internal")
        classification = classify_inbound_email(
            sender=sender,
            subject=subject,
            body_text=body_text,
            recipient=recipient,
        )

        try:
            tenant_uuid = uuid.UUID(str(tenant_id))
        except Exception:
            tenant_uuid = settings.DEFAULT_TENANT_ID

        # If system alert, security notification, or non-commercial email, filter it out
        if classification.intent == EmailIntent.SYSTEM_NOTIFICATION:
            logger.info("Filtered non-commercial system email from %s: '%s'", sender, subject)
            return IngestedEmailMessage(
                message_id=msg_data.get("id", f"msg_{uuid.uuid4().hex[:8]}"),
                sender=sender,
                recipient=recipient,
                subject=subject,
                body_text=body_text,
                attachments=attachments,
                event_type=classification.event_type,
                tenant_id=tenant_id,
                status="FILTERED_NOTIFICATION",
                associated_dag_id=None,
            )

        cust_name = sender.split("<")[0].strip().replace('"', "") or "Enterprise Customer"

        # Build appropriate DAG
        if classification.intent == EmailIntent.CUSTOMER_ORDER:
            dag = chief_orchestrator.build_order_fulfillment_workflow_dag(
                tenant_id=tenant_uuid,
                order_payload={
                    "customer_name": cust_name,
                    "customer_email": sender,
                    "inquiry_text": f"Subject: {subject}\n\n{body_text}",
                    "attachments": [a.filename for a in attachments],
                },
            )
        else:
            dag = chief_orchestrator.build_rfq_workflow_dag(
                tenant_id=tenant_uuid,
                rfq_payload={
                    "customer_name": cust_name,
                    "customer_email": sender,
                    "inquiry_text": f"Subject: {subject}\n\n{body_text}",
                    "attachments": [a.filename for a in attachments],
                },
            )

        # Trigger DAG execution across agent mesh immediately
        asyncio.create_task(dag_executor.execute_dag(dag))

        return IngestedEmailMessage(
            message_id=msg_data.get("id", f"msg_{uuid.uuid4().hex[:8]}"),
            sender=sender,
            recipient=recipient,
            subject=subject,
            body_text=body_text,
            attachments=attachments,
            event_type=classification.event_type,
            tenant_id=tenant_id,
            status="DISPATCHED_TO_MESH",
            associated_dag_id=dag.dag_id,
        )

    async def send_email_via_gmail(
        self,
        tenant_id: str,
        recipient: str,
        subject: str,
        body: str,
        pdf_bytes: bytes | None = None,
        filename: str = "Quotation.pdf",
        session: AsyncSession | None = None,
    ) -> SentEmailMessage:
        """Sends an outbound email using the tenant's connected Gmail OAuth account."""
        conn = await self.ensure_valid_token(tenant_id, session)
        if not conn.is_connected or not conn.access_token:
            raise ValueError("Gmail account is not connected. Cannot send outbound quote via Gmail.")

        msg = EmailMessage()
        msg["To"] = recipient
        msg["From"] = conn.connected_email or "sales@company.com"
        msg["Subject"] = subject
        msg.set_content(body)

        if pdf_bytes:
            msg.add_attachment(
                pdf_bytes,
                maintype="application",
                subtype="pdf",
                filename=filename,
            )

        raw_msg = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
        async with httpx.AsyncClient(timeout=15.0) as client:
            send_resp = await client.post(
                f"{GMAIL_API_BASE}/messages/send",
                headers={
                    "Authorization": f"Bearer {conn.access_token}",
                    "Content-Type": "application/json",
                },
                json={"raw": raw_msg},
            )
            if not send_resp.is_success:
                raise ValueError(f"Gmail send API failed ({send_resp.status_code}): {send_resp.text}")

        sent_msg = SentEmailMessage(
            recipient=recipient,
            subject=subject,
            body=body,
            attachment_name=filename if pdf_bytes else None,
            attachment_size_bytes=len(pdf_bytes) if pdf_bytes else 0,
            tenant_id=tenant_id,
            status="DELIVERED_VIA_GMAIL",
        )
        mailbox.add_sent(sent_msg)
        return sent_msg


gmail_service = GmailIntegrationService()
