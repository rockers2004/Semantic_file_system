import { useEffect, useState } from "react";
import { fetchTree, TreeEntry } from "../api/files";

interface FileTreeProps {
  onFileSelect: (path: string) => void;
}

export function FileTree({ onFileSelect }: FileTreeProps) {
  const [rootPath, setRootPath] = useState<string>("");
  const [rootEntries, setRootEntries] = useState<TreeEntry[]>([]);
  const [childrenByPath, setChildrenByPath] = useState<Record<string, TreeEntry[]>>({});
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string>("");

  useEffect(() => {
    const loadRoot = async () => {
      try {
        const data = await fetchTree();
        setRootPath(data.path);
        setRootEntries(data.entries);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load file tree");
      }
    };

    loadRoot();
  }, []);

  const toggleDirectory = async (entry: TreeEntry) => {
    if (!entry.is_dir) {
      onFileSelect(entry.path);
      return;
    }

    const isExpanded = !!expanded[entry.path];
    setExpanded((prev) => ({ ...prev, [entry.path]: !isExpanded }));

    if (!isExpanded && !childrenByPath[entry.path]) {
      setLoading((prev) => ({ ...prev, [entry.path]: true }));
      try {
        const data = await fetchTree(entry.path);
        setChildrenByPath((prev) => ({ ...prev, [entry.path]: data.entries }));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to expand directory");
      } finally {
        setLoading((prev) => ({ ...prev, [entry.path]: false }));
      }
    }
  };

  const renderEntries = (entries: TreeEntry[], level = 0) => {
    return entries.map((entry) => {
      const isOpen = !!expanded[entry.path];
      const children = childrenByPath[entry.path] || [];
      const isLoading = !!loading[entry.path];

      return (
        <div key={entry.path}>
          <button
            className="tree-item"
            style={{ paddingLeft: `${level * 14 + 8}px` }}
            onClick={() => void toggleDirectory(entry)}
            type="button"
          >
            <span className="tree-icon">{entry.is_dir ? (isOpen ? "▾" : "▸") : "•"}</span>
            <span>{entry.name}</span>
          </button>

          {entry.is_dir && isOpen && isLoading && (
            <div className="tree-loading" style={{ paddingLeft: `${(level + 1) * 14 + 8}px` }}>
              Loading...
            </div>
          )}

          {entry.is_dir && isOpen && children.length > 0 && renderEntries(children, level + 1)}
        </div>
      );
    });
  };

  return (
    <section className="file-tree-panel">
      <h3>Files</h3>
      <p className="file-tree-root">{rootPath || "Loading root..."}</p>
      {error && <p className="file-tree-error">{error}</p>}
      <div className="file-tree-list">{renderEntries(rootEntries)}</div>
    </section>
  );
}
