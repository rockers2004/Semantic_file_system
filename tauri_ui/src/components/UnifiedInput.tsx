import { useState } from "react";
import { CommandResultItem, runCommand, searchFiles } from "../api/files";

interface UnifiedInputProps {
  setSelectedFile: (path: string) => void;
}

type UnifiedStatus = "idle" | "loading" | "error" | "done";
type SearchMode = "general" | "multimodal" | "auto" | "hybrid";
type ActionPreset =
  | "auto"
  | "search"
  | "image"
  | "create_file"
  | "create_dir"
  | "write"
  | "read"
  | "list"
  | "delete"
  | "move"
  | "copy"
  | "reindex"
  | "stats"
  | "chat";

type ActionConfig = {
  label: string;
  prefix: string;
  route: "auto" | "command" | "search" | "multimodal";
  requiresBody: boolean;
  placeholder: string;
};

const ACTION_ORDER: ActionPreset[] = [
  "auto",
  "search",
  "image",
  "create_file",
  "create_dir",
  "write",
  "read",
  "list",
  "delete",
  "move",
  "copy",
  "reindex",
  "stats",
  "chat",
];

const ACTION_PRESETS: Record<ActionPreset, ActionConfig> = {
  auto: {
    label: "Auto",
    prefix: "",
    route: "auto",
    requiresBody: true,
    placeholder: "Type a question, command, or search query",
  },
  search: {
    label: "search",
    prefix: "search",
    route: "search",
    requiresBody: true,
    placeholder: "Describe the file or text you want to retrieve",
  },
  image: {
    label: "image",
    prefix: "image",
    route: "multimodal",
    requiresBody: true,
    placeholder: "Describe the image you want to retrieve",
  },
  create_file: {
    label: "create_file",
    prefix: "create_file",
    route: "command",
    requiresBody: true,
    placeholder: "Add the file name and optional content",
  },
  create_dir: {
    label: "create_dir",
    prefix: "create_dir",
    route: "command",
    requiresBody: true,
    placeholder: "Add the directory name",
  },
  write: {
    label: "write",
    prefix: "write",
    route: "command",
    requiresBody: true,
    placeholder: "Add the file name and content to write",
  },
  read: {
    label: "read",
    prefix: "read",
    route: "command",
    requiresBody: true,
    placeholder: "Add the file name you want to read",
  },
  list: {
    label: "list",
    prefix: "list",
    route: "command",
    requiresBody: false,
    placeholder: "Optionally add a subdirectory to list",
  },
  delete: {
    label: "delete",
    prefix: "delete",
    route: "command",
    requiresBody: true,
    placeholder: "Add the file or directory you want to delete",
  },
  move: {
    label: "move",
    prefix: "move",
    route: "command",
    requiresBody: true,
    placeholder: "Add source and destination",
  },
  copy: {
    label: "copy",
    prefix: "copy",
    route: "command",
    requiresBody: true,
    placeholder: "Add source and destination",
  },
  reindex: {
    label: "reindex",
    prefix: "reindex",
    route: "command",
    requiresBody: false,
    placeholder: "No extra text needed",
  },
  stats: {
    label: "stats",
    prefix: "stats",
    route: "command",
    requiresBody: false,
    placeholder: "No extra text needed",
  },
  chat: {
    label: "chat",
    prefix: "chat",
    route: "command",
    requiresBody: true,
    placeholder: "Type your message to the assistant",
  },
};

