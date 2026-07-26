"""Base adapter interface + adapter registry with plugin discovery.

## Plugin SDK

External packages can register adapters by defining an entry point in
their ``pyproject.toml``::

    [project.entry-points."specbridge.adapters"]
    my_adapter = "my_package.my_adapter:MyAdapter"

The class must subclass ``ProjectAdapter`` and does **not** need the
``@register`` decorator (the entry-point loader calls ``register()``
automatically on instantiation).

See ``examples/example-plugin/`` for a complete working example.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from importlib.metadata import entry_points

from specbridge.core import TraceGraph

# ---------------------------------------------------------------------------
# Built-in adapter list (seeded by @register, extended by plugin discovery)
# ---------------------------------------------------------------------------

_ADAPTERS: list[type[ProjectAdapter]] = []

# Track plugin origin for the `specbridge plugins` command
_PLUGIN_REGISTRY: dict[str, str] = {}  # adapter class name → package name

# Lazy-discovery guard
_PLUGINS_DISCOVERED = False

# ---------------------------------------------------------------------------
# ProjectAdapter ABC
# ---------------------------------------------------------------------------


class ProjectAdapter(ABC):
    """Reads a project's specs/code and builds a TraceGraph."""

    @abstractmethod
    def detect(self, directory: str) -> float:
        """Return a confidence score (0-1) that this adapter handles *directory*.
        Adapters are tried in descending confidence order; the first with >0 is used."""
        ...

    @abstractmethod
    def analyze(self, directory: str) -> TraceGraph:
        ...


# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------


def register(adapter: type[ProjectAdapter], *, plugin_package: str = "") -> type[ProjectAdapter]:
    """Decorator to register an adapter class.

    Idempotent — registering the same class twice is a no-op.

    Args:
        adapter: The ProjectAdapter subclass to register.
        plugin_package: Optional name of the package that provides this adapter
            (used for ``specbridge plugins`` display).
    """
    if adapter not in _ADAPTERS:
        _ADAPTERS.append(adapter)
    if plugin_package and adapter.__name__ not in _PLUGIN_REGISTRY:
        _PLUGIN_REGISTRY[adapter.__name__] = plugin_package
    return adapter


def all_adapters() -> list[type[ProjectAdapter]]:
    _ensure_plugins_discovered()
    return list(_ADAPTERS)


def plugin_adapters() -> list[tuple[str, str]]:
    """Return ``[(class_name, package_name), ...]`` for plugin-provided adapters only."""
    return list(_PLUGIN_REGISTRY.items())


# ---------------------------------------------------------------------------
# Lazy discovery
# ---------------------------------------------------------------------------


def _ensure_plugins_discovered() -> None:
    """Run ``discover_plugins()`` once, on first adapter access."""
    global _PLUGINS_DISCOVERED  # noqa: PLW0603
    if not _PLUGINS_DISCOVERED:
        discover_plugins()
        _PLUGINS_DISCOVERED = True


# ---------------------------------------------------------------------------
# Plugin discovery — auto-load adapters from installed packages
# ---------------------------------------------------------------------------


def discover_plugins() -> int:
    """Scan installed packages for the ``specbridge.adapters`` entry point group.

    Each discovered class is automatically registered.  Already-registered
    classes are skipped (idempotent).  Returns the number of newly loaded
    plugins.
    """
    discovered = entry_points(group="specbridge.adapters")
    count = 0
    for ep in discovered:
        try:
            cls = ep.load()
        except Exception:  # noqa: BLE001  —  a flaky plugin must not crash us
            continue
        if not (isinstance(cls, type) and issubclass(cls, ProjectAdapter)):
            continue
        if cls in _ADAPTERS:
            continue
        register(cls, plugin_package=ep.dist.name if ep.dist else ep.module)
        count += 1
    return count


# ---------------------------------------------------------------------------
# Adapter selection
# ---------------------------------------------------------------------------


def detect_adapter(directory: str) -> ProjectAdapter | None:
    """Pick the best adapter for *directory*."""
    _ensure_plugins_discovered()
    scored = []
    for cls in _ADAPTERS:
        inst = cls()
        score = inst.detect(directory)
        if score > 0:
            scored.append((score, inst))
    if not scored:
        return None
    scored.sort(key=lambda x: -x[0])
    return scored[0][1]


def detect_all(directory: str) -> list[tuple[float, ProjectAdapter]]:
    """Return ALL adapters with positive detection scores, sorted descending.

    Use this for merge mode where multiple adapters contribute to one graph.
    """
    _ensure_plugins_discovered()
    scored = []
    for cls in _ADAPTERS:
        inst = cls()
        score = inst.detect(directory)
        if score > 0:
            scored.append((score, inst))
    scored.sort(key=lambda x: -x[0])
    return scored


def merge_graphs(graphs: list[TraceGraph]) -> TraceGraph:
    """Merge multiple TraceGraphs into one (union of nodes + edges).

    Later graphs' nodes overwrite earlier ones with the same ID.
    Edges from all graphs are concatenated.
    """
    merged = TraceGraph()
    for g in graphs:
        for nid, node in g.nodes.items():
            merged.nodes[nid] = node
        for e in g.edges:
            merged.edges.append(e)
    return merged
