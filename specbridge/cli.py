"""specbridge CLI — traceability analyzer for spec-driven development."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from specbridge import __version__
from specbridge.core import NodeType, find_spec_nodes
from specbridge.outputs.json_out import render_json
from specbridge.outputs.text import render_text


@click.group()
@click.version_option(version=__version__, prog_name="specbridge")
def cli() -> None:
    """Spec ↔ Code bridge: read-only traceability analyzer for SSD."""


@cli.command()
@click.option("--dir", "-d", default=".", help="Project directory to analyze", show_default=True)
@click.option("--format", "output_fmt", default="text", type=click.Choice(["text", "json", "html"]),
              help="Output format (text, json, or html)", show_default=True)
@click.option("--merge", "-m", is_flag=True, default=False,
              help="Merge results from ALL matching adapters (not just the best one)",
              show_default=True)
@click.option("--top", type=int, default=None,
              help="Show only top N items per category (default: all)", show_default=True)
@click.option("--deps", is_flag=True, default=False,
              help="Build code dependency graph from imports (adds DEPENDS edges)",
              show_default=True)
@click.option("--call-graph", "-c", is_flag=True, default=False,
              help="Build call graph for transitive impact analysis",
              show_default=True)
@click.option("--fast", is_flag=True, default=False,
              help="Skip function-level matching for faster analysis on large projects",
              show_default=True)
def analyze(dir: str, output_fmt: str, merge: bool, top: int | None, deps: bool,
            call_graph: bool, fast: bool) -> None:
    """Analyze a project and build a trace graph."""
    from specbridge.adapters import detect_adapter, detect_all, merge_graphs

    root = Path(dir).resolve()
    click.echo(f"🔍 Scanning {root} ...", err=True)

    if merge:
        scored = detect_all(str(root))
        if not scored:
            click.echo("❌ No recognized SSD framework found.", err=True)
            raise click.Abort()
        graphs = []
        for score, adapter in scored:
            click.echo(f"   Using {type(adapter).__name__} (confidence {score})", err=True)
            if fast and hasattr(adapter, 'fast'):
                adapter.fast = True
            g = adapter.analyze(str(root))
            graphs.append(g)
        graph = merge_graphs(graphs)
    else:
        detected = detect_adapter(str(root))
        if detected is None:
            click.echo("❌ No recognized SSD framework found.", err=True)
            raise click.Abort()
        if fast and hasattr(detected, 'fast'):
            detected.fast = True
        graph = detected.analyze(str(root))

    # Build code dependency graph if requested
    if deps:
        from specbridge.analyzers.graph import build_code_dependency_graph
        before = len(graph.edges)
        build_code_dependency_graph(graph, str(root))
        dep_count = len(graph.edges) - before
        click.echo(f"   Deps:   {dep_count} import edges", err=True)

    if call_graph:
        from specbridge.analyzers.call_graph import build_call_graph
        cg = build_call_graph(graph, str(root))
        edge_count = len(cg.edges)
        node_count = len(cg.nodes)
        click.echo(f"   Calls:  {edge_count} edges, {node_count} functions", err=True)
        # Store call graph reference for downstream commands
        # (call graph will be rebuilt from the trace graph when needed)

    spec_count = len(graph.nodes_by_type(NodeType.SPEC))
    code_count = len(graph.nodes_by_type(NodeType.CODE))
    test_count = len(graph.nodes_by_type(NodeType.TEST))
    click.echo(f"\n   Nodes: {len(graph.nodes)} | Edges: {len(graph.edges)}", err=True)
    click.echo(f"   Specs: {spec_count} | Code refs: {code_count} | Tests: {test_count}", err=True)

    if output_fmt == "json":
        click.echo(render_json(graph))
    elif output_fmt == "html":
        from specbridge.outputs.html import render_html
        html = render_html(graph)
        out_path = root / ".specbridge" / "trace.html"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html, encoding="utf-8")
        click.echo(f"   📊 HTML graph saved to: {out_path}", err=True)
        import webbrowser
        webbrowser.open(f"file://{out_path.resolve()}")
    else:
        click.echo(render_text(graph, max_nodes=top))


@cli.command()
@click.option("--dir", "-d", default=".", help="Project directory", show_default=True)
@click.option("--spec-id", required=True, help="Spec ID to analyze (e.g. 1.1)")
@click.option("--format", "output_fmt", default="text", type=click.Choice(["text", "json"]),
              help="Output format", show_default=True)
@click.option("--call-graph", "-c", is_flag=True, default=False,
              help="Include transitive (indirect) impact via call graph",
              show_default=True)
@click.option("--max-depth", type=int, default=3,
              help="Max call-graph traversal depth for transitive impact",
              show_default=True)
def impact(dir: str, spec_id: str, output_fmt: str, call_graph: bool, max_depth: int) -> None:
    """Find what implements a given spec."""
    from specbridge.adapters import detect_adapter

    root = Path(dir).resolve()
    adapter = detect_adapter(str(root))
    if adapter is None:
        click.echo("❌ No recognized SSD framework found.", err=True)
        raise click.Abort()

    graph = adapter.analyze(str(root))

    # If no exact match, try merging ALL adapters for broader search
    if not find_spec_nodes(graph, spec_id):
        from specbridge.adapters import detect_all, merge_graphs

        scored = detect_all(str(root))
        extra_graphs = [graph]
        for score, inst in scored:
            if inst is not adapter:
                click.echo(f"   Merging {type(inst).__name__} (confidence {score})", err=True)
                extra_graphs.append(inst.analyze(str(root)))
        if len(extra_graphs) > 1:
            graph = merge_graphs(extra_graphs)

    spec_nodes = find_spec_nodes(graph, spec_id)
    if not spec_nodes:
        click.echo(f"❌ Spec '{spec_id}' not found in trace graph.", err=True)
        click.echo("   Try a more specific ID (e.g. '07-cli-commands.1.1' or a partial title).", err=True)
        raise click.Abort()

    # Transitive impact via call graph
    transitive_files: list[str] = []
    transitives: list[tuple[str, str]] = []
    if call_graph:
        from specbridge.analyzers.call_graph import build_call_graph, transitive_impact
        cg = build_call_graph(graph, str(root))
        if cg.nodes:
            ti = transitive_impact(graph, cg, spec_id, max_depth=max_depth)
            transitive_files = ti["transitive_files"]
            transitives = ti["transitive_edges"]
            if transitive_files:
                click.echo(f"\n   🔗 Transitive impact ({ti['hops']} hop(s)):")
                for f in transitive_files:
                    click.echo(f"      → {f}")

    for spec_node in spec_nodes:
        edges = graph.edges_to(spec_node.id)
        if not edges:
            click.echo(f"📄 {spec_node.id}: {spec_node.title}")
            click.echo("   (no implementing artifacts found)")
            continue

        click.echo(f"📄 {spec_node.id}: {spec_node.title}")
        click.echo(f"   Confidence: {spec_node.confidence}")
        click.echo(f"   Source: {spec_node.source.file}")

    for e in sorted(edges, key=lambda x: x.strength.value):
        src = graph.nodes.get(e.src_id)
        if src:
            click.echo(f"  [{e.strength.value.upper():8s}] {src.source.file}  ({e.relation.value})")
            for ev in e.evidence[:2]:
                click.echo(f"            ∵ {ev.kind}: {ev.value}")

    if output_fmt == "json":
        import json as _json
        results = []
        for spec_node in spec_nodes:
            edges = graph.edges_to(spec_node.id)
            entry: dict[str, Any] = {
                "spec_id": spec_node.id,
                "title": spec_node.title,
                "edges": [{"src": e.src_id, "relation": e.relation.value, "strength": e.strength.value,
                           "evidence": [{"kind": ev.kind, "value": ev.value} for ev in e.evidence]}
                          for e in edges],
            }
            if transitive_files:
                entry["transitive_files"] = transitive_files
                entry["transitive_edges"] = transitives
            results.append(entry)
        click.echo(_json.dumps(results if len(results) > 1 else results[0], indent=2, ensure_ascii=False))


@cli.command()
@click.option("--dir", "-d", default=".", help="Project directory", show_default=True)
@click.option("--format", "output_fmt", default="text", type=click.Choice(["text", "json"]),
              help="Output format", show_default=True)
def coverage(dir: str, output_fmt: str) -> None:
    """Show spec coverage statistics."""
    from specbridge.adapters import detect_adapter
    from specbridge.analyzers import coverage_summary, find_orphan_code, find_orphan_specs

    root = Path(dir).resolve()
    adapter = detect_adapter(str(root))
    if adapter is None:
        click.echo("❌ No recognized SSD framework found.", err=True)
        raise click.Abort()

    graph = adapter.analyze(str(root))
    cov = coverage_summary(graph)
    orphans_spec = find_orphan_specs(graph)
    orphans_code = find_orphan_code(graph)

    if output_fmt == "json":
        import json as _json
        click.echo(_json.dumps({
            **cov,
            "orphan_specs": orphans_spec,
            "orphan_code": orphans_code,
        }, indent=2, ensure_ascii=False))
        return

    click.echo("📊 Spec Coverage")
    click.echo(f"{'=' * 40}")
    click.echo(f"  Total specs:  {cov['total']}")
    click.echo(f"  Covered:      {cov['covered']}")
    click.echo(f"  Orphan specs: {cov['orphan']}")
    click.echo(f"  Coverage:     {cov['coverage_pct']}%")
    if orphans_spec:
        click.echo("\n🟡 Orphan specs (no code ref):")
        for nid in orphans_spec:
            click.echo(f"   - {nid}")
    if orphans_code:
        click.echo("\n🟡 Orphan code files (no spec ref):")
        for nid in orphans_code[:10]:
            click.echo(f"   - {nid}")
        if len(orphans_code) > 10:
            click.echo(f"   ... and {len(orphans_code) - 10} more")


@cli.command()
@click.option("--dir", "-d", default=".", help="Project directory", show_default=True)
@click.option("--reason", default="", help="Description of why snapshot was taken")
def snapshot(dir: str, reason: str) -> None:
    """Take a structural snapshot of specs and code."""
    from specbridge.analyzers.drift import build_snapshot, save_snapshot
    from specbridge.config import SpecbridgeConfig

    root = Path(dir).resolve()
    click.echo(f"📸 Snapshotting {root} ...", err=True)

    cfg = SpecbridgeConfig.load(str(root))
    snap = build_snapshot(
        str(root),
        reason=reason,
        spec_dirs=cfg.spec_dirs,
        source_dirs=cfg.source_dirs,
    )
    path = save_snapshot(snap, str(root))

    click.echo(f"   Specs: {len(snap['specs'])} | Code files: {len(snap['code'])}")
    click.echo(f"   Coverage: {snap['coverage']['coverage_pct']}%")
    click.echo(f"   Saved: {path}")


@cli.command()
@click.option("--dir", "-d", default=".", help="Project directory", show_default=True)
@click.option("--snapshot", "snapshot_path", default=None,
              help="Path to snapshot file (default: .specbridge/snapshot.json)")
@click.option("--gate", is_flag=True, help="Exit with code 1 if drift detected")
@click.option("--format", "output_fmt", default="text", type=click.Choice(["text", "json"]),
              help="Output format", show_default=True)
@click.option("--git-base", default=None,
              help="Git base ref to diff against (alternative to snapshot comparison)")
def drift(dir: str, snapshot_path: str | None, gate: bool, output_fmt: str, git_base: str | None) -> None:
    """Detect changes between snapshot and current state."""
    root = Path(dir).resolve()

    if git_base:
        _drift_git(str(root), git_base, gate)
        return

    from specbridge.analyzers.drift import compute_drift, load_snapshot
    from specbridge.config import SpecbridgeConfig

    if snapshot_path:
        snap_path = Path(snapshot_path)
        click.echo(f"   Loading snapshot: {snap_path}", err=True)
        try:
            import json
            snapshot = json.loads(snap_path.read_text(encoding="utf-8"))
        except Exception as e:
            click.echo(f"❌ Failed to load snapshot: {e}", err=True)
            raise click.Abort() from e
    else:
        snapshot = load_snapshot(str(root))
        if snapshot is None:
            click.echo("❌ No snapshot found. Run 'specbridge snapshot' first.", err=True)
            raise click.Abort()

    click.echo(f"🔍 Comparing {root} against snapshot from {snapshot.get('timestamp', '?')} ...", err=True)

    cfg = SpecbridgeConfig.load(str(root))
    report = compute_drift(
        snapshot, str(root),
        spec_dirs=cfg.spec_dirs,
        source_dirs=cfg.source_dirs,
    )

    if output_fmt == "json":
        import json as _json
        click.echo(_json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    else:
        click.echo("")
        click.echo(report.render_text())

    if gate and report.has_drift:
        raise SystemExit(1)


def _drift_git(project_dir: str, git_base: str, gate: bool) -> None:
    """Git-based drift detection (alternative to snapshot comparison)."""
    import subprocess

    from specbridge.adapters import detect_adapter

    root = Path(project_dir).resolve()

    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", git_base],
            capture_output=True, text=True, check=True, cwd=str(root),
        )
    except subprocess.CalledProcessError as e:
        click.echo(f"❌ git diff failed: {e}", err=True)
        raise click.Abort() from e

    changed = [f for f in result.stdout.strip().split("\n") if f]
    if not changed:
        click.echo("✅ No changes detected.")
        return

    adapter = detect_adapter(str(root))
    if adapter is None:
        click.echo("❌ No recognized SSD framework found.", err=True)
        raise click.Abort()

    graph = adapter.analyze(str(root))

    affected: list[dict[str, Any]] = []
    for cf in changed:
        for nid, node in graph.nodes.items():
            if node.type in (NodeType.CODE, NodeType.TEST) and node.source.file == cf:
                for edge in graph.edges_from(nid):
                    if edge.relation.value in ("implements", "verifies", "satisfies"):
                        affected.append({"file": cf, "spec_id": edge.dst_id})

    if not affected:
        click.echo("✅ No spec-impacting changes detected.")
        return

    click.echo(f"⚠️  {len(affected)} spec-affecting change(s):")
    for a in affected:
        click.echo(f"   {a['file']} → affects spec {a['spec_id']}")

    if gate:
        click.echo("\n❌ Gate failed — drift detected.", err=True)
        raise SystemExit(1)


@cli.command()
@click.option("--dir", "-d", default=".", help="Project directory", show_default=True)
def validate_boundary(dir: str) -> None:
    """Validate that code refs stay within declared _Boundary:_ markers."""
    from specbridge.adapters import detect_adapter
    from specbridge.core import NodeType

    root = Path(dir).resolve()
    adapter = detect_adapter(str(root))
    if adapter is None:
        click.echo("❌ No recognized SSD framework found.", err=True)
        raise click.Abort()

    graph = adapter.analyze(str(root))

    # Find spec nodes with boundaries
    boundary_issues = []
    for nid, node in graph.nodes.items():
        if node.type != NodeType.SPEC:
            continue
        boundaries = node.metadata.get("boundaries", [])
        if not boundaries:
            continue

        # Check each implementing code file against boundaries
        # Try primary ID first, then fallback id (e.g. "spec::1.1" → "1.1")
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
            import fnmatch
            inside = any(
                fnmatch.fnmatch(code_path, b["path"])
                if any(c in b["path"] for c in "*?[")
                else code_path.startswith(b["path"])
                for b in boundaries
            )
            if not inside:
                boundary_issues.append({
                    "spec_id": nid,
                    "code_file": code_path,
                    "boundaries": [b["path"] for b in boundaries],
                    "spec_file": boundaries[0]["file"],
                })

    if not boundary_issues:
        click.echo("✅ All code refs are within declared boundaries.")
        return

    click.echo(f"⚠️  {len(boundary_issues)} boundary violation(s):")
    for bi in boundary_issues:
        click.echo(f"  {bi['spec_id']} in {bi['spec_file']}")
        click.echo(f"    declares boundaries: {', '.join(bi['boundaries'])}")
        click.echo(f"    but {bi['code_file']} is outside")
    click.echo("\nTip: Add _Boundary:_ src/path/ or move the @impl to a file inside the boundary.")


@cli.command()
@click.option("--dir", "-d", default=".", help="Project directory", show_default=True)
@click.option("--yaml", "yaml_output", is_flag=True, default=False,
              help="Output config as YAML")
def config(dir: str, yaml_output: bool) -> None:
    """Show current specbridge configuration."""
    from specbridge.config import SpecbridgeConfig

    root = Path(dir).resolve()
    cfg = SpecbridgeConfig.load(str(root))

    if yaml_output:
        import yaml
        click.echo(yaml.dump({
            "spec_dirs": cfg.spec_dirs,
            "source_dirs": cfg.source_dirs,
            "exclude_dirs": sorted(cfg.exclude_dirs),
            "min_confidence": cfg.min_confidence,
            "max_output_nodes": cfg.max_output_nodes,
        }, default_flow_style=False))
        return

    # Detect config source
    yaml_path = root / ".specbridge.yaml"
    pyproject = root / "pyproject.toml"
    source = "defaults"
    if yaml_path.exists():
        source = ".specbridge.yaml"
    elif pyproject.exists():
        try:
            import tomllib  # type: ignore[import-not-found]
            py_data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            if "tool" in py_data and "specbridge" in py_data["tool"]:
                source = "pyproject.toml [tool.specbridge]"
        except Exception:
            pass

    click.echo(f"📋 specbridge config ({source})")
    click.echo(f"{'=' * 40}")
    click.echo(f"  spec_dirs:        {cfg.spec_dirs}")
    click.echo(f"  source_dirs:      {cfg.source_dirs}")
    click.echo(f"  exclude_dirs:     {len(cfg.exclude_dirs)} patterns")
    click.echo(f"  min_confidence:   {cfg.min_confidence}")
    click.echo(f"  max_output_nodes: {cfg.max_output_nodes}")


@cli.command()
@click.option("--dir", "-d", default=".", help="Project directory", show_default=True)
@click.option("--interval", type=float, default=2.0,
              help="Debounce interval in seconds", show_default=True)
@click.option("--fast", is_flag=True, default=False,
              help="Skip function-level matching for faster analysis",
              show_default=True)
def watch(dir: str, interval: float, fast: bool) -> None:
    """Watch project for changes and re-analyze automatically.

    Requires the optional 'watch' extra: pip install specbridge[watch]
    """
    from specbridge.adapters import detect_all, merge_graphs
    from specbridge.config import SpecbridgeConfig
    from specbridge.outputs.text import render_text

    root = Path(dir).resolve()

    try:
        from watchdog.events import FileSystemEventHandler  # type: ignore[import-not-found]
        from watchdog.observers import Observer  # type: ignore[import-not-found]
    except ImportError:
        click.echo("❌ watchdog not installed. Run: pip install specbridge[watch]",
                    err=True)
        raise click.Abort() from None

    class SpecbridgeHandler(FileSystemEventHandler):  # type: ignore[misc]
        def __init__(self) -> None:
            self._last_run = 0.0
            import time
            self._time = time

        def on_any_event(self, event: Any) -> None:
            # Ignore directory and .specbridge changes to avoid re-trigger loops
            if event.is_directory:
                return
            if ".specbridge" in str(event.src_path):
                return

            # Debounce
            now = self._time.time()
            if now - self._last_run < interval:
                return
            self._last_run = now

            # Run analysis
            click.clear()
            click.echo(f"🔄 Change detected: {event.src_path}", err=True)
            click.echo(f"   Re-analyzing {root} ...\n", err=True)

            try:
                config = SpecbridgeConfig.load(str(root))
                scored = detect_all(str(root))
                if scored:
                    graphs = []
                    for _score, adapter in scored:
                        if fast and hasattr(adapter, 'fast'):
                            adapter.fast = True
                        try:
                            g = adapter.analyze(str(root))
                            graphs.append(g)
                        except Exception as exc:
                            click.echo(f"   ⚠️  {type(adapter).__name__} failed: {exc}",
                                      err=True)
                    if graphs:
                        merged = merge_graphs(graphs)
                        click.echo(render_text(merged, max_nodes=config.max_output_nodes))
                        click.echo(f"\n⏳ Watching {root} ... (Ctrl+C to stop)", err=True)
                else:
                    click.echo("❌ No recognized SSD framework found.", err=True)
            except Exception as exc:
                click.echo(f"❌ Analysis error: {exc}", err=True)

    click.echo(f"⏳ Watching {root} for changes ... (Ctrl+C to stop)", err=True)
    click.echo(f"   Interval: {interval}s", err=True)

    event_handler = SpecbridgeHandler()
    observer = Observer()
    observer.schedule(event_handler, str(root), recursive=True)
    observer.start()
    try:
        while observer.is_alive():
            observer.join(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


@cli.command()
@click.option("--refresh", is_flag=True, help="Re-scan installed packages for new plugins")
def plugins(refresh: bool) -> None:
    """List installed specbridge adapter plugins."""
    from specbridge.adapters import all_adapters, discover_plugins, plugin_adapters

    count = 0
    if refresh:
        count = discover_plugins()
        if count:
            click.echo(f"🔌 Discovered {count} new plugin adapter(s).", err=True)

    builtins = [c for c in all_adapters()
                if c.__name__ not in dict(plugin_adapters())]
    plugins_loaded = plugin_adapters()

    click.echo("📦 specbridge Adapters")
    click.echo(f"{'=' * 50}")
    click.echo(f"\n🏠 Built-in ({len(builtins)}):")
    for cls in builtins:
        click.echo(f"   • {cls.__name__}")

    if plugins_loaded:
        click.echo(f"\n🔌 Plugins ({len(plugins_loaded)}):")
        for name, pkg in plugins_loaded:
            click.echo(f"   • {name}  (from {pkg})")
    else:
        click.echo("\n🔌 Plugins (0)")
        click.echo("   No external plugins installed.")
        click.echo("   See: https://github.com/nekolife1984/specbridge#writing-a-plugin")


@cli.command()
@click.option("--dir", "-d", default=".", help="Project directory", show_default=True)
def serve(dir: str) -> None:
    """Start MCP server for AI agent integration.

    Exposes specbridge tools (analyze, impact, coverage, drift, validate_boundary)
    via the Model Context Protocol. Requires: pip install specbridge[mcp]
    """
    import asyncio
    try:
        from specbridge.mcp_server import run_mcp_server
    except ImportError as exc:
        click.echo(f"❌ MCP dependencies not installed: {exc}", err=True)
        click.echo("   Run: pip install specbridge[mcp]", err=True)
        raise click.Abort() from None

    click.echo(f"🔌 Starting specbridge MCP server for {dir} ...", err=True)
    click.echo("   Connect via stdio transport.", err=True)
    asyncio.run(run_mcp_server(str(dir)))


@cli.command()
@click.option("--dir", "-d", default=".", help="Project directory", show_default=True)
@click.option("--spec-id", required=True, help="Spec ID to analyze (e.g. 1.1)")
@click.option("--max-depth", type=int, default=3,
              help="Max call-graph traversal depth", show_default=True)
@click.option("--format", "output_fmt", default="text", type=click.Choice(["text", "json"]),
              help="Output format", show_default=True)
def call_graph(dir: str, spec_id: str, max_depth: int, output_fmt: str) -> None:
    """Build call graph and show transitive (indirect) impact for a spec.

    Analyzes function-level call relationships in the codebase to
    find files that are indirectly impacted by changes to a spec.
    """
    from specbridge.adapters import detect_adapter
    from specbridge.analyzers.call_graph import build_call_graph, transitive_impact
    from specbridge.core import find_spec_nodes

    root = Path(dir).resolve()
    adapter = detect_adapter(str(root))
    if adapter is None:
        click.echo("❌ No recognized SSD framework found.", err=True)
        raise click.Abort()

    graph = adapter.analyze(str(root))

    spec_nodes = find_spec_nodes(graph, spec_id)
    if not spec_nodes:
        click.echo(f"❌ Spec '{spec_id}' not found.", err=True)
        raise click.Abort()

    cg = build_call_graph(graph, str(root))
    if not cg.nodes:
        click.echo("⚠️  No call graph could be built — no function-level nodes found.", err=True)
        click.echo("   Run `specbridge analyze --deps` first to extract function blocks.", err=True)
        raise click.Abort()

    click.echo(f"🔗 Call graph: {len(cg.nodes)} functions, {len(cg.edges)} calls", err=True)

    ti = transitive_impact(graph, cg, spec_id, max_depth=max_depth)
    direct = ti["direct_files"]
    transitive = ti["transitive_files"]
    hops = ti["hops"]

    click.echo(f"\n📄 Spec: {spec_id}")
    click.echo(f"   Direct files:     {len(direct)}")
    for f in direct:
        click.echo(f"     📁 {f}")
    click.echo(f"   🔗 Transitive files ({hops} hop(s)): {len(transitive)}")
    for f in transitive:
        click.echo(f"     → {f}")

    if output_fmt == "json":
        import json as _json
        click.echo(_json.dumps(ti, indent=2, ensure_ascii=False))


@cli.command()
@click.option("--dir", "-d", default=".", help="Project directory to set up", show_default=True)
@click.option("--ci", is_flag=True, default=False,
              help="Also create GitHub Actions CI workflow", show_default=True)
def setup(dir: str, ci: bool) -> None:
    """One‑command setup: install hook, create config, deploy AGENTS.md.

    Runs the interactive setup script that:

    \\b
    - Creates .specbridge.yaml (auto‑detects source/spec dirs)
    - Installs pre‑commit drift hook
    - Deploys AGENTS.md for AI agent workflow guidance
    - Deploys Hermes skill (if ~/.hermes/ exists)
    - Takes initial snapshot
    - Optionally sets up GitHub Actions CI

    Equivalent to: \\b bash scripts/setup.sh
    """
    root = Path(dir).resolve()
    if not root.exists():
        click.echo(f"❌ Directory '{root}' does not exist.", err=True)
        raise click.Abort()

    # Locate the setup.sh script relative to the specbridge installation
    # Try several locations: alongside the package, in the repo, via pip show
    candidates = [
        Path(__file__).resolve().parent.parent / "scripts" / "setup.sh",
        Path(__file__).resolve().parent.parent.parent / "scripts" / "setup.sh",
        Path.cwd() / "scripts" / "setup.sh",
    ]
    setup_script: Path | None = None
    for c in candidates:
        if c.exists():
            setup_script = c
            break

    if setup_script is None:
        click.echo("❌ Could not find scripts/setup.sh", err=True)
        click.echo("   Download it manually:", err=True)
        click.echo("     curl -fsSL https://raw.githubusercontent.com/nekolife1984/specbridge/main/scripts/setup.sh | bash", err=True)
        raise click.Abort()

    import os
    import subprocess
    env = os.environ.copy()
    if ci:
        env["CI_SETUP"] = "1"
    result = subprocess.run(
        ["bash", str(setup_script), str(root)],
        env=env,
    )
    if result.returncode != 0:
        click.echo("❌ Setup script failed.", err=True)
        raise click.Abort()


if __name__ == "__main__":
    cli()
