# Configuration & Read-Only Guard

> **Date:** 2026-07-26
> **Version:** 1.0.0

## 1. Overview

specbridge uses a layered configuration system and a strict read-only guard to ensure the tool never modifies specs or source code.

## 2. Configuration (`config.py`)

### 2.1 Config Sources (merged, not exclusive)

Configuration is loaded by **merging** multiple sources. Later sources override specific fields:

1. **Defaults** — Hardcoded defaults
2. **`pyproject.toml`** — `[tool.specbridge]` section (base settings)
3. **`.specbridge.yaml`** — Overrides specific fields (highest priority)

If both `pyproject.toml` and `.specbridge.yaml` exist, they are **merged** — unspecified fields are inherited from the upstream source. This allows e.g. `source_dirs` in `pyproject.toml` and `spec_dirs` in `.specbridge.yaml` to coexist.

```python
@dataclass
class SpecbridgeConfig:
    spec_dirs: list[str]        # Default: ["docs", "spec", "specs"]
    source_dirs: list[str]      # Default: ["src", "lib", "app"]
    exclude_dirs: set[str]      # Default: [".git", "node_modules", ".venv", ...]
    min_confidence: float       # Default: 0.15
    max_output_nodes: int       # Default: 20
```

### 2.2 YAML Config Format (`.specbridge.yaml`)

```yaml
# .specbridge.yaml
spec_dirs:
  - docs
  - spec
  - specs
source_dirs:
  - src
  - lib
  - app
exclude_dirs:
  - .git
  - node_modules
  - .venv
  - __pycache__
  - dist
  - build
  - .spectra
  - .specbridge
  - .artgraph
  - .trace
  - venv
  - env
  - .tox
  - .mypy_cache
  - .ruff_cache
  - .pytest_cache
  - .egg-info
  - site-packages
  - coverage
  - htmlcov
min_confidence: 0.15
max_output_nodes: 20
```

### 2.3 `pyproject.toml` Format

```toml
[tool.specbridge]
spec_dirs = ["docs", "spec", "specs"]
source_dirs = ["src", "lib", "app"]
min_confidence = 0.15
max_output_nodes = 20
```

### 2.4 Config Loading Logic

```python
@classmethod
def load(cls, project_dir: str | Path) -> SpecbridgeConfig:
    root = Path(project_dir).resolve()

    # 1. Try .specbridge.yaml
    yaml_path = root / ".specbridge.yaml"
    if yaml_path.exists():
        return cls._from_yaml(yaml_path)

    # 2. Try pyproject.toml [tool.specbridge]
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        return cls._from_pyproject(pyproject)

    # 3. Defaults
    return cls()
```

### 2.5 Configuration Display

The `specbridge config` command shows the resolved configuration and its source:

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

## 3. Read-Only Guard (`guard.py`)

### 3.1 Purpose

specbridge is a **read-only** tool — it never modifies specs or source code. The guard enforces this by validating every write path.

### 3.2 Allowed Write Directory

The only directory specbridge can write to is `.specbridge/` within the project root:

```python
ALLOWED_WRITE_DIR = ".specbridge"
```

### 3.3 Validation Logic

```python
def validate_write_path(target_path, project_root) -> Path:
    """Validate that target_path is inside .specbridge/.

    Returns the resolved path if valid.
    Raises PermissionError if blocked.
    """
    root = Path(project_root).resolve()
    target = Path(target_path).resolve()
    allowed = root / ALLOWED_WRITE_DIR

    # 1. Inside .specbridge/ → OK
    try:
        target.relative_to(allowed)
        return target
    except ValueError:
        pass

    # 2. Inside spec directories (docs/, spec/, specs/) → BLOCK
    spec_dirs = {root / d for d in ["docs", "spec", "specs"]}
    for forbidden in spec_dirs:
        try:
            target.relative_to(forbidden)
            raise PermissionError("...")
        except ValueError:
            continue

    # 3. Inside source directories (src/, lib/, app/, tests/) → BLOCK
    source_dirs = {root / d for d in ["src", "lib", "app", "tests"]}
    for forbidden in source_dirs:
        try:
            target.relative_to(forbidden)
            raise PermissionError("...")
        except ValueError:
            continue

    # 4. Outside project root → BLOCK
    try:
        target.relative_to(root)
    except ValueError:
        raise PermissionError("...")

    # 5. Inside project root but not .specbridge/ → BLOCK
    raise PermissionError("...")
```

### 3.4 Protected Directories

| Directory | Reason |
|-----------|--------|
| `docs/`, `spec/`, `specs/` | Spec documents — read-only |
| `src/`, `lib/`, `app/` | Source code — read-only |
| `tests/` | Test code — read-only |
| `.specbridge/` | **Only** writable directory |
| Outside project root | Prevent accidental writes |

### 3.5 Error Messages

```
Write blocked: /Users/me/project/src/auth/login.py is inside 'src/' which
is a protected spec or source directory. specbridge is read-only and only
writes to .specbridge/.

Write blocked: /Users/me/project/docs/auth/auth.md is inside 'docs/' which
is a protected spec or source directory. specbridge is read-only and only
writes to .specbridge/.

Write blocked: /tmp/whatever is outside the project root /Users/me/project.
specbridge only writes to .specbridge/ within the project.
```

### 3.6 Where the Guard is Used

```python
# In drift.py save_snapshot():
from specbridge.guard import validate_write_path
validate_write_path(path, root)
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(...)

# In cli.py HTML output:
out_path = root / ".specbridge" / "trace.html"
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(html, encoding="utf-8")
```

## 4. Summary

The combination of layered configuration and strict write guard ensures:

- **No accidental writes** to specs or source code
- **Clear error messages** when a write would violate the read-only policy
- **Flexible configuration** via YAML or pyproject.toml with sensible defaults
- **Easy debugging** via `specbridge config` to inspect resolved settings
