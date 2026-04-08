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
      await invoke("open_with_dialog", { path: selectedPath });
    } catch (err) {
      setOpenError(err instanceof Error ? err.message : String(err || "Failed to open app chooser for this file"));
    }
  };

  if (!selectedPath) {
    return <div className="file-preview-placeholder">Select a file to preview its contents.</div>;
  }

  return (
    <section className="file-preview-panel">
      <div className="file-preview-header">
        <div>
          <h3>Preview</h3>
          <p className="file-preview-label">Selected file</p>
        </div>
        <button
          type="button"
          className="file-preview-path file-preview-path-button"
          onClick={() => void handleOpenSelectedPath()}
          title="Choose app to open this file"
        >
          {selectedPath}
        </button>
      </div>

      {openError && <div className="file-preview-error">{openError}</div>}

      {loading && <div className="file-preview-status">Loading preview...</div>}

      {error && <div className="file-preview-error">{error}</div>}

      {!loading && !error && previewKind === "text" && (
        <>
          <div className="file-preview-meta">
            <span>Encoding: {encoding || "unknown"}</span>
            <span>Size: {size ?? 0} bytes</span>
            <span>Modified: {modified || "unknown"}</span>
          </div>

          <pre className="file-preview-content" aria-label="file content preview">
            {content}
          </pre>
        </>
      )}

      {!loading && !error && previewKind === "image" && mediaSrc && (
        <div className="file-preview-media-wrap">
          <img
            className="file-preview-image"
            src={mediaSrc}
            alt="Selected file preview"
            onError={() => setMediaError("Image preview failed to load in WebView.")}
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
            onError={() => setMediaError("Video preview failed to load in WebView.")}
          />
        </div>
      )}

      {mediaError && <div className="file-preview-error">{mediaError}</div>}

      {!loading && !error && previewKind === "pdf" && (
        <div className="file-preview-placeholder">
          <p>PDF preview is disabled in-app for stability on large files.</p>
          <button type="button" onClick={() => void handleOpenSelectedPath()}>
            Open With...
          </button>
        </div>
      )}
    </section>
  );
}