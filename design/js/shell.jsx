/* App shell — DSFR Marianne header, nav, footer. → window.Shell */

const NAV = [
  { to: "accueil", label: "Accueil", Icon: window.Icon.Home },
  { to: "graphe", label: "Graphe institutionnel", short: "Graphe", Icon: window.Icon.Graph },
  { to: "recherche", label: "Recherche", Icon: window.Icon.Search },
  { to: "flux", label: "Flux de financement", short: "Flux", Icon: window.Icon.Flow },
  { to: "donnees", label: "Données & licences", short: "Données", Icon: window.Icon.Scale },
];

function MarianneBloc() {
  return (
    <a href="#/accueil" className="row-center" style={{ textDecoration: "none" }} title="Accueil — Cartographie des Fonds Publics">
      <span className="tricolore" aria-hidden="true"><i className="bleu"></i><i className="blanc"></i><i className="rouge"></i></span>
      <span className="bloc-marque">
        <span className="bloc-marque__rf">République<br />Française</span>
      </span>
    </a>
  );
}

function Header({ route, go }) {
  const [menuOpen, setMenuOpen] = React.useState(false);
  React.useEffect(() => { setMenuOpen(false); }, [route]);
  const current = route.split("/")[0];

  return (
    <header className="header" role="banner">
      <div className="fr-container">
        <div className="header__body">
          <div className="header__brand">
            <MarianneBloc />
            <span className="header__service">
              <span className="header__service-title">Cartographie des Fonds Publics</span>
              <span className="header__service-tagline">Comprendre l’usage des fonds publics</span>
            </span>
          </div>
          <div className="header__tools">
            <a className="header__tool-link" href="#/recherche"><window.Icon.Search /><span>Rechercher</span></a>
            <a className="header__tool-link" href="#/donnees"><window.Icon.Scale /><span>Données</span></a>
            <button className="btn btn--tertiary btn--icon-only burger" aria-label="Ouvrir le menu" aria-expanded={menuOpen} onClick={() => setMenuOpen(true)}>
              <window.Icon.Menu />
            </button>
          </div>
        </div>
      </div>
      <nav className="nav" aria-label="Menu principal" id="main-nav">
        <div className="fr-container" style={{ padding: 0 }}>
          {menuOpen ? <button className="btn btn--tertiary btn--icon-only nav-close" aria-label="Fermer le menu" onClick={() => setMenuOpen(false)}><window.Icon.Close /></button> : null}
          <ul className="nav__list">
            {NAV.map((n) => {
              const active = current === n.to;
              return (
                <li key={n.to}>
                  <a className="nav__link" href={`#/${n.to}`} aria-current={active ? "page" : undefined}>
                    <n.Icon />
                    <span className="nav__label-full">{n.label}</span>
                    <span className="nav__label-short" style={{ display: "none" }}>{n.short || n.label}</span>
                  </a>
                </li>
              );
            })}
          </ul>
        </div>
      </nav>
      <div className={`nav ${menuOpen ? "" : ""}`}></div>
      {menuOpen ? <div className="nav-scrim" onClick={() => setMenuOpen(false)}></div> : null}
    </header>
  );
}

function Footer() {
  return (
    <footer className="footer" role="contentinfo">
      <div className="fr-container">
        <div className="footer__body">
          <div>
            <MarianneBloc />
            <p className="footer__desc">
              Cartographie des Fonds Publics réutilise des données publiques ouvertes pour rendre lisibles les liens, les financements et les mandats des institutions françaises.
            </p>
          </div>
          <nav className="footer__links" aria-label="Liens de pied de page">
            <a href="#/accueil">Accueil</a>
            <a href="#/graphe">Graphe institutionnel</a>
            <a href="#/recherche">Recherche</a>
            <a href="#/flux">Flux de financement</a>
            <a href="#/donnees">Données & licences</a>
            <a href="#/donnees">Méthodologie</a>
            <a href="https://www.etalab.gouv.fr/licence-ouverte-open-licence/" target="_blank" rel="noopener">Licence Ouverte 2.0</a>
            <a href="#/donnees">Accessibilité : partielle</a>
            <a href="#/donnees">Code source (AGPL-3.0)</a>
          </nav>
        </div>
        <div className="footer__bottom">
          <a href="#/donnees">Mentions légales</a>
          <a href="#/donnees">Données personnelles</a>
          <a href="#/donnees">Gestion des cookies</a>
          <a href="#/donnees">Accessibilité : partiellement conforme</a>
          <span className="fr-xs text-mention">© République Française {new Date().getFullYear()} — Sauf mention contraire, contenus sous Licence Ouverte 2.0</span>
        </div>
      </div>
    </footer>
  );
}

window.Shell = { Header, Footer, NAV };
