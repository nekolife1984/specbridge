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

    After merging, spec IDs are normalized: if the same spec exists with
    both a ``spec::X`` ID (from SpectraAdapter) and a heuristic ID
    (e.g. ``docs.auth.X``), they are folded into a single canonical node.
    """
    merged = TraceGraph()
    for g in graphs:
        for nid, node in g.nodes.items():
            merged.nodes[nid] = node
        for e in g.edges:
            merged.edges.append(e)

    # Normalize spec IDs: fold spec::X → canonical heuristic IDs
    _normalize_spec_ids(merged)

    return merged


def _normalize_spec_ids(graph: TraceGraph) -> None:
    """Fold duplicate spec nodes with different ID formats into one.

    HeuristicAdapter produces IDs like ``docs.auth.1.1``.
    SpectraAdapter produces IDs like ``spec::1.1`` using ``spec::`` prefix.

    When both refer to the same spec number (e.g. ``1.1``), the
    ``spec::`` node is merged into the heuristic node.
    """
    from specbridge.core import NodeType, TraceNode

    # 1. Collect all spec nodes; track spec:: nodes separately
    spec_nodes: dict[str, TraceNode] = {}
    spec_prefix_nodes: dict[str, TraceNode] = {}  # num → node  (e.g. "1.1" → node)
    heuristic_nodes: dict[str, list[TraceNode]] = {}  # num → [nodes]

    for nid, node in list(graph.nodes.items()):
        if node.type != NodeType.SPEC:
            continue
        spec_nodes[nid] = node
        if nid.startswith("spec::"):
            num = nid[len("spec::"):]
            spec_prefix_nodes[num] = node
        else:
            # Extract trailing numeric suffix like "1.1" from "docs.auth.1.1"
            import re
            m = re.search(r"\.(\d[\d.]*)$", nid)
            if m:
                num = m.group(1)
                heuristic_nodes.setdefault(num, []).append(node)
            # Also index by title to catch non-numeric IDs
            title_key = node.title.lower().strip()
            if title_key:
                heuristic_nodes.setdefault(f"__title__:{title_key}", []).append(node)

    # 2. For each spec:: node, find a matching heuristic node
    aliases: dict[str, str] = {}  # spec:: ID → canonical heuristic ID
    nodes_to_remove: set[str] = set()

    for num, sp_node in spec_prefix_nodes.items():
        candidates = heuristic_nodes.get(num, [])
        if not candidates:
            # Try partial suffix match: "1.1" inside "auth.1.1" or "2.1"
            import re
            for h_id, h_nodes in heuristic_nodes.items():
                if h_id.startswith("__title__:"):
                    continue
                if h_id.endswith(f".{num}") or num.endswith(f".{h_id}") or num in h_id or h_id in num:
                    candidates.extend(h_nodes)

        if candidates:
            # Pick the first heuristic candidate as canonical
            canonical = candidates[0]
            alias_id = sp_node.id
            canonical_id = canonical.id

            if alias_id != canonical_id:
                aliases[alias_id] = canonical_id
                nodes_to_remove.add(alias_id)
                # Propagate metadata
                existing_aliases = canonical.metadata.get("aliases", [])
                if alias_id not in existing_aliases:
                    canonical.metadata["aliases"] = existing_aliases + [alias_id]

                if sp_node.title and not canonical.title:
                    canonical.title = sp_node.title
                if sp_node.confidence > canonical.confidence:
                    canonical.confidence = sp_node.confidence

    # 3. Redirect edges from alias IDs to canonical IDs
    for edge in graph.edges:
        if edge.src_id in aliases:
            edge.src_id = aliases[edge.src_id]
        if edge.dst_id in aliases:
            edge.dst_id = aliases[edge.dst_id]

    # 4. Remove alias nodes
    for nid in nodes_to_remove:
        graph.nodes.pop(nid, None)
