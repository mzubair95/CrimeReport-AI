"""
Step 4 — Legal reference lookup ("ℹ️ Info" button), reachable from Step 3
onward once a category is set (docs/FIR_TECHNICAL_SPEC.md §2/§3.2).

Every citation shown here comes from ai/legal_service.py's RAG lookup
against the curated `legal` knowledge base — never from an LLM guessing a
section number. The disclaimer is shown every time, unconditionally.
"""
from __future__ import annotations

import logging

import streamlit as st

from ai.legal_service import lookup, DISCLAIMER
from ui.components import brand_header, go_to, card
from ui.state import draft

logger = logging.getLogger("crime_report_ai.ui.legal_lookup")


def render():
    brand_header(show_tagline=False)
    st.markdown("## ℹ️ Legal Reference Lookup")

    d = draft()
    return_page = st.session_state.get("legal_return_page", "questionnaire")

    if not d.get("category"):
        st.info("Choose an incident category first to see relevant legal references.")
        if st.button("⬅️ Back", use_container_width=True):
            go_to(return_page)
        return

    st.warning(DISCLAIMER, icon="⚠️")

    if not d.get("legal_references"):
        with st.spinner("Looking up applicable legal references..."):
            try:
                d["legal_references"] = lookup(d["category"], d.get("description", ""))
            except Exception:
                logger.exception("Legal lookup failed")
                d["legal_references"] = []

    refs = d.get("legal_references", [])
    if not refs:
        st.info(
            f"No curated legal references are available yet for **{d['category']}**. "
            "This doesn't mean no law applies — please consult a lawyer or the police "
            "for guidance specific to your situation."
        )
    else:
        st.caption(f"Showing references relevant to: **{d['category']}**")
        for ref in refs:
            card(f"""
                <b>{ref.get('statute', '')} — Section {ref.get('section_number', '')}</b><br>
                <i>{ref.get('section_title', '')}</i><br><br>
                {ref.get('summary', '')}<br><br>
                <b>Cognizable:</b> {ref.get('cognizable', 'unknown')}<br>
                <b>Bailable:</b> {ref.get('bailable', 'unknown')}<br>
                <b>Punishment range:</b> {ref.get('punishment_range', 'unknown')}<br>
                <span style="font-size:0.8rem; color:#94A3B8;">
                Source: {ref.get('source_citation', 'N/A')}</span>
            """)

    st.write("")
    if st.button("🔄 Refresh lookup", use_container_width=True):
        d["legal_references"] = []
        st.rerun()

    st.write("")
    if st.button("⬅️ Back", type="primary", use_container_width=True):
        go_to(return_page)
