"""Report submitted confirmation — case ID and status, ready for an
authorized reviewer to triage (PRD §8 end-to-end user journey, step 8)."""
from __future__ import annotations

import streamlit as st

from ui.components import brand_header, go_to
from ui.state import reset_draft


def render():
    brand_header(show_tagline=False)

    report_id = st.session_state.get("last_report_id")
    submission = st.session_state.get("last_submission") or {}

    if not report_id:
        st.warning("No report found in this session.")
        if st.button("⬅️ Back to Home"):
            go_to("home")
        return

    st.markdown("## ✅ Report Submitted")
    st.markdown(f"### Case ID: `{report_id}`")
    st.markdown("**Status:** Submitted")
    st.info(submission.get("note", ""), icon="ℹ️")
    st.caption(
        "An authorized reviewer will triage this report next. You can check "
        "its status anytime under \"My Reports\" using this case ID."
    )

    st.write("")
    pdf_bytes = st.session_state.get("last_pdf_bytes")
    json_str = st.session_state.get("last_json_str")

    col1, col2 = st.columns(2)
    with col1:
        if pdf_bytes:
            st.download_button("⬇️ Download Report PDF", data=pdf_bytes,
                                file_name=f"{report_id}.pdf", mime="application/pdf",
                                use_container_width=True)
    with col2:
        if json_str:
            st.download_button("⬇️ Download JSON", data=json_str,
                                file_name=f"{report_id}.json", mime="application/json",
                                use_container_width=True)

    st.write("")
    if st.button("📄 MY REPORTS", type="primary", use_container_width=True):
        go_to("my_reports")

    if st.button("🏠 Report Another Incident", use_container_width=True):
        reset_draft()
        go_to("home")
