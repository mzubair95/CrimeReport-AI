"""
Final incident summary (section 19) and full report text generation.
Clearly separates USER PROVIDED facts from AI INFERRED/ANALYZED content.
"""
from __future__ import annotations

import json
import logging

from ai import gemini

logger = logging.getLogger("crime_report_ai.summarizer")


def build_incident_summary(report_state: dict) -> str:
    """
    report_state is expected to contain: description, classification, facts,
    qa_history, evidence_analysis (image/video AI findings).
    Produces a short factual paragraph summary for the report.
    """
    prompt = f"""Write a concise, neutral, factual incident summary (3-6 sentences)
for a crime report, based on the structured data below. Write in third person
("The user reports that..."). Clearly separate facts the user stated from
anything derived from AI analysis of photos/video by explicitly labeling AI
observations as AI-analyzed. Do not speculate beyond the data given. Do not
use dramatic language. Output plain text only, no markdown, no JSON.

Data:
{json.dumps(report_state, indent=2, default=str)}
"""
    try:
        return gemini.generate_text(prompt, temperature=0.3)
    except gemini.GeminiUnavailable as exc:
        logger.warning("Summary generation unavailable: %s", exc)
        desc = report_state.get("description", "")
        return (
            "AI summary unavailable. Original user description: " + (desc or "N/A")
        )
