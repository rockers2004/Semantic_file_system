"""Lightweight protected/encrypted file classification helpers."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Optional

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None


KNOWN_ENCRYPTED_EXTENSIONS = {
    ".age",
    ".asc",
    ".enc",
    ".encrypted",
    ".gpg",
    ".hc",
    ".kdbx",
    ".pgp",
    ".pfx",
    ".p12",
    ".tc",
}
PROTECTED_CONTAINER_EXTENSIONS = {
    ".dmg",
    ".sparsebundle",
    ".sparseimage",
}
ARCHIVE_EXTENSIONS = {".zip"}


def classify_protected_file(path: str | Path) -> Optional[dict[str, str]]:
    """Return protected-file classification details, if the path appears protected."""
    file_path = Path(path)
    ext = file_path.suffix.lower()

    if ext in KNOWN_ENCRYPTED_EXTENSIONS:
        return {
            "status": "encrypted_known_extension",
            "reason": f"Known encrypted/sensitive extension: {ext}",
        }

    if ext in PROTECTED_CONTAINER_EXTENSIONS:
        return {
            "status": "possibly_encrypted_container",
            "reason": f"Protected disk image/container extension: {ext}",
        }

    if ext == ".pdf" and PdfReader is not None:
        try:
            reader = PdfReader(str(file_path))
            if reader.is_encrypted:
                return {
                    "status": "password_required",
                    "reason": "Encrypted PDF requires a password",
                }
        except Exception:
            return None

    if ext in ARCHIVE_EXTENSIONS:
        try:
            with zipfile.ZipFile(file_path) as archive:
                if any(info.flag_bits & 0x1 for info in archive.infolist()):
                    return {
                        "status": "password_required",
                        "reason": "Encrypted zip archive requires a password",
                    }
        except Exception:
            return None

    return None
