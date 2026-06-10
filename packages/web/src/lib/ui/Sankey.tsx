import { useEffect, useMemo, useRef, useState } from "react";
import { euroCompact, euroFull } from "../format";
import { levelMeta } from "../levels";
import type { SankeyLink } from "../flows";

/** A link after layout — carries its stroke width + vertical endpoints. */
interface LaidOutLink extends SankeyLink {
  sw: number;
  sy0: number;
  ty0: number;
}

interface LaidOutNode {
  id: string;
  col: number;
  label: string;
  level: string | null;
  value: number;
  x: number;
  y: number;
  w: number;
  h: number;
  sourceLinks: LaidOutLink[];
  targetLinks: LaidOutLink[];
}

export interface SankeyLayout {
  nodes: LaidOutNode[];
  links: LaidOutLink[];
  nodeById: Map<string, LaidOutNode>;
  nodeW: number;
}

const NODE_W = 16;
const GAP = 14;

/**
 * Hand-rolled Sankey layout (ported from `design/js/sankey.jsx`): derive nodes + columns from the
 * links, size each node by `max(inflow, outflow)`, stack columns top-down by value, then assign each
 * link a vertical offset. Pure and deterministic — unit-tested.
 */
export function computeSankey(
  links: SankeyLink[],
  width: number,
  height: number,
  pad: number,
): SankeyLayout {
  const nodeById = new Map<string, LaidOutNode>();
  const getNode = (id: string, col: number, label: string, level: string | null): LaidOutNode => {
    let node = nodeById.get(id);
    if (!node) {
      node = {
        id,
        col,
        label,
        level,
        value: 0,
        x: 0,
        y: 0,
        w: NODE_W,
        h: 0,
        sourceLinks: [],
        targetLinks: [],
      };
      nodeById.set(id, node);
    }
    node.col = col;
    return node;
  };

  const laidOut = links.map((l) => ({ ...l }) as LaidOutLink);
  for (const link of laidOut) {
    const source = getNode(link.source, link.sourceCol, link.sourceLabel, link.sourceLevel);
    const target = getNode(link.target, link.targetCol, link.targetLabel, link.targetLevel);
    source.sourceLinks.push(link);
    target.targetLinks.push(link);
  }

  const nodes = [...nodeById.values()];
  for (const node of nodes) {
    const out = node.sourceLinks.reduce((s, l) => s + l.value, 0);
    const inc = node.targetLinks.reduce((s, l) => s + l.value, 0);
    node.value = Math.max(out, inc);
  }

  const cols = [...new Set(nodes.map((n) => n.col))].sort((a, b) => a - b);
  const colX = new Map<number, number>();
  cols.forEach((c, i) => {
    colX.set(c, pad + (i * (width - pad * 2 - NODE_W)) / (cols.length - 1 || 1));
  });

  for (const c of cols) {
    const colNodes = nodes.filter((n) => n.col === c).sort((a, b) => b.value - a.value);
    const totalByCol = colNodes.reduce((s, n) => s + n.value, 0);
    const totalGap = GAP * (colNodes.length - 1);
    const scale = (height - pad * 2 - totalGap) / (totalByCol || 1);
    let y = pad;
    for (const node of colNodes) {
      node.x = colX.get(c) ?? pad;
      node.w = NODE_W;
      node.h = Math.max(3, node.value * scale);
      node.y = y;
      y += node.h + GAP;
    }
  }

  for (const node of nodes) {
    node.sourceLinks.sort(
      (a, b) => (nodeById.get(a.target)?.y ?? 0) - (nodeById.get(b.target)?.y ?? 0),
    );
    let sy = node.y;
    for (const link of node.sourceLinks) {
      link.sw = (node.h / (node.value || 1)) * link.value;
      link.sy0 = sy + link.sw / 2;
      sy += link.sw;
    }
    node.targetLinks.sort(
      (a, b) => (nodeById.get(a.source)?.y ?? 0) - (nodeById.get(b.source)?.y ?? 0),
    );
    let ty = node.y;
    for (const link of node.targetLinks) {
      link.ty0 = ty + ((node.h / (node.value || 1)) * link.value) / 2;
      ty += (node.h / (node.value || 1)) * link.value;
    }
  }

  return { nodes, links: laidOut, nodeById, nodeW: NODE_W };
}

