"""
Shared UI building blocks: global CSS (mobile-friendly, large-button, card
style) and small helpers reused across every page.
"""
from __future__ import annotations

import streamlit as st

from config.settings import APP_NAME, APP_TAGLINE, DISCLAIMER

PRIMARY = "#B91C1C"       # safety red — used sparingly, for emergency/alerts only
ACCENT = "#0F172A"        # deep slate — trustworthy, calm
SURFACE = "#F8FAFC"

GLOBAL_CSS = f"""
<style>
    #MainMenu, header, footer {{visibility: hidden;}}
    .block-container {{
        padding-top: 1.2rem;
        padding-bottom: 3rem;
        max-width: 720px;
    }}
    /* Large, thumb-friendly buttons everywhere */
    .stButton > button {{
        width: 100%;
        min-height: 3.1rem;
        font-size: 1.05rem;
        font-weight: 600;
        border-radius: 14px;
        border: 1px solid #E2E8F0;
        transition: all 0.15s ease;
    }}
    .stButton > button:hover {{
        border-color: {ACCENT};
        transform: translateY(-1px);
    }}
    div[data-testid="stForm"] {{
        border: none;
        padding: 0;
    }}
    .crai-brand {{
        font-size: 1.6rem;
        font-weight: 800;
        color: {ACCENT};
        letter-spacing: -0.02em;
        margin-bottom: 0;
    }}
    .crai-tagline {{
        color: #64748B;
        font-size: 0.95rem;
        margin-top: -0.3rem;
        margin-bottom: 1.2rem;
    }}
    .crai-card {{
        background: {SURFACE};
        border: 1px solid #E2E8F0;
        border-radius: 16px;
        padding: 1.1rem 1.3rem;
        margin-bottom: 0.9rem;
    }}
    .crai-badge {{
        display: inline-block;
        padding: 0.15rem 0.65rem;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 700;
        background: #FEE2E2;
        color: {PRIMARY};
    }}
    .crai-badge-ok {{
        background: #DCFCE7;
        color: #166534;
    }}
    .crai-badge-ai {{
        background: #E0E7FF;
        color: #3730A3;
    }}
    .crai-disclaimer {{
        font-size: 0.78rem;
        color: #94A3B8;
        border-top: 1px solid #E2E8F0;
        padding-top: 0.8rem;
        margin-top: 2rem;
    }}
    .crai-emergency-btn button {{
        background: {PRIMARY} !important;
        color: white !important;
        border: none !important;
    }}
    @media (max-width: 480px) {{
        .block-container {{ padding-left: 0.8rem; padding-right: 0.8rem; }}
    }}
</style>
"""


def inject_css():
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


def brand_header(show_tagline: bool = True):
    st.markdown(f'<p class="crai-brand">🛡️ {APP_NAME}</p>', unsafe_allow_html=True)
    if show_tagline:
        st.markdown(f'<p class="crai-tagline">{APP_TAGLINE}</p>', unsafe_allow_html=True)


def top_nav(current: str):
    """Minimal, low-clutter navigation strip — kept small on purpose for
    someone reporting under stress."""
    cols = st.columns(4)
    labels = [("home", "🏠 Home"), ("status", "🔎 Status"),
              ("dashboard", "📊 Dashboard"), ("about", "ℹ️ About")]
    for col, (key, label) in zip(cols, labels):
        with col:
            if st.button(label, key=f"nav_{key}", disabled=(current == key),
                         use_container_width=True):
                go_to(key)


def go_to(page: str, **extra_state):
    st.session_state.page = page
    for k, v in extra_state.items():
        st.session_state[k] = v
    st.rerun()


def disclaimer_footer():
    st.markdown(f'<div class="crai-disclaimer">{DISCLAIMER}</div>', unsafe_allow_html=True)


def progress_bar(step: int, total_steps: int, label: str = ""):
    st.progress(step / total_steps, text=label or f"Step {step} of {total_steps}")


def card(content_html: str):
    st.markdown(f'<div class="crai-card">{content_html}</div>', unsafe_allow_html=True)
