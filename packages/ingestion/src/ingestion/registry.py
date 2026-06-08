"""Load and query the source registry. The ONLY place sources are defined.

Golden rule (see CLAUDE.md): never hardcode dataset slugs/URLs elsewhere.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# Default assumes the editable workspace layout (repo-root/packages/ingestion/src/ingestion/).
# `CFP_REGISTRY_PATH` overrides it for installed/non-editable environments where the
# parents[4] walk would not point at the repo root.
_DEFAULT_REGISTRY_PATH = (
    Path(__file__).resolve().parents[4] / "data" / "registry" / "sources-registry.yaml"
)
REGISTRY_PATH = Path(os.environ.get("CFP_REGISTRY_PATH", _DEFAULT_REGISTRY_PATH))


@dataclass(frozen=True)
class Source:
    id: str
    raw: dict[str, Any]

    @property
    def layer(self) -> str:
        return self.raw.get("layer", "")

    @property
    def discovery(self) -> dict[str, Any]:
        return self.raw.get("discovery", {})


def load_registry(path: Path | str = REGISTRY_PATH) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def sources(path: Path | str = REGISTRY_PATH) -> list[Source]:
    data = load_registry(path)
    return [Source(id=s["id"], raw=s) for s in data.get("sources", [])]


def get_source(source_id: str, path: Path | str = REGISTRY_PATH) -> Source:
    for s in sources(path):
        if s.id == source_id:
            return s
    raise KeyError(f"Unknown source id: {source_id!r}")
