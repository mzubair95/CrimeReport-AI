"""
Urgency/severity assessment (PRD §11 Severity/Triage Model, AI Modules
"Urgency Assessment"). Always paired with an explainable reason — a
priority level is never shown to a reviewer as an opaque number.
"""
from __future__ import annotations

import logging

from ai import llm
from ai.schemas import SeverityAssessment, safe_validate
from config.settings import SEVERITY_LEVELS, SEVERITY_MEANING

logger = logging.getLogger("crime_report_ai.urgency")

_LEVELS_TEXT = "\n".join(f"- {lvl}: {SEVERITY_MEANING[lvl]}" for lvl in SEVERITY_LEVELS)


def assess_severity(category: str, description: str, facts: dict) -> SeverityAssessment:
    prompt = f"""Assess the urgency/severity of this reported incident for a
human reviewer's triage queue. Base this ONLY on what is stated — do not
assume facts not given. Categories, from most to least urgent:
{_LEVELS_TEXT}

Category: {category}
Description: \"\"\"{description}\"\"\"
Known facts: {facts}

Signals that should push toward Critical/High: an ongoing/active threat,
a weapon mentioned, injury reported, immediate danger to a person, a
missing person case. Signals that push toward Medium/Low: incident already
concluded with no ongoing danger, property-only damage, informational
reports.

Return ONLY JSON:
{{"severity": "Critical"|"High"|"Medium"|"Low", "reason": "one short, factual sentence citing what in the report drove this level"}}
"""
    data = llm.generate_json(prompt, temperature=0.1)
    result = safe_validate(SeverityAssessment, data)
    if result:
        return result
    # Fail safe: an unassessable report should not silently disappear into
    # the lowest priority — default to Medium so it still surfaces for review.
    return SeverityAssessment(severity="Medium", reason="Automatic assessment unavailable — please review manually.")
