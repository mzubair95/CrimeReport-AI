"""
Pydantic models for validating every structured (JSON) response coming back
from Gemini, so the rest of the app never has to trust raw LLM output blindly.
"""
from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field, ValidationError

QuestionType = Literal[
    "single_choice", "multiple_choice", "text", "date", "time",
    "number", "location", "boolean",
]


class IncidentExtraction(BaseModel):
    """Structured facts pulled from the user's free-form description (section 7)."""
    incident_type: Optional[str] = None
    object_involved: Optional[str] = None
    location: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    injury: Optional[str] = None
    suspect_information: Optional[str] = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class ClassificationResult(BaseModel):
    """Section 11 — controlled category + confidence, never presented as proof."""
    category: str
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str = ""


class Question(BaseModel):
    """Section 15 — one dynamically generated questionnaire item."""
    question: str
    question_type: QuestionType
    options: list[str] = Field(default_factory=list)
    required: bool = True
    reason: str = ""


class QuestionnaireStep(BaseModel):
    """Section 16 — the model's verdict on whether enough info has been gathered."""
    complete: bool
    missing_information: list[str] = Field(default_factory=list)
    next_question: Optional[Question] = None


class ImageAnalysis(BaseModel):
    """Section 9 — only what is visibly present, nothing inferred about identity/intent."""
    visible_items: list[str] = Field(default_factory=list)
    visible_damage: Optional[str] = None
    people_visible: bool = False
    text_visible: bool = False
    notes: str = ""


class VideoAnalysis(BaseModel):
    """Section 10 — frame-based or direct video understanding summary."""
    summary: str = ""
    visible_items: list[str] = Field(default_factory=list)
    people_visible: bool = False
    notes: str = ""


def safe_validate(model_cls, data) -> Optional[BaseModel]:
    """Validate `data` against a Pydantic model; return None instead of raising."""
    if data is None:
        return None
    try:
        return model_cls.model_validate(data)
    except ValidationError:
        return None
