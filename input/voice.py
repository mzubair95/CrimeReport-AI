"""
Voice input handling (section 8).

Streamlit's native st.audio_input records browser microphone audio directly
(works on desktop, Android, and iPhone browsers) — no extra JS component
needed. The raw audio bytes are sent straight to Gemini, which transcribes
and understands audio natively, so no separate speech-to-text provider is
required. The provider is still isolated behind this module so it could be
swapped for a dedicated STT API later (section 36).
"""
from __future__ import annotations

import logging

from ai import gemini

logger = logging.getLogger("crime_report_ai.voice")

_TRANSCRIBE_PROMPT = """Transcribe the spoken audio exactly as said, correcting
only obvious filler words. Return ONLY the transcript text, nothing else —
no labels, no quotation marks, no commentary."""


def transcribe_audio(audio_bytes: bytes, mime_type: str = "audio/wav") -> str:
    """Returns the best-effort transcript, or an empty string on failure."""
    if not audio_bytes:
        return ""
    try:
        text = gemini.generate_with_media(
            prompt=_TRANSCRIBE_PROMPT,
            media_bytes=audio_bytes,
            mime_type=mime_type,
            as_json=False,
            retries=1,
        )
        return text.strip()
    except gemini.GeminiUnavailable as exc:
        logger.warning("Voice transcription unavailable: %s", exc)
        return ""
