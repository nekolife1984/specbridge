# Drift Detection

> **Date:** 2026-07-26
> **Version:** 0.0.1.dev0

## 1. Overview

specbridge provides drift detection to identify changes between a saved snapshot and the current project state. This enables CI gates ("has any spec drifted?"), pre-commit validation, and change impact analysis.

```
                        Time
                    ──────────▶

Snapshot (t₀)                         Current State (t₁)
┌──────────────────┐                  ┌──────────────────┐
│ discover_specs()  │                  │ discover_specs()  │
│ discover_code()   │                  │ discover_code()   │
│ build_graph()     │                  │ build_graph()     │
└────────┬─────────┘                  └────────┬─────────┘
         │                                      │
         └──────────────┬──────────────────────┘
                        │
                        ▼
              ┌────────────────────┐
              │   compute_drift()  │
              │   ───────────────  │
              │   Compare hashes   │
              │   section by sec.  │
              └────────┬───────────┘
                       │
                       ▼
              ┌────────────────────┐
              │   DriftReport      │
              │   ───────────────  │
              │   .has_drift       │
              │   .render_text()   │
              │   .to_dict()      │
              └────────────────────┘
```

## 2. Snapshot Model

A snapshot is a JSON file saved to `.specbridge/snapshot.json`. It captures:

### Snapshot Structure

```json
{
  "timestamp": "2026-07-26T14:30:00",
  "reason": "Pre-refactor baseline",
  "specs": [
    {
      "id": "auth.auth.1.1",
      "file": "docs/auth/auth.md",
      "title": "User Authentication",
      "heading_text": "1.1 User Authentication",
      "depth": 2,
      "line": 3,
      "body_hash": "a1b2c3d4e5f6a7b8",         // SHA256[:16] of heading + body
      "body_hash_content": "b2c3d4e5f6a7b8c9",  // SHA256[:16] of body only
      "body_line_count": 15,
      "body_preview": "The system shall authenticate users via email and password..."
    }
  ],
  "code": [
    {
      "file": "src/auth/login.py",
      "module": "auth",
      "symbols": ["login", "authenticate", "validate_password"],
      "is_test": false,
      "language": "Python",
      "imports": ["flask", "sqlalchemy"],
      "file_hash": "c3d4e5f6a7b8c9d0",         // SHA256[:16] of entire file
      "functions": [
        {
          "name": "login",
          "kind": "function",
          "line": 10,
          "body_hash": "d4e5f6a7b8c9d0e1",     // SHA256[:16] of function body
          "body_lines": 25
        }
      ]
    }
  ],
  "orphan_spec_ids": ["auth.auth.2.1"],
  "coverage": {
    "total": 5,
    "covered": 4,
    "orphan": 1,
    "coverage_pct": 80.0,
    "spec_count": 5,
    "code_count": 12
  }
}
```

### Hash Strategy

Three layers of hashing for granular change detection:

| Level | What | Hash Algorithm | Used For |
|-------|------|----------------|----------|
| **Section** | Spec heading + body text | SHA256[:16] | Detecting spec content changes |
| **Section (no heading)** | Body text only | SHA256[:16] | Rename detection (same body, moved heading) |
| **File** | Entire code file | SHA256[:16] | Detecting code file changes |
| **Function** | Function/class body | SHA256[:16] | Detecting per-function changes |

The 16-character hex truncation is sufficient to detect any meaningful change while keeping snapshot size manageable.

## 3. Drift Comparison: `compute_drift()`

```python
def compute_drift(
    snapshot: dict,
    directory: str,
    *,
    spec_dirs: list[str] | None = None,
    source_dirs: list[str] | None = None,
) -> DriftReport:
```

### 3.1 Spec Comparison

For each spec in the snapshot, compare against the current state:

1. **Removed**: Spec ID exists in snapshot but not in current state
2. **Added**: Spec ID exists in current state but not in snapshot
3. **Title changed**: Same ID, different `title`
4. **Body changed**: Same ID, same title, different `body_hash`
5. **Renamed**: Same `body_hash_content` but different auto_id (removed + added pair)

### 3.2 Code Comparison

For each code file in the snapshot, compare against the current state:

