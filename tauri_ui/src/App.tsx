import { useState } from "react";
import { StartupScreen } from "./components/StartupScreen";
import { FileTree } from "./components/FileTree";
import "./App.css";

function App() {
  const [backendReady, setBackendReady] = useState(false);
  const [selectedFile, setSelectedFile] = useState<string>("");
  
  // Loading state: show startup screen until backend is ready
  if (!backendReady) {
    return <StartupScreen onReady={() => setBackendReady(true)} />;
  }

  // Main app UI goes here once backend is ready
  return (
    <div className="app-layout">
      <aside className="sidebar">
        <FileTree onFileSelect={setSelectedFile} />
      </aside>

      <main className="main-panel">
        <h1>SLPFS Desktop App</h1>
        <p>Backend ready.</p>
        <div className="selected-file-card">
          <strong>Selected file:</strong>
          <p>{selectedFile || "No file selected yet"}</p>
        </div>
      </main>
    </div>
  );
}

export default App;