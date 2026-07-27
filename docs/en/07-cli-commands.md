# CLI Commands Reference

> **Date:** 2026-07-27
> **Version:** 1.0.0

## 1. Overview

specbridge provides a Click-based CLI with **17 commands** for traceability analysis, drift detection, and project management.

```
Usage: specbridge [OPTIONS] COMMAND [ARGS]...

  Spec ↔ Code bridge: read-only traceability analyzer for SSD.

Options:
  --version  Show the version and exit.
  --help     Show this message and exit.

Commands:
  analyze            Analyze a project and build a trace graph.
  call-graph         Build call graph and show transitive (indirect) impact for a spec.
  config             Show / validate current specbridge configuration.
  coverage           Show spec coverage statistics.
  diff               Compare two snapshot files and show a summary diff.
  drift              Detect changes between snapshot and current state.
  impact             Find what implements a given spec.
  init               Interactive config generator (.specbridge.yaml).
  plugins            List installed specbridge adapter plugins.
  serve              Start MCP server for AI agent integration.
  setup              One‑command project setup (config, hook, AGENTS.md, snapshot).
  shell-completion   Generate or install shell completion scripts.
  snapshot           Take a structural snapshot of specs and code.
  status             Show project state dashboard (config, snapshot, coverage, drift).
  suggest            Suggest code files for uncovered specs.
  validate-boundary  Validate that code refs stay within declared _Boundary:_ markers.
  watch              Watch project for changes and re-analyze automatically.
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
  --fast              Skip function-level matching [default: on, use --func-match to enable]
  --func-match        Enable function-level matching (may be slow on large projects)
  --dry-run           Analyze without writing any output files (.specbridge/)
  --summary-only      Show only a one-line coverage summary (CI-friendly)
  --help              Show this message and exit.
```

**New options (v1.1):**

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

Find which code/test files implement a specific specification, **or** find which specs are affected by changes to a file. Supports two modes:

- **Forward impact** (`--spec-id`): Spec → implementing code files
- **Reverse impact** (`--file`): Code file → affected specs (new in v1.1)

```
Usage: specbridge impact [OPTIONS]

  Analyze impact between specs and code.

Options:
  -d, --dir TEXT      Project directory  [default: .]
  --spec-id TEXT      Spec ID to analyze (e.g. "1.1")
  --file TEXT         File path for reverse impact: find specs affected by
                      this file
  --format TEXT       Output format (text, json)  [default: text]
  -c, --call-graph    Include transitive (indirect) impact via call graph
  --max-depth INTEGER Max call-graph traversal depth  [default: 3]
  --help              Show this message and exit.
```

`--spec-id` and `--file` are mutually exclusive — exactly one must be provided.

**Forward impact examples:**

```bash
# Find what implements spec 1.1
$ specbridge impact --spec-id 1.1

# With transitive (indirect) impact via call graph
$ specbridge impact --spec-id 1.1 --call-graph --max-depth 3
```

**Reverse impact examples (v1.1+):**

```bash
# Find which specs are affected by changes to a file
$ specbridge impact --file src/auth/login.py

# With transitive impact
$ specbridge impact --file specbridge/cli.py --call-graph
```

### 2.3 `coverage`

Display spec coverage statistics with color-coded indicators.

```
Usage: specbridge coverage [OPTIONS]

  Show spec coverage statistics.

Options:
  -d, --dir TEXT          Project directory  [default: .]
  --format TEXT           Output format (text, json)  [default: text]
  --gate                  Exit with code 1 if coverage is below min_coverage
                          threshold
  --min-coverage FLOAT    Override min_coverage threshold for --gate
                          (default: from config)
  --help                  Show this message and exit.
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

**Coverage gate (CI mode):**

```
$ specbridge coverage --gate
✅ Coverage gate passed: 83.3% >= 50.0% (10/12 specs covered)
$ echo $?
0

$ specbridge coverage --gate --min-coverage 90
❌ Coverage gate FAILED: 83.3% < 90.0% (10/12 specs covered)
$ echo $?
1
```

The `--gate` flag turns `specbridge coverage` into a CI gate: it exits with code 0 if coverage meets the threshold, or 1 if below. Use `--min-coverage` to override the threshold from config for a single run. Combined with `drift --gate`, this provides a complete pre-commit / CI quality gate.

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

**HTML coverage report (v1.1+):**

```
$ specbridge analyze --merge --report
```

Generates a rich self-contained HTML coverage report at `.specbridge/report.html` with:
- Coverage progress bar with pass/fail gate indicator
- Tabbed view: All / Covered / Partial (code only) / Orphan (uncovered)
- Search/filter by spec ID or title
- Color-coded rows (green/yellow/red)
- Orphan code files list
- Interactive JavaScript filtering (no build step required)

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

### 2.7 `shell-completion` ✨ New

Generate or install shell completion scripts for Bash, Zsh, and Fish.

```
Usage: specbridge shell-completion [OPTIONS]

  Generate or install shell completion scripts.

  specbridge uses Click's built-in shell completion.  After installing,
  press TAB to auto-complete commands, options, and arguments.

  Quick start:   specbridge shell-completion --install

  Or manually:   eval "$(specbridge shell-completion --show --shell bash)"

