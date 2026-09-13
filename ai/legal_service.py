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


# Static fallback for the false-reporting notice (Step 6) — this notice must
# always render even if Pinecone/embeddings are down at that moment, since
# it's shown immediately before every submission regardless of category.
# Mirrors the PPC 182 record in knowledge_base/legal/legal_references.json.
_FALSE_REPORTING_FALLBACK = {
    "statute": "PPC",
    "section_number": "182",
    "section_title": "False information with intent to cause a public servant to use "
                      "his lawful power to the injury of another person",
    "summary": "Applies to knowingly giving false information to a public servant "
               "(including police), intending or knowing it is likely to cause that "
               "public servant to act (or omit to act) improperly, or to injure/annoy "
               "someone.",
    "cognizable": "not independently confirmed against CrPC Schedule II primary text",
    "bailable": "commonly cited as bailable (secondary sources) — not independently "
                "confirmed against CrPC Schedule II primary text",
    "punishment_range": "Base: imprisonment of either description for a term which may "
                         "extend to 6 months, or fine. If the falsely-alleged offence is "
                         "punishable by death: up to 7 years. If punishable by life "
                         "imprisonment: up to 5 years. For other offences: up to "
                         "one-fourth of the longest term prescribed for that offence. "
                         "(Base term and escalation structure verified against primary "
                         "source text.)",
    "source_citation": "http://www.pljlawsite.com/html/ppc182.htm (verified 2026-09-13)",
}


def get_false_reporting_notice() -> dict:
    """
    Step 6 — the PPC 182 (false information / false FIR) notice shown before
    every submission, regardless of category. Uses an exact metadata filter
    (category="Other" AND section_number="182") rather than semantic search,
    since this specific citation must never be substituted for a different
    one; falls back to a hard-coded copy of the same record if Pinecone is
    unavailable, so this notice is never simply missing.
    """
    try:
        vector = embed_query("false information false FIR PPC 182")
        matches = pinecone_client.query(
            vector, top_k=1,
            filter={"category": {"$eq": "Other"}, "section_number": {"$eq": "182"}},
            namespace=LEGAL_NAMESPACE,
        )
        if matches:
            meta = matches[0].get("metadata", {}) if isinstance(matches[0], dict) \
                else getattr(matches[0], "metadata", {})
            if meta:
                return dict(meta)
    except Exception as exc:
        logger.warning("False-reporting notice lookup failed, using fallback: %s", exc)
    return dict(_FALSE_REPORTING_FALLBACK)


DISCLAIMER = (
    "⚠️ These legal references are drafted from publicly available sources "
    "for informational purposes only — they are NOT legal advice and have "
    "NOT been verified by a lawyer. Cognizable/bailable status and "
    "punishment ranges can depend on case-specific facts and on Schedule II "
    "of the Code of Criminal Procedure, 1898. Consult a lawyer or the police "
    "for guidance specific to your situation."
)
