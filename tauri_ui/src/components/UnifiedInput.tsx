import { useState } from "react";
import { CommandResultItem, SkippedFileItem, runCommand, searchByImage, searchFiles } from "../api/files";
import { SemanticGraph } from "./SemanticGraph";

interface UnifiedInputProps {
  setSelectedFile: (path: string) => void;
}

type UnifiedStatus = "idle" | "loading" | "error" | "done";
type SearchMode = "general" | "multimodal" | "audio" | "auto" | "hybrid" | "keyword";
type ActionPreset =
  | "auto"
  | "search"
  | "image"
  | "video"
  | "audio"
  | "keyword"
  | "similar_image"
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
  route: "auto" | "command" | "search" | "multimodal" | "keyword" | "imageSearch";
  mediaType?: "all" | "image" | "video" | "audio";
  requiresBody: boolean;
  placeholder: string;
};

const ACTION_ORDER: ActionPreset[] = [
  "auto",
  "search",
  "image",
  "video",
  "audio",
  "keyword",
  "similar_image",
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
    mediaType: "image",
    requiresBody: true,
    placeholder: "Describe the image you want to retrieve",
  },
  video: {
    label: "video",
    prefix: "video",
    route: "multimodal",
    mediaType: "video",
    requiresBody: true,
    placeholder: "Describe the video you want to retrieve",
  },
  audio: {
    label: "audio",
    prefix: "audio",
    route: "multimodal",
    mediaType: "audio",
    requiresBody: true,
    placeholder: "Describe speech, lyrics, or sounds you want to retrieve",
  },
  keyword: {
    label: "keyword",
    prefix: "keyword",
    route: "keyword",
    mediaType: "all",
    requiresBody: true,
    placeholder: "Search exact OCR text or audio transcript words",
  },
  similar_image: {
    label: "similar_image",
    prefix: "similar_image",
    route: "imageSearch",
    mediaType: "all",
    requiresBody: true,
    placeholder: "Paste a local image path or image URL",
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
  const [results, setResults] = useState<CommandResultItem[]>([]);
  const [skippedFiles, setSkippedFiles] = useState<SkippedFileItem[]>([]);

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
      setResults([]);
      setSkippedFiles([]);
      return;
    }

    setStatus("loading");
    setError("");
    setSkippedFiles([]);

    try {
      setInputText(composedInput);

      if (presetConfig.route === "search") {
        const data = await searchFiles(trimmed, 10, "general");
        setMessage(getSearchMessage(data.total, "SLPFS", data.error));
        setResults(data.results);
        setSkippedFiles([]);
        if (data.results.length > 0 && data.results[0].path) {
          setSelectedFile(data.results[0].path);
        }
      } else if (presetConfig.route === "multimodal") {
        const data = await searchFiles(trimmed, 10, "multimodal", {
          mediaType: presetConfig.mediaType ?? "all",
        });
        setMessage(getSearchMessage(data.total, "multimodal", data.error));
        setResults(data.results);
        setSkippedFiles([]);
        if (data.results.length > 0 && data.results[0].path) {
          setSelectedFile(data.results[0].path);
        }
      } else if (presetConfig.route === "keyword") {
        const data = await searchFiles(trimmed, 10, "keyword", {
          mediaType: presetConfig.mediaType ?? "all",
        });
        setMessage(getSearchMessage(data.total, "keyword", data.error));
        setResults(data.results);
        setSkippedFiles([]);
        if (data.results.length > 0 && data.results[0].path) {
          setSelectedFile(data.results[0].path);
        }
      } else if (presetConfig.route === "imageSearch") {
        const data = await searchByImage(trimmed, 10, {
          mediaType: presetConfig.mediaType ?? "all",
        });
        setMessage(getSearchMessage(data.total, "similar image", data.error));
        setResults(data.results);
        setSkippedFiles([]);
        if (data.results.length > 0 && data.results[0].path) {
          setSelectedFile(data.results[0].path);
        }
      } else if (presetConfig.route === "command") {
        const data = await runCommand(composedInput);
        setMessage(data.message);
        setResults(data.results);
        setSkippedFiles(data.skipped_files ?? []);
        if (data.results.length > 0 && data.results[0].path) {
          setSelectedFile(data.results[0].path);
        }
      } else if (mode === "general") {
        const data = await runCommand(trimmed);
        setMessage(data.message);
        setResults(data.results);
        setSkippedFiles(data.skipped_files ?? []);
        if (data.results.length > 0 && data.results[0].path) {
          setSelectedFile(data.results[0].path);
        }
      } else {
        const data = await searchFiles(trimmed, 10, mode, {
          mediaType: mode === "audio" ? "audio" : "all",
        });
        setMessage(getSearchMessage(data.total, mode, data.error));
        setResults(data.results);
        setSkippedFiles([]);
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
      setResults([]);
      setSkippedFiles([]);
    }
  };

  return (
    <section className="unified-input-panel">
      <div className="unified-input-body">
        
        <div className="chat-thread unified-chat-thread">
          {status === "loading" && (
            <div className="chat-bubble chat-assistant-bubble status-loading">
              <div className="typing-indicator">
                <span></span><span></span><span></span>
              </div>
              <p className="chat-text">Working on it...</p>
            </div>
          )}
          {status === "error" && (
            <div className="chat-bubble error-bubble">
              <p className="chat-text">{error}</p>
            </div>
          )}

          {status === "done" && (
            <>
              <div className="chat-bubble chat-user-bubble">
                <p className="chat-text">{inputText || text}</p>
              </div>

              <div className="chat-bubble chat-assistant-bubble">
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
                      <div className="result-main-row">
                        <span className="unified-result-path" title={item.path}>
                          {item.path.split(/[/\\]/).pop() || item.path}
                        </span>
                        <span className="unified-result-score">
                          {item.media_type ? item.media_type : ""}
                        </span>
                      </div>
                      <div className="unified-result-snippet">{item.snippet || item.path}</div>
                    </button>
                  ))}
                </div>
              )}

              {skippedFiles.length > 0 && (
                <div className="protected-file-list">
                  <div className="protected-file-heading">
                    Protected files found separately
                  </div>
                  {skippedFiles.map((item) => (
                    <div
                      key={`${item.status}:${item.path}`}
                      className="protected-file-item"
                      title={item.path}
                    >
                      <div className="result-main-row">
                        <span className="unified-result-path">
                          {item.file_name || item.relative_path || item.path}
                        </span>
                        <span className="protected-file-status">{item.status}</span>
                      </div>
                      <div className="unified-result-snippet">
                        {item.reason}
                        {item.metadata_indexed ? " Metadata-only search is available." : ""}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>

        <div className="unified-input-controls-bottom">
          <div className="input-bar-container">
            <select 
              className="action-select-subtle" 
              value={preset} 
              onChange={(event) => setPreset(event.target.value as ActionPreset)}
              title="What do you want to do?"
            >
              {ACTION_ORDER.map((value) => (
                <option key={value} value={value}>
                  {value === "auto" ? "Smart Assistant" : ACTION_PRESETS[value].label}
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

            <button className="send-btn" type="button" onClick={() => void handleRun()} disabled={status === "loading"}>
              {status === "loading" ? "..." : "Send"}
            </button>
          </div>
          
          <div className="secondary-controls">
            <span className="routing-hint">
               Search mode:
            </span>
            <select 
              className="mode-select-subtle"
              value={mode} 
              onChange={(event) => setMode(event.target.value as SearchMode)} 
              disabled={!canEditMode}
            >
              <option value="general">Standard (Text)</option>
              <option value="multimodal">Deep AI Search (Images/Content)</option>
              <option value="audio">Audio</option>
              <option value="keyword">OCR/Transcript Keywords</option>
              <option value="auto">Auto-detect</option>
              <option value="hybrid">Best of both</option>
            </select>
          </div>
        </div>

        <SemanticGraph setSelectedFile={setSelectedFile} />

      </div>
    </section>
  );
}
