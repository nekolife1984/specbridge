# Testing Strategy

> **Date:** 2026-07-27
> **Version:** 1.0.0

## 1. Overview

The specbridge test suite uses `pytest` and covers all major modules with unit tests, integration tests, scale tests, edge-case tests, and concurrent access tests.

**Test location:** `tests/`

**Current count:** 220 tests (all passing)

## 2. Test Files

| File | Module Under Test | Focus |
|------|-------------------|-------|
| `test_ast.py` | `discovery/ast.py` | Tree-sitter AST extraction |
| `test_code_discovery.py` | `discovery/code.py` | Code candidate extraction (18 languages) |
| `test_extract.py` | `core/extract.py` | Tag extraction from spec and source files |
| `test_heuristic_adapter.py` | `adapters/heuristic.py`, `infer/` | Heuristic matching engine |
| `test_spectra_adapter.py` | `adapters/spectra.py` | Spectra framework adapter |
| `test_adapter_merge.py` | `adapters/_base.py` | Adapter detection, graph merging, spec:: ID normalization |
| `test_analyzers.py` | `analyzers/__init__.py` | Coverage, orphan detection |
| `test_drift.py` | `analyzers/drift.py` | Snapshot and drift detection |
| `test_import_graph.py` | `analyzers/graph.py` | Code dependency graph |
| `test_boundary.py` | `cli.py` | Boundary validation |
| `test_guard.py` | `guard.py` | Read-only write path enforcement |
| `test_config.py` | `config.py` | Config loading from YAML / pyproject.toml, edge-case configs |
| `test_plugin_discovery.py` | `adapters/_base.py` | Plugin discovery via entry points |
| `test_large_scale.py` ✨ | Full pipeline | Scale test with 50+ spec files and 200+ code files |
| `test_edge_cases.py` ✨ | Full pipeline | Unicode paths, spaces, binary files, empty files, large headings |
| `test_concurrent.py` ✨ | `analyzers/drift.py` | Concurrent snapshot save/load during analysis |

## 3. Test Categories

### 3.1 Unit Tests

Test individual functions and classes in isolation.

**Examples:**
- `discovery/spec.py`: `_split_sections()`, `_auto_id()`, `_clean_title()`
- `core/extract.py`: `extract_tags_from_file()` for various languages
- `infer/__init__.py`: `_score_edge()`, `_tokenize()`
- `config.py`: Loading from YAML, TOML, defaults

### 3.2 Integration Tests

Test how modules work together.

**Examples:**
- `build_heuristic_graph()` with real project directory structures
- `discover_specs()` + `discover_code()` + `build_heuristic_graph()` end-to-end
- Drift detection: snapshot → modify → drift → report
- Adapter merge: multiple adapters detect + analyze + merge

### 3.3 Boundary Tests

Test edge cases and error handling.

**Examples:**
- Empty project directories (no specs, no code)
- Spec files with no headings
- Source files with syntax errors
- Invalid YAML/TOML config files
- Files outside project root
- Unicode in file names and content
- `_Boundary:_` violations
- Paths with spaces, emoji, and 250+ character filenames ✨
- Binary files and empty files in spec directories ✨
- Config with wrong value types (safe_float/safe_int fallback) ✨

## 4. Test Fixtures (`tests/conftest.py`)

The test suite uses shared fixtures to reduce boilerplate.

**Typical fixtures:**
- `tmp_project`: Temporary directory structure with specs and code
- `empty_project`: Temporary directory with no specs or code
- `spectra_project`: Directory with `.spectra/trace-mapping.yaml`
- `sample_specs`: Pre-parsed `SpecCandidate[]` fixtures
- `sample_codes`: Pre-parsed `CodeCandidate[]` fixtures
- `snapshot_data`: Pre-built snapshot dictionary for drift tests

## 5. Running Tests

```bash
# Standard test run
pytest

# With coverage
pytest --cov=specbridge

# Specific test file
pytest tests/test_drift.py

# Verbose output
pytest -v

# Stop on first failure
pytest -x
```

## 6. Test Configuration

From `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers"
```

## 7. Linting and Type Checking

The project also enforces:

- **Ruff** — linting with rulesets: E, F, W, I, B, UP, C4, SIM
- **Mypy** — strict mode for type checking

Both run as part of CI and can be run locally:

```bash
ruff check .
mypy specbridge/
```

## 8. CI Integration

GitHub Actions (`/.github/workflows/ci.yml`):

```yaml
- run: pip install -e ".[dev,ast]"
- run: ruff check .
- run: mypy specbridge/
- run: pytest --cov=specbridge
```

## 9. Testing Principles

1. **Test the public API** — Prefer testing through public function signatures, not private methods
2. **Realistic fixtures** — Use minimal but representative project structures
3. **Deterministic** — Tests should produce the same result every time (no network calls)
4. **Isolated** — Each test creates and discards its own temporary directory
5. **Read-only** — No test writes to the real filesystem outside temp directories
6. **Coverage** — Aim for >80% coverage on core modules (core/, infer/, adapters/)
