import { useEffect, useState } from "react";
import { readFile } from "../api/files";

interface FilePreviewProps {
  selectedPath: string;
}

export function FilePreview({ selectedPath }: FilePreviewProps) {
  const [content, setContent] = useState("");
  const [encoding, setEncoding] = useState("");
  const [size, setSize] = useState<number | null>(null);
  const [modified, setModified] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let isActive = true;

    const loadFile = async () => {
      if (!selectedPath) {
        setContent("");
        setEncoding("");
        setSize(null);
        setModified("");
        setError("");
        setLoading(false);
        return;
      }

      setLoading(true);
      setError("");

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
  }, [selectedPath]);

  if (!selectedPath) {
    return <div className="file-preview-placeholder">Select a file to preview its contents.</div>;
  }

  return (
    <section className="file-preview-panel">
      <h3>Preview</h3>
      <p className="file-preview-path">{selectedPath}</p>

      {loading && <div className="file-preview-status">Loading preview...</div>}

      {error && <div className="file-preview-error">{error}</div>}

      {!loading && !error && (
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
    </section>
  );
}