"""
Tests for question_engine + schema validation. Falls back gracefully (and
skips the live-Gemini assertions) if GEMINI_API_KEY isn't set, so CI without
secrets still runs the offline checks.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai.schemas import Question, QuestionnaireStep, safe_validate
from ai import gemini


def test_safe_validate_rejects_bad_data():
    assert safe_validate(Question, {"question": "x"}) is None  # missing required fields
    assert safe_validate(Question, None) is None


def test_safe_validate_accepts_good_data():
    q = safe_validate(Question, {
        "question": "Was anyone injured?",
        "question_type": "boolean",
        "options": ["Yes", "No", "Not sure"],
        "required": True,
        "reason": "Determine medical relevance",
    })
    assert isinstance(q, Question)
    assert q.question_type == "boolean"


def test_question_engine_live_or_skips():
    from ai.question_engine import next_question
    step = next_question(
        incident_type="Theft",
        original_description="Someone stole my phone from my car.",
        known_facts={"object_involved": "phone"},
        qa_history=[],
    )
    assert isinstance(step, QuestionnaireStep)
    if not gemini.is_available():
        # Without a configured key we still expect the safe fallback question.
        assert step.next_question is not None or step.complete


if __name__ == "__main__":
    test_safe_validate_rejects_bad_data()
    test_safe_validate_accepts_good_data()
    test_question_engine_live_or_skips()
    print("Question engine tests passed.")
