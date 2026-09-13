"""
Verification-support engine (PRD AI Modules: "Consistency Engine" +
"Abuse Pattern Detection"). Every flag is worded neutrally — "Needs Review" /
"Information Inconsistent" — per the UX spec (§14): never an accusation, and
never a determination that a report is false. A human reviewer decides what
to do with a flag; the AI only surfaces it.
"""
from __future__ import annotations

import logging

from ai import llm
from ai.schemas import ConsistencyReview, VerificationFlag, safe_validate

logger = logging.getLogger("crime_report_ai.verification")


def check_consistency(description: str, qa_history: list[dict]) -> list[VerificationFlag]:
    """LLM-based contradiction check across the description and follow-up
    answers — e.g. a date/time/location/count that doesn't line up. Returns
    [] (never raises) if nothing stands out or the LLM is unavailable."""
    if not description and not qa_history:
        return []

    prompt = f"""Review this incident report ONLY for internal contradictions
or inconsistencies — e.g. two different times/dates/locations given for the
same event, or a detail in the answers that conflicts with the original
description. Do NOT judge whether the incident is true or false, and do NOT
speculate about the reporter's motives. If nothing conflicts, return an
empty list.

Original description: \"\"\"{description}\"\"\"
Follow-up Q&A: {qa_history}

Return ONLY JSON:
{{"flags": [{{"flag_type": "inconsistency", "message": "short, neutral, factual description of what doesn't line up — e.g. 'The description says the incident happened at night, but the follow-up answer says it happened in the morning.'", "severity": "info"|"warning"}}]}}
Return {{"flags": []}} if nothing stands out — do not invent a flag just to have one.
"""
    data = llm.generate_json(prompt, temperature=0.1)
    result = safe_validate(ConsistencyReview, data)
    if result is None:
        return []
    return result.flags


def check_low_detail(description: str, qa_history: list[dict]) -> list[VerificationFlag]:
    """Lightweight rule-based check (no LLM needed) — a report with almost no
    detail is harder to act on and worth flagging for the reviewer, not
    rejecting. Part of PRD's "Abuse Pattern Detection" (spam-like reports)."""
    flags = []
    word_count = len((description or "").split())
    skipped = sum(1 for qa in qa_history if (qa.get("answer") or "").strip().lower()
                  in ("", "not provided", "skip", "n/a"))

    if word_count < 6 and not qa_history:
        flags.append(VerificationFlag(
            flag_type="low_detail",
            message="This report has very little detail — consider following up with the reporter.",
            severity="info",
        ))
    if qa_history and skipped >= max(3, len(qa_history) // 2):
        flags.append(VerificationFlag(
            flag_type="low_detail",
            message=f"{skipped} of {len(qa_history)} follow-up questions were skipped or left blank.",
            severity="info",
        ))
    return flags


def run_all_checks(description: str, qa_history: list[dict]) -> list[dict]:
    """Combines the consistency + low-detail checks into one flag list ready
    to store on the report. Never raises — verification is advisory, not a
    gate on submission."""
    flags: list[VerificationFlag] = []
    try:
        flags.extend(check_consistency(description, qa_history))
    except Exception:
        logger.exception("Consistency check failed")
    try:
        flags.extend(check_low_detail(description, qa_history))
    except Exception:
        logger.exception("Low-detail check failed")
    return [f.model_dump() for f in flags]
