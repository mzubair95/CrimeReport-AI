"""Report review screen (section 20) — Step 5, editable summary before the
false-reporting notice and final confirmation (Step 6)."""
from __future__ import annotations

import logging

import streamlit as st

from ai.summarizer import build_incident_summary
from ui.components import brand_header, go_to, progress_bar, card
from ui.state import draft

logger = logging.getLogger("crime_report_ai.ui.review")


def render():
    brand_header(show_tagline=False)
    progress_bar(6, 8, "Step 6 of 8 — Review your report")

    d = draft()

    if not d.get("summary"):
        with st.spinner("Preparing your report summary..."):
            try:
                d["summary"] = build_incident_summary(d)
            except Exception:
                logger.exception("Summary generation failed")
                d["summary"] = d.get("description", "")

    st.markdown("## Review Your Report")

    card(f"""
        <b>Incident</b><br>
        Type: {d.get('category') or d.get('crime_type') or 'Not classified'}<br>
        Date: {d.get('incident_date') or 'Not provided'}<br>
        Time: {d.get('incident_time') or 'Not provided'}<br>
        Location: {d.get('location') or 'Not provided'}
    """)

    card(f"""
        <b>AI Summary</b> <span class="crai-badge crai-ai">AI-generated — please verify</span><br><br>
        {d.get('summary', '')}
    """)

    with st.expander("Original description (user provided)"):
        st.write(d.get("description") or "N/A")

    if d.get("qa_history"):
        with st.expander(f"Follow-up answers ({len(d['qa_history'])})"):
            for qa in d["qa_history"]:
                st.markdown(f"**{qa['question']}** — {qa['answer']}")

    evidence = d.get("evidence", [])
    card(f"<b>Evidence</b><br>{len(evidence)} file(s) attached" if evidence
         else "<b>Evidence</b><br>No files attached")

    legal_refs = d.get("legal_references", [])
    if legal_refs:
        with st.expander(f"⚖️ Legal references shown ({len(legal_refs)}) — unverified, see disclaimer"):
            for ref in legal_refs:
                st.markdown(f"**{ref.get('statute')} § {ref.get('section_number')}** — "
                            f"{ref.get('section_title')}")
    else:
        if st.button("ℹ️ View applicable legal references", use_container_width=True):
            st.session_state["legal_return_page"] = "review"
            go_to("legal_lookup")

    victim = d.get("victim", {})
    card(f"""
        <b>Personal Information</b><br>
        {victim.get('full_name', 'N/A')}<br>
        {victim.get('phone', '')} {('· ' + victim.get('email')) if victim.get('email') else ''}
    """)

    st.caption(
        "This report may contain AI-generated content — review it carefully. "
        "On the next step, you'll see a notice about false reporting and give "
        "final confirmation before it's submitted."
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("✏️ Edit", use_container_width=True):
            go_to("evidence")
    with col2:
        if st.button("Continue →", type="primary", use_container_width=True):
            go_to("false_reporting_notice")
