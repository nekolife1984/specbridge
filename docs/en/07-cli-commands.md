# CLI Commands Reference

> **Date:** 2026-07-27
> **Version:** 1.0.0

## 1. Overview

specbridge provides a Click-based CLI with **13 commands** for traceability analysis, drift detection, and project management.

```
Usage: specbridge [OPTIONS] COMMAND [ARGS]...

  Spec ↔ Code bridge: read-only traceability analyzer for SSD.

Options:
  --version  Show the version and exit.
  --help     Show this message and exit.

Commands:
  analyze            Analyze a project and build a trace graph.
  impact             Find what implements a given spec.
  coverage           Show spec coverage statistics.
  snapshot           Take a structural snapshot of specs and code.
  drift              Detect changes between snapshot and current state.
  status             Show project state dashboard (config, snapshot, coverage, drift).
  validate-boundary  Validate that code refs stay within declared _Boundary:_ markers.
  config             Show / validate current specbridge configuration.
  watch              Watch project for changes and re-analyze automatically.
  plugins            List installed specbridge adapter plugins.
  serve              Start MCP server for AI agent integration.
  call-graph         Build call graph and show transitive (indirect) impact for a spec.
  setup              One‑command project setup (config, hook, AGENTS.md, snapshot).
```

## 2. Commands

### 2.1 `analyze`

Build a trace graph for the project. This is the primary command.

```
Usage: specbridge analyze [OPTIONS]

  Analyze a project and build a trace graph.

Options:
  -d, --dir TEXT      Project directory to analyze  [default: .]
  --format TEXT       Output format (text, json, or html)  [default: text]
  -m, --merge         Merge results from ALL matching adapters (not just the best one)
  --top INTEGER       Show only top N items per category (default: all)
  --deps              Build code dependency graph from imports (adds DEPENDS edges)
  -c, --call-graph    Build call graph for transitive impact analysis
  --fast              Skip function-level matching for faster analysis on large projects
  --dry-run           Analyze without writing any output files (.specbridge/)
  --summary-only      Show only a one-line coverage summary (CI-friendly)
  --help              Show this message and exit.
```

**New options (v1.0):**

| Option | Purpose |
|--------|---------|
| `--dry-run` | Skip writing HTML output to `.specbridge/trace.html` |
| `--summary-only` | Display a single CI-friendly line like `🟢 Coverage: 60.7% (259/427)` |

**Progress display:** Long-running analysis operations show a spinner via Rich progress bar.

**Examples:**

```
# Basic analysis
$ specbridge analyze

# JSON output for piping
$ specbridge analyze --format json | jq '.edges'

# Interactive HTML graph
$ specbridge analyze --format html

# Merge all matching adapters
$ specbridge analyze --merge

# CI-friendly one-line summary
$ specbridge analyze --summary-only
🟢 Coverage: 83.3% (10/12)

# Dry run (preview without saving HTML)
$ specbridge analyze --format html --dry-run
   📄 HTML output generated (--dry-run, not saved)
```

### 2.2 `impact`

Find which code/test files implement a specific specification. Supports **fuzzy spec ID resolution** — you don't need the full hierarchical ID.

```
Usage: specbridge impact [OPTIONS]

  Find what implements a given spec.

Options:
  -d, --dir TEXT      Project directory  [default: .]
  --spec-id TEXT      Spec ID or title to analyze (e.g. "1.1", "TraceNode")  [required]
  --format TEXT       Output format (text, json)  [default: text]
  -c, --call-graph    Include transitive (indirect) impact via call graph
  --max-depth INTEGER Max call-graph traversal depth  [default: 3]
  --help              Show this message and exit.
```

### 2.3 `coverage`

Display spec coverage statistics with color-coded indicators.

```
Usage: specbridge coverage [OPTIONS]

  Show spec coverage statistics.

Options:
  -d, --dir TEXT      Project directory  [default: .]
  --format TEXT       Output format (text, json)  [default: text]
  --help              Show this message and exit.
```

**Example output:**

```
$ specbridge coverage
📊 Spec Coverage  🟢
========================================
  Total specs:  12
  Covered:      10
  Orphan specs: 2
  Coverage:     83.3%
```

Coverage is color-coded: 🟢 ≥80%, 🟡 ≥50%, 🔴 <50%.

### 2.4 `snapshot`

Take a structural snapshot of the current project state for later drift comparison.

```
Usage: specbridge snapshot [OPTIONS]

  Take a structural snapshot of specs and code.

Options:
  -d, --dir TEXT      Project directory  [default: .]
  --config TEXT       Path to config file (default: auto-discover .specbridge.yaml / pyproject.toml)
  --reason TEXT       Description of why snapshot was taken
  --dry-run           Build snapshot without writing to disk
  --help              Show this message and exit.
```

**New options (v1.0):**

| Option | Purpose |
|--------|---------|
| `--config` | Use a custom config file path instead of auto-discovery |
| `--dry-run` | Build the snapshot in memory without saving to `.specbridge/snapshot.json` |

**Example:**

```
$ specbridge snapshot --reason "Before auth refactor"
📸 Snapshotting /Users/me/project ...
   Specs: 12 | Code files: 45
   Coverage: 83.3%
   Saved: .specbridge/snapshot.json
```

### 2.5 `drift`

Detect changes between a saved snapshot and the current project state.

```
Usage: specbridge drift [OPTIONS]

  Detect changes between snapshot and current state.

Options:
  -d, --dir TEXT          Project directory  [default: .]
  --config TEXT           Path to config file (default: auto-discover .specbridge.yaml / pyproject.toml)
  --snapshot TEXT         Path to snapshot file (default: .specbridge/snapshot.json)
  --gate                  Exit with code 1 if drift detected
  --format TEXT           Output format (text, json)  [default: text]
  --git-base TEXT         Git base ref to diff against (alternative to snapshot comparison)
  --help                  Show this message and exit.
```

