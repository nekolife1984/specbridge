---
name: specbridge
description: "Use specbridge: install, run, analyze, check drift, MCP."
version: 1.0.0
author: Hermes Agent
tags: [specbridge, traceability, spec-driven, heuristic, mcp]
---

# specbridge — Spec↔Code Traceability Tool

**specbridge** maps relationships between design documents and source code without modifying either. It detects coverage gaps, drift, impact, and boundary violations across 18 programming languages.

## When to Use This Skill

- **Analyze traceability**: "What specs does this code implement?" or "What code implements this spec?"
- **Check drift**: "Did the code diverge from the design docs since the last snapshot?"
- **CI gate**: "Block this PR if specs and code are out of sync."
- **Coverage report**: "Which specs have no implementing code yet?"
- **AI agent integration**: "Let the agent query traceability via MCP."
- **Onboard a new project**: "Set up specbridge for this repo."

## Installation

```bash
# From GitHub (limited release)
pip install git+https://github.com/nekolife1984/specbridge.git

# Or local clone
git clone https://github.com/nekolife1984/specbridge.git
cd specbridge && pip install -e ".[dev]"
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
| `coverage` | Show spec coverage stats | "Are all specs covered?" |
| `snapshot` | Save current state as baseline | Before making changes |
| `drift` | Detect changes since snapshot | "Did code diverge from specs?" |
| `drift --gate` | Exit 1 if drift (CI-friendly) | CI gate |
| `drift --git-base <ref>` | Compare against git ref | "What changed since last release?" |
| `validate-boundary` | Check `_Boundary:_` markers | "Does code stay in declared scope?" |
| `watch` | Re-analyze on file changes | Real-time feedback during dev |
| `config` | Show current config | Debug configuration |

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

## Pre-commit Hook Setup

```bash
# One-command install
bash scripts/install-hooks.sh

# Or manually
ln -sf ../../.agents/scripts/pre-commit.specbridge.sh .git/hooks/pre-commit
```

The hook runs `specbridge drift --gate` before each commit — blocks if drift is detected.

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
| JSON output error | Old `json.dump` vs `json.dumps` | Ensure you have the latest version |

## Related Skills

- `heuristic-traceability` — deep-dive into coverage improvement strategies
- `spectra-traceability` — tag-based traceability with spectra framework
- `spec-traceability` — general spec-driven traceability

## Installing This Skill into Hermes

```bash
# Symlink from repo to Hermes skills directory
mkdir -p ~/.hermes/skills/software-development/
ln -sf "$(pwd)/.agents/skills/specbridge" ~/.hermes/skills/software-development/specbridge
```
