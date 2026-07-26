# specbridge

> **Spec ↔ Code bridge.** Framework-agnostic, read-only traceability tool for spec-driven development.

`specbridge` is a **read-only traceability analyzer** that maps the relationships between your specifications and source code. It never modifies your specs or code — it only writes to its own `.specbridge/` management directory.

## Why?

If you have a spec-driven development workflow but want to:

- **Audit** spec↔code coverage without committing to one SSD framework
- **Analyze impact** when a spec or code file changes
- **Detect drift** between specs and reality
- **Validate boundaries** (code refs must stay within declared paths)
- **Get a unified view** across heterogeneous projects (merge multiple adapters)
- **Keep your specs and code untouched** (read-only is the core principle)

…then `specbridge` is for you.

## Quick start

```bash
# Analyze a project (spectra framework + heuristic fallback)
$ specbridge analyze --dir /path/to/project

# Merge results from all matching adapters
$ specbridge analyze --dir /path/to/project --merge

# Impact analysis: which files implement spec 1.1?
$ specbridge impact --spec-id 1.1

# Coverage report: which specs have no code?
$ specbridge coverage

# Take a structural snapshot of the current state
$ specbridge snapshot

# Drift detection against a snapshot
$ specbridge drift

# Drift detection against a git base
$ specbridge drift --git-base main

# Validate that code refs stay within declared _Boundary:_ markers
$ specbridge validate-boundary

# JSON output for piping
$ specbridge analyze --dir . --format json | jq '.edges'
```

## Core principles

1. **Read-only by default** — never modifies specs or code. All output goes to `.specbridge/`. Protected by `validate_write_path`.
2. **Framework-agnostic** — supports multiple SSD formats via adapters (spectra, heuristic).
3. **Multi-language** — Python, TypeScript, Go, Rust, Java, Ruby, C/C++, C#, Swift, Kotlin, Dart, PHP.
4. **Output flexibility** — text for humans, JSON for tooling.
5. **No magic** — every inferred relationship has a confidence score and source of evidence.
6. **Boundary validation** — declare `_Boundary:_ src/path/` in spec docs; `specbridge validate-boundary` checks code refs stay within them.

## Status

**v0.1 — Skeleton + spectra adapter + heuristic bridge.**

### Implemented

| Feature | CLI | Status |
|---------|-----|--------|
| Core model (TraceNode, TraceEdge, Evidence) | — | ✅ |
| Tag extractor (multi-language: `#`, `//`, `<!-- -->`) | — | ✅ |
| spectra adapter (`@impl`, `<!-- @spec -->`, `@verifies`, `@module`, `@feature`, `@satisfies`) | `analyze` | ✅ |
| Heuristic adapter (name-based matching, no tags required) | `analyze` | ✅ |
| Adapter merge mode (combine all adapters) | `analyze --merge` | ✅ |
| Impact analysis | `impact` | ✅ |
| Coverage report | `coverage` | ✅ |
| Structural snapshot | `snapshot` | ✅ |
| Drift detection (spec body/code func/file hash) | `drift` | ✅ |
| Drift gate (CI-friendly exit code) | `drift --gate` | ✅ |
| Git-based drift | `drift --git-base` | ✅ |
| `_Boundary:_` parsing | — | ✅ |
| Boundary validation | `validate-boundary` | ✅ |
| Read-only write guard (`.specbridge/` only) | — | ✅ |
| JSON output | `--format json` | ✅ |
| Multi-language code discovery | — | ✅ |
| Snapshot I/O (`.specbridge/snapshot.json`) | — | ✅ |

### Planned

See [ROADMAP.md](ROADMAP.md) for:
- **v0.2**: cc-sdd adapter, plain-markdown adapter, custom adapter via YAML
- **v0.3**: AST parsers (Python, TypeScript, Go), HTML graph output
- **v0.5**: MCP server for AI agent integration
- **v1.0**: Plugin SDK, incremental analysis, documentation site

## Architecture

```text
┌──────────────────────────────────────────────┐
│  SSD Frameworks (spectra, heuristic, …)      │
└──────────────┬───────────────────────────────┘
               │ read (input)
               ▼
┌──────────────────────────────────────────────┐
│  ★ specbridge (this tool) ★                  │
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

## License

MIT
