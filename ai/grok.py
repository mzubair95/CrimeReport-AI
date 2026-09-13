"""
Thin, resilient wrapper around xAI's Grok API — an alternative LLM backend
to ai/gemini.py, selected via LLM_PROVIDER=grok in .env (section 36: the LLM
must be swappable without rewriting the rest of the app).

Grok exposes an OpenAI-compatible Chat Completions endpoint, so this uses
the `openai` SDK pointed at https://api.x.ai/v1 rather than a bespoke client.

Note: Grok's chat endpoint accepts text + images, but not raw audio/video the
way Gemini does. generate_with_media() only supports image mime types here —
video always falls back to frame extraction (input/video.py), and voice
transcription is handled locally by Whisper (input/voice.py), independent of
whichever LLM_PROVIDER is selected.
"""
from __future__ import annotations

import base64
import json
import logging
import re
import time
from typing import Any, Optional

from config import settings
from ai.errors import LLMUnavailable

logger = logging.getLogger("crime_report_ai.grok")

_client = None
_client_error: Optional[str] = None

_IMAGE_MIME_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}


def _get_client():
    """Lazily create the OpenAI-compatible client so import never crashes without a key."""
    global _client, _client_error
    if _client is not None or _client_error is not None:
        return _client
    if not settings.grok_configured():
        _client_error = "GROK_API_KEY is not configured."
        return None
    try:
        from openai import OpenAI
        _client = OpenAI(api_key=settings.GROK_API_KEY, base_url=settings.GROK_BASE_URL)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Failed to initialize Grok client")
        _client_error = f"Could not initialize Grok client: {exc}"
    return _client


def is_available() -> bool:
    return _get_client() is not None


def get_client():
    return _get_client()


def _extract_json_block(text: str) -> str:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        return fence.group(1).strip()
    return text


def _try_parse_json(text: str) -> Optional[dict | list]:
    candidate = _extract_json_block(text)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start = candidate.find(open_ch)
        end = candidate.rfind(close_ch)
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(candidate[start:end + 1])
            except json.JSONDecodeError:
                continue
    return None


def generate_text(prompt: str, system_instruction: str | None = None,
                   temperature: float = 0.4, retries: int = 2) -> str:
    client = _get_client()
    if client is None:
        raise LLMUnavailable(_client_error or "Grok not configured")

    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})

    last_error = None
    for attempt in range(retries + 1):
        try:
            resp = client.chat.completions.create(
                model=settings.GROK_TEXT_MODEL,
                messages=messages,
                temperature=temperature,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as exc:
            last_error = exc
            logger.warning("Grok generate_text attempt %s failed: %s", attempt, exc)
            time.sleep(min(2 ** attempt, 4))
    raise LLMUnavailable(f"Grok text generation failed: {last_error}")


def generate_json(prompt: str, system_instruction: str | None = None,
                   temperature: float = 0.2, retries: int = 2) -> Optional[dict | list]:
    """Retry -> repair -> fallback JSON parsing (section 29), same contract as ai.gemini."""
    client = _get_client()
    if client is None:
        logger.warning("Grok not configured; cannot generate JSON")
        return None

    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})

    last_raw = ""
    for attempt in range(retries + 1):
        try:
            resp = client.chat.completions.create(
                model=settings.GROK_TEXT_MODEL,
                messages=messages,
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            last_raw = resp.choices[0].message.content or ""
            parsed = _try_parse_json(last_raw)
            if parsed is not None:
                return parsed
            logger.warning("Grok JSON parse failed on attempt %s: %r", attempt, last_raw[:300])
        except Exception as exc:
            logger.warning("Grok generate_json attempt %s failed: %s", attempt, exc)
        time.sleep(min(2 ** attempt, 4))

    if last_raw:
        try:
            repair_messages = [{
                "role": "user",
                "content": "The following text was supposed to be valid JSON but failed to "
                            "parse. Return ONLY corrected, valid JSON with no explanation:\n\n"
                            + last_raw,
            }]
            resp = client.chat.completions.create(
                model=settings.GROK_TEXT_MODEL,
                messages=repair_messages,
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            parsed = _try_parse_json(resp.choices[0].message.content or "")
            if parsed is not None:
                return parsed
        except Exception as exc:
            logger.warning("Grok JSON repair pass failed: %s", exc)

    return None


def generate_with_media(prompt: str, media_bytes: bytes, mime_type: str,
                         system_instruction: str | None = None,
                         as_json: bool = False, temperature: float = 0.2,
                         retries: int = 1) -> Any:
    """Image analysis only (see module docstring) — raises LLMUnavailable for
    audio/video so callers fall back to their non-Grok-specific paths."""
    if mime_type not in _IMAGE_MIME_TYPES:
        raise LLMUnavailable(
            f"Grok backend does not support direct analysis of {mime_type}; "
            "use frame extraction / local transcription instead."
        )

    client = _get_client()
    if client is None:
        raise LLMUnavailable(_client_error or "Grok not configured")

    b64 = base64.b64encode(media_bytes).decode("ascii")
    content = [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}},
    ]
    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": content})

    last_error = None
    for attempt in range(retries + 1):
        try:
            resp = client.chat.completions.create(
                model=settings.GROK_VISION_MODEL,
                messages=messages,
                temperature=temperature,
                response_format={"type": "json_object"} if as_json else None,
            )
            text = (resp.choices[0].message.content or "").strip()
            if as_json:
                parsed = _try_parse_json(text)
                if parsed is not None:
                    return parsed
                last_error = "invalid JSON returned"
                continue
            return text
        except Exception as exc:
            last_error = exc
            logger.warning("Grok media call attempt %s failed: %s", attempt, exc)
            time.sleep(min(2 ** attempt, 4))
    raise LLMUnavailable(f"Grok media analysis failed: {last_error}")
