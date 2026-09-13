"""
Central session-state schema so no progress is lost moving between pages
(section 27).
"""
from __future__ import annotations

import streamlit as st

DEFAULT_DRAFT = {
    "is_emergency": None,           # Step 0 answer — True/False, set before category selection
    "category": None,               # Step 1 user-selected category — canonical for
                                     # routing/legal-lookup/required-fields checklist
    "description": "",              # raw combined user text (typed + transcribed)
    "input_methods_used": [],       # ["text", "voice", "image", "video"]
    "facts": {},                    # IncidentExtraction fields
    "crime_type": None,             # AI-suggested category — confirmation/override signal only
    "classification_confidence": None,
    "classification_explanation": "",
    "rag_context": "",
    "qa_history": [],               # [{"question": ..., "answer": ...}]
    "current_question": None,       # dict form of ai.schemas.Question
    "questionnaire_complete": False,
    "incident_date": None,
    "incident_time": None,
    "location": None,
    "evidence": [],                 # [{"name","type","bytes" (not persisted to disk raw), "ai_analysis"}]
    "victim": {},
    "summary": "",
    "legal_references": [],         # Step 4 lookups — see ai/legal_service.py
}


def _fresh_draft() -> dict:
    # dict(DEFAULT_DRAFT) is a shallow copy — nested lists/dicts would still be
    # the SAME objects as DEFAULT_DRAFT's until reassigned here, so anything
    # mutated in place elsewhere (.append(), etc.) must get a fresh container,
    # or every session would end up sharing (and corrupting) one global list.
    fresh = dict(DEFAULT_DRAFT)
    for key in ("qa_history", "evidence", "legal_references"):
        fresh[key] = []
    for key in ("facts", "victim"):
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
