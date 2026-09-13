"""
Similarity search over the knowledge base (section 13).
"""
from __future__ import annotations

import logging

from rag import pinecone_client
from rag.embeddings import embed_query

logger = logging.getLogger("crime_report_ai.retriever")


def retrieve_context(query_text: str, top_k: int = 4, category: str | None = None) -> str:
    """
    Return a newline-joined string of the most relevant knowledge-base chunks
    for `query_text`, optionally filtered by crime category metadata.
    Returns "" gracefully if RAG isn't available/configured.
    """
    if not query_text.strip():
        return ""
    try:
        vector = embed_query(query_text)
    except Exception as exc:
        logger.warning("Embedding failed, skipping retrieval: %s", exc)
        return ""

    filt = {"category": {"$eq": category}} if category else None
    matches = pinecone_client.query(vector, top_k=top_k, filter=filt)
    if not matches:
        return ""

    chunks = []
    for m in matches:
        meta = m.get("metadata", {}) if isinstance(m, dict) else getattr(m, "metadata", {})
        text = (meta or {}).get("text", "")
        if text:
            chunks.append(text)
    return "\n\n".join(chunks)


def retrieve_matches(query_text: str, top_k: int = 4, category: str | None = None) -> list[dict]:
    """Same as retrieve_context but returns raw matches with metadata for display."""
    try:
        vector = embed_query(query_text)
    except Exception:
        return []
    filt = {"category": {"$eq": category}} if category else None
    return pinecone_client.query(vector, top_k=top_k, filter=filt)
