"""Emergency mode (section 5) — clearly separated from AI assistance and
from official authority submission. No real dispatch integration exists;
everything here is explicitly labeled as a demo/configurable action."""
from __future__ import annotations

import streamlit as st

from config.settings import EMERGENCY_NUMBER
from ui.components import brand_header, go_to, card
from ui.state import reset_draft


def render():
    brand_header(show_tagline=False)
    st.markdown("## 🆘 Emergency")

    card(f"""
        <b>If you are in immediate danger, this app cannot help you directly.</b><br><br>
        Call <b>{EMERGENCY_NUMBER}</b> (or your local emergency number) right now.
    """)

    st.markdown(
        f'<div class="crai-emergency-btn"><a href="tel:{EMERGENCY_NUMBER}" '
        f'style="text-decoration:none;">'
        f'<button style="width:100%;min-height:3.4rem;font-size:1.15rem;'
        f'font-weight:700;border-radius:14px;border:none;background:#B91C1C;'
        f'color:white;">📞 CALL EMERGENCY SERVICES ({EMERGENCY_NUMBER})</button>'
        f'</a></div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "This button dials your device's phone app — Crime Report.AI is a "
        "prototype and is **not** itself connected to any emergency dispatch system."
    )

    st.write("")
    if st.button("🤫  START SILENT REPORT", use_container_width=True,
                  help="Continue into the AI-guided reporting flow quietly, "
                       "without a phone call — for when calling isn't safe."):
        reset_draft()
        go_to("report")

    st.write("")
    if st.button("⬅️  EXIT", use_container_width=True):
        go_to("home")

    st.write("")
    st.info(
        "**AI assistance**, **emergency calling**, and **official authority "
        "submission** are three separate things in this app. Using the AI "
        "questionnaire never itself contacts emergency services or a real "
        "police department.",
        icon="ℹ️",
    )
