"""
Shared UI building blocks: global CSS (mobile-friendly, large-button, card
style) and small helpers reused across every page.
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from config.settings import APP_NAME, APP_TAGLINE, DISCLAIMER, BASE_DIR

# Brand palette, matched to the Crime Report.AI shield logo: a deep-blue-to-red
# duotone (trustworthy blue for the shield/authority side, alert red for the
# urgency side), with a white/navy neutral base for everyday readability.
BLUE_DEEP = "#123B91"
BLUE_BRIGHT = "#2E8FE8"
RED_BRIGHT = "#F0432E"
RED_DEEP = "#C81E22"
ACCENT = "#0B1330"        # near-navy — trustworthy, calm text color
SURFACE = "#F4F7FE"

BRAND_GRADIENT = f"linear-gradient(135deg, {BLUE_DEEP} 0%, {BLUE_BRIGHT} 38%, {RED_BRIGHT} 72%, {RED_DEEP} 100%)"

LOGO_PATH = BASE_DIR / "assets" / "logo.png"


def has_logo() -> bool:
    return LOGO_PATH.exists()


PRIMARY = RED_DEEP  # kept for modules that still import PRIMARY directly

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
        border: 1px solid #DCE3F5;
        transition: all 0.15s ease;
    }}
    .stButton > button:hover {{
        border-color: {BLUE_DEEP};
        transform: translateY(-1px);
    }}
    /* Primary CTAs (type="primary") get the full brand gradient */
    .stButton > button[kind="primary"] {{
        background: {BRAND_GRADIENT} !important;
        border: none !important;
        color: white !important;
        box-shadow: 0 4px 14px rgba(18, 59, 145, 0.25);
    }}
    .stButton > button[kind="primary"]:hover {{
        filter: brightness(1.06);
        transform: translateY(-1px);
    }}
    div[data-testid="stForm"] {{
        border: none;
        padding: 0;
    }}
    .crai-brand-row {{
        display: flex;
        align-items: center;
        gap: 0.6rem;
        margin-bottom: 0.1rem;
    }}
    .crai-brand {{
        font-size: 1.6rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        margin: 0;
        background: {BRAND_GRADIENT};
        -webkit-background-clip: text;
        background-clip: text;
        -webkit-text-fill-color: transparent;
    }}
    .crai-tagline {{
        color: #5B6A94;
        font-size: 0.95rem;
        margin-top: -0.1rem;
        margin-bottom: 1.2rem;
    }}
    .crai-card {{
        background: {SURFACE};
        border: 1px solid #DCE3F5;
        border-left: 4px solid {BLUE_BRIGHT};
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
        background: #FCE4E2;
        color: {RED_DEEP};
    }}
    .crai-badge-ok {{
        background: #DCFCE7;
        color: #166534;
    }}
    .crai-badge-ai {{
        background: #E0E9FF;
        color: {BLUE_DEEP};
    }}
    .crai-disclaimer {{
        font-size: 0.78rem;
        color: #94A3B8;
        border-top: 1px solid #E2E8F0;
        padding-top: 0.8rem;
        margin-top: 2rem;
    }}
    .crai-emergency-btn button {{
        background: {RED_DEEP} !important;
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
    if has_logo():
        col_logo, col_text = st.columns([1, 5], vertical_alignment="center")
        with col_logo:
            st.image(str(LOGO_PATH), width=56)
        with col_text:
            st.markdown(f'<p class="crai-brand">{APP_NAME}</p>', unsafe_allow_html=True)
    else:
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
