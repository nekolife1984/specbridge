"""Drift detection: snapshot comparison engine with section/function hashing."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from specbridge.analyzers import coverage_summary, find_orphan_specs
from specbridge.core import NodeType
from specbridge.discovery.code import discover_code
from specbridge.discovery.spec import discover_specs
from specbridge.infer import build_heuristic_graph

SNAPSHOT_RELPATH = ".specbridge/snapshot.json"


# ── Snapshot ─────────────────────────────────────────────────


def build_snapshot(
    directory: str,
    *,
    reason: str = "",
    spec_dirs: list[str] | None = None,
    source_dirs: list[str] | None = None,
) -> dict:
    """Build a snapshot of the current project state with hashes."""
    specs = discover_specs(directory, spec_dirs=spec_dirs)
    codes = discover_code(directory, source_dirs=source_dirs)
    graph = build_heuristic_graph(directory, specs=specs, codes=codes, spec_dirs=spec_dirs, source_dirs=source_dirs)
    cov = coverage_summary(graph)

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
                # Section body hash (heading + body text)
                "body_hash": s.body_hash,
                "body_hash_content": s.body_hash_content,
                "body_line_count": s.body_line_count,
                "body_preview": s.body_preview,
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
                # File-level hash
                "file_hash": c.file_hash,
                # Per-function hashes
                "functions": [
                    {
                        "name": f.name,
                        "kind": f.kind,
                        "line": f.line,
                        "body_hash": f.body_hash,
                        "body_lines": f.body_lines,
                    }
                    for f in c.functions
                ],
            }
            for c in codes
        ],
        "orphan_spec_ids": sorted(find_orphan_specs(graph)),
        "coverage": {
            **cov,
            "spec_count": len(specs),
            "code_count": len(codes),
        },
    }
    return snapshot


def save_snapshot(snapshot: dict, project_dir: str) -> Path:
    root = Path(project_dir).resolve()
    path = root / SNAPSHOT_RELPATH
    from specbridge.guard import validate_write_path
    validate_write_path(path, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False))
    return path


def load_snapshot(project_dir: str) -> dict | None:
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
        self.specs_changed: list[dict] = []        # title changed
        self.specs_body_changed: list[dict] = []   # body changed, title same
        self.specs_renamed: list[dict] = []        # removed + added with same body_hash
        self.code_added: list[dict] = []
        self.code_removed: list[dict] = []
        self.code_symbols_changed: list[dict] = []
        self.code_funcs_changed: list[dict] = []   # function body hash changed
        self.new_orphan_specs: list[str] = []
        self.resolved_orphan_specs: list[str] = []
        self.new_orphan_code: list[str] = []
        self.resolved_orphan_code: list[str] = []
        self.coverage_before: dict | None = None
        self.coverage_after: dict | None = None

    @property
    def has_drift(self) -> bool:
        return any([
            self.specs_added, self.specs_removed, self.specs_changed,
            self.specs_body_changed, self.specs_renamed,
            self.code_added, self.code_removed, self.code_symbols_changed,
            self.code_funcs_changed,
            self.new_orphan_specs, self.resolved_orphan_specs,
            self.new_orphan_code, self.resolved_orphan_code,
        ])

    def render_text(self) -> str:
        lines: list[str] = []
        if not self.has_drift:
            return "✅ No drift detected — project state matches snapshot."

        # ── Spec changes ──
        if self.specs_renamed:
            lines.append(f"✏️  Renamed specs ({len(self.specs_renamed)}):")
            for s in self.specs_renamed:
                lines.append(f"     ~ \"{s['old_title']}\" → \"{s['new_title']}\"  ({s['file']})")
            lines.append("")

        if self.specs_added:
            lines.append(f"📄  New specs ({len(self.specs_added)}):")
            for s in self.specs_added:
                lines.append(f"     + {s['id']}: {s['title']}  ({s['file']})")

        if self.specs_removed:
            lines.append(f"🗑️  Removed specs ({len(self.specs_removed)}):")
            for s in self.specs_removed:
                lines.append(f"     - {s['id']}: {s['title']}  ({s['file']})")

        if self.specs_changed:
            lines.append(f"✏️  Changed spec titles ({len(self.specs_changed)}):")
            for s in self.specs_changed:
                lines.append(f"     ~ {s['id']}: \"{s['old_title']}\" → \"{s['new_title']}\"")
                if s.get("body_hash_changed"):
                    lines.append("       (body also changed)")

        if self.specs_body_changed:
            lines.append(f"📝  Changed spec body ({len(self.specs_body_changed)}):")
            for s in self.specs_body_changed:
                lines.append(f"     ~ {s['id']}: \"{s['title']}\"  (lines: {s['old_lines']}→{s['new_lines']})")
                lines.append(f"       hash: {s['old_hash']} → {s['new_hash']}")

        # ── Code changes ──
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
                if c.get("file_hash_changed"):
                    lines.append("       (file content changed)")

        if self.code_funcs_changed:
            lines.append(f"⚡  Changed function bodies ({len(self.code_funcs_changed)}):")
            for c in self.code_funcs_changed:
                lines.append(f"     ~ {c['file']}")
                for f in c.get("funcs", [])[:5]:
                    lines.append(f"         {f['name']}  ({f['kind']}:{f['line']})  hash: {f['old_hash']} → {f['new_hash']}")
                if len(c.get("funcs", [])) > 5:
                    lines.append(f"         ... and {len(c['funcs']) - 5} more")

        # ── Orphan changes ──
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

        # ── Coverage ──
        if self.coverage_before and self.coverage_after:
            b = self.coverage_before
            a = self.coverage_after
            delta = round(a["coverage_pct"] - b["coverage_pct"], 1)
            arrow = "📈" if delta > 0 else "📉"
            lines.append(f"\n{arrow}  Coverage: {b['coverage_pct']}% → {a['coverage_pct']}%  ({delta:+.1f}%)")
            lines.append(f"     Specs: {b.get('spec_count', '?')} → {a.get('spec_count', '?')}")
            lines.append(f"     Code:  {b.get('code_count', '?')} → {a.get('code_count', '?')}")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "has_drift": self.has_drift,
            "specs_added": self.specs_added,
            "specs_removed": self.specs_removed,
            "specs_changed": self.specs_changed,
            "specs_body_changed": self.specs_body_changed,
            "specs_renamed": self.specs_renamed,
            "code_added": self.code_added,
            "code_removed": self.code_removed,
            "code_symbols_changed": self.code_symbols_changed,
            "code_funcs_changed": self.code_funcs_changed,
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
    spec_dirs: list[str] | None = None,
    source_dirs: list[str] | None = None,
) -> DriftReport:
    """Compare snapshot against current state."""
    report = DriftReport()

    # Snapshot lookup
    snap_specs = {s["id"]: s for s in snapshot.get("specs", [])}
    snap_code = {c["file"]: c for c in snapshot.get("code", [])}

    # Current state
    curr_specs = discover_specs(directory, spec_dirs=spec_dirs)
    curr_codes = discover_code(directory, source_dirs=source_dirs)
    curr_spec_map = {s.auto_id: s for s in curr_specs}
    curr_code_map = {c.file: c for c in curr_codes}

    # ── Specs ──
    for sid, snap_s in snap_specs.items():
        curr = curr_spec_map.get(sid)
        if curr is None:
            report.specs_removed.append(snap_s)
        else:
            title_changed = curr.title != snap_s["title"]
            body_changed = curr.body_hash != snap_s["body_hash"]

            if title_changed:
                report.specs_changed.append({
                    "id": sid,
                    "old_title": snap_s["title"],
                    "new_title": curr.title,
                    "file": curr.file,
                    "body_hash_changed": body_changed,
                })
            elif body_changed:
                report.specs_body_changed.append({
                    "id": sid,
                    "title": curr.title,
                    "file": curr.file,
                    "old_hash": snap_s.get("body_hash", ""),
                    "new_hash": curr.body_hash,
                    "old_lines": snap_s.get("body_line_count", 0),
                    "new_lines": curr.body_line_count,
                    "old_preview": snap_s.get("body_preview", ""),
                    "new_preview": curr.body_preview,
                })

    for cs in curr_specs:
        if cs.auto_id not in snap_specs:
            report.specs_added.append({
                "id": cs.auto_id,
                "title": cs.title,
                "file": cs.file,
                "body_hash": cs.body_hash,
                "body_hash_content": cs.body_hash_content,
            })

    # ── Rename detection: match removed → added by body_hash_content ──
    if report.specs_removed and report.specs_added:
        removed_by_hash: dict[str, dict] = {
            s["body_hash_content"]: s for s in report.specs_removed
            if s.get("body_hash_content")
        }
        truly_added: list[dict] = []
        for added in report.specs_added:
            match = removed_by_hash.get(added.get("body_hash_content"))
            if match:
                report.specs_renamed.append({
                    "old_id": match["id"],
                    "new_id": added["id"],
                    "old_title": match["title"],
                    "new_title": added["title"],
                    "file": added["file"],
                    "body_hash_content": added.get("body_hash_content", ""),
                })
            else:
                truly_added.append(added)
        report.specs_added = truly_added

    # ── Code ──
    for cf, snap_c in snap_code.items():
        curr = curr_code_map.get(cf)
        if curr is None:
            report.code_removed.append(snap_c)
        else:
            # File-level hash
            file_hash_changed = curr.file_hash != snap_c.get("file_hash", "")

            # Symbol changes
            old_syms = set(snap_c.get("symbols", []))
            new_syms = set(curr.symbols)
            added_syms = new_syms - old_syms
            removed_syms = old_syms - new_syms

            # Function body hashes
            snap_funcs = {f["name"]: f for f in snap_c.get("functions", [])}
            changed_funcs: list[dict] = []

            for cf_func in curr.functions:
                snap_f = snap_funcs.get(cf_func.name)
                if snap_f and cf_func.body_hash != snap_f["body_hash"]:
                    changed_funcs.append({
                        "name": cf_func.name,
                        "kind": cf_func.kind,
                        "line": cf_func.line,
                        "old_hash": snap_f["body_hash"],
                        "new_hash": cf_func.body_hash,
                    })

            if added_syms or removed_syms or (file_hash_changed and not (added_syms or removed_syms)):
                entry: dict = {"file": cf}
                if added_syms:
                    entry["added"] = sorted(added_syms)
                if removed_syms:
                    entry["removed"] = sorted(removed_syms)
                if file_hash_changed:
                    entry["file_hash_changed"] = True
                report.code_symbols_changed.append(entry)

            if changed_funcs:
                report.code_funcs_changed.append({
                    "file": cf,
                    "funcs": changed_funcs,
                })

    for cc in curr_codes:
        if cc.file not in snap_code:
            report.code_added.append({
                "file": cc.file,
                "module": cc.module,
                "symbols": cc.symbols,
                "language": cc.language,
            })

    # ── Coverage / orphans ──
    graph_now = build_heuristic_graph(
        directory,
        specs=curr_specs if curr_specs else None,
        codes=curr_codes if curr_codes else None,
        spec_dirs=spec_dirs, source_dirs=source_dirs,
    )
    from specbridge.analyzers import coverage_summary, find_orphan_specs

    report.coverage_before = snapshot.get("coverage", {})
    after_cov = coverage_summary(graph_now)
    after_cov["spec_count"] = len(graph_now.nodes_by_type(NodeType.SPEC))
    after_cov["code_count"] = len(graph_now.nodes_by_type(NodeType.CODE)) + len(graph_now.nodes_by_type(NodeType.TEST))
    report.coverage_after = after_cov

    curr_orphan_specs = set(find_orphan_specs(graph_now))
    prev_orphan_specs = set(snapshot.get("orphan_spec_ids", []))
    common_specs = set(snap_specs.keys()) & {s.auto_id for s in curr_specs}
    for sid in common_specs:
        if sid in curr_orphan_specs and sid not in prev_orphan_specs:
            report.new_orphan_specs.append(sid)
        elif sid not in curr_orphan_specs and sid in prev_orphan_specs:
            report.resolved_orphan_specs.append(sid)

    return report
