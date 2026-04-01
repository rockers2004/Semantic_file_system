import { useState } from "react";
import { CommandResultItem, runCommand } from "../api/files";

interface UnifiedInputProps {
  setSelectedFile: (path: string) => void;
}

type UnifiedStatus = "idle" | "loading" | "error" | "done";

export function UnifiedInput({ setSelectedFile }: UnifiedInputProps) {
  const [text, setText] = useState("");
  const [status, setStatus] = useState<UnifiedStatus>("idle");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [kind, setKind] = useState<"command_placeholder" | "search" | "">("");
  const [results, setResults] = useState<CommandResultItem[]>([]);

  const handleRun = async () => {
    const trimmed = text.trim();
    if (!trimmed) {
      setStatus("error");
      setError("Please enter a command or search query.");
      setKind("");
      setMessage("");
      setResults([]);
      return;
    }

    setStatus("loading");
    setError("");

    try {
      const data = await runCommand(trimmed);
      setKind(data.kind);
      setMessage(data.message);
      setResults(data.results);
      setStatus("done");
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : "Failed to run input");
      setKind("");
      setMessage("");
      setResults([]);
    }
  };

  return (
    <section className="unified-input-panel">
      <h3>Ask or Command</h3>
      <div className="unified-input-controls">
        <input
          type="text"
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder="Type search text or command-like input"
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              void handleRun();
            }
          }}
        />
        <button type="button" onClick={() => void handleRun()} disabled={status === "loading"}>
          {status === "loading" ? "Running..." : "Run"}
        </button>
      </div>

      {status === "loading" && <p className="unified-status">Running request...</p>}
      {status === "error" && <p className="unified-error">{error}</p>}

      {status === "done" && (
        <div className="unified-result">
          <p className="unified-result-kind">Type: {kind || "unknown"}</p>
          <p className="unified-result-message">{message || "No message"}</p>

          {results.length > 0 && (
            <div className="unified-result-list">
              {results.map((item) => (
                <button
                  key={item.path}
                  type="button"
                  className="unified-result-item"
                  onClick={() => setSelectedFile(item.path)}
                >
                  <div className="unified-result-path">{item.path}</div>
                  <div className="unified-result-score">score: {item.score.toFixed(2)}</div>
                  <div className="unified-result-snippet">{item.snippet || "No snippet"}</div>
                </button>
              ))}
            </div>
          )}

          {kind === "search" && results.length === 0 && <p className="unified-status">No matches found.</p>}
        </div>
      )}
    </section>
  );
}
