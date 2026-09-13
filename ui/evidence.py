"""
Evidence management + reporter information. Original evidence files are
never altered — AI analysis (including privacy flags) is stored alongside,
never in place of, the original. Anonymous reporting (PRD FR-11, "Should")
is offered directly here.
"""
from __future__ import annotations

import streamlit as st

from ai import llm as gemini  # routed through ai/llm.py — backend set by LLM_PROVIDER
from input.image import process_image
from input.video import process_video
from ui.components import brand_header, go_to, progress_bar
from ui.state import draft

CONTACT_METHODS = ["Email", "Phone", "Either"]


def render():
    brand_header(show_tagline=False)
    progress_bar(4, 5, "Step 4 of 5 — Evidence & your contact info")

    d = draft()

    st.markdown("### Evidence")
    if d["evidence"]:
        for e in d["evidence"]:
            icon = {"image": "🖼️", "video": "🎥", "audio": "🎤", "document": "📄"}.get(e["type"], "📎")
            st.markdown(f"✓ {icon} **{e['name']}**")
            if e.get("ai_analysis"):
                st.caption(f"AI-analyzed (not confirmed fact): {e['ai_analysis']}")
            for flag in e.get("privacy_flags", []):
                st.caption(f"🔒 {flag}")
    else:
        st.caption("No evidence attached yet.")

    with st.expander("➕ Add more evidence (photo, video, or document)"):
        extra_files = st.file_uploader(
            "Supporting files", type=["jpg", "jpeg", "png", "webp", "mp4", "mov",
                                       "pdf", "docx", "txt"],
            accept_multiple_files=True, key="extra_evidence",
        )
        if extra_files and st.button("Attach & analyze", key="attach_extra"):
            _process_extra_files(extra_files)
            st.rerun()

    st.divider()
    st.markdown("### Your Information")

    anonymous = st.checkbox(
        "Report anonymously",
        value=d.get("anonymous", False),
        help="Skip providing your name/contact details. An authorized reviewer can still "
             "triage this report, but won't be able to follow up with you directly.",
        key="anonymous_toggle",
    )
    d["anonymous"] = anonymous

    reporter = d.get("reporter", {})
    if anonymous:
        st.caption("No name, phone, or email will be collected for this report.")
        full_name = phone = email = address = ""
        preferred = "Email"
    else:
        st.caption("Only what's needed to follow up with you. Never share passwords or "
                   "banking details here.")
        full_name = st.text_input("Full name", value=reporter.get("full_name", ""))
        phone = st.text_input("Phone number", value=reporter.get("phone", ""))
        email = st.text_input("Email", value=reporter.get("email", ""))
        address = st.text_input("Address (optional)", value=reporter.get("address", ""))
        preferred = st.radio("Preferred contact method", CONTACT_METHODS,
                              index=CONTACT_METHODS.index(reporter.get("preferred_contact", "Email"))
                              if reporter.get("preferred_contact") in CONTACT_METHODS else 0,
                              horizontal=True)

    consent = st.checkbox(
        "I confirm the information I've provided is accurate to the best of my "
        "knowledge, and I consent to this report being submitted for review.",
        value=reporter.get("consent", False) or d.get("_consent_given", False),
        key="consent_checkbox",
    )

    if st.button("Continue →", type="primary", use_container_width=True):
        if not anonymous and not (full_name and (phone or email)):
            st.error("Please provide your name and at least one way to reach you, "
                     "or check \"Report anonymously\".")
        elif not consent:
            st.error("Please confirm the consent checkbox to continue.")
        else:
            d["reporter"] = {} if anonymous else {
                "full_name": full_name, "phone": phone, "email": email,
                "address": address, "preferred_contact": preferred, "consent": True,
            }
            d["_consent_given"] = True
            go_to("review")

    if st.button("⬅️ Back", use_container_width=True):
        go_to("questionnaire")


def _process_extra_files(files):
    d = draft()
    with st.spinner("Analyzing attached files..."):
        for f in files:
            ext = f.name.rsplit(".", 1)[-1].lower()
            entry = {"name": f.name, "type": "document", "ai_analysis": "", "privacy_flags": []}
            try:
                if ext in ("jpg", "jpeg", "png", "webp"):
                    entry["type"] = "image"
                    analysis = process_image(f.getvalue(), f.name, incident_context=d.get("description", ""))
                    entry["ai_analysis"] = "; ".join(filter(None, [
                        "Visible: " + ", ".join(analysis.visible_items) if analysis.visible_items else "",
                        analysis.visible_damage or "",
                    ])) or "No notable details detected."
                    if analysis.id_document_visible:
                        entry["privacy_flags"].append("ID document visible — consider redacting")
                    if analysis.phone_number_visible:
                        entry["privacy_flags"].append("Phone number visible — consider redacting")
                    if analysis.people_visible:
                        entry["privacy_flags"].append("Face(s) detected")
                elif ext in ("mp4", "mov"):
                    entry["type"] = "video"
                    v = process_video(f.getvalue(), f.name)
                    entry["ai_analysis"] = v.summary
                else:
                    entry["ai_analysis"] = "Document attached as supporting evidence (not AI-analyzed)."
            except gemini.LLMUnavailable:
                entry["ai_analysis"] = "AI analysis unavailable right now."
            d["evidence"].append(entry)