1. **Removed**: File path exists in snapshot but not on disk
2. **Added**: File path exists on disk but not in snapshot
3. **Symbols changed**: Same file, different set of extracted symbols
4. **Function body changed**: Same function name, different `body_hash`
5. **File hash changed**: Different `file_hash` without symbol changes (content-only edits)

### 3.3 Rename Detection Algorithm

```python
# Detect renames by matching body_hash_content
# A spec that was removed + added with the same body_hash_content = renamed
removed_by_hash = {s["body_hash_content"]: s for s in specs_removed
                   if s.get("body_hash_content")}
for added in specs_added:
    match = removed_by_hash.get(added.get("body_hash_content"))
    if match:
        specs_renamed.append({...})
    else:
        truly_added.append(added)
```

### 3.4 Orphan / Coverage Delta

After comparing specs and code, the function re-builds the heuristic graph for the current state and computes:

- New orphan specs (previously covered, now orphaned)
- Resolved orphan specs (previously orphaned, now covered)
- Coverage percentage before → after (with delta)

## 4. DriftReport

The comparison result is a `DriftReport` object with the following change categories:

| Category | Field | Description |
|----------|-------|-------------|
| **Specs** | `specs_added` | New spec sections |
| | `specs_removed` | Deleted spec sections |
| | `specs_changed` | Title changes |
| | `specs_body_changed` | Body content changes (same title) |
| | `specs_renamed` | Content preserved, ID/title changed |
| **Code** | `code_added` | New source files |
| | `code_removed` | Deleted source files |
| | `code_symbols_changed` | Symbol additions/removals |
| | `code_funcs_changed` | Function body hash changes |
| **Coverage** | `new_orphan_specs` | Specs that lost all implementations |
| | `resolved_orphan_specs` | Specs that gained implementations |
| | `new_orphan_code` | Code files with no spec reference |
| | `resolved_orphan_code` | Code files that gained a spec reference |
| | `coverage_before` / `coverage_after` | Overall coverage stats |

## 5. Commands

### `specbridge snapshot`

Takes a new snapshot of the current project state.

```
$ specbridge snapshot --dir . --reason "Pre-refactor baseline"
📸 Snapshotting /Users/me/project ...
   Specs: 12 | Code files: 45
   Coverage: 83.3%
   Saved: .specbridge/snapshot.json
```

### `specbridge drift`

Compares current state against the saved snapshot.

```
$ specbridge drift
📄  New specs (2):
     + auth.auth.3: Password Reset  (docs/auth/password.md)
🗑️  Removed specs (1):
     - auth.auth.1.3: Deprecated Feature  (docs/auth/auth.md)
⚡  Changed function bodies (1):
     ~ src/auth/login.py
         login  (function:10)  hash: a1b2... → c3d4...
📈  Coverage: 83.3% → 75.0%  (-8.3%)
```

### `specbridge drift --git-base`

Compares changes against a git base ref without needing a snapshot. This is an alternative to snapshot-based drift:

```
$ specbridge drift --git-base main
⚠️  3 spec-affecting change(s):
   src/auth/login.py → affects spec auth.auth.1.1
   tests/test_auth.py → affects spec auth.auth.1.2
```

### `specbridge drift --gate`

Exit with code 1 if any drift is detected. Useful for CI pipelines:

```yaml
# GitHub Actions
- run: specbridge snapshot
- run: specbridge drift --gate
```

## 6. Git-Based Drift (`_drift_git()`)

An alternative drift path that uses `git diff --name-only <base>` instead of snapshots:

```
1. git diff --name-only base_ref → list of changed files
2. Run full analysis (detect adapter → analyze → TraceGraph)
3. For each changed file, check if it implements any spec
4. Report spec-affecting changes only
```

This is lighter than snapshot comparison (no hash comparison) but only tells you *which* specs are affected, not *how* (title change, body change, etc.).

## 7. Edge Cases

| Situation | Behavior |
|-----------|----------|
| **No snapshot exists** | `drift` errors: "run `specbridge snapshot` first" |
| **Snapshot file corrupted** | `load_snapshot()` returns `None`, triggers error |
| **File renames** | Code files matched by path; renames show as removed + added |
| **Spec renames** | Detected via `body_hash_content` matching |
| **Empty project on re-scan** | All specs/code show as removed |
| **Git base with no changes** | "No changes detected" |
| **Snapshot from different directory** | Works if structure is compatible (no guard against this) |
