"""Emergency Guidance (PRD §14 home action) — clearly separated from AI
report intake and from review/triage. No real dispatch integration exists;
everything here is explicitly labeled as a demo/configurable action."""
from __future__ import annotations

import streamlit as st

from config.settings import EMERGENCY_NUMBER
from ui.components import brand_header, go_to, card, RED_DEEP
from ui.state import reset_draft


def render():
    brand_header(show_tagline=False)
    st.markdown("## 🆘 Emergency Guidance")

    card(f"""
        <b>If you are in immediate danger, this app cannot help you directly.</b><br><br>
        Call <b>{EMERGENCY_NUMBER}</b> (or your local emergency number) right now.
    """)

    st.markdown(
        f'<div class="crai-emergency-btn"><a href="tel:{EMERGENCY_NUMBER}" '
        f'style="text-decoration:none;">'
        f'<button style="width:100%;min-height:3.4rem;font-size:1.15rem;'
        f'font-weight:700;border-radius:14px;border:none;background:{RED_DEEP};'
        f'color:white;">📞 CALL {EMERGENCY_NUMBER}</button>'
        f'</a></div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "This button dials your device's phone app — Crime Report is a "
        "prototype and is **not** itself connected to any emergency dispatch system."
    )

    st.write("")
    if st.button("📝  Report an Incident Instead", use_container_width=True,
                  help="If this isn't an active emergency, continue to the guided report flow."):
        reset_draft()
        go_to("category_select")

    st.write("")
    if st.button("⬅️  Back to Home", use_container_width=True):
        go_to("home")

    st.write("")
    st.info(
        "**AI-assisted reporting**, **emergency calling**, and **authorized "
        "review/response** are three separate things in this app. Using the "
        "report flow never itself contacts emergency services or dispatches "
        "a responder.",
        icon="ℹ️",
    )
