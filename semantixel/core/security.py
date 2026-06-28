"""Path-traversal and URL-safety validation utilities."""

import os
from typing import List
from urllib.parse import urlparse


def is_safe_path(path: str, allowed_dirs: List[str]) -> bool:
    """Check whether *path* is contained within one of *allowed_dirs*.

    Performs a prefix check on resolved absolute paths to prevent
    directory traversal attacks (e.g. ``../../etc/passwd``).

    Args:
        path: The file path to validate.
        allowed_dirs: List of permitted root directories.

    Returns:
        ``True`` if the path is safe.
    """
    abs_path = os.path.abspath(path)
    for allowed_dir in allowed_dirs:
        abs_allowed_dir = os.path.abspath(allowed_dir)
        if os.path.commonpath([abs_path, abs_allowed_dir]) == abs_allowed_dir:
            return True
    return False


def is_safe_url(url: str) -> bool:
    """Reject URLs with disallowed schemes or internal addresses.

    Only ``http`` / ``https`` schemes are allowed.  Loopback hosts
    (``localhost``, ``127.0.0.1``, ``0.0.0.0``) are explicitly blocked
    to prevent SSRF.

    Args:
        url: The URL to validate.

    Returns:
        ``True`` if the URL is safe to fetch.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    if not parsed.netloc or parsed.netloc in ("localhost", "127.0.0.1", "0.0.0.0"):
        return False
    return True
