"""Media type definitions and modality routing helpers.

This module is the single source of truth for file-extension based media
classification across Semantixel.  It keeps scanner discovery, indexing
routing, and modality-specific services aligned so each layer does not
maintain its own copy of supported extensions.

Extension groups:
    IMAGE_EXTENSIONS:
        Still-image formats that can be passed directly to visual/OCR
        processing.
    VIDEO_EXTENSIONS:
        Video containers that can produce visual frames and may also contain
        audio streams.
    AUDIO_EXTENSIONS:
        Native audio formats for transcription and ambient-audio embedding.

Derived groups:
    VISUAL_EXTENSIONS:
        Media that should be routed to visual indexers.  This includes images
        and videos because videos are indexed through extracted frames.
    AUDIO_CAPABLE_EXTENSIONS:
        Media that should be routed to audio indexers.  This includes native
        audio and videos because videos may contain speech or ambient sound.
    MEDIA_EXTENSIONS:
        The complete set of extensions accepted by local media scanning.

Important:
    Videos are intentionally treated as multimodal.  A video can be indexed
    visually through frames and acoustically through transcription/CLAP, so
    helper names distinguish native type checks from modality routing checks.
"""

import os

IMAGE_EXTENSIONS = frozenset({".jpg",".jpeg",".png",".gif",".bmp",".webp",".tiff",".tif"})

VIDEO_EXTENSIONS = frozenset({".mp4",".mkv",".avi",".mov",".webm",".m4v",".ogg"})

AUDIO_EXTENSIONS = frozenset({".mp3",".wav",".flac",".m4a",".aac"})

VISUAL_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
AUDIO_CAPABLE_EXTENSIONS = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS
MEDIA_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS | AUDIO_EXTENSIONS


def get_extension(path: str) -> str:
    """Return a normalized file extension for *path*."""
    return os.path.splitext(path)[1].lower()


def is_image_file(path: str) -> bool:
    """Return whether *path* has a supported image extension."""
    return get_extension(path) in IMAGE_EXTENSIONS


def is_video_file(path: str) -> bool:
    """Return whether *path* has a supported video extension."""
    return get_extension(path) in VIDEO_EXTENSIONS


def is_audio_file(path: str) -> bool:
    """Return whether *path* has a supported native audio extension."""
    return get_extension(path) in AUDIO_EXTENSIONS


def is_media_file(path: str) -> bool:
    """Return whether *path* has any supported media extension."""
    return get_extension(path) in MEDIA_EXTENSIONS


def has_visual_modality(path: str) -> bool:
    """Return whether *path* should be processed by visual indexers."""
    return get_extension(path) in VISUAL_EXTENSIONS


def has_audio_modality(path: str) -> bool:
    """Return whether *path* should be processed by audio indexers."""
    return get_extension(path) in AUDIO_CAPABLE_EXTENSIONS
