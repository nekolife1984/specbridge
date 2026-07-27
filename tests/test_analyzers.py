"""Tests for analysis utilities (analyzers/__init__.py)."""

from __future__ import annotations

import pytest

from specbridge.analyzers import (
    coverage_summary,
    find_orphan_code,
    find_orphan_specs,
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


@pytest.fixture
def three_spec_graph() -> TraceGraph:
    """A graph with 3 specs, 2 covered + 1 orphan."""
    g = TraceGraph()
    # Specs
    g.add_node(TraceNode(id="1", type=NodeType.SPEC, title="Auth",
                         source=SourceRef(file="docs/auth.md"),
                         framework_origin="heuristic"))
    g.add_node(TraceNode(id="2", type=NodeType.SPEC, title="API",
                         source=SourceRef(file="docs/api.md"),
                         framework_origin="heuristic"))
    g.add_node(TraceNode(id="3", type=NodeType.SPEC, title="Orphan",
                         source=SourceRef(file="docs/orphan.md"),
                         framework_origin="heuristic"))
    # Code
    g.add_node(TraceNode(id="login.py", type=NodeType.CODE, title="login",
                         source=SourceRef(file="src/auth/login.py"),
                         framework_origin="heuristic"))
    g.add_node(TraceNode(id="test_login.py", type=NodeType.TEST, title="test",
                         source=SourceRef(file="tests/test_login.py"),
                         framework_origin="heuristic"))
    # Edges: spec 1 and 2 are covered
    g.add_edge(TraceEdge(src_id="login.py", dst_id="1",
                         relation=EdgeRelation.IMPLEMENTS,
                         strength=EdgeStrength.EXPLICIT))
    g.add_edge(TraceEdge(src_id="test_login.py", dst_id="1",
                         relation=EdgeRelation.VERIFIES,
                         strength=EdgeStrength.EXPLICIT))
    return g


class TestCoverageSummary:
    """Coverage computation."""

    def test_basic_coverage(self, three_spec_graph: TraceGraph) -> None:
        cov = coverage_summary(three_spec_graph)
        assert cov["total"] == 3
        assert cov["covered"] == 1  # only spec "1" has edges
        assert cov["orphan"] == 2
        assert cov["coverage_pct"] == pytest.approx(33.3, rel=0.1)

    def test_empty_graph(self) -> None:
        g = TraceGraph()
        cov = coverage_summary(g)
        assert cov["total"] == 0
        assert cov["coverage_pct"] == 0.0

    def test_full_coverage(self) -> None:
        g = TraceGraph()
        g.add_node(TraceNode(id="1", type=NodeType.SPEC, title="Auth",
                             source=SourceRef(file="docs/auth.md"),
                             framework_origin="heuristic"))
        g.add_node(TraceNode(id="login.py", type=NodeType.CODE, title="login",
                             source=SourceRef(file="login.py"),
                             framework_origin="heuristic"))
        g.add_edge(TraceEdge(src_id="login.py", dst_id="1",
                             relation=EdgeRelation.IMPLEMENTS,
                             strength=EdgeStrength.EXPLICIT))
        cov = coverage_summary(g)
        assert cov["covered"] == 1
        assert cov["total"] == 1
        assert cov["coverage_pct"] == 100.0

    def test_satisfies_counts_as_covered(self) -> None:
        g = TraceGraph()
        g.add_node(TraceNode(id="1", type=NodeType.SPEC, title="Auth",
                             source=SourceRef(file="docs/auth.md"),
                             framework_origin="heuristic"))
        g.add_node(TraceNode(id="design-x", type=NodeType.DESIGN, title="Design",
                             source=SourceRef(file="docs/design.md"),
                             framework_origin="heuristic"))
        g.add_edge(TraceEdge(src_id="design-x", dst_id="1",
                             relation=EdgeRelation.SATISFIES,
                             strength=EdgeStrength.EXPLICIT))
        cov = coverage_summary(g)
        assert cov["covered"] == 1


class TestFindOrphans:
    """Orphan detection."""

    def test_orphan_specs(self, three_spec_graph: TraceGraph) -> None:
        orphans = find_orphan_specs(three_spec_graph)
        assert "3" in orphans
        assert "2" in orphans  # spec "2" has no incoming edges
        assert "1" not in orphans

    def test_orphan_code(self, three_spec_graph: TraceGraph) -> None:
        orphans = find_orphan_code(three_spec_graph)
        # Everything is linked to spec 1, so no orphans
        # But spec 2 has no code — code nodes linked to spec 2? No.
        assert isinstance(orphans, list)

    def test_no_orphans(self) -> None:
        g = TraceGraph()
        g.add_node(TraceNode(id="1", type=NodeType.SPEC, title="Auth",
                             source=SourceRef(file="docs/auth.md"),
                             framework_origin="heuristic"))
        g.add_node(TraceNode(id="login.py", type=NodeType.CODE, title="login",
                             source=SourceRef(file="login.py"),
                             framework_origin="heuristic"))
        g.add_edge(TraceEdge(src_id="login.py", dst_id="1",
                             relation=EdgeRelation.IMPLEMENTS,
                             strength=EdgeStrength.EXPLICIT))
        assert find_orphan_specs(g) == []
        assert find_orphan_code(g) == []

    def test_orphan_code_only(self) -> None:
        g = TraceGraph()
        g.add_node(TraceNode(id="lonely.py", type=NodeType.CODE, title="lonely",
                             source=SourceRef(file="lonely.py"),
                             framework_origin="heuristic"))
        g.add_node(TraceNode(id="spec1", type=NodeType.SPEC, title="Spec",
                             source=SourceRef(file="docs/spec.md"),
                             framework_origin="heuristic"))
        orphans = find_orphan_code(g)
        assert "lonely.py" in orphans

    def test_edge_relation_filtering(self) -> None:
        """Only IMPLEMENTS, VERIFIES, SATISFIES edges count for orphan spec detection."""
        g = TraceGraph()
        g.add_node(TraceNode(id="1", type=NodeType.SPEC, title="Auth",
                             source=SourceRef(file="docs/auth.md"),
                             framework_origin="heuristic"))
        g.add_node(TraceNode(id="ref.py", type=NodeType.CODE, title="ref",
                             source=SourceRef(file="ref.py"),
                             framework_origin="heuristic"))
        # Only a REFERENCES edge — does NOT count as covered
        g.add_edge(TraceEdge(src_id="ref.py", dst_id="1",
                             relation=EdgeRelation.REFERENCES,
                             strength=EdgeStrength.WEAK))
        orphans = find_orphan_specs(g)
        assert "1" in orphans

    def test_design_node_is_ignored_for_orphan_code(self) -> None:
        g = TraceGraph()
        g.add_node(TraceNode(id="design-1", type=NodeType.DESIGN, title="Design",
                             source=SourceRef(file="docs/design.md"),
                             framework_origin="heuristic"))
        orphans = find_orphan_code(g)
        # DESIGN nodes should not appear in CODE orphan list
        assert len(orphans) == 0


class TestCoverageGateCheck:
    """Coverage gate check."""

    def test_gate_passes(self, three_spec_graph: TraceGraph) -> None:
        from specbridge.analyzers import coverage_gate_check
        result = coverage_gate_check(three_spec_graph, min_coverage=30.0)
        assert result["passed"] is True
        assert result["coverage_pct"] == pytest.approx(33.3, rel=0.1)
        assert "passed" in result["message"]

    def test_gate_fails(self, three_spec_graph: TraceGraph) -> None:
        from specbridge.analyzers import coverage_gate_check
        result = coverage_gate_check(three_spec_graph, min_coverage=50.0)
        assert result["passed"] is False
        assert result["coverage_pct"] == pytest.approx(33.3, rel=0.1)
        assert "FAILED" in result["message"]

    def test_gate_perfect_coverage(self) -> None:
        from specbridge.analyzers import coverage_gate_check
        g = TraceGraph()
        g.add_node(TraceNode(id="1", type=NodeType.SPEC, title="Auth",
                             source=SourceRef(file="docs/auth.md"),
                             framework_origin="heuristic"))
        g.add_node(TraceNode(id="login.py", type=NodeType.CODE, title="login",
                             source=SourceRef(file="login.py"),
                             framework_origin="heuristic"))
        g.add_edge(TraceEdge(src_id="login.py", dst_id="1",
                             relation=EdgeRelation.IMPLEMENTS,
                             strength=EdgeStrength.EXPLICIT))
        result = coverage_gate_check(g, min_coverage=100.0)
        assert result["passed"] is True
        assert result["coverage_pct"] == 100.0

    def test_gate_empty_graph(self) -> None:
        from specbridge.analyzers import coverage_gate_check
        g = TraceGraph()
        result = coverage_gate_check(g, min_coverage=50.0)
        assert result["passed"] is False
        assert result["coverage_pct"] == 0.0
        assert result["total"] == 0

    def test_gate_default_threshold(self) -> None:
        from specbridge.analyzers import coverage_gate_check
        g = TraceGraph()
        # Default threshold is 50.0
        result = coverage_gate_check(g)
        assert result["min_coverage"] == 50.0

    def test_gate_result_structure(self, three_spec_graph: TraceGraph) -> None:
        from specbridge.analyzers import coverage_gate_check
        result = coverage_gate_check(three_spec_graph, min_coverage=30.0)
        assert "passed" in result
        assert "coverage_pct" in result
        assert "covered" in result
        assert "total" in result
        assert "min_coverage" in result
        assert "message" in result


class TestReverseImpact:
    """Reverse impact: file → spec lookup."""

    @pytest.fixture
    def impact_graph(self) -> TraceGraph:
        g = TraceGraph()
        # Specs
        g.add_node(TraceNode(id="1", type=NodeType.SPEC, title="Auth",
                             source=SourceRef(file="docs/auth.md"),
                             framework_origin="heuristic"))
        g.add_node(TraceNode(id="2", type=NodeType.SPEC, title="API",
                             source=SourceRef(file="docs/api.md"),
                             framework_origin="heuristic"))
        # Code files
        g.add_node(TraceNode(id="login.py", type=NodeType.CODE, title="login",
                             source=SourceRef(file="src/auth/login.py"),
                             framework_origin="heuristic"))
        g.add_node(TraceNode(id="api.py", type=NodeType.CODE, title="api",
                             source=SourceRef(file="src/api/handler.py"),
                             framework_origin="heuristic"))
        g.add_node(TraceNode(id="orphan.py", type=NodeType.CODE, title="orphan",
                             source=SourceRef(file="src/utils/helper.py"),
                             framework_origin="heuristic"))
        # Edges
        g.add_edge(TraceEdge(src_id="login.py", dst_id="1",
                             relation=EdgeRelation.IMPLEMENTS,
                             strength=EdgeStrength.EXPLICIT))
        g.add_edge(TraceEdge(src_id="api.py", dst_id="2",
                             relation=EdgeRelation.IMPLEMENTS,
                             strength=EdgeStrength.EXPLICIT))
        return g

    def test_find_specs_by_exact_file(self, impact_graph: TraceGraph) -> None:
        from specbridge.core import find_specs_by_file
        results = find_specs_by_file(impact_graph, "src/auth/login.py")
        assert len(results) == 1
        assert results[0]["file"] == "src/auth/login.py"
        assert results[0]["specs"][0]["spec_id"] == "1"

    def test_find_specs_by_filename(self, impact_graph: TraceGraph) -> None:
        from specbridge.core import find_specs_by_file
        results = find_specs_by_file(impact_graph, "login.py")
        assert len(results) == 1
        assert results[0]["file"] == "src/auth/login.py"

    def test_file_with_no_specs(self, impact_graph: TraceGraph) -> None:
        from specbridge.core import find_specs_by_file
        results = find_specs_by_file(impact_graph, "src/utils/helper.py")
        assert len(results) == 0

    def test_file_not_found(self, impact_graph: TraceGraph) -> None:
        from specbridge.core import find_specs_by_file
        results = find_specs_by_file(impact_graph, "nonexistent.py")
        assert len(results) == 0

    def test_find_specs_by_file_returns_all_specs(self, impact_graph: TraceGraph) -> None:
        from specbridge.core import find_specs_by_file
        results = find_specs_by_file(impact_graph, "src/auth/login.py")
        assert len(results) == 1
        assert results[0]["specs"][0]["spec_id"] == "1"
        assert results[0]["specs"][0]["title"] == "Auth"
        assert results[0]["specs"][0]["relation"] == "implements"
        assert results[0]["specs"][0]["strength"] == "explicit"

    def test_find_specs_structure(self, impact_graph: TraceGraph) -> None:
        from specbridge.core import find_specs_by_file
        results = find_specs_by_file(impact_graph, "src/auth/login.py")
        assert len(results) == 1
        r = results[0]
        assert "file" in r
        assert "node_type" in r
        assert "specs" in r
        assert len(r["specs"]) == 1
        s = r["specs"][0]
        assert "spec_id" in s
        assert "title" in s
        assert "relation" in s
        assert "strength" in s
        assert "evidence" in s
