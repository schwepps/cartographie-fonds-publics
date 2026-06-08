"""Offline tests for the self-registering connector factory (FSC-14).

Two layers: pure unit tests (an autouse fixture swaps the module-level registry for an empty
dict and suppresses the real scan) plus a few tests that drive the *real* ``pkgutil`` scan
over a throwaway package built on ``tmp_path`` — covering discovery, skip rules, and import
failure attribution without polluting the production ``connectors`` package.
"""

import sys
from typing import Any

import pytest
from ingestion.connectors import factory
from ingestion.connectors.base import Connector
from ingestion.connectors.factory import (
    ConnectorImportError,
    UnknownPlatformError,
    get_connector,
    register,
)
from ingestion.registry import Source


@pytest.fixture(autouse=True)
def isolate_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Give each test an empty registry and skip the real package scan."""
    monkeypatch.setattr(factory, "_REGISTRY", {})
    monkeypatch.setattr(factory, "_discovered", True)


def _stub_cls() -> type[Connector]:
    class _Stub(Connector):
        def discover(self, source: dict[str, Any]) -> dict[str, Any]:
            return {}

        def extract(self, resolved: dict[str, Any]) -> bytes:
            return b""

        def validate(self, raw: bytes, schema_ref: str | None) -> None:
            return None

        def snapshot(self, raw: bytes, source_id: str) -> str:
            return ""

        def stage(self, snapshot_uri: str, source_id: str) -> None:
            return None

    return _Stub


def _source(platform: str, source_id: str = "s") -> Source:
    return Source(id=source_id, raw={"id": source_id, "platform": platform})


def test_two_stubs_register_and_dispatch() -> None:
    register("alpha")(type("Alpha", (_stub_cls(),), {}))
    register("beta")(type("Beta", (_stub_cls(),), {}))

    a = get_connector(_source("alpha"))
    b = get_connector(_source("beta"))

    assert type(a).__name__ == "Alpha"
    assert type(b).__name__ == "Beta"
    assert isinstance(a, Connector)
    assert isinstance(b, Connector)


def test_unknown_platform_fails_loud() -> None:
    register("alpha")(_stub_cls())

    with pytest.raises(UnknownPlatformError) as ei:
        get_connector(_source("ghost", source_id="bad_src"))

    msg = str(ei.value)
    assert "ghost" in msg  # offending platform
    assert "bad_src" in msg  # offending source id
    assert "alpha" in msg  # lists known platforms


def test_missing_platform_key_fails_loud() -> None:
    src = Source(id="np", raw={"id": "np"})  # no platform key -> ""

    with pytest.raises(UnknownPlatformError, match="no usable platform"):
        get_connector(src)


def test_non_string_platform_fails_loud() -> None:
    register("alpha")(_stub_cls())
    src = Source(id="weird", raw={"id": "weird", "platform": ["not", "a", "str"]})

    with pytest.raises(UnknownPlatformError, match="no usable platform"):
        get_connector(src)


def test_duplicate_registration_raises() -> None:
    register("dup")(_stub_cls())

    with pytest.raises(ValueError, match="Duplicate connector for platform 'dup'"):
        register("dup")(_stub_cls())


def test_registration_is_case_sensitive() -> None:
    register("Alpha")(_stub_cls())

    with pytest.raises(UnknownPlatformError):
        get_connector(_source("alpha"))


def test_real_discovery_runs_and_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Auto-discovery is wired and a no-op on the second call.

    Uses a copy of the real registry (not the isolated empty one) and re-enables the scan;
    asserts no specific connector exists, so it stays green before any connector ships.
    """
    monkeypatch.setattr(factory, "_REGISTRY", dict(factory._REGISTRY))
    monkeypatch.setattr(factory, "_discovered", False)

    factory._discover_connectors()
    snapshot = dict(factory._REGISTRY)
    factory._discover_connectors()  # second call: no-op, no duplicates, no errors

    assert snapshot == factory._REGISTRY


# --- real-scan tests: drive the actual pkgutil/importlib discovery over a temp package ---

_GOOD_MODULE = """\
from ingestion.connectors import Connector, register


@register("tmpplat")
class TmpConnector(Connector):
    def discover(self, source): return {}
    def extract(self, resolved): return b""
    def validate(self, raw, schema_ref): return None
    def snapshot(self, raw, source_id): return ""
    def stage(self, snapshot_uri, source_id): return None
"""


def _write_pkg(tmp_path, pkgname: str, files: dict[str, str]) -> None:
    pkg = tmp_path / pkgname
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    for fname, content in files.items():
        (pkg / fname).write_text(content)


def _purge_modules(prefix: str) -> None:
    for name in [m for m in sys.modules if m == prefix or m.startswith(f"{prefix}.")]:
        sys.modules.pop(name, None)


def test_real_scan_registers_connector_and_skips_machinery(tmp_path, monkeypatch) -> None:
    # base.py and _private.py raise if imported — proving the scan actually skips them.
    _write_pkg(
        tmp_path,
        "tmp_connectors_ok",
        {
            "good.py": _GOOD_MODULE,
            "base.py": "raise AssertionError('base must be skipped')\n",
            "_private.py": "raise AssertionError('underscore modules must be skipped')\n",
        },
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(factory, "_REGISTRY", {})
    monkeypatch.setattr(factory, "_discovered", False)

    try:
        factory._discover_connectors("tmp_connectors_ok")
        assert "tmpplat" in factory._REGISTRY  # good.py picked up by the real scan
    finally:
        _purge_modules("tmp_connectors_ok")


def test_broken_connector_module_raises_typed_error(tmp_path, monkeypatch) -> None:
    _write_pkg(
        tmp_path,
        "tmp_connectors_broken",
        {"boom.py": "raise RuntimeError('kaboom at import')\n"},
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(factory, "_REGISTRY", {})
    monkeypatch.setattr(factory, "_discovered", False)

    try:
        with pytest.raises(ConnectorImportError, match="boom"):
            factory._discover_connectors("tmp_connectors_broken")
    finally:
        _purge_modules("tmp_connectors_broken")
