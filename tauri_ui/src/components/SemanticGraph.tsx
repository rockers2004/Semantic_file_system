import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchMultimodalGraph, GraphLink, GraphNode, GraphLink as GraphLinkT } from "../api/files";

interface SemanticGraphProps {
  setSelectedFile: (path: string) => void;
}

type GraphStatus = "idle" | "loading" | "error" | "ready";

interface PositionedNode extends GraphNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
}

interface LinkWithCoords extends GraphLinkT {
  sourceNode: PositionedNode;
  targetNode: PositionedNode;
}

const WIDTH = 800;
const HEIGHT = 500;

function resolveLinkId(endpoint: GraphLink["source"] | GraphLink["target"]): string {
  return String(endpoint);
}

function runForceLayout(nodes: GraphNode[], links: GraphLinkT[]): PositionedNode[] {
  const positioned: Map<string, PositionedNode> = new Map();
  const cx = WIDTH / 2;
  const cy = HEIGHT / 2;

  for (const node of nodes) {
    const angle = Math.random() * Math.PI * 2;
    const radius = 80 + Math.random() * 60;
    positioned.set(node.id, {
      ...node,
      x: cx + Math.cos(angle) * radius,
      y: cy + Math.sin(angle) * radius,
      vx: 0,
      vy: 0,
    });
  }

  const REPULSION = 6000;
  const ATTRACTION = 0.005;
  const DAMPING = 0.85;
  const GRAVITY = 0.01;
  const ITERATIONS = 120;

  for (let iter = 0; iter < ITERATIONS; iter++) {
    const nodesArr = [...positioned.values()];
    const cooling = 1 - iter / ITERATIONS;

    for (let i = 0; i < nodesArr.length; i++) {
      for (let j = i + 1; j < nodesArr.length; j++) {
        const a = nodesArr[i];
        const b = nodesArr[j];
        let dx = a.x - b.x;
        let dy = a.y - b.y;
        let dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = (REPULSION / (dist * dist)) * cooling;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        a.vx += fx;
        a.vy += fy;
        b.vx -= fx;
        b.vy -= fy;
      }
    }

    for (const link of links) {
      const source = positioned.get(resolveLinkId(link.source));
      const target = positioned.get(resolveLinkId(link.target));
      if (!source || !target) continue;
      const dx = target.x - source.x;
      const dy = target.y - source.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const force = ATTRACTION * (dist - 100) * cooling;
      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;
      source.vx += fx;
      source.vy += fy;
      target.vx -= fx;
      target.vy -= fy;
    }

    for (const n of nodesArr) {
      const dx = cx - n.x;
      const dy = cy - n.y;
      n.vx += dx * GRAVITY * cooling;
      n.vy += dy * GRAVITY * cooling;
      n.vx *= DAMPING;
      n.vy *= DAMPING;
      n.x += n.vx;
      n.y += n.vy;
    }
  }

  return [...positioned.values()];
}

export function SemanticGraph({ setSelectedFile }: SemanticGraphProps) {
  const [status, setStatus] = useState<GraphStatus>("idle");
  const [error, setError] = useState("");
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [links, setLinks] = useState<GraphLinkT[]>([]);

  const [transform, setTransform] = useState({ x: 0, y: 0, k: 1 });

  const svgRef = useRef<SVGSVGElement>(null);
  const panning = useRef(false);
  const panStart = useRef({ x: 0, y: 0 });
  const transformRef = useRef(transform);
  transformRef.current = transform;

  const positionedNodes = useMemo(() => {
    if (nodes.length === 0) return [];
    return runForceLayout(nodes, links);
  }, [nodes, links]);

  const nodeMap = useMemo(() => new Map(positionedNodes.map((n) => [n.id, n])), [positionedNodes]);

  const visibleLinks = useMemo(() => {
    return links
      .map((link) => {
        const source = nodeMap.get(resolveLinkId(link.source));
        const target = nodeMap.get(resolveLinkId(link.target));
        if (!source || !target) return null;
        return { ...link, sourceNode: source, targetNode: target } as LinkWithCoords;
      })
      .filter((l): l is LinkWithCoords => Boolean(l));
  }, [links, nodeMap]);

  const loadGraph = useCallback(async () => {
    setStatus("loading");
    setError("");
    try {
      const graph = await fetchMultimodalGraph();
      setNodes(graph.nodes ?? []);
      setLinks(graph.links ?? []);
      setStatus("ready");
      setTransform({ x: 0, y: 0, k: 1 });
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : "Failed to load graph");
    }
  }, []);

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const delta = -e.deltaY * 0.001;
    const newK = Math.max(0.2, Math.min(5, transformRef.current.k * (1 + delta)));
    const ratio = newK / transformRef.current.k;
    setTransform((prev) => ({
      x: mx - (mx - prev.x) * ratio,
      y: my - (my - prev.y) * ratio,
      k: newK,
    }));
  }, []);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if ((e.target as Element).closest(".graph-node")) return;
    panning.current = true;
    panStart.current = { x: e.clientX - transformRef.current.x, y: e.clientY - transformRef.current.y };
  }, []);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!panning.current) return;
    setTransform((prev) => ({
      ...prev,
      x: e.clientX - panStart.current.x,
      y: e.clientY - panStart.current.y,
    }));
  }, []);

  const handleMouseUp = useCallback(() => {
    panning.current = false;
  }, []);

  useEffect(() => {
    const handleGlobalUp = () => { panning.current = false; };
    window.addEventListener("mouseup", handleGlobalUp);
    return () => window.removeEventListener("mouseup", handleGlobalUp);
  }, []);

  const handleNodeClick = useCallback((path: string) => {
    setSelectedFile(path);
  }, [setSelectedFile]);

  return (
    <section className="semantic-graph-panel">
      <div className="semantic-graph-header">
        <div>
          <h3>File Relations</h3>
          <p>{nodes.length} nodes, {links.length} links &middot; scroll to zoom, drag to pan</p>
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
          <svg
            ref={svgRef}
            className="semantic-graph-svg"
            viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
            role="img"
            aria-label="Semantic file relation graph"
            onWheel={handleWheel}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            style={{ cursor: panning.current ? "grabbing" : "grab" }}
          >
            <g transform={`translate(${transform.x},${transform.y}) scale(${transform.k})`}>
              {visibleLinks.map((link, index) => (
                <line
                  key={`${resolveLinkId(link.source)}:${resolveLinkId(link.target)}:${index}`}
                  x1={link.sourceNode.x}
                  y1={link.sourceNode.y}
                  x2={link.targetNode.x}
                  y2={link.targetNode.y}
                  strokeWidth={Math.max(0.5, Math.min(3, (link.value || 1) * 2))}
                />
              ))}
              {positionedNodes.map((node) => (
                <g key={node.id} className="graph-node" onClick={() => handleNodeClick(node.path)} style={{ cursor: "pointer" }}>
                  <circle cx={node.x} cy={node.y} r={node.type === "video" ? 7 : 5} />
                  <text x={node.x + 9} y={node.y + 3}>
                    {(node.fileName || node.path.split(/[/\\]/).pop() || "file").slice(0, 22)}
                  </text>
                </g>
              ))}
            </g>
          </svg>
        )}
      </div>
    </section>
  );
}
