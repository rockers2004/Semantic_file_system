import { useEffect, useState } from "react";
import { PanelRightClose, PanelRightOpen } from "lucide-react";
import { StartupScreen } from "./components/StartupScreen";
import { FileTree } from "./components/FileTree";
import { FilePreview } from "./components/FilePreview";
import { UnifiedInput } from "./components/UnifiedInput";
import { getConfig, TreeEntry, updateRootPath } from "./api/files";
import { open } from "@tauri-apps/plugin-dialog";
import "./App.css";

function App() {
  const [backendReady, setBackendReady] = useState(false);
  const [selectedFile, setSelectedFile] = useState<string>("");
  const [selectedFileEntry, setSelectedFileEntry] = useState<TreeEntry | null>(null);
  const [rootPathInput, setRootPathInput] = useState("");
  const [currentRootPath, setCurrentRootPath] = useState("");
  const [rootError, setRootError] = useState("");
  const [isUpdatingRoot, setIsUpdatingRoot] = useState(false);
  const [treeRefreshToken, setTreeRefreshToken] = useState(0);
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);

  useEffect(() => {
    if (selectedFile) {
      setIsPreviewOpen(true);
    }
  }, [selectedFile]);

  useEffect(() => {
    if (!backendReady) {
      return;
    }

    const loadConfig = async () => {
      try {
        const config = await getConfig();
        setCurrentRootPath(config.root_path);
        setRootPathInput(config.root_path);
      } catch (err) {
        setRootError(err instanceof Error ? err.message : "Failed to load current root path");
      }
    };

    void loadConfig();
  }, [backendReady]);

  const handleSetRoot = async () => {
    const nextRoot = rootPathInput.trim();
    if (!nextRoot) {
      setRootError("Root path cannot be empty");
      return;
    }

    setIsUpdatingRoot(true);
    setRootError("");

    try {
      const data = await updateRootPath(nextRoot);
      setCurrentRootPath(data.root_path);
      setRootPathInput(data.root_path);
      setSelectedFile("");
      setSelectedFileEntry(null);
      setTreeRefreshToken((prev) => prev + 1);
    } catch (err) {
      setRootError(err instanceof Error ? err.message : "Failed to set root path");
    } finally {
      setIsUpdatingRoot(false);
    }
  };

  const handleFileSelect = (path: string, entry?: TreeEntry) => {
    setSelectedFile(path);
    setSelectedFileEntry(entry ?? null);
  };

  const handleBrowseRoot = async () => {
    setRootError("");

    try {
      const selected = await open({
        directory: true,
        multiple: false,
        defaultPath: rootPathInput || currentRootPath || undefined,
      });

      if (typeof selected === "string" && selected.trim()) {
        setRootPathInput(selected);
      }
    } catch (err) {
      setRootError(err instanceof Error ? err.message : "Failed to open folder picker");
    }
  };
  
  // Loading state: show startup screen until backend is ready
  if (!backendReady) {
    return <StartupScreen onReady={() => setBackendReady(true)} />;
  }

  // Main app UI gets a smoother layout for Layman users
  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-header">
          <h2>My Files</h2>
        </div>
        
        <FileTree onFileSelect={handleFileSelect} refreshToken={treeRefreshToken} selectedFile={selectedFile} />
        
        <div className="root-settings-compact">
          <p className="settings-label">Search Folder</p>
          <div className="root-quick-selector">
            <span className="current-root-pill" title={currentRootPath}>{currentRootPath ? "Folder Set" : "Not Set"}</span>
            <button type="button" className="btn-icon" onClick={() => void handleBrowseRoot()} title="Change Folder">
              ⚙️
            </button>
          </div>
          {rootPathInput !== currentRootPath && (
             <button type="button" className="btn-confirm" onClick={() => void handleSetRoot()} disabled={isUpdatingRoot}>
              {isUpdatingRoot ? "Applying..." : `Apply Folder`}
             </button>
          )}
          {rootError && <p className="root-status-error">{rootError}</p>}
        </div>
      </aside>

      <main className="main-panel">
        <header className="main-header">
          <div className="main-header-titles">
            <h1>What are you looking for?</h1>
            <p>Just type what you need. We'll find the right files or do the task for you.</p>
          </div>
          <button className="btn-icon preview-toggle" onClick={() => setIsPreviewOpen(!isPreviewOpen)} title="Toggle Preview">
            {isPreviewOpen ? <PanelRightClose size={20} /> : <PanelRightOpen size={20} />}
          </button>
        </header>

        <div className="content-split-area">
          <div className={`search-arena ${isPreviewOpen ? 'with-preview' : ''}`}>
            <UnifiedInput setSelectedFile={handleFileSelect} />
          </div>

          {isPreviewOpen && (
            <div className="preview-arena">
              <FilePreview selectedPath={selectedFile} selectedEntry={selectedFileEntry} onFileSelect={handleFileSelect} />
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

export default App;
