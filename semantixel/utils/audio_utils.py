"""Audio-stream detection via ffprobe."""

import subprocess
from semantixel.core.logging import logger


def has_audio_stream(file_path: str) -> bool:
    """Check whether *file_path* contains an audio track.

    Delegates to ``ffprobe``.  Returns ``False`` when no audio stream is
    found so callers can skip processing.  On probe failure the method
    is permissive (returns ``True``) to avoid silently dropping files
    when the probe tool is missing.

    Args:
        file_path: Absolute path to the media file.

    Returns:
        ``True`` if an audio stream is present (or probe failed).
    """
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "csv=p=0",
                file_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return "audio" in result.stdout
    except Exception as exc:
        logger.debug("ffprobe check failed for %s: %s", file_path, exc)
        return True
