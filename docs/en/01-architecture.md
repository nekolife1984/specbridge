# Architecture Overview

> **Date:** 2026-07-26
> **Version:** 0.0.1.dev0

## 1. Purpose

specbridge is a **framework-agnostic, read-only traceability analyzer** that maps relationships between specifications and source code. It never modifies specs or code — all output goes to `.specbridge/`.

## 2. High-Level Architecture

```mermaid
flowchart TB
    subgraph UI["User Interfaces"]
        CLI["CLI (click)"]
        MCP["MCP Server (stdio MCP)"]
        SDK["Plugin SDK (entry_points)"]
    end

    subgraph OUT["Output Renderers"]
        TEXT["text.py"]
        JSON["json_out.py"]
        HTML["html.py (D3.js)"]
    end

    subgraph AL["Analysis Layer"]
        COV["Coverage<br/>(orphans, %)"]
        DRIFT["Drift<br/>(snapshot compare)"]
        DEP["Dep Graph<br/>(imports)"]
    end

    subgraph INF["Inference Engine (infer/)"]
        HEUR["build_heuristic_graph()<br/>4-signal scoring<br/>(dirname, filename, symbol, keyword)"]
    end

    subgraph DISC["Discovery Layer"]
        SD["Spec Discovery<br/>(markdown headings)"]
        CD["Code Discovery<br/>(18 languages, regex symbol)"]
        AST["AST<br/>(tree-sitter)"]
    end

    subgraph ADAPT["Adapter Layer"]
        HE["Heuristic<br/>(no-tag, primary)"]
        SP["Spectra<br/>(@impl, trace-map)"]
        PL["Plugins<br/>(entry points)"]
    end

    subgraph CORE["Core Model (core/)"]
        MODEL["TraceNode | TraceEdge<br/>TraceGraph | Evidence"]
        TAGEX["Tag Extractor<br/>(tokenize + regex multi-lang)"]
    end

    subgraph CFG["Config + Guard"]
        CONFIG["config.py"]
        GUARD["guard.py"]
    end

    CLI --> OUT
    MCP --> OUT
    SDK --> OUT

    OUT --> AL
    AL --> INF
    INF --> DISC
    DISC --> ADAPT
    ADAPT --> CORE
    CORE --> CFG
```

## 3. Module Responsibilities

| Module | Responsibility | Key Exports |
|--------|---------------|-------------|
| `core/` | Data model definitions, tag extraction from files | `TraceNode`, `TraceEdge`, `TraceGraph`, `Tag`, `extract_tags_from_dir()` |
| `adapters/` | Framework-specific project analysis, plugin discovery | `ProjectAdapter`, `detect_adapter()`, `merge_graphs()`, `register()` |
| `discovery/` | Parse specs (markdown) and code (multi-language) into candidates | `SpecCandidate`, `CodeCandidate`, `discover_specs()`, `discover_code()` |
| `infer/` | Heuristic matching between specs and code candidates | `build_heuristic_graph()` |
| `analyzers/` | Coverage stats, orphan detection, drift comparison, dependency graph | `coverage_summary()`, `find_orphan_*()`, `compute_drift()`, `build_code_dependency_graph()` |
| `outputs/` | Render `TraceGraph` as text, JSON, or interactive HTML | `render_text()`, `render_json()`, `render_html()` |
| `cli.py` | Click-based CLI entry point | `cli` group, 9 commands |
| `mcp_server.py` | MCP protocol server for AI agent integration | `create_mcp_server()`, `run_mcp_server()` |
| `config.py` | Project configuration from `.specbridge.yaml` / `pyproject.toml` | `SpecbridgeConfig.load()` |
| `guard.py` | Validate write paths stay inside `.specbridge/` | `validate_write_path()` |

## 4. Data Flow

### Read Path (primary flow)

```mermaid
flowchart TB
    PROJ["Project directory"]
    AD["Adapter Detection<br/>detect_adapter(root) → scores all adapters, picks best"]
    AN["Adapter.analyze(root)"]
    SPS["Spec Discovery<br/>discover_specs() → scan docs/ for *.md<br/>→ heading parse → SpecCandidate[]"]
    CD["Code Discovery<br/>discover_code() → scan src/ for 18 lang ext<br/>→ symbol/import extract → CodeCandidate[]"]
    INF["Inference Engine (if heuristic)<br/>build_heuristic_graph() → match spec ↔ code → TraceGraph<br/>or<br/>Tag Extraction (if spectra)<br/>extract_tags_from_dir() → @impl / <!-- @spec -->"]
    CLI2["CLI analyzes the TraceGraph<br/>for impact/coverage/etc."]

    PROJ --> AD
    AD --> AN
    AN --> SPS
    AN --> CD
    AN --> INF
    SPS --> INF
    CD --> INF
    INF --> CLI2
```