Options:
  --shell [bash|zsh|fish]  Target shell (default: auto-detect from SHELL env)
  --install                Install completion permanently (appends to shell rc
                           file)
  --show                   Print the completion script to stdout (for manual
                           install)
  --help                   Show this message and exit.
```

**Examples:**

```bash
# Auto-detect shell and show instructions
$ specbridge shell-completion

# Install permanently
$ specbridge shell-completion --install

# Manual setup for a specific shell
$ eval "$(specbridge shell-completion --show --shell zsh)"
```

**How it works:**

specbridge uses Click 8.1+'s built-in shell completion via the `_SPECBRIDGE_COMPLETE` environment variable. When this variable is set and the CLI is invoked, Click outputs the completion script instead of running the command.

**Shell support:**

| Shell | RC File | Completion Variable |
|-------|---------|-------------------|
| Bash | `~/.bashrc` | `_SPECBRIDGE_COMPLETE=bash_source` |
| Zsh | `~/.zshrc` | `_SPECBRIDGE_COMPLETE=zsh_source` |
| Fish | `~/.config/fish/config.fish` | `_SPECBRIDGE_COMPLETE=fish_source` |

After installation, you can tab-complete commands, options, and arguments:

```
$ specbridge [TAB]
analyze       call-graph    config        coverage      drift
impact        plugins       serve         setup         shell-completion
snapshot      status        validate-boundary  watch

$ specbridge analyze --[TAB]
--call-graph  --config    --deps      --dir       --dry-run
--fast        --format    --func-match  --help      --merge     --summary-only
--top
```

### 2.8 `validate-boundary`

Check that all code references stay within declared `_Boundary:_` markers in spec documents.

```
Usage: specbridge validate-boundary [OPTIONS]

  Validate that code refs stay within declared _Boundary:_ markers.

Options:
  -d, --dir TEXT      Project directory  [default: .]
  --help              Show this message and exit.
```

### 2.9 `config`

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

### 2.10 `watch`

Watch the project directory for file changes and re-run analysis automatically. Requires `watchdog` package.

```
Usage: specbridge watch [OPTIONS]

  Watch project for changes and re-analyze automatically.

  Requires the optional 'watch' extra: pip install specbridge[watch]

Options:
  -d, --dir TEXT          Project directory  [default: .]
  --interval FLOAT        Debounce interval in seconds  [default: 2.0]
  --fast                  Skip function-level matching [default: on]
  --func-match            Enable function-level matching (may be slow on large projects)
  --help                  Show this message and exit.
```

### 2.11 `plugins`

List all installed adapter plugins (both built-in and third-party).

```
Usage: specbridge plugins [OPTIONS]

  List installed specbridge adapter plugins.

Options:
  --refresh       Re-scan installed packages for new plugins
  --help          Show this message and exit.
```

### 2.12 `call-graph`

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

### 2.13 `serve`

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

### 2.14 `setup`

One‑command project bootstrap that creates config, installs hooks, deploys AI agent files, and takes the first snapshot.

```
Usage: specbridge setup [OPTIONS]

  One‑command setup: install hook, create config, deploy AGENTS.md.

Options:
  -d, --dir TEXT   Project directory to set up  [default: .]
  --ci             Also create GitHub Actions CI workflow
  --help           Show this message and exit.
```

### 2.15 `init` ✨ New

Interactive config generator that creates `.specbridge.yaml` step by step.

```
Usage: specbridge init [OPTIONS]

  Interactive config generator — create .specbridge.yaml step by step.

  Scans the project for spec directories (docs/, spec/, specs/, ...) and
  source directories (src/, lib/, app/, tests/, ...), then guides you
  through selecting which to include and writing the config file.

Options:
  -d, --dir TEXT   Project directory to initialize  [default: .]
  --force          Overwrite existing .specbridge.yaml without confirmation
  --help           Show this message and exit.
```

**Interactive flow:**

```
$ specbridge init

🔍 Scanning /home/user/myproject ...

📁 Spec directories found:
    docs/  (12 .md files)
    specs/  (3 .md files)
   Include all of them? [Y/n] y

