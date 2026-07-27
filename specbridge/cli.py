"""specbridge CLI — traceability analyzer for spec-driven development."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from specbridge import __version__
from specbridge.core import NodeType, find_spec_nodes
from specbridge.outputs.json_out import render_json
from specbridge.outputs.text import render_text


@click.group(name="specbridge")
@click.version_option(version=__version__, prog_name="specbridge")
def cli() -> None:
    """Spec ↔ Code bridge: read-only traceability analyzer for SSD."""


def _no_adapter_hint() -> None:
    click.echo("   Hints:", err=True)
    click.echo("     • Ensure you are in a project with Markdown spec docs and source code.", err=True)
    click.echo("     • Default spec dirs: docs/, spec/, specs/", err=True)
    click.echo("     • Default source dirs: src/, lib/, app/", err=True)
    click.echo("     • Create .specbridge.yaml to configure custom directories.", err=True)
    click.echo("     • Run 'specbridge config' to see current discovered settings.", err=True)


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
@click.option("--dry-run", is_flag=True, default=False,
              help="Analyze without writing any output files (.specbridge/)",
              show_default=True)
@click.option("--summary-only", is_flag=True, default=False,
              help="Show only a one-line coverage summary (CI-friendly)",
              show_default=True)
def analyze(dir: str, output_fmt: str, merge: bool, top: int | None, deps: bool,
            call_graph: bool, fast: bool, dry_run: bool, summary_only: bool) -> None:
    """Analyze a project and build a trace graph."""
    from specbridge.adapters import detect_adapter, detect_all, merge_graphs
    from specbridge.outputs.rich_utils import get_console, progress_spinner

    root = Path(dir).resolve()
    console = get_console()

    with progress_spinner("🔍 Scanning project..."):
        if merge:
            scored = detect_all(str(root))
            if not scored:
                click.echo("❌ No recognized SSD framework found.", err=True)
                _no_adapter_hint()
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
                _no_adapter_hint()
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

    # CI-friendly one-line summary
    if summary_only:
        from specbridge.outputs.text import render_one_line_coverage
        from specbridge.analyzers import coverage_summary
        cov = coverage_summary(graph)
        click.echo(render_one_line_coverage(
            float(cov["coverage_pct"]), int(cov["covered"]), int(cov["total"])
        ))
        return

    click.echo(f"\n   Nodes: {len(graph.nodes)} | Edges: {len(graph.edges)}", err=True)
    click.echo(f"   Specs: {spec_count} | Code refs: {code_count} | Tests: {test_count}", err=True)

    if output_fmt == "json":
        click.echo(render_json(graph))
    elif output_fmt == "html":
        from specbridge.outputs.html import render_html
        html = render_html(graph)
        if dry_run:
            click.echo("   📄 HTML output generated (--dry-run, not saved)", err=True)
        else:
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
        _no_adapter_hint()
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
        _no_adapter_hint()
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
@click.option("--config", "cfg_path", default=None,
              help="Path to config file (default: auto-discover .specbridge.yaml / pyproject.toml)",
              show_default=True)
@click.option("--reason", default="", help="Description of why snapshot was taken")
@click.option("--dry-run", is_flag=True, default=False,
              help="Build snapshot without writing to disk",
              show_default=True)
def snapshot(dir: str, cfg_path: str | None, reason: str, dry_run: bool) -> None:
    """Take a structural snapshot of specs and code."""
    from specbridge.analyzers.drift import build_snapshot, save_snapshot
    from specbridge.config import SpecbridgeConfig
    from specbridge.outputs.rich_utils import progress_spinner

    root = Path(dir).resolve()

    with progress_spinner("📸 Snapshotting..."):
        cfg = SpecbridgeConfig.load(str(root), config_path=cfg_path)
        snap = build_snapshot(
            str(root),
            reason=reason,
            spec_dirs=cfg.spec_dirs,
            source_dirs=cfg.source_dirs,
            spec_files=cfg.spec_files,
            source_files=cfg.source_files,
        )
        if not dry_run:
            path = save_snapshot(snap, str(root))

    click.echo(f"   Specs: {len(snap['specs'])} | Code files: {len(snap['code'])}")
    click.echo(f"   Coverage: {snap['coverage']['coverage_pct']}%")
    if dry_run:
        click.echo(f"   (--dry-run, snapshot not saved)")
    else:
        click.echo(f"   Saved: {path}")


@cli.command()
@click.option("--dir", "-d", default=".", help="Project directory", show_default=True)
@click.option("--config", "cfg_path", default=None,
              help="Path to config file (default: auto-discover .specbridge.yaml / pyproject.toml)",
              show_default=True)
@click.option("--snapshot", "snapshot_path", default=None,
              help="Path to snapshot file (default: .specbridge/snapshot.json)")
@click.option("--gate", is_flag=True, help="Exit with code 1 if drift detected")
@click.option("--format", "output_fmt", default="text", type=click.Choice(["text", "json"]),
              help="Output format", show_default=True)
@click.option("--git-base", default=None,
              help="Git base ref to diff against (alternative to snapshot comparison)")
def drift(dir: str, cfg_path: str | None, snapshot_path: str | None, gate: bool, output_fmt: str, git_base: str | None) -> None:
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

    cfg = SpecbridgeConfig.load(str(root), config_path=cfg_path)
    report = compute_drift(
        snapshot, str(root),
        spec_dirs=cfg.spec_dirs,
        source_dirs=cfg.source_dirs,
        spec_files=cfg.spec_files,
        source_files=cfg.source_files,
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
        _no_adapter_hint()
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
@click.option("--format", "output_fmt", default="text", type=click.Choice(["text", "json"]),
              help="Output format", show_default=True)
def status(dir: str, output_fmt: str) -> None:
    """Show project state dashboard: config, snapshot, coverage, drift in one view."""
    from specbridge.analyzers import coverage_summary, find_orphan_code, find_orphan_specs
    from specbridge.analyzers.drift import load_snapshot
    from specbridge.config import SpecbridgeConfig
    from specbridge.adapters import detect_adapter

    root = Path(dir).resolve()

    # 1. Config
    cfg = SpecbridgeConfig.load(str(root))
    click.echo("📋 specbridge Status")
    click.echo(f"{'=' * 50}")

    click.echo(f"\n🔧 Configuration:")
    click.echo(f"   spec_dirs:        {cfg.spec_dirs}")
    click.echo(f"   source_dirs:      {cfg.source_dirs}")
    click.echo(f"   exclude_dirs:     {len(cfg.exclude_dirs)} patterns")
    click.echo(f"   min_confidence:   {cfg.min_confidence}")

    # 2. Snapshot info
    snap = load_snapshot(str(root))
    if snap:
        click.echo(f"\n📸 Snapshot:")
        click.echo(f"   Taken:           {snap.get('timestamp', '?')}")
        click.echo(f"   Reason:          {snap.get('reason', '(none)') or '(none)'}")
        cov_snap = snap.get("coverage", {})
        click.echo(f"   Coverage:        {cov_snap.get('coverage_pct', '?')}%")
        click.echo(f"   Specs (snap):    {cov_snap.get('spec_count', '?')}")
        click.echo(f"   Code files:      {cov_snap.get('code_count', '?')}")
    else:
        click.echo(f"\n📸 Snapshot:        (none)")
        click.echo("   Run 'specbridge snapshot' to create one.")

    # 3. Current coverage
    adapter = detect_adapter(str(root))
    if adapter:
        graph = adapter.analyze(str(root))
        cov = coverage_summary(graph)
        orphans_spec = find_orphan_specs(graph)
        orphans_code = find_orphan_code(graph)

        delta_pct = ""
        if snap:
            snap_pct = snap.get("coverage", {}).get("coverage_pct", 0)
            curr_pct = cov["coverage_pct"]
            if isinstance(snap_pct, (int, float)) and isinstance(curr_pct, (int, float)):
                diff = round(curr_pct - snap_pct, 1)
                sign = "+" if diff >= 0 else ""
                delta_pct = f" ({sign}{diff}% from snapshot)"

        click.echo(f"\n📊 Current Coverage:")
        click.echo(f"   Coverage:        {cov['coverage_pct']}%{delta_pct}")
        click.echo(f"   Total specs:     {cov['total']}")
        click.echo(f"   Covered:         {cov['covered']}")
        click.echo(f"   Orphan specs:    {len(orphans_spec)}")
        click.echo(f"   Orphan code:     {len(orphans_code)}")
    else:
        click.echo(f"\n📊 Current Coverage: (no adapter found)")

    # 4. Drift check
    if snap:
        from specbridge.analyzers.drift import compute_drift
        report = compute_drift(
            snap, str(root),
            spec_dirs=cfg.spec_dirs,
            source_dirs=cfg.source_dirs,
            spec_files=cfg.spec_files,
            source_files=cfg.source_files,
        )
        if report.has_drift:
            click.echo(f"\n⚠️  Drift detected! Run 'specbridge drift' for details.")
        else:
            click.echo(f"\n✅ No drift detected — project state matches snapshot.")

    if output_fmt == "json":
        import json as _json
        result = {
            "config": {
                "spec_dirs": cfg.spec_dirs,
                "source_dirs": cfg.source_dirs,
                "min_confidence": cfg.min_confidence,
            },
            "snapshot": {
                "exists": snap is not None,
                "timestamp": snap.get("timestamp") if snap else None,
                "coverage": snap.get("coverage") if snap else None,
            } if snap else {"exists": False},
            "coverage": cov if adapter else None,
        }
        click.echo(_json.dumps(result, indent=2, ensure_ascii=False))


@cli.command()
@click.option("--dir", "-d", default=".", help="Project directory", show_default=True)
@click.option("--config", "cfg_path", default=None,
              help="Path to config file (default: auto-discover .specbridge.yaml / pyproject.toml)",
              show_default=True)
@click.option("--yaml", "yaml_output", is_flag=True, default=False,
              help="Output config as YAML")
@click.option("--validate", "do_validate", is_flag=True, default=False,
              help="Validate configuration for correctness")
def config(dir: str, cfg_path: str | None, yaml_output: bool, do_validate: bool) -> None:
    """Show current specbridge configuration."""
    from specbridge.config import SpecbridgeConfig

    root = Path(dir).resolve()
    cfg = SpecbridgeConfig.load(str(root), config_path=cfg_path)

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

    if do_validate:
        issues = _validate_config(cfg, root)
        if issues:
            click.echo("\n❌ Validation failed:")
            for issue in issues:
                click.echo(f"  • {issue}")
            raise click.Abort()
        click.echo("  ✅ Configuration is valid.\n")

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
                    _no_adapter_hint()
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
        _no_adapter_hint()
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


@cli.command()
@click.option("--dir", "-d", default=".", help="Project directory to initialize", show_default=True)
@click.option("--force", is_flag=True, default=False,
              help="Overwrite existing .specbridge.yaml without confirmation")
def init(dir: str, force: bool) -> None:
    """Interactive config generator — create .specbridge.yaml step by step.

    Scans the project for spec directories (docs/, spec/, specs/, ...) and
    source directories (src/, lib/, app/, tests/, ...), then guides you
    through selecting which to include and writing the config file.
    """
    from specbridge.config import SpecbridgeConfig, DEFAULT_SPEC_DIRS, DEFAULT_SOURCE_DIRS

    root = Path(dir).resolve()

    # Check for existing config
    yaml_path = root / ".specbridge.yaml"
    if yaml_path.exists() and not force:
        click.echo(f"⚠️  .specbridge.yaml already exists in {root}", err=True)
        if not click.confirm("   Overwrite?", default=False):
            click.echo("   Canceled.")
            return

    click.echo(f"\n🔍 Scanning {root} ...")

    # ── Detect spec directories ──
    known_spec_dirs = ["docs", "spec", "specs", "design", "requirements", "ドキュメント", "仕様"]
    found_spec_dirs: list[str] = []
    for d in known_spec_dirs:
        p = root / d
        if p.exists() and p.is_dir():
            md_count = len(list(p.rglob("*.md")))
            found_spec_dirs.append(f"{d}/  ({md_count} .md files)")

    if found_spec_dirs:
        click.echo(f"\n📁 Spec directories found:")
        for d in found_spec_dirs:
            click.echo(f"    {d}")
        use_all_spec = click.confirm("   Include all of them?", default=True)
        if use_all_spec:
            spec_dirs = [d.split("/")[0] for d in found_spec_dirs]
        else:
            spec_dirs = []
            for s in found_spec_dirs:
                dir_name = s.split("/")[0]
                if click.confirm(f"   Include {dir_name}/?", default=True):
                    spec_dirs.append(dir_name)
    else:
        click.echo("   No standard spec directories found.")
        custom = click.prompt("   Enter custom spec dir(s) (comma-separated, or empty for 'docs')",
                              default="")
        spec_dirs = [d.strip() for d in custom.split(",")] if custom.strip() else ["docs"]

    # ── Detect source directories ──
    known_source_dirs = ["src", "lib", "app", "tests", "source", "コード", "ソースコード"]
    found_source_dirs: list[str] = []
    for d in known_source_dirs:
        p = root / d
        if p.exists() and p.is_dir():
            # Count source files
            extensions = {".py", ".ts", ".js", ".rs", ".go", ".rb", ".java", ".kt", ".swift", ".cpp", ".c", ".h"}
            src_count = sum(1 for f in p.rglob("*") if f.is_file() and f.suffix.lower() in extensions)
            found_source_dirs.append(f"{d}/  ({src_count} source files)")

    if found_source_dirs:
        click.echo(f"\n🔧 Source directories found:")
        for d in found_source_dirs:
            click.echo(f"    {d}")
        use_all_src = click.confirm("   Include all of them?", default=True)
        if use_all_src:
            source_dirs = [d.split("/")[0] for d in found_source_dirs]
        else:
            source_dirs = []
            for s in found_source_dirs:
                dir_name = s.split("/")[0]
                if click.confirm(f"   Include {dir_name}/?", default=True):
                    source_dirs.append(dir_name)
    else:
        click.echo("   No standard source directories found.")
        custom = click.prompt("   Enter custom source dir(s) (comma-separated, or empty for 'src')",
                              default="")
        source_dirs = [d.strip() for d in custom.split(",")] if custom.strip() else ["src"]

    # ── Advanced options ──
    click.echo("")
    if click.confirm("   Configure advanced options (min_confidence, max_output_nodes)?",
                     default=False):
        min_confidence = click.prompt("   Minimum confidence (0.0-1.0)",
                                      type=float, default=0.15)
        max_output_nodes = click.prompt("   Max output nodes per category",
                                        type=int, default=20)
    else:
        min_confidence = 0.15
        max_output_nodes = 20

    # ── Preview & confirm ──
    click.echo(f"\n📝 Config preview:")
    click.echo(f"    spec_dirs:        {spec_dirs}")
    click.echo(f"    source_dirs:      {source_dirs}")
    click.echo(f"    min_confidence:   {min_confidence}")
    click.echo(f"    max_output_nodes: {max_output_nodes}")

    if not click.confirm("\n   Write .specbridge.yaml?", default=True):
        click.echo("   Canceled.")
        return

    # ── Write .specbridge.yaml ──
    import yaml
    config_data = {
        "spec_dirs": spec_dirs,
        "source_dirs": source_dirs,
        "min_confidence": min_confidence,
        "max_output_nodes": max_output_nodes,
    }
    yaml_path.write_text(yaml.dump(config_data, default_flow_style=False), encoding="utf-8")
    click.echo(f"\n✅ .specbridge.yaml created in {root}")

    # ── Offer next steps ──
    click.echo("")
    click.echo("💡 Next steps:")
    click.echo("   1. Run 'specbridge setup' to install pre-commit hook and AGENTS.md")
    click.echo("   2. Run 'specbridge snapshot' to create the initial baseline")
    click.echo("   3. Run 'specbridge analyze' to see your trace graph")


@cli.command()
@click.option("--shell", type=click.Choice(["bash", "zsh", "fish"]), default=None,
              help="Target shell (default: auto-detect from SHELL env)")
@click.option("--install", is_flag=True, default=False,
              help="Install completion permanently (appends to shell rc file)")
@click.option("--show", is_flag=True, default=False,
              help="Print the completion script to stdout (for manual install)")
def shell_completion(shell: str | None, install: bool, show: bool) -> None:
    """Generate or install shell completion scripts.

    specbridge uses Click's built-in shell completion.  After installing,
    press TAB to auto-complete commands, options, and arguments.

    Quick start:
      specbridge shell-completion --install

    Or manually:
      eval "$(specbridge shell-completion --show --shell bash)"
    """
    auto_shell = shell
    if auto_shell is None:
        import os
        shell_env = os.environ.get("SHELL", "")
        if "zsh" in shell_env:
            auto_shell = "zsh"
        elif "fish" in shell_env:
            auto_shell = "fish"
        else:
            auto_shell = "bash"

    root_cmd = cli  # the top-level Click group

    if show:
        _emit_completion_script(root_cmd, auto_shell)
        return

    if install:
        _install_completion(root_cmd, auto_shell)
        return

    # Default: show instructions
    click.echo(f"🔧 Shell completion for specbridge ({auto_shell})")
    click.echo(f"{'=' * 50}")
    click.echo("")

    if auto_shell == "bash":
        click.echo("  Add this to your ~/.bashrc:")
        click.echo('    eval "$(_SPECBRIDGE_COMPLETE=bash_source specbridge)"')
    elif auto_shell == "zsh":
        click.echo("  Add this to your ~/.zshrc:")
        click.echo('    eval "$(_SPECBRIDGE_COMPLETE=zsh_source specbridge)"')
    elif auto_shell == "fish":
        click.echo("  Add this to your ~/.config/fish/config.fish:")
        click.echo('    eval (env _SPECBRIDGE_COMPLETE=fish_source specbridge)')

    click.echo("")
    click.echo("  Or simply run:")
    click.echo(f"    specbridge shell-completion --install --shell {auto_shell}")
    click.echo("")
    click.echo("  Then restart your shell or source your rc file.")


def _emit_completion_script(cmd: click.BaseCommand, shell: str) -> None:  # type: ignore[valid-type]
    """Print the shell eval command for enabling completion."""
    var = "_SPECBRIDGE_COMPLETE"
    if shell == "fish":
        click.echo(f'eval (env {var}=fish_source specbridge)')
    else:
        click.echo(f'eval "$({var}={shell}_source specbridge)"')


def _install_completion(cmd: click.BaseCommand, shell: str) -> None:  # type: ignore[valid-type]
    """Append the completion eval line to the user's shell rc file."""
    from pathlib import Path

    rc_map = {
        "bash": Path.home() / ".bashrc",
        "zsh": Path.home() / ".zshrc",
        "fish": Path.home() / ".config" / "fish" / "config.fish",
    }
    rc_path = rc_map.get(shell)
    if rc_path is None:
        click.echo(f"❌ Unknown shell: {shell}", err=True)
        raise click.Abort()

    var = "_SPECBRIDGE_COMPLETE"
    if shell == "fish":
        line = f'eval (env {var}=fish_source specbridge)'
    else:
        line = f'eval "$({var}={shell}_source specbridge)"'

    # Check if already installed
    if rc_path.exists():
        existing = rc_path.read_text(encoding="utf-8")
        if line in existing:
            click.echo(f"✅ specbridge completion already installed in {rc_path}")
            return

    rc_path.parent.mkdir(parents=True, exist_ok=True)
    with open(rc_path, "a", encoding="utf-8") as f:
        f.write(f"\n# specbridge shell completion\n{line}\n")

    click.echo(f"✅ specbridge completion installed in {rc_path}")
    click.echo("   Restart your shell or run:")
    if shell == "fish":
        click.echo(f"     source {rc_path}")
    else:
        click.echo(f"     source {rc_path}")


