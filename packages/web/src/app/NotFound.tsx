import { Link } from "react-router-dom";

/** Catch-all 404, rendered inside the Layout so header/footer stay visible. */
export function NotFound() {
  return (
    <section className="fr-py-6w">
      <h1 className="fr-h1">Page introuvable</h1>
      <p className="fr-text--lead">La page que vous cherchez n'existe pas.</p>
      <Link className="fr-btn" to="/">
        Retour à l'accueil
      </Link>
    </section>
  );
}
