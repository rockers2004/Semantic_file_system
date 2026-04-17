import { useEffect, useState } from "react";
import { StartupScreen } from "./components/StartupScreen";
import { FileTree } from "./components/FileTree";
import { FilePreview } from "./components/FilePreview";
import { UnifiedInput } from "./components/UnifiedInput";
import { getConfig, updateRootPath } from "./api/files";
import { open } from "@tauri-apps/plugin-dialog";
import "./App.css";

function App() {
  const [backendReady, setBackendReady] = useState(false);
  const [selectedFile, setSelectedFile] = useState<string>("");
  const [rootPathInput, setRootPathInput] = useState("");
  const [currentRootPath, setCurrentRootPath] = useState("");
  const [rootStatus, setRootStatus] = useState("");
  const [rootError, setRootError] = useState("");
  const [isUpdatingRoot, setIsUpdatingRoot] = useState(false);
  const [treeRefreshToken, setTreeRefreshToken] = useState(0);

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
      setRootStatus("");
      return;
    }

    setIsUpdatingRoot(true);
    setRootError("");
    setRootStatus("");

    try {
      const data = await updateRootPath(nextRoot);
      setCurrentRootPath(data.root_path);
      setRootPathInput(data.root_path);
      setSelectedFile("");
      setTreeRefreshToken((prev) => prev + 1);
      setRootStatus("Root path updated successfully.");
    } catch (err) {
      setRootError(err instanceof Error ? err.message : "Failed to set root path");
    } finally {
      setIsUpdatingRoot(false);
    }
  };

  const handleBrowseRoot = async () => {
    setRootError("");
    setRootStatus("");

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
        
        <FileTree onFileSelect={setSelectedFile} refreshToken={treeRefreshToken} />
        
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
          <h1>What are you looking for?</h1>
          <p>Just type what you need. We'll find the right files or do the task for you.</p>
        </header>

        <div className="search-arena">
          <UnifiedInput setSelectedFile={setSelectedFile} />
        </div>

        <div className="preview-arena">
          <FilePreview selectedPath={selectedFile} />
        </div>
      </main>
    </div>
  );
}

export default App;