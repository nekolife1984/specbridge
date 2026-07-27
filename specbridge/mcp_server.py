"""MCP server for specbridge — AI agent integration.

Exposes specbridge analysis as MCP tools:
- analyze: run full analysis
- impact: find what implements a spec
- coverage: get spec coverage stats
- drift: detect spec-code drift
- validate_boundary: check code refs stay within boundaries

Usage:
    specbridge serve
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from specbridge.adapters import detect_all, merge_graphs
from specbridge.analyzers import coverage_summary, find_orphan_code, find_orphan_specs
from specbridge.analyzers.drift import build_snapshot, compute_drift, load_snapshot, save_snapshot
from specbridge.core import NodeType, find_spec_nodes

if TYPE_CHECKING:
    from mcp.types import TextContent, Tool  # noqa: F401


def create_mcp_server(project_dir: str = ".") -> object:
    """Create an MCP server instance with specbridge tools.

    Requires the 'mcp' optional dependency.
    """
    from mcp.server import Server
    from mcp.types import TextContent, Tool

    root = Path(project_dir).resolve()

    server = Server("specbridge")

    from specbridge.core import TraceGraph

    def _analyze_graph() -> TraceGraph:
        """Run all adapters and merge results."""
        scored = detect_all(str(root))
        if not scored:
            raise ValueError("No recognized SSD framework found")
        graphs = [adapter.analyze(str(root)) for _, adapter in scored]
        return merge_graphs(graphs)

    @server.list_tools()  # type: ignore[no-untyped-call, untyped-decorator]
    async def handle_list_tools() -> list[Tool]:
        return [
            Tool(
                name="analyze",
                description="Run full spec-code trace analysis on the project",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="impact",
                description="Find what implements a given spec (supports transitive impact via call graph)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "spec_id": {
                            "type": "string",
                            "description": "Spec ID (e.g. '1.1' or 'spec::1.1')",
                        },
                        "call_graph": {
                            "type": "boolean",
                            "description": "Include transitive (indirect) impact via call graph analysis",
                            "default": False,
                        },
                        "max_depth": {
                            "type": "integer",
                            "description": "Max call-graph traversal depth for transitive impact",
                            "default": 3,
                        },
                    },
                    "required": ["spec_id"],
                },
            ),
            Tool(
                name="coverage",
                description="Get spec coverage statistics",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="drift",
                description="Detect changes between snapshot and current state",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "take_snapshot": {
                            "type": "boolean",
                            "description": "Take a new snapshot before comparing",
                            "default": False,
                        },
                    },
                },
            ),
            Tool(
                name="validate_boundary",
                description="Check code refs stay within declared _Boundary:_ markers",
                inputSchema={"type": "object", "properties": {}},
            ),
        ]

    @server.call_tool()  # type: ignore[untyped-decorator]
    async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:  # type: ignore[return]
        if name == "analyze":
            graph = _analyze_graph()
            specs = len(graph.nodes_by_type(NodeType.SPEC))
            codes = len(graph.nodes_by_type(NodeType.CODE))
            tests = len(graph.nodes_by_type(NodeType.TEST))
            cov = coverage_summary(graph)
            return [TextContent(
                type="text",
                text=(
                    f"Project: {root}\n"
                    f"Nodes: {len(graph.nodes)} | Edges: {len(graph.edges)}\n"
                    f"Specs: {specs} | Code refs: {codes} | Tests: {tests}\n"
                    f"Coverage: {cov['coverage_pct']}% ({cov['covered']}/{cov['total']})"
                ),
            )]

        elif name == "impact":
            spec_id = arguments["spec_id"]
            call_graph_flag = arguments.get("call_graph", False)
            max_depth = arguments.get("max_depth", 3)

            graph = _analyze_graph()
            nodes = find_spec_nodes(graph, spec_id)
            if not nodes:
                return [TextContent(type="text", text=f"Spec '{spec_id}' not found.")]

            # Transitive impact via call graph
            transitive_info = ""
            if call_graph_flag:
                from specbridge.analyzers.call_graph import build_call_graph, transitive_impact
                cg = build_call_graph(graph, str(root))
                if cg.nodes:
                    ti = transitive_impact(graph, cg, spec_id, max_depth=max_depth)
                    tf = ti["transitive_files"]
                    if tf:
                        transitive_info = f"\n🔗 Transitive impact ({ti['hops']} hop(s)):\n" + \
                            "\n".join(f"  → {f}" for f in tf)

            lines = []
            for node in nodes:
                edges = graph.edges_to(node.id) or graph.edges_to(
                    spec_id.replace("spec::", "")
                )
                lines.append(f"Spec {node.id}: {node.title} (confidence: {node.confidence})")
                if not edges:
                    lines.append("  (no implementing artifacts found)")
                    continue

                for e in sorted(edges, key=lambda x: x.strength.value):
                    src = graph.nodes.get(e.src_id)
                    file_part = f" in {src.source.file}" if src else ""
                    lines.append(f"  [{e.strength.value.upper():8s}] {e.relation.value}{file_part}")

            result = "\n".join(lines)
            if transitive_info:
                result += transitive_info
            return [TextContent(type="text", text=result)]

        elif name == "coverage":
            graph = _analyze_graph()
            cov = coverage_summary(graph)
            orphans_spec = find_orphan_specs(graph)
            orphans_code = find_orphan_code(graph)
            lines = [
                f"Coverage: {cov['coverage_pct']}% ({cov['covered']}/{cov['total']})",
                f"Orphan specs: {len(orphans_spec)}",
                f"Orphan code:  {len(orphans_code)}",
            ]
            if orphans_spec:
                lines.append(f"  Uncovered specs: {', '.join(orphans_spec[:5])}")
            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "drift":
            take_snapshot_flag = arguments.get("take_snapshot", False)

            if take_snapshot_flag:
                snap = build_snapshot(str(root))
                save_snapshot(snap, str(root))
                return [TextContent(
                    type="text",
                    text=f"Snapshot taken: {len(snap['specs'])} specs, {len(snap['code'])} code files.",
                )]

            snapshot = load_snapshot(str(root))
            if snapshot is None:
                return [TextContent(
                    type="text",
                    text="No snapshot found. Run drift with take_snapshot=true first.",
                )]

            report = compute_drift(snapshot, str(root))
            return [TextContent(type="text", text=report.render_text())]

        elif name == "validate_boundary":
            graph = _analyze_graph()
            import fnmatch
            boundary_issues = []
            for nid, node in graph.nodes.items():
                if node.type != NodeType.SPEC:
                    continue
                boundaries = node.metadata.get("boundaries", [])
                if not boundaries:
                    continue
                impl_edges = [e for e in graph.edges_to(nid)
                              if e.relation.value in ("implements", "verifies")]
                if not impl_edges and nid.startswith("spec::"):
                    alt_id = nid.replace("spec::", "")
                    impl_edges = [e for e in graph.edges_to(alt_id)
                                  if e.relation.value in ("implements", "verifies")]
                for edge in impl_edges:
                    src = graph.nodes.get(edge.src_id)
                    if not src or not src.source.file:
                        continue
                    code_path = src.source.file
                    inside = any(
                        fnmatch.fnmatch(code_path, b["path"])
                        if any(c in b["path"] for c in "*?[")
                        else code_path.startswith(b["path"])
                        for b in boundaries
                    )
                    if not inside:
                        boundary_issues.append(
                            f"  {code_path} outside {', '.join(b['path'] for b in boundaries)}"
                        )
            if not boundary_issues:
                return [TextContent(type="text", text="All code refs are within declared boundaries.")]
            return [TextContent(
                type="text",
                text=f"Boundary violations ({len(boundary_issues)}):\n" + "\n".join(boundary_issues),
            )]

        else:
            raise ValueError(f"Unknown tool: {name}")

    return server


async def run_mcp_server(project_dir: str = ".") -> None:
    """Run the MCP server using stdio transport."""
    from mcp.server.stdio import stdio_server

    server = create_mcp_server(project_dir)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())  # type: ignore[attr-defined]
