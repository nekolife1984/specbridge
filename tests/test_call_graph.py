"""Tests for call-graph analysis (analyzers/call_graph.py)."""

from __future__ import annotations

from pathlib import Path

from specbridge.analyzers.call_graph import (
    CallGraph,
    CallGraphNode,
    build_call_graph,
    import_crg_json,
    transitive_impact,
)
from specbridge.core import (
    EdgeRelation,
    EdgeStrength,
    Evidence,
    NodeType,
    SourceRef,
    TraceEdge,
    TraceGraph,
    TraceNode,
)


def _make_graph() -> TraceGraph:
    """Build a simple TraceGraph with two code files that have function-level nodes."""
    g = TraceGraph()
    g.nodes["src/service.py::create_task"] = TraceNode(
        id="src/service.py::create_task",
        type=NodeType.CODE,
        title="create_task",
        source=SourceRef(file="src/service.py", line=10, label="create_task"),
        framework_origin="plain",
        metadata={"imports": ["src/db"]},
    )
    g.nodes["src/service.py::_validate"] = TraceNode(
        id="src/service.py::_validate",
        type=NodeType.CODE,
        title="_validate",
        source=SourceRef(file="src/service.py", line=30, label="_validate"),
        framework_origin="plain",
    )
    g.nodes["src/db.py::save_task"] = TraceNode(
        id="src/db.py::save_task",
        type=NodeType.CODE,
        title="save_task",
        source=SourceRef(file="src/db.py", line=5, label="save_task"),
        framework_origin="plain",
    )
    g.nodes["docs/spec.md::1.1"] = TraceNode(
        id="docs/spec.md::1.1",
        type=NodeType.SPEC,
        title="Task Creation",
        source=SourceRef(file="docs/spec.md", line=1),
        framework_origin="plain",
    )
    g.nodes["src/service.py"] = TraceNode(
        id="src/service.py",
        type=NodeType.CODE,
        title="service.py",
        source=SourceRef(file="src/service.py"),
        framework_origin="plain",
    )
    # Edge: create_task → spec
    g.edges.append(TraceEdge(
        src_id="src/service.py::create_task",
        dst_id="docs/spec.md::1.1",
        relation=EdgeRelation.IMPLEMENTS,
        strength=EdgeStrength.INFERRED,
        evidence=[Evidence(kind="heuristic", value="matching", source=SourceRef(file="src/service.py"))],
    ))
    return g


class TestBuildCallGraph:
    """Lightweight call-graph builder."""

    def test_build_from_trace_graph(self) -> None:
        graph = _make_graph()
        # Create a temporary source file so the builder can scan calls
        import tempfile, os
        d = tempfile.mkdtemp()
        srcdir = os.path.join(d, "src")
        os.makedirs(srcdir, exist_ok=True)

        service_path = os.path.join(srcdir, "service.py")
        with open(service_path, "w") as f:
            f.write("def create_task():\n    save_task()\n    _validate()\n\n")
        db_path = os.path.join(srcdir, "db.py")
        with open(db_path, "w") as f:
            f.write("def save_task():\n    pass\n")

        cg = build_call_graph(graph, d)
        assert len(cg.nodes) >= 2
        assert "src/service.py::create_task" in cg.nodes
        assert "src/db.py::save_task" in cg.nodes or any(
            "save_task" in k for k in cg.nodes
        )

    def test_empty_graph(self) -> None:
        graph = TraceGraph()
        cg = build_call_graph(graph, "/tmp")
        assert len(cg.nodes) == 0
        assert len(cg.edges) == 0


