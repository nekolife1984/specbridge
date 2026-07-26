# specbridge Roadmap

## v0.1 — Skeleton + spectra adapter

- [x] Repo scaffold (pyproject, README, gitignore)
- [x] CLI entry point with `click`
- [x] Core model: `TraceNode`, `TraceEdge`, `Evidence`
- [x] Tag extractor (multi-language: `#`, `//`, `<!-- -->`)
- [x] **spectra adapter** (read `.spectra/trace-mapping.yaml`, `@impl`, `<!-- @spec -->`, `@verifies`, `@satisfies`, `@design`, `@module`, `@feature`)
- [x] Commands: `analyze`, `impact`, `coverage`, `drift`
- [x] Outputs: text (default) + JSON
- [ ] Unit tests for extractor + adapter + analyzers
- [ ] Example project fixture

## v0.2 — More adapters

- [ ] **cc-sdd adapter** (Kiro-style spec format)
- [ ] **plain-markdown adapter** (parse heading hierarchy as implicit spec IDs)
- [ ] **OpenSpec adapter**
- [ ] Custom adapter via YAML schema

## v0.3 — AST + graph

- [ ] Python AST parser (functions, classes, imports)
- [ ] TypeScript/JavaScript AST parser (via tree-sitter)
- [ ] Go AST parser
- [ ] Rust AST parser
- [ ] CRG-style call-graph import for indirect impact
- [ ] `--graph` HTML output (interactive)

## v0.4 — Confidence + heuristics

- [ ] Directory → module inference (when no `@module` tag)
- [ ] Filename → spec reference heuristic (`docs/auth.md` ↔ `src/auth/*`)
- [ ] Test file → spec reference heuristic
- [ ] Confidence scoring per edge

## v0.5 — MCP server

- [ ] `specbridge serve --mcp` exposes analysis as MCP tools
- [ ] Tools: `get_impact`, `get_coverage`, `get_orphans`, `get_drift`

## v1.0 — Stabilization

- [x] **Plugin SDK for community adapters** (entry-point discovery, `specbridge plugins` CLI, example plugin)
- [ ] Comprehensive language coverage (17 languages)
- [ ] Stable core model API
- [ ] Performance: incremental analysis, caching
- [ ] Documentation site

## Non-goals

- ❌ Writing/modifying specs or code (read-only is the core principle)
- ❌ Replacing SSD frameworks — we complement them
- ❌ AI-driven spec generation (out of scope)
- ❌ Project-wide refactoring (out of scope)
