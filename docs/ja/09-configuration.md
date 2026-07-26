# 設定と読み取り専用ガード

> **日付:** 2026-07-26
> **バージョン:** 0.0.1.dev0

## 1. 概要
<!-- @impl specbridge/adapters/_base.py::ProjectAdapter -->
<!-- @impl specbridge/cli.py::cli -->
<!-- @impl specbridge/cli.py::config -->
<!-- @impl tests/test_code_discovery.py::TestDiscoverCode -->

specbridgeは階層的な設定システムと厳格な読み取り専用ガードを使用して、ツールが仕様やソースコードを決して変更しないことを保証します。

## 2. 設定 (`config.py`)

### 2.1 設定ソース

設定は以下の優先順位で読み込まれます：

1. **`.specbridge.yaml`** — プロジェクトルートのプロジェクト固有設定ファイル
2. **`pyproject.toml`** — `[tool.specbridge]` セクション（Pythonプロジェクト標準）
3. **デフォルト値** — ハードコードされたデフォルト

```python
@dataclass
class SpecbridgeConfig:
    spec_dirs: list[str]        # デフォルト: ["docs", "spec", "specs"]
    source_dirs: list[str]      # デフォルト: ["src", "lib", "app"]
    exclude_dirs: set[str]      # デフォルト: [".git", "node_modules", ".venv", ...]
    min_confidence: float       # デフォルト: 0.15
    max_output_nodes: int       # デフォルト: 20
```

### 2.2 YAML設定形式（`.specbridge.yaml`）

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

### 2.3 `pyproject.toml` 形式

```toml
[tool.specbridge]
spec_dirs = ["docs", "spec", "specs"]
source_dirs = ["src", "lib", "app"]
min_confidence = 0.15
max_output_nodes = 20
```

### 2.4 設定読み込みロジック

```python
@classmethod
def load(cls, project_dir: str | Path) -> SpecbridgeConfig:
    root = Path(project_dir).resolve()

    # 1. .specbridge.yaml を試行
    yaml_path = root / ".specbridge.yaml"
    if yaml_path.exists():
        return cls._from_yaml(yaml_path)

    # 2. pyproject.toml [tool.specbridge] を試行
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        return cls._from_pyproject(pyproject)

    # 3. デフォルト
    return cls()
```

### 2.5 設定の表示

`specbridge config` コマンドで解決された設定とそのソースを表示：

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

## 3. 読み取り専用ガード (`guard.py`)

### 3.1 目的

specbridgeは**読み取り専用**のツールです — 仕様やソースコードを決して変更しません。ガードはすべての書き込みパスを検証することでこれを強制します。

### 3.2 許可される書き込みディレクトリ

specbridgeが書き込み可能な唯一のディレクトリはプロジェクトルート内の `.specbridge/` です：

```python
ALLOWED_WRITE_DIR = ".specbridge"
```

### 3.3 検証ロジック

```python
def validate_write_path(target_path, project_root) -> Path:
    """target_path が .specbridge/ 内にあることを検証。

    有効な場合は解決されたパスを返す。
    ブロックされた場合は PermissionError を発生。
    """
    root = Path(project_root).resolve()
    target = Path(target_path).resolve()
    allowed = root / ALLOWED_WRITE_DIR

    # 1. .specbridge/ 内 → OK
    try:
        target.relative_to(allowed)
        return target
    except ValueError:
        pass

    # 2. 仕様ディレクトリ内 (docs/, spec/, specs/) → BLOCK
    spec_dirs = {root / d for d in ["docs", "spec", "specs"]}
    for forbidden in spec_dirs:
        try:
            target.relative_to(forbidden)
            raise PermissionError("...")
        except ValueError:
            continue

    # 3. ソースディレクトリ内 (src/, lib/, app/, tests/) → BLOCK
    source_dirs = {root / d for d in ["src", "lib", "app", "tests"]}
    for forbidden in source_dirs:
        try:
            target.relative_to(forbidden)
            raise PermissionError("...")
        except ValueError:
            continue

    # 4. プロジェクトルート外 → BLOCK
    try:
        target.relative_to(root)
    except ValueError:
        raise PermissionError("...")

    # 5. プロジェクトルート内だが .specbridge/ ではない → BLOCK
    raise PermissionError("...")
```

### 3.4 保護されるディレクトリ

| ディレクトリ | 理由 |
|-----------|------|
| `docs/`, `spec/`, `specs/` | 仕様ドキュメント — 読み取り専用 |
| `src/`, `lib/`, `app/` | ソースコード — 読み取り専用 |
| `tests/` | テストコード — 読み取り専用 |
| `.specbridge/` | **唯一**の書き込み可能ディレクトリ |
| プロジェクトルート外 | 誤書き込みを防止 |

### 3.5 エラーメッセージ

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

### 3.6 ガードが使用される場所

```python
# drift.py save_snapshot():
from specbridge.guard import validate_write_path
validate_write_path(path, root)
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(...)

# cli.py HTML出力:
out_path = root / ".specbridge" / "trace.html"
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(html, encoding="utf-8")
```

## 4. まとめ

階層的な設定と厳格な書き込みガードの組み合わせにより以下が保証されます：

- **仕様やソースコードへの誤書き込みなし**
- **読み取り専用ポリシー違反時の明確なエラーメッセージ**
- **YAMLまたはpyproject.tomlによる柔軟な設定**と適切なデフォルト値
- **`specbridge config` による簡単な設定確認**
