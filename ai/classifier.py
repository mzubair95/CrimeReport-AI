"""
Crime classification (section 11) and free-text field extraction (section 7).
"""
from __future__ import annotations

from config.settings import CRIME_CATEGORIES
from ai import gemini
from ai.schemas import IncidentExtraction, ClassificationResult, safe_validate

_CATEGORY_LIST = ", ".join(CRIME_CATEGORIES)


def extract_incident_facts(description: str) -> IncidentExtraction:
    """
    Pull structured facts out of a free-text incident description.
    Never invents missing information — uses null/None instead (section 7).
    """
    prompt = f"""You extract structured facts from a crime/incident report written
by a member of the public. Only use information that is explicitly stated or
strongly implied by the text. If something is not mentioned, use null — never
guess or invent it.

Return ONLY JSON matching this exact schema:
{{
  "incident_type": string or null,
  "object_involved": string or null,
  "location": string or null,
  "date": string or null,
  "time": string or null,
  "injury": string or null,
  "suspect_information": string or null,
  "confidence": number between 0 and 1 (how confident you are in this extraction)
}}

User's description:
\"\"\"{description}\"\"\"
"""
    data = gemini.generate_json(prompt)
    result = safe_validate(IncidentExtraction, data)
    return result or IncidentExtraction()


def classify_incident(description: str, extra_context: str = "") -> ClassificationResult:
    """
    Classify the incident into a controlled category (section 11).
    Confidence is informational only and must never be shown as proof a crime occurred.
    """
    prompt = f"""Classify the following incident into EXACTLY ONE of these categories:
{_CATEGORY_LIST}

Use "Other" if nothing fits well. Return ONLY JSON:
{{"category": one of the categories above, "confidence": number 0-1, "explanation": short internal reasoning}}

Incident description:
\"\"\"{description}\"\"\"

Additional context (may be empty):
\"\"\"{extra_context}\"\"\"
"""
    data = gemini.generate_json(prompt)
    result = safe_validate(ClassificationResult, data)
    if result and result.category not in CRIME_CATEGORIES:
        result.category = "Other"
    return result or ClassificationResult(category="Other", confidence=0.0,
                                           explanation="Classification unavailable.")
