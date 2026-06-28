export type PreviewTabId = "overview" | "content" | "graph" | "info";

const TABS: { id: PreviewTabId; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "content", label: "Content" },
  { id: "graph", label: "Graph" },
  { id: "info", label: "Info" },
];

interface PreviewTabsProps {
  activeTab: PreviewTabId;
  onTabChange: (tab: PreviewTabId) => void;
}

export function PreviewTabs({ activeTab, onTabChange }: PreviewTabsProps) {
  return (
    <div className="preview-tabs">
      {TABS.map((t) => (
        <button
          key={t.id}
          type="button"
          className={`preview-tab ${activeTab === t.id ? "active" : ""}`}
          onClick={() => onTabChange(t.id)}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
