"""specbridge CLI — traceability analyzer for spec-driven development."""

from __future__ import annotations

from pathlib import Path

import click

from specbridge import __version__
from specbridge.core import NodeType
from specbridge.outputs.text import render_text
from specbridge.outputs.json_out import render_json

# Lazy imports for adapters/analyzers so CLI boots fast
_adapters: list | None = None
_analyzers: list | None = None


def _get_adapters():
    global _adapters
    if _adapters is None:
        from specbridge.adapters import detect_adapter
        _adapters = [detect_adapter]  # just the resolver
    return _adapters


def _get_analyzers():
    global _analyzers
    if _analyzers is None:
        from specbridge.analyzers import coverage_summary, find_orphan_specs, find_orphan_code
        _analyzers = [coverage_summary, find_orphan_specs, find_orphan_code]
    return _analyzers


@click.group()
@click.version_option(version=__version__, prog_name="specbridge")
def cli():
    """Spec ↔ Code bridge: read-only traceability analyzer for SSD."""


@cli.command()
@click.option("--dir", "-d", default=".", help="Project directory to analyze", show_default=True)
@click.option("--format", "output_fmt", default="text", type=click.Choice(["text", "json"]),
              help="Output format", show_default=True)
def analyze(dir, output_fmt):
    """Analyze a project and build a trace graph."""
    from specbridge.adapters import detect_adapter
    from specbridge.analyzers import coverage_summary

    root = Path(dir).resolve()
    click.echo(f"🔍 Scanning {root} ...", err=True)

    adapter = detect_adapter(str(root))
    if adapter is None:
        click.echo("❌ No recognized SSD framework found.", err=True)
        raise click.Abort()

    click.echo(f"   Using adapter: {adapter.__class__.__name__}", err=True)
    graph = adapter.analyze(str(root))

    # Summary
    spec_count = len(graph.nodes_by_type(NodeType.SPEC))
    code_count = len(graph.nodes_by_type(NodeType.CODE))
    test_count = len(graph.nodes_by_type(NodeType.TEST))
    click.echo(f"\n   Nodes: {len(graph.nodes)} | Edges: {len(graph.edges)}", err=True)
    click.echo(f"   Specs: {spec_count} | Code refs: {code_count} | Tests: {test_count}", err=True)

    cov = coverage_summary(graph)
    if cov["total"] > 0:
        click.echo(f"   Coverage: {cov['coverage_pct']}% ({cov['covered']}/{cov['total']})", err=True)

    # Output
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

    # Find the spec node
    spec_node = graph.nodes.get(spec_id) or graph.nodes.get(f"spec::{spec_id}")
    if spec_node is None:
        click.echo(f"❌ Spec '{spec_id}' not found in trace graph.", err=True)
        raise click.Abort()

    edges = graph.edges_to(spec_node.id)
    if not edges:
        click.echo(f"📄 {spec_node.id}: {spec_node.title}")
        click.echo(f"   (no implementing artifacts found)")
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
    from specbridge.analyzers import coverage_summary, find_orphan_specs, find_orphan_code

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

    click.echo(f"📊 Spec Coverage")
    click.echo(f"{'=' * 40}")
    click.echo(f"  Total specs:  {cov['total']}")
    click.echo(f"  Covered:      {cov['covered']}")
    click.echo(f"  Orphan specs: {cov['orphan']}")
    click.echo(f"  Coverage:     {cov['coverage_pct']}%")
    if orphans_spec:
        click.echo(f"\n🟡 Orphan specs (no code ref):")
        for nid in orphans_spec:
            click.echo(f"   - {nid}")
    if orphans_code:
        click.echo(f"\n🟡 Orphan code files (no spec ref):")
        for nid in orphans_code[:10]:
            click.echo(f"   - {nid}")
        if len(orphans_code) > 10:
            click.echo(f"   ... and {len(orphans_code) - 10} more")


@cli.command()
@click.option("--dir", "-d", default=".", help="Project directory", show_default=True)
@click.option("--git-base", default="main", help="Git base ref to diff against", show_default=True)
@click.option("--gate", is_flag=True, help="Exit with code 1 if drift detected")
def drift(dir, git_base, gate):
    """Detect changes that affect specs."""
    import json as _json
    import subprocess
    from pathlib import Path

    root = Path(dir).resolve()

    # git diff
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", git_base],
            capture_output=True, text=True, check=True, cwd=str(root),
        )
    except subprocess.CalledProcessError as e:
        click.echo(f"❌ git diff failed: {e}", err=True)
        raise click.Abort()

    changed = [f for f in result.stdout.strip().split("\n") if f]
    if not changed:
        click.echo("✅ No changes detected.")
        return

    # Load trace graph and find affected specs
    from specbridge.adapters import detect_adapter
    adapter = detect_adapter(str(root))
    if adapter is None:
        click.echo("❌ No recognized SSD framework found.", err=True)
        raise click.Abort()

    graph = adapter.analyze(str(root))

    affected: list[dict] = []
    for cf in changed:
        for nid, node in graph.nodes.items():
            if node.type == NodeType.CODE and node.source.file == cf:
                for e in graph.edges_from(nid):
                    if e.relation.value in ("implements",):
                        affected.append({"file": cf, "spec_id": e.dst_id})

    if not affected:
        click.echo("✅ No spec-impacting changes detected.")
        return

    click.echo(f"⚠️  {len(affected)} spec-affecting change(s):")
    for a in affected:
        click.echo(f"   {a['file']} → affects spec {a['spec_id']}")

    if gate:
        click.echo("\n❌ Gate failed — drift detected.", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    cli()