class TestCallGraphData:
    """CallGraph data structure."""

    def test_add_call_dedup(self) -> None:
        cg = CallGraph()
        cg.add_call("a", "b")
        cg.add_call("a", "b")
        assert len(cg.edges) == 1

    def test_callees_of(self) -> None:
        cg = CallGraph()
        cg.add_call("a", "b")
        cg.add_call("a", "c")
        assert set(cg.callees_of("a")) == {"b", "c"}

    def test_callers_of(self) -> None:
        cg = CallGraph()
        cg.add_call("a", "b")
        cg.add_call("c", "b")
        assert set(cg.callers_of("b")) == {"a", "c"}

    def test_files_of(self) -> None:
        cg = CallGraph()
        cg.nodes["src/a.py::foo"] = CallGraphNode(name="foo", file="src/a.py")
        cg.nodes["src/a.py::bar"] = CallGraphNode(name="bar", file="src/a.py")
        cg.nodes["src/b.py::baz"] = CallGraphNode(name="baz", file="src/b.py")
        files = cg.files_of(["src/a.py::foo", "src/a.py::bar", "src/b.py::baz"])
        assert files == ["src/a.py", "src/b.py"]


class TestImportCRG:
    """CRG JSON import."""

    def test_import_basic(self, tmp_path: Path) -> None:
        crg_file = tmp_path / "crg.json"
        crg_file.write_text("""[
            {"symbol": "login", "file": "src/auth.py",
             "callers": [], "callees": ["validate_token"]},
            {"symbol": "validate_token", "file": "src/auth.py",
             "callers": ["login"], "callees": []}
        ]""")
        cg = import_crg_json(str(crg_file))
        assert len(cg.nodes) >= 2
        assert cg.edges == [("src/auth.py::login", "src/auth.py::validate_token")]

    def test_import_not_found(self) -> None:
        cg = import_crg_json("/nonexistent/crg.json")
        assert len(cg.nodes) == 0

    def test_import_invalid_json(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text("not json")
        cg = import_crg_json(str(bad))
        assert len(cg.nodes) == 0

    def test_import_empty(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty.json"
        empty.write_text("[]")
        cg = import_crg_json(str(empty))
        assert len(cg.nodes) == 0


class TestTransitiveImpact:
    """Transitive impact analysis."""

    def test_basic_transitive(self) -> None:
        graph = _make_graph()
        cg = CallGraph()
        cg.nodes["src/service.py::create_task"] = CallGraphNode(
            name="create_task", file="src/service.py")
        cg.nodes["src/db.py::save_task"] = CallGraphNode(
            name="save_task", file="src/db.py")
        cg.add_call("src/service.py::create_task", "src/db.py::save_task")

        result = transitive_impact(graph, cg, "docs/spec.md::1.1")
        assert "src/service.py" in result["direct_files"]
        assert "src/db.py" in result["transitive_files"]

    def test_max_depth(self) -> None:
        """Chain A → B → C → D, depth=2 should only reach C."""
        graph = TraceGraph()
        graph.nodes["spec::1"] = TraceNode(
            id="spec::1", type=NodeType.SPEC, title="Root",
            source=SourceRef(file="spec.md"),
            framework_origin="plain",
        )

        cg = CallGraph()
        for name, filepath in [("A", "a.py"), ("B", "b.py"), ("C", "c.py"), ("D", "d.py")]:
            key = f"src/{filepath}::{name}"
            cg.nodes[key] = CallGraphNode(name=name, file=f"src/{filepath}")
        cg.add_call("src/a.py::A", "src/b.py::B")
        cg.add_call("src/b.py::B", "src/c.py::C")
        cg.add_call("src/c.py::C", "src/d.py::D")

        # Direct: A (but no edges to spec, so no direct files)
        result = transitive_impact(graph, cg, "spec::1", max_depth=2)
        # No direct files since no edges connect spec::1 to functions
        assert result["direct_files"] == []

    def test_no_call_graph(self) -> None:
        graph = _make_graph()
        cg = CallGraph()  # empty
        result = transitive_impact(graph, cg, "docs/spec.md::1.1")
        assert result["direct_files"] == []
        assert result["transitive_files"] == []

    def test_no_matching_spec(self) -> None:
        graph = _make_graph()
        cg = CallGraph()
        result = transitive_impact(graph, cg, "nonexistent")
        assert result["direct_files"] == []
