"""
Thin Pinecone wrapper (section 36: vector DB must be swappable). All other
RAG code goes through here rather than importing the pinecone SDK directly.
"""
from __future__ import annotations

import logging
from typing import Optional

from config import settings

logger = logging.getLogger("crime_report_ai.pinecone")

_pc = None
_index = None
_init_error: Optional[str] = None


def is_available() -> bool:
    return get_index() is not None


def get_index():
    global _pc, _index, _init_error
    if _index is not None or _init_error is not None:
        return _index
    if not settings.pinecone_configured():
        _init_error = "PINECONE_API_KEY is not configured."
        return None
    try:
        from pinecone import Pinecone, ServerlessSpec

        _pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        existing = [i["name"] for i in _pc.list_indexes()]
        if settings.PINECONE_INDEX not in existing:
            _pc.create_index(
                name=settings.PINECONE_INDEX,
                dimension=settings.EMBEDDING_DIMENSION,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1"),
            )
        _index = _pc.Index(settings.PINECONE_INDEX)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Failed to initialize Pinecone")
        _init_error = f"Could not initialize Pinecone: {exc}"
    return _index


def upsert_vectors(vectors: list[dict]) -> bool:
    """vectors: list of {"id": str, "values": [float], "metadata": {...}}"""
    index = get_index()
    if index is None:
        logger.warning("Pinecone unavailable, skipping upsert (%s)", _init_error)
        return False
    try:
        index.upsert(vectors=vectors)
        return True
    except Exception as exc:
        logger.exception("Pinecone upsert failed: %s", exc)
        return False


def query(vector: list[float], top_k: int = 4, filter: dict | None = None) -> list[dict]:
    index = get_index()
    if index is None:
        return []
    try:
        result = index.query(vector=vector, top_k=top_k, include_metadata=True, filter=filter)
        return result.get("matches", []) if isinstance(result, dict) else result.matches
    except Exception as exc:
        logger.exception("Pinecone query failed: %s", exc)
        return []
