"""Report submitted confirmation (section 22)."""
from __future__ import annotations

import streamlit as st

from ui.components import brand_header, go_to, progress_bar
from ui.state import reset_draft


def render():
    brand_header(show_tagline=False)
    progress_bar(6, 6, "Step 6 of 6 — Submitted")

    report_id = st.session_state.get("last_report_id")
    submission = st.session_state.get("last_submission") or {}

    if not report_id:
        st.warning("No report found in this session.")
        if st.button("⬅️ Back to Home"):
            go_to("home")
        return

    st.markdown("## ✅ Report Submitted")
    st.markdown(f"### Report ID: `{report_id}`")
    st.markdown("**Status:** RECEIVED")
    st.caption(f"Routed to: {submission.get('authority_name', 'Demo backend')}")
    st.info(submission.get("note", ""), icon="ℹ️")

    st.write("")
    pdf_bytes = st.session_state.get("last_pdf_bytes")
    json_str = st.session_state.get("last_json_str")

    col1, col2 = st.columns(2)
    with col1:
        if pdf_bytes:
            st.download_button("⬇️ DOWNLOAD PDF", data=pdf_bytes,
                                file_name=f"{report_id}.pdf", mime="application/pdf",
                                use_container_width=True)
    with col2:
        if json_str:
            st.download_button("⬇️ DOWNLOAD JSON", data=json_str,
                                file_name=f"{report_id}.json", mime="application/json",
                                use_container_width=True)

    st.write("")
    if st.button("🔎 VIEW REPORT STATUS", use_container_width=True):
        st.session_state.status_lookup_id = report_id
        go_to("status")

    if st.button("🏠 Report Another Incident", use_container_width=True):
        reset_draft()
        go_to("home")
