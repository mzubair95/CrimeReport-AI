"""
Dynamic AI questionnaire UI (sections 14-17). Renders whichever widget type
Gemini's next_question() response calls for, and stops asking once the
engine reports completion.
"""
from __future__ import annotations

import logging

import streamlit as st

from ai import gemini
from ai.question_engine import next_question
from ui.components import brand_header, go_to, progress_bar
from ui.state import draft

logger = logging.getLogger("crime_report_ai.ui.questionnaire")


def render():
    brand_header(show_tagline=False)
    progress_bar(2, 5, "Step 2 of 5 — A few quick questions")

    d = draft()

    if d["crime_type"]:
        st.markdown(f"**Likely category:** {d['crime_type']}  "
                    f"<span class='crai-badge crai-ai'>AI-suggested, not confirmed</span>",
                    unsafe_allow_html=True)

    if "current_question" not in st.session_state or st.session_state.get("_need_next_q", True):
        _load_next_question()

    q = st.session_state.get("current_question")

    if q is None:
        st.success("✅ We have enough information to prepare your report.")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("⬅️ Back", use_container_width=True):
                go_to("report")
        with col2:
            if st.button("Continue →", type="primary", use_container_width=True):
                go_to("evidence")
        return

    st.markdown(f"#### {q['question']}")
    if q.get("reason"):
        st.caption(q["reason"])

    answer = _render_input(q)

    st.write("")
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("⏭ Skip", use_container_width=True):
            _submit_answer(q, "Not provided")
    with col2:
        if st.button("Next →", type="primary", use_container_width=True):
            if q.get("required") and (answer is None or answer == "" or answer == []):
                st.error("This helps us route your report correctly — please answer, or tap Skip.")
            else:
                _submit_answer(q, answer)


def _render_input(q: dict):
    qtype = q.get("question_type")
    options = q.get("options") or []
    key = f"qa_input_{len(st.session_state.draft['qa_history'])}"

    if qtype == "single_choice" and options:
        return st.radio("Choose one:", options, key=key, label_visibility="collapsed")
    if qtype == "boolean":
        return st.radio("Choose one:", ["Yes", "No", "Not sure"], key=key,
                         label_visibility="collapsed")
    if qtype == "multiple_choice" and options:
        return st.multiselect("Choose all that apply:", options, key=key,
                               label_visibility="collapsed")
    if qtype == "date":
        return str(st.date_input("Date", key=key))
    if qtype == "time":
        return str(st.time_input("Time", key=key))
    if qtype == "number":
        return st.number_input("Number", step=1, key=key, label_visibility="collapsed")
    if qtype == "location":
        return _location_input(key)
    # default: free text
    return st.text_input("Your answer", key=key, label_visibility="collapsed")


def _location_input(key: str):
    st.caption("Only share what you're comfortable with — location is used to route your report.")
    mode = st.radio("Location", ["📍 Use my location", "✍️ Enter manually"],
                     key=f"{key}_mode", label_visibility="collapsed", horizontal=True)
    if mode.startswith("📍"):
        st.caption("Browser geolocation isn't available in this embedded view — "
                   "please enter the location manually below.")
    return st.text_input("Location", key=f"{key}_text", placeholder="Street, area, or city")


def _load_next_question():
    d = draft()
    try:
        step = next_question(
            incident_type=d.get("crime_type") or "Other",
            original_description=d.get("description", ""),
            known_facts=d.get("facts", {}),
            qa_history=d.get("qa_history", []),
            rag_context=d.get("rag_context", ""),
        )
    except Exception:
        logger.exception("Question engine failed")
        st.session_state.current_question = None
        st.session_state["_need_next_q"] = False
        return

    if step.complete or step.next_question is None:
        st.session_state.current_question = None
    else:
        st.session_state.current_question = step.next_question.model_dump()
    st.session_state["_need_next_q"] = False


def _submit_answer(q: dict, answer):
    d = draft()
    answer_str = ", ".join(answer) if isinstance(answer, list) else str(answer)
    d["qa_history"].append({"question": q["question"], "answer": answer_str})

    # Fold a couple of well-known question types straight into structured fields.
    ql = q["question"].lower()
    if "where" in ql or q.get("question_type") == "location":
        d["location"] = answer_str
    if "when" in ql and q.get("question_type") in ("date", "text"):
        d["incident_date"] = answer_str
    if "time" in ql and q.get("question_type") == "time":
        d["incident_time"] = answer_str

    st.session_state["_need_next_q"] = True
    st.rerun()