const COL_TITLES = ["Financeur public", "Opérateur", "Titulaire / délégataire"];
const LINK_COLOR: Record<string, string> = {
  delegates: "#e69f00",
  participation: "#009e73",
  funds: "#0072b2",
};

const DEFAULT_ARIA_LABEL =
  "Diagramme de flux de financement (Sankey). Un équivalent tabulaire est fourni ci-dessous.";

export interface SankeyProps {
  links: SankeyLink[];
  height?: number;
  /**
   * Accessible label for the diagram. Defaults to a label that promises an accompanying tabular
   * equivalent — override it (e.g. for a decorative teaser without a table) so the promise holds.
   */
  ariaLabel?: string;
}

/**
 * Sankey flow diagram (SVG). Responsive to its container width; hover dims the other flows. When the
 * default label is used a tabular equivalent must accompany it for accessibility.
 */
export function Sankey({ links, height = 460, ariaLabel = DEFAULT_ARIA_LABEL }: SankeyProps) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(900);
  const [hover, setHover] = useState<string | null>(null);

  useEffect(() => {
    const element = wrapRef.current;
    if (!element || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver((entries) => setWidth(entries[0].contentRect.width));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const layout = useMemo(() => computeSankey(links, width, height, 28), [links, width, height]);
  const { nodes, nodeById } = layout;
  const maxCol = nodes.length ? Math.max(...nodes.map((n) => n.col)) : 0;

  const ribbon = (link: LaidOutLink): string => {
    const s = nodeById.get(link.source);
    const t = nodeById.get(link.target);
    if (!s || !t) return "";
    const x0 = s.x + s.w;
    const x1 = t.x;
    const xm = (x0 + x1) / 2;
    return `M${x0},${link.sy0} C${xm},${link.sy0} ${xm},${link.ty0} ${x1},${link.ty0}`;
  };

  return (
    <div ref={wrapRef} style={{ width: "100%" }}>
      <svg width={width} height={height} role="img" aria-label={ariaLabel}>
        {[...new Set(nodes.map((n) => n.col))]
          .sort((a, b) => a - b)
          .map((col, i) => {
            const colNodes = nodes.filter((n) => n.col === col);
            const x = colNodes[0] ? colNodes[0].x + colNodes[0].w / 2 : 0;
            return (
              <text
                key={col}
                x={x}
                y={14}
                className="sankey-node-sub"
                textAnchor="middle"
                style={{ fontWeight: 700, fill: "#666" }}
              >
                {COL_TITLES[i]}
              </text>
            );
          })}
        {layout.links.map((link, i) => {
          const active = hover == null || hover === link.source || hover === link.target;
          return (
            <path
              key={`${link.source}-${link.target}-${i}`}
              className="sankey-link"
              d={ribbon(link)}
              stroke={LINK_COLOR[link.type] ?? LINK_COLOR.funds}
              strokeWidth={Math.max(1, link.sw)}
              strokeOpacity={active ? 0.34 : 0.07}
              onMouseEnter={() => setHover(link.source)}
              onMouseLeave={() => setHover(null)}
            >
              <title>
                {link.sourceLabel} → {link.targetLabel} : {euroFull(link.value)} (
                {link.exercice ?? "exemple"})
              </title>
            </path>
          );
        })}
        {nodes.map((node) => {
          const meta = levelMeta(node.level);
          const right = node.col === maxCol;
          const label = node.label.length > 30 ? `${node.label.slice(0, 28)}…` : node.label;
          return (
            <g
              key={node.id}
              onMouseEnter={() => setHover(node.id)}
              onMouseLeave={() => setHover(null)}
            >
              <rect
                x={node.x}
                y={node.y}
                width={node.w}
                height={node.h}
                rx="2"
                fill={node.level ? meta.color : "#888"}
                opacity={hover == null || hover === node.id ? 1 : 0.5}
              />
              <text
                x={right ? node.x - 6 : node.x + node.w + 6}
                y={node.y + node.h / 2 - 4}
                className="sankey-node-label"
                textAnchor={right ? "end" : "start"}
                dominantBaseline="middle"
              >
                {label}
              </text>
              <text
                x={right ? node.x - 6 : node.x + node.w + 6}
                y={node.y + node.h / 2 + 9}
                className="sankey-node-sub"
                textAnchor={right ? "end" : "start"}
                dominantBaseline="middle"
              >
                {euroCompact(node.value)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
