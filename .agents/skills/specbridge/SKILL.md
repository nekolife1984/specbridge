---
name: specbridge
description: "Use specbridge: install, run, analyze, check drift, MCP."
version: 1.1.0
author: Hermes Agent
tags: [specbridge, traceability, spec-driven, heuristic, mcp, call-graph]
---

# specbridge — Spec↔Code Traceability Tool

**specbridge** maps relationships between design documents and source code without modifying either. It detects coverage gaps, drift, impact, boundary violations, and **transitive (indirect) impact** via call graph analysis across 18 programming languages.

## When to Use This Skill

- **Analyze traceability**: "What specs does this code implement?" or "What code implements this spec?"
- **Transitive impact**: "What files are indirectly impacted via function calls?"
- **Check drift**: "Did the code diverge from the design docs since the last snapshot?"
- **CI gate**: "Block this PR if specs and code are out of sync."
- **Coverage report**: "Which specs have no implementing code yet?"
- **AI agent integration**: "Let the agent query traceability via MCP."
- **Onboard a new project**: "Set up specbridge for this repo."

## Agent Session Lifecycle

AIエージェントが specbridge を使うプロジェクトで作業する際のルール：

### セッション開始時

```bash
specbridge snapshot --reason "Session: <今回のタスク>"
```

### セッション終了時

```bash
specbridge drift
```

drift が検出されたら → **先に設計書を直すこと**。コードだけ変更してコミットしない。

### コミット前

```bash
git commit  # pre-commit hook が自動で drift --gate を実行
```

---

## Installation

```bash
# From GitHub (limited release)
pip install git+https://github.com/nekolife1984/specbridge.git

# Or local clone
git clone https://github.com/nekolife1984/specbridge.git
cd specbridge && pip install -e ".[dev]"

# Optional: AST-based function extraction (Python/TS/Go/Rust)
pip install "specbridge[ast]"
```

## Quick Start (for any project)

### 1. Create `.specbridge.yaml`

```yaml
spec_dirs:
  - docs           # Where your design docs live
  - specs
source_dirs:
  - src            # Where your source code lives
  - tests
exclude_dirs:
  - .git
  - .venv
  - .specbridge
  - node_modules
min_confidence: 0.15
```

### 2. Run analysis

```bash
specbridge analyze --merge
```

This discovers all spec sections (Markdown headings) and code files (18 languages), then infers relationships using:
- **SpectraAdapter**: reads `@impl`/`@spec`/`@verifies` tags (if present)
- **HeuristicAdapter**: matches by filename, directory, symbol names, and content (no tags required)

## Commands Reference

| Command | What It Does | When to Use |
|---------|-------------|-------------|
| `analyze` | Build trace graph and show coverage | First command to run; daily check |
| `impact --spec-id <id>` | Find what implements a spec | "What files implement spec X?" |
| `impact --spec-id <id> --call-graph` | Include transitive (indirect) impact | "What else is affected via call chains?" |
| `call-graph --spec-id <id>` | Standalone call graph with transitive impact | Deep dive into indirect dependencies |
| `coverage` | Show spec coverage stats | "Are all specs covered?" |
| `snapshot` | Save current state as baseline | Before making changes |
| `drift` | Detect changes since snapshot | "Did code diverge from specs?" |
| `drift --gate` | Exit 1 if drift (CI-friendly) | CI gate |
| `drift --git-base <ref>` | Compare against git ref | "What changed since last release?" |
| `validate-boundary` | Check `_Boundary:_` markers | "Does code stay in declared scope?" |
| `watch` | Re-analyze on file changes | Real-time feedback during dev |
| `config` | Show current config | Debug configuration |
| `plugins` | List installed adapter plugins | Check plugin availability |
| `serve` | Start MCP server for AI agents | AI agent integration |

### Common Workflows

**Daily coverage check:**
```bash
specbridge analyze --merge --top 20
```

**Before committing:**
```bash
specbridge snapshot
specbridge drift --gate
```

**Find what implements a spec (fuzzy search):**
```bash
specbridge impact --spec-id 1.2.1       # suffix match
specbridge impact --spec-id TraceNode   # title search
specbridge impact --spec-id build_heuristic_graph  # heading search
```

**Transitive (indirect) impact:**
```bash
# During impact analysis
specbridge impact --spec-id 1.2.1 --call-graph --max-depth 3

# Standalone call graph analysis
specbridge call-graph --spec-id 1.2.1
specbridge call-graph --spec-id 1.2.1 --max-depth 5 --format json
```

**CI gate (GitHub Actions):**
```yaml
- run: specbridge snapshot
- run: specbridge drift --gate
- run: specbridge analyze --merge --top 10
```

**HTML graph for visual review:**
```bash
specbridge analyze --merge --format html
open .specbridge/trace.html
```

**Include dependency and call graphs:**
```bash
specbridge analyze --merge --deps --call-graph
# Output: Deps: 42 import edges, Calls: 156 edges, 47 functions
```

## Output Interpretation

### File-level view
```
Nodes: 476 | Edges: 478
Coverage: 60.7% (259/427)

📄 Specs:
  docs.en.02-data-model.1.2.1  [2 refs]  TraceNode

📁 Code refs:
  specbridge/core/__init__.py   → docs.en.02-data-model.1.2.1, ...
```