# ── snapshot diff ──────────────────────────────────────────


@cli.command()
@click.argument("before", type=click.Path(exists=True, dir_okay=False))
@click.argument("after", type=click.Path(exists=True, dir_okay=False))
@click.option("--format", "output_fmt", default="text", type=click.Choice(["text", "json"]),
              help="Output format", show_default=True)
def diff(before: str, after: str, output_fmt: str) -> None:
    """Compare two snapshot files and show a summary diff.

    BEFORE and AFTER are paths to .specbridge/snapshot.json files.

    Shows coverage trend, spec/code changes, and orphan differences
    between two points in time — like ``git diff --stat`` for specs.
    """
    import json

    from specbridge.analyzers.drift import snapshot_diff

    try:
        snap_before = json.loads(Path(before).read_text(encoding="utf-8"))
        snap_after = json.loads(Path(after).read_text(encoding="utf-8"))
    except Exception as e:
        click.echo(f"❌ Failed to load snapshot: {e}", err=True)
        raise click.Abort() from e

    result = snapshot_diff(snap_before, snap_after)

    if output_fmt == "json":
        click.echo(json.dumps(result, indent=2, ensure_ascii=False))
        return

    # ── Text output ──
    cov_b = result["coverage_before"]
    cov_a = result["coverage_after"]
    bpct = cov_b.get("coverage_pct", 0)
    apct = cov_a.get("coverage_pct", 0)
    delta = round(float(apct) - float(bpct), 1)
    sign = "+" if delta >= 0 else ""

    click.echo(f"📊 specbridge snapshot diff")
    click.echo(f"{'=' * 50}")

    click.echo(f"\n📊 Coverage trend:")
    click.echo(f"   Before:  {bpct}% ({cov_b.get('covered', '?')}/{cov_b.get('total', '?')})")
    click.echo(f"   After:   {apct}% ({cov_a.get('covered', '?')}/{cov_a.get('total', '?')})")
    click.echo(f"   Change:  {sign}{delta}%")

    s_added = result["specs_added"]
    s_removed = result["specs_removed"]
    s_changed = result["specs_changed"]
    s_renamed = result["specs_renamed"]
    if s_added or s_removed or s_changed:
        click.echo(f"\n📄 Spec changes:")
        if s_added:
            click.echo(f"   + {s_added} added")
            for d in result.get("added_specs_detail", []):
                click.echo(f"       + {d.get('title', d['id'])}")
        if s_removed:
            click.echo(f"   - {s_removed} removed")
        if s_renamed:
            click.echo(f"   ~ {s_renamed} renamed")
        if s_changed:
            click.echo(f"   ~ {s_changed} titles changed")

    c_added = result["code_added"]
    c_removed = result["code_removed"]
    funcs = result["funcs_changed"]
    if c_added or c_removed or funcs:
        click.echo(f"\n📁 Code changes:")
        if c_added:
            click.echo(f"   + {c_added} files added")
        if c_removed:
            click.echo(f"   - {c_removed} files removed")
        if funcs:
            click.echo(f"   ⚡ {funcs} functions changed")

    new_orph = result["new_orphans"]
    res_orph = result["resolved_orphans"]
    if new_orph or res_orph:
        click.echo(f"\n🟡 Orphan changes:")
        click.echo(f"   Before:  {result['orphans_before']} orphan specs")
        click.echo(f"   After:   {result['orphans_after']} orphan specs")
        if new_orph:
            click.echo(f"   New:     {new_orph} orphan specs appeared")
        if res_orph:
            click.echo(f"   Resolved: {res_orph} orphan specs covered")


