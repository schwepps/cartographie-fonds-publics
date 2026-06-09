/* Router + app mount. */

function parseHash() {
  let h = window.location.hash.replace(/^#\/?/, "");
  const [path, queryStr] = h.split("?");
  const segs = path.split("/").filter(Boolean);
  const route = segs[0] || "accueil";
  const params = {};
  if (queryStr) queryStr.split("&").forEach((kv) => { const [k, v] = kv.split("="); params[k] = decodeURIComponent(v || ""); });
  return { route, segs, params };
}

function App() {
  const [loc, setLoc] = React.useState(parseHash());
  const mainRef = React.useRef(null);

  React.useEffect(() => {
    const onHash = () => { setLoc(parseHash()); };
    window.addEventListener("hashchange", onHash);
    if (!window.location.hash) window.location.hash = "#/accueil";
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  React.useEffect(() => {
    if (mainRef.current) mainRef.current.focus({ preventScroll: true });
    window.scrollTo({ top: 0, behavior: "auto" });
  }, [loc.route, loc.segs[1]]);

  const go = React.useCallback((path) => { window.location.hash = "#/" + path; }, []);

  const { route, segs, params } = loc;
  let Page;
  if (route === "accueil") Page = <window.HomePage go={go} />;
  else if (route === "graphe") Page = <window.GraphPage params={params} go={go} />;
  else if (route === "fiche") Page = <window.FichePage params={{ siren: segs[1] }} go={go} />;
  else if (route === "flux") Page = <window.FluxPage params={{ focus: segs[1] }} go={go} />;
  else if (route === "recherche") Page = <window.RecherchePage params={params} go={go} />;
  else if (route === "donnees") Page = <window.DonneesPage go={go} />;
  else Page = <window.HomePage go={go} />;

  return (
    <div id="app">
      <a className="skip-link" href="#content">Aller au contenu</a>
      <window.Shell.Header route={segs.join("/")} go={go} />
      <main className="main" id="content" tabIndex={-1} ref={mainRef} role="main" style={{ outline: "none" }}>
        {Page}
      </main>
      <window.Shell.Footer />
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
