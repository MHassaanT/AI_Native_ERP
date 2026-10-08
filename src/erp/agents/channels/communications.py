"""Multi-channel communication dispatcher (WhatsApp, Gmail, and ERP Ledger)."""

import base64
import logging
import os
import uuid
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Any, Dict, Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from erp.db.models.agents import AgentCommunication, ChannelType
from erp.db.session import async_session_factory

logger = logging.getLogger(__name__)


class CommunicationDispatcher:
    """Dispatches messages across WhatsApp, Gmail, and ERP internal ledger."""

    def __init__(self):
        self.backend_url = os.getenv("BACKEND_URL", "http://localhost:4000")
        self.internal_token = os.getenv("INTERNAL_SERVICE_TOKEN")

    async def send_whatsapp(
        self,
        tenant_id: uuid.UUID,
        agent_name: str,
        to_phone: str,
        message: str,
        run_id: Optional[uuid.UUID] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentCommunication:
        """Sends WhatsApp message via Baileys MCP service and logs to PostgreSQL."""
        status = "FAILED"
        ext_msg_id = None

        # Attempt live dispatch to internal WhatsApp service if active
        try:
            if not self.internal_token:
                raise RuntimeError("WhatsApp gateway credentials are not configured")
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.post(
                    f"{self.backend_url}/internal/whatsapp/send",
                    headers={"X-Internal-Token": self.internal_token},
                    json={"tenantId": str(tenant_id), "to": to_phone, "message": message},
                )
                if res.is_success:
                    data = res.json()
                    ext_msg_id = data.get("messageId")
                    status = "SENT"
                    logger.info(f"WhatsApp message dispatched to {to_phone} (id: {ext_msg_id})")
                else:
                    logger.warning(f"WhatsApp service returned HTTP {res.status_code}.")
        except Exception as e:
            logger.warning("WhatsApp delivery failed: %s", e)

        # Always persist in PostgreSQL agent_communications ledger
        async with async_session_factory() as session:
            comm = AgentCommunication(
                comm_id=uuid.uuid4(),
                tenant_id=tenant_id,
                run_id=run_id,
                agent_name=agent_name,
                channel=ChannelType.WHATSAPP,
                recipient=to_phone,
                subject=None,
                body=message,
                metadata_json=metadata or {},
                status=status,
                external_message_id=ext_msg_id,
                created_at=datetime.now(timezone.utc),
            )
            session.add(comm)
            await session.commit()
            await session.refresh(comm)
            return comm

    async def send_gmail(
        self,
        tenant_id: uuid.UUID,
        agent_name: str,
        to_email: str,
        subject: str,
        body: str,
        run_id: Optional[uuid.UUID] = None,
        metadata: Optional[Dict[str, Any]] = None,
        credentials: Optional[Dict[str, Any]] = None,
    ) -> AgentCommunication:
        """Sends Gmail message via Gmail API or logs to PostgreSQL."""
        status = "FAILED"
        ext_msg_id = None

        # If OAuth access token provided, send via Google API
        token = credentials.get("access_token") if credentials else None
        if token:
            try:
                msg = EmailMessage()
                msg["To"] = to_email
                msg["Subject"] = subject
                msg.set_content(body)
                raw_b64 = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

                async with httpx.AsyncClient(timeout=10.0) as client:
                    res = await client.post(
                        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                        json={"raw": raw_b64},
                    )
                    if res.is_success:
                        ext_msg_id = res.json().get("id")
                        status = "SENT"
                        logger.info(f"Gmail sent successfully to {to_email} (id: {ext_msg_id})")
                    else:
                        logger.warning(f"Gmail API returned HTTP {res.status_code}.")
            except Exception as e:
                logger.error("Failed to dispatch via Gmail API: %s", e)

        # Always record in PostgreSQL agent_communications ledger
        async with async_session_factory() as session:
            comm = AgentCommunication(
                comm_id=uuid.uuid4(),
                tenant_id=tenant_id,
                run_id=run_id,
                agent_name=agent_name,
                channel=ChannelType.GMAIL,
                recipient=to_email,
                subject=subject,
                body=body,
                metadata_json=metadata or {},
                status=status,
                external_message_id=ext_msg_id,
                created_at=datetime.now(timezone.utc),
            )
            session.add(comm)
            await session.commit()
            await session.refresh(comm)
            return comm

    async def send_internal_notice(
        self,
        tenant_id: uuid.UUID,
        agent_name: str,
        recipient_role_or_email: str,
        subject: str,
        body: str,
        run_id: Optional[uuid.UUID] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentCommunication:
        """Logs internal company notification into ERP communication ledger."""
        async with async_session_factory() as session:
            comm = AgentCommunication(
                comm_id=uuid.uuid4(),
                tenant_id=tenant_id,
                run_id=run_id,
                agent_name=agent_name,
                channel=ChannelType.INTERNAL,
                recipient=recipient_role_or_email,
                subject=subject,
                body=body,
                metadata_json=metadata or {},
                status="RECORDED",
                external_message_id=None,
                created_at=datetime.now(timezone.utc),
            )
            session.add(comm)
            await session.commit()
            await session.refresh(comm)
            return comm


dispatcher = CommunicationDispatcher()
