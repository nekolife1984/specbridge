"""Tests for heuristic adapter + bridge (adapters/heuristic.py, bridge/)."""

from __future__ import annotations

from pathlib import Path

from specbridge.adapters import detect_adapter
from specbridge.adapters.heuristic import HeuristicAdapter
from specbridge.core import NodeType, TraceGraph


class TestHeuristicDetect:
    """HeuristicAdapter.detect() scoring."""

    def test_detect_both_dirs(self, tmp_project_heuristic: Path) -> None:
        """docs/ + src/ → 0.8."""
        adapter = HeuristicAdapter()
        score = adapter.detect(str(tmp_project_heuristic))
        assert score == 0.8

    def test_detect_specs_only(self, tmp_path: Path) -> None:
        """Only docs/ → 0.4."""
        project = tmp_path / "specs-only"
        project.mkdir()
        (project / "docs").mkdir()
        adapter = HeuristicAdapter()
        score = adapter.detect(str(project))
        assert score == 0.4

    def test_detect_code_only(self, tmp_path: Path) -> None:
        """Only src/ → 0.4."""
        project = tmp_path / "code-only"
        project.mkdir()
        (project / "src").mkdir()
        adapter = HeuristicAdapter()
        score = adapter.detect(str(project))
        assert score == 0.4

    def test_detect_neither(self, tmp_path: Path) -> None:
        """No docs/ or src/ → 0.0."""
        project = tmp_path / "empty"
        project.mkdir()
        adapter = HeuristicAdapter()
        score = adapter.detect(str(project))
        assert score == 0.0

    def test_spec_alternatives(self, tmp_path: Path) -> None:
        """spec/ or specs/ also work."""
        for d in ["spec", "specs"]:
            project = tmp_path / f"project-{d}"
            project.mkdir()
            (project / d).mkdir()
            (project / "src").mkdir()
            adapter = HeuristicAdapter()
            score = adapter.detect(str(project))
            assert score == 0.8

    def test_src_alternatives(self, tmp_path: Path) -> None:
        """lib/ or app/ also work."""
        for d in ["lib", "app"]:
            project = tmp_path / f"project-{d}"
            project.mkdir()
            (project / "docs").mkdir()
            (project / d).mkdir()
            adapter = HeuristicAdapter()
            score = adapter.detect(str(project))
            assert score == 0.8


class TestHeuristicAnalyze:
    """HeuristicAdapter.analyze() graph construction."""

    def test_analyze_basic(self, tmp_project_heuristic: Path) -> None:
        """Produces a graph with expected node types."""
        adapter = HeuristicAdapter()
        graph = adapter.analyze(str(tmp_project_heuristic))
        assert isinstance(graph, TraceGraph)
        assert len(graph.nodes) > 0
        assert len(graph.nodes_by_type(NodeType.SPEC)) >= 2  # auth.md + reporting.md
        assert len(graph.nodes_by_type(NodeType.CODE)) >= 2  # login.py + charts.py

    def test_analyze_edges_created(self, tmp_project_heuristic: Path) -> None:
        """Edges exist between specs and code nodes."""
        adapter = HeuristicAdapter()
        graph = adapter.analyze(str(tmp_project_heuristic))
        assert len(graph.edges) > 0
        # All edges should be IMPLEMENTS or VERIFIES
        for e in graph.edges:
            assert e.relation.value in ("implements", "verifies")

    def test_analyze_edge_confidence(self, tmp_project_heuristic: Path) -> None:
        """Edges have strengths: WEAK or INFERRED."""
        adapter = HeuristicAdapter()
        graph = adapter.analyze(str(tmp_project_heuristic))
        for e in graph.edges:
            assert e.strength.value in ("weak", "inferred")

    def test_analyze_evidence(self, tmp_project_heuristic: Path) -> None:
        """Each edge has at least one evidence item."""
        adapter = HeuristicAdapter()
        graph = adapter.analyze(str(tmp_project_heuristic))
        for e in graph.edges:
            assert len(e.evidence) >= 1
            assert e.evidence[0].kind.startswith("heuristic:")

    def test_analyze_no_framework_conflict(self, tmp_project_heuristic: Path) -> None:
        """All nodes have framework_origin='heuristic'."""
        adapter = HeuristicAdapter()
        graph = adapter.analyze(str(tmp_project_heuristic))
        for n in graph.nodes.values():
            assert n.framework_origin == "heuristic"

    def test_analyze_empty_project(self, tmp_path: Path) -> None:
        """Empty project returns empty graph (no crash)."""
        project = tmp_path / "empty"
        project.mkdir()
        adapter = HeuristicAdapter()
        graph = adapter.analyze(str(project))
        assert isinstance(graph, TraceGraph)
        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0

    def test_analyze_dirname_matching(self, tmp_path: Path) -> None:
        """docs/auth/ ↔ src/auth/ should produce edges via dirname match."""
        project = tmp_path / "match-test"
        project.mkdir()

        docs = project / "docs" / "auth"
        docs.mkdir(parents=True)
        (docs / "login.md").write_text("# Login\nLogin function spec.\n")

        src = project / "src" / "auth"
        src.mkdir(parents=True)
        (src / "login.py").write_text("def login(): pass\n")

        adapter = HeuristicAdapter()
        graph = adapter.analyze(str(project))
        assert len(graph.edges) >= 1

    def test_analyze_detects_tests(self, tmp_path: Path) -> None:
        """Test files tagged as TEST nodes."""
        project = tmp_path / "test-proj"
        project.mkdir()
        (project / "docs").mkdir()
        (project / "docs" / "auth.md").write_text("# Auth\nAuth spec.\n")
        (project / "src").mkdir()
        (project / "src" / "test_auth.py").write_text("def test_auth(): pass\n")

        adapter = HeuristicAdapter()
        graph = adapter.analyze(str(project))
        test_nodes = graph.nodes_by_type(NodeType.TEST)
        assert len(test_nodes) >= 1


class TestAdapterRegistry:
    """Adapter detection via registry."""

    def test_detect_prefers_higher_score(self, tmp_project_spectra: Path) -> None:
        """spectra adapter (0.95) > heuristic (0.8) when trace-mapping.yaml exists."""
        adapter = detect_adapter(str(tmp_project_spectra))
        assert adapter is not None
        from specbridge.adapters.spectra import SpectraAdapter
        assert isinstance(adapter, SpectraAdapter)

    def test_detect_falls_back_to_heuristic(self, tmp_project_heuristic: Path) -> None:
        """heuristic adapter selected when no trace-mapping.yaml."""
        adapter = detect_adapter(str(tmp_project_heuristic))
        assert adapter is not None
        assert isinstance(adapter, HeuristicAdapter)

    def test_detect_no_adapter(self, tmp_path: Path) -> None:
        """None returned for unrecognized project."""
        empty = tmp_path / "empty"
        empty.mkdir()
        adapter = detect_adapter(str(empty))
        assert adapter is None
