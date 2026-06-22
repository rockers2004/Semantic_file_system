import { useEffect, useState } from "react";
import { fetchTree, TreeEntry } from "../api/files";

interface FileTreeProps {
  onFileSelect: (path: string, entry?: TreeEntry) => void;
  refreshToken?: number;
  selectedFile?: string;
}

function getFileIcon(name: string, is_dir: boolean, isOpen: boolean, isProtected = false) {
  if (is_dir) {
    return isOpen ? (
      <svg className="neo-icon neo-folder-icon" viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M2.25 18a2.25 2.25 0 0 0 2.25 2.25h15A2.25 2.25 0 0 0 21.75 18V9.75a2.25 2.25 0 0 0-2.25-2.25h-5.38l-1.72-2.58A2.25 2.25 0 0 0 10.53 4.5H4.5A2.25 2.25 0 0 0 2.25 6.75v11.25z"/></svg>
    ) : (
      <svg className="neo-icon neo-folder-icon" viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M4.5 4.5h6l1.72 2.58a2.25 2.25 0 0 0 1.87.92h5.41A2.25 2.25 0 0 1 21.75 10.25v2.5H2.25v-6A2.25 2.25 0 0 1 4.5 4.5ZM21.75 18v-3.75H2.25V18A2.25 2.25 0 0 0 4.5 20.25h15A2.25 2.25 0 0 0 21.75 18Z"/></svg>
    );
  }

  const ext = name.split('.').pop()?.toLowerCase();

  if (isProtected) {
    return <svg className="neo-icon neo-file-icon neo-ext-protected" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>;
  }
  
  if (ext === 'js' || ext === 'jsx' || ext === 'ts' || ext === 'tsx' || ext === 'py' || ext === 'json' || ext === 'rs') {
    return <svg className={`neo-icon neo-file-icon neo-ext-code`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m18 16 4-4-4-4"/><path d="m6 8-4 4 4 4"/><path d="m14.5 4-5 16"/></svg>;
  }
  if (ext === 'png' || ext === 'jpg' || ext === 'jpeg' || ext === 'svg' || ext === 'gif') {
    return <svg className={`neo-icon neo-file-icon neo-ext-image`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/></svg>;
  }
  if (ext === 'md' || ext === 'txt' || ext === 'csv' || ext === 'log') {
    return <svg className={`neo-icon neo-file-icon neo-ext-text`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><line x1="16" x2="8" y1="13" y2="13"/><line x1="16" x2="8" y1="17" y2="17"/><line x1="10" x2="8" y1="9" y2="9"/></svg>;
  }

  return <svg className="neo-icon neo-file-icon neo-ext-generic" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/></svg>;
}

export function FileTree({ onFileSelect, refreshToken = 0, selectedFile }: FileTreeProps) {
  const [rootPath, setRootPath] = useState<string>("");
  const [rootEntries, setRootEntries] = useState<TreeEntry[]>([]);
  const [useSemantic, setUseSemantic] = useState<boolean>(false);
  const [childrenByPath, setChildrenByPath] = useState<Record<string, TreeEntry[]>>({});
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string>("");

  const loadRoot = async (semanticOverride?: boolean) => {
    setError("");
    setRootPath("");
    setExpanded({});
    setChildrenByPath({});
    setLoading({});
    setRootEntries([]);

    try {
      const data = await fetchTree(undefined, typeof semanticOverride === 'boolean' ? semanticOverride : useSemantic);
      setRootPath(data.path);
      setRootEntries(data.entries);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load file tree");
    }
  };

  useEffect(() => {
    void loadRoot();
  }, [refreshToken, useSemantic]);

  const toggleDirectory = async (entry: TreeEntry) => {
    if (!entry.is_dir) {
      onFileSelect(entry.path, entry);
      return;
    }

    const isExpanded = !!expanded[entry.path];
    setExpanded((prev) => ({ ...prev, [entry.path]: !isExpanded }));

    if (!isExpanded && !childrenByPath[entry.path]) {
      setLoading((prev) => ({ ...prev, [entry.path]: true }));
      try {
        const data = await fetchTree(entry.path, useSemantic);
        setChildrenByPath((prev) => ({ ...prev, [entry.path]: data.entries }));
      } catch (err) {
        // Soft error for tree expansion
        console.error("Failed to expand directory", err);
      } finally {
        setLoading((prev) => ({ ...prev, [entry.path]: false }));
      }
    }
  };

  const renderEntries = (entries: TreeEntry[], level = 0) => {
    // Group entries by selected category kind
    const groupKey = (entry: TreeEntry) => {
      // If semantic mode, prefer backend-provided category
      if (useSemantic && entry.category) return entry.category;
      // Otherwise default grouping by extension/type
      const name = entry.name || '';
      const ext = name.includes('.') ? name.substring(name.lastIndexOf('.')).toLowerCase() : '';
      if (entry.is_protected) return 'Protected';
      if (['.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.c', '.cpp', '.h', '.cs', '.go', '.rs', '.php', '.rb', '.swift', '.kt', '.scala', '.sh', '.ps1', '.sql'].includes(ext)) return 'Code';
      if (['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.svg', '.heic'].includes(ext)) return 'Images';
      if (['.mp4', '.mkv', '.avi', '.mov', '.webm', '.m4v', '.ogg'].includes(ext)) return 'Videos';
      if (['.mp3', '.wav', '.aac', '.flac', '.m4a', '.ogg'].includes(ext)) return 'Audio';
      if (['.zip', '.rar', '.7z', '.tar', '.gz'].includes(ext)) return 'Archives';
      if (['.csv', '.tsv', '.json', '.xml', '.db', '.sqlite', '.sqlite3', '.parquet'].includes(ext)) return 'Data';
      if (['.ppt', '.pptx', '.key', '.odp'].includes(ext)) return 'Presentations';
      if (['.xls', '.xlsx', '.ods'].includes(ext)) return 'Spreadsheets';
      if (['.pdf', '.doc', '.docx', '.txt', '.md', '.rtf', '.odt', '.pages'].includes(ext)) return 'Documents';
      return 'Other';
    };

    const grouped: Record<string, TreeEntry[]> = {};
    for (const e of entries) {
      const k = groupKey(e) || 'Other';
      if (!grouped[k]) grouped[k] = [];
      grouped[k].push(e);
    }

    const sortedGroups = Object.keys(grouped).sort((a, b) => a.localeCompare(b));

    return (
      <div className="neo-tree-level">
        {sortedGroups.map((grp) => (
          <div key={grp} className="neo-group">
            <div className="neo-group-header">{grp} ({grouped[grp].length})</div>
            {grouped[grp].map((entry) => {
              const isOpen = !!expanded[entry.path];
              const children = childrenByPath[entry.path] || [];
              const isLoading = !!loading[entry.path];
              const isExactSelected = selectedFile === entry.path;

              return (
                <div key={entry.path} className="neo-item-wrapper">
                  <button
                    className={`neo-tree-item ${entry.is_dir ? 'neo-dir' : 'neo-file'} ${entry.is_protected ? 'neo-protected' : ''} ${isExactSelected ? 'neo-selected' : ''}`}
                    style={{ paddingLeft: `${(entry.is_dir ? 0 : 8) + 8}px` }}
                    onClick={() => void toggleDirectory(entry)}
                    type="button"
                    title={entry.security_reason || entry.path}
                  >
                    <div className="neo-item-content">
                      {entry.is_dir ? (
                        <svg className={`neo-chevron ${isOpen ? 'neo-chevron-open' : ''}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m9 18 6-6-6-6"/></svg>
                      ) : (
                        <span className="neo-chevron-spacer" />
                      )}
                      {getFileIcon(entry.name, entry.is_dir, isOpen, !!entry.is_protected)}
                      <span className={`neo-name ${entry.is_dir ? 'neo-dir-name' : 'neo-file-name'}`}>{entry.name}</span>
                      {entry.is_protected && <span className="neo-protected-badge">Protected</span>}
                      {entry.category && !entry.is_dir && useSemantic && (
                        (() => {
                          const safeCat = (entry.category || '').toString().replace(/\s+/g, '-').toLowerCase();
                          const className = `neo-category-badge ${safeCat ? `neo-category-${safeCat}` : ''}`;
                          return (
                            <span className={className} title={entry.category_reason ?? ''} data-cat={entry.category}>{entry.category}</span>
                          );
                        })()
                      )}
                    </div>
                  </button>

                  <div className={`neo-children-container ${isOpen ? 'neo-open' : 'neo-closed'}`}>
                    {entry.is_dir && isOpen && isLoading && (
                      <div className="neo-tree-loading" style={{ paddingLeft: `${(level + 1) * 16 + 8 + 24}px` }}>
                        <div className="neo-loading-spinner" /> Loading...
                      </div>
                    )}
                    {entry.is_dir && isOpen && children.length > 0 && renderEntries(children, level + 1)}
                  </div>
                </div>
              );
            })}
          </div>
        ))}
      </div>
    );
  };

  return (
    <section className="neo-file-tree-panel">
      <div className="neo-tree-header">
        <div style={{display: 'flex', alignItems: 'center', gap: '12px'}}>
          <h3 style={{margin: 0}}>Explorer</h3>
          <label style={{fontSize: '12px', color: 'var(--text-dim)', display: 'flex', alignItems: 'center', gap: '6px'}}>
            <input
              type="checkbox"
              checked={useSemantic}
              onChange={(e) => {
                const newVal = e.target.checked;
                setUseSemantic(newVal);
                // Load immediately with the new value to avoid race with state update
                void loadRoot(newVal);
              }}
            />
            Semantic categories
          </label>
        </div>
      </div>
      {error && (
        <div className="file-tree-error">
          <p>{error}</p>
          <button type="button" className="btn-confirm" onClick={() => void loadRoot()}>
            Retry
          </button>
        </div>
      )}
      <div className="neo-file-tree-list">
        {rootEntries.length > 0 ? renderEntries(rootEntries) : (
           <div className="neo-tree-empty-state">
              {rootPath ? "Directory is empty." : "No folder opened."}
           </div>
        )}
      </div>
    </section>
  );
}
