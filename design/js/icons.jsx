/* Icon set — simple stroke glyphs (Remix-style), shared via window.Icon. */
const Icon = (function () {
  const S = (path, props = {}) => (p) =>
    React.createElement(
      "svg",
      Object.assign({ viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": "true" }, props, p),
      path
    );

  return {
    Search: S(<><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" /></>),
    Graph: S(<><circle cx="5" cy="6" r="2.4" /><circle cx="19" cy="7" r="2.4" /><circle cx="12" cy="18" r="2.4" /><path d="M7.1 7.1l3 8M16.8 8.6l-3.6 7.6M7 6.6h9.6" /></>),
    Home: S(<><path d="M3 11l9-8 9 8" /><path d="M5 10v10h14V10" /></>),
    Flow: S(<><path d="M4 6h6c4 0 4 12 10 12" /><path d="M4 18h6" /><path d="M17 4l3 2-3 2" /><path d="M17 16l3 2-3 2" /></>),
    Doc: S(<><path d="M6 2h8l4 4v16H6z" /><path d="M14 2v4h4" /><path d="M9 13h6M9 17h6" /></>),
    Arrow: S(<path d="M5 12h14M13 6l6 6-6 6" />),
    ArrowUp: S(<path d="M12 19V5M6 11l6-6 6 6" />),
    ArrowDown: S(<path d="M12 5v14M6 13l6 6 6-6" />),
    External: S(<><path d="M14 4h6v6" /><path d="M20 4l-9 9" /><path d="M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5" /></>),
    Close: S(<path d="M6 6l12 12M18 6L6 18" />),
    Plus: S(<path d="M12 5v14M5 12h14" />),
    Minus: S(<path d="M5 12h14" />),
    Reset: S(<><path d="M3 12a9 9 0 1 0 3-6.7L3 8" /><path d="M3 3v5h5" /></>),
    Filter: S(<path d="M3 5h18l-7 8v5l-4 2v-7z" />),
    Info: S(<><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" /></>),
    Check: S(<path d="M5 12l5 5L20 6" />),
    Shield: S(<><path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z" /><path d="M9 12l2 2 4-4" /></>),
    Scale: S(<><path d="M12 3v18M5 7h14" /><path d="M5 7l-2.5 6h5zM19 7l-2.5 6h5z" /><path d="M8 20h8" /></>),
    Table: S(<><rect x="3" y="4" width="18" height="16" rx="1" /><path d="M3 9h18M3 14h18M9 4v16" /></>),
    Layers: S(<><path d="M12 3l9 5-9 5-9-5z" /><path d="M3 13l9 5 9-5" /></>),
    Building: S(<><rect x="5" y="3" width="14" height="18" rx="1" /><path d="M9 7h2M13 7h2M9 11h2M13 11h2M9 15h2M13 15h2" /></>),
    Menu: S(<path d="M4 6h16M4 12h16M4 18h16" />),
    Warning: S(<><path d="M12 3l9 16H3z" /><path d="M12 10v4M12 17h.01" /></>),
    Pin: S(<><path d="M12 21s7-6.3 7-11a7 7 0 1 0-14 0c0 4.7 7 11 7 11z" /><circle cx="12" cy="10" r="2.4" /></>),
    Keyboard: S(<><rect x="2" y="6" width="20" height="12" rx="2" /><path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01M7 14h10" /></>),
    Download: S(<><path d="M12 3v12M7 10l5 5 5-5" /><path d="M5 21h14" /></>),
    Chevron: S(<path d="M9 6l6 6-6 6" />),
  };
})();
window.Icon = Icon;
