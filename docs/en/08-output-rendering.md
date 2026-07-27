# Output Rendering

> **Date:** 2026-07-27
> **Version:** 1.0.0

## 1. Overview

The `outputs/` module renders a `TraceGraph` into three formats, selected via the `--format` CLI option or used programmatically.

```
TraceGraph
    │
    ├──▶ render_text()  → Human-readable terminal output
    ├──▶ render_json()  → Structured data for tooling (jq, CI, APIs)
    └──▶ render_html()  → Interactive D3.js force-directed graph
```

Additionally, new in v1.0:

- **Color-coded coverage** — coverage percentage displayed with 🟢🟡🔴 indicators
- **One-line CI summary** — `render_one_line_coverage()` for `--summary-only` mode
- **Rich progress display** — `rich_utils.py` provides spinner and progress bar helpers

## 2. Text Output (`outputs/text.py`)

The default output format. Renders the graph as a human-readable terminal report.

**Output structure:**

```
specbridge — Trace Graph
========================================
Nodes: 28 | Edges: 34
Coverage: 83.3% (10/12)

📄 Specs:
  auth.auth.1.1         [2 refs]  User Authentication
  auth.auth.1.2         [1 refs]  Login
  auth.auth.2           [0 refs]  Password Reset

📁 Code refs:
  src/auth/login.py                   → auth.auth.1.1, auth.auth.1.2
  src/auth/register.py                → auth.auth.2
  src/lib/utils.py                     (unlinked)

🧪 Test refs:
  tests/test_auth.py                  → auth.auth.1.1
```

**With function-level matching:**

When `build_heuristic_graph()` is used (heuristic adapter), function-level nodes appear in a dedicated section:

```
🔧 Function refs:
  specbridge/core/__init__.py::TraceNode      → docs.en.02-data-model.1.2.1
  specbridge/infer/__init__.py::_tokenize     → docs.en.05-heuristic-matching.1.4
```

Function nodes are identified by `::` in their ID (`file.py::function_name`). They appear alongside file-level edges and include evidence from `heuristic:funcname` matches.

**With `--top N`:**

If `max_nodes` is set, only the top N items per category are shown with a truncation note:

```
  ... and 3 more specs
  ... and 5 more code files
```

### 2.1 Color-Coded Coverage

Coverage stats now include a visual indicator:

| Coverage | Indicator | Meaning |
|----------|-----------|---------|
| ≥ 80% | 🟢 Green | Good coverage |
| ≥ 50% | 🟡 Yellow | Moderate coverage |
| < 50% | 🔴 Red | Low coverage |

```
📊 Spec Coverage  🟢
========================================
  Total specs:  12
  Covered:      10
  Orphan specs: 2
  Coverage:     83.3%
```

### 2.2 One-Line CI Summary

The `render_one_line_coverage()` function produces a compact, CI-friendly line:

```
🟢 Coverage: 83.3% (10/12) | Specs: 12 | Code refs: 45 | 🟡 3 total orphans
```

Used by `specbridge analyze --summary-only`.

## 3. JSON Output (`outputs/json_out.py`)

Structured JSON intended for machine consumption.

**Output structure:**

```json
{
  "specbridge_version": "1.0.0",
  "nodes": [
    {
      "id": "auth.auth.1.1",
      "type": "spec",
      "title": "User Authentication",
      "source": {
        "file": "docs/auth/auth.md",
        "line": 3,
        "column": null,
        "label": null
      },
      "framework_origin": "heuristic",
      "confidence": 0.8,
      "metadata": {
        "heading_depth": 2,
        "heading_text": "1.1 User Authentication"
      }
    }
  ],
  "edges": [
    {
      "src_id": "src/auth/login.py",
      "dst_id": "auth.auth.1.1",
      "relation": "implements",
      "strength": "inferred",
      "evidence": [
        {
          "kind": "heuristic:dirname",
          "value": "dir 'auth' matches",
          "source": { "file": "docs/auth/auth.md", "line": 3, "column": null, "label": null }
        }
      ]
    }
  ]
}
```

**Implementation:**

```python
def render_json(graph: TraceGraph, indent: int = 2) -> str:
    payload = {
        "specbridge_version": "1.0.0",
        "nodes": [_node_dict(n) for n in graph.nodes.values()],
        "edges": [_edge_dict(e) for e in graph.edges],
    }
    return json.dumps(payload, indent=indent, ensure_ascii=False, default=str)
```

Enum values are serialized to their `.value` string representation.

## 4. HTML Output (`outputs/html.py`)

Generates a self-contained HTML page with an interactive D3.js force-directed graph.

### Features

- **Color-coded nodes** by type (SPEC = blue, CODE = green, TEST = yellow, DESIGN = purple)
- **Shape-coded nodes** (SPEC = rectangle, CODE = circle, TEST = diamond, DESIGN = triangle)
- **Arrow-directed edges** with relation labels (implements, verifies, satisfies, depends)
- **Interactive drag** — nodes are draggable
- **Zoom and pan** — mouse wheel zoom, drag to pan
- **Click to highlight** — clicking a node dims unrelated nodes
- **Hover tooltip** — shows ID, type, file, framework
- **Legend** — bottom-left color/shape reference
- **Header** — shows spec/code/test/edge counts
- **`--dry-run` support** — preview without saving to disk

### D3.js Implementation

The HTML uses D3.js v7 loaded from CDN (`https://d3js.org/d3.v7.min.js`). The graph uses:

- `d3.forceSimulation` with:
  - `forceLink` (spacing: 120px)
  - `forceManyBody` (strength: -300)
  - `forceCenter` (centered on viewport)
  - `forceCollide` (30px radius)
- SVG markers per relation type for arrow heads
- CSS transitions for highlight effects

### Output Location

The HTML file is saved to `.specbridge/trace.html` (unless `--dry-run` is set):

```python
if dry_run:
    click.echo("   📄 HTML output generated (--dry-run, not saved)", err=True)
else:
    out_path = root / ".specbridge" / "trace.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    webbrowser.open(f"file://{out_path.resolve()}")
```

## 5. Rich Progress Utilities (`outputs/rich_utils.py`) ✨ New in v1.0

A new module providing Rich-based progress displays for long-running operations.

### Spinner

For indeterminate progress:

```python
with progress_spinner("🔍 Scanning project..."):
    # long operation
    result = do_work()
```

### Progress Bar

For determinate progress with known step count:

```python
with progress_bar("Analyzing files...", total=len(files)) as (progress, task):
    for f in files:
        # process file
        progress.advance(task)
```

### Console

Shared Rich Console instance (stderr by default) for styled output:

```python
from specbridge.outputs.rich_utils import get_console
console = get_console()
```

## 6. Evidence Display

All three output formats include evidence information:

| Format | Evidence Display |
|--------|-----------------|
| **Text** | `∵ kind: value` lines under each edge |
| **JSON** | `evidence` array on each edge object |
| **HTML** | Tooltip on hover + edge labels |

## 7. Text vs JSON vs HTML

| Feature | Text | JSON | HTML |
|---------|------|------|------|
| **Human readability** | ★★★ | ★ | ★★★ (interactive) |
| **Machine parsing** | ★ | ★★★ | ★ |
| **File size** | Small | Medium | Large (~30KB) |
| **External deps** | None | None | D3.js (CDN) |
| **Output location** | stdout | stdout | `.specbridge/trace.html` |
| **Chaining (pipe)** | ✓ | ✓ (with jq) | ✗ |
| **CI friendly** | ✓ (text parsing) | ✓ (JSON parser) | ✗ |
| **Summary-only mode** | ✓ | N/A | N/A |
