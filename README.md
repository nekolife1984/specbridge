# specbridge

> **Spec ↔ Code bridge.** Framework-agnostic, read-only traceability analyzer for spec-driven development.

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
[![ci](https://github.com/nekolife1984/specbridge/actions/workflows/ci.yml/badge.svg)](https://github.com/nekolife1984/specbridge/actions)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

`specbridge` maps the relationships between your specifications and source code — **without modifying either**. It's a read-only tool that detects spec↔code coverage, drift, impact, and boundary violations.

---

## Install (limited release)

```bash
pip install git+https://github.com/nekolife1984/specbridge.git
```

Or clone and install locally:

```bash
git clone https://github.com/nekolife1984/specbridge.git
cd specbridge
pip install -e .
```

After installation, the fastest way to set up a project is:

```bash
# Interactive setup: detects dirs, installs hook, deploys AGENTS.md
specbridge setup
```

Or use the standalone script (no pre-install needed):

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/nekolife1984/specbridge/main/scripts/setup.sh)
```

---

## Quickstart (3 minutes)

### 0. One-command setup

```bash
specbridge setup
```

This creates `.specbridge.yaml`, installs the pre-commit drift hook, deploys `AGENTS.md` for AI agents, and takes the first snapshot — all in one go.

### 1. Try the example project

```bash
cd examples/todo-app
specbridge analyze --merge
```

You'll see output like:

```
Nodes: 9 | Edges: 16
Coverage: 100.0%
```

That's specbridge reading the Markdown specs (`docs/tasks.md`) and Python code (`src/tasks/service.py`), then linking them via `@impl` tags and filename heuristics.

### 2. Run it on your own project

Create a `.specbridge.yaml` in your project root:

```yaml
spec_dirs:
  - docs           # Where your spec documents live
source_dirs:
  - src            # Where your source code lives
  - tests          # (optional) test files
```

Then run:

```bash
specbridge analyze --merge
```

### 3. See what else you can do

```bash
specbridge coverage                  # Coverage stats (text)
specbridge impact --spec-id 1.1      # What implements this spec?
specbridge snapshot                  # Save a baseline
specbridge drift --git-base main     # Detect changes since a git ref
specbridge validate-boundary         # Check _Boundary:_ markers
specbridge impact --spec-id 1.1 --call-graph  # Transitive (indirect) impact
specbridge call-graph --spec-id 1.1  # Call graph analysis standalone
specbridge setup                     # One‑command project setup
```

---

## What is specbridge good for?

| Use case | Command | Why it matters |
|----------|---------|----------------|
| **Audit coverage** | `specbridge coverage` | Which specs have no implementing code? |
|| **Impact analysis** | `specbridge impact --spec-id 1.1` | What files change if spec 1.1 changes? |
|| **Transitive impact** | `specbridge impact --spec-id 1.1 --call-graph` | What files are indirectly impacted via function calls? |
|| **Call graph** | `specbridge call-graph --spec-id 1.1` | Standalone call graph analysis |
| **Drift detection** | `specbridge drift --git-base main` | Did code diverge from specs? |
| **CI gate** | `specbridge drift --gate` | Block PRs with undrifted changes |
| **Boundary validation** | `specbridge validate-boundary` | Code refs staying in declared scope? |
|| **No tags required** | `specbridge analyze --merge` | Works even on projects without SSD tags |
|| **MCP / AI agent** | `specbridge serve` | Let AI agents query traceability |
|| **One‑command setup** | `specbridge setup` | Auto‑configure project in 30 seconds |

---

## Key features

- **Read-only**: Never touches your specs or code. All output goes to `.specbridge/`.
- **Dual mode**: Tag-based (spectra `@impl`, `@verifies`) **and** heuristic (filename/symbol matching, no tags needed).
|- **Multi-language**: Python, TypeScript, Go, Rust, Java, Ruby, C/C++, C#, Swift, Kotlin, Dart, PHP — 18 languages (AST-based function extraction via **tree-sitter**, optional: `pip install specbridge[ast]`).
|- **Call graph**: Function-level call graph for transitive (indirect) impact analysis via `--call-graph` flag.
|- **Graphify adapter** (optional): Deep AST-based code graph via `graphify` CLI (`pipx install graphifyy`, then `specbridge analyze --merge`).
|- **3 output formats**: text (terminal), JSON (jq/CI), HTML (interactive D3.js graph).
- **Plugin SDK**: Write custom adapters as pip-installable packages.

---

## Demo: see it in action

```bash
# Clone once
git clone https://github.com/nekolife1984/specbridge.git
cd specbridge
pip install -e .

# Run the example
specbridge analyze --dir examples/todo-app --merge

# Show coverage
specbridge coverage --dir examples/todo-app

# HTML graph (open .specbridge/trace.html in browser)
specbridge analyze --dir examples/todo-app --merge --format html

# Watch mode (live update on file changes)
specbridge watch --dir examples/todo-app --merge
```

---

## Project structure

```
specbridge/
├── specbridge/         # Core library
│   ├── cli.py          # Click-based CLI (12 commands)
│   ├── core/           # Data model (TraceNode, TraceEdge, TraceGraph)
│   ├── adapters/       # Plugin registry + built-in adapters
│   ├── infer/          # Heuristic matching engine
│   ├── discovery/      # Spec/code file scanning (18 languages)
│   ├── analyzers/      # Coverage, drift, import graph, call graph
│   ├── outputs/        # Text, JSON, HTML rendering
│   ├── guard.py        # Read-only write validation
│   ├── config.py       # .specbridge.yaml loader
│   └── mcp_server.py   # MCP server for AI agents
├── examples/
│   └── todo-app/       # Runnable demo project
├── docs/               # Design docs (EN + JA, 11 categories)
├── .agents/
│   ├── scripts/
│   │   └── pre-commit.specbridge.sh   # Pre-commit drift hook
│   └── skills/
│       └── specbridge/
│           └── SKILL.md             # AI agent skill for using specbridge
├── AGENTS.md            # AI agent workflow guide (read by all agents)
└── tests/              # 198+ tests
```

---

## Required setup

Every project needs a `.specbridge.yaml` (or `[tool.specbridge]` in `pyproject.toml`):

```yaml
spec_dirs:
  - docs
  - specs
source_dirs:
  - src
  - lib
  - app
exclude_dirs:
  - .git
  - node_modules
  - .venv
  - .specbridge
min_confidence: 0.15
max_output_nodes: 40
```

That's it. No tags, no annotations — specbridge infers what it can out of the box.

---

## Pre-commit Hook (Drift Gate)

specbridge includes a **pre-commit hook** that automatically checks for trace drift before every commit. If the code has changed but the corresponding spec hasn't been updated (or vice versa), the commit is blocked.

```
git commit ─→ specbridge drift --git-base HEAD --gate ─→ no drift → commit OK
                                                     └→ drift detected → ❌ commit blocked
```

**Install:**

```bash
# Recommended: one‑command setup (creates config, installs hook, deploys AGENTS.md)
specbridge setup

# Or install hook only:
bash scripts/install-hooks.sh

# Or manually:
ln -sf ../../.agents/scripts/pre-commit.specbridge.sh .git/hooks/pre-commit
```

**What happens when drift is detected:**

```text
❌ specbridge: Drift detected between snapshot and your changes!
   Run 'specbridge drift' to see details.
   If changes are intentional, run 'specbridge snapshot' to update baseline
   and include .specbridge/snapshot.json in your commit.
```

The hook uses **git-base mode** (`drift --git-base HEAD`) — only files changed since the last commit are analysed, making it lightweight even on large projects.

**Manual baseline setup (first time):**

```bash
specbridge snapshot          # Take the initial snapshot
git add .specbridge/         # Track the baseline
```

---

## AI Agent Skill

specbridge ships with an **AI agent skill** at `.agents/skills/specbridge/SKILL.md` that teaches AI coding agents how to use the tool — install, run analysis, check drift, set up CI gates, and use the MCP server.

**Install into Hermes Agent:**

```bash
# Recommended: specbridge setup handles this automatically
specbridge setup

# Or manually:
bash scripts/install-hooks.sh
```

This symlinks both the pre-commit hook and the skill into `~/.hermes/skills/`. Agents can then load the `specbridge` skill to get full usage documentation.

**Manual install (other agents):**

```bash
ln -sf "$(pwd)/.agents/skills/specbridge" ~/.hermes/skills/software-development/specbridge
```

Or reference `.agents/skills/specbridge/SKILL.md` directly.

### Setting up AGENTS.md for your project

To make **any AI agent** (Hermes, Claude Code, OpenCode, Cursor, Codex) follow specbridge conventions, add an `AGENTS.md` to your project root:

```markdown
# Project Guide

This project uses **specbridge** for spec↔code traceability.

## Required rules (before and after every code change)

1. `specbridge snapshot --reason "..."` — save the current state
2. Write code (and update specs if needed)
3. `specbridge drift` — check for drift
4. If drift is detected, update the design document first
5. `git commit` (pre-commit hook auto-checks)
```

See [AGENTS.md](AGENTS.md) in the specbridge repo for a complete example.

---

## Architecture

```text
┌──────────────────────────────────────────────┐
│  SSD Frameworks (spectra, heuristic, …)      │
└──────────────┬───────────────────────────────┘
               │ read (input)
               ▼
┌──────────────────────────────────────────────┐
│  ★ specbridge ★                               │
│  ├─ adapters/  (registry + per-framework)    │
│  ├─ infer/     (heuristic bridge)            │
│  ├─ core/      (model + tag extractor)       │
│  ├─ discovery/ (spec/code candidate parsing) │
│  ├─ analyzers/ (coverage, drift, orphans)    │
│  └─ guard/     (read-only path validation)   │
└──────────────┬───────────────────────────────┘
               │ text / JSON / exit code
               ▼
┌──────────────────────────────────────────────┐
│  CLI output / .specbridge/snapshot.json      │
└──────────────────────────────────────────────┘
```

---

## Documentation

Full design docs are in [`docs/`](docs/) (EN + JA, 12 categories):

| Doc | Description |
|-----|-------------|
| [Architecture](docs/en/01-architecture.md) | High-level design & data flow |
| [Data Model](docs/en/02-data-model.md) | TraceNode, TraceEdge, TraceGraph |
| [Adapter Plugin System](docs/en/03-adapter-plugin-system.md) | Plugin SDK, built-in adapters |
| [Discovery Engine](docs/en/04-discovery-engine.md) | Spec/code scanning, symbol extraction |
| [Heuristic Matching](docs/en/05-heuristic-matching.md) | No-tag inference algorithm |
| [Drift Detection](docs/en/06-drift-detection.md) | Snapshot, drift, rename detection |
| [CLI Commands](docs/en/07-cli-commands.md) | All 10 commands reference |
| [Output Rendering](docs/en/08-output-rendering.md) | Text, JSON, HTML output formats |
| [Configuration](docs/en/09-configuration.md) | .specbridge.yaml, layered config |
| [MCP Integration](docs/en/10-mcp-integration.md) | AI agent integration |
|| [Testing Strategy](docs/en/11-testing-strategy.md) | Test architecture |
|| [Branching Strategy](docs/en/12-branching-strategy.md) | Branch conventions, PR workflow, release process |

---

## Feedback (limited release)

This is a private beta. Feedback, bugs, and feature requests welcome:

- **GitHub Issues**: https://github.com/nekolife1984/specbridge/issues
- **Direct**: nekolife@gmail.com

When reporting an issue, include:

```bash
specbridge --version
specbridge config
```

---

## License

MIT
