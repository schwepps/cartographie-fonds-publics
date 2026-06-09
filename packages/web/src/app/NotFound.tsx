import { Link } from "react-router-dom";

/** Catch-all 404, rendered inside the Layout so header/footer stay visible. */
export function NotFound() {
  return (
    <section>
      <h1 className="fr-h1">Page introuvable</h1>
      <p className="fr-lead">La page que vous cherchez n'existe pas.</p>
      <Link className="btn btn--primary" to="/">
        Retour à l'accueil
      </Link>
    </section>
  );
}
