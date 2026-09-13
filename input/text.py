"""
Text input handling (section 7). Thin wrapper so the UI layer doesn't call
the AI layer directly, keeping input sources modular/swappable.
"""
from __future__ import annotations

from ai.classifier import extract_incident_facts, classify_incident
from ai.schemas import IncidentExtraction, ClassificationResult


def process_text_description(description: str) -> tuple[IncidentExtraction, ClassificationResult]:
    """Extract structured facts + classify a free-text incident description."""
    description = (description or "").strip()
    facts = extract_incident_facts(description)
    classification = classify_incident(description)
    return facts, classification
