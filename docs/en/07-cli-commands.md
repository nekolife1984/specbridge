# CLI Commands Reference

> **Date:** 2026-07-26
> **Version:** 0.0.1.dev0

## 1. Overview

specbridge provides a Click-based CLI with 9 commands for traceability analysis, drift detection, and project management.

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
  validate-boundary  Validate that code refs stay within declared _Boundary:_ markers.
  config             Show current specbridge configuration.
  watch              Watch project for changes and re-analyze automatically.
  plugins            List installed specbridge adapter plugins.
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
  --help              Show this message and exit.
```

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

# Show only top 5 per category
$ specbridge analyze --top 5

# Include code dependency graph
$ specbridge analyze --deps
```

**Behavior:**

1. Detects the best adapter for the project (or all adapters with `--merge`)
2. Runs the adapter's `analyze()` to build a TraceGraph
3. Optionally builds code dependency graph (`--deps`)
4. Renders output in the selected format

### 2.2 `impact`

Find which code/test files implement a specific specification.

```
Usage: specbridge impact [OPTIONS]

  Find what implements a given spec.

Options:
  -d, --dir TEXT      Project directory  [default: .]
  --spec-id TEXT      Spec ID to analyze (e.g. 1.1)  [required]
  --format TEXT       Output format (text, json)  [default: text]
  --help              Show this message and exit.
```

**Examples:**

```
$ specbridge impact --spec-id 1.1
📄 auth.auth.1.1: User Authentication
   Confidence: 0.95
   Source: docs/auth/auth.md
  [EXPLICIT] src/auth/login.py  (implements)
            ∵ tag:impl: AUTH-1
  [EXPLICIT] tests/test_auth.py  (verifies)
            ∵ tag:verifies: 1.1

$ specbridge impact --spec-id 1.1 --format json
```

### 2.3 `coverage`

Display spec coverage statistics.

```
Usage: specbridge coverage [OPTIONS]

  Show spec coverage statistics.

Options:
  -d, --dir TEXT      Project directory  [default: .]
  --format TEXT       Output format (text, json)  [default: text]
  --help              Show this message and exit.
```

**Examples:**

```
$ specbridge coverage
📊 Spec Coverage
========================================
  Total specs:  12
  Covered:      10
  Orphan specs: 2
  Coverage:     83.3%

🟡 Orphan specs (no code ref):
   - docs.auth.auth.3.1
   - docs.auth.auth.4.0
```

### 2.4 `snapshot`

Take a structural snapshot of the current project state for later drift comparison.

```
Usage: specbridge snapshot [OPTIONS]

  Take a structural snapshot of specs and code.

Options:
  -d, --dir TEXT      Project directory  [default: .]
  --reason TEXT       Description of why snapshot was taken
  --help              Show this message and exit.
```

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
  --snapshot TEXT         Path to snapshot file (default: .specbridge/snapshot.json)
  --gate                  Exit with code 1 if drift detected
  --format TEXT           Output format (text, json)  [default: text]
  --git-base TEXT         Git base ref to diff against (alternative to snapshot comparison)
  --help                  Show this message and exit.
```

**Examples:**

```
# Compare against saved snapshot
$ specbridge drift

# JSON report
$ specbridge drift --format json

# CI gate (exit 1 if drift)
$ specbridge drift --gate

# Git-based comparison (no snapshot needed)
$ specbridge drift --git-base main

# Use a specific snapshot file
$ specbridge drift --snapshot ./backups/snapshot-2026-01.json
```

### 2.6 `validate-boundary`

Check that all code references stay within declared `_Boundary:_` markers in spec documents.

```
Usage: specbridge validate-boundary [OPTIONS]

  Validate that code refs stay within declared _Boundary:_ markers.

Options:
  -d, --dir TEXT      Project directory  [default: .]
  --help              Show this message and exit.
```

**Example:**

```
$ specbridge validate-boundary
⚠️  2 boundary violation(s):
  auth.auth.1.1 in docs/auth/auth.md
    declares boundaries: src/auth/
    but tests/test_external_api.py is outside

Tip: Add _Boundary:_ src/path/ or move the @impl to a file inside the boundary.
```

### 2.7 `config`

Display the current specbridge configuration and its source.

```
Usage: specbridge config [OPTIONS]

  Show current specbridge configuration.

Options:
  -d, --dir TEXT      Project directory  [default: .]
  --yaml              Output config as YAML
  --help              Show this message and exit.
```

**Example:**

```
$ specbridge config
📋 specbridge config (.specbridge.yaml)
========================================
  spec_dirs:        ['docs', 'spec', 'specs']
  source_dirs:      ['src', 'lib', 'app']
  exclude_dirs:     15 patterns
  min_confidence:   0.15
  max_output_nodes: 20
```

### 2.8 `watch`

Watch the project directory for file changes and re-run analysis automatically. Requires `watchdog` package.

```
Usage: specbridge watch [OPTIONS]

  Watch project for changes and re-analyze automatically.

  Requires the optional 'watch' extra: pip install specbridge[watch]

Options:
  -d, --dir TEXT          Project directory  [default: .]
  --interval FLOAT        Debounce interval in seconds  [default: 2.0]
  --help                  Show this message and exit.
```

**Behavior:**

- Uses `watchdog.observers.Observer` for file system monitoring
- Debounces rapid changes (default: 2s interval)
- Ignores `.specbridge/` directory changes to avoid re-trigger loops
- Runs full analysis on each detected change
- Clears terminal and re-renders output on each trigger

### 2.9 `plugins`

List all installed adapter plugins (both built-in and third-party).

```
Usage: specbridge plugins [OPTIONS]

  List installed specbridge adapter plugins.

Options:
  --refresh       Re-scan installed packages for new plugins
  --help          Show this message and exit.
```

**Example:**

```
$ specbridge plugins
🔌 Built-in adapters:
   HeuristicAdapter
   SpectraAdapter

🔌 Plugin adapters (0):
   (none)
```

## 3. Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success (or no drift detected with `--gate`) |
| 1 | Drift detected (`drift --gate`), no adapter found, or runtime error |

## 4. Plugin SDK (`specbridge plugins`)

The `plugins` command discovers adapters registered via Python entry points:

```
$ pip install my-specbridge-plugin
$ specbridge plugins --refresh
🔌 Plugin adapters (1):
   MyAdapter (from my-specbridge-plugin)
```

## 5. Help

Every command supports `--help`:

```
$ specbridge analyze --help
$ specbridge drift --help
```

The top-level help shows all available commands:

```
$ specbridge --help
```
