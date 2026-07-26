"""specbridge CLI — traceability analyzer for spec-driven development."""

from __future__ import annotations

from pathlib import Path

import click

from specbridge import __version__
from specbridge.core import NodeType
from specbridge.outputs.json_out import render_json
from specbridge.outputs.text import render_text


@click.group()
@click.version_option(version=__version__, prog_name="specbridge")
def cli():
    """Spec ↔ Code bridge: read-only traceability analyzer for SSD."""


@cli.command()
@click.option("--dir", "-d", default=".", help="Project directory to analyze", show_default=True)
@click.option("--format", "output_fmt", default="text", type=click.Choice(["text", "json"]),
              help="Output format", show_default=True)
@click.option("--merge", "-m", is_flag=True, default=False,
              help="Merge results from ALL matching adapters (not just the best one)",
              show_default=True)
def analyze(dir, output_fmt, merge):
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
            g = adapter.analyze(str(root))
            graphs.append(g)
        graph = merge_graphs(graphs)
    else:
        adapter = detect_adapter(str(root))
        if adapter is None:
            click.echo("❌ No recognized SSD framework found.", err=True)
            raise click.Abort()
        graph = adapter.analyze(str(root))

    from specbridge.analyzers import coverage_summary

    spec_count = len(graph.nodes_by_type(NodeType.SPEC))
    code_count = len(graph.nodes_by_type(NodeType.CODE))
    test_count = len(graph.nodes_by_type(NodeType.TEST))
    click.echo(f"\n   Nodes: {len(graph.nodes)} | Edges: {len(graph.edges)}", err=True)
    click.echo(f"   Specs: {spec_count} | Code refs: {code_count} | Tests: {test_count}", err=True)

    cov = coverage_summary(graph)
    if cov["total"] > 0:
        click.echo(f"   Coverage: {cov['coverage_pct']}% ({cov['covered']}/{cov['total']})", err=True)

    if output_fmt == "json":
        click.echo(render_json(graph))
    else:
        click.echo(render_text(graph))


@cli.command()
@click.option("--dir", "-d", default=".", help="Project directory", show_default=True)
@click.option("--spec-id", required=True, help="Spec ID to analyze (e.g. 1.1)")
@click.option("--format", "output_fmt", default="text", type=click.Choice(["text", "json"]),
              help="Output format", show_default=True)
def impact(dir, spec_id, output_fmt):
    """Find what implements a given spec."""
    from specbridge.adapters import detect_adapter

    root = Path(dir).resolve()
    adapter = detect_adapter(str(root))
    if adapter is None:
        click.echo("❌ No recognized SSD framework found.", err=True)
        raise click.Abort()

    graph = adapter.analyze(str(root))

    spec_node = graph.nodes.get(spec_id) or graph.nodes.get(f"spec::{spec_id}")
    if spec_node is None:
        click.echo(f"❌ Spec '{spec_id}' not found in trace graph.", err=True)
        raise click.Abort()

    edges = graph.edges_to(spec_node.id)
    if not edges:
        click.echo(f"📄 {spec_node.id}: {spec_node.title}")
        click.echo("   (no implementing artifacts found)")
        return

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
        _json.dump({
            "spec_id": spec_node.id,
            "title": spec_node.title,
            "edges": [{"src": e.src_id, "relation": e.relation.value, "strength": e.strength.value,
                        "evidence": [{"kind": ev.kind, "value": ev.value} for ev in e.evidence]}
                       for e in edges],
        }, indent=2, ensure_ascii=False)


@cli.command()
@click.option("--dir", "-d", default=".", help="Project directory", show_default=True)
@click.option("--format", "output_fmt", default="text", type=click.Choice(["text", "json"]),
              help="Output format", show_default=True)
def coverage(dir, output_fmt):
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
def snapshot(dir, reason):
    """Take a structural snapshot of specs and code."""
    from specbridge.analyzers.drift import build_snapshot, save_snapshot

    root = Path(dir).resolve()
    click.echo(f"📸 Snapshotting {root} ...", err=True)

    snap = build_snapshot(str(root), reason=reason)
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
def drift(dir, snapshot_path, gate, output_fmt, git_base):
    """Detect changes between snapshot and current state."""
    root = Path(dir).resolve()

    if git_base:
        _drift_git(str(root), git_base, gate)
        return

    from specbridge.analyzers.drift import compute_drift, load_snapshot

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

    report = compute_drift(snapshot, str(root))

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

    affected: list[dict] = []
    for cf in changed:
        for nid, node in graph.nodes.items():
            if node.type == NodeType.CODE and node.source.file == cf:
                for edge in graph.edges_from(nid):
                    if edge.relation.value in ("implements",):
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
def validate_boundary(dir):
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
            inside = any(code_path.startswith(b["path"]) for b in boundaries)
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


if __name__ == "__main__":
    cli()
