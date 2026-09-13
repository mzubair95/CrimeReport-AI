"""
Thin, resilient wrapper around Groq's fast-inference API — another alternative
LLM backend to ai/gemini.py / ai/grok.py, selected via LLM_PROVIDER=groq in
.env (section 36: the LLM must be swappable without rewriting the rest of
the app).

Note: Groq (api.groq.com, hosts open models like Llama/Qwen/gpt-oss at high
speed) is a different company from Grok (xAI) despite the near-identical
name — this file is for the former.

Groq exposes an OpenAI-compatible Chat Completions endpoint, so this uses
the `openai` SDK pointed at https://api.groq.com/openai/v1 rather than a
bespoke client — same approach as ai/grok.py.
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

logger = logging.getLogger("crime_report_ai.groq")

_client = None
_client_error: Optional[str] = None

_IMAGE_MIME_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}


def _get_client():
    """Lazily create the OpenAI-compatible client so import never crashes without a key."""
    global _client, _client_error
    if _client is not None or _client_error is not None:
        return _client
    if not settings.groq_configured():
        _client_error = "GROQ_API_KEY is not configured."
        return None
    try:
        from openai import OpenAI
        _client = OpenAI(api_key=settings.GROQ_API_KEY, base_url=settings.GROQ_BASE_URL)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Failed to initialize Groq client")
        _client_error = f"Could not initialize Groq client: {exc}"
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
        raise LLMUnavailable(_client_error or "Groq not configured")

    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})

    last_error = None
    for attempt in range(retries + 1):
        try:
            resp = client.chat.completions.create(
                model=settings.GROQ_TEXT_MODEL,
                messages=messages,
                temperature=temperature,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as exc:
            last_error = exc
            logger.warning("Groq generate_text attempt %s failed: %s", attempt, exc)
            time.sleep(min(2 ** attempt, 4))
    raise LLMUnavailable(f"Groq text generation failed: {last_error}")


def generate_json(prompt: str, system_instruction: str | None = None,
                   temperature: float = 0.2, retries: int = 2) -> Optional[dict | list]:
    """Retry -> repair -> fallback JSON parsing (section 29), same contract as ai.gemini."""
    client = _get_client()
    if client is None:
        logger.warning("Groq not configured; cannot generate JSON")
        return None

    # Groq's JSON mode requires the word "json" to appear in the prompt.
    json_prompt = prompt if "json" in prompt.lower() else prompt + "\n\nRespond with JSON."

    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": json_prompt})

    last_raw = ""
    for attempt in range(retries + 1):
        try:
            resp = client.chat.completions.create(
                model=settings.GROQ_TEXT_MODEL,
                messages=messages,
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            last_raw = resp.choices[0].message.content or ""
            parsed = _try_parse_json(last_raw)
            if parsed is not None:
                return parsed
            logger.warning("Groq JSON parse failed on attempt %s: %r", attempt, last_raw[:300])
        except Exception as exc:
            logger.warning("Groq generate_json attempt %s failed: %s", attempt, exc)
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
                model=settings.GROQ_TEXT_MODEL,
                messages=repair_messages,
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            parsed = _try_parse_json(resp.choices[0].message.content or "")
            if parsed is not None:
                return parsed
        except Exception as exc:
            logger.warning("Groq JSON repair pass failed: %s", exc)

    return None


def generate_with_media(prompt: str, media_bytes: bytes, mime_type: str,
                         system_instruction: str | None = None,
                         as_json: bool = False, temperature: float = 0.2,
                         retries: int = 1) -> Any:
    """Image analysis only — raises LLMUnavailable for audio/video so callers
    fall back to their non-provider-specific paths (frame extraction, local
    Whisper transcription)."""
    if mime_type not in _IMAGE_MIME_TYPES:
        raise LLMUnavailable(
            f"Groq backend does not support direct analysis of {mime_type}; "
            "use frame extraction / local transcription instead."
        )

    client = _get_client()
    if client is None:
        raise LLMUnavailable(_client_error or "Groq not configured")

    prompt_for_media = prompt if not as_json or "json" in prompt.lower() else prompt + " Respond with JSON."
    b64 = base64.b64encode(media_bytes).decode("ascii")
    content = [
        {"type": "text", "text": prompt_for_media},
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
                model=settings.GROQ_VISION_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=700,  # stay under Groq's free-tier output-tokens-per-minute cap
                response_format={"type": "json_object"} if as_json else None,
                # The qwen vision models default to "thinking" mode, which can burn
                # the whole token budget on <think> reasoning before ever answering.
                # Vision analysis here doesn't need deep reasoning, so turn it off.
                extra_body={"reasoning_effort": "none"},
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
            logger.warning("Groq media call attempt %s failed: %s", attempt, exc)
            time.sleep(min(2 ** attempt, 4))
    raise LLMUnavailable(f"Groq media analysis failed: {last_error}")
