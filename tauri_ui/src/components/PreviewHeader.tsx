import { useState } from "react";

interface PreviewHeaderProps {
  fileName: string;
  filePath: string;
}

export function PreviewHeader({ fileName, filePath }: PreviewHeaderProps) {
  const [favorite, setFavorite] = useState(false);

  return (
    <div className="preview-header">
      <div className="preview-header-left">
        <div className="preview-file-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
            <polyline points="10 9 9 9 8 9" />
          </svg>
        </div>
        <div className="preview-file-info">
          <h2 className="preview-file-name" title={fileName}>{fileName}</h2>
          <p className="preview-file-path" title={filePath}>{filePath}</p>
        </div>
      </div>
      <button
        type="button"
        className={`preview-fav-btn ${favorite ? "active" : ""}`}
        onClick={() => setFavorite((p) => !p)}
        title={favorite ? "Remove from favorites" : "Add to favorites"}
      >
        {favorite ? (
          <svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" strokeWidth="1.5">
            <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
          </svg>
        ) : (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
          </svg>
        )}
      </button>
    </div>
  );
}
