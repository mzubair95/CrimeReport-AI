"""Shared exception types so callers can catch one error regardless of which
LLM backend (Gemini, Grok, ...) is actually configured (section 36)."""


class LLMUnavailable(RuntimeError):
    """Raised when the configured LLM backend cannot be reached or is not configured."""
