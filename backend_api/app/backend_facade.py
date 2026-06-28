"""App-level backend facade for SLPFS and Semantixel engines.

This module exposes a single service used by API handlers so routing and
normalization decisions stay out of FastAPI endpoint code.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from backend_api.app.runtime_manager import get_backend_health_snapshot, initialize_backends, shutdown_backends
from backend_api.app.semantixel_runtime import get_semantixel_config, get_semantixel_runtime
from backend_api.app.slpfs_runtime import get_root_path, get_runtime, set_root_path
from slpfs.file_security import classify_protected_file
from slpfs.file_categories import categorize_file, extract_content_tags


class BackendFacade:
    """Single routing brain for backend operations."""

    def initialize(self) -> None:
        initialize_backends()

    def shutdown(self) -> None:
        shutdown_backends()

    def health_snapshot(self) -> dict[str, Any]:
        return get_backend_health_snapshot()

    def config_snapshot(self) -> dict[str, Any]:
        return {
            "root_path": self.get_root_path(),
            "max_depth": 10,
            "multimodal": get_semantixel_config(),
        }

    def get_root_path(self) -> str:
        return get_root_path()

    def update_root_path(self, new_root: str) -> str:
        return set_root_path(new_root)

    def list_tree(self, path: Optional[str], depth: int, semantic: bool = False) -> dict[str, Any]:
        target = self._resolve_safe_path(path)

        if not target.exists():
            raise FileNotFoundError("Path does not exist")
        if not target.is_dir():
            raise NotADirectoryError("Path is not a directory")

        entries = []
        for entry in target.iterdir():
            try:
                stat = entry.stat()
                protected = None if entry.is_dir() else classify_protected_file(entry)

                # Decide whether to compute semantic category using a small content sample
                cat = {"category": None, "category_confidence": 0.0, "category_reason": None}
                tags: list[str] = []
                if semantic and not entry.is_dir() and not protected:
                    try:
                        # Read a small content sample safely
                        sample = None
                        try:
                            with open(entry, 'r', encoding='utf-8', errors='ignore') as fh:
                                sample = fh.read(4096)
                        except OSError:
                            sample = None
                        cat = categorize_file(entry, is_protected=False, content_sample=sample)
                        tags = extract_content_tags(entry, content_sample=sample)
                    except Exception:
                        cat = {"category": None, "category_confidence": 0.0, "category_reason": None}

                entries.append(
                    {
                        "name": entry.name,
                        "path": str(entry.resolve()),
                        "is_dir": entry.is_dir(),
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "is_protected": protected is not None,
                        "security_status": protected.get("status") if protected else None,
                        "security_reason": protected.get("reason") if protected else None,
                        "category": cat.get("category"),
                        "category_confidence": float(cat.get("category_confidence", 0.0) or 0.0),
                        "category_reason": cat.get("category_reason"),
                        "tags": tags,
                    }
                )
            except OSError:
                continue

        entries.sort(key=lambda item: (not item["is_dir"], item["name"].lower()))

        return {
            "root": self.get_root_path(),
            "path": str(target),
            "depth": max(1, depth),
            "entries": entries,
        }

    def read_text_file(self, path: str, max_preview_bytes: int) -> dict[str, Any]:
        if not path or not path.strip():
            raise ValueError("Path is required")

        target = self._resolve_safe_path(path)

        if not target.exists():
            raise FileNotFoundError("File not found")
        if not target.is_file():
            raise IsADirectoryError("Path is a directory, not a file")

        protected = classify_protected_file(target)
        if protected:
            raise ValueError(protected["reason"])

        stat = target.stat()

        if target.suffix.lower() == ".pdf":
            raise ValueError("PDF text preview is disabled in API. Open the file with a system app.")

        if stat.st_size > max_preview_bytes:
            raise OverflowError(f"File is too large for preview (>{max_preview_bytes} bytes)")

        raw = target.read_bytes()

        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError("Binary file preview is not supported")

        if not content.strip():
            raise ValueError("Binary file preview is not supported")

        return {
            "path": str(target),
            "content": content,
            "encoding": "utf-8",
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        }

    def run_command(self, text: str) -> dict[str, Any]:
        runtime = get_runtime()
        return runtime.process_natural_language(text)

    def run_multimodal_indexing(self) -> dict[str, Any]:
        """Run a full Semantixel index scan in-process when multimodal is enabled."""
        runtime = get_semantixel_runtime()
        return runtime.run_full_scan()

    def run_text_indexing(self) -> dict[str, Any]:
        """Run a full SLPFS text index rebuild."""
        runtime = get_runtime()
        result = runtime.reindex_all()
        if not bool(result.get("success", False)):
            raise RuntimeError(str(result.get("error") or "Text indexing failed"))

        stats = result.get("stats", {}) if isinstance(result, dict) else {}
        return {
            "status": "ok",
            "message": result.get("message", "Text indexing completed"),
            "source": "slpfs",
            "indexed": stats.get("indexed"),
            "unchanged": stats.get("unchanged"),
            "metadata_indexed": stats.get("metadata_indexed"),
            "failed": stats.get("failed", stats.get("errors")),
            "skipped": stats.get("skipped"),
            "skipped_files": stats.get("skipped_files", []),
            "errors": stats.get("errors"),
        }

    def trigger_indexing(self, target: str) -> dict[str, Any]:
        """Trigger indexing by target: text, multimodal, or all."""
        normalized = (target or "").strip().lower()
        if normalized == "text":
            return {
                "target": "text",
                "results": [self.run_text_indexing()],
            }
        if normalized == "multimodal":
            return {
                "target": "multimodal",
                "results": [self.run_multimodal_indexing()],
            }
        if normalized == "all":
            results: list[dict[str, Any]] = []
            results.append(self.run_text_indexing())
            results.append(self.run_multimodal_indexing())
            return {
                "target": "all",
                "results": results,
            }
        raise ValueError("Unsupported indexing target: expected one of text, multimodal, all")

    def search_text(
        self,
        query: str,
        k: int,
        mode: str = "general",
        *,
        top_k: Optional[int] = None,
        threshold: Optional[float] = None,
        media_type: str = "all",
    ) -> dict[str, Any]:
        resolved_mode = (mode or "general").strip().lower()
        if resolved_mode in {"general", "normal", "text", "semantic", "slpfs"}:
            return self._search_slpfs(query, k)
        if resolved_mode in {"multimodal", "semantixel", "image", "video", "audio"}:
            mm_type = media_type
            if resolved_mode in {"image", "video", "audio"}:
                mm_type = resolved_mode
            return self._search_multimodal(query, top_k or k, threshold, mm_type)
        if resolved_mode in {"keyword", "ocr", "transcript"}:
            return self._search_multimodal_keywords(query, top_k or k, threshold, media_type)
        if resolved_mode in {"combined", "hybrid", "all"}:
            return self._search_combined(query, k, top_k=top_k, threshold=threshold, media_type=media_type)
        if resolved_mode == "auto":
            sem_enabled = bool(get_semantixel_config().get("enabled", False))
            if sem_enabled:
                return self._search_combined(
                    query,
                    k,
                    top_k=top_k,
                    threshold=threshold,
                    media_type=media_type,
                )
            return self._search_slpfs(query, k)

        raise ValueError(f"Unsupported search mode: {mode}")

    def _search_slpfs(self, query: str, k: int) -> dict[str, Any]:
        use_fallback = str(os.getenv("SLPFS_SEARCH_FALLBACK", "0")).lower() in {"1", "true", "yes"}

        try:
            runtime = get_runtime()
            core_result = runtime.search_files(query=query, k=k, keywords=None)
        except RuntimeError:
            if not use_fallback:
                raise
            fallback_items = self._fallback_search_runtime_backup(query=query, k=k)
            return {
                "query": query,
                "total": len(fallback_items),
                "results": fallback_items,
                "source": "fallback",
                "search_status": "ok",
            }

        if not core_result.get("success", False):
            return {
                "query": query,
                "total": 0,
                "results": [],
                "source": "runtime",
                "search_status": "failed",
                "error": core_result.get("error", "Search failed"),
            }

        current_root = Path(self.get_root_path()).resolve()
        filtered_results: list[dict[str, Any]] = []

        for item in core_result.get("results", []):
            raw_path = str(item.get("file_path", "") or "")
            if not raw_path:
                continue

            try:
                resolved_path = Path(raw_path).resolve()
                resolved_path.relative_to(current_root)
            except ValueError:
                # Ignore stale vector hits outside active root.
                continue
            except OSError:
                continue

            filtered_results.append(
                {
                    "path": str(resolved_path),
                    "score": float(item.get("score", 0.0) or 0.0),
                    "snippet": item.get("preview", "") or "",
                    "is_dir": False,
                    "source": "slpfs",
                    "kind": "text",
                    "category": item.get("category"),
                    "category_confidence": float(item.get("category_confidence", 0.0) or 0.0),
                    "category_reason": item.get("category_reason"),
                }
            )

            if len(filtered_results) >= max(1, k):
                break

        return {
            "query": query,
            "total": len(filtered_results),
            "results": filtered_results,
            "source": "runtime",
            "search_status": "ok",
        }

    def _search_multimodal(
        self,
        query: str,
        top_k: int,
        threshold: Optional[float],
        media_type: str,
    ) -> dict[str, Any]:
        runtime = get_semantixel_runtime()
        items = runtime.semantic_text_search(
            query=query,
            top_k=top_k,
            threshold=threshold,
            media_type=media_type,
        )

        normalized = [
            {
                "path": item.get("path", ""),
                "score": float(item.get("score", 0.0) or 0.0),
                "snippet": item.get("type", "multimodal"),
                "is_dir": False,
                "source": "semantixel",
                "kind": "multimodal",
                "media_type": item.get("type", media_type),
                "timestamp": item.get("timestamp"),
                "composite_id": item.get("composite_id"),
            }
            for item in items
            if isinstance(item, dict)
        ]

        return {
            "query": query,
            "total": len(normalized),
            "results": normalized,
            "source": "semantixel",
            "search_status": "ok",
        }

    def _search_multimodal_keywords(
        self,
        query: str,
        top_k: int,
        threshold: Optional[float],
        media_type: str,
    ) -> dict[str, Any]:
        runtime = get_semantixel_runtime()
        items = runtime.keyword_search(
            query=query,
            top_k=top_k,
            threshold=threshold,
            media_type=media_type,
        )
        normalized = [self._normalize_multimodal_result(item, media_type) for item in items if isinstance(item, dict)]
        return {
            "query": query,
            "total": len(normalized),
            "results": normalized,
            "source": "semantixel",
            "search_status": "ok",
        }

    def search_by_image(
        self,
        image_path: str,
        top_k: int,
        threshold: Optional[float],
        media_type: str,
    ) -> dict[str, Any]:
        runtime = get_semantixel_runtime()
        items = runtime.semantic_image_search(
            image_path=image_path,
            top_k=top_k,
            threshold=threshold,
            media_type=media_type,
        )
        normalized = [self._normalize_multimodal_result(item, media_type) for item in items if isinstance(item, dict)]
        return {
            "query": image_path,
            "total": len(normalized),
            "results": normalized,
            "source": "semantixel",
            "search_status": "ok",
        }

    def multimodal_graph(self) -> dict[str, Any]:
        runtime = get_semantixel_runtime()
        return {
            "source": "semantixel",
            "graph": runtime.graph_data(),
        }

    @staticmethod
    def _normalize_multimodal_result(item: dict[str, Any], fallback_media_type: str) -> dict[str, Any]:
        return {
            "path": item.get("path", ""),
            "score": float(item.get("score", 0.0) or 0.0),
            "snippet": item.get("type", "multimodal"),
            "is_dir": False,
            "source": "semantixel",
            "kind": "multimodal",
            "media_type": item.get("type", fallback_media_type),
            "timestamp": item.get("timestamp"),
            "composite_id": item.get("composite_id"),
            "media_id": item.get("media_id"),
        }

    def _search_combined(
        self,
        query: str,
        k: int,
        *,
        top_k: Optional[int],
        threshold: Optional[float],
        media_type: str,
    ) -> dict[str, Any]:
        combined: list[dict[str, Any]] = []
        errors: list[str] = []

        try:
            slpfs_response = self._search_slpfs(query, k)
            combined.extend(slpfs_response.get("results", []))
        except RuntimeError as exc:
            errors.append(f"slpfs: {exc}")

        try:
            mm_response = self._search_multimodal(query, top_k or k, threshold, media_type)
            combined.extend(mm_response.get("results", []))
        except RuntimeError as exc:
            errors.append(f"semantixel: {exc}")

        if not combined and errors:
            raise RuntimeError("; ".join(errors))

        combined.sort(key=lambda item: float(item.get("score", 0.0) or 0.0), reverse=True)
        limited = combined[: max(1, k)]

        payload: dict[str, Any] = {
            "query": query,
            "total": len(limited),
            "results": limited,
            "source": "combined",
            "search_status": "ok" if not errors else "partial",
        }
        if errors:
            payload["warnings"] = errors
        return payload

    def _resolve_safe_path(self, raw_path: Optional[str]) -> Path:
        current_root = Path(self.get_root_path()).resolve()

        if not raw_path:
            candidate = current_root
        else:
            requested_path = Path(raw_path)
            candidate = requested_path if requested_path.is_absolute() else current_root / requested_path
            candidate = candidate.resolve()

        try:
            candidate.relative_to(current_root)
        except ValueError as exc:
            raise ValueError("Path is outside of the configured root") from exc

        return candidate

    def _fallback_search_runtime_backup(self, query: str, k: int) -> list[dict[str, Any]]:
        root_dir = Path(self.get_root_path()).resolve()
        query_lower = query.lower()
        out: list[dict[str, Any]] = []

        for file_path in root_dir.rglob("*"):
            if not file_path.is_file():
                continue
            try:
                name_match = query_lower in file_path.name.lower()
                content = file_path.read_text(encoding="utf-8", errors="replace")
                content_lower = content.lower()
                content_match = query_lower in content_lower
            except OSError:
                continue

            if not name_match and not content_match:
                continue

            score = 1.0 if name_match else 0.5
            snippet = ""
            if content_match:
                idx = content_lower.find(query_lower)
                start = max(0, idx - 80)
                end = min(len(content), idx + len(query) + 80)
                snippet = content[start:end].replace("\n", " ").replace("\r", " ")

            out.append(
                {
                    "path": str(file_path),
                    "score": score,
                    "snippet": snippet,
                    "is_dir": False,
                    "source": "fallback",
                    "kind": "text",
                }
            )
            if len(out) >= k:
                break

        return out


_backend_facade = BackendFacade()


def get_backend_facade() -> BackendFacade:
    return _backend_facade
