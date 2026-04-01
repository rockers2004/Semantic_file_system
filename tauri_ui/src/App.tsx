import { useEffect, useState } from "react";
import { StartupScreen } from "./components/StartupScreen";
import { FileTree } from "./components/FileTree";
import { FilePreview } from "./components/FilePreview";
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

  // Main app UI goes here once backend is ready
  return (
    <div className="app-layout">
      <aside className="sidebar">
        <section className="root-selector-card">
          <h3>Root Directory</h3>
          <p className="root-path-display">Current: {currentRootPath || "Loading..."}</p>
          <div className="root-selector-row">
            <input
              type="text"
              value={rootPathInput}
              onChange={(event) => setRootPathInput(event.target.value)}
              placeholder="Enter folder path"
            />
            <button type="button" onClick={() => void handleBrowseRoot()} disabled={isUpdatingRoot}>
              Browse...
            </button>
            <button type="button" onClick={() => void handleSetRoot()} disabled={isUpdatingRoot}>
              {isUpdatingRoot ? "Setting..." : "Set Root"}
            </button>
          </div>
          {rootStatus && <p className="root-status-ok">{rootStatus}</p>}
          {rootError && <p className="root-status-error">{rootError}</p>}
        </section>

        <FileTree onFileSelect={setSelectedFile} refreshToken={treeRefreshToken} />
      </aside>

      <main className="main-panel">
        <h1>SLPFS Desktop App</h1>
        <p>Backend ready.</p>

        <div className="selected-file-card">
          <strong>Selected file:</strong>
          <p>{selectedFile || "No file selected yet"}</p>
        </div>

        <FilePreview selectedPath={selectedFile} />
      </main>
    </div>
  );
}

export default App;