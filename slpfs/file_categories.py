"""Automatic virtual file categorization helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Optional
import re


CATEGORY_ORDER = [
    "All",
    "Study",
    "Documents",
    "Code",
    "Images",
    "Videos",
    "Audio",
    "Data",
    "Archives",
    "Finance",
    "Medical",
    "Presentations",
    "Spreadsheets",
    "Protected",
    "Personal",
    "College",
    "Other",
]

CODE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".c", ".cc", ".cpp", ".h", ".hpp",
    ".cs", ".go", ".rs", ".php", ".rb", ".swift", ".kt", ".kts", ".scala", ".sh",
    ".ps1", ".sql", ".html", ".css", ".json", ".xml", ".yaml", ".yml",
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg", ".heic"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".ogg", ".mov", ".m4v", ".avi", ".mkv"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".aac", ".flac", ".m4a", ".ogg"}
ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"}
DATA_EXTENSIONS = {".csv", ".tsv", ".json", ".xml", ".db", ".sqlite", ".sqlite3", ".parquet"}
PRESENTATION_EXTENSIONS = {".ppt", ".pptx", ".key", ".odp"}
SPREADSHEET_EXTENSIONS = {".xls", ".xlsx", ".ods"}
DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt", ".md", ".rtf", ".odt", ".pages"}

STUDY_KEYWORDS = {
    "assignment", "book", "chapter", "class", "college", "course", "database", "exam",
    "homework", "lecture", "lesson", "notes", "paper", "project", "school", "study",
    "syllabus", "textbook", "tutorial", "university",
}
MEDICAL_KEYWORDS = {
    "diabetes", "doctor", "health", "hospital", "medical", "medicine", "patient",
    "prescription", "report", "symptom", "treatment",
}
FINANCE_KEYWORDS = {
    "bank", "bill", "budget", "expense", "finance", "invoice", "payment", "receipt",
    "salary", "statement", "tax",
}


def _keyword_hit(haystack: str, keywords: set[str]) -> bool:
    # Use word-boundary aware matching to reduce false positives (e.g., 'patient' vs 'inpatient')
    for keyword in keywords:
        if not keyword:
            continue
        # simple substring check first for performance, then precise word-boundary match
        if keyword in haystack:
            # if keyword contains non-word chars or spaces, accept substring match
            if re.search(r"\w", keyword) and re.search(r"\b" + re.escape(keyword) + r"\b", haystack):
                return True
            elif not re.search(r"\w", keyword):
                return True
        # fallback to explicit word-boundary match
        if re.search(r"\b" + re.escape(keyword) + r"\b", haystack):
            return True
    return False


def categorize_file(
    path: str | Path,
    *,
    is_protected: bool = False,
    content_sample: Optional[str] = None,
) -> dict[str, object]:
    """Return virtual category metadata for a file path and optional content sample."""
    file_path = Path(path)
    ext = file_path.suffix.lower()
    haystack = f"{file_path.name} {file_path.parent} {content_sample or ''}".lower()

    if is_protected:
        return {
            "category": "Protected",
            "category_confidence": 1.0,
            "category_reason": "Protected or encrypted file status",
        }
    if ext in CODE_EXTENSIONS:
        return {"category": "Code", "category_confidence": 0.95, "category_reason": f"Code extension: {ext}"}
    if ext in IMAGE_EXTENSIONS:
        return {"category": "Images", "category_confidence": 0.95, "category_reason": f"Image extension: {ext}"}
    if ext in VIDEO_EXTENSIONS:
        return {"category": "Videos", "category_confidence": 0.95, "category_reason": f"Video extension: {ext}"}
    if ext in AUDIO_EXTENSIONS:
        return {"category": "Audio", "category_confidence": 0.95, "category_reason": f"Audio extension: {ext}"}
    if ext in ARCHIVE_EXTENSIONS:
        return {"category": "Archives", "category_confidence": 0.9, "category_reason": f"Archive extension: {ext}"}
    if ext in PRESENTATION_EXTENSIONS:
        return {"category": "Presentations", "category_confidence": 0.9, "category_reason": f"Presentation extension: {ext}"}
    if ext in SPREADSHEET_EXTENSIONS:
        return {"category": "Spreadsheets", "category_confidence": 0.9, "category_reason": f"Spreadsheet extension: {ext}"}
    if _keyword_hit(haystack, MEDICAL_KEYWORDS):
        return {"category": "Medical", "category_confidence": 0.78, "category_reason": "Medical keyword match"}
    if _keyword_hit(haystack, FINANCE_KEYWORDS):
        return {"category": "Finance", "category_confidence": 0.78, "category_reason": "Finance keyword match"}
    if _keyword_hit(haystack, STUDY_KEYWORDS):
        return {"category": "Study", "category_confidence": 0.78, "category_reason": "Study keyword match"}
    if ext in DATA_EXTENSIONS:
        return {"category": "Data", "category_confidence": 0.85, "category_reason": f"Data extension: {ext}"}
    if ext in DOCUMENT_EXTENSIONS:
        return {"category": "Documents", "category_confidence": 0.8, "category_reason": f"Document extension: {ext}"}

    return {"category": "Other", "category_confidence": 0.4, "category_reason": "No category rule matched"}
