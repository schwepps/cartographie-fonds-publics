"""Connector for ``platform: rest`` sources — the PISTE/Légifrance API (FSC-27, manual-first).

The registry source ``legifrance_attributions`` is ``platform: rest`` with ``auth: clé API PISTE``.
This connector registers that platform with the factory and reads the PISTE OAuth2 credentials, but
**Phase-1 attributions are editorial**: the curated mandates come from a committed YAML transformed
by ``ingestion.transforms.legifrance_attributions`` (the offline source of truth). Live discovery
(PISTE OAuth2 token → Légifrance LODA search for « décret d'attribution » → text→entity linking) is
the documented **scaling path**, tracked in **FSC-66** — so ``discover``/``extract`` fail loud with
an actionable message rather than silently doing nothing. This keeps the lowest-priority Phase-1
connector lean while honouring the registry's ``platform: rest`` (today ``get_connector`` would
otherwise raise ``UnknownPlatformError``) and reading the secret from the env (never committed).

``validate``/``snapshot`` delegate to the shared helpers so the class is concrete and ready for the
FSC-66 live path; ``stage`` defers to the cross-source loader (FSC-35), like the other connectors.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from ..snapshot import write_snapshot
from ..validation import validate_extract
from . import Connector, register

# PISTE uses OAuth2 client-credentials; both are required to mint a bearer token. Server/CI only,
# never the frontend (see .env.example). Read from the env, never hardcoded.
PISTE_CLIENT_ID_ENV = "PISTE_CLIENT_ID"
PISTE_CLIENT_SECRET_ENV = "PISTE_CLIENT_SECRET"

# PISTE / Légifrance API hosts (platform infrastructure, not a document id). Documented for FSC-66.
PISTE_TOKEN_URL = "https://oauth.piste.gouv.fr/api/oauth/token"
LEGIFRANCE_API_BASE = "https://api.piste.gouv.fr/dila/legifrance/lf-engine-app"

_SCALING_MSG = (
    "Live PISTE/Légifrance extraction is not implemented yet — it is the documented scaling path "
    "(FSC-66): PISTE OAuth2 token -> Légifrance LODA search for « décret d'attribution » -> "
    "text->entity linking, human-reviewed. Phase-1 ministerial attributions are EDITORIAL: see "
    "ingestion.transforms.legifrance_attributions (data/attributions/ministres.yaml). Set "
    f"{PISTE_CLIENT_ID_ENV}/{PISTE_CLIENT_SECRET_ENV} and implement FSC-66 to enable the live path."
)


@register("rest")
class RestConnector(Connector):
    """PISTE/Légifrance connector scaffold. Registers the platform + reads OAuth2 credentials."""

    def __init__(self) -> None:
        # Empty string env vars (the .env.example placeholders) count as absent.
        self._client_id = os.environ.get(PISTE_CLIENT_ID_ENV) or None
        self._client_secret = os.environ.get(PISTE_CLIENT_SECRET_ENV) or None
        self._source_id: str = "legifrance_attributions"
        self._license: str | None = None
        self._source_ref: str | None = None

    @property
    def has_credentials(self) -> bool:
        """True iff both PISTE OAuth2 credentials are present (needed for the live FSC-66 path)."""
        return bool(self._client_id and self._client_secret)

    # -- discover ----------------------------------------------------------- #
    def discover(self, _source: dict[str, Any]) -> dict[str, Any]:
        """Defer to the editorial transform — live PISTE discovery is FSC-66 (fails loud).

        Provenance (source id, licence, resource ref) is captured at its real point of use when
        FSC-66 implements the live discover→extract→snapshot loop, not here where it would be dead.
        """
        raise NotImplementedError(_SCALING_MSG)

    # -- extract ------------------------------------------------------------ #
    def extract(self, resolved: dict[str, Any]) -> bytes:
        raise NotImplementedError(_SCALING_MSG)

    # -- validate ----------------------------------------------------------- #
    def validate(self, raw: bytes, schema_ref: str | None) -> None:
        """Validate against any Table Schema (skipped when none — Légifrance has no schema)."""
        validate_extract(raw, source_id=self._source_id, schema_ref=schema_ref)

    # -- snapshot ----------------------------------------------------------- #
    def snapshot(self, raw: bytes, source_id: str) -> str:
        """Persist a provenance-tagged snapshot of the (JSON) PISTE extract; return its path."""
        path = write_snapshot(
            raw,
            source_id=source_id,
            extracted_at=datetime.now(tz=UTC).isoformat(),
            source_ref=self._source_ref or LEGIFRANCE_API_BASE,
            license=self._license,
            schema_ref=None,
            fmt="json",
        )
        return str(path)

    # -- stage -------------------------------------------------------------- #
    def stage(self, snapshot_uri: str, source_id: str) -> None:
        raise NotImplementedError(
            "Curated loading is a cross-source, provenance-scoped rebuild done after snapshots "
            "exist — see `ingestion.load` / `make load` (FSC-35), not a per-source stage()."
        )
