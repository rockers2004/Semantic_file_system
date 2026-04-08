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
  const [inputText, setInputText] = useState("");
  const [action, setAction] = useState("");
  const [results, setResults] = useState<CommandResultItem[]>([]);

  const handleRun = async () => {
    const trimmed = text.trim();
    if (!trimmed) {
      setStatus("error");
      setError("Please enter a command or search query.");
      setMessage("");
      setInputText("");
      setAction("");
      setResults([]);
      return;
    }

    setStatus("loading");
    setError("");

    try {
      setInputText(trimmed);
      const data = await runCommand(trimmed);
      setMessage(data.message);
      setAction(data.parsed?.action || "");
      setResults(data.results);
      if (data.results.length > 0 && data.results[0].path) {
        setSelectedFile(data.results[0].path);
      }
      setStatus("done");
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : "Failed to run input");
      setMessage("");
      setInputText("");
      setAction("");
      setResults([]);
    }
  };

  return (
    <section className="unified-input-panel">
      <div className="unified-input-body">
        <div className="chat-thread unified-chat-thread">
          {status === "loading" && <p className="unified-status">Thinking...</p>}
          {status === "error" && <p className="unified-error">{error}</p>}

          {status === "done" && (
            <>
              <div className="chat-bubble chat-user-bubble">
                <span className="chat-label">You</span>
                <p className="chat-text">{inputText || text}</p>
              </div>

              <div className="chat-bubble chat-assistant-bubble">
                <span className="chat-label">Assistant</span>
                <p className="chat-text">{message || "No response generated."}</p>
              </div>

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
                      <div className="unified-result-score">
                        relevance: {Math.max(0, item.score).toFixed(2)}
                        {item.score < 0 ? " (low match)" : ""}
                      </div>
                      <div className="unified-result-snippet">{item.snippet || "No snippet"}</div>
                    </button>
                  ))}
                </div>
              )}

              {results.length === 0 && action === "search" && <p className="unified-status">No matches found.</p>}
            </>
          )}
        </div>

        <div className="unified-input-controls unified-input-controls-bottom">
          <input
            type="text"
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder="Type a question or command"
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                void handleRun();
              }
            }}
          />
          <button type="button" onClick={() => void handleRun()} disabled={status === "loading"}>
            {status === "loading" ? "Running..." : "Send"}
          </button>
        </div>
      </div>
    </section>
  );
}
