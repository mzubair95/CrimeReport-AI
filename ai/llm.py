"""
LLM router (section 36) — every other module calls the functions in *this*
file, never ai.gemini or ai.grok directly, so the backend is swapped in one
place by setting LLM_PROVIDER=gemini|grok in .env.
"""
from __future__ import annotations

from config import settings
from ai.errors import LLMUnavailable

if settings.LLM_PROVIDER == "grok":
    from ai import grok as _backend
else:
    from ai import gemini as _backend

is_available = _backend.is_available
generate_text = _backend.generate_text
generate_json = _backend.generate_json
generate_with_media = _backend.generate_with_media

__all__ = ["is_available", "generate_text", "generate_json", "generate_with_media",
           "LLMUnavailable", "provider_name"]


def provider_name() -> str:
    return settings.LLM_PROVIDER
