"""Media identifier system — encoding, decoding, and descriptor types.

Semantixel assigns every indexed media item a unique **media ID**
composed of a source tag, a base64-encoded locator, and an optional
timestamp::

    local|<b64_path>          (image)
    local|<b64_path>|<sec>    (video frame)
    gdrive|<b64_file_id>      (Google Drive image)

The :class:`MediaDescriptor` dataclass normalises these IDs into a
uniform representation used throughout the indexing and search pipeline.
"""

import base64
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

LOCAL_SOURCE = "local"
GOOGLE_DRIVE_SOURCE = "gdrive"
FRAME_SEPARATOR = ":::"


def _b64_encode(value: str) -> str:
    """URL-safe base64 encode (without padding)."""
    return (
        base64.urlsafe_b64encode(value.encode("utf-8"))
        .decode("ascii")
        .rstrip("=")
    )


def _b64_decode(value: str) -> str:
    """URL-safe base64 decode (with padding restoration)."""
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii")).decode("utf-8")


def normalize_local_path(path: str) -> str:
    """Resolve a potentially-quoted local path to an absolute path.

    Strips surrounding single/double quotes and calls ``os.path.abspath``.

    Args:
        path: Raw path string.

    Returns:
        Canonical absolute path.
    """
    return os.path.abspath(path.strip('"').strip("'"))


def build_media_id(
    source: str, locator: str, timestamp: Optional[float] = None
) -> str:
    """Construct a media identifier string.

    Format: ``source|<b64-locator>[|<timestamp>]``

    Args:
        source: Source tag (``"local"``, ``"gdrive"``, etc.).
        locator: File path or Drive file ID.
        timestamp: Optional video-frame timestamp.

    Returns:
        A unique media identifier string.
    """
    encoded_locator = _b64_encode(locator)
    if timestamp is None:
        return "%s|%s" % (source, encoded_locator)
    return "%s|%s|%.6f" % (source, encoded_locator, timestamp)


@dataclass(frozen=True)
class MediaDescriptor:
    """Normalised descriptor for a single indexed media item.

    Attributes:
        source: Source tag (``"local"``, ``"gdrive"``).
        locator: File path or Drive file ID.
        media_type: ``"image"``, ``"video_frame"``, ``"audio"``.
        media_id: Unique ID string.
        display_path: Human-readable path for UI display.
        timestamp: Video-frame timestamp in seconds (optional).
    """

    source: str
    locator: str
    media_type: str
    media_id: str
    display_path: str
    timestamp: Optional[float] = None

    @property
    def is_video_frame(self) -> bool:
        """Whether this descriptor represents a video frame."""
        return self.timestamp is not None

    @property
    def composite_id(self) -> str:
        """Full identifier including frame/transcript postfix.

        For images this is the same as :attr:`media_id`; for video
        frames it appends ``:::timestamp``.
        """
        if self.timestamp is None:
            return self.media_id
        return "%s%s%.6f" % (self.media_id, FRAME_SEPARATOR, self.timestamp)

    def to_result(self) -> Dict[str, Any]:
        """Convert to a JSON-serialisable result dict.

        Used by the search API to return uniform result objects.
        """
        payload: Dict[str, Any] = {
            "media_id": self.media_id,
            "source": self.source,
            "path": self.display_path,
            "display_path": self.display_path,
            "type": "video" if self.is_video_frame else self.media_type,
            "locator": self.locator,
        }
        if self.timestamp is not None:
            payload["timestamp"] = self.timestamp
            payload["composite_id"] = self.composite_id
        else:
            payload["composite_id"] = self.media_id
        return payload


def describe_local_media(
    path: str, timestamp: Optional[float] = None
) -> MediaDescriptor:
    """Create a :class:`MediaDescriptor` for a local file.

    Args:
        path: Local file path.
        timestamp: Optional video-frame timestamp.

    Returns:
        A descriptor with ``source="local"``.
    """
    normalized_path = normalize_local_path(path)
    media_type = "video_frame" if timestamp is not None else "image"
    return MediaDescriptor(
        source=LOCAL_SOURCE,
        locator=normalized_path,
        media_type=media_type,
        media_id=build_media_id(LOCAL_SOURCE, normalized_path),
        display_path=normalized_path,
        timestamp=timestamp,
    )


def parse_media_id(raw_id: str) -> MediaDescriptor:
    """Parse a media identifier string back into a descriptor.

    Args:
        raw_id: A media ID or composite ID string.

    Returns:
        The corresponding :class:`MediaDescriptor`.

    Raises:
        ValueError: If the ID format is unrecognised.
    """
    if "|" not in raw_id:
        if FRAME_SEPARATOR in raw_id:
            locator, timestamp_fragment = raw_id.rsplit(FRAME_SEPARATOR, 1)
            return describe_local_media(locator, timestamp=float(timestamp_fragment))
        return describe_local_media(raw_id)

    base_id, _, timestamp_fragment = raw_id.partition(FRAME_SEPARATOR)
    parts = base_id.split("|")
    if len(parts) != 2:
        raise ValueError("Unsupported media identifier: %s" % raw_id)

    source, encoded_locator = parts
    locator = _b64_decode(encoded_locator)
    timestamp = float(timestamp_fragment) if timestamp_fragment else None

    if source == LOCAL_SOURCE:
        return describe_local_media(locator, timestamp=timestamp)
    if source == GOOGLE_DRIVE_SOURCE:
        return MediaDescriptor(
            source=GOOGLE_DRIVE_SOURCE,
            locator=locator,
            media_type="image",
            media_id=build_media_id(GOOGLE_DRIVE_SOURCE, locator),
            display_path="Google Drive/%s" % locator,
            timestamp=timestamp,
        )

    raise ValueError("Unsupported media source: %s" % source)


def is_media_id(value: str) -> bool:
    """Quick check whether a string looks like a media identifier.

    A valid media ID contains at least one ``|`` and the prefix before
    the first ``|`` is a recognised source tag.
    """
    parts = value.split("|")
    return len(parts) >= 2 and parts[0] in {LOCAL_SOURCE, GOOGLE_DRIVE_SOURCE}