### Snapshot / Drift Flow

```mermaid
flowchart LR
    subgraph SNAP["specbridge snapshot"]
        A1["discover_specs() + discover_code()"]
        A2["build_heuristic_graph() + coverage_summary()"]
        A3["Hash each spec section body (SHA256[:16])"]
        A4["Hash each code file (SHA256[:16]) + each function body"]
        A5["Save to .specbridge/snapshot.json"]
        A1 --> A2 --> A3 --> A4 --> A5
    end

    subgraph DRI["specbridge drift"]
        B1["Load .specbridge/snapshot.json"]
        B2["Re-discover current state (specs + code)"]
        B3["Compare section by section (hash diff)"]
        B4["added / removed / changed / renamed specs"]
        B5["added / removed / changed code files"]
        B6["function body hash changes"]
        B7["orphan coverage delta"]
        B8["Return DriftReport (text / JSON / gate exit code)"]

        B1 --> B2 --> B3
        B3 --> B4
        B3 --> B5
        B3 --> B6
        B3 --> B7
        B4 --> B8
        B5 --> B8
        B6 --> B8
        B7 --> B8
    end
```

### Adapter Merge Flow

```mermaid
flowchart TB
    DA["detect_all(root) → all adapters with score > 0"]
    LOOP["For each: adapter.analyze(root) → TraceGraph"]
    MG["merge_graphs(graphs) → union of nodes + concatenate edges<br/>(later adapter's nodes overwrite same-ID nodes)"]
    OUT["Output merged TraceGraph"]

    DA --> LOOP --> MG --> OUT
```

## 5. Key Design Principles

| Principle | Implementation |
|-----------|---------------|
| **Read-only** | `guard.py` blocks any write outside `.specbridge/`. Snapshot/drift output only goes to `.specbridge/snapshot.json`. |
| **Framework-agnostic** | Adapter pattern with `ProjectAdapter` ABC. Built-in: heuristic + spectra. Extensible via `entry_points` plugin discovery. |
| **No-tag-first** | HeuristicAdapter is primary (always loaded first). Tag-based adapters are optional extras that add explicit edges on top. |
| **Multi-language** | 18 languages supported via regex symbol extraction. Python optionally uses tree-sitter AST for accuracy. |
| **Confidence scoring** | Every edge has `EdgeStrength` (EXPLICIT > INFERRED > WEAK) and source evidence. Users see *why* a relationship was inferred. |
| **Hash-based drift** | 3-layer hashing: file-level, function-level, section-level. Only changed items are reported (no full re-scan). |

## 6. Dependencies

### Runtime
- `click>=8.1` — CLI framework
- `rich>=13.0` — Terminal formatting
- `pyyaml>=6.0` — YAML config

### Optional
- `watchdog>=4.0` — `specbridge watch` command
- `mcp>=1.0` — MCP server
- `tree-sitter>=0.21`, `tree-sitter-python>=0.21` — AST-based Python analysis

### Dev
- `pytest`, `pytest-cov`, `mypy`, `ruff`, `types-PyYAML`

## 7. File Layout

```
specbridge/
├── __init__.py          # Version
├── cli.py               # CLI: 9 commands
├── config.py            # Config loading
├── guard.py             # Write path guard
├── mcp_server.py        # MCP protocol server
├── adapters/
│   ├── __init__.py      # Re-exports + eager import
│   ├── _base.py         # ABC + registry + plugin discovery + merge
│   ├── heuristic.py     # HeuristicAdapter
│   └── spectra.py       # SpectraAdapter
├── analyzers/
│   ├── __init__.py      # coverage_summary, orphan detection
│   ├── drift.py         # Snapshot + drift engine
│   └── graph.py         # Code dependency graph
├── core/
│   ├── __init__.py      # Data model (TraceNode, TraceEdge, TraceGraph, enums)
│   └── extract.py       # Tag extraction (tokenize + regex)
├── discovery/
│   ├── __init__.py
│   ├── ast.py           # Tree-sitter AST (Python)
│   ├── code.py          # Code discovery (18 lang)
│   └── spec.py          # Spec discovery (markdown headings)
├── infer/
│   └── __init__.py      # Heuristic graph builder
└── outputs/
    ├── __init__.py
    ├── html.py          # D3.js HTML output
    ├── json_out.py      # JSON output
    └── text.py          # Text output
tests/
├── __init__.py
├── conftest.py
├── test_adapter_merge.py
├── test_analyzers.py
├── test_ast.py
├── test_boundary.py
├── test_code_discovery.py
├── test_config.py
├── test_drift.py
├── test_extract.py
├── test_guard.py
├── test_heuristic_adapter.py
├── test_import_graph.py
├── test_plugin_discovery.py
└── test_spectra_adapter.py
```
