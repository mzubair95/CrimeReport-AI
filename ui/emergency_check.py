"""
Step 0 — Emergency check (docs/FIR_TECHNICAL_SPEC.md §2). Asked before
anything else in the reporting flow: is this in progress / an emergency
right now? Kept separate from the dedicated ui/emergency.py page (reachable
directly from Home for someone already in panic mode) — this is the
same screening question surfaced inline for someone who tapped "Report a
Crime" without first realizing it's urgent.
"""
from __future__ import annotations

import streamlit as st

from config.settings import EMERGENCY_NUMBER
from ui.components import brand_header, go_to, card, progress_bar, RED_DEEP
from ui.state import draft


def render():
    brand_header(show_tagline=False)
    progress_bar(1, 8, "Step 1 of 8 — Before we start")

    d = draft()

    st.markdown("### Is this happening right now, or are you in immediate danger?")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="crai-emergency-btn">', unsafe_allow_html=True)
        if st.button("🆘 Yes", use_container_width=True, key="ec_yes"):
            st.session_state["_emergency_flagged"] = True
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        if st.button("No, this already happened", type="primary", use_container_width=True,
                      key="ec_no"):
            d["is_emergency"] = False
            go_to("category_select")

    if st.session_state.get("_emergency_flagged"):
        st.write("")
        card(f"""
            <b>If you are in immediate danger, this app cannot help you directly.</b><br><br>
            Call <b>Police Helpline {EMERGENCY_NUMBER}</b> now.
        """)
        st.markdown(
            f'<div class="crai-emergency-btn"><a href="tel:{EMERGENCY_NUMBER}" '
            f'style="text-decoration:none;">'
            f'<button style="width:100%;min-height:3.2rem;font-size:1.1rem;'
            f'font-weight:700;border-radius:14px;border:none;background:{RED_DEEP};'
            f'color:white;">📞 CALL POLICE HELPLINE {EMERGENCY_NUMBER}</button>'
            f'</a></div>',
            unsafe_allow_html=True,
        )
        st.caption(
            "This button dials your device's phone app — Crime Report.AI is a "
            "prototype and is **not** itself connected to any emergency dispatch system."
        )
        st.write("")
        if st.button("Continue reporting anyway", use_container_width=True):
            d["is_emergency"] = True
            go_to("category_select")

    st.write("")
    if st.button("⬅️ Back to Home", use_container_width=True):
        st.session_state.pop("_emergency_flagged", None)
        go_to("home")
