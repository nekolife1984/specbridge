"""Plain text output with Rich color enhancement."""

from typing import Any

from rich.console import Console
from rich.table import Table
from rich.text import Text

from specbridge.core import EdgeStrength, NodeType, TraceGraph

_console = Console()


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
        pct = cov["coverage_pct"]
        pct_str = f"Coverage: {pct}% ({cov['covered']}/{cov['total']})"
        lines.append(pct_str)
    lines.append("")

    def _maybe_truncate(items: list[Any], label: str, max_n: int | None) -> tuple[list[Any], bool]:
        if max_n is not None and len(items) > max_n:
            return items[:max_n], True
        return items, False

    def _is_func_node(n: Any) -> bool:
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
            refs = len(impls)
            # Color the ref count: green if >0, yellow if 0
            ref_tag = f"[{refs}]" if refs > 0 else "(unlinked)"
            lines.append(f"  {n.id:20s}  {ref_tag:12s}  {n.title}")
        if truncated:
            lines.append(f"  ... and {len(specs) - (max_nodes or 0)} more specs")
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
            lines.append(f"  ... and {len(codes) - (max_nodes or 0)} more code files")
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
            lines.append(f"  ... and {len(funcs) - (max_nodes or 0)} more functions")
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
            lines.append(f"  ... and {len(tests) - (max_nodes or 0)} more test files")
        lines.append("")

    return "\n".join(lines)


def render_coverage(cov: dict[str, int | float], orphans_spec: list[str],
                    orphans_code: list[str]) -> str:
    """Render coverage stats with color-coded percentages."""
    lines: list[str] = []
    pct = cov["coverage_pct"]

    # Color-coding indicator based on coverage level
    if isinstance(pct, (int, float)):
        if pct >= 80:
            indicator = "🟢"
        elif pct >= 50:
            indicator = "🟡"
        else:
            indicator = "🔴"

    lines.append(f"📊 Spec Coverage  {indicator}")
    lines.append(f"{'=' * 40}")
    lines.append(f"  Total specs:  {cov['total']}")
    lines.append(f"  Covered:      {cov['covered']}")
    lines.append(f"  Orphan specs: {cov['orphan']}")
    lines.append(f"  Coverage:     {pct}%")

    if orphans_spec:
        lines.append(f"\n🟡 Orphan specs (no code ref):")
        for nid in orphans_spec:
            lines.append(f"   - {nid}")
    if orphans_code:
        lines.append(f"\n🟡 Orphan code files (no spec ref):")
        for nid in orphans_code[:10]:
            lines.append(f"   - {nid}")
        if len(orphans_code) > 10:
            lines.append(f"   ... and {len(orphans_code) - 10} more")

    return "\n".join(lines)


def render_status_summary(summary: dict[str, Any]) -> str:
    """Render a one-line summary suitable for CI dashboards.

    Format: Coverage: 60.7% (259/427) | Specs: 42 | Code refs: 87 | Orphans: 5
    """
    cov = summary.get("coverage", {})
    pct = cov.get("coverage_pct", 0)
    total = cov.get("total", 0)
    covered = cov.get("covered", 0)
    spec_count = summary.get("spec_count", 0)
    code_count = summary.get("code_count", 0)
    orphan_specs = len(summary.get("orphan_specs", []))
    orphan_code = len(summary.get("orphan_code", []))

    return (
        f"📊 Coverage: {pct}% ({covered}/{total}) "
        f"| Specs: {spec_count} "
        f"| Code refs: {code_count} "
        f"| 🟡 {orphan_specs + orphan_code} total orphans"
    )


def render_one_line_coverage(pct: float, covered: int, total: int) -> str:
    """Render coverage as a single CI-friendly line."""
    if isinstance(pct, (int, float)):
        if pct >= 80:
            emoji = "🟢"
        elif pct >= 50:
            emoji = "🟡"
        else:
            emoji = "🔴"
    else:
        emoji = "📊"
    return f"{emoji} Coverage: {pct}% ({covered}/{total})"
