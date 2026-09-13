"""
Image input handling (section 9) — thin wrapper over ai.vision.
"""
from __future__ import annotations

from ai.vision import analyze_image
from ai.schemas import ImageAnalysis

SUPPORTED_IMAGE_TYPES = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                          "webp": "image/webp"}


def process_image(file_bytes: bytes, filename: str, incident_context: str = "") -> ImageAnalysis:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    mime = SUPPORTED_IMAGE_TYPES.get(ext, "image/jpeg")
    return analyze_image(file_bytes, mime_type=mime, incident_context=incident_context)
