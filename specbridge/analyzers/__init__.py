"""Analysis utilities."""
from specbridge.analyzers.call_graph import (
    CallGraph,
    build_call_graph,
    transitive_impact,
)

from typing import Any

from specbridge.core import EdgeRelation, NodeType, TraceGraph


def find_orphan_specs(graph: TraceGraph) -> list[str]:
    """Spec nodes with zero implementing edges."""
    orphans = []
    for nid, node in graph.nodes.items():
        if node.type != NodeType.SPEC:
            continue
        impl_edges = [e for e in graph.edges_to(nid) if e.relation in (
            EdgeRelation.IMPLEMENTS, EdgeRelation.SATISFIES, EdgeRelation.VERIFIES,
        )]
        if not impl_edges:
            orphans.append(nid)
    return orphans


def find_orphan_code(graph: TraceGraph) -> list[str]:
    """Code/test nodes that don't link to any spec."""
    linked_specs = {e.dst_id for e in graph.edges if e.relation in (
        EdgeRelation.IMPLEMENTS, EdgeRelation.SATISFIES, EdgeRelation.VERIFIES,
    )}
    orphans = []
    for nid, node in graph.nodes.items():
        if node.type in (NodeType.CODE, NodeType.TEST) and nid not in linked_specs and not graph.edges_from(nid):
                orphans.append(nid)
    return orphans


def coverage_summary(graph: TraceGraph) -> dict[str, int | float]:
    """Compute spec coverage stats."""
    specs = graph.nodes_by_type(NodeType.SPEC)
    if not specs:
        return {"total": 0, "covered": 0, "orphan": 0, "coverage_pct": 0.0}

    linked_spec_ids = set()
    for e in graph.edges:
        if e.relation in (EdgeRelation.IMPLEMENTS, EdgeRelation.VERIFIES, EdgeRelation.SATISFIES):
            linked_spec_ids.add(e.dst_id)

    covered = sum(1 for s in specs if s.id in linked_spec_ids)
    return {
        "total": len(specs),
        "covered": covered,
        "orphan": len(specs) - covered,
        "coverage_pct": round(covered / len(specs) * 100, 1),
    }
