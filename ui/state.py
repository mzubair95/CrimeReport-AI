"""
Central session-state schema so no progress is lost moving between pages
(section 27).
"""
from __future__ import annotations

import streamlit as st

DEFAULT_DRAFT = {
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
}


def init_session():
    if "page" not in st.session_state:
        st.session_state.page = "home"
    if "draft" not in st.session_state:
        st.session_state.draft = dict(DEFAULT_DRAFT)
    if "last_report_id" not in st.session_state:
        st.session_state.last_report_id = None
    if "last_submission" not in st.session_state:
        st.session_state.last_submission = None


def reset_draft():
    st.session_state.draft = dict(DEFAULT_DRAFT)
    st.session_state.draft["qa_history"] = []
    st.session_state.draft["evidence"] = []
    st.session_state.draft["facts"] = {}
    st.session_state.draft["victim"] = {}


def draft() -> dict:
    return st.session_state.draft
