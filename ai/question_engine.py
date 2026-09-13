"""
Dynamic AI questionnaire engine (sections 14-16).

Instead of a fixed script, Gemini looks at what's already known plus
RAG-retrieved guidance on what information that type of report normally
needs, and decides the single most useful next question — or declares the
questionnaire complete.
"""
from __future__ import annotations

import json

from ai import llm as gemini  # routed through ai/llm.py — backend set by LLM_PROVIDER
from ai.schemas import QuestionnaireStep, Question, safe_validate
from config.settings import CATEGORY_REQUIRED_FIELDS

MAX_QUESTIONS = 8  # hard cap so a stressed user is never stuck answering forever


def next_question(
    incident_type: str,
    original_description: str,
    known_facts: dict,
    qa_history: list[dict],
    rag_context: str = "",
    language: str = "English",
) -> QuestionnaireStep:
    """
    known_facts: dict of field -> value already collected (may contain nulls).
    qa_history: list of {"question": str, "answer": str} already asked/answered.
    rag_context: relevant snippets retrieved from Pinecone about what this
                 crime type's report normally requires.
    language: "English" | "Urdu" | "Roman Urdu" (PRD FR-03) — the question
              text and options are generated in this language so a Roman
              Urdu speaker isn't suddenly handed an English form.
    """
    if len(qa_history) >= MAX_QUESTIONS:
        return QuestionnaireStep(complete=True, missing_information=[], next_question=None)

    required_fields = CATEGORY_REQUIRED_FIELDS.get(
        incident_type, CATEGORY_REQUIRED_FIELDS["Other / Unclassified"])

    prompt = f"""You are helping a crime victim/witness complete an incident report
through a short, adaptive interview. Ask at most ONE next question — the single
most important missing piece of information — using large-button-friendly
options where possible so it's fast to answer on a phone during a stressful moment.

Write the "question" and "options" text in {language}. If {language} is
"Roman Urdu", write Urdu using Latin letters (e.g. "Yeh kahan hua?"), not the
Urdu script and not English.

Incident type (may be "Other" or unknown): {incident_type}
Original description from the user: \"\"\"{original_description}\"\"\"

Facts already known (null/omitted = not yet known):
{json.dumps(known_facts, indent=2)}

Questions already asked and answered so far:
{json.dumps(qa_history, indent=2)}

For this incident type, a complete report should eventually cover these
points (not necessarily in this order, and not every one needs its own
question if the description already covers it):
{json.dumps(required_fields, indent=2)}

Relevant guidance on what this type of report typically requires (from our
knowledge base, may be empty):
\"\"\"{rag_context}\"\"\"

Rules:
- Do NOT re-ask something already answered — check qa_history carefully first.
- Prefer single_choice/boolean/date/time/location/number question types with
  short concrete "options" over open-ended "text" so the user can tap a button.
- Stop and mark complete:true once the checklist above is reasonably covered
  (skip a point entirely if the description/evidence already answers it —
  don't ask again just to double-confirm). Do not interrogate for
  unnecessary detail beyond the checklist.
- Never ask for passwords, banking details, or unrelated personal data.

Return ONLY JSON matching exactly:
{{
  "complete": boolean,
  "missing_information": [list of short field names still missing, empty if complete],
  "next_question": null OR {{
      "question": string,
      "question_type": "single_choice"|"multiple_choice"|"text"|"date"|"time"|"number"|"location"|"boolean",
      "options": [list of strings, empty for text/date/time/number/location],
      "required": boolean,
      "reason": short string explaining why this is being asked
  }}
}}
"""
    data = gemini.generate_json(prompt)
    result = safe_validate(QuestionnaireStep, data)
    if result:
        return result

    # Fallback: if Gemini is unavailable or returns something unusable, ask a
    # safe generic question rather than crashing the flow.
    if len(qa_history) == 0:
        return QuestionnaireStep(
            complete=False,
            missing_information=["location"],
            next_question=Question(
                question="Where did this happen?",
                question_type="text",
                required=True,
                reason="Location could not be determined automatically.",
            ),
        )
    return QuestionnaireStep(complete=True, missing_information=[], next_question=None)