export function UnifiedInput({ setSelectedFile }: UnifiedInputProps) {
  const [text, setText] = useState("");
  const [mode, setMode] = useState<SearchMode>("general");
  const [preset, setPreset] = useState<ActionPreset>("auto");
  const [status, setStatus] = useState<UnifiedStatus>("idle");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [inputText, setInputText] = useState("");
  const [action, setAction] = useState("");
  const [results, setResults] = useState<CommandResultItem[]>([]);

  const presetConfig = ACTION_PRESETS[preset];
  const canEditMode = presetConfig.route === "auto";

  const getSearchMessage = (
    total: number,
    modeLabel: string,
    backendError?: string,
  ): string => {
    if (backendError) {
      return backendError;
    }
    if (total <= 0) {
      return `No ${modeLabel} matches found.`;
    }
    return `${total} ${modeLabel} result${total === 1 ? "" : "s"} found.`;
  };

  const handleRun = async () => {
    const trimmed = text.trim();
    const composedInput = presetConfig.prefix ? `${presetConfig.prefix}${trimmed ? ` ${trimmed}` : ""}` : trimmed;

    if ((presetConfig.requiresBody && !trimmed) || !composedInput) {
      setStatus("error");
      setError(presetConfig.requiresBody ? "Please enter the rest of the request." : "Please enter a command or search query.");
      setMessage("");
      setInputText("");
      setAction("");
      setResults([]);
      return;
    }

    setStatus("loading");
    setError("");

    try {
      setInputText(composedInput);

      if (presetConfig.route === "search") {
        const data = await searchFiles(trimmed, 10, "general");
        setMessage(getSearchMessage(data.total, "SLPFS", data.error));
        setAction("search");
        setResults(data.results);
        if (data.results.length > 0 && data.results[0].path) {
          setSelectedFile(data.results[0].path);
        }
      } else if (presetConfig.route === "multimodal") {
        const data = await searchFiles(trimmed, 10, "multimodal");
        setMessage(getSearchMessage(data.total, "multimodal", data.error));
        setAction("image");
        setResults(data.results);
        if (data.results.length > 0 && data.results[0].path) {
          setSelectedFile(data.results[0].path);
        }
      } else if (presetConfig.route === "command") {
        const data = await runCommand(composedInput);
        setMessage(data.message);
        setAction(data.parsed?.action || "");
        setResults(data.results);
        if (data.results.length > 0 && data.results[0].path) {
          setSelectedFile(data.results[0].path);
        }
      } else if (mode === "general") {
        const data = await runCommand(trimmed);
        setMessage(data.message);
        setAction(data.parsed?.action || "");
        setResults(data.results);
        if (data.results.length > 0 && data.results[0].path) {
          setSelectedFile(data.results[0].path);
        }
      } else {
        const data = await searchFiles(trimmed, 10, mode);
        setMessage(getSearchMessage(data.total, mode, data.error));
        setAction(mode === "multimodal" ? "image" : "search");
        setResults(data.results);
        if (data.results.length > 0 && data.results[0].path) {
          setSelectedFile(data.results[0].path);
        }
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
                      key={item.composite_id || item.path}
                      type="button"
                      className="unified-result-item"
                      onClick={() => setSelectedFile(item.path)}
                    >
                      <div className="unified-result-path">{item.path}</div>
                      <div className="unified-result-score">
                        relevance: {Math.max(0, item.score).toFixed(2)}
                        {item.score < 0 ? " (low match)" : ""}
                        {item.media_type ? ` | type: ${item.media_type}` : ""}
                        {typeof item.timestamp === "number" ? ` | time: ${item.timestamp.toFixed(2)}s` : ""}
                      </div>
                      <div className="unified-result-snippet">{item.snippet || "No snippet"}</div>
                    </button>
                  ))}
                </div>
              )}

              {results.length === 0 && (action === "search" || action === "image") && (
                <p className="unified-status">
                  {action === "image"
                    ? "No multimodal results to display. If you expected matches, run multimodal indexing first."
                    : "No matches found."}
                </p>
              )}
            </>
          )}
        </div>

        <div className="unified-input-controls unified-input-controls-bottom">
          <select value={preset} onChange={(event) => setPreset(event.target.value as ActionPreset)}>
            {ACTION_ORDER.map((value) => (
              <option key={value} value={value}>
                {ACTION_PRESETS[value].label}
              </option>
            ))}
          </select>
          <div className="unified-input-entry">
            {presetConfig.prefix && <span className="unified-input-prefix">{presetConfig.prefix}</span>}
            <input
              type="text"
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder={presetConfig.placeholder}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  void handleRun();
                }
              }}
            />
          </div>
          <select value={mode} onChange={(event) => setMode(event.target.value as SearchMode)} disabled={!canEditMode}>
            <option value="general">General (SLPFS)</option>
            <option value="multimodal">Multimodal (Semantixel)</option>
            <option value="auto">Auto</option>
            <option value="hybrid">Hybrid</option>
          </select>
          <button type="button" onClick={() => void handleRun()} disabled={status === "loading"}>
            {status === "loading" ? "Running..." : "Send"}
          </button>
        </div>
        {!canEditMode && (
          <p className="unified-routing-hint">
            The selected prefix controls routing automatically: command prefixes use SLPFS, `search` uses SLPFS retrieval,
            and `image` uses multimodal retrieval.
          </p>
        )}
        {canEditMode && <p className="unified-routing-hint">Use the routing selector on the right only when the action preset is set to Auto.</p>}
      </div>
    </section>
  );
}
