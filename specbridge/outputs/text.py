"""Plain text output."""

from specbridge.core import TraceGraph, NodeType


def render_text(graph: TraceGraph) -> str:
    """Render the full trace graph as human-readable text."""
    lines: list[str] = []
    lines.append(f"specbridge — Trace Graph")
    lines.append(f"{'=' * 40}")
    lines.append(f"Nodes: {len(graph.nodes)} | Edges: {len(graph.edges)}")
    lines.append("")

    # Specs
    specs = graph.nodes_by_type(NodeType.SPEC)
    if specs:
        lines.append("📄 Specs:")
        for n in sorted(specs, key=lambda x: x.id):
            edges_to = graph.edges_to(n.id)
            impls = [e for e in edges_to if e.relation.value in ("implements", "verifies", "satisfies")]
            lines.append(f"  {n.id:20s}  [{len(impls)} refs]  {n.title}")
        lines.append("")

    # Code
    codes = graph.nodes_by_type(NodeType.CODE)
    if codes:
        lines.append("📁 Code refs:")
        for n in sorted(codes, key=lambda x: x.id):
            edges_from = graph.edges_from(n.id)
            if edges_from:
                targets = ", ".join(e.dst_id for e in edges_from)
                lines.append(f"  {n.id:40s} → {targets}")
            else:
                lines.append(f"  {n.id:40s}  (unlinked)")
        lines.append("")

    # Tests
    tests = graph.nodes_by_type(NodeType.TEST)
    if tests:
        lines.append("🧪 Test refs:")
        for n in sorted(tests, key=lambda x: x.id):
            edges_from = graph.edges_from(n.id)
            if edges_from:
                targets = ", ".join(e.dst_id for e in edges_from)
                lines.append(f"  {n.id:40s} → {targets}")
        lines.append("")

    return "\n".join(lines)
