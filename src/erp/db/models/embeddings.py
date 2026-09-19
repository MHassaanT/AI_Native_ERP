"""Semantic Document Embeddings Model for pgvector RAG (PRD Schema 4)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from erp.db.models.base import Base, TenantMixin


class SemanticDocumentEmbedding(Base, TenantMixin):
    """Stores high-dimensional vector embeddings for RAG retrieval across enterprise documents."""

    __tablename__ = "semantic_document_embeddings"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    entity_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="INVOICE_PDF, CONTRACT_LEGAL, EMAIL_THREAD, BANK_STATEMENT, ITEM_DESCRIPTION",
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_chunk: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
    )
    embedding: Mapped[list[float]] = mapped_column(
        ARRAY(Float),
        nullable=False,
        doc="1536-dimensional semantic representation",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.clock_timestamp(),
        nullable=False,
    )

    __table_args__ = (Index("idx_doc_tenant_entity", "tenant_id", "entity_type", "entity_id"),)
