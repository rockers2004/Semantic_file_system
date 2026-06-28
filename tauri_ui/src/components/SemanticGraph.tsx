import { useMemo, useState } from "react";
import { fetchMultimodalGraph, GraphLink, GraphNode } from "../api/files";

interface SemanticGraphProps {
  setSelectedFile: (path: string) => void;
}

type GraphStatus = "idle" | "loading" | "error" | "ready";

function resolveLinkId(endpoint: GraphLink["source"] | GraphLink["target"]): string {
  return String(endpoint);
}

export function SemanticGraph({ setSelectedFile }: SemanticGraphProps) {
  const [status, setStatus] = useState<GraphStatus>("idle");
  const [error, setError] = useState("");
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [links, setLinks] = useState<GraphLink[]>([]);

  const positionedNodes = useMemo(() => {
    const width = 760;
    const height = 320;
    const radius = Math.min(width, height) * 0.38;
    const cx = width / 2;
    const cy = height / 2;

    return nodes.slice(0, 80).map((node, index, visibleNodes) => {
      const angle = (Math.PI * 2 * index) / Math.max(1, visibleNodes.length);
      return {
        ...node,
        x: cx + Math.cos(angle) * radius,
        y: cy + Math.sin(angle) * radius,
      };
    });
  }, [nodes]);

  const nodeById = useMemo(() => {
    return new Map(positionedNodes.map((node) => [node.id, node]));
  }, [positionedNodes]);

  const visibleLinks = links
    .map((link) => {
      const source = nodeById.get(resolveLinkId(link.source));
      const target = nodeById.get(resolveLinkId(link.target));
      return source && target ? { ...link, sourceNode: source, targetNode: target } : null;
    })
    .filter((link): link is NonNullable<typeof link> => Boolean(link))
    .slice(0, 160);

  const loadGraph = async () => {
    setStatus("loading");
    setError("");
    try {
      const graph = await fetchMultimodalGraph();
      setNodes(graph.nodes ?? []);
      setLinks(graph.links ?? []);
      setStatus("ready");
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : "Failed to load graph");
    }
  };

  return (
    <section className="semantic-graph-panel">
      <div className="semantic-graph-header">
        <div>
          <h3>File Relations</h3>
          <p>{nodes.length} nodes, {links.length} links</p>
        </div>
        <button type="button" className="graph-load-btn" onClick={() => void loadGraph()} disabled={status === "loading"}>
          {status === "loading" ? "Loading..." : "Load Graph"}
        </button>
      </div>

      {status === "error" && <p className="graph-error">{error}</p>}

      <div className="graph-canvas-wrap">
        {status === "idle" && <p className="graph-placeholder">Load indexed visual relations.</p>}
        {status === "ready" && positionedNodes.length === 0 && <p className="graph-placeholder">No graph data yet.</p>}
        {positionedNodes.length > 0 && (
          <svg className="semantic-graph-svg" viewBox="0 0 760 320" role="img" aria-label="Semantic file relation graph">
            {visibleLinks.map((link, index) => (
              <line
                key={`${resolveLinkId(link.source)}:${resolveLinkId(link.target)}:${index}`}
                x1={link.sourceNode.x}
                y1={link.sourceNode.y}
                x2={link.targetNode.x}
                y2={link.targetNode.y}
                strokeWidth={Math.max(1, Math.min(4, link.value * 4))}
              />
            ))}
            {positionedNodes.map((node) => (
              <g key={node.id} className="graph-node" onClick={() => setSelectedFile(node.path)}>
                <circle cx={node.x} cy={node.y} r={node.type === "video" ? 8 : 6} />
                <text x={node.x + 10} y={node.y + 4}>
                  {(node.fileName || node.path.split(/[/\\]/).pop() || "file").slice(0, 24)}
                </text>
              </g>
            ))}
          </svg>
        )}
      </div>
    </section>
  );
}
