"""
Central session-state schema so no progress is lost moving between pages.
"""
from __future__ import annotations

import streamlit as st

DEFAULT_DRAFT = {
    "language": "English",          # PRD FR-03 — English / Urdu / Roman Urdu
    "anonymous": False,              # PRD FR-11 — report without identifying info
    "category": None,               # user-selected category — canonical for
                                     # required-fields checklist and routing
    "description": "",              # raw combined user text (typed + transcribed)
    "input_methods_used": [],       # ["text", "voice", "image", "video"]
    "facts": {},                    # IncidentExtraction fields
    "crime_type": None,             # AI-suggested category — confirmation/override signal only
    "classification_confidence": None,
    "classification_explanation": "",
    "severity": None,               # Critical / High / Medium / Low (ai/urgency.py)
    "severity_reason": "",
    "verification_flags": [],       # [{"type","message","severity"}] — consistency/duplicate/abuse
    "duplicate_matches": [],        # [{"report_id","similarity","reason"}]
    "rag_context": "",
    "qa_history": [],               # [{"question": ..., "answer": ...}]
    "current_question": None,       # dict form of ai.schemas.Question
    "questionnaire_complete": False,
    "incident_date": None,
    "incident_time": None,
    "location": None,
    "evidence": [],                 # [{"name","type","ai_analysis","privacy_flags"}]
    "reporter": {},                 # {} if anonymous; else full_name/phone/email
    "summary": "",
}


def _fresh_draft() -> dict:
    # dict(DEFAULT_DRAFT) is a shallow copy — nested lists/dicts would still be
    # the SAME objects as DEFAULT_DRAFT's until reassigned here, so anything
    # mutated in place elsewhere (.append(), etc.) must get a fresh container,
    # or every session would end up sharing (and corrupting) one global list.
    fresh = dict(DEFAULT_DRAFT)
    for key in ("qa_history", "evidence", "verification_flags", "duplicate_matches"):
        fresh[key] = []
    for key in ("facts", "reporter"):
        fresh[key] = {}
    return fresh


def init_session():
    if "page" not in st.session_state:
        st.session_state.page = "home"
    if "draft" not in st.session_state:
        st.session_state.draft = _fresh_draft()
    if "last_report_id" not in st.session_state:
        st.session_state.last_report_id = None
    if "last_submission" not in st.session_state:
        st.session_state.last_submission = None


def reset_draft():
    st.session_state.draft = _fresh_draft()


def draft() -> dict:
    return st.session_state.draft
