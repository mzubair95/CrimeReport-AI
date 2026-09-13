"""
Dynamic AI questionnaire engine (sections 14-16).

Instead of a fixed script, Gemini looks at what's already known plus
RAG-retrieved guidance on what information that type of report normally
needs, and decides the single most useful next question — or declares the
questionnaire complete.
"""
from __future__ import annotations

import json

from ai import gemini
from ai.schemas import QuestionnaireStep, Question, safe_validate

MAX_QUESTIONS = 8  # hard cap so a stressed user is never stuck answering forever


def next_question(
    incident_type: str,
    original_description: str,
    known_facts: dict,
    qa_history: list[dict],
    rag_context: str = "",
) -> QuestionnaireStep:
    """
    known_facts: dict of field -> value already collected (may contain nulls).
    qa_history: list of {"question": str, "answer": str} already asked/answered.
    rag_context: relevant snippets retrieved from Pinecone about what this
                 crime type's report normally requires.
    """
    if len(qa_history) >= MAX_QUESTIONS:
        return QuestionnaireStep(complete=True, missing_information=[], next_question=None)

    prompt = f"""You are helping a crime victim/witness complete an incident report
through a short, adaptive interview. Ask at most ONE next question — the single
most important missing piece of information — using large-button-friendly
options where possible so it's fast to answer on a phone during a stressful moment.

Incident type (may be "Other" or unknown): {incident_type}
Original description from the user: \"\"\"{original_description}\"\"\"

Facts already known (null/omitted = not yet known):
{json.dumps(known_facts, indent=2)}

Questions already asked and answered so far:
{json.dumps(qa_history, indent=2)}

Relevant guidance on what this type of report typically requires (from our
knowledge base, may be empty):
\"\"\"{rag_context}\"\"\"

Rules:
- Do NOT re-ask something already answered.
- Prefer single_choice/boolean/date/time/location/number question types with
  short concrete "options" over open-ended "text" so the user can tap a button.
- Stop and mark complete:true once you have enough to write a useful report:
  roughly what happened, when, where, and whether anyone was hurt. Do not
  interrogate for unnecessary detail.
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
