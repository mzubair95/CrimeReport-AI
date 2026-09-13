"""
Duplicate/related-incident detection (PRD AI Modules: "Duplicate Detection").
Uses the same sentence-transformer embeddings already used for RAG, stored
in a dedicated "reports" Pinecone namespace so this never mixes with the
general reporting-guidance vectors. A high similarity score is surfaced to
the reviewer as a *possible* duplicate/related report — never auto-merged
or auto-rejected; the human reviewer decides.
"""
from __future__ import annotations

import logging

from rag import pinecone_client
from rag.embeddings import embed_query

logger = logging.getLogger("crime_report_ai.duplicate_detector")

REPORTS_NAMESPACE = "reports"
SIMILARITY_THRESHOLD = 0.80  # cosine similarity above which two reports are flagged as related


def find_duplicates(category: str, description: str, top_k: int = 5) -> list[dict]:
    """Returns [{"report_id", "similarity", "reason"}] for existing reports
    that look similar to this one — same category is required so a robbery
    report never matches a noise complaint just because the wording is
    generic. Returns [] gracefully if Pinecone/embeddings are unavailable."""
    if not description or not description.strip():
        return []
    try:
        vector = embed_query(description)
    except Exception as exc:
        logger.warning("Duplicate-detection embedding failed: %s", exc)
        return []

    matches = pinecone_client.query(
        vector, top_k=top_k, filter={"category": {"$eq": category}} if category else None,
        namespace=REPORTS_NAMESPACE,
    )

    results = []
    for m in matches:
        score = m.get("score") if isinstance(m, dict) else getattr(m, "score", 0)
        if score is None or score < SIMILARITY_THRESHOLD:
            continue
        meta = m.get("metadata", {}) if isinstance(m, dict) else getattr(m, "metadata", {})
        match_id = m.get("id") if isinstance(m, dict) else getattr(m, "id", None)
        results.append({
            "report_id": (meta or {}).get("report_id", match_id),
            "similarity": round(float(score), 3),
            "reason": f"Similar description within the same category (similarity {score:.0%}).",
        })
    return results


def index_report(report_id: str, category: str, description: str) -> None:
    """Stores this report's embedding so *future* reports can be compared
    against it. Called after submission — a report is never compared
    against itself."""
    if not description or not description.strip():
        return
    try:
        vector = embed_query(description)
    except Exception as exc:
        logger.warning("Duplicate-detection indexing failed: %s", exc)
        return
    pinecone_client.upsert_vectors(
        [{"id": report_id, "values": vector, "metadata": {"report_id": report_id, "category": category}}],
        namespace=REPORTS_NAMESPACE,
    )
