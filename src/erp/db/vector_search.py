"""High-Dimensional Vector Search Engine (PRD §Schema 4 Vector Embeddings).

Supports sub-millisecond HNSW cosine similarity retrieval over 1536-dimensional
enterprise documents (invoices, RFQs, vendor catalogs, contracts) with tenant isolation.
"""

import logging
import uuid
from typing import Any

import httpx

from erp.config import settings

logger = logging.getLogger(__name__)

QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "ai_erp_documents"
VECTOR_DIMENSION = 1536


class VectorSearchEngine:
    """Dispatches HNSW vector queries and multi-tenant document indexing."""

    def __init__(self, base_url: str = QDRANT_URL, collection: str = COLLECTION_NAME):
        self.base_url = base_url
        self.collection = collection
        self._is_initialized = False
        self._memory_points: dict[str, dict[str, Any]] = {}

    async def ensure_collection(self) -> bool:
        """Verifies or creates the HNSW cosine vector collection."""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(f"{self.base_url}/collections/{self.collection}")
                if res.status_code == 200:
                    self._is_initialized = True
                    return True

                # Create collection with HNSW parameters
                payload = {
                    "vectors": {"size": VECTOR_DIMENSION, "distance": "Cosine"},
                    "hnsw_config": {
                        "m": 16,
                        "ef_construct": 100,
                        "full_scan_threshold": 1000,
                    },
                }
                put_res = await client.put(f"{self.base_url}/collections/{self.collection}", json=payload)
                self._is_initialized = put_res.status_code in (200, 201)
                return self._is_initialized
        except Exception as e:
            logger.warning("Vector engine connection failed (%s). Running in memory fallback.", e)
            self._is_initialized = False
            return False

    async def upsert_vector(
        self,
        point_id: str,
        tenant_id: uuid.UUID | str,
        entity_type: str,
        entity_id: uuid.UUID | str,
        vector: list[float],
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Upserts a document vector with multi-tenant payload."""
        await self.ensure_collection()
        point_uuid = str(uuid.UUID(point_id)) if len(point_id) == 36 else str(uuid.uuid4())

        payload = {
            "tenant_id": str(tenant_id),
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "content": content,
            "metadata": metadata or {},
        }

        if not self._is_initialized:
            self._memory_points[point_uuid] = {
                "id": point_uuid,
                "vector": vector,
                "payload": payload,
            }
            return True

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.put(
                    f"{self.base_url}/collections/{self.collection}/points",
                    json={
                        "points": [
                            {
                                "id": point_uuid,
                                "vector": vector,
                                "payload": payload,
                            }
                        ]
                    },
                )
                return res.status_code == 200
        except Exception as e:
            logger.error("Failed to upsert vector %s: %s. Storing in memory fallback.", point_id, e)
            self._memory_points[point_uuid] = {
                "id": point_uuid,
                "vector": vector,
                "payload": payload,
            }
            return True

    async def search_similar(
        self,
        tenant_id: uuid.UUID | str,
        query_vector: list[float],
        entity_type: str | None = None,
        limit: int = 5,
        score_threshold: float = 0.5,
    ) -> list[dict[str, Any]]:
        """Performs HNSW nearest neighbor cosine search filtered by tenant_id."""
        await self.ensure_collection()

        if not self._is_initialized:
            import math
            results = []
            q_norm = math.sqrt(sum(x * x for x in query_vector)) or 1.0
            for pt in self._memory_points.values():
                pl = pt["payload"]
                if pl.get("tenant_id") != str(tenant_id):
                    continue
                if entity_type and pl.get("entity_type") != entity_type:
                    continue
                v = pt["vector"]
                v_norm = math.sqrt(sum(x * x for x in v)) or 1.0
                dot = sum(a * b for a, b in zip(query_vector, v))
                score = dot / (q_norm * v_norm)
                if score >= score_threshold:
                    results.append({
                        "id": pt["id"],
                        "score": score,
                        "content": pl.get("content", ""),
                        "entity_type": pl.get("entity_type", ""),
                        "entity_id": pl.get("entity_id", ""),
                        "metadata": pl.get("metadata", {}),
                    })
            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:limit]

        must_conditions: list[dict[str, Any]] = [
            {"key": "tenant_id", "match": {"value": str(tenant_id)}}
        ]
        if entity_type:
            must_conditions.append({"key": "entity_type", "match": {"value": entity_type}})

        query_body = {
            "vector": query_vector,
            "limit": limit,
            "score_threshold": score_threshold,
            "with_payload": True,
            "filter": {"must": must_conditions},
        }

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.post(
                    f"{self.base_url}/collections/{self.collection}/points/search",
                    json=query_body,
                )
                if res.status_code == 200:
                    hits = res.json().get("result", [])
                    return [
                        {
                            "id": hit.get("id"),
                            "score": hit.get("score"),
                            "content": hit.get("payload", {}).get("content", ""),
                            "entity_type": hit.get("payload", {}).get("entity_type", ""),
                            "entity_id": hit.get("payload", {}).get("entity_id", ""),
                            "metadata": hit.get("payload", {}).get("metadata", {}),
                        }
                        for hit in hits
                    ]
        except Exception as e:
            logger.warning("Vector search query failed (%s). Returning empty hits.", e)

        return []


vector_search_engine = VectorSearchEngine()
