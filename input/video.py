"""
Video input handling (section 10).

Tries direct Gemini video understanding first (fine for short/small clips);
falls back to extracting a handful of representative frames with OpenCV and
running vision analysis on those, which is far cheaper and keeps a hackathon
deployment responsive. The output is always clearly labeled as AI-assisted.
"""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from ai.vision import analyze_video_direct, analyze_video_frames
from ai.schemas import VideoAnalysis

logger = logging.getLogger("crime_report_ai.video")

DIRECT_ANALYSIS_SIZE_LIMIT = 15 * 1024 * 1024  # 15MB: above this, go straight to frames
MAX_FRAMES = 5


def extract_frames(video_bytes: bytes, max_frames: int = MAX_FRAMES) -> list[bytes]:
    """Extract up to max_frames evenly spaced JPEG frames using OpenCV."""
    import cv2

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp.write(video_bytes)
        tmp_path = tmp.name

    frames: list[bytes] = []
    try:
        cap = cv2.VideoCapture(tmp_path)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        if total <= 0:
            cap.release()
            return frames
        step = max(total // max_frames, 1)
        idx = 0
        while len(frames) < max_frames and idx < total:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
            if ok:
                ok2, buf = cv2.imencode(".jpg", frame)
                if ok2:
                    frames.append(buf.tobytes())
            idx += step
        cap.release()
    except Exception as exc:
        logger.warning("Frame extraction failed: %s", exc)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    return frames


def process_video(video_bytes: bytes, filename: str) -> VideoAnalysis:
    mime = "video/mp4" if filename.lower().endswith(".mp4") else "video/quicktime"

    if len(video_bytes) <= DIRECT_ANALYSIS_SIZE_LIMIT:
        result = analyze_video_direct(video_bytes, mime_type=mime)
        if result is not None:
            return result

    frames = extract_frames(video_bytes)
    if not frames:
        return VideoAnalysis(
            summary="AI-assisted video analysis was unavailable for this file.",
            notes="Could not extract frames or analyze the video directly.",
        )
    return analyze_video_frames(frames)
