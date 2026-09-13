"""
Crime reporting interface (sections 6-10): combine text, voice, photo, and
video into one incident description, then hand off to classification + RAG
+ the dynamic questionnaire.
"""
from __future__ import annotations

import logging

import streamlit as st

from ai import llm as gemini  # routed through ai/llm.py — backend set by LLM_PROVIDER
from ai.classifier import extract_incident_facts, classify_incident
from input.voice import transcribe_audio
from input.image import process_image
from input.video import process_video
from rag.retriever import retrieve_context
from ui.components import brand_header, go_to, progress_bar
from ui.state import draft

logger = logging.getLogger("crime_report_ai.ui.report")


def render():
    brand_header(show_tagline=False)
    progress_bar(1, 5, "Step 1 of 5 — Tell us what happened")
    st.markdown("### How would you like to report?")
    st.caption("Use one or combine several — voice, a photo, and text together works great.")

    d = draft()

    tab_text, tab_voice, tab_photo, tab_video = st.tabs(
        ["⌨️ Type it", "🎤 Speak", "📷 Photo", "🎥 Video"]
    )

    with tab_text:
        typed = st.text_area(
            "Describe what happened...",
            value=st.session_state.get("typed_description", ""),
            height=140,
            placeholder="e.g. Someone stole my phone from my car last night.",
            key="typed_description",
        )

    with tab_voice:
        st.write("Record your statement — you'll be able to review and edit the text.")
        audio = st.audio_input("Tap to record", key="voice_recording")
        if audio is not None and st.session_state.get("_last_audio_id") != id(audio):
            with st.spinner("Transcribing your statement... (first use loads the local "
                              "speech-to-text model, which can take a moment)"):
                try:
                    transcript = transcribe_audio(audio.getvalue(), mime_type="audio/wav")
                except Exception:
                    logger.exception("Transcription failed")
                    transcript = ""
            if not transcript:
                st.error("We're temporarily unable to transcribe audio. "
                          "Please try again or continue using text input.")
            st.session_state.voice_transcript = transcript
            st.session_state["_last_audio_id"] = id(audio)

        if st.session_state.get("voice_transcript"):
            st.markdown("**Your statement:**")
            edited = st.text_area(
                "Edit if anything is wrong before continuing:",
                value=st.session_state.voice_transcript,
                key="voice_transcript_edit",
                height=120,
            )
            st.session_state.voice_transcript = edited

    with tab_photo:
        photos = st.file_uploader(
            "Upload photo evidence (damage, scene, screenshots, etc.)",
            type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True, key="photo_uploads",
        )

    with tab_video:
        video = st.file_uploader(
            "Upload a video clip", type=["mp4", "mov", "m4v"], key="video_upload",
        )
        st.caption("Large videos are analyzed via extracted key frames rather than "
                   "full playback, and are labeled as AI-assisted analysis.")

    st.write("")
    if st.button("Analyze & Continue →", type="primary", use_container_width=True):
        _handle_continue(photos_files=photos, video_file=video)

    st.write("")
    if st.button("⬅️ Back to Home", use_container_width=True):
        go_to("home")


def _handle_continue(photos_files, video_file):
    d = draft()
    typed = st.session_state.get("typed_description", "").strip()
    voice_text = st.session_state.get("voice_transcript", "").strip()

    combined_parts = []
    methods_used = []
    if typed:
        combined_parts.append(typed)
        methods_used.append("text")
    if voice_text:
        combined_parts.append(voice_text)
        methods_used.append("voice")

    if not combined_parts and not photos_files and not video_file:
        st.error("Please describe what happened using text, voice, a photo, or a video "
                  "before continuing.")
        return

    if not gemini.is_available():
        st.warning(
            f"⚠️ AI features are not fully configured ({gemini.provider_name().upper()} "
            "API key missing), so classification and follow-up questions will be "
            "limited. You can still complete and submit a basic report.",
            icon="⚠️",
        )

    evidence = []
    with st.spinner("Analyzing evidence..."):
        for f in (photos_files or []):
            try:
                analysis = process_image(f.getvalue(), f.name)
                note = _format_image_note(analysis)
            except Exception:
                logger.exception("Image analysis failed for %s", f.name)
                note = "AI analysis unavailable for this image."
            evidence.append({"name": f.name, "type": "image", "ai_analysis": note})
            methods_used.append("image")

        if video_file is not None:
            try:
                v_analysis = process_video(video_file.getvalue(), video_file.name)
                note = f"{v_analysis.summary} Items noted: {', '.join(v_analysis.visible_items) or 'none'}."
            except Exception:
                logger.exception("Video analysis failed for %s", video_file.name)
                note = "AI analysis unavailable for this video."
            evidence.append({"name": video_file.name, "type": "video", "ai_analysis": note})
            methods_used.append("video")

    description = " ".join(combined_parts).strip()
    if not description and evidence:
        description = "No written description provided; see AI-analyzed evidence below."

    with st.spinner("Understanding your report..."):
        try:
            facts = extract_incident_facts(description) if description else None
            classification = classify_incident(
                description,
                extra_context=" ".join(e.get("ai_analysis", "") for e in evidence),
            ) if description else None
        except gemini.LLMUnavailable:
            facts, classification = None, None
            st.error("We're temporarily unable to reach the AI service. "
                      "Please try again shortly.")

        rag_context = ""
        try:
            if classification:
                rag_context = retrieve_context(description, category=None)
        except Exception:
            logger.exception("RAG retrieval failed")

    d["description"] = description
    d["input_methods_used"] = sorted(set(methods_used))
    d["facts"] = facts.model_dump() if facts else {}
    d["crime_type"] = classification.category if classification else None
    d["classification_confidence"] = classification.confidence if classification else None
    d["classification_explanation"] = classification.explanation if classification else ""
    d["rag_context"] = rag_context
    d["evidence"] = evidence
    d["location"] = d["facts"].get("location")
    d["incident_date"] = d["facts"].get("date")
    d["incident_time"] = d["facts"].get("time")

    go_to("questionnaire")


def _format_image_note(analysis) -> str:
    parts = []
    if analysis.visible_items:
        parts.append("Visible: " + ", ".join(analysis.visible_items))
    if analysis.visible_damage:
        parts.append(f"Damage noted: {analysis.visible_damage}")
    parts.append("People visible" if analysis.people_visible else "No people clearly visible")
    if analysis.notes:
        parts.append(analysis.notes)
    return "; ".join(parts)
