# specbridge Roadmap

> **Legend:** [x] done · [~] partial · [ ] not started

---

## v0.1 — Foundation (complete)

- [x] Repo scaffold (pyproject, README, gitignore)
- [x] CLI entry point with `click`
- [x] Core model: `TraceNode`, `TraceEdge`, `Evidence`
- [x] Tag extractor (multi-language: `#`, `//`, `<!-- -->`)
- [x] **spectra adapter** (read `.spectra/trace-mapping.yaml`, `@impl`, `<!-- @spec -->`, `@verifies`, `@satisfies`, `@design`, `@module`, `@feature`)
- [x] Commands: `analyze`, `impact`, `coverage`, `drift`, `snapshot`
- [x] Outputs: text (default) + JSON + HTML (interactive D3.js)
- [x] Unit tests — 169 tests covering extractor, adapters, analyzers, drift, boundaries, plugins, guard
- [x] Example project fixture (`examples/todo-app/`)
- [x] Plugin SDK (entry-point discovery, `plugins` CLI, `examples/example-plugin/`)

## v0.2 — More adapters

- [x] **Heuristic adapter** (primary, no tags required) — filename/dirname/test-name matching across `docs/` + `src/`
- [ ] **cc-sdd adapter** (Kiro-style spec format)
- [ ] **OpenSpec adapter**
- [ ] Custom adapter via YAML schema

## v0.3 — AST + graph

- [x] Python code discovery (functions, classes, imports, body hashes)
- [x] Code dependency graph (`build_code_dependency_graph` via imports)
- [x] Function-level traceability (`_resolve_import` + stem matching)
- [x] HTML interactive graph output (`outputs/html.py` — D3.js force-directed layout)
- [x] **TypeScript/JavaScript AST parser** (via tree-sitter)
- [x] **Go AST parser**
- [x] **Rust AST parser**
- [x] **CRG-style call-graph import for indirect impact**

## v0.4 — Confidence + heuristics (complete)

- [x] Directory → module inference (when no `@module` tag)
- [x] Filename → spec reference heuristic (`docs/auth.md` ↔ `src/auth/*`)
- [x] Test file → spec reference heuristic
- [x] Confidence scoring per edge (4 strategies, configurable)

## v0.5 — MCP server

- [x] `specbridge serve` — exposes analysis as MCP tools
- [x] Tools: `analyze`, `get_impact`, `get_coverage`, `get_drift`, `validate_boundary`
- [ ] `get_orphans` MCP tool

## v0.6 — Validation & DX

- [x] **Boundary validation** — `validate-boundary` CLI + MCP tool
- [x] **pre-commit hook** — drift gate on `git commit` (works with any AI agent)
- [x] **CI gate** — GitHub Actions workflow (`ci` + `trace-gate`)
- [x] **Bilingual docs** — EN + JA (11 chapters each, `docs/en/` + `docs/ja/`)
- [x] **Watch mode** — `specbridge watch` for live file monitoring
- [x] **Config** — `.specbridge.yaml` support with `config` CLI

## v0.7 — Project Setup & Onboarding

- [x] **One‑command setup script** (`scripts/setup.sh`) — creates `.specbridge.yaml`, installs hook, deploys AGENTS.md + Hermes skill, takes snapshot
- [x] **`specbridge setup` CLI command** — wraps setup script for post‑install convenience
- [x] **`AGENTS.md`** — universal AI agent workflow guide (read by Hermes, OpenCode, Claude Code, Cursor, Codex)

## v1.0 — Stabilization

- [x] Plugin SDK for community adapters (entry-point discovery, `plugins` CLI, example plugin)
- [ ] **Comprehensive language coverage** (17 languages)
- [ ] **Stable core model API** (semver 1.0.0)
- [ ] **Performance**: incremental analysis, caching
- [ ] **Documentation site** (GitHub Pages or similar)

## Non-goals

- ❌ Writing/modifying specs or code (read-only is the core principle)
- ❌ Replacing SSD frameworks — we complement them
- ❌ AI-driven spec generation (out of scope)
- ❌ Project-wide refactoring (out of scope)
