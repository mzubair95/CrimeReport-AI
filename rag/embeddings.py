"""
Modular embedding provider (section 36: embedding model must be swappable).

Default: sentence-transformers (local, free, no API quota) — good for a
hackathon budget. An alternative Gemini-embeddings provider is included but
not selected by default; switch via EMBEDDING_PROVIDER in .env.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from config import settings

logger = logging.getLogger("crime_report_ai.embeddings")

_st_model = None


def _get_sentence_transformer():
    global _st_model
    if _st_model is None:
        from sentence_transformers import SentenceTransformer
        _st_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _st_model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Return one embedding vector per input text, using the configured provider."""
    if not texts:
        return []
    provider = settings.EMBEDDING_PROVIDER

    if provider == "gemini":
        return _embed_with_gemini(texts)

    # default: sentence-transformers
    model = _get_sentence_transformer()
    vectors = model.encode(texts, normalize_embeddings=True)
    return [v.tolist() for v in vectors]


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]


def _embed_with_gemini(texts: list[str]) -> list[list[float]]:
    from ai.gemini import get_client  # reuse the shared client
    client = get_client()
    if client is None:
        raise RuntimeError("Gemini not configured; cannot compute embeddings.")
    result = client.models.embed_content(model="text-embedding-004", contents=texts)
    return [e.values for e in result.embeddings]