### 2.6 `status` ✨ New in v1.0

Show a unified project state dashboard: configuration, snapshot status, current coverage, and drift check — all in one command.

```
Usage: specbridge status [OPTIONS]

  Show project state dashboard: config, snapshot, coverage, drift in one view.

Options:
  -d, --dir TEXT      Project directory  [default: .]
  --format TEXT       Output format (text, json)  [default: text]
  --help              Show this message and exit.
```

**Example output:**

```
$ specbridge status
📋 specbridge Status
==================================================

🔧 Configuration:
   spec_dirs:        ['docs', 'spec']
   source_dirs:      ['src', 'lib']
   exclude_dirs:     15 patterns
   min_confidence:   0.15

📸 Snapshot:
   Taken:           2026-07-27T10:30:00
   Reason:          Before auth refactor
   Coverage:        83.3%
   Specs (snap):    12
   Code files:      45

📊 Current Coverage:
   Coverage:        83.3%
   Total specs:     12
   Covered:         10
   Orphan specs:    2
   Orphan code:     1

✅ No drift detected — project state matches snapshot.
```

**Use cases:**

- **Quick health check** — one command to see if your project is in good shape
- **CI diagnostics** — `status --format json` for machine parsing
- **Before/after comparison** — run before and after changes to see impact

### 2.7 `validate-boundary`

Check that all code references stay within declared `_Boundary:_` markers in spec documents.

```
Usage: specbridge validate-boundary [OPTIONS]

  Validate that code refs stay within declared _Boundary:_ markers.

Options:
  -d, --dir TEXT      Project directory  [default: .]
  --help              Show this message and exit.
```

### 2.8 `config`

Display or validate the current specbridge configuration and its source.

```
Usage: specbridge config [OPTIONS]

  Show current specbridge configuration.

Options:
  -d, --dir TEXT      Project directory  [default: .]
  --config TEXT       Path to config file (default: auto-discover .specbridge.yaml / pyproject.toml)
  --yaml              Output config as YAML
  --validate          Validate configuration for correctness
  --help              Show this message and exit.
```

**New options (v1.0):**

| Option | Purpose |
|--------|---------|
| `--config` | Load and display/validate a specific config file |
| `--validate` | Check that spec directories and source directories exist, and that numeric values are in valid ranges |

**Validation checks:**

* `spec_dirs` and `source_dirs` are not empty
* Every directory in `spec_dirs` and `source_dirs` actually exists on disk
* `min_confidence` is between 0.0 and 1.0
* `max_output_nodes` is ≥ 1

**Example:**

```
$ specbridge config --validate
📋 specbridge config (.specbridge.yaml)
========================================
  ✅ Configuration is valid.

  spec_dirs:        ['docs', 'spec', 'specs']
  source_dirs:      ['src', 'lib', 'app']
  ...
```

### 2.9 `watch`

Watch the project directory for file changes and re-run analysis automatically. Requires `watchdog` package.

```
Usage: specbridge watch [OPTIONS]

  Watch project for changes and re-analyze automatically.

  Requires the optional 'watch' extra: pip install specbridge[watch]

Options:
  -d, --dir TEXT          Project directory  [default: .]
  --interval FLOAT        Debounce interval in seconds  [default: 2.0]
  --fast                  Skip function-level matching for faster analysis
  --help                  Show this message and exit.
```

### 2.10 `plugins`

List all installed adapter plugins (both built-in and third-party).

```
Usage: specbridge plugins [OPTIONS]

  List installed specbridge adapter plugins.

Options:
  --refresh       Re-scan installed packages for new plugins
  --help          Show this message and exit.
```

### 2.11 `call-graph`

Analyze transitive (indirect) impact for a spec via function-level call graph.

```
Usage: specbridge call-graph [OPTIONS]

  Build call graph and show transitive (indirect) impact for a spec.

Options:
  -d, --dir TEXT       Project directory  [default: .]
  --spec-id TEXT       Spec ID to analyze (e.g. 1.1)  [required]
  --max-depth INTEGER  Max call-graph traversal depth  [default: 3]
  --format TEXT        Output format (text, json)  [default: text]
  --help               Show this message and exit.
```

### 2.12 `serve`

Start an MCP server for AI agent integration.

```
Usage: specbridge serve [OPTIONS]

  Start MCP server for AI agent integration.

  Exposes specbridge tools (analyze, impact, coverage, drift, validate_boundary)
  via the Model Context Protocol. Requires: pip install specbridge[mcp]

Options:
  -d, --dir TEXT   Project directory  [default: .]
  --help           Show this message and exit.
```

### 2.13 `setup`

One‑command project bootstrap that creates config, installs hooks, deploys AI agent files, and takes the first snapshot.

```
Usage: specbridge setup [OPTIONS]

  One‑command setup: install hook, create config, deploy AGENTS.md.

Options:
  -d, --dir TEXT   Project directory to set up  [default: .]
  --ci             Also create GitHub Actions CI workflow
  --help           Show this message and exit.
```

## 3. Improved Error Messages (v1.0)

When specbridge cannot find a supported project structure, it now provides **actionable hints**:

```
❌ No recognized SSD framework found.
   Hints:
     • Ensure you are in a project with Markdown spec docs and source code.
     • Default spec dirs: docs/, spec/, specs/
     • Default source dirs: src/, lib/, app/
     • Create .specbridge.yaml to configure custom directories.
     • Run 'specbridge config' to see current discovered settings.
```

## 4. Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success (or no drift detected with `--gate`) |
| 1 | Drift detected (`drift --gate`), no adapter found, config validation failure, or runtime error |