🔧 Source directories found:
    src/  (45 source files)
    lib/  (12 source files)
    tests/  (18 source files)
   Include all of them? [Y/n] y

📝 Config preview:
    spec_dirs:        ['docs', 'specs']
    source_dirs:      ['src', 'lib', 'tests']
    min_confidence:   0.15
    max_output_nodes: 20

   Write .specbridge.yaml? [Y/n] y

✅ .specbridge.yaml created in /home/user/myproject

💡 Next steps:
   1. Run 'specbridge setup' to install pre-commit hook and AGENTS.md
   2. Run 'specbridge snapshot' to create the initial baseline
   3. Run 'specbridge analyze' to see your trace graph
```

### 2.16 `diff` ✨ New

Compare two snapshot files and show a summary diff — like `git diff --stat` for specs.

```
Usage: specbridge diff [OPTIONS] BEFORE AFTER

  Compare two snapshot files and show a summary diff.

  BEFORE and AFTER are paths to .specbridge/snapshot.json files.

Options:
  --format [text|json]  Output format  [default: text]
  --help                Show this message and exit.
```

**Example:**

```
$ specbridge diff snapshots/baseline.json snapshots/current.json
📊 specbridge snapshot diff
==================================================

📊 Coverage trend:
   Before:  65.2% (28/43)
   After:   78.7% (37/47)
   Change:  +13.5%

📄 Spec changes:
   + 3 added
       + "Rate Limiting"
       + "OAuth Flow"
   - 1 removed
   ~ 2 titles changed

📁 Code changes:
   + 12 files added
   - 1 file removed
   ⚡ 3 functions changed

🟡 Orphan changes:
   Before:  12 orphan specs
   After:   5 orphan specs
   Resolved: 7 orphan specs covered
```

### 2.17 `suggest` ✨ New

Suggest code files that may implement uncovered (orphan) specs.

```
Usage: specbridge suggest [OPTIONS]

  Suggest code files that may implement uncovered specs.

Options:
  -d, --dir TEXT        Project directory  [default: .]
  --top INTEGER         Number of suggestions to show  [default: 5]
  --format [text|json]  Output format  [default: text]
  --threshold FLOAT     Minimum similarity score (0.0-1.0)  [default: 0.1]
  --help                Show this message and exit.
```

**Example:**

```
$ specbridge suggest
📋 specbridge suggest — 3 orphan spec(s)
==================================================

1. docs.api.2.3 "Rate Limiting" (docs/api/api.md)
   → 3 candidate(s), top 2:
     📁 src/api/middleware/rate_limiter.py  (score: 0.45)
     🔤 src/api/handler.py                  (score: 0.28)

2. docs.auth.1.2 "OAuth Flow" (docs/auth/auth.md)
   → 2 candidate(s), top 2:
     📁 src/auth/oauth.py  (score: 0.52)
     🔧 src/auth/oauth.py::handle_oauth     (score: 0.38)

3. docs.db.3.1 "Migration Strategy" (docs/db/db.md)
   → No matching code files found (threshold: 0.1)
     💡 Check that source_dirs in .specbridge.yaml covers the implementation
```

### 2.18 `session-check` ✨ New in v1.1

Run session-end integrity checks before closing a session. Combines drift detection, coverage check, orphan detection, git status, and custom hooks in one command.

```
Usage: specbridge session-check [OPTIONS]

  Run session-end integrity checks before closing a session.

Options:
  -d, --dir TEXT      Project directory  [default: .]
  --config TEXT       Path to config file
  --skip-git          Skip uncommitted changes check
  --skip-hooks        Skip custom session_check hooks from config
  --help              Show this message and exit.
```

**Example output:**

```
$ specbridge session-check
📋 specbridge Session Check — /Users/me/project
==================================================
  ✅ Drift: no drift detected
  ✅ Coverage: 83.3% (10/12)
  ✅ Orphan specs: none
  ✅ Orphan code: none
  ✅ Git: working tree is clean
  📭 Hooks: none configured
==================================================
✅ All checks passed — session state is clean.
```

**Exit codes:** 0 = all clean, 1 = warnings (review suggested), 2 = blockers (must fix).

**Custom hooks** can be configured in `.specbridge.yaml`:

```yaml
session_check:
  hooks:
    - command: "bash scripts/check-doc-sync.sh"
      description: "EN↔JA documentation sync check"
      optional: true
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
| 0 | Success (or no drift detected with `--gate`, coverage >= threshold with `coverage --gate`) |
| 1 | Drift detected (`drift --gate`), coverage below threshold (`coverage --gate`), no adapter found, config validation failure, or runtime error |
