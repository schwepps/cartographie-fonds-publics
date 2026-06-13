import { useEffect, useMemo, useRef, useState } from "react";
import { euroCompact } from "../../lib/format";
import { levelMeta, MENTION_COLOR } from "../../lib/levels";
import { radiusForCp } from "../../lib/magnitude";
import {
  buildAdjacency,
  computeExpandable,
  computeVisible,
  type GraphEdge,
  type GraphFilters,
  type GraphModel,
  type GraphNode,
} from "./graph-model";

export type { GraphFilters };

export interface GraphApi {
  zoomIn: () => void;
  zoomOut: () => void;
  fit: () => void;
}

const EDGE_STYLE: Record<string, { color: string; dash: number[] | null; base: number }> = {
  tutelle: { color: "#7a7a86", dash: null, base: 1.2 },
  funds: { color: "#0072b2", dash: null, base: 1.4 },
  participation: { color: "#1f8a5b", dash: null, base: 1.2 },
  delegates: { color: "#cf7a00", dash: [5, 4], base: 1.2 },
};

const radiusFor = (n: GraphNode) => radiusForCp(n.cp);

// Per-frame wall-clock budget (ms) for the reduced-motion fast-settle (see frame()): we step the
// layout until it is calm or this budget is spent, so it converges in a frame or two regardless of
// graph size — never a long main-thread freeze, never a multi-second incremental drift.
const SETTLE_MS = 12;

interface SimState {
  scale: number;
  tx: number;
  ty: number;
  w: number;
  h: number;
  dpr: number;
  dragging: GraphNode | null;
  hovering: string | null;
  panning: boolean;
  lastX: number;
  lastY: number;
  downAt: { x: number; y: number };
  moved: boolean;
  alpha: number;
  raf: number;
  placed: boolean;
  clusterPos: Record<string, { x: number; y: number }>;
  cx: number;
  cy: number;
  visibleNodes: GraphNode[];
  visibleEdges: GraphEdge[];
  expandableSet: Set<string>;
  focus: string | null;
  focusNeighbours: Set<string>;
  onFocus: (s: string | null) => void;
  onExpand: (s: string) => void;
  onOpenSheet: (s: string) => void;
  kick: () => void;
  zoomAt: (sx: number, sy: number, factor: number) => void;
  fitView: () => void;
  fitTimer: ReturnType<typeof setTimeout>;
}

export interface GraphCanvasProps {
  model: GraphModel;
  filters: GraphFilters;
  expanded: Set<string>;
  focus: string | null;
  onFocus: (siren: string | null) => void;
  onExpand: (siren: string) => void;
  onOpenSheet: (siren: string) => void;
  onCounts: (counts: { shown: number; total: number }) => void;
  locate: string | null;
  resetSignal: number;
  reduceMotion: boolean;
  apiRef: React.RefObject<GraphApi | null>;
}

/**
 * Force-directed institutional graph on a 2D canvas (ported from `design/js/graph.jsx`): charge
 * repulsion + link springs + per-cluster gravity, with pan / zoom / drag, click-to-focus, hover
 * tooltip and keyboard navigation. The synchronized accessible table fallback lives in the page.
 */
