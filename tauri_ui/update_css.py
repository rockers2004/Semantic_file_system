import re
import os

css_path = os.path.join('d:\\\\', 'project', 'semantic file system instant search', 'Semantic_file_system', 'tauri_ui', 'src', 'App.css')
with open(css_path, 'r', encoding='utf-8') as f:
    content = f.read()

css_additions = """
/* Layout updates for split content */
.main-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}

.main-header-titles {
  flex: 1;
  text-align: left;
}

.main-header-titles h1 {
  font-size: 28px;
  font-weight: 600;
  margin: 0 0 8px 0;
}

.main-header-titles p {
  color: var(--text-dim);
  font-size: 15px;
  margin: 0;
}

.preview-toggle {
  margin-top: 4px;
  color: var(--text-dim);
  transition: color 0.2s;
}

.preview-toggle:hover {
  color: var(--accent);
}

.content-split-area {
  display: flex;
  gap: 24px;
  flex: 1;
  min-height: 0; /* needed for flex scrolling */
  width: 100%;
}

.search-arena {
  width: 100%;
  max-width: 800px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  transition: max-width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.search-arena.with-preview {
  max-width: 50%;
  margin: 0;
}

/* Reduced Unified Input size nicely */
.unified-input-panel {
  padding: 16px;
  border-radius: var(--radius-sm);
}

.preview-arena {
  width: 50%;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  animation: slideIn 0.3s cubic-bezier(0.4, 0, 0.2, 1) forwards;
}

.file-preview-panel {
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 20px;
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
  box-shadow: var(--shadow-sm);
}

@keyframes slideIn {
  from { opacity: 0; transform: translateX(20px); }
  to { opacity: 1; transform: translateX(0); }
}
"""

content = re.sub(r'\n\.main-header\s+\{[^\}]*\}', '', content, flags=re.DOTALL)
content = re.sub(r'\n\.main-header h1\s+\{[^\}]*\}', '', content, flags=re.DOTALL)
content = re.sub(r'\n\.main-header p\s+\{[^\}]*\}', '', content, flags=re.DOTALL)
content = re.sub(r'\n\.search-arena\s+\{[^\}]*\}', '', content, flags=re.DOTALL)
content = re.sub(r'\n\.unified-input-panel\s+\{[^\}]*\}', '', content, flags=re.DOTALL)
content = re.sub(r'\n\.preview-arena\s+\{[^\}]*\}', '', content, flags=re.DOTALL)
content = re.sub(r'\n\.file-preview-panel\s+\{[^\}]*\}', '', content, flags=re.DOTALL)

with open(css_path, 'w', encoding='utf-8') as f:
    f.write(content + "\n" + css_additions)
