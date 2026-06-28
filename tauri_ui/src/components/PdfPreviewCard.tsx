import { useEffect, useState } from "react";
import { convertFileSrc } from "@tauri-apps/api/core";
import { readFile } from "../api/files";
import type { TreeEntry } from "../api/files";

type PreviewKind = "text" | "image" | "video" | "pdf" | "protected";

interface PdfPreviewCardProps {
  previewKind: PreviewKind;
  selectedPath: string;
  selectedEntry?: TreeEntry | null;
}

export function PdfPreviewCard({ previewKind, selectedPath, selectedEntry }: PdfPreviewCardProps) {
  const [loading, setLoading] = useState(false);
  const [content, setContent] = useState("");
  const [mediaSrc, setMediaSrc] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    const load = async () => {
      if (!selectedPath) return;

      if (previewKind === "text") {
        setLoading(true);
        setMediaSrc("");
        try {
          const data = await readFile(selectedPath);
          if (active) setContent(data.content);
        } catch (err) {
          if (active) setError(err instanceof Error ? err.message : "Failed to load");
        } finally {
          if (active) setLoading(false);
        }
      } else {
        setContent("");
        setError("");
        setLoading(false);
        if (previewKind !== "pdf") {
          setMediaSrc(getMediaSrc(selectedPath));
        }
      }
    };

    void load();
    return () => { active = false; };
  }, [selectedPath, previewKind]);

  if (loading) {
    return (
      <div className="preview-skeleton">
        <div className="preview-skeleton-pulse" />
      </div>
    );
  }

  if (error) {
    return <div className="preview-error">{error}</div>;
  }

  if (previewKind === "text") {
    return <div className="preview-text-content">{content || "(empty)"}</div>;
  }

  if (previewKind === "image") {
    return (
      <div className="preview-media-card">
        <img src={mediaSrc} alt="Preview" onError={() => setError("Unable to display image")} />
      </div>
    );
  }

  if (previewKind === "video") {
    return (
      <div className="preview-media-card">
        <video src={mediaSrc} controls preload="metadata" onError={() => setError("Unable to play video")} />
      </div>
    );
  }

  if (previewKind === "protected") {
    return (
      <div className="preview-protected-card">
        <h4>Protected file</h4>
        <p>{selectedEntry?.security_reason || "This file type is treated as protected, so content preview is skipped."}</p>
        <p style={{ fontSize: 13, color: "var(--text-secondary)" }}>
          {selectedEntry?.security_status || "metadata-only"} indexing is available.
        </p>
      </div>
    );
  }

  if (previewKind === "pdf") {
    return (
      <div className="preview-media-card">
        <div style={{ textAlign: "center", color: "var(--text-secondary)" }}>
          <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.2" style={{ marginBottom: 16, opacity: 0.4 }}>
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
          </svg>
          <p style={{ margin: 0, fontSize: 15 }}>PDF preview not shown to keep the app fast.</p>
        </div>
        <div className="preview-page-indicator">1 / 1</div>
      </div>
    );
  }

  return null;
}

function getMediaSrc(path: string): string {
  try {
    return convertFileSrc(path);
  } catch {
    const normalized = path.replace(/\\/g, "/");
    return `file:///${encodeURI(normalized)}`;
  }
}
