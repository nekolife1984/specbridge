# specbridge

> **Spec ↔ Code bridge.** Framework-agnostic, read-only traceability tool for spec-driven development.

`specbridge` is a **read-only traceability analyzer** that maps the relationships between your specifications and source code, regardless of which SSD framework (spectra, cc-sdd, OpenSpec, plain Markdown, etc.) you use. It never modifies your specs or code — it only writes to its own `.specbridge/` management directory.

## Why?

If you have a spec-driven development workflow but want to:

- **Audit** spec↔code coverage without committing to one SSD framework
- **Analyze impact** when a spec or code file changes
- **Detect drift** between specs and reality
- **Get a unified view** across heterogeneous projects (some with `<!-- @spec -->`, some without)
- **Keep your specs and code untouched** (no `@impl` tag injection unless you want it)

…then `specbridge` is for you.

## Position

```
┌──────────────────────────────────────────────┐
│  SSD Frameworks (spectra, cc-sdd, OpenSpec)  │
└──────────────┬───────────────────────────────┘
               │ read (input)
               ▼
┌──────────────────────────────────────────────┐
│  ★ specbridge (this tool) ★                  │
│  - framework-agnostic core model            │
│  - tag extractor + AST analyzer             │
│  - impact / coverage / drift detection      │
└──────────────┬───────────────────────────────┘
               │ text / JSON
               ▼
┌──────────────────────────────────────────────┐
│  CLI output / .specbridge/trace.json        │
└──────────────────────────────────────────────┘
```

## Quick start

```bash
# Analyze a project (read-only)
$ specbridge analyze --dir /path/to/project

# Impact analysis: which files implement spec 1.1?
$ specbridge impact --spec-id 1.1

# Coverage report: which specs have no code?
$ specbridge coverage

# Drift detection against a git base
$ specbridge drift --git-base main

# JSON output for piping
$ specbridge analyze --dir . --format json | jq '.edges'
```

## Core principles

1. **Read-only by default** — never modifies specs or code. All output goes to `.specbridge/`.
2. **Framework-agnostic** — supports multiple SSD formats via adapters. Custom adapters via YAML config.
3. **Multi-language** — Python, TypeScript, Go, Rust, Java, Ruby, C/C++, C#, Swift, Kotlin.
4. **Output flexibility** — text for humans, JSON for tooling.
5. **No magic** — every inferred relationship has a confidence score and source of evidence.

## Status

🚧 **Pre-alpha**. Initial scaffolding. See `ROADMAP.md` for planned milestones.

## License

MIT
