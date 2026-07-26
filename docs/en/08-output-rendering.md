# Output Rendering

> **Date:** 2026-07-26
> **Version:** 0.0.1.dev0

## 1. Overview

The `outputs/` module renders a `TraceGraph` into three formats, selected via the `--format` CLI option or used programmatically.

```
TraceGraph
    │
    ├──▶ render_text()  → Human-readable terminal output
    ├──▶ render_json()  → Structured data for tooling (jq, CI, APIs)
    └──▶ render_html()  → Interactive D3.js force-directed graph
```

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

**With `--top N`:**

If `max_nodes` is set, only the top N items per category are shown with a truncation note:

```
  ... and 3 more specs
  ... and 5 more code files
```

## 3. JSON Output (`outputs/json_out.py`)

Structured JSON intended for machine consumption.

**Output structure:**

```json
{
  "specbridge_version": "0.0.1.dev0",
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
        "specbridge_version": "0.0.1.dev0",
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

The HTML file is saved to `.specbridge/trace.html` and automatically opened in the default browser:

```python
out_path = root / ".specbridge" / "trace.html"
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(html, encoding="utf-8")
webbrowser.open(f"file://{out_path.resolve()}")
```

### Node Color and Shape Map

```python
NODE_COLORS = {
    NodeType.SPEC:   "#4A90D9",  # Blue
    NodeType.CODE:   "#50B86C",  # Green
    NodeType.TEST:   "#F5A623",  # Yellow/Orange
    NodeType.DESIGN: "#9B59B6",  # Purple
    NodeType.TASK:   "#7F8C8D",  # Gray
}
```

**When to use HTML output:**
- Exploring trace relationships visually
- Presentations and code reviews
- Debugging heuristic matching results
- Understanding project structure at a glance

## 5. Evidence Display

All three output formats include evidence information:

| Format | Evidence Display |
|--------|-----------------|
| **Text** | `∵ kind: value` lines under each edge |
| **JSON** | `evidence` array on each edge object |
| **HTML** | Tooltip on hover + edge labels |

## 6. Text vs JSON vs HTML

| Feature | Text | JSON | HTML |
|---------|------|------|------|
| **Human readability** | ★★★ | ★ | ★★★ (interactive) |
| **Machine parsing** | ★ | ★★★ | ★ |
| **File size** | Small | Medium | Large (~30KB) |
| **External deps** | None | None | D3.js (CDN) |
| **Output location** | stdout | stdout | `.specbridge/trace.html` |
| **Chaining (pipe)** | ✓ | ✓ (with jq) | ✗ |
| **CI friendly** | ✓ (text parsing) | ✓ (JSON parser) | ✗ |
