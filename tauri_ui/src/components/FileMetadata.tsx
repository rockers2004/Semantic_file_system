import type { TreeEntry } from "../api/files";

interface FileMetadataProps {
  selectedEntry?: TreeEntry | null;
  selectedPath: string;
  similarityScore?: number;
  tags?: string[];
}

const FORMAT_LABELS: Record<string, string> = {
  pdf: "PDF Document",
  txt: "Text File",
  md: "Markdown",
  js: "JavaScript",
  ts: "TypeScript",
  jsx: "React (JSX)",
  tsx: "React (TSX)",
  py: "Python",
  rs: "Rust",
  go: "Go",
  java: "Java",
  cpp: "C++",
  c: "C",
  h: "C Header",
  json: "JSON",
  yaml: "YAML",
  yml: "YAML",
  xml: "XML",
  html: "HTML",
  css: "CSS",
  scss: "SCSS",
  sass: "SASS",
  less: "LESS",
  png: "PNG Image",
  jpg: "JPEG Image",
  jpeg: "JPEG Image",
  gif: "GIF Image",
  webp: "WebP Image",
  svg: "SVG Image",
  bmp: "BMP Image",
  ico: "Icon",
  mp4: "MP4 Video",
  webm: "WebM Video",
  mov: "MOV Video",
  avi: "AVI Video",
  mkv: "MKV Video",
  m4v: "M4V Video",
  mp3: "MP3 Audio",
  wav: "WAV Audio",
  flac: "FLAC Audio",
  ogg: "OGG Audio",
  m4a: "M4A Audio",
  aac: "AAC Audio",
  wma: "WMA Audio",
  doc: "Word Document",
  docx: "Word Document",
  xls: "Excel Spreadsheet",
  xlsx: "Excel Spreadsheet",
  ppt: "PowerPoint",
  pptx: "PowerPoint",
  zip: "ZIP Archive",
  tar: "TAR Archive",
  gz: "GZip Archive",
  rar: "RAR Archive",
  "7z": "7z Archive",
  iso: "Disk Image",
  dmg: "Disk Image",
  exe: "Executable",
  sh: "Shell Script",
  bat: "Batch Script",
  log: "Log File",
  cfg: "Configuration",
  conf: "Configuration",
  ini: "Configuration",
  env: "Environment File",
  lock: "Lock File",
  tmp: "Temporary File",
};

const CATEGORY_LABELS: Record<string, string> = {
  study: "Study Material",
  documents: "Documents",
  code: "Source Code",
  images: "Images",
  protected: "Protected",
  personal: "Personal",
  college: "College Work",
  medical: "Medical",
  finance: "Finance",
};

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function getExtension(path: string): string {
  const parts = path.toLowerCase().split(".");
  return parts.length > 1 ? parts[parts.length - 1] : "";
}

function getFileTypeLabel(path: string): string {
  const ext = getExtension(path);
  return FORMAT_LABELS[ext] || `${ext.toUpperCase()} File`;
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString("en-US", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function FileMetadata({ selectedEntry, selectedPath, similarityScore, tags }: FileMetadataProps) {
  const ext = getExtension(selectedPath);
  const typeLabel = getFileTypeLabel(selectedPath);
  const sizeLabel = selectedEntry?.size != null ? formatSize(selectedEntry.size) : null;
  const modifiedLabel = selectedEntry?.modified ? formatDate(selectedEntry.modified) : null;
  const category = selectedEntry?.category ?? null;
  const categoryConfidence = selectedEntry?.category_confidence ?? null;
  const categoryReason = selectedEntry?.category_reason ?? null;
  const securityStatus = selectedEntry?.security_status ?? null;
  const dirPath = selectedPath.split(/[/\\]/).slice(0, -1).join("/");

  const displayTags = tags ?? [];
  const showMore = displayTags.length > 4;
  const visibleTags = showMore ? displayTags.slice(0, 4) : displayTags;
  const extraCount = displayTags.length - 4;

  return (
    <div className="preview-metadata">
      <h3 className="preview-metadata-title">About this file</h3>
      <div className="preview-metadata-grid">

        {/* Basic info section */}
        <span className="preview-meta-label">Type</span>
        <span className="preview-meta-value">{typeLabel}</span>

        <span className="preview-meta-label">Extension</span>
        <span className="preview-meta-value">.{ext}</span>

        {sizeLabel != null && (
          <>
            <span className="preview-meta-label">Size</span>
            <span className="preview-meta-value">{sizeLabel}</span>
          </>
        )}

        <span className="preview-meta-label">Location</span>
        <span className="preview-meta-value preview-meta-path" title={dirPath}>{dirPath}</span>

        {modifiedLabel != null && (
          <>
            <span className="preview-meta-label">Modified</span>
            <span className="preview-meta-value">{modifiedLabel}</span>
          </>
        )}

        {/* Semantic info */}
        <div className="preview-meta-divider" />

        {category && (
          <>
            <span className="preview-meta-label">Category</span>
            <span className="preview-meta-value">
              <span className="preview-category-badge" title={categoryReason ?? undefined}>
                {CATEGORY_LABELS[category] || category}
                {categoryConfidence != null && (
                  <span className="preview-category-confidence">
                    {Math.round(categoryConfidence * 100)}%
                  </span>
                )}
              </span>
            </span>
          </>
        )}

        {securityStatus && (
          <>
            <span className="preview-meta-label">Indexing</span>
            <span className="preview-meta-value">
              <span className="preview-status-badge">
                {securityStatus === "content" ? "Full content" : securityStatus}
              </span>
            </span>
          </>
        )}

        {similarityScore != null && (
          <>
            <span className="preview-meta-label">Similarity</span>
            <span className="preview-meta-value">
              <span className="preview-similarity">
                <span className="preview-similarity-dot" />
                {Math.round(similarityScore * 100)}%
              </span>
            </span>
          </>
        )}

        {displayTags.length > 0 && (
          <>
            <span className="preview-meta-label">Tags</span>
            <span className="preview-meta-value">
              <span className="preview-tag-list">
                {visibleTags.map((tag) => (
                  <span key={tag} className="preview-tag">{tag}</span>
                ))}
                {showMore && <span className="preview-tag-more">+{extraCount}</span>}
              </span>
            </span>
          </>
        )}
      </div>
    </div>
  );
}
