/* ============================================================================
   Force-directed institutional graph (canvas, ~hundreds of nodes).
   Custom physics: charge repulsion + link springs + per-ministère cluster
   gravity + centering. Pan/zoom, drag, click-to-focus, hover tooltip,
   keyboard navigation. → window.GraphCanvas
   ============================================================================ */

const LEVEL_ORDER = ["etat", "local", "social", "delegue"];

function buildModel() {
  const D = window.DATA;
  const nodes = D.entities.map((e) => ({ ...e }));
  const nodeById = new Map(nodes.map((n) => [n.siren, n]));
  const edges = D.edges
    .filter((e) => nodeById.has(e.source_siren) && nodeById.has(e.target_siren))
    .map((e) => ({ ...e }));

  // cluster = ministry root for état; otherwise grouped by level
  nodes.forEach((n) => {
    const chain = window.U.tutelleChain(n.siren);
    const root = chain[0];
    n.cluster = n.level === "etat" ? root.siren : "grp_" + n.level;
    n.isAnchor = !n.parent_siren && (n.level !== "delegue"); // ministries, caisses, collectivités
    n.isMinistry = n.category === "ministère";
    n.degree = 0;
  });
  edges.forEach((e) => { nodeById.get(e.source_siren).degree++; nodeById.get(e.target_siren).degree++; });

  return { nodes, nodeById, edges };
}

// log-scaled radius from CP magnitude
function radiusFor(n) {
  const cp = n.cp_eur || 0;
  if (cp <= 0) return 7;
  const r = 6 + Math.log10(cp) * 2.6; // ~6..32
  return Math.max(6, Math.min(34, r));
}

const EDGE_STYLE = {
  tutelle: { color: "#7a7a86", dash: null, base: 1.2 },
  funds: { color: "#0072b2", dash: null, base: 1.4 },
  participation: { color: "#1f8a5b", dash: [1, 0], base: 1.2 },
  delegates: { color: "#cf7a00", dash: [5, 4], base: 1.2 },
};

