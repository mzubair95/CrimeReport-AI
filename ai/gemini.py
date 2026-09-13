"""
Thin, resilient wrapper around the Gemini API (google-genai SDK).

Every other module talks to Gemini only through this file, so the LLM
provider can be swapped without touching the rest of the app (section 36).
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Optional

from config import settings

logger = logging.getLogger("crime_report_ai.gemini")

_client = None
_client_error: Optional[str] = None


def _get_client():
    """Lazily create the genai client so import never crashes without a key."""
    global _client, _client_error
    if _client is not None or _client_error is not None:
        return _client
    if not settings.gemini_configured():
        _client_error = "GEMINI_API_KEY is not configured."
        return None
    try:
        from google import genai
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Failed to initialize Gemini client")
        _client_error = f"Could not initialize Gemini client: {exc}"
    return _client


class GeminiUnavailable(RuntimeError):
    """Raised when Gemini cannot be reached / is not configured."""


def is_available() -> bool:
    return _get_client() is not None


def get_client():
    """Public accessor for the shared genai client (e.g. for embeddings)."""
    return _get_client()


def _extract_json_block(text: str) -> str:
    """Strip ```json ... ``` fences (or plain ``` fences) if present."""
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
    # Repair attempt: grab the outermost {...} or [...] substring.
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start = candidate.find(open_ch)
        end = candidate.rfind(close_ch)
        if start != -1 and end != -1 and end > start:
            snippet = candidate[start:end + 1]
            try:
                return json.loads(snippet)
            except json.JSONDecodeError:
                continue
    return None


def generate_text(prompt: str, system_instruction: str | None = None,
                   temperature: float = 0.4, retries: int = 2) -> str:
    """Plain text generation with retry-on-failure. Raises GeminiUnavailable."""
    client = _get_client()
    if client is None:
        raise GeminiUnavailable(_client_error or "Gemini not configured")

    from google.genai import types
    cfg = types.GenerateContentConfig(
        temperature=temperature,
        system_instruction=system_instruction,
    )
    last_error = None
    for attempt in range(retries + 1):
        try:
            resp = client.models.generate_content(
                model=settings.GEMINI_TEXT_MODEL,
                contents=prompt,
                config=cfg,
            )
            return (resp.text or "").strip()
        except Exception as exc:  # network/timeout/rate-limit
            last_error = exc
            logger.warning("Gemini generate_text attempt %s failed: %s", attempt, exc)
            time.sleep(min(2 ** attempt, 4))
    raise GeminiUnavailable(f"Gemini text generation failed: {last_error}")


def generate_json(prompt: str, system_instruction: str | None = None,
                   temperature: float = 0.2, retries: int = 2) -> Optional[dict | list]:
    """
    Generate structured JSON with robust parsing (section 29):
    retry -> repair -> fallback. Returns None (never raises) on total failure
    so callers can fall back gracefully instead of crashing.
    """
    client = _get_client()
    if client is None:
        logger.warning("Gemini not configured; cannot generate JSON")
        return None

    from google.genai import types
    cfg = types.GenerateContentConfig(
        temperature=temperature,
        system_instruction=system_instruction,
        response_mime_type="application/json",
    )
    last_raw = ""
    for attempt in range(retries + 1):
        try:
            resp = client.models.generate_content(
                model=settings.GEMINI_TEXT_MODEL,
                contents=prompt,
                config=cfg,
            )
            last_raw = resp.text or ""
            parsed = _try_parse_json(last_raw)
            if parsed is not None:
                return parsed
            logger.warning("Gemini JSON parse failed on attempt %s: %r", attempt, last_raw[:300])
        except Exception as exc:
            logger.warning("Gemini generate_json attempt %s failed: %s", attempt, exc)
        time.sleep(min(2 ** attempt, 4))

    # Final repair attempt: ask Gemini to fix its own broken output.
    if last_raw:
        try:
            repair_prompt = (
                "The following text was supposed to be valid JSON but failed to "
                "parse. Return ONLY corrected, valid JSON with no explanation:\n\n"
                f"{last_raw}"
            )
            resp = client.models.generate_content(
                model=settings.GEMINI_TEXT_MODEL,
                contents=repair_prompt,
                config=cfg,
            )
            parsed = _try_parse_json(resp.text or "")
            if parsed is not None:
                return parsed
        except Exception as exc:
            logger.warning("Gemini JSON repair pass failed: %s", exc)

    return None


def generate_with_media(prompt: str, media_bytes: bytes, mime_type: str,
                         system_instruction: str | None = None,
                         as_json: bool = False, temperature: float = 0.2,
                         retries: int = 1) -> Any:
    """
    Multimodal call: send raw bytes (image/audio/video) plus a text prompt.
    Used for vision analysis, audio transcription/understanding, and video
    understanding (sections 8-10).
    """
    client = _get_client()
    if client is None:
        raise GeminiUnavailable(_client_error or "Gemini not configured")

    from google.genai import types
    part = types.Part.from_bytes(data=media_bytes, mime_type=mime_type)
    cfg = types.GenerateContentConfig(
        temperature=temperature,
        system_instruction=system_instruction,
        response_mime_type="application/json" if as_json else None,
    )
    last_error = None
    for attempt in range(retries + 1):
        try:
            resp = client.models.generate_content(
                model=settings.GEMINI_VISION_MODEL,
                contents=[part, prompt],
                config=cfg,
            )
            text = (resp.text or "").strip()
            if as_json:
                parsed = _try_parse_json(text)
                if parsed is not None:
                    return parsed
                last_error = "invalid JSON returned"
                continue
            return text
        except Exception as exc:
            last_error = exc
            logger.warning("Gemini media call attempt %s failed: %s", attempt, exc)
            time.sleep(min(2 ** attempt, 4))
    raise GeminiUnavailable(f"Gemini media analysis failed: {last_error}")
