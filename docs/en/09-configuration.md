# Configuration & Read-Only Guard

> **Date:** 2026-07-27
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
    min_coverage: float         # Default: 50.0 (for coverage --gate)
```

### 2.2 Explicit Config Path (`--config` CLI Option) ✨ New in v1.0

All commands that use configuration (`snapshot`, `drift`, `config`) now support a `--config` option that specifies a custom config file path:

```bash
# Use a custom config file
$ specbridge snapshot --config /path/to/custom-config.yaml

# Show/validate a specific config
$ specbridge config --config ./ci-specbridge.yaml --validate
```

When `--config` is provided, auto-discovery of `.specbridge.yaml` and `pyproject.toml` is **skipped entirely** — only the specified file is loaded. This is useful for:

- **CI/CD pipelines** — separate config for CI vs local development
- **Multi-project analysis** — point specbridge at different project configs
- **Validation workflows** — validate a config before deploying it

### 2.3 YAML Config Format (`.specbridge.yaml`)

### spec_files — Explicit file list for root-level documents

`spec_files` lets you specify individual Markdown files (relative to the project root) **independently** of `spec_dirs`. These bypass the `_EXCLUDE_FILES` set, so documents like `README.md` that are normally excluded are still tracked as specs.

```yaml
spec_dirs:
  - docs
spec_files:
  - README.md             # Each heading becomes a SpecCandidate
  - AGENTS.md
  - CHANGELOG.md
  - .github/pull_request_template.md
```

Similarly, `source_files` lets you specify individual source files:

```yaml
source_files:
  - scripts/install-hooks.sh
```

### Config key reference

````yaml
spec_dirs:
  - docs
  - specs
spec_files:               # Explicit spec files (bypasses _EXCLUDE_FILES)
  - README.md
  - AGENTS.md
source_dirs:
  - src
  - lib
  - app
source_files:             # Explicit source files
  - scripts/setup.sh
exclude_dirs:
  - .git
  - node_modules
  - .venv
  - .specbridge
min_confidence: 0.15
max_output_nodes: 40
min_coverage: 50.0
````
```


### 2.4 `pyproject.toml` Format

```toml
[tool.specbridge]
spec_dirs = ["docs", "spec", "specs"]
source_dirs = ["src", "lib", "app"]
min_confidence = 0.15
max_output_nodes = 20
min_coverage = 50.0
```

### 2.5 Config Loading Logic

```python
@classmethod
def load(cls, project_dir: str | Path, config_path: str | Path | None = None) -> SpecbridgeConfig:
    root = Path(project_dir).resolve()

    # Explicit path mode (v1.0)
    if config_path is not None:
        explicit = Path(config_path)
        if not explicit.exists():
            raise FileNotFoundError(...)
        data = cls._try_read_yaml(explicit)
        if data is None:
            raise ValueError(...)
        return cls._merge_dict(cls(), data)

    # Auto-discovery mode
    config = cls()

    # 1. Try pyproject.toml as base
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        data = cls._try_read_pyproject(pyproject)
        if data:
            config = cls._merge_dict(config, data)

    # 2. Try .specbridge.yaml as override
    yaml_path = root / ".specbridge.yaml"
    if yaml_path.exists():
        data = cls._try_read_yaml(yaml_path)
        if data:
            config = cls._merge_dict(config, data)

    return config
```

### 2.6 Configuration Validation (`config --validate`) ✨ New in v1.0

The `specbridge config --validate` command checks:

| Check | Description |
|-------|-------------|
| `spec_dirs` not empty | At least one spec directory must be configured |
| `source_dirs` not empty | At least one source directory must be configured |
| Directory exists | Every configured directory must exist on disk |
| `min_confidence` range | Must be between 0.0 and 1.0 |
| `max_output_nodes` | Must be ≥ 1 |

**Example:**

```
$ specbridge config --validate
📋 specbridge config (.specbridge.yaml)
========================================
  ✅ Configuration is valid.

  spec_dirs:        ['docs', 'spec', 'specs']
  source_dirs:      ['src', 'lib', 'app']
  exclude_dirs:     15 patterns
  min_confidence:   0.15
  max_output_nodes: 20
```

**Failure example:**

```
$ specbridge config --config bad-config.yaml --validate
📋 specbridge config (bad-config.yaml)
========================================
❌ Validation failed:
  • spec_dir 'nonexistent-docs' does not exist at /path/nonexistent-docs
```

### 2.8 Coverage Gate Threshold (`min_coverage`) ✨ New in v1.1

The `min_coverage` setting defines the minimum coverage percentage for `specbridge coverage --gate`:

```yaml
min_coverage: 50.0   # Fail if coverage drops below 50%
```

Default: `50.0`. Use in combination with `min_coverage` from config or `--min-coverage` CLI override.

**CI workflow example:**

```yaml
- run: specbridge coverage --gate          # uses config threshold
  # or
- run: specbridge coverage --gate --min-coverage 80  # overrides to 80%
```

Together with `specbridge drift --gate`, this forms a complete CI quality gate:
- `drift --gate` — blocks if specs/code have diverged from the snapshot
- `coverage --gate` — blocks if spec coverage is below threshold

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

# In cache.py save_cache():
from specbridge.guard import validate_write_path
validate_write_path(path, root)
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(...)
```

## 4. Cache Module (`cache.py`) ✨ New in v1.0

A new file-hash cache module speeds up repeated analyses by tracking file content hashes.

### Key Functions

| Function | Purpose |
|----------|---------|
| `load_cache()` | Load the cache from `.specbridge/cache.json` |
| `save_cache()` | Persist cache to disk (guard-protected) |
| `filter_cached()` | Compare file hashes against cache, return changed files only |
| `resolve_file_list()` | Recursively list files matching given extensions within source directories |
| `clear_cache()` | Remove the cache file (e.g. after config changes) |

### Cache Format

```json
{
  "docs/auth/auth.md": {
    "hash": "a1b2c3d4e5f6...",
    "mtime": 1722000000
  },
  "src/auth/login.py": {
    "hash": "f6e5d4c3b2a1...",
    "mtime": 1722000100
  }
}
```

The cache uses a two-tier check: **mtime first** (fast, no I/O), then **SHA256 hash** (reliable, file-content based). A file is considered unchanged only if both its mtime and hash match the cache.

### Integration Status

The cache module is available for programmatic use. Full integration into the discovery pipeline is planned for a future release. Currently, `filter_cached()` can be called directly:

```python
from specbridge.cache import filter_cached, load_cache, save_cache

# Get list of source files
files = resolved_file_list("myproject", extensions={".py"}, source_dirs=["src"])

# Check which files changed
changed, updated = filter_cached("myproject", files)

# Update cache
cache = load_cache("myproject")
cache.update(updated)
save_cache("myproject", cache)
```

## 5. Summary

The combination of layered configuration and strict write guard ensures:

- **No accidental writes** to specs or source code
- **Clear error messages** when a write would violate the read-only policy
- **Flexible configuration** via YAML or pyproject.toml with sensible defaults
- **Easy debugging** via `specbridge config` to inspect resolved settings
- **Explicit config paths** via `--config` for CI and multi-project workflows
- **Validation** via `config --validate` to catch configuration errors early
