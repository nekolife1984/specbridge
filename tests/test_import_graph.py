"""Tests for code dependency graph (analyzers/graph.py)."""

from __future__ import annotations

import pytest

from specbridge.analyzers.graph import build_code_dependency_graph
from specbridge.core import (
    EdgeRelation,
    NodeType,
    SourceRef,
    TraceGraph,
    TraceNode,
)


@pytest.fixture
def graph_with_imports() -> TraceGraph:
    g = TraceGraph()
    # auth/login.py imports auth/token.py and utils/helpers.py
    g.add_node(TraceNode(
        id="src/auth/login.py",
        type=NodeType.CODE, title="login",
        source=SourceRef(file="src/auth/login.py"),
        framework_origin="heuristic",
        metadata={"imports": ["src.auth.token", "utils.helpers"]},
    ))
    g.add_node(TraceNode(
        id="src/auth/token.py",
        type=NodeType.CODE, title="token",
        source=SourceRef(file="src/auth/token.py"),
        framework_origin="heuristic",
        metadata={"imports": []},
    ))
    g.add_node(TraceNode(
        id="src/utils/helpers.py",
        type=NodeType.CODE, title="helpers",
        source=SourceRef(file="src/utils/helpers.py"),
        framework_origin="heuristic",
        metadata={"imports": []},
    ))
    # test file that imports login
    g.add_node(TraceNode(
        id="tests/test_login.py",
        type=NodeType.TEST, title="test_login",
        source=SourceRef(file="tests/test_login.py"),
        framework_origin="heuristic",
        metadata={"imports": ["src.auth.login"]},
    ))
    return g


class TestBuildDepGraph:
    """build_code_dependency_graph adds correct DEPENDS edges."""

    def test_creates_edges(self, graph_with_imports: TraceGraph) -> None:
        g = graph_with_imports
        build_code_dependency_graph(g, ".")
        edges = [e for e in g.edges if e.relation == EdgeRelation.DEPENDS]
        assert len(edges) >= 2

    def test_login_depends_on_token(self, graph_with_imports: TraceGraph) -> None:
        g = graph_with_imports
        build_code_dependency_graph(g, ".")
        depends = {(e.src_id, e.dst_id) for e in g.edges
                   if e.relation == EdgeRelation.DEPENDS}
        assert ("src/auth/login.py", "src/auth/token.py") in depends

    def test_login_depends_on_helpers(self, graph_with_imports: TraceGraph) -> None:
        g = graph_with_imports
        build_code_dependency_graph(g, ".")
        depends = {(e.src_id, e.dst_id) for e in g.edges
                   if e.relation == EdgeRelation.DEPENDS}
        assert ("src/auth/login.py", "src/utils/helpers.py") in depends

    def test_test_depends_on_login(self, graph_with_imports: TraceGraph) -> None:
        g = graph_with_imports
        build_code_dependency_graph(g, ".")
        depends = {(e.src_id, e.dst_id) for e in g.edges
                   if e.relation == EdgeRelation.DEPENDS}
        assert ("tests/test_login.py", "src/auth/login.py") in depends

    def test_no_self_depends(self, graph_with_imports: TraceGraph) -> None:
        """Files should not depend on themselves."""
        g = graph_with_imports
        build_code_dependency_graph(g, ".")
        depends = {(e.src_id, e.dst_id) for e in g.edges
                   if e.relation == EdgeRelation.DEPENDS}
        assert ("src/auth/login.py", "src/auth/login.py") not in depends

    def test_no_duplicate_edges(self, graph_with_imports: TraceGraph) -> None:
        g = graph_with_imports
        build_code_dependency_graph(g, ".")
        depends = [(e.src_id, e.dst_id) for e in g.edges
                   if e.relation == EdgeRelation.DEPENDS]
        assert len(depends) == len(set(depends)), "Duplicate DEPENDS edges"

    def test_empty_imports(self) -> None:
        """No imports = no DEPENDS edges."""
        g = TraceGraph()
        g.add_node(TraceNode(
            id="main.py",
            type=NodeType.CODE, title="main",
            source=SourceRef(file="main.py"),
            framework_origin="heuristic",
            metadata={"imports": []},
        ))
        build_code_dependency_graph(g, ".")
        deps = [e for e in g.edges if e.relation == EdgeRelation.DEPENDS]
        assert len(deps) == 0

    def test_preserves_existing_edges(self, graph_with_imports: TraceGraph) -> None:
        """Import graph doesn't clobber existing edges."""
        g = graph_with_imports
        before = len(g.edges)
        build_code_dependency_graph(g, ".")
        # No edges should be removed
        assert len(g.edges) >= before
