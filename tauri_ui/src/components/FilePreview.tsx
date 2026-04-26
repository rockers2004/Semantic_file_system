import { useEffect, useState } from "react";
import { convertFileSrc, invoke } from "@tauri-apps/api/core";
import { readFile } from "../api/files";

interface FilePreviewProps {
  selectedPath: string;
}

type PreviewKind = "text" | "image" | "video" | "pdf";

function getPreviewKind(path: string): PreviewKind {
  const lower = path.toLowerCase();
  const imageExt = [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg"];
  const videoExt = [".mp4", ".webm", ".ogg", ".mov", ".m4v", ".avi", ".mkv"];

  if (lower.endsWith(".pdf")) {
    return "pdf";
  }
  if (imageExt.some((ext) => lower.endsWith(ext))) {
    return "image";
  }
  if (videoExt.some((ext) => lower.endsWith(ext))) {
    return "video";
  }
  return "text";
}

function getMediaSrc(path: string): string {
  try {
    return convertFileSrc(path);
  } catch {
    const normalized = path.replace(/\\/g, "/");
    return `file:///${encodeURI(normalized)}`;
  }
}

export function FilePreview({ selectedPath }: FilePreviewProps) {
  const [content, setContent] = useState("");
  const [encoding, setEncoding] = useState("");
  const [size, setSize] = useState<number | null>(null);
  const [modified, setModified] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [mediaSrc, setMediaSrc] = useState("");
  const [mediaError, setMediaError] = useState("");
  const [openError, setOpenError] = useState("");

  const previewKind = getPreviewKind(selectedPath);

  useEffect(() => {
    let isActive = true;

    const loadFile = async () => {
      if (!selectedPath) {
        setContent("");
        setEncoding("");
        setSize(null);
        setModified("");
        setMediaSrc("");
        setMediaError("");
        setError("");
        setLoading(false);
        return;
      }

      if (previewKind !== "text") {
        setContent("");
        setEncoding("");
        setSize(null);
        setModified("");
        setError("");
        setMediaError("");
        setMediaSrc(previewKind === "pdf" ? "" : getMediaSrc(selectedPath));
        setLoading(false);
        return;
      }

      setLoading(true);
      setError("");
      setMediaSrc("");
      setMediaError("");

      try {
        const data = await readFile(selectedPath);

        if (!isActive) {
          return;
        }

        setContent(data.content);
        setEncoding(data.encoding);
        setSize(data.size);
        setModified(data.modified);
      } catch (err) {
        if (!isActive) {
          return;
        }

        setContent("");
        setEncoding("");
        setSize(null);
        setModified("");
        setMediaSrc("");
        setMediaError("");
        setError(err instanceof Error ? err.message : "Failed to load file preview");
      } finally {
        if (isActive) {
          setLoading(false);
        }
      }
    };

    void loadFile();

    return () => {
      isActive = false;
    };
  }, [selectedPath, previewKind]);

  const handleOpenSelectedPath = async () => {
    if (!selectedPath) {
      return;
    }

    setOpenError("");
    try {
      await invoke("open_in_default_app", { path: selectedPath });
    } catch (err) {
      setOpenError(err instanceof Error ? err.message : String(err || "Failed to open this file in the default app"));
    }
  };

  if (!selectedPath) {
    return <div className="file-preview-placeholder">Select a file to see what's inside.</div>;
  }

  return (
    <section className="file-preview-panel">
      <div className="file-preview-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h3>{selectedPath.split(/[/\\]/).pop()}</h3>
          <p className="file-preview-path">{selectedPath}</p>
        </div>
        <button
          type="button"
          className="btn-icon"
          onClick={() => void handleOpenSelectedPath()}
          title="Open in default app"
          style={{ width: '40px', height: '40px', display: 'flex', justifyContent: 'center', alignItems: 'center', background: 'var(--accent)', color: 'white', borderRadius: '50%' }}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
        </button>
      </div>

      {openError && <div className="file-preview-error" style={{ color: 'red', marginTop: '10px' }}>{openError}</div>}

      {loading && <div className="file-preview-status status-loading" style={{ marginTop: '20px' }}>Loading...</div>}
      
      {error && <div className="file-preview-error error-bubble" style={{ marginTop: '20px', padding: '12px' }}>{error}</div>}

      {!loading && !error && previewKind === "text" && (
        <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
          <pre className="file-preview-content" aria-label="file content preview">
            {content}
          </pre>
          <div className="file-preview-meta" style={{ display: 'flex', gap: '16px', fontSize: '12px', color: 'var(--text-dim)', paddingTop: '8px' }}>
            <span>{(size ?? 0) < 1024 ? `${size} B` : `${Math.round((size ?? 0) / 1024)} KB`}</span>
            <span>{encoding || "Unknown encoding"}</span>
            <span>{modified ? new Date(modified).toLocaleString() : "Unknown date"}</span>
          </div>
        </div>
      )}

      {!loading && !error && previewKind === "image" && mediaSrc && (
        <div className="file-preview-media-wrap">
          <img
            className="file-preview-image"
            src={mediaSrc}
            alt="Preview"
            onError={() => setMediaError("Unable to display image preview.")}
          />
        </div>
      )}

      {!loading && !error && previewKind === "video" && mediaSrc && (
        <div className="file-preview-media-wrap">
          <video
            className="file-preview-video"
            src={mediaSrc}
            controls
            preload="metadata"
            onError={() => setMediaError("Unable to play video preview.")}
          />
        </div>
      )}

      {mediaError && <div className="file-preview-error error-bubble" style={{ marginTop: '20px', padding: '12px' }}>{mediaError}</div>}

      {!loading && !error && previewKind === "pdf" && (
        <div className="file-preview-placeholder">
          <p>We don't preview PDFs directly to keep the app fast.</p>
          <button className="btn-confirm" type="button" onClick={() => void handleOpenSelectedPath()} style={{ width: 'auto', padding: '10px 24px' }}>
            Open PDF
          </button>
        </div>
      )}
    </section>
  );
}
