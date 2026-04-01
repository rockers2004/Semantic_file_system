import { useState } from "react";
import { searchFiles, SearchResult } from "../api/files";

interface SearchPanelProps {
    setSelectedFile: (path: string) => void;
}

type SearchStatus = "idle" | "loading" | "error" | "results";

export function SearchPanel({ setSelectedFile }: SearchPanelProps) {
    const [query, setQuery] = useState("");
    const [k, setK] = useState(10);
    const [status, setStatus] = useState<SearchStatus>("idle");
    const [results, setResults] = useState<SearchResult[]>([]);
    const [error, setError] = useState("");
    const [total, setTotal] = useState(0);

    const runSearch = async () => {
        const trimmed = query.trim();
        if (!trimmed) {
            setStatus("error");
            setError("Please enter a search query.");
            setResults([]);
            setTotal(0);
            return;
        }

        setStatus("loading");
        setError("");

        try {
            const data = await searchFiles(trimmed, k, "normal");
            setResults(data.results);
            setTotal(data.total);
            setStatus("results");
        } catch (err) {
            setStatus("error");
            setError(err instanceof Error ? err.message: "Search failed");
            setResults([]);
            setTotal(0);
        }
    };

    return (
        <section className = "search-panel">
            <h3>Search</h3>
            <div className = "search-controls">
                <input 
                    type = "text"
                    value = {query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Search files of content..."
                    onKeyDown={(e) => {
                        if(e.key === "Enter") {
                            void runSearch();
                        }
                    }}
                />
                <select value={k} onChange={(e) => setK(Number(e.target.value))}>
                    <option value={5}>5</option>
                    <option value={10}>10</option>
                    <option value={20}>20</option>
                    <option value={50}>50</option>
                </select>
                <button type="button" onClick={() => void runSearch()}disabled={status === "loading"}>
                    {status === "loading" ? "Searching..." : "Search"}
                </button>
            </div>
            {status === "idle" && <p className="search-hint">Type a query and press Search.</p>}
            {status === "error" && <p className="search-error">{error}</p>}

            {status === "results" && (
                <div className="search-results">
                <p className="search-total">Total: {total}</p>
                {results.length === 0 && <p className="search-hint">No matches found.</p>}
                {results.map((item) => (
                    <button
                    key={item.path}
                    type="button"
                    className="search-result-item"
                    onClick={() => setSelectedFile(item.path)}
                    >
                    <div className="search-result-path">{item.path}</div>
                    <div className="search-result-meta">score: {item.score.toFixed(2)}</div>
                    <div className="search-result-snippet">{item.snippet || "No snippet"}</div>
                    </button>
                ))}
                </div>
            )}
        </section>
    );

}