"""Landing page — PRD §14 primary home actions: Report Incident, Emergency
Guidance, My Reports."""
from __future__ import annotations

import streamlit as st

from ui.components import brand_header, go_to, card
from ui.state import reset_draft


def render():
    brand_header()

    st.write("")
    if st.button("🚨  REPORT INCIDENT", type="primary", use_container_width=True):
        reset_draft()
        go_to("category_select")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="crai-emergency-btn">', unsafe_allow_html=True)
        if st.button("🆘  EMERGENCY GUIDANCE", use_container_width=True):
            go_to("emergency")
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        if st.button("📄  MY REPORTS", use_container_width=True):
            go_to("my_reports")

    st.write("")
    card("""
        <b>Or start immediately with:</b><br><br>
        🎤 Voice &nbsp;&nbsp; 📷 Photo &nbsp;&nbsp; 🎥 Video &nbsp;&nbsp; ⌨️ Text
        <br><br>
        <span style="color:#64748B; font-size:0.9rem;">
        Tap "Report Incident" — you'll be able to describe what happened
        using any combination of these, in English, Urdu, or Roman Urdu.</span>
    """)

    st.write("")
    st.caption(
        "Crime Report is an AI-assisted reporting **prototype** built for a "
        "hackathon. It is not connected to real emergency dispatch. If you are "
        "in immediate danger, call your local emergency number now."
    )
