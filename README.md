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
- **v0.3**: AST parsers (TypeScript, Go, Rust), import-graph call analysis
- **v0.5**: incremental analysis, performance improvements
- **v1.0**: Stable API, comprehensive language coverage, documentation site

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

## Writing a Plugin

Extend specbridge with custom adapters packaged as Python packages.

### Step-by-step

1. **Create a package** with a `pyproject.toml`.
2. **Subclass `ProjectAdapter`** — implement `detect()` and `analyze()`:

   ```python
   from specbridge.adapters._base import ProjectAdapter, register
   from specbridge.core import TraceGraph

   @register
   class MyAdapter(ProjectAdapter):
       def detect(self, directory: str) -> float:
           return 0.8 if Path(directory, ".my-marker").exists() else 0.0

       def analyze(self, directory: str) -> TraceGraph:
           # … build and return a TraceGraph …
           return TraceGraph()
   ```

   The `@register` decorator is optional if you declare an entry point (see below).
   The `detect()` score should be **0.0–1.0**; the highest-scoring adapter wins.

3. **Declare the entry point** in `pyproject.toml`:

   ```toml
   [project.entry-points."specbridge.adapters"]
   my_adapter = "my_package.my_adapter:MyAdapter"
   ```

4. **Install** the plugin package in the same Python environment as specbridge:

   ```bash
   pip install -e /path/to/my-plugin
   ```

5. **Verify** it's loaded:

   ```bash
   specbridge plugins
   specbridge plugins --refresh   # if installed while specbridge was already running
   ```

### Best practices

- Keep `detect()` **fast** — it runs on every `analyze`/`impact`/`coverage` call.
- Use the `@register` decorator *or* the entry point, not both (entry point is preferred for distributable plugins).
- Handle parse errors gracefully — return an empty `TraceGraph()` rather than crashing.
- See [`examples/example-plugin/`](examples/example-plugin/) for a complete working example.

---

## License

MIT