# ── suggest ────────────────────────────────────────────────


@cli.command()
@click.option("--dir", "-d", default=".", help="Project directory", show_default=True)
@click.option("--top", type=int, default=5, help="Number of suggestions to show", show_default=True)
@click.option("--format", "output_fmt", default="text", type=click.Choice(["text", "json"]),
              help="Output format", show_default=True)
@click.option("--threshold", type=float, default=0.1,
              help="Minimum similarity score (0.0-1.0) to include a suggestion", show_default=True)
def suggest(dir: str, top: int, output_fmt: str, threshold: float) -> None:
    """Suggest code files that may implement uncovered specs.

    Analyzes orphan specs (specs with zero implementing code files) and
    scores each code file in the project for relevance using the same
    heuristic matching engine that powers ``specbridge analyze``.

    The top N suggestions per orphan spec are shown, ordered by
    similarity score. Use ``--threshold`` to filter out weak matches.
    """
    from specbridge.adapters import detect_adapter
    from specbridge.analyzers import find_orphan_code, find_orphan_specs
    from specbridge.core import NodeType
    from specbridge.discovery.code import discover_code
    from specbridge.discovery.spec import discover_specs
    from specbridge.infer import _score_edge, _tokenize

    root = Path(dir).resolve()
    adapter = detect_adapter(str(root))
    if adapter is None:
        click.echo("❌ No recognized SSD framework found.", err=True)
        _no_adapter_hint()
        raise click.Abort()

    graph = adapter.analyze(str(root))
    orphan_specs = find_orphan_specs(graph)
    if not orphan_specs:
        click.echo("✅ All specs have implementing code — no suggestions needed.")
        return

    # Get raw candidates for scoring
    from specbridge.config import SpecbridgeConfig
    cfg = SpecbridgeConfig.load(str(root))
    specs = discover_specs(str(root), spec_dirs=cfg.spec_dirs, spec_files=cfg.spec_files)
    codes = discover_code(str(root), source_dirs=cfg.source_dirs, source_files=cfg.source_files)

    # Build spec lookup
    spec_map = {s.auto_id: s for s in specs}
    orphan_spec_candidates = [s for s in specs if s.auto_id in orphan_specs]

    suggestions: list[dict[str, Any]] = []
    for sc in orphan_spec_candidates:
        spec_text = f"{sc.title} {sc.heading_text}"
        if sc.parent_chain:
            spec_text += " " + " ".join(sc.parent_chain)
        if sc.body_text:
            spec_text += " " + sc.body_text[:300]
        spec_tokens = _tokenize(spec_text)

        scored: list[tuple[float, str, str]] = []
        for cc in codes:
            conf, evidence = _score_edge(sc, cc, spec_tokens, str(root))
            if conf >= threshold:
                kind = evidence[0].kind if evidence else ""
                scored.append((conf, cc.file, kind))

        scored.sort(key=lambda x: -x[0])
        top_scored = scored[:top]

        suggestions.append({
            "spec_id": sc.auto_id,
            "title": sc.title or sc.heading_text,
            "file": sc.file,
            "suggestions": [
                {"file": f, "score": round(s, 3), "evidence": k}
                for s, f, k in top_scored
            ],
            "total_candidates": len(scored),
        })

    if output_fmt == "json":
        import json as _json
        click.echo(_json.dumps(suggestions, indent=2, ensure_ascii=False))
        return

    # Text output
    click.echo(f"📋 specbridge suggest — {len(suggestions)} orphan spec(s)")
    click.echo(f"{'=' * 50}")
    click.echo("")

    for i, sg in enumerate(suggestions[:top], 1):
        click.echo(f"{i}. {sg['spec_id']} \"{sg['title']}\" ({sg['file']})")
        if sg["suggestions"]:
            click.echo(f"   → {sg['total_candidates']} candidate(s), top {len(sg['suggestions'])}:")
            for s in sg["suggestions"]:
                icon = {"heuristic:funcname": "🔧", "heuristic:filename": "📁",
                        "heuristic:symbol": "🔤"}.get(s["evidence"], "  ")
                click.echo(f"     {icon} {s['file']}  (score: {s['score']})")
        else:
            click.echo(f"   → No matching code files found (threshold: {threshold})")
            click.echo("     💡 Check that source_dirs in .specbridge.yaml covers the implementation")
        click.echo("")


# ── Config validation ──────────────────────────────────────


def _validate_config(cfg: Any, root: Path) -> list[str]:
    """Validate a SpecbridgeConfig instance and return a list of issues."""
    issues: list[str] = []

    # spec_dirs
    if not cfg.spec_dirs:
        issues.append("spec_dirs is empty — at least one spec directory is needed")
    for d in cfg.spec_dirs:
        resolved = root / d
        if not resolved.exists():
            issues.append(f"spec_dir '{d}' does not exist at {resolved}")

    # source_dirs
    if not cfg.source_dirs:
        issues.append("source_dirs is empty — at least one source directory is needed")
    for d in cfg.source_dirs:
        resolved = root / d
        if not resolved.exists():
            issues.append(f"source_dir '{d}' does not exist at {resolved}")

    # min_confidence
    if not 0.0 <= cfg.min_confidence <= 1.0:
        issues.append(f"min_confidence ({cfg.min_confidence}) must be between 0.0 and 1.0")

    # max_output_nodes
    if cfg.max_output_nodes < 1:
        issues.append(f"max_output_nodes ({cfg.max_output_nodes}) must be >= 1")

    return issues


if __name__ == "__main__":
    cli()
