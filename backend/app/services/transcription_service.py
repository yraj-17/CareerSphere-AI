"""
Optional speech-to-text for voice interviews (local Faster-Whisper).

CareerSphere has no pre-existing speech infrastructure, so this adapter is
opt-in: it is only "available" when INTERVIEW_WHISPER_MODEL is set AND the
`faster-whisper` package is installed. Otherwise voice interviews are reported
as unavailable and the UI falls back to typed answers — nothing pretends to
transcribe.

Audio handling
--------------
* The client-supplied MIME type is ignored; the container is sniffed from magic bytes.
* Size is capped by INTERVIEW_MAX_AUDIO_BYTES and decoded duration by INTERVIEW_MAX_AUDIO_SECONDS.
* Audio is decoded from an in-memory buffer — raw audio is never written to disk,
  stored, or logged. Transcripts are not logged.
* One transcription runs at a time per process, bounded by
  INTERVIEW_TRANSCRIPTION_TIMEOUT_SECONDS.
"""

from __future__ import annotations

import asyncio
import importlib.util
import io
import logging
import threading
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

_model = None
_model_lock = threading.Lock()
_semaphore = asyncio.Semaphore(1)


class TranscriptionUnavailable(Exception):
    """Transcription is not configured on this server."""


class TranscriptionError(Exception):
    """The audio could not be transcribed. The message is safe to show to users."""


def is_available() -> bool:
    if not settings.INTERVIEW_WHISPER_MODEL.strip():
        return False
    return importlib.util.find_spec("faster_whisper") is not None


def detect_audio_format(data: bytes) -> Optional[str]:
    """Identify supported audio containers from magic bytes."""
    if len(data) < 12:
        return None
    if data[:4] == b"\x1a\x45\xdf\xa3":
        return "webm"
    if data[:4] == b"OggS":
        return "ogg"
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "wav"
    if data[4:8] == b"ftyp":
        return "mp4"
    if data[:3] == b"ID3" or (data[0] == 0xFF and (data[1] & 0xE0) == 0xE0):
        return "mp3"
    return None


def _get_model():
    global _model
    with _model_lock:
        if _model is None:
            from faster_whisper import WhisperModel  # optional dependency

            _model = WhisperModel(
                settings.INTERVIEW_WHISPER_MODEL,
                device=settings.INTERVIEW_WHISPER_DEVICE,
                compute_type=settings.INTERVIEW_WHISPER_COMPUTE_TYPE,
            )
        return _model


def _transcribe_bytes(data: bytes) -> tuple[str, float]:
    model = _get_model()
    segments, info = model.transcribe(io.BytesIO(data), beam_size=1, vad_filter=True)
    duration = float(getattr(info, "duration", 0.0) or 0.0)
    if duration > settings.INTERVIEW_MAX_AUDIO_SECONDS + 1:
        raise TranscriptionError(
            f"Recording is longer than the {settings.INTERVIEW_MAX_AUDIO_SECONDS} second limit."
        )
    text = " ".join(segment.text.strip() for segment in segments if segment.text and segment.text.strip())
    return " ".join(text.split()), duration


async def transcribe(data: bytes) -> tuple[str, float]:
    if not is_available():
        raise TranscriptionUnavailable()
    if not data:
        raise TranscriptionError("The recording is empty.")
    if len(data) > settings.INTERVIEW_MAX_AUDIO_BYTES:
        raise TranscriptionError("The recording is too large.")
    if detect_audio_format(data) is None:
        raise TranscriptionError("Unsupported audio format. Please record again.")

    try:
        async with _semaphore:
            text, duration = await asyncio.wait_for(
                asyncio.to_thread(_transcribe_bytes, data),
                timeout=settings.INTERVIEW_TRANSCRIPTION_TIMEOUT_SECONDS,
            )
    except TranscriptionError:
        raise
    except asyncio.TimeoutError as exc:
        raise TranscriptionError("Transcription took too long. Please try a shorter recording.") from exc
    except Exception as exc:  # decoder/model failures; never log audio or transcript content
        logger.warning("[Transcription] failed: %s", type(exc).__name__)
        raise TranscriptionError("The recording could not be transcribed. Please try again or type your answer.") from exc

    if not text:
        raise TranscriptionError("No speech was detected in the recording.")
    return text, duration
