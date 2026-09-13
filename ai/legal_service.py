"""
Step 4 — Legal reference lookup (docs/FIR_TECHNICAL_SPEC.md §3.2/§4.1).

Deliberately NOT an LLM call: legal citations (PPC/PECA sections, cognizable/
bailable status, punishment ranges) come only from the curated
knowledge_base/legal/legal_references.json records, retrieved from a
dedicated Pinecone namespace and returned as-is. An LLM is never asked to
recall or synthesize a statute number — this is exactly the kind of narrow,
high-stakes factual lookup where a model can confidently state a wrong
section number, and RAG grounding is the whole point (see the spec's
disclaimer).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from rag import pinecone_client
from rag.embeddings import embed_query
from rag.ingest import LEGAL_NAMESPACE

logger = logging.getLogger("crime_report_ai.legal_service")


def lookup(category: str, description: str = "", top_k: int = 5) -> list[dict]:
    """
    Returns a list of legal_reference-shaped dicts (statute, section_number,
    section_title, summary, cognizable, bailable, punishment_range,
    source_citation) for the given category, ranked by relevance to the
    incident description within that category. Returns [] gracefully if
    Pinecone/embeddings aren't available — callers must handle an empty
    result by telling the user to consult a lawyer/police directly, never by
    falling back to an LLM guess.
    """
    if not category:
        return []

    query_text = f"{category}. {description}".strip()
    try:
        vector = embed_query(query_text)
    except Exception as exc:
        logger.warning("Legal lookup embedding failed: %s", exc)
        return []

    # Always filter by exact category — semantic similarity alone must never
    # be allowed to surface a different category's statute.
    matches = pinecone_client.query(
        vector, top_k=top_k, filter={"category": {"$eq": category}}, namespace=LEGAL_NAMESPACE,
    )

    results = []
    retrieved_at = datetime.now(timezone.utc).isoformat()
    for m in matches:
        meta = m.get("metadata", {}) if isinstance(m, dict) else getattr(m, "metadata", {})
        if not meta:
            continue
        results.append({**meta, "retrieved_at": retrieved_at, "disclaimer_shown": True})
    return results


DISCLAIMER = (
    "⚠️ These legal references are drafted from publicly available sources "
    "for informational purposes only — they are NOT legal advice and have "
    "NOT been verified by a lawyer. Cognizable/bailable status and "
    "punishment ranges can depend on case-specific facts and on Schedule II "
    "of the Code of Criminal Procedure, 1898. Consult a lawyer or the police "
    "for guidance specific to your situation."
)