export function GraphCanvas({
  model,
  filters,
  expanded,
  focus,
  onFocus,
  onExpand,
  onOpenSheet,
  onCounts,
  locate,
  resetSignal,
  reduceMotion,
  apiRef,
}: GraphCanvasProps) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const stateRef = useRef<SimState | null>(null);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; node: GraphNode } | null>(null);

  // Filtered adjacency is the backbone of the visible set + the expand affordance; build it once per
  // (model, filters) and reuse it so neither computation re-scans every edge (FSC-60).
  const adjacency = useMemo(() => buildAdjacency(model, filters), [model, filters]);
  const visible = useMemo(
    () => computeVisible(model, filters, expanded, adjacency),
    [model, filters, expanded, adjacency],
  );
  // Precompute the visible node/edge subsets + the expandable set once per change, so the per-frame
  // step()/draw() loops iterate a small array instead of filtering the whole model every frame.
  const visibleNodes = useMemo(
    () => model.nodes.filter((n) => visible.has(n.siren)),
    [model, visible],
  );
  const visibleEdges = useMemo(
    () =>
      model.edges.filter(
        (e) =>
          filters.linkTypes[e.type] !== false &&
          visible.has(e.source_siren) &&
          visible.has(e.target_siren),
      ),
    [model, visible, filters],
  );
  const expandable = useMemo(
    () => computeExpandable(visible, expanded, adjacency),
    [visible, expanded, adjacency],
  );

  const focusNeighbours = useMemo(() => {
    const set = new Set<string>();
    if (!focus) return set;
    for (const e of model.edges) {
      if (e.source_siren === focus) set.add(e.target_siren);
      if (e.target_siren === focus) set.add(e.source_siren);
    }
    return set;
  }, [focus, model]);

  useEffect(() => {
    onCounts({ shown: visible.size, total: model.nodes.length });
  }, [visible, model, onCounts]);

  useEffect(() => {
    const rawCanvas = canvasRef.current;
    const rawWrap = wrapRef.current;
    if (!rawCanvas || !rawWrap) return;
    const rawCtx = rawCanvas.getContext("2d");
    if (!rawCtx) return;
    // Re-bind as non-null types so the hoisted draw/resize closures keep the narrowing.
    const canvas: HTMLCanvasElement = rawCanvas;
    const wrap: HTMLDivElement = rawWrap;
    const ctx: CanvasRenderingContext2D = rawCtx;

    const st: SimState = {
      scale: 1,
      tx: 0,
      ty: 0,
      w: 0,
      h: 0,
      dpr: Math.min(2, window.devicePixelRatio || 1),
      dragging: null,
      hovering: null,
      panning: false,
      lastX: 0,
      lastY: 0,
      downAt: { x: 0, y: 0 },
      moved: false,
      alpha: 1,
      raf: 0,
      placed: false,
      clusterPos: {},
      cx: 0,
      cy: 0,
      visibleNodes,
      visibleEdges,
      expandableSet: expandable,
      focus,
      focusNeighbours,
      onFocus,
      onExpand,
      onOpenSheet,
      kick: () => {},
      zoomAt: () => {},
      fitView: () => {},
      fitTimer: setTimeout(() => {}, 0),
    };
    stateRef.current = st;
    const { nodes, byId } = model;

    function place() {
      const clusters = [...new Set(nodes.map((n) => n.cluster))];
      const cw = st.w || 800;
      const ch = st.h || 600;
      st.cx = cw / 2;
      st.cy = ch / 2;
      const R = Math.min(cw, ch) * 0.32;
      const cpos: Record<string, { x: number; y: number }> = {};
      clusters.forEach((c, i) => {
        const a = (2 * Math.PI * i) / clusters.length - Math.PI / 2;
        cpos[c] = { x: st.cx + Math.cos(a) * R, y: st.cy + Math.sin(a) * R };
      });
      st.clusterPos = cpos;
      nodes.forEach((n, i) => {
        if (n.x == null) {
          const c = cpos[n.cluster] ?? { x: st.cx, y: st.cy };
          const ang = i * 2.399963;
          const rr = 30 + (i % 11) * 7;
          n.x = c.x + Math.cos(ang) * rr;
          n.y = c.y + Math.sin(ang) * rr;
          n.vx = 0;
          n.vy = 0;
        }
      });
      st.placed = true;
    }

    function resize() {
      const rect = wrap.getBoundingClientRect();
      st.w = rect.width;
      st.h = rect.height;
      canvas.width = Math.round(rect.width * st.dpr);
      canvas.height = Math.round(rect.height * st.dpr);
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
      if (!st.placed) place();
      st.alpha = Math.max(st.alpha, 0.3);
      st.kick();
    }

    function step() {
      const arr = st.visibleNodes;
      const k = st.alpha;
      for (let i = 0; i < arr.length; i++) {
        const a = arr[i];
        for (let j = i + 1; j < arr.length; j++) {
          const b = arr[j];
          let dx = (a.x ?? 0) - (b.x ?? 0);
          let dy = (a.y ?? 0) - (b.y ?? 0);
          let d2 = dx * dx + dy * dy;
          if (d2 < 0.01) {
            dx = Math.random() - 0.5;
            dy = Math.random() - 0.5;
            d2 = 1;
          }
          const minD = radiusFor(a) + radiusFor(b) + 14;
          const dist = Math.sqrt(d2);
          let force = 2600 / d2;
          if (dist < minD) force += ((minD - dist) * 0.9) / dist;
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;
          a.vx = (a.vx ?? 0) + fx * k;
          a.vy = (a.vy ?? 0) + fy * k;
          b.vx = (b.vx ?? 0) - fx * k;
          b.vy = (b.vy ?? 0) - fy * k;
        }
      }
      for (const e of st.visibleEdges) {
        const a = byId.get(e.source_siren);
        const b = byId.get(e.target_siren);
        if (!a || !b) continue;
        const dx = (b.x ?? 0) - (a.x ?? 0);
        const dy = (b.y ?? 0) - (a.y ?? 0);
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const target = e.type === "tutelle" ? 90 : 130;
        const f = (dist - target) * 0.015 * k;
        const fx = (dx / dist) * f;
        const fy = (dy / dist) * f;
        a.vx = (a.vx ?? 0) + fx;
        a.vy = (a.vy ?? 0) + fy;
        b.vx = (b.vx ?? 0) - fx;
        b.vy = (b.vy ?? 0) - fy;
      }
      for (const n of arr) {
        const c = st.clusterPos[n.cluster] ?? { x: st.cx, y: st.cy };
        n.vx = (n.vx ?? 0) + (c.x - (n.x ?? 0)) * 0.012 * k + (st.cx - (n.x ?? 0)) * 0.002 * k;
        n.vy = (n.vy ?? 0) + (c.y - (n.y ?? 0)) * 0.012 * k + (st.cy - (n.y ?? 0)) * 0.002 * k;
      }
      for (const n of arr) {
        if (n === st.dragging) {
          n.vx = 0;
          n.vy = 0;
          continue;
        }
        n.vx = (n.vx ?? 0) * 0.82;
        n.vy = (n.vy ?? 0) * 0.82;
        n.x = (n.x ?? 0) + Math.max(-40, Math.min(40, n.vx));
        n.y = (n.y ?? 0) + Math.max(-40, Math.min(40, n.vy));
      }
      st.alpha *= 0.985;
    }

    const worldToScreen = (x: number, y: number) => ({
      x: x * st.scale + st.tx,
      y: y * st.scale + st.ty,
    });
    const screenToWorld = (x: number, y: number) => ({
      x: (x - st.tx) / st.scale,
      y: (y - st.ty) / st.scale,
    });

    function shapePath(node: GraphNode, sx: number, sy: number, r: number) {
      const shape = node.resolved ? levelMeta(node.level).shape : "circle";
      ctx.beginPath();
      if (shape === "circle") ctx.arc(sx, sy, r, 0, Math.PI * 2);
      else if (shape === "square") ctx.rect(sx - r, sy - r, r * 2, r * 2);
      else if (shape === "diamond") {
        ctx.moveTo(sx, sy - r * 1.25);
        ctx.lineTo(sx + r * 1.25, sy);
        ctx.lineTo(sx, sy + r * 1.25);
        ctx.lineTo(sx - r * 1.25, sy);
        ctx.closePath();
      } else {
        const rr = r * 1.3;
        ctx.moveTo(sx, sy - rr);
        ctx.lineTo(sx + rr * 0.92, sy + rr * 0.7);
        ctx.lineTo(sx - rr * 0.92, sy + rr * 0.7);
        ctx.closePath();
      }
    }

    function draw() {
      ctx.setTransform(st.dpr, 0, 0, st.dpr, 0, 0);
      ctx.clearRect(0, 0, st.w, st.h);
      const foc = st.focus;
      const fn = st.focusNeighbours;
      const dim = (s: string) => !!foc && s !== foc && !fn.has(s);

      for (const e of st.visibleEdges) {
        const a = byId.get(e.source_siren);
        const b = byId.get(e.target_siren);
        if (!a || !b) continue;
        const A = worldToScreen(a.x ?? 0, a.y ?? 0);
        const B = worldToScreen(b.x ?? 0, b.y ?? 0);
        const style = EDGE_STYLE[e.type] ?? EDGE_STYLE.tutelle;
        let w = style.base;
        if (e.type === "funds" && e.amount_eur) w = 1 + Math.min(7, Math.log10(e.amount_eur) - 5);
        if (e.type === "delegates" && e.amount_eur)
          w = 1 + Math.min(5, Math.log10(e.amount_eur) - 5);
        const edgeDim = foc ? !(e.source_siren === foc || e.target_siren === foc) : false;
        ctx.save();
        ctx.globalAlpha = edgeDim ? 0.08 : foc ? 0.9 : 0.5;
        ctx.strokeStyle = style.color;
        ctx.lineWidth = w * st.scale;
        if (style.dash) ctx.setLineDash(style.dash.map((d) => d * st.scale));
        const mx = (A.x + B.x) / 2;
        const my = (A.y + B.y) / 2;
        const nx = -(B.y - A.y);
        const ny = B.x - A.x;
        const nl = Math.hypot(nx, ny) || 1;
        const bow = 12 * st.scale;
        const cxp = mx + (nx / nl) * bow;
        const cyp = my + (ny / nl) * bow;
        ctx.beginPath();
        ctx.moveTo(A.x, A.y);
        ctx.quadraticCurveTo(cxp, cyp, B.x, B.y);
        ctx.stroke();
        ctx.setLineDash([]);
        const rb = radiusFor(b) * st.scale;
        const ang = Math.atan2(B.y - cyp, B.x - cxp);
        const tipX = B.x - Math.cos(ang) * (rb + 2);
        const tipY = B.y - Math.sin(ang) * (rb + 2);
        const ah = 5 * st.scale + w;
        ctx.beginPath();
        ctx.moveTo(tipX, tipY);
        ctx.lineTo(tipX - Math.cos(ang - 0.5) * ah, tipY - Math.sin(ang - 0.5) * ah);
        ctx.lineTo(tipX - Math.cos(ang + 0.5) * ah, tipY - Math.sin(ang + 0.5) * ah);
        ctx.closePath();
        ctx.fillStyle = style.color;
        ctx.fill();
        ctx.restore();
      }

      for (const n of st.visibleNodes) {
        const P = worldToScreen(n.x ?? 0, n.y ?? 0);
        const r = radiusFor(n) * st.scale;
        const meta = levelMeta(n.level);
        ctx.save();
        ctx.globalAlpha = dim(n.siren) ? 0.14 : 1;
        shapePath(n, P.x, P.y, r + 2.5);
        ctx.fillStyle = "#ffffff";
        ctx.fill();
        shapePath(n, P.x, P.y, r);
        ctx.fillStyle = n.resolved ? meta.color : "#d9d9d9";
        ctx.fill();
        const isFoc = n.siren === foc;
        const expandable = st.expandableSet.has(n.siren);
        ctx.lineWidth = (isFoc ? 3 : 1.4) * st.scale;
        ctx.strokeStyle = isFoc ? "#161616" : n.resolved ? "rgba(0,0,0,0.25)" : "#9a9a9a";
        if (!n.resolved) ctx.setLineDash([3 * st.scale, 2 * st.scale]);
        shapePath(n, P.x, P.y, r);
        ctx.stroke();
        ctx.setLineDash([]);
        if (expandable && !isFoc) {
          ctx.beginPath();
          ctx.arc(P.x + r * 0.8, P.y - r * 0.8, 5 * st.scale, 0, Math.PI * 2);
          ctx.fillStyle = "#161616";
          ctx.fill();
          ctx.strokeStyle = "#fff";
          ctx.lineWidth = 1 * st.scale;
          ctx.stroke();
          ctx.fillStyle = "#fff";
          ctx.font = `${7 * st.scale}px Marianne`;
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText("+", P.x + r * 0.8, P.y - r * 0.8 + 0.5);
        }
        // Oversight marker: a small vermillion dot (top-left, distinct quadrant from the "+") on
        // entities « épinglé par la Cour des comptes ». Meaning is carried by the legend + the table
        // fallback, so the dot is purely a navigational cue, never the sole signal (FSC-65).
        if (n.hasMention) {
          ctx.beginPath();
          ctx.arc(P.x - r * 0.8, P.y - r * 0.8, 5 * st.scale, 0, Math.PI * 2);
          ctx.fillStyle = MENTION_COLOR;
          ctx.fill();
          ctx.strokeStyle = "#fff";
          ctx.lineWidth = 1 * st.scale;
          ctx.stroke();
        }
        ctx.restore();

        const showLabel =
          n.isMinistry ||
          isFoc ||
          fn.has(n.siren) ||
          n.siren === st.hovering ||
          (st.scale > 1.3 && r > 14);
        if (showLabel && !dim(n.siren)) {
          ctx.save();
          const fs = n.isMinistry ? 13 : 11;
          ctx.font = `${n.isMinistry || isFoc ? 600 : 400} ${fs}px Marianne`;
          ctx.textAlign = "center";
          ctx.textBaseline = "top";
          let label = n.acronym ?? n.name;
          if (label.length > 30) label = `${label.slice(0, 28)}…`;
          const ty = P.y + r + 3;
          const tw = ctx.measureText(label).width;
          ctx.fillStyle = "rgba(255,255,255,0.86)";
          ctx.fillRect(P.x - tw / 2 - 3, ty - 1, tw + 6, fs + 4);
          ctx.fillStyle = isFoc ? "#000091" : "#161616";
          ctx.fillText(label, P.x, ty);
          ctx.restore();
        }
      }
    }

    function frame() {
      if (st.alpha > 0.02) {
        if (reduceMotion) {
          // Settle with no perceptible animation: keep stepping this frame until the layout is calm
          // or the wall-clock budget is spent. Small graphs settle in one frame (instant); large
          // ones converge over a frame or two, each bounded — avoiding both the multi-second drift
          // that would break the reduced-motion accessibility contract and the unbounded
          // O(visible²) × 40 freeze of the previous fixed settle (FSC-60, motivated by FSC-59).
          const deadline = performance.now() + SETTLE_MS;
          do step();
          while (st.alpha > 0.02 && performance.now() < deadline);
        } else {
          step();
        }
      }
      draw();
      st.raf = requestAnimationFrame(frame);
    }
    st.kick = () => {
      st.alpha = Math.max(st.alpha, 0.6);
    };

    function nodeAt(sx: number, sy: number): GraphNode | null {
      const cand = st.visibleNodes;
      for (let i = cand.length - 1; i >= 0; i--) {
        const n = cand[i];
        const P = worldToScreen(n.x ?? 0, n.y ?? 0);
        const r = radiusFor(n) * st.scale + 3;
        if ((sx - P.x) ** 2 + (sy - P.y) ** 2 <= r * r) return n;
      }
      return null;
    }
    function pos(ev: MouseEvent | TouchEvent) {
      const rect = canvas.getBoundingClientRect();
      const t = "touches" in ev ? ev.touches[0] : ev;
      return { x: t.clientX - rect.left, y: t.clientY - rect.top };
    }
    function onDown(ev: MouseEvent | TouchEvent) {
      const p = pos(ev);
      const n = nodeAt(p.x, p.y);
      st.downAt = p;
      st.moved = false;
      if (n) st.dragging = n;
      else {
        st.panning = true;
        st.lastX = p.x;
        st.lastY = p.y;
      }
    }
    function onMove(ev: MouseEvent | TouchEvent) {
      const p = pos(ev);
      if (st.dragging) {
        const w = screenToWorld(p.x, p.y);
        st.dragging.x = w.x;
        st.dragging.y = w.y;
        st.dragging.vx = 0;
        st.dragging.vy = 0;
        if (Math.hypot(p.x - st.downAt.x, p.y - st.downAt.y) > 4) st.moved = true;
        st.kick();
        return;
      }
      if (st.panning) {
        st.tx += p.x - st.lastX;
        st.ty += p.y - st.lastY;
        st.lastX = p.x;
        st.lastY = p.y;
        if (Math.hypot(p.x - st.downAt.x, p.y - st.downAt.y) > 4) st.moved = true;
        return;
      }
      const n = nodeAt(p.x, p.y);
      st.hovering = n ? n.siren : null;
      canvas.style.cursor = n ? "pointer" : "grab";
      if (n) {
        const P = worldToScreen(n.x ?? 0, n.y ?? 0);
        setTooltip({ x: P.x, y: P.y - radiusFor(n) * st.scale - 10, node: n });
      } else setTooltip(null);
    }
    function onUp() {
      if (st.dragging && !st.moved) {
        st.onExpand(st.dragging.siren);
        st.onFocus(st.dragging.siren);
        st.kick();
      } else if (st.panning && !st.moved) st.onFocus(null);
      st.dragging = null;
      st.panning = false;
    }
    function onDbl(ev: MouseEvent) {
      const p = pos(ev);
      const n = nodeAt(p.x, p.y);
      if (n) st.onOpenSheet(n.siren);
    }
    st.zoomAt = (sx, sy, factor) => {
      const before = screenToWorld(sx, sy);
      st.scale = Math.max(0.3, Math.min(3.5, st.scale * factor));
      const after = screenToWorld(sx, sy);
      st.tx += (after.x - before.x) * st.scale;
      st.ty += (after.y - before.y) * st.scale;
    };
    function onWheel(ev: WheelEvent) {
      ev.preventDefault();
      const p = pos(ev);
      st.zoomAt(p.x, p.y, ev.deltaY < 0 ? 1.12 : 0.89);
    }
    st.fitView = () => {
      const arr = st.visibleNodes;
      if (!arr.length) return;
      let minX = Infinity;
      let minY = Infinity;
      let maxX = -Infinity;
      let maxY = -Infinity;
      for (const n of arr) {
        minX = Math.min(minX, n.x ?? 0);
        minY = Math.min(minY, n.y ?? 0);
        maxX = Math.max(maxX, n.x ?? 0);
        maxY = Math.max(maxY, n.y ?? 0);
      }
      const pad = 60;
      const sx = st.w / (maxX - minX + pad * 2);
      const sy = st.h / (maxY - minY + pad * 2);
      st.scale = Math.max(0.3, Math.min(2, Math.min(sx, sy)));
      st.tx = st.w / 2 - ((minX + maxX) / 2) * st.scale;
      st.ty = st.h / 2 - ((minY + maxY) / 2) * st.scale;
    };

    apiRef.current = {
      zoomIn: () => st.zoomAt(st.w / 2, st.h / 2, 1.2),
      zoomOut: () => st.zoomAt(st.w / 2, st.h / 2, 0.83),
      fit: () => st.fitView(),
    };

    canvas.addEventListener("mousedown", onDown);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    canvas.addEventListener("dblclick", onDbl);
    canvas.addEventListener("wheel", onWheel, { passive: false });

    const ro = new ResizeObserver(resize);
    ro.observe(wrap);
    resize();
    frame();
    st.fitTimer = setTimeout(() => st.fitView(), 900);

    return () => {
      cancelAnimationFrame(st.raf);
      clearTimeout(st.fitTimer);
      ro.disconnect();
      canvas.removeEventListener("mousedown", onDown);
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      canvas.removeEventListener("dblclick", onDbl);
      canvas.removeEventListener("wheel", onWheel);
      apiRef.current = null;
    };
    // The simulation is rebuilt only when the model or motion preference changes; reactive props are
    // pushed into the mutable state below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [model, reduceMotion]);

  // Push reactive props into the running simulation. The precomputed visible subsets change together
  // whenever the model, filters or expansion change, so syncing them re-energizes the layout (kick).
  useEffect(() => {
    const st = stateRef.current;
    if (st) {
      st.visibleNodes = visibleNodes;
      st.visibleEdges = visibleEdges;
      st.expandableSet = expandable;
      st.kick();
    }
  }, [visibleNodes, visibleEdges, expandable]);
  useEffect(() => {
    const st = stateRef.current;
    if (st) {
      st.focus = focus;
      st.focusNeighbours = focusNeighbours;
    }
  }, [focus, focusNeighbours]);
  useEffect(() => {
    const st = stateRef.current;
    if (st) {
      st.onFocus = onFocus;
      st.onExpand = onExpand;
      st.onOpenSheet = onOpenSheet;
    }
  }, [onFocus, onExpand, onOpenSheet]);

  useEffect(() => {
    const st = stateRef.current;
    if (!st || !locate) return;
    const n = model.byId.get(locate);
    if (!n) return;
    st.scale = 1.4;
    st.tx = st.w / 2 - (n.x ?? 0) * st.scale;
    st.ty = st.h / 2 - (n.y ?? 0) * st.scale;
  }, [locate, model]);

  useEffect(() => {
    const st = stateRef.current;
    if (st && resetSignal) setTimeout(() => st.fitView(), 30);
  }, [resetSignal]);

  function onKeyDown(e: React.KeyboardEvent) {
    const st = stateRef.current;
    if (!st) return;
    const visArr = model.nodes.filter((n) => visible.has(n.siren));
    if (!visArr.length) return;
    if (["ArrowRight", "ArrowLeft", "ArrowUp", "ArrowDown"].includes(e.key)) {
      e.preventDefault();
      const cur = focus ? model.byId.get(focus) : visArr[0];
      if (!focus && cur) {
        onFocus(cur.siren);
        return;
      }
      if (!cur) return;
      const dir = { ArrowRight: [1, 0], ArrowLeft: [-1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[
        e.key
      ] ?? [1, 0];
      let best: GraphNode | null = null;
      let bestScore = Infinity;
      for (const n of visArr) {
        if (n === cur) continue;
        const dx = (n.x ?? 0) - (cur.x ?? 0);
        const dy = (n.y ?? 0) - (cur.y ?? 0);
        const dot = dx * dir[0] + dy * dir[1];
        if (dot <= 0) continue;
        const off = Math.abs(dx * dir[1] - dy * dir[0]);
        const score = Math.hypot(dx, dy) + off * 2;
        if (score < bestScore) {
          bestScore = score;
          best = n;
        }
      }
      if (best) {
        onFocus(best.siren);
        onExpand(best.siren);
      }
    } else if (e.key === "Enter" && focus) onOpenSheet(focus);
    else if (e.key === "Escape") onFocus(null);
  }

  return (
    <div
      className="graph-canvas-wrap"
      ref={wrapRef}
      tabIndex={0}
      role="application"
      aria-label="Graphe institutionnel interactif. Tab pour entrer, les flèches pour naviguer entre institutions, Entrée pour ouvrir la fiche, Échap pour désélectionner. Un équivalent tabulaire est disponible via « Vue tableau »."
      onKeyDown={onKeyDown}
    >
      <canvas ref={canvasRef} />
      {tooltip ? (
        <div
          className="graph-tooltip"
          style={{ left: tooltip.x, top: tooltip.y, transform: "translate(-50%,-100%)" }}
        >
          <strong>{tooltip.node.name}</strong>
          <span className="gt-meta">
            {levelMeta(tooltip.node.level).label}
            {tooltip.node.category ? ` · ${tooltip.node.category}` : ""}
          </span>
          {tooltip.node.cp ? (
            <div className="gt-meta">CP {euroCompact(tooltip.node.cp)} · exemple</div>
          ) : null}
          {!tooltip.node.resolved ? <div className="gt-meta">SIREN non résolu</div> : null}
        </div>
      ) : null}
    </div>
  );
}
