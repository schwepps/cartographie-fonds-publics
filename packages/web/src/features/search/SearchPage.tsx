import { useSearchParams } from "react-router-dom";

export default function SearchPage() {
  const [params] = useSearchParams();
  const query = params.get("q")?.trim() ?? "";

  return (
    <section>
      <h1 className="fr-h1">Recherche</h1>
      {query ? (
        <p>
          Résultats pour «&nbsp;<strong>{query}</strong>&nbsp;» — à implémenter (recherche Supabase
          plein-texte / RPC).
        </p>
      ) : (
        <p className="fr-text--lead">Saisissez un terme dans la barre de recherche.</p>
      )}
    </section>
  );
}
