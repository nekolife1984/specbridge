"""Show per-adapter coverage breakdown."""

from specbridge.adapters import all_adapters
from specbridge.analyzers import coverage_summary, find_orphan_specs
from pathlib import Path

root = str(Path(".").resolve())

print("=" * 62)
print(f"  Adapter Coverage Comparison — {Path(root).name}")
print("=" * 62)

for cls in all_adapters():
    inst = cls()
    score = inst.detect(root)
    if score <= 0:
        continue

    graph = inst.analyze(root)
    cov = coverage_summary(graph)
    orphans = find_orphan_specs(graph)

    print(f"\n  📌 {cls.__name__:25s}  detect={score:.2f}")
    print(f"     Nodes: {len(graph.nodes):5d}  |  Edges: {len(graph.edges):6d}")
    print(f"     Specs: {cov['total']:4d}  |  "
          f"Covered: {cov['covered']:4d}  |  "
          f"Coverage: {cov['coverage_pct']:5.1f}%")

    # Show framework origins
    origins: dict[str, int] = {}
    for n in graph.nodes.values():
        o = n.framework_origin
        origins[o] = origins.get(o, 0) + 1
    if origins:
        print("     Origins:", ", ".join(f"{k}={v}" for k, v in sorted(origins.items())))

    if orphans:
        preview = ", ".join(orphans[:3])
        more = f" ... and {len(orphans) - 3} more" if len(orphans) > 3 else ""
        print(f"     Orphan specs ({len(orphans)}): {preview}{more}")
