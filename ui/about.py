"""About / Privacy page (sections 25-26)."""
from __future__ import annotations

import streamlit as st

from config.settings import DISCLAIMER
from ai import gemini
from rag import pinecone_client
from ui.components import brand_header, go_to


def render():
    brand_header(show_tagline=False)
    st.markdown("## ℹ️ About & Privacy")

    st.markdown("""
**Crime Report.AI** is an AI-assisted crime reporting prototype built for a
hackathon. It helps a person describe an incident in their own words —
by text, voice, photo, or video — and uses AI to ask the right follow-up
questions, classify the incident, and produce a structured report.

### What this app does
- Uses Google Gemini to understand descriptions, analyze images/video, and
  generate follow-up questions.
- Uses a Retrieval-Augmented Generation (RAG) system backed by Pinecone to
  ground its questions in general reporting guidance.
- Generates a downloadable PDF and JSON report and submits it to a **demo**
  backend with a tracking ID.

### What this app does NOT do
- It is **not** connected to real emergency dispatch or any real police
  department's systems. All "authority" submission in this prototype is a
  demo/simulated backend.
- It does not provide legal advice.
- It does not automatically accuse or identify anyone — AI image/video
  analysis only describes what is visibly present.

### Privacy & data handling
- Secrets (API keys) are stored only in environment variables, never in code
  or version control.
- Only the information needed to file and follow up on a report is
  collected — no passwords or banking details are ever requested.
- Original evidence files are kept separate from AI-generated summaries and
  are never altered by the AI.
- You must explicitly review and confirm your report before it is submitted.
""")

    st.divider()
    st.markdown("**System status**")
    st.write(f"- Gemini AI: {'✅ configured' if gemini.is_available() else '⚠️ not configured'}")
    st.write(f"- Pinecone RAG: {'✅ configured' if pinecone_client.is_available() else '⚠️ not configured'}")

    st.divider()
    st.caption(DISCLAIMER)

    st.write("")
    if st.button("⬅️ Back to Home", use_container_width=True):
        go_to("home")
