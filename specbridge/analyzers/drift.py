"""Drift detection: snapshot comparison engine.

Takes a baseline snapshot of spec/code structure, then compares
current state against it to detect what changed.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from specbridge.discovery.spec import SpecCandidate, discover_specs
from specbridge.discovery.code import CodeCandidate, discover_code
from specbridge.analyzers import coverage_summary
from specbridge.bridge import build_heuristic_graph


SNAPSHOT_RELPATH = ".specbridge/snapshot.json"


# ── Snapshot schema ──────────────────────────────────────────


def build_snapshot(
    directory: str,
    *,
    reason: str = "",
    spec_dirs: Optional[list[str]] = None,
    source_dirs: Optional[list[str]] = None,
) -> dict:
    """Build a snapshot of the current project state."""
    graph = build_heuristic_graph(directory, spec_dirs=spec_dirs, source_dirs=source_dirs)
    cov = coverage_summary(graph)

    specs = discover_specs(directory, spec_dirs=spec_dirs)
    codes = discover_code(directory, source_dirs=source_dirs)

    snapshot = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "reason": reason,
        "specs": [
            {
                "id": s.auto_id,
                "file": s.file,
                "title": s.title,
                "heading_text": s.heading_text,
                "depth": s.heading_depth,
                "line": s.line,
            }
            for s in specs
        ],
        "code": [
            {
                "file": c.file,
                "module": c.module,
                "symbols": c.symbols,
                "is_test": c.is_test,
                "language": c.language,
                "imports": c.imports[:3],
            }
            for c in codes
        ],
        "coverage": cov,
    }
    return snapshot


def save_snapshot(snapshot: dict, project_dir: str) -> Path:
    """Write snapshot to .specbridge/snapshot.json."""
    root = Path(project_dir).resolve()
    path = root / SNAPSHOT_RELPATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False))
    return path


def load_snapshot(project_dir: str) -> Optional[dict]:
    """Read snapshot from .specbridge/snapshot.json."""
    path = Path(project_dir).resolve() / SNAPSHOT_RELPATH
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


# ── Drift comparison ─────────────────────────────────────────


class DriftReport:
    """Structured drift comparison result."""

    def __init__(self):
        self.specs_added: list[dict] = []
        self.specs_removed: list[dict] = []
        self.specs_changed: list[dict] = []
        self.code_added: list[dict] = []
        self.code_removed: list[dict] = []
        self.code_symbols_changed: list[dict] = []
        self.new_orphan_specs: list[str] = []
        self.resolved_orphan_specs: list[str] = []
        self.new_orphan_code: list[str] = []
        self.resolved_orphan_code: list[str] = []
        self.coverage_before: Optional[dict] = None
        self.coverage_after: Optional[dict] = None

    @property
    def has_drift(self) -> bool:
        return any([
            self.specs_added, self.specs_removed, self.specs_changed,
            self.code_added, self.code_removed, self.code_symbols_changed,
            self.new_orphan_specs, self.resolved_orphan_specs,
            self.new_orphan_code, self.resolved_orphan_code,
        ])

    def render_text(self) -> str:
        lines: list[str] = []
        if not self.has_drift:
            return "✅ No drift detected — project state matches snapshot."

        if self.specs_added:
            lines.append(f"📄  New specs ({len(self.specs_added)}):")
            for s in self.specs_added:
                lines.append(f"     + {s['id']}: {s['title']}  ({s['file']})")

        if self.specs_removed:
            lines.append(f"🗑️  Removed specs ({len(self.specs_removed)}):")
            for s in self.specs_removed:
                lines.append(f"     - {s['id']}: {s['title']}  ({s['file']})")

        if self.specs_changed:
            lines.append(f"✏️  Changed specs ({len(self.specs_changed)}):")
            for s in self.specs_changed:
                lines.append(f"     ~ {s['id']}: \"{s['old_title']}\" → \"{s['new_title']}\"")

        if self.code_added:
            lines.append(f"📁  New code files ({len(self.code_added)}):")
            for c in self.code_added:
                syms = ", ".join(c.get("symbols", [])[:3])
                lines.append(f"     + {c['file']}  ({c['language']})  [{syms}]")

        if self.code_removed:
            lines.append(f"🗑️  Removed code files ({len(self.code_removed)}):")
            for c in self.code_removed:
                lines.append(f"     - {c['file']}")

        if self.code_symbols_changed:
            lines.append(f"🔧  Changed symbols ({len(self.code_symbols_changed)}):")
            for c in self.code_symbols_changed:
                if c.get("added"):
                    lines.append(f"     + {c['file']}: {', '.join(c['added'][:5])}")
                if c.get("removed"):
                    lines.append(f"     - {c['file']}: {', '.join(c['removed'][:5])}")

        if self.new_orphan_specs:
            lines.append(f"\n🟡  New orphan specs ({len(self.new_orphan_specs)}):")
            for o in self.new_orphan_specs[:5]:
                lines.append(f"     • {o}")
            if len(self.new_orphan_specs) > 5:
                lines.append(f"     ... and {len(self.new_orphan_specs) - 5} more")

        if self.resolved_orphan_specs:
            lines.append(f"\n🟢  Resolved orphan specs ({len(self.resolved_orphan_specs)}):")
            for o in self.resolved_orphan_specs[:5]:
                lines.append(f"     ✓ {o}")

        if self.new_orphan_code:
            lines.append(f"\n🟡  New orphan code files ({len(self.new_orphan_code)}):")
            for o in self.new_orphan_code[:5]:
                lines.append(f"     • {o}")

        if self.coverage_before and self.coverage_after:
            b = self.coverage_before
            a = self.coverage_after
            delta = round(a["coverage_pct"] - b["coverage_pct"], 1)
            arrow = "📈" if delta > 0 else "📉"
            lines.append(f"\n{arrow}  Coverage: {b['coverage_pct']}% → {a['coverage_pct']}%  ({delta:+.1f}%)")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "has_drift": self.has_drift,
            "specs_added": self.specs_added,
            "specs_removed": self.specs_removed,
            "specs_changed": self.specs_changed,
            "code_added": self.code_added,
            "code_removed": self.code_removed,
            "code_symbols_changed": self.code_symbols_changed,
            "new_orphan_specs": self.new_orphan_specs,
            "resolved_orphan_specs": self.resolved_orphan_specs,
            "new_orphan_code": self.new_orphan_code,
            "resolved_orphan_code": self.resolved_orphan_code,
            "coverage_before": self.coverage_before,
            "coverage_after": self.coverage_after,
        }


def compute_drift(
    snapshot: dict,
    directory: str,
    *,
    spec_dirs: Optional[list[str]] = None,
    source_dirs: Optional[list[str]] = None,
) -> DriftReport:
    """Compare snapshot against current state."""
    report = DriftReport()

    # Parse snapshot data into lookup tables
    snap_specs = {s["id"]: s for s in snapshot.get("specs", [])}
    snap_code = {c["file"]: c for c in snapshot.get("code", [])}

    # Current state
    curr_specs = discover_specs(directory, spec_dirs=spec_dirs)
    curr_codes = discover_code(directory, source_dirs=source_dirs)

    curr_spec_map = {s.auto_id: s for s in curr_specs}
    curr_code_map = {c.file: c for c in curr_codes}

    # --- Specs ---
    for sid, snap_s in snap_specs.items():
        curr = curr_spec_map.get(sid)
        if curr is None:
            report.specs_removed.append(snap_s)
        elif curr.title != snap_s["title"]:
            report.specs_changed.append({
                "id": sid,
                "old_title": snap_s["title"],
                "new_title": curr.title,
                "file": curr.file,
            })

    for cs in curr_specs:
        if cs.auto_id not in snap_specs:
            report.specs_added.append({
                "id": cs.auto_id,
                "title": cs.title,
                "file": cs.file,
            })

    # --- Code ---
    for cf, snap_c in snap_code.items():
        curr = curr_code_map.get(cf)
        if curr is None:
            report.code_removed.append(snap_c)
        else:
            # Check symbol changes
            old_syms = set(snap_c.get("symbols", []))
            new_syms = set(curr.symbols)
            added = new_syms - old_syms
            removed = old_syms - new_syms
            if added or removed:
                report.code_symbols_changed.append({
                    "file": cf,
                    "added": sorted(added),
                    "removed": sorted(removed),
                })

    for cc in curr_codes:
        if cc.file not in snap_code:
            report.code_added.append({
                "file": cc.file,
                "module": cc.module,
                "symbols": cc.symbols,
                "language": cc.language,
            })

    # --- Coverage / orphans ---
    graph_now = build_heuristic_graph(directory, spec_dirs=spec_dirs, source_dirs=source_dirs)
    from specbridge.analyzers import coverage_summary, find_orphan_specs, find_orphan_code

    report.coverage_before = snapshot.get("coverage")
    report.coverage_after = coverage_summary(graph_now)

    now_orphan_specs = set(find_orphan_specs(graph_now))
    before_orphan_specs = set(snapshot.get("coverage", {}).get("orphan_spec_ids", []))
    # Recalculate before orphans from spec nodes that had no edges
    # (Simpler: just compare current orphan set to a computed set from snapshot data)
    snap_linked = set()
    snap_orphan_ids = set()
    for s in snapshot.get("specs", []):
        sid = s["id"]
        # We can't fully rebuild old edges, so approximate:
        # If a spec had no edges in the old graph, it was orphan
        pass

    # Approximate orphan changes by comparing spec presence
    all_snap_specs = set(snap_specs.keys())
    all_curr_specs = {s.auto_id for s in curr_specs}

    # Compute current orphans properly
    curr_orphan_specs = set(find_orphan_specs(graph_now))
    curr_orphan_code = set(find_orphan_code(graph_now))

    # Compare against snapshot (crude but effective)
    # We'll track new orphans by looking at spec IDs present in both
    # but only orphan in current
    common_specs = all_snap_specs & all_curr_specs
    for sid in common_specs:
        if sid in curr_orphan_specs:
            report.new_orphan_specs.append(sid)

    return report
