"""Automatic virtual file categorization and topic tag extraction."""

from __future__ import annotations

from pathlib import Path
from typing import Optional
import re
import os


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

# --- Expanded topic keyword sets ---

STUDY_KEYWORDS = {
    "assignment", "book", "chapter", "class", "college", "course", "database", "exam",
    "homework", "lecture", "lesson", "notes", "paper", "project", "school", "study",
    "syllabus", "textbook", "tutorial", "university", "curriculum", "semester",
    "homework", "worksheet", "quiz", "grade", "professor", "faculty", "lecture",
}
MEDICAL_KEYWORDS = {
    "diabetes", "doctor", "health", "hospital", "medical", "medicine", "patient",
    "prescription", "report", "symptom", "treatment", "diagnosis", "clinic",
    "surgery", "therapy", "pharmacy", "vaccine", "disease", "nurse", "clinical",
}
FINANCE_KEYWORDS = {
    "bank", "bill", "budget", "expense", "finance", "invoice", "payment", "receipt",
    "salary", "statement", "tax", "accounting", "audit", "balance", "credit",
    "debit", "deposit", "investment", "loan", "mortgage", "revenue", "transaction",
}
PROGRAMMING_KEYWORDS = {
    "api", "array", "async", "callback", "class", "component", "config",
    "database", "debug", "deploy", "docker", "error", "function", "hook",
    "import", "interface", "library", "middleware", "module", "query",
    "request", "response", "route", "schema", "server", "socket", "template",
    "types", "variable", "widget", "algorithm", "buffer", "cache", "compile",
}
AI_ML_KEYWORDS = {
    "accuracy", "algorithm", "annotation", "attention", "bert", "classification",
    "clip", "clustering", "cnn", "dataset", "deep", "embedding", "encoder",
    "epoch", "feature", "gradient", "gpt", "inference", "label", "language",
    "latent", "layer", "learning", "llm", "loss", "model", "neural", "nlp",
    "normalization", "prediction", "pretrained", "regression", "reinforcement",
    "sample", "semantic", "sentiment", "supervised", "token", "training",
    "transformer", "unsupervised", "validation", "vector", "vision", "vocabulary",
}
DESIGN_KEYWORDS = {
    "animation", "artboard", "canvas", "color", "component", "design", "figma",
    "font", "frame", "icon", "illustration", "layer", "layout", "mask", "mockup",
    "pixel", "prototype", "render", "sketch", "style", "template", "theme",
    "typography", "ui", "ux", "vector", "wireframe", "brand", "logo",
}
BUSINESS_KEYWORDS = {
    "agenda", "agreement", "analysis", "approval", "board", "business", "client",
    "compliance", "contract", "corporate", "dashboard", "enterprise", "forecast",
    "framework", "goal", "growth", "initiative", "invoice", "kpi", "leadership",
    "marketing", "meeting", "metric", "objective", "plan", "portfolio", "presentation",
    "profit", "project", "proposal", "report", "revenue", "risk", "roadmap",
    "stakeholder", "startup", "strategy", "summary", "task", "team", "vendor",
}
SCIENCE_KEYWORDS = {
    "analysis", "biology", "calculation", "chemistry", "correlation", "data",
    "equation", "experiment", "formula", "genetics", "hypothesis", "laboratory",
    "measurement", "microscope", "molecule", "observation", "physics", "protocol",
    "quantum", "research", "sample", "simulation", "spectrum", "statistics",
    "synthesis", "theory",
}

TOPIC_SETS: list[tuple[str, set[str]]] = [
    ("programming", PROGRAMMING_KEYWORDS),
    ("ai-ml", AI_ML_KEYWORDS),
    ("design", DESIGN_KEYWORDS),
    ("business", BUSINESS_KEYWORDS),
    ("science", SCIENCE_KEYWORDS),
    ("medical", MEDICAL_KEYWORDS),
    ("finance", FINANCE_KEYWORDS),
    ("study", STUDY_KEYWORDS),
]

STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "can", "could", "may", "might", "shall", "should", "about",
    "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such", "no",
    "nor", "not", "only", "own", "same", "so", "than", "too", "very", "just",
    "also", "any", "because", "if", "this", "that", "these", "those",
    "it", "its", "it's", "which", "who", "whom", "what",
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "0",
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "get", "set", "use", "using", "used", "make", "made", "like", "well",
    "also", "within", "without", "across", "along", "around",
}


def _keyword_hit(haystack: str, keywords: set[str]) -> bool:
    for keyword in keywords:
        if not keyword:
            continue
        if keyword in haystack:
            if re.search(r"\w", keyword) and re.search(r"\b" + re.escape(keyword) + r"\b", haystack):
                return True
            elif not re.search(r"\w", keyword):
                return True
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


def extract_content_tags(path: str | Path, content_sample: Optional[str] = None, max_tags: int = 8) -> list[str]:
    """Extract meaningful topic tags from file name, path, and optional content sample.

    Uses a combination of:
    - Topic keyword matching against expanded domain-specific sets
    - Frequent word extraction (non-stopwords, meaningful tokens)
    - Filename-derived tags
    """
    file_path = Path(path)
    ext = file_path.suffix.lower()
    tags: list[str] = []
    seen: set[str] = set()

    def add_tag(tag: str) -> None:
        normalized = tag.strip().lower().replace("_", " ").replace("-", " ")
        normalized = re.sub(r"\s+", " ", normalized).strip()
        if normalized and normalized not in seen and len(normalized) <= 40:
            seen.add(normalized)
            tags.append(normalized[:40])

    # 1. Extract tags from filename (split on non-alphanumeric)
    name_stem = file_path.stem
    for part in re.split(r"[\s_\-\.]+", name_stem):
        part = part.strip().lower()
        if (
            part
            and len(part) > 2
            and part not in STOP_WORDS
            and not part.isdigit()
            and not re.match(r"^[0-9a-f]{8,}$", part)  # skip hex hashes
        ):
            add_tag(part)

    # 2. Topic keyword matching against content haystack
    haystack = f"{file_path.name} {file_path.parent} {content_sample or ''}".lower()
    for topic_name, keywords in TOPIC_SETS:
        if _keyword_hit(haystack, keywords):
            add_tag(topic_name)

    # 3. If we have content, extract frequent meaningful words
    if content_sample:
        words = re.findall(r"[a-zA-Z][a-zA-Z_\-]{2,}", content_sample.lower())
        word_counts: dict[str, int] = {}
        for w in words:
            if w not in STOP_WORDS and len(w) > 2 and not re.match(r"^[0-9a-f]{8,}$", w):
                word_counts[w] = word_counts.get(w, 0) + 1

        # Take top frequent words not already in tags
        sorted_words = sorted(word_counts.items(), key=lambda x: -x[1])
        for word, count in sorted_words:
            if len(tags) >= max_tags:
                break
            if count >= 2 and word not in seen:
                add_tag(word)

    # 4. Code-specific: extract imports / class/function names
    if ext in CODE_EXTENSIONS and content_sample:
        # Detect import names
        for match in re.finditer(r"(?:from|import)\s+([a-zA-Z_][a-zA-Z0-9_.]*)", content_sample):
            if len(tags) >= max_tags:
                break
            module = match.group(1).split(".")[0]
            if module and module.lower() not in STOP_WORDS and module not in seen and len(module) > 1:
                add_tag(module)
        # Detect class/function/def names
        for match in re.finditer(r"(?:class|def|fn|func|function)\s+([a-zA-Z_][a-zA-Z0-9_]*)", content_sample):
            if len(tags) >= max_tags:
                break
            name = match.group(1)
            if name.lower() not in STOP_WORDS and name not in seen and len(name) > 1:
                add_tag(name)

    # 5. Add extension-based descriptive tag
    ext_tag = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".jsx": "react", ".tsx": "react", ".html": "html",
        ".css": "css", ".json": "json", ".xml": "xml",
        ".md": "markdown", ".pdf": "pdf", ".txt": "text",
        ".png": "image", ".jpg": "image", ".jpeg": "image",
        ".mp4": "video", ".csv": "data",
    }.get(ext)
    if ext_tag and ext_tag not in seen:
        add_tag(ext_tag)

    return tags[:max_tags]
