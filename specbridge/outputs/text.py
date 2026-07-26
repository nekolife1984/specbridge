"""Plain text output."""

from specbridge.core import NodeType, TraceGraph


def render_text(graph: TraceGraph, max_nodes: int | None = None) -> str:
    """Render the full trace graph as human-readable text.

    When *max_nodes* is set, only the top N items per category are shown
    and a truncation note is appended.
    """
    from specbridge.analyzers import coverage_summary

    lines: list[str] = []
    lines.append("specbridge — Trace Graph")
    lines.append(f"{'=' * 40}")
    lines.append(f"Nodes: {len(graph.nodes)} | Edges: {len(graph.edges)}")

    # Coverage summary
    cov = coverage_summary(graph)
    if cov["total"] > 0:
        lines.append(f"Coverage: {cov['coverage_pct']}% ({cov['covered']}/{cov['total']})")
    lines.append("")

    def _maybe_truncate(items: list, label: str, max_n: int | None) -> tuple[list, bool]:
        if max_n is not None and len(items) > max_n:
            return items[:max_n], True
        return items, False

    def _is_func_node(n) -> bool:
        """Function-level nodes have '::' in their ID."""
        return "::" in n.id

    # Specs
    specs = graph.nodes_by_type(NodeType.SPEC)
    if specs:
        lines.append("📄 Specs:")
        displayed, truncated = _maybe_truncate(specs, "specs", max_nodes)
        for n in sorted(displayed, key=lambda x: x.id):
            edges_to = graph.edges_to(n.id)
            impls = [e for e in edges_to if e.relation.value in ("implements", "verifies", "satisfies")]
            lines.append(f"  {n.id:20s}  [{len(impls)} refs]  {n.title}")
        if truncated:
            lines.append(f"  ... and {len(specs) - max_nodes} more specs")
        lines.append("")

    # Code files (file-level only, not function-level)
    codes = [n for n in graph.nodes_by_type(NodeType.CODE) if not _is_func_node(n)]
    if codes:
        lines.append("📁 Code refs:")
        displayed, truncated = _maybe_truncate(codes, "code", max_nodes)
        for n in sorted(displayed, key=lambda x: x.id):
            edges_from = graph.edges_from(n.id)
            if edges_from:
                targets = ", ".join(e.dst_id for e in edges_from)
                lines.append(f"  {n.id:40s} → {targets}")
            else:
                lines.append(f"  {n.id:40s}  (unlinked)")
        if truncated:
            lines.append(f"  ... and {len(codes) - max_nodes} more code files")
        lines.append("")

    # Function refs (function-level nodes)
    funcs = [n for n in graph.nodes_by_type(NodeType.CODE) if _is_func_node(n)]
    if funcs:
        lines.append("🔧 Function refs:")
        displayed, truncated = _maybe_truncate(funcs, "funcs", max_nodes)
        for n in sorted(displayed, key=lambda x: x.id):
            edges_from = graph.edges_from(n.id)
            if edges_from:
                targets = ", ".join(e.dst_id for e in edges_from)
                lines.append(f"  {n.id:45s} → {targets}")
            else:
                lines.append(f"  {n.id:45s}  (unlinked)")
        if truncated:
            lines.append(f"  ... and {len(funcs) - max_nodes} more functions")
        lines.append("")

    # Tests
    tests = graph.nodes_by_type(NodeType.TEST)
    if tests:
        lines.append("🧪 Test refs:")
        displayed, truncated = _maybe_truncate(tests, "tests", max_nodes)
        for n in sorted(displayed, key=lambda x: x.id):
            edges_from = graph.edges_from(n.id)
            if edges_from:
                targets = ", ".join(e.dst_id for e in edges_from)
                lines.append(f"  {n.id:40s} → {targets}")
        if truncated:
            lines.append(f"  ... and {len(tests) - max_nodes} more test files")
        lines.append("")

    return "\n".join(lines)
