"""Tests for adapter composition (merge mode) in _base.py and CLI."""

from __future__ import annotations

from pathlib import Path

import pytest

from specbridge.adapters._base import (
    detect_all,
    merge_graphs,
)
from specbridge.core import (
    EdgeRelation,
    EdgeStrength,
    NodeType,
    SourceRef,
    TraceEdge,
    TraceGraph,
    TraceNode,
)


class TestDetectAll:
    """detect_all returns all matching adapters."""

    def test_returns_multiple_adapters(self, tmp_project_spectra: Path) -> None:
        """Spectra project returns both spectra + heuristic adapters."""
        scored = detect_all(str(tmp_project_spectra))
        assert len(scored) >= 2
        scores = [s for s, _ in scored]
        # Spectra (0.95) should be first, heuristic (0.8) second
        assert scores[0] >= scores[1]

    def test_empty_dir(self, tmp_path: Path) -> None:
        """Empty directory returns empty list."""
        empty = tmp_path / "empty"
        empty.mkdir()
        scored = detect_all(str(empty))
        assert scored == []

    def test_detect_all_order(self, tmp_project_heuristic: Path) -> None:
        """Results are sorted descending by score."""
        scored = detect_all(str(tmp_project_heuristic))
        if len(scored) > 1:
            for i in range(len(scored) - 1):
                assert scored[i][0] >= scored[i + 1][0]


class TestMergeGraphs:
    """Graph merging logic."""

    def make_graph_a(self) -> TraceGraph:
        g = TraceGraph()
        g.add_node(TraceNode(id="spec1", type=NodeType.SPEC, title="Auth",
                             source=SourceRef(file="docs/auth.md"),
                             framework_origin="heuristic"))
        g.add_node(TraceNode(id="login.py", type=NodeType.CODE, title="login",
                             source=SourceRef(file="src/auth/login.py"),
                             framework_origin="heuristic"))
        g.add_edge(TraceEdge(src_id="login.py", dst_id="spec1",
                             relation=EdgeRelation.IMPLEMENTS,
                             strength=EdgeStrength.INFERRED))
        return g

    def make_graph_b(self) -> TraceGraph:
        g = TraceGraph()
        g.add_node(TraceNode(id="spec1", type=NodeType.SPEC, title="User Auth",
                             source=SourceRef(file="docs/auth.md"),
                             framework_origin="spectra"))
        g.add_node(TraceNode(id="token.py", type=NodeType.CODE, title="token",
                             source=SourceRef(file="src/auth/token.py"),
                             framework_origin="spectra"))
        g.add_edge(TraceEdge(src_id="token.py", dst_id="spec1",
                             relation=EdgeRelation.IMPLEMENTS,
                             strength=EdgeStrength.EXPLICIT))
        return g

    def test_merge_union_nodes(self) -> None:
        """Merged graph contains all unique nodes."""
        ga = self.make_graph_a()
        gb = self.make_graph_b()
        merged = merge_graphs([ga, gb])
        assert len(merged.nodes) == 3  # spec1, login.py, token.py
        assert "spec1" in merged.nodes
        assert "login.py" in merged.nodes
        assert "token.py" in merged.nodes

    def test_merge_concatenates_edges(self) -> None:
        """Edges from both graphs are present."""
        ga = self.make_graph_a()
        gb = self.make_graph_b()
        merged = merge_graphs([ga, gb])
        assert len(merged.edges) == 2

    def test_merge_second_overwrites(self) -> None:
        """Later graph's node overwrites earlier on ID collision."""
        ga = self.make_graph_a()
        gb = self.make_graph_b()
        merged = merge_graphs([ga, gb])
        # spec1 from graph_b (spectra) should overwrite graph_a (heuristic)
        assert merged.nodes["spec1"].framework_origin == "spectra"
        assert merged.nodes["spec1"].title == "User Auth"

    def test_merge_empty(self) -> None:
        """Merging empty list returns empty graph."""
        merged = merge_graphs([])
        assert len(merged.nodes) == 0
        assert len(merged.edges) == 0

    def test_merge_single(self) -> None:
        """Merging single graph returns its content."""
        ga = self.make_graph_a()
        merged = merge_graphs([ga])
        assert len(merged.nodes) == 2
        assert len(merged.edges) == 1

    def test_merge_node_types(self) -> None:
        """Node types are preserved after merge."""
        ga = self.make_graph_a()
        merged = merge_graphs([ga])
        specs = merged.nodes_by_type(NodeType.SPEC)
        codes = merged.nodes_by_type(NodeType.CODE)
        assert len(specs) == 1
        assert len(codes) == 1


class TestMergeCLI:
    """CLI --merge flag integration (tested via adapter code path)."""

    def test_merge_produces_graph(self, tmp_project_spectra: Path) -> None:
        """Merge mode works and produces a valid graph."""
        from specbridge.adapters import detect_all, merge_graphs

        scored = detect_all(str(tmp_project_spectra))
        graphs = [adapter.analyze(str(tmp_project_spectra)) for _, adapter in scored]
        merged = merge_graphs(graphs)
        assert isinstance(merged, TraceGraph)
        assert len(merged.nodes) > 0
        assert len(merged.edges) > 0
