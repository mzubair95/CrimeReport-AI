"""About / Responsible AI & Privacy page (PRD §16, §23)."""
from __future__ import annotations

import streamlit as st

from config.settings import DISCLAIMER
from ai import llm
from rag import pinecone_client
from ui.components import brand_header, go_to


def render():
    brand_header(show_tagline=False)
    st.markdown("## ℹ️ About, Responsible AI & Privacy")

    st.markdown("""
**Crime Report** is an AI-powered civic safety platform prototype built for
a hackathon (Pak Angels). It helps a citizen describe an incident in their
own words — by text, voice, photo, or video, in English, Urdu, or Roman
Urdu — and uses AI to classify it, assess urgency, ask the right follow-up
questions, and produce a structured, reviewable case for an authorized
reviewer to triage.

### What this app does
- Uses an AI model (configurable — Gemini, Grok, or Groq) to understand
  descriptions, analyze images/video, generate follow-up questions, and
  assess priority.
- Runs verification-support checks: internal consistency, low-detail
  reports, and duplicate/related-report detection — all surfaced as
  neutral flags for a human reviewer, never as an accusation.
- Checks evidence photos for plausible relevance to the incident and flags
  (not automatically redacts) visible ID documents, phone numbers, or
  faces for the reviewer's awareness.
- Generates a downloadable PDF/JSON report and submits it to a **demo**
  review queue with a case ID.

### What this app does NOT do (PRD Non-Goals)
- It does **not** determine guilt, innocence, or legal liability.
- It does **not** automatically accuse a person of committing a crime.
- It does **not** independently dispatch police or emergency responders.
- It does **not** perform facial recognition or identify private
  individuals from images — a detected face is a privacy flag, not an
  identification.
- It is **not** connected to real emergency dispatch or any police
  department's systems — every "submission" goes to a demo backend only.

### Privacy & data handling
- Secrets (API keys) are stored only in environment variables, never in
  code or version control.
- Data minimization: reporting anonymously is supported — no name, phone,
  or email is required to submit a report.
- Original evidence files are kept separate from AI-generated analysis and
  are never altered by the AI.
- You must explicitly review and confirm your report before it is
  submitted, and every reviewer status change is logged for audit (FR-10).
""")

    st.divider()
    st.markdown("**System status**")
    st.write(f"- LLM ({llm.provider_name()}): "
             f"{'✅ configured' if llm.is_available() else '⚠️ not configured'}")
    st.write(f"- Pinecone RAG/duplicate detection: "
             f"{'✅ configured' if pinecone_client.is_available() else '⚠️ not configured'}")

    st.divider()
    st.caption(DISCLAIMER)

    st.write("")
    if st.button("⬅️ Back to Home", use_container_width=True):
        go_to("home")
