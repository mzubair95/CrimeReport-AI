"""
Image and video understanding via Gemini multimodal input (sections 9-10).

Strict rule enforced in the prompts: only describe what is visibly present.
Never claim identity, exact location/time, or criminal intent.
"""
from __future__ import annotations

import io
import logging
from typing import Optional

from ai import gemini
from ai.schemas import ImageAnalysis, VideoAnalysis, safe_validate

logger = logging.getLogger("crime_report_ai.vision")

_IMAGE_RULES = """You are analyzing a photo submitted as evidence for a crime report.
Describe ONLY what is visibly present in the image. Do NOT:
- identify or name any person
- guess an exact location or time
- assert criminal intent or who is at fault
If something is unclear or not visible, leave it out or mark it false/null.
Return ONLY JSON matching exactly:
{"visible_items": [list of short strings], "visible_damage": string or null,
 "people_visible": boolean, "text_visible": boolean, "notes": short string}
"""

_VIDEO_RULES = """You are analyzing frame(s)/a clip submitted as video evidence for a
crime report. Describe ONLY what is visibly present. Do NOT identify people by
name, guess exact location/time, or assert criminal intent.
Return ONLY JSON matching exactly:
{"summary": short factual summary, "visible_items": [list of short strings],
 "people_visible": boolean, "notes": short string}
"""


def analyze_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> ImageAnalysis:
    try:
        data = gemini.generate_with_media(
            prompt="Analyze this evidence photo.",
            media_bytes=image_bytes,
            mime_type=mime_type,
            system_instruction=_IMAGE_RULES,
            as_json=True,
        )
    except gemini.GeminiUnavailable as exc:
        logger.warning("Image analysis unavailable: %s", exc)
        return ImageAnalysis(notes="AI image analysis unavailable right now.")
    result = safe_validate(ImageAnalysis, data)
    return result or ImageAnalysis(notes="AI could not reliably analyze this image.")


def analyze_video_direct(video_bytes: bytes, mime_type: str = "video/mp4") -> Optional[VideoAnalysis]:
    """Try sending the whole clip to Gemini (works for short/small clips)."""
    try:
        data = gemini.generate_with_media(
            prompt="Analyze this evidence video clip.",
            media_bytes=video_bytes,
            mime_type=mime_type,
            system_instruction=_VIDEO_RULES,
            as_json=True,
            retries=0,
        )
    except gemini.GeminiUnavailable as exc:
        logger.info("Direct video analysis failed, will fall back to frames: %s", exc)
        return None
    return safe_validate(VideoAnalysis, data)


def analyze_video_frames(frame_jpeg_bytes_list: list[bytes]) -> VideoAnalysis:
    """
    Fallback (section 10): analyze a handful of extracted representative
    frames instead of the raw video, and merge the per-frame findings.
    """
    all_items: set[str] = set()
    people_visible = False
    notes_parts = []

    for i, frame in enumerate(frame_jpeg_bytes_list):
        analysis = analyze_image(frame, mime_type="image/jpeg")
        all_items.update(analysis.visible_items)
        people_visible = people_visible or analysis.people_visible
        if analysis.visible_damage:
            all_items.add(analysis.visible_damage)

    summary = (
        f"AI-assisted analysis of {len(frame_jpeg_bytes_list)} representative "
        "video frame(s). " + ("People were visible in at least one frame. "
        if people_visible else "No people were clearly visible in the sampled frames. ")
    )
    return VideoAnalysis(
        summary=summary,
        visible_items=sorted(all_items),
        people_visible=people_visible,
        notes="Video was summarized via extracted frames, not full playback.",
    )
