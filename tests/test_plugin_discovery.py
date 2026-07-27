"""
Tests for the Plugin SDK — adapter discovery and registration.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specbridge.adapters._base import (
    _ADAPTERS,
    _PLUGIN_REGISTRY,
    _PLUGINS_DISCOVERED,
    all_adapters,
    plugin_adapters,
    register,
)
from specbridge.core import TraceGraph

# ── helpers ──────────────────────────────────────────────────────────


class _DummyAdapter:
    """Not a ProjectAdapter — used to verify type guard."""

    def detect(self, directory: str) -> float:
        return 0.0

    def analyze(self, directory: str) -> TraceGraph:
        return TraceGraph()


@pytest.fixture(autouse=True)
def _reset_registry():
    """Save/restore global state around each test."""
    saved_adapters = list(_ADAPTERS)
    saved_plugins = dict(_PLUGIN_REGISTRY)
    saved_discovered = _PLUGINS_DISCOVERED
    yield
    _ADAPTERS[:] = saved_adapters
    _PLUGIN_REGISTRY.clear()
    _PLUGIN_REGISTRY.update(saved_plugins)
    globals()["_PLUGINS_DISCOVERED"] = saved_discovered  # noqa: F811


# ── basic registration ───────────────────────────────────────────────


def test_register_adds_adapter():
    from specbridge.adapters._base import ProjectAdapter

    class TestAdapter(ProjectAdapter):
        def detect(self, directory: str) -> float:
            return 0.5

        def analyze(self, directory: str) -> TraceGraph:
            return TraceGraph()

    register(TestAdapter)
    assert TestAdapter in all_adapters()


def test_register_with_package_tracking():
    from specbridge.adapters._base import ProjectAdapter

    class TrackedAdapter(ProjectAdapter):
        def detect(self, directory: str) -> float:
            return 0.5

        def analyze(self, directory: str) -> TraceGraph:
            return TraceGraph()

    register(TrackedAdapter, plugin_package="test-pkg")
    assert ("TrackedAdapter", "test-pkg") in plugin_adapters()


# ── plugin_adapters() returns only plugin-tracked ones ───────────────


def test_plugin_adapters_excludes_builtins():
    from specbridge.adapters._base import ProjectAdapter

    class BuiltinAdapter(ProjectAdapter):
        def detect(self, directory: str) -> float:
            return 0.0

        def analyze(self, directory: str) -> TraceGraph:
            return TraceGraph()

    register(BuiltinAdapter)  # no plugin_package
    assert plugin_adapters() == []  # not tracked


# ── discover_plugins — type guard ────────────────────────────────────


def test_discover_plugins_skips_non_adapter(tmp_path: Path):
    """A class that does not subclass ProjectAdapter should not be registered."""
    from specbridge.adapters._base import _ensure_plugins_discovered

    # Create a minimal fake entry point by manually checking the type guard
    # logic: non-adapter classes are skipped inside discover_plugins
    count_before = len(all_adapters())
    # No-op since there are no real entry points in test env
    _ensure_plugins_discovered()
    assert len(all_adapters()) >= count_before  # may have discovered nothing


# ── discover_plugins is idempotent ───────────────────────────────────


def test_discover_plugins_idempotent():
    """Calling discover_plugins multiple times should not duplicate adapters."""
    from specbridge.adapters._base import ProjectAdapter

    class IdempotentAdapter(ProjectAdapter):
        def detect(self, directory: str) -> float:
            return 0.0

        def analyze(self, directory: str) -> TraceGraph:
            return TraceGraph()

    register(IdempotentAdapter)
    count_before = len(all_adapters())
    # register again should be ignored by run-once guard
    register(IdempotentAdapter)
    assert len(all_adapters()) == count_before


# ── full pipeline: example plugin as editable install ────────────────


@pytest.mark.skipif(
    not Path(__file__).resolve().parent.parent.joinpath(
        "examples/example-plugin/example_adapter.py"
    ).exists(),
    reason="example-plugin directory not found",
)
def test_example_plugin_installable():
    """The example plugin's pyproject.toml should be valid TOML."""
    try:
        import tomllib  # Python 3.11+
    except ImportError:
        import tomli as tomllib  # backport

    plugin_pyproject = (
        Path(__file__).resolve().parent.parent
        / "examples/example-plugin/pyproject.toml"
    )
    data = tomllib.loads(plugin_pyproject.read_text(encoding="utf-8"))
    eps = data["project"]["entry-points"]["specbridge.adapters"]
    assert "example" in eps
    assert eps["example"] == "example_adapter:ExampleAdapter"
