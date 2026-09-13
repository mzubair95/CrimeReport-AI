"""
Image and video understanding via multimodal LLM input, plus the PRD's
"Evidence Relevance" and "Privacy Detection" AI modules.

Strict rule enforced in the prompts: only describe what is visibly present.
Never claim identity, exact location/time, or criminal intent. Privacy flags
(face/ID/phone-number detected) are for the *reviewer's* awareness so
unrelated sensitive content can be redacted before wider handling — they are
not an identification of any person.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np

from ai import llm as gemini  # routed through ai/llm.py — backend set by LLM_PROVIDER
from ai.schemas import ImageAnalysis, VideoAnalysis, safe_validate

logger = logging.getLogger("crime_report_ai.vision")

_IMAGE_RULES = """You are analyzing a photo submitted as evidence for a crime report.
Describe ONLY what is visibly present in the image. Do NOT:
- identify or name any person
- guess an exact location or time
- assert criminal intent or who is at fault
If something is unclear or not visible, leave it out or mark it false/null.
Also check (for a human reviewer's awareness, not an accusation):
- id_document_visible: is a legible ID card, passport, license plate close-up, or similar official document visible?
- phone_number_visible: is a legible phone number visible anywhere in the image (screen, paper, sign)?
Return ONLY JSON matching exactly:
{"visible_items": [list of short strings], "visible_damage": string or null,
 "people_visible": boolean, "text_visible": boolean, "notes": short string,
 "id_document_visible": boolean, "phone_number_visible": boolean}
"""

_VIDEO_RULES = """You are analyzing frame(s)/a clip submitted as video evidence for a
crime report. Describe ONLY what is visibly present. Do NOT identify people by
name, guess exact location/time, or assert criminal intent.
Return ONLY JSON matching exactly:
{"summary": short factual summary, "visible_items": [list of short strings],
 "people_visible": boolean, "notes": short string}
"""


def analyze_image(image_bytes: bytes, mime_type: str = "image/jpeg",
                   incident_context: str = "") -> ImageAnalysis:
    """incident_context (optional): the incident description/category, used
    only to ask whether the image plausibly relates to it (PRD "Evidence
    Relevance") — never to infer facts not visible in the image itself."""
    prompt = "Analyze this evidence photo."
    if incident_context:
        prompt += (f" The reported incident is: \"{incident_context}\". Also set "
                   "relevant_to_incident: true/false/null for whether this image "
                   "plausibly depicts something consistent with that incident "
                   "(null if you can't tell).")
    try:
        data = gemini.generate_with_media(
            prompt=prompt,
            media_bytes=image_bytes,
            mime_type=mime_type,
            system_instruction=_IMAGE_RULES,
            as_json=True,
        )
    except gemini.LLMUnavailable as exc:
        logger.warning("Image analysis unavailable: %s", exc)
        return ImageAnalysis(notes="AI image analysis unavailable right now.")
    result = safe_validate(ImageAnalysis, data) or ImageAnalysis(notes="AI could not reliably analyze this image.")

    # Deterministic, non-LLM face check (PRD "Privacy Detection") — runs
    # regardless of whether the LLM call above succeeded, since it's cheap
    # and doesn't depend on any API key.
    try:
        if detect_faces(image_bytes) > 0:
            result.people_visible = True
    except Exception:
        logger.exception("OpenCV face detection failed")

    return result


def detect_faces(image_bytes: bytes) -> int:
    """Local, free, offline face detection (Haar cascade, bundled with
    OpenCV — no model download or API call). Used as a deterministic backstop
    for the LLM's own people_visible judgment, not to identify anyone."""
    import cv2

    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return 0
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    cascade = cv2.CascadeClassifier(cascade_path)
    faces = cascade.detectMultiScale(img, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    return len(faces)


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
    except gemini.LLMUnavailable as exc:
        logger.info("Direct video analysis failed, will fall back to frames: %s", exc)
        return None
    return safe_validate(VideoAnalysis, data)


def analyze_video_frames(frame_jpeg_bytes_list: list[bytes]) -> VideoAnalysis:
    """
    Fallback: analyze a handful of extracted representative frames instead
    of the raw video, and merge the per-frame findings.
    """
    all_items: set[str] = set()
    people_visible = False

    for frame in frame_jpeg_bytes_list:
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
