import { useEffect, useCallback, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { TreeEntry } from "../api/files";
import { PreviewHeader } from "./PreviewHeader";
import { PreviewTabs, PreviewTabId } from "./PreviewTabs";
import { PdfPreviewCard } from "./PdfPreviewCard";
import { FileMetadata } from "./FileMetadata";
import { ActionBar } from "./ActionBar";
import { SemanticGraph } from "./SemanticGraph";

interface FilePreviewProps {
  selectedPath: string;
  selectedEntry?: TreeEntry | null;
  similarityScore?: number;
  tags?: string[];
  onFileSelect?: (path: string) => void;
}

type PreviewKind = "text" | "image" | "video" | "pdf" | "protected";

const KNOWN_PROTECTED_EXTENSIONS = [
  ".age", ".asc", ".dmg", ".enc", ".encrypted", ".gpg", ".hc",
  ".kdbx", ".p12", ".pfx", ".pgp", ".sparsebundle", ".sparseimage", ".tc",
];

function getPreviewKind(path: string, selectedEntry?: TreeEntry | null): PreviewKind {
  if (selectedEntry?.is_protected) return "protected";

  const lower = path.toLowerCase();
  const imageExt = [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg"];
  const videoExt = [".mp4", ".webm", ".ogg", ".mov", ".m4v", ".avi", ".mkv"];

  if (KNOWN_PROTECTED_EXTENSIONS.some((ext) => lower.endsWith(ext))) return "protected";
  if (lower.endsWith(".pdf")) return "pdf";
  if (imageExt.some((ext) => lower.endsWith(ext))) return "image";
  if (videoExt.some((ext) => lower.endsWith(ext))) return "video";
  return "text";
}

export function FilePreview({ selectedPath, selectedEntry, similarityScore, tags, onFileSelect }: FilePreviewProps) {
  const [activeTab, setActiveTab] = useState<PreviewTabId>("overview");
  const [openError, setOpenError] = useState("");

  const previewKind = getPreviewKind(selectedPath, selectedEntry);

  useEffect(() => {
    setActiveTab("overview");
    setOpenError("");
  }, [selectedPath]);

  const handleOpen = useCallback(async () => {
    if (!selectedPath) return;
    setOpenError("");
    try {
      await invoke("open_in_default_app", { path: selectedPath });
    } catch (err) {
      setOpenError(err instanceof Error ? err.message : String(err || "Failed to open"));
    }
  }, [selectedPath]);

  const handleOpenFolder = useCallback(async () => {
    if (!selectedPath) return;
    try {
      await invoke("show_in_folder", { path: selectedPath });
    } catch {
      setOpenError("Could not open containing folder");
    }
  }, [selectedPath]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.ctrlKey && !e.metaKey) {
      void handleOpen();
    }
    if ((e.ctrlKey || e.metaKey) && e.key === "o") {
      e.preventDefault();
      void handleOpenFolder();
    }
  }, [handleOpen, handleOpenFolder]);

  if (!selectedPath) {
    return (
      <section className="preview-card">
        <div className="preview-placeholder">Select a file to see what's inside.</div>
      </section>
    );
  }

  const fileName = selectedPath.split(/[/\\]/).pop() || selectedPath;
  const resolvedTags = tags ?? selectedEntry?.tags ?? [];

  return (
    <section className="preview-card" onKeyDown={handleKeyDown} tabIndex={0}>
      <div className="preview-card-header">
        <PreviewHeader fileName={fileName} filePath={selectedPath} />
      </div>
      <div className="preview-card-tabs">
        <PreviewTabs activeTab={activeTab} onTabChange={setActiveTab} />
      </div>

      <div className="preview-card-body">
        {activeTab === "overview" && (
          <>
            <PdfPreviewCard
              previewKind={previewKind}
              selectedPath={selectedPath}
              selectedEntry={selectedEntry}
            />
            <FileMetadata
              selectedEntry={selectedEntry}
              selectedPath={selectedPath}
              similarityScore={similarityScore}
              tags={resolvedTags}
            />
          </>
        )}

        {activeTab === "content" && (
          <PdfPreviewCard
            previewKind={previewKind}
            selectedPath={selectedPath}
            selectedEntry={selectedEntry}
          />
        )}

        {activeTab === "graph" && (
          <SemanticGraph setSelectedFile={onFileSelect || (() => {})} />
        )}

        {activeTab === "info" && (
          <FileMetadata
            selectedEntry={selectedEntry}
            selectedPath={selectedPath}
            similarityScore={similarityScore}
            tags={resolvedTags}
          />
        )}

        {openError && <div className="preview-error">{openError}</div>}
      </div>

      <div className="preview-card-actions">
        <ActionBar onOpen={handleOpen} onOpenFolder={handleOpenFolder} />
      </div>
    </section>
  );
}
