/* Shared UI components → window. */

// ---- Level shape glyph (non-colour cue) ----
function LevelShape({ level, size = 12, color }) {
  const m = window.U.levelMeta(level);
  const c = color || m.color;
  const s = size;
  if (m.shape === "circle") return <svg width={s} height={s} viewBox="0 0 12 12" aria-hidden="true"><circle cx="6" cy="6" r="5" fill={c} /></svg>;
  if (m.shape === "square") return <svg width={s} height={s} viewBox="0 0 12 12" aria-hidden="true"><rect x="1" y="1" width="10" height="10" rx="1" fill={c} /></svg>;
  if (m.shape === "diamond") return <svg width={s} height={s} viewBox="0 0 12 12" aria-hidden="true"><rect x="2.5" y="2.5" width="7" height="7" transform="rotate(45 6 6)" fill={c} /></svg>;
  return <svg width={s} height={s} viewBox="0 0 12 12" aria-hidden="true"><path d="M6 1l5 9.5H1z" fill={c} /></svg>;
}

// ---- Level badge ----
function LevelBadge({ level, unresolved }) {
  const m = window.U.levelMeta(level);
  if (unresolved) {
    return <span className="badge badge--unresolved"><window.Icon.Warning style={{ width: 12, height: 12 }} /> SIREN non résolu</span>;
  }
  return (
    <span className={`badge badge--niv badge--${level}`}>
      <LevelShape level={level} size={11} color={level === "delegue" ? "#4a3500" : "#fff"} />
      {m.label}
    </span>
  );
}

// ---- Provenance badge (source · licence · millésime) ----
function ProvenanceBadge({ provId, millesime, onOpenSource }) {
  const src = window.U.sourceOf(provId);
  if (!src) return null;
  const label = `${src.publisher.split("—")[0].trim()} · ${src.licence}${millesime ? " · " + millesime : src.millesime ? " · " + src.millesime : ""}`;
  return (
    <span className="prov" title={`Source : ${src.publisher} — ${src.licence}, millésime ${millesime || src.millesime}`}>
      <span className="prov__dot"></span>
      {onOpenSource
        ? <button onClick={() => onOpenSource(provId)}>{label}</button>
        : <span>{label}</span>}
    </span>
  );
}

function ExampleFlag({ children }) {
  return <span className="example-flag"><window.Icon.Info style={{ width: 12, height: 12 }} /> {children || "Exemple"}</span>;
}

// ---- Level chip (clickable, links to graph filtered) ----
function Chip({ children, onClick, selected, level, sm }) {
  return (
    <button className={`tag ${selected ? "tag--selected" : "tag--clickable"} ${sm ? "tag--sm" : ""}`} onClick={onClick}>
      {level ? <LevelShape level={level} size={9} color={selected ? "#fff" : undefined} /> : null}
      {children}
    </button>
  );
}

// ---- Generic accessible data table with optional sort ----
function DataTable({ caption, columns, rows, getRowKey }) {
  const [sort, setSort] = React.useState(null); // {key, dir}
  const sorted = React.useMemo(() => {
    if (!sort) return rows;
    const col = columns.find((c) => c.key === sort.key);
    const r = [...rows].sort((a, b) => {
      const av = col.sortValue ? col.sortValue(a) : a[sort.key];
      const bv = col.sortValue ? col.sortValue(b) : b[sort.key];
      if (typeof av === "number" && typeof bv === "number") return av - bv;
      return String(av).localeCompare(String(bv), "fr");
    });
    return sort.dir === "desc" ? r.reverse() : r;
  }, [rows, sort, columns]);

  function toggle(key) {
    setSort((s) => (s && s.key === key ? (s.dir === "asc" ? { key, dir: "desc" } : null) : { key, dir: "asc" }));
  }
  return (
    <div className="table-wrap">
      <table className="fr-table">
        {caption ? <caption>{caption}</caption> : null}
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} className={c.num ? "num" : ""} aria-sort={sort && sort.key === c.key ? (sort.dir === "asc" ? "ascending" : "descending") : "none"}>
                {c.sortable === false ? c.header : (
                  <button className="sort" onClick={() => toggle(c.key)}>
                    {c.header}
                    {sort && sort.key === c.key ? (sort.dir === "asc" ? <window.Icon.ArrowUp style={{ width: 13, height: 13 }} /> : <window.Icon.ArrowDown style={{ width: 13, height: 13 }} />) : null}
                  </button>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr key={getRowKey(row)}>
              {columns.map((c) => (
                <td key={c.key} className={c.num ? "num" : ""}>{c.render ? c.render(row) : row[c.key]}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

Object.assign(window, { LevelShape, LevelBadge, ProvenanceBadge, ExampleFlag, Chip, DataTable });
