"""
Voice input handling (section 8).

Streamlit's native st.audio_input records browser microphone audio directly
(works on desktop, Android, and iPhone browsers) — no extra JS component
needed. Transcription runs locally via faster-whisper (CTranslate2/Whisper),
kept independent of whichever LLM_PROVIDER is configured for the rest of the
app (section 36) — not every LLM API accepts raw audio the way Gemini does,
so a local, free, offline STT model keeps voice input working regardless of
which LLM backend is selected.
"""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from config import settings

logger = logging.getLogger("crime_report_ai.voice")

_model = None
_model_error: str | None = None


def _get_model():
    """Lazily load the Whisper model so import/startup never blocks on it."""
    global _model, _model_error
    if _model is not None or _model_error is not None:
        return _model
    if not settings.WHISPER_MODEL_SIZE:
        _model_error = "WHISPER_MODEL_SIZE is not configured."
        return None
    try:
        from faster_whisper import WhisperModel
        _model = WhisperModel(settings.WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Failed to load Whisper model")
        _model_error = f"Could not load local speech-to-text model: {exc}"
    return _model


def is_available() -> bool:
    return _get_model() is not None


def transcribe_audio(audio_bytes: bytes, mime_type: str = "audio/wav") -> str:
    """Returns the best-effort transcript, or an empty string on failure."""
    if not audio_bytes:
        return ""
    model = _get_model()
    if model is None:
        logger.warning("Voice transcription unavailable: %s", _model_error)
        return ""

    suffix = ".wav" if "wav" in mime_type else ".ogg" if "ogg" in mime_type else ".m4a"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        segments, _info = model.transcribe(tmp_path, beam_size=5)
        return " ".join(seg.text.strip() for seg in segments).strip()
    except Exception:
        logger.exception("Transcription failed")
        return ""
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)
