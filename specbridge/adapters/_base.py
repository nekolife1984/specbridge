"""Base adapter interface + adapter registry (no circular-import-safe module)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from specbridge.core import TraceGraph


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


_ADAPTERS: list[type[ProjectAdapter]] = []


def register(adapter: type[ProjectAdapter]) -> type[ProjectAdapter]:
    """Decorator to register an adapter class."""
    _ADAPTERS.append(adapter)
    return adapter


def all_adapters() -> list[type[ProjectAdapter]]:
    return list(_ADAPTERS)


def detect_adapter(directory: str) -> ProjectAdapter | None:
    """Pick the best adapter for *directory*."""
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
