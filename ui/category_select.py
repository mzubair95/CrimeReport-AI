"""
Incident type selection (PRD §10). The user picks a category first;
everything downstream (questionnaire checklist, severity assessment)
treats this as canonical. The AI classifier still runs later on the
free-text description, but only as a soft confirmation/override signal —
never overriding what the user tapped.
"""
from __future__ import annotations

import streamlit as st

from config.settings import CRIME_CATEGORIES
from ui.components import brand_header, go_to, progress_bar
from ui.state import draft

# Emoji per category, purely cosmetic — falls back to a generic icon.
CATEGORY_ICONS = {
    "Theft / Pickpocketing": "💰",
    "Robbery": "🚨",
    "Vehicle Theft": "🚗",
    "Assault / Physical Harm": "🤕",
    "Harassment": "🗣️",
    "Domestic / Family Safety": "🏠",
    "Fraud / Scam": "🎭",
    "Cybercrime": "💻",
    "Missing Person": "🔍",
    "Vandalism / Property Damage": "🔨",
    "Suspicious Activity": "👀",
    "Drug-related Incident": "💊",
    "Other / Unclassified": "📝",
}


def render():
    brand_header(show_tagline=False)
    progress_bar(1, 5, "Step 1 of 5 — What happened?")
    st.markdown("### Choose the category that best fits")
    st.caption("You'll be able to describe it in your own words next — this just helps "
               "us ask the right follow-up questions.")

    d = draft()

    for category in CRIME_CATEGORIES:
        icon = CATEGORY_ICONS.get(category, "📌")
        if st.button(f"{icon}  {category}", key=f"cat_{category}", use_container_width=True):
            d["category"] = category
            go_to("report")

    st.write("")
    if st.button("⬅️ Back to Home", use_container_width=True):
        go_to("home")
