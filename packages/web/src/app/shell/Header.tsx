import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { navItems } from "../routes";
import { Button, Close, Icons, Menu, Scale, Search } from "../../lib/ui";
import { MarianneBloc } from "./MarianneBloc";

const SERVICE_TITLE = "Cartographie des Fonds Publics";

/**
 * App header — Marianne bloc-marque, service title/tagline, quick tool links, and the main
 * navigation (registry-driven via `navItems`, so adding a feature adds its nav entry). On narrow
 * viewports the nav collapses behind a burger into a slide-in panel. Ported from `design/`
 * (`shell.jsx`), wired to react-router for client-side navigation.
 */
export function Header() {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const closeMenu = () => setMenuOpen(false);

  const isActive = (to: string) =>
    to === "/" ? pathname === "/" : pathname === to || pathname.startsWith(`${to}/`);

  return (
    <header className="header" role="banner">
      <div className="fr-container">
        <div className="header__body">
          <div className="header__brand">
            <MarianneBloc />
            <span className="header__service">
              <span className="header__service-title">{SERVICE_TITLE}</span>
              <span className="header__service-tagline">{t("shell.tagline")}</span>
            </span>
          </div>
          <div className="header__tools">
            <Link className="header__tool-link" to="/search" aria-label={t("shell.search")}>
              <Search />
              <span>{t("shell.search")}</span>
            </Link>
            <Link className="header__tool-link" to="/sources" aria-label={t("shell.data")}>
              <Scale />
              <span>{t("shell.data")}</span>
            </Link>
            <Button
              variant="tertiary"
              iconOnly
              className="burger"
              aria-label={t("shell.openMenu")}
              aria-expanded={menuOpen}
              aria-controls="main-nav"
              onClick={() => setMenuOpen(true)}
            >
              <Menu />
            </Button>
          </div>
        </div>
      </div>

      <nav
        className={`nav ${menuOpen ? "open" : ""}`}
        aria-label={t("shell.mainMenu")}
        id="main-nav"
      >
        <div className="fr-container" style={{ padding: 0 }}>
          {menuOpen ? (
            <Button
              variant="tertiary"
              iconOnly
              className="nav-close"
              aria-label={t("shell.closeMenu")}
              onClick={closeMenu}
            >
              <Close />
            </Button>
          ) : null}
          <ul className="nav__list">
            {navItems.map((item) => {
              const Icon = item.icon ? Icons[item.icon] : null;
              const active = isActive(item.to);
              return (
                <li key={item.to}>
                  <Link
                    className="nav__link"
                    to={item.to}
                    aria-current={active ? "page" : undefined}
                    aria-label={item.label}
                    onClick={closeMenu}
                  >
                    {Icon ? <Icon /> : null}
                    <span className="nav__label-full">{item.label}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      </nav>
      {menuOpen ? <div className="nav-scrim" aria-hidden="true" onClick={closeMenu} /> : null}
    </header>
  );
}
