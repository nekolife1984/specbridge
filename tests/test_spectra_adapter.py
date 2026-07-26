"""Tests for spectra adapter (adapters/spectra.py)."""

from __future__ import annotations

from pathlib import Path

from specbridge.adapters.spectra import SpectraAdapter
from specbridge.core import NodeType, TraceGraph


class TestSpectraDetect:
    """SpectraAdapter.detect() scoring."""

    def test_detect_with_mapping(self, tmp_project_spectra: Path) -> None:
        """trace-mapping.yaml present → 0.95."""
        adapter = SpectraAdapter()
        score = adapter.detect(str(tmp_project_spectra))
        assert score == 0.95

    def test_detect_without_mapping(self, tmp_project_heuristic: Path) -> None:
        """No trace-mapping.yaml and no @impl tags → 0.0 (no longer a fallback)."""
        adapter = SpectraAdapter()
        score = adapter.detect(str(tmp_project_heuristic))
        assert score == 0.0


class TestSpectraAnalyze:
    """SpectraAdapter.analyze() graph construction."""

    def test_analyze_full_graph(self, tmp_project_spectra: Path) -> None:
        """Full analyze produces nodes and edges."""
        adapter = SpectraAdapter()
        graph = adapter.analyze(str(tmp_project_spectra))
        assert isinstance(graph, TraceGraph)
        assert len(graph.nodes) > 0
        assert len(graph.edges) > 0

    def test_analyze_spec_nodes(self, tmp_project_spectra: Path) -> None:
        """Spec nodes exist from trace-mapping.yaml and <!-- @spec --> tags."""
        adapter = SpectraAdapter()
        graph = adapter.analyze(str(tmp_project_spectra))
        specs = graph.nodes_by_type(NodeType.SPEC)
        assert len(specs) >= 1

    def test_analyze_code_nodes(self, tmp_project_spectra: Path) -> None:
        """Code nodes exist from @impl tags and trace-mapping code refs."""
        adapter = SpectraAdapter()
        graph = adapter.analyze(str(tmp_project_spectra))
        codes = graph.nodes_by_type(NodeType.CODE)
        assert len(codes) >= 1

    def test_analyze_test_nodes(self, tmp_project_spectra: Path) -> None:
        """Test nodes from @verifies tags."""
        adapter = SpectraAdapter()
        graph = adapter.analyze(str(tmp_project_spectra))
        tests = graph.nodes_by_type(NodeType.TEST)
        assert len(tests) >= 1
        for t in tests:
            assert t.type == NodeType.TEST
            assert t.framework_origin == "spectra"

    def test_analyze_design_nodes(self, tmp_project_spectra: Path) -> None:
        """Design nodes from <!-- @satisfies -->."""
        adapter = SpectraAdapter()
        graph = adapter.analyze(str(tmp_project_spectra))
        designs = graph.nodes_by_type(NodeType.DESIGN)
        assert len(designs) >= 1

    def test_analyze_edge_relations(self, tmp_project_spectra: Path) -> None:
        """Edges have appropriate relations."""
        adapter = SpectraAdapter()
        graph = adapter.analyze(str(tmp_project_spectra))
        relations = {e.relation.value for e in graph.edges}
        assert "implements" in relations
        assert "verifies" in relations
        assert "satisfies" in relations

    def test_analyze_all_explicit(self, tmp_project_spectra: Path) -> None:
        """All edges from spectra adapter are EXPLICIT."""
        adapter = SpectraAdapter()
        graph = adapter.analyze(str(tmp_project_spectra))
        for e in graph.edges:
            assert e.strength.value == "explicit"

    def test_analyze_evidence_on_edges(self, tmp_project_spectra: Path) -> None:
        """Every edge has evidence with kind and source."""
        adapter = SpectraAdapter()
        graph = adapter.analyze(str(tmp_project_spectra))
        for e in graph.edges:
            assert len(e.evidence) >= 1
            ev = e.evidence[0]
            assert ev.kind in ("mapping", "tag:impl", "tag:verifies", "tag:satisfies")
            assert ev.source.file

    def test_analyze_no_mapping_file(self, tmp_project_heuristic: Path) -> None:
        """Analyze on project without trace-mapping.yaml doesn't crash."""
        adapter = SpectraAdapter()
        graph = adapter.analyze(str(tmp_project_heuristic))
        assert isinstance(graph, TraceGraph)

    def test_analyze_framework_origin(self, tmp_project_spectra: Path) -> None:
        """All nodes have framework_origin='spectra'."""
        adapter = SpectraAdapter()
        graph = adapter.analyze(str(tmp_project_spectra))
        for n in graph.nodes.values():
            assert n.framework_origin == "spectra"

    def test_analyze_coverage(self, tmp_project_spectra: Path) -> None:
        """Coverage is computable after analysis."""
        adapter = SpectraAdapter()
        graph = adapter.analyze(str(tmp_project_spectra))
        from specbridge.analyzers import coverage_summary
        cov = coverage_summary(graph)
        assert cov["total"] > 0
        # spec 1.1 should be covered (login.py + token.py)
        # spec 1.2 should be covered (logout.py)
        assert cov["covered"] >= 1

    def test_analyze_no_duplicate_nodes(self, tmp_project_spectra: Path) -> None:
        """Same file referenced by mapping and @impl tag doesn't duplicate."""
        adapter = SpectraAdapter()
        graph = adapter.analyze(str(tmp_project_spectra))
        ids = list(graph.nodes.keys())
        assert len(ids) == len(set(ids)), f"Duplicate node IDs: {ids}"