### Function-level view (heuristic mode)
```
🔧 Function refs:
  specbridge/core/__init__.py::TraceNode  → docs.en.02-data-model.1.2.1
```

Function nodes have `::` in their ID (`file.py::func_name`).

### Transitive impact view
```
📄 Spec: docs.tasks.1
   Direct files:     2
     📁 src/tasks/service.py
     📁 tests/test_tasks.py
   🔗 Transitive files (1 hop(s)): 1
     → src/tasks/db.py
```

## Call Graph Analysis

The call graph maps **function-level caller→callee relationships** to find indirectly impacted files.

### How it works

1. **Lightweight builder** (built-in, no deps): scans source files for function calls matching known definitions
2. **CRG import** (optional): reads `code-review-graph` JSON output for AST-precise graphs
3. **BFS traversal**: starting from direct implementers, walks function calls up to `--max-depth` hops

### Use cases

- "If I change `db.py::save_task()`, what specs could be affected?"
- "This function is called from 3 places — any transitive impact on my spec?"
- CI check: "Does this PR introduce unexpected transitive coupling?"

## MCP Server (AI Agent Integration)

Start the MCP server so AI agents can query traceability directly:

```bash
pip install specbridge[mcp]
specbridge serve
```

The server exposes these tools:
- `analyze` — run full analysis
- `impact` — find what implements a spec (supports fuzzy search)
- `coverage` — get coverage stats
- `drift` — check for drift
- `validate_boundary` — check boundary violations

**Agent usage example:**
```
User: "What implements spec TraceNode?"
Agent: (calls specbridge impact tool)
→ "specbridge/core/__init__.py::TraceNode implements docs.en.02-data-model.1.2.1"
```

## Configuration File (.specbridge.yaml)

```yaml
spec_dirs: [docs, specs, design]
source_dirs: [src, lib, app]
exclude_dirs: [.git, node_modules, .venv, __pycache__, dist, build, .specbridge]
min_confidence: 0.15        # Lower = more edges (noisier)
max_output_nodes: 40        # Truncation for --top N
```

Config can also live in `pyproject.toml` under `[tool.specbridge]`.

## Git Hooks Setup

specbridge provides hooks for **two audiences**:

| Audience | Command | What's installed |
|----------|---------|-----------------|
| **specbridge developers** | `sh scripts/install-hooks.sh` | pre-commit (branch validation + drift) + pre-push (block push to main) |
| **Downstream users** | `specbridge setup` or `bash scripts/setup.sh` | pre-commit (drift gate only) |

### For specbridge development (this repo)

```bash
bash scripts/install-hooks.sh
```

### For downstream projects

```bash
specbridge setup
```

The pre-commit hook is shared between both audiences — it **auto-detects** whether it's running inside the specbridge repo (by checking for `specbridge/cli.py`). Branch validation and doc sync warnings only activate when inside the specbridge repo. Downstream projects get the drift gate only.

## Drift Detection

```bash
# Take a baseline
specbridge snapshot --reason "Before auth refactor"

# Make changes...

# Check drift
specbridge drift

# CI-friendly
specbridge drift --gate
```

Drift detects:
- New/removed specs
- Heading changes
- **Body-only changes** (content changed, heading unchanged)
- New/removed code files
- Function signature changes
- **Function body changes** (logic changed, name unchanged)
- Coverage changes

## Spec ID Resolution (for impact command)

The `impact --spec-id` command uses multi-level fuzzy search:

1. **Exact ID**: `docs.en.02-data-model.1.2.1`
2. **`spec::` prefix**: `1.1` → `spec::1.1`
3. **ID suffix**: `1.2.1` → matches `docs.en.02-data-model.1.2.1` etc.
4. **Title substring**: `TraceNode` → any spec with "TraceNode" in title
5. **Heading text**: `build_heuristic_graph` → heading containing that text

When multiple specs match, all are displayed with their implementing files.

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `No recognized SSD framework found` | No `.specbridge.yaml` or it's empty | Create config file |
| `Coverage: 0.0%` | Wrong `source_dirs` or `spec_dirs` | Check paths in `.specbridge.yaml` |
| No `@impl` tags being read | Files don't have spectra tags | Heuristic mode works without tags; use `--merge` |
| `No snapshot found` | Haven't run `snapshot` yet | Run `specbridge snapshot` first |
| `Spec 'X' not found` | Wrong spec ID format | Use fuzzy search: try a title or suffix |
| `No call graph could be built` | No function-level nodes | Run `specbridge analyze --deps` first to extract functions |
| JSON output error | Old `json.dump` vs `json.dumps` | Ensure you have the latest version |

## Installing This Skill into Hermes

```bash
# Symlink from repo to Hermes skills directory
mkdir -p ~/.hermes/skills/software-development/
ln -sf "$(pwd)/.agents/skills/specbridge" ~/.hermes/skills/software-development/specbridge
```

## Related Skills

- `heuristic-traceability` — deep-dive into coverage improvement strategies
- `spectra-traceability` — tag-based traceability with spectra framework
- `spec-traceability` — general spec-driven traceability