function GraphCanvas({ filters, expanded, focus, onFocus, onExpand, onOpenSheet, onCounts, locate, resetSignal, reduceMotion }) {
  const wrapRef = React.useRef(null);
  const canvasRef = React.useRef(null);
  const stateRef = React.useRef(null);
  const [tooltip, setTooltip] = React.useState(null);

  // build model once
  const model = React.useMemo(buildModel, []);

  // ---- visibility from anchors + expanded set ----
  const visible = React.useMemo(() => {
    const { nodes, edges, nodeById } = model;
    // filter predicate
    const passFilter = (n) => {
      if (!filters.levels[n.level]) return false;
      if (filters.ministry !== "all" && n.level === "etat") {
        if (window.U.tutelleChain(n.siren)[0].siren !== filters.ministry) return false;
      }
      if (filters.minAmount > 0 && (n.cp_eur || 0) < filters.minAmount) {
        if (!n.isMinistry) return false;
      }
      return true;
    };
    const adj = new Map(nodes.map((n) => [n.siren, []]));
    edges.forEach((e) => {
      if (filters.linkTypes[e.type] === false) return;
      adj.get(e.source_siren).push(e.target_siren);
      adj.get(e.target_siren).push(e.source_siren);
    });
    const vis = new Set();
    nodes.forEach((n) => { if (n.isAnchor && passFilter(n)) vis.add(n.siren); });
    // expand: reveal neighbours of expanded+visible nodes (iterate to fixpoint)
    let changed = true, guard = 0;
    while (changed && guard++ < 12) {
      changed = false;
      [...vis].forEach((s) => {
        if (!expanded.has(s)) return;
        adj.get(s).forEach((t) => {
          const tn = nodeById.get(t);
          if (!vis.has(t) && passFilter(tn)) { vis.add(t); changed = true; }
        });
      });
    }
    return vis;
  }, [model, filters, expanded]);

  // neighbours of focus (for emphasis)
  const focusNeighbours = React.useMemo(() => {
    const set = new Set();
    if (!focus) return set;
    model.edges.forEach((e) => {
      if (e.source_siren === focus) set.add(e.target_siren);
      if (e.target_siren === focus) set.add(e.source_siren);
    });
    return set;
  }, [focus, model]);

  React.useEffect(() => {
    onCounts && onCounts({ shown: visible.size, total: model.nodes.length });
  }, [visible, model, onCounts]);

  // ---- simulation setup ----
  React.useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;
    const ctx = canvas.getContext("2d");

    const st = {
      nodes: model.nodes, edges: model.edges, nodeById: model.nodeById,
      scale: 1, tx: 0, ty: 0, w: 0, h: 0, dpr: Math.min(2, window.devicePixelRatio || 1),
      dragging: null, hovering: null, panning: false, lastX: 0, lastY: 0,
      alpha: 1, raf: 0, placed: false,
      // seed reactive fields so the first (synchronous) frame is safe,
      // before the prop-sync effects run:
      visible, filters, expanded, focus, focusNeighbours,
      onFocus, onExpand, onOpenSheet,
    };
    stateRef.current = st;

    // place clusters around a circle (once)
    function place() {
      const { nodes } = st;
      const clusters = [...new Set(nodes.map((n) => n.cluster))];
      const cw = st.w || 800, ch = st.h || 600;
      const cx = cw / 2, cy = ch / 2;
      const R = Math.min(cw, ch) * 0.32;
      const cpos = {};
      clusters.forEach((c, i) => {
        const a = (2 * Math.PI * i) / clusters.length - Math.PI / 2;
        cpos[c] = { x: cx + Math.cos(a) * R, y: cy + Math.sin(a) * R };
      });
      st.clusterPos = cpos; st.cx = cx; st.cy = cy;
      nodes.forEach((n, i) => {
        if (n.x == null) {
          const c = cpos[n.cluster];
          const ang = (i * 2.399963); // golden-angle scatter
          const rr = 30 + (i % 11) * 7;
          n.x = c.x + Math.cos(ang) * rr;
          n.y = c.y + Math.sin(ang) * rr;
          n.vx = 0; n.vy = 0;
        }
      });
      st.placed = true;
    }

    function resize() {
      const rect = wrap.getBoundingClientRect();
      st.w = rect.width; st.h = rect.height;
      canvas.width = Math.round(rect.width * st.dpr);
      canvas.height = Math.round(rect.height * st.dpr);
      canvas.style.width = rect.width + "px";
      canvas.style.height = rect.height + "px";
      if (!st.placed) place();
      st.alpha = Math.max(st.alpha, 0.3);
      kick();
    }

    // physics step
    function step() {
      const vis = st.visible;
      const arr = st.nodes.filter((n) => vis.has(n.siren));
      const k = st.alpha;
      // charge repulsion (only visible)
      for (let i = 0; i < arr.length; i++) {
        const a = arr[i];
        for (let j = i + 1; j < arr.length; j++) {
          const b = arr[j];
          let dx = a.x - b.x, dy = a.y - b.y;
          let d2 = dx * dx + dy * dy;
          if (d2 < 0.01) { dx = (Math.random() - 0.5); dy = (Math.random() - 0.5); d2 = 1; }
          const ra = radiusFor(a), rb = radiusFor(b);
          const minD = (ra + rb + 14);
          const dist = Math.sqrt(d2);
          let force = (2600) / d2;
          // hard anti-overlap
          if (dist < minD) force += (minD - dist) * 0.9 / dist;
          const fx = (dx / dist) * force, fy = (dy / dist) * force;
          a.vx += fx * k; a.vy += fy * k;
          b.vx -= fx * k; b.vy -= fy * k;
        }
      }
      // link springs
      st.edges.forEach((e) => {
        if (!vis.has(e.source_siren) || !vis.has(e.target_siren)) return;
        if (st.filters.linkTypes[e.type] === false) return;
        const a = st.nodeById.get(e.source_siren), b = st.nodeById.get(e.target_siren);
        const dx = b.x - a.x, dy = b.y - a.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const target = e.type === "tutelle" ? 90 : 130;
        const f = (dist - target) * 0.015 * k;
        const fx = (dx / dist) * f, fy = (dy / dist) * f;
        a.vx += fx; a.vy += fy; b.vx -= fx; b.vy -= fy;
      });
      // cluster gravity + centering
      arr.forEach((n) => {
        const c = st.clusterPos[n.cluster];
        n.vx += (c.x - n.x) * 0.012 * k;
        n.vy += (c.y - n.y) * 0.012 * k;
        n.vx += (st.cx - n.x) * 0.002 * k;
        n.vy += (st.cy - n.y) * 0.002 * k;
      });
      // integrate
      arr.forEach((n) => {
        if (n === st.dragging) { n.vx = 0; n.vy = 0; return; }
        n.vx *= 0.82; n.vy *= 0.82;
        n.x += Math.max(-40, Math.min(40, n.vx));
        n.y += Math.max(-40, Math.min(40, n.vy));
      });
      st.alpha *= 0.985;
    }

    function worldToScreen(x, y) { return { x: x * st.scale + st.tx, y: y * st.scale + st.ty }; }
    function screenToWorld(x, y) { return { x: (x - st.tx) / st.scale, y: (y - st.ty) / st.scale }; }

    function shapePath(ctx, n, sx, sy, r) {
      const sh = window.U.levelMeta(n.level).shape;
      ctx.beginPath();
      if (sh === "circle") { ctx.arc(sx, sy, r, 0, Math.PI * 2); }
      else if (sh === "square") { ctx.rect(sx - r, sy - r, r * 2, r * 2); }
      else if (sh === "diamond") { ctx.moveTo(sx, sy - r * 1.25); ctx.lineTo(sx + r * 1.25, sy); ctx.lineTo(sx, sy + r * 1.25); ctx.lineTo(sx - r * 1.25, sy); ctx.closePath(); }
      else { const rr = r * 1.3; ctx.moveTo(sx, sy - rr); ctx.lineTo(sx + rr * 0.92, sy + rr * 0.7); ctx.lineTo(sx - rr * 0.92, sy + rr * 0.7); ctx.closePath(); }
    }

    function draw() {
      const dpr = st.dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, st.w, st.h);
      const vis = st.visible;
      const foc = st.focus;
      const fn = st.focusNeighbours;
      const dim = (s) => foc && s !== foc && !fn.has(s);

      // edges
      st.edges.forEach((e) => {
        if (!vis.has(e.source_siren) || !vis.has(e.target_siren)) return;
        if (st.filters.linkTypes[e.type] === false) return;
        const a = st.nodeById.get(e.source_siren), b = st.nodeById.get(e.target_siren);
        const A = worldToScreen(a.x, a.y), B = worldToScreen(b.x, b.y);
        const style = EDGE_STYLE[e.type] || EDGE_STYLE.tutelle;
        let w = style.base;
        if (e.type === "funds" && e.amount_eur) w = 1 + Math.min(7, Math.log10(e.amount_eur) - 5);
        if (e.type === "delegates" && e.amount_eur) w = 1 + Math.min(5, Math.log10(e.amount_eur) - 5);
        const edgeDim = foc ? (e.source_siren === foc || e.target_siren === foc ? false : true) : false;
        ctx.save();
        ctx.globalAlpha = edgeDim ? 0.08 : (foc ? 0.9 : 0.5);
        ctx.strokeStyle = style.color;
        ctx.lineWidth = w * st.scale;
        if (style.dash) ctx.setLineDash(style.dash.map((d) => d * st.scale));
        // slight curve
        const mx = (A.x + B.x) / 2, my = (A.y + B.y) / 2;
        const nx = -(B.y - A.y), ny = (B.x - A.x);
        const nl = Math.hypot(nx, ny) || 1;
        const bow = 12 * st.scale;
        const cxp = mx + (nx / nl) * bow, cyp = my + (ny / nl) * bow;
        ctx.beginPath(); ctx.moveTo(A.x, A.y); ctx.quadraticCurveTo(cxp, cyp, B.x, B.y); ctx.stroke();
        ctx.setLineDash([]);
        // arrowhead near target
        const rb = radiusFor(b) * st.scale;
        const ang = Math.atan2(B.y - cyp, B.x - cxp);
        const tipX = B.x - Math.cos(ang) * (rb + 2), tipY = B.y - Math.sin(ang) * (rb + 2);
        const ah = 5 * st.scale + w;
        ctx.beginPath();
        ctx.moveTo(tipX, tipY);
        ctx.lineTo(tipX - Math.cos(ang - 0.5) * ah, tipY - Math.sin(ang - 0.5) * ah);
        ctx.lineTo(tipX - Math.cos(ang + 0.5) * ah, tipY - Math.sin(ang + 0.5) * ah);
        ctx.closePath();
        ctx.fillStyle = style.color; ctx.fill();
        ctx.restore();
      });

      // nodes
      const visNodes = st.nodes.filter((n) => vis.has(n.siren));
      visNodes.forEach((n) => {
        const P = worldToScreen(n.x, n.y);
        const r = radiusFor(n) * st.scale;
        const m = window.U.levelMeta(n.level);
        ctx.save();
        ctx.globalAlpha = dim(n.siren) ? 0.14 : 1;
        // halo
        shapePath(ctx, n, P.x, P.y, r + 2.5);
        ctx.fillStyle = "#ffffff"; ctx.fill();
        // body
        shapePath(ctx, n, P.x, P.y, r);
        ctx.fillStyle = n.resolved === false ? "#d9d9d9" : m.color;
        ctx.fill();
        // border / focus ring
        const isFoc = n.siren === foc;
        const expandable = st.expanded && !st.expanded.has(n.siren) && hasHiddenNeighbours(n.siren);
        ctx.lineWidth = (isFoc ? 3 : 1.4) * st.scale;
        ctx.strokeStyle = isFoc ? "#161616" : (n.resolved === false ? "#9a9a9a" : "rgba(0,0,0,0.25)");
        if (n.resolved === false) ctx.setLineDash([3 * st.scale, 2 * st.scale]);
        shapePath(ctx, n, P.x, P.y, r);
        ctx.stroke();
        ctx.setLineDash([]);
        // expandable hint: small + ring
        if (expandable && !isFoc) {
          ctx.beginPath(); ctx.arc(P.x + r * 0.8, P.y - r * 0.8, 5 * st.scale, 0, Math.PI * 2);
          ctx.fillStyle = "#161616"; ctx.fill();
          ctx.strokeStyle = "#fff"; ctx.lineWidth = 1 * st.scale; ctx.stroke();
          ctx.fillStyle = "#fff"; ctx.font = `${7 * st.scale}px Marianne`; ctx.textAlign = "center"; ctx.textBaseline = "middle";
          ctx.fillText("+", P.x + r * 0.8, P.y - r * 0.8 + 0.5);
        }
        ctx.restore();

        // labels: ministries always; focus + neighbours; hover; large nodes when zoomed
        const showLabel = n.isMinistry || isFoc || fn.has(n.siren) || n.siren === st.hovering || (st.scale > 1.3 && r > 14);
        if (showLabel && !dim(n.siren)) {
          ctx.save();
          const fs = (n.isMinistry ? 13 : 11);
          ctx.font = `${n.isMinistry || isFoc ? 600 : 400} ${fs}px Marianne`;
          ctx.textAlign = "center"; ctx.textBaseline = "top";
          let label = n.acronym || n.name;
          if (label.length > 30) label = label.slice(0, 28) + "…";
          const ty = P.y + r + 3;
          const tw = ctx.measureText(label).width;
          ctx.fillStyle = "rgba(255,255,255,0.86)";
          ctx.fillRect(P.x - tw / 2 - 3, ty - 1, tw + 6, fs + 4);
          ctx.fillStyle = isFoc ? "#000091" : "#161616";
          ctx.fillText(label, P.x, ty);
          ctx.restore();
        }
      });
    }

    function hasHiddenNeighbours(siren) {
      let any = false;
      st.edges.forEach((e) => {
        if (st.filters.linkTypes[e.type] === false) return;
        const other = e.source_siren === siren ? e.target_siren : (e.target_siren === siren ? e.source_siren : null);
        if (other && !st.visible.has(other)) any = true;
      });
      return any;
    }
    st._hasHidden = hasHiddenNeighbours;

    function frame() {
      if (st.alpha > 0.02 && !reduceMotion) step();
      else if (st.alpha > 0.02 && reduceMotion) { for (let i = 0; i < 40; i++) step(); }
      draw();
      st.raf = requestAnimationFrame(frame);
    }
    function kick() { st.alpha = Math.max(st.alpha, 0.6); }
    st.kick = kick;

    // ---- pointer interaction ----
    function nodeAt(sx, sy) {
      const vis = st.visible;
      const cand = st.nodes.filter((n) => vis.has(n.siren));
      for (let i = cand.length - 1; i >= 0; i--) {
        const n = cand[i];
        const P = worldToScreen(n.x, n.y);
        const r = radiusFor(n) * st.scale + 3;
        if ((sx - P.x) ** 2 + (sy - P.y) ** 2 <= r * r) return n;
      }
      return null;
    }
    function pos(ev) {
      const rect = canvas.getBoundingClientRect();
      const t = ev.touches ? ev.touches[0] : ev;
      return { x: t.clientX - rect.left, y: t.clientY - rect.top };
    }
    function onDown(ev) {
      const p = pos(ev);
      const n = nodeAt(p.x, p.y);
      st.downAt = p; st.moved = false;
      if (n) { st.dragging = n; st.dragStart = p; }
      else { st.panning = true; st.lastX = p.x; st.lastY = p.y; }
    }
    function onMove(ev) {
      const p = pos(ev);
      if (st.dragging) {
        const w = screenToWorld(p.x, p.y);
        st.dragging.x = w.x; st.dragging.y = w.y; st.dragging.vx = 0; st.dragging.vy = 0;
        if (Math.hypot(p.x - st.downAt.x, p.y - st.downAt.y) > 4) st.moved = true;
        kick(); return;
      }
      if (st.panning) {
        st.tx += p.x - st.lastX; st.ty += p.y - st.lastY;
        st.lastX = p.x; st.lastY = p.y;
        if (Math.hypot(p.x - st.downAt.x, p.y - st.downAt.y) > 4) st.moved = true;
        return;
      }
      const n = nodeAt(p.x, p.y);
      st.hovering = n ? n.siren : null;
      canvas.style.cursor = n ? "pointer" : "grab";
      if (n) {
        const P = worldToScreen(n.x, n.y);
        setTooltip({ x: P.x, y: P.y - radiusFor(n) * st.scale - 10, node: n });
      } else setTooltip(null);
    }
    function onUp(ev) {
      if (st.dragging && !st.moved) clickNode(st.dragging);
      else if (st.panning && !st.moved) { st.onFocus && st.onFocus(null); }
      st.dragging = null; st.panning = false;
    }
    function clickNode(n) {
      st.onExpand && st.onExpand(n.siren);
      st.onFocus && st.onFocus(n.siren);
      kick();
    }
    function onDbl(ev) {
      const p = pos(ev);
      const n = nodeAt(p.x, p.y);
      if (n) st.onOpenSheet && st.onOpenSheet(n.siren);
    }
    function onWheel(ev) {
      ev.preventDefault();
      const p = pos(ev);
      const factor = ev.deltaY < 0 ? 1.12 : 0.89;
      zoomAt(p.x, p.y, factor);
    }
    function zoomAt(sx, sy, factor) {
      const before = screenToWorld(sx, sy);
      st.scale = Math.max(0.3, Math.min(3.5, st.scale * factor));
      const after = screenToWorld(sx, sy);
      st.tx += (after.x - before.x) * st.scale;
      st.ty += (after.y - before.y) * st.scale;
    }
    st.zoomAt = zoomAt;

    canvas.addEventListener("mousedown", onDown);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    canvas.addEventListener("dblclick", onDbl);
    canvas.addEventListener("wheel", onWheel, { passive: false });
    canvas.addEventListener("touchstart", onDown, { passive: true });
    canvas.addEventListener("touchmove", (e) => { onMove(e); }, { passive: true });
    canvas.addEventListener("touchend", onUp);

    const ro = new ResizeObserver(resize);
    ro.observe(wrap);
    resize();
    frame();
    // auto-fit once the initial layout settles
    st.fitTimer = setTimeout(() => { st.fitView && st.fitView(); }, 900);

    st.fitView = function () {
      const vis = st.visible;
      const arr = st.nodes.filter((n) => vis.has(n.siren));
      if (!arr.length) return;
      let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
      arr.forEach((n) => { minX = Math.min(minX, n.x); minY = Math.min(minY, n.y); maxX = Math.max(maxX, n.x); maxY = Math.max(maxY, n.y); });
      const pad = 60;
      const sx = st.w / (maxX - minX + pad * 2);
      const sy = st.h / (maxY - minY + pad * 2);
      st.scale = Math.max(0.3, Math.min(2, Math.min(sx, sy)));
      st.tx = st.w / 2 - ((minX + maxX) / 2) * st.scale;
      st.ty = st.h / 2 - ((minY + maxY) / 2) * st.scale;
    };

    return () => {
      cancelAnimationFrame(st.raf);
      clearTimeout(st.fitTimer);
      ro.disconnect();
      canvas.removeEventListener("mousedown", onDown);
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      canvas.removeEventListener("dblclick", onDbl);
      canvas.removeEventListener("wheel", onWheel);
    };
  }, [model, reduceMotion]);

  // push reactive props into sim state
  React.useEffect(() => { const st = stateRef.current; if (!st) return; st.visible = visible; st.kick && st.kick(); }, [visible]);
  React.useEffect(() => { const st = stateRef.current; if (st) { st.focus = focus; st.focusNeighbours = focusNeighbours; } }, [focus, focusNeighbours]);
  React.useEffect(() => { const st = stateRef.current; if (st) { st.expanded = expanded; st.filters = filters; st.kick && st.kick(); } }, [expanded, filters]);
  React.useEffect(() => { const st = stateRef.current; if (st) { st.onFocus = onFocus; st.onExpand = onExpand; st.onOpenSheet = onOpenSheet; } }, [onFocus, onExpand, onOpenSheet]);

  // locate / center a node
  React.useEffect(() => {
    const st = stateRef.current; if (!st || !locate) return;
    const n = st.nodeById.get(locate);
    if (!n) return;
    st.scale = 1.4;
    st.tx = st.w / 2 - n.x * st.scale;
    st.ty = st.h / 2 - n.y * st.scale;
  }, [locate]);

  // reset / fit
  React.useEffect(() => {
    const st = stateRef.current; if (!st) return;
    if (resetSignal && st.fitView) { setTimeout(() => st.fitView(), 30); }
  }, [resetSignal]);

  // expose zoom controls via window for buttons
  const api = {
    zoomIn: () => { const st = stateRef.current; st && st.zoomAt(st.w / 2, st.h / 2, 1.2); },
    zoomOut: () => { const st = stateRef.current; st && st.zoomAt(st.w / 2, st.h / 2, 0.83); },
    fit: () => { const st = stateRef.current; st && st.fitView(); },
  };
  React.useEffect(() => { if (window.__graphApi !== undefined || true) window.__graphApi = api; });

  // keyboard navigation: tab into canvas, arrows move focus to nearest neighbour
  function onKeyDown(e) {
    const st = stateRef.current; if (!st) return;
    const visArr = st.nodes.filter((n) => visible.has(n.siren));
    if (!visArr.length) return;
    if (["ArrowRight", "ArrowLeft", "ArrowUp", "ArrowDown"].includes(e.key)) {
      e.preventDefault();
      let cur = focus ? st.nodeById.get(focus) : visArr[0];
      if (!focus) { onFocus(cur.siren); return; }
      const dir = { ArrowRight: [1, 0], ArrowLeft: [-1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[e.key];
      let best = null, bestScore = Infinity;
      visArr.forEach((n) => {
        if (n === cur) return;
        const dx = n.x - cur.x, dy = n.y - cur.y;
        const dot = dx * dir[0] + dy * dir[1];
        if (dot <= 0) return;
        const dist = Math.hypot(dx, dy);
        const off = Math.abs(dx * dir[1] - dy * dir[0]);
        const score = dist + off * 2;
        if (score < bestScore) { bestScore = score; best = n; }
      });
      if (best) { onFocus(best.siren); onExpand(best.siren); }
    } else if (e.key === "Enter" && focus) { onOpenSheet(focus); }
    else if (e.key === "Escape") { onFocus(null); }
  }

  return (
    <div className="graph-canvas-wrap" ref={wrapRef}
      tabIndex={0} role="application"
      aria-label="Graphe institutionnel interactif. Utilisez Tab pour entrer, les flèches pour naviguer entre institutions, Entrée pour ouvrir la fiche, Échap pour désélectionner. Un équivalent tabulaire est disponible via l’onglet « Vue tableau »."
      onKeyDown={onKeyDown}>
      <canvas ref={canvasRef}></canvas>
      {tooltip ? (
        <div className="graph-tooltip" style={{ left: tooltip.x, top: tooltip.y, transform: "translate(-50%,-100%)" }}>
          <strong>{tooltip.node.name}</strong>
          <span className="gt-meta">{window.U.levelMeta(tooltip.node.level).label}{tooltip.node.category ? " · " + tooltip.node.category : ""}</span>
          {tooltip.node.cp_eur ? <div className="gt-meta">CP {window.U.euroCompact(tooltip.node.cp_eur)} · exemple</div> : null}
          {tooltip.node.resolved === false ? <div className="gt-meta">SIREN non résolu</div> : null}
        </div>
      ) : null}
    </div>
  );
}

window.GraphCanvas = GraphCanvas;
