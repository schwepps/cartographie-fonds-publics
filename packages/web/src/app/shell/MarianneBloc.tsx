import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

/**
 * Official "bloc-marque" — the tricolore flag + « République Française » text mark, linking home.
 * Shared by the header and footer. Ported from the `design/` export (`shell.jsx`).
 */
export function MarianneBloc() {
  const { t } = useTranslation();
  return (
    <Link
      to="/"
      className="row-center"
      style={{ textDecoration: "none" }}
      title={t("shell.homeTitle")}
    >
      <span className="tricolore" aria-hidden="true">
        <i className="bleu" />
        <i className="blanc" />
        <i className="rouge" />
      </span>
      <span className="bloc-marque">
        <span className="bloc-marque__rf">
          République
          <br />
          Française
        </span>
      </span>
    </Link>
  );
}
