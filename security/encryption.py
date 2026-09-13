"""
Field-level encryption for sensitive PII — currently just CNIC (docs/
FIR_TECHNICAL_SPEC.md §4.4). Uses Fernet (symmetric, authenticated) from
the `cryptography` package: adequate for a hackathon-to-early-production
step, but a real deployment should move to a managed secrets store for the
key and consider full-column/tablespace encryption at the database layer —
noted here, not built, since that's out of scope for this prototype.

The key comes from FIELD_ENCRYPTION_KEY in .env — never hard-coded, never
committed. Generate one with:

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
from __future__ import annotations

import logging

from config import settings

logger = logging.getLogger("crime_report_ai.encryption")

_fernet = None
_init_error: str | None = None


def _get_fernet():
    global _fernet, _init_error
    if _fernet is not None or _init_error is not None:
        return _fernet
    if not settings.FIELD_ENCRYPTION_KEY:
        _init_error = "FIELD_ENCRYPTION_KEY is not configured."
        return None
    try:
        from cryptography.fernet import Fernet
        _fernet = Fernet(settings.FIELD_ENCRYPTION_KEY.encode())
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Failed to initialize field encryption")
        _init_error = f"Could not initialize encryption: {exc}"
    return _fernet


def is_available() -> bool:
    return _get_fernet() is not None


def encrypt_field(plaintext: str) -> bytes | None:
    """Returns encrypted bytes, or None if encryption isn't configured —
    callers must decide how to handle that (e.g. refuse to store the field
    in plaintext rather than silently falling back)."""
    if not plaintext:
        return None
    fernet = _get_fernet()
    if fernet is None:
        logger.warning("Field encryption unavailable: %s", _init_error)
        return None
    return fernet.encrypt(plaintext.encode("utf-8"))


def decrypt_field(ciphertext: bytes | None) -> str | None:
    if not ciphertext:
        return None
    fernet = _get_fernet()
    if fernet is None:
        logger.warning("Field decryption unavailable: %s", _init_error)
        return None
    try:
        return fernet.decrypt(bytes(ciphertext)).decode("utf-8")
    except Exception:
        logger.exception("Failed to decrypt field — wrong key, or corrupted data")
        return None
