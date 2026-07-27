# 設定と読み取り専用ガード

> **日付:** 2026-07-27
> **バージョン:** 1.0.0

## 1. 概要
<!-- @impl specbridge/adapters/_base.py::ProjectAdapter -->
<!-- @impl specbridge/cli.py::cli -->
<!-- @impl specbridge/cli.py::config -->
<!-- @impl tests/test_code_discovery.py::TestDiscoverCode -->

specbridgeは階層的な設定システムと厳格な読み取り専用ガードを使用して、ツールが仕様やソースコードを決して変更しないことを保証します。

## 2. 設定 (`config.py`)

### 2.1 設定ソース（排他的ではなくマージ）

設定は複数のソースを**マージ**して読み込まれます。後続のソースが特定のフィールドを上書きします：

1. **デフォルト値** — ハードコードされたデフォルト
2. **`pyproject.toml`** — `[tool.specbridge]` セクション（基本設定）
3. **`.specbridge.yaml`** — 特定のフィールドを上書き（最優先）

`pyproject.toml` と `.specbridge.yaml` の両方が存在する場合、それらは**マージ**され、未指定のフィールドは上流のソースから継承されます。これにより、例えば `source_dirs` を `pyproject.toml` で、`spec_dirs` を `.specbridge.yaml` で共存させることができます。

```python
@dataclass
class SpecbridgeConfig:
    spec_dirs: list[str]        # デフォルト: ["docs", "spec", "specs"]
    source_dirs: list[str]      # デフォルト: ["src", "lib", "app"]
    exclude_dirs: set[str]      # デフォルト: [".git", "node_modules", ".venv", ...]
    min_confidence: float       # デフォルト: 0.15
    max_output_nodes: int       # デフォルト: 20
```

### 2.2 明示的な設定パス（`--config` CLIオプション） ✨ v1.0新機能
<!-- @impl specbridge/config.py::SpecbridgeConfig.load -->

設定を使用するすべてのコマンド（`snapshot`、`drift`、`config`）が、カスタム設定ファイルパスを指定する `--config` オプションをサポートするようになりました：

```bash
# カスタム設定ファイルを使用
$ specbridge snapshot --config /path/to/custom-config.yaml

# 特定の設定を表示・検証
$ specbridge config --config ./ci-specbridge.yaml --validate
```

`--config` が指定された場合、`.specbridge.yaml` と `pyproject.toml` の自動検出は**完全にスキップ**され、指定されたファイルのみが読み込まれます。これは以下で役立ちます：

- **CI/CDパイプライン** — ローカル開発とCIで異なる設定を使用
- **マルチプロジェクト分析** — 異なるプロジェクト設定を指定
- **検証ワークフロー** — デプロイ前に設定を検証

### 2.3 YAML設定形式（`.specbridge.yaml`）

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

### 2.4 `pyproject.toml` 形式

```toml
[tool.specbridge]
spec_dirs = ["docs", "spec", "specs"]
source_dirs = ["src", "lib", "app"]
min_confidence = 0.15
max_output_nodes = 20
```

### 2.5 設定読み込みロジック

```python
@classmethod
def load(cls, project_dir: str | Path, config_path: str | Path | None = None) -> SpecbridgeConfig:
    root = Path(project_dir).resolve()

    # 明示的パスモード（v1.0）
    if config_path is not None:
        explicit = Path(config_path)
        if not explicit.exists():
            raise FileNotFoundError(...)
        data = cls._try_read_yaml(explicit)
        if data is None:
            raise ValueError(...)
        return cls._merge_dict(cls(), data)

    # 自動検出モード
    config = cls()

    # 1. pyproject.toml をベースに試行
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        data = cls._try_read_pyproject(pyproject)
        if data:
            config = cls._merge_dict(config, data)

    # 2. .specbridge.yaml を上書きとして試行
    yaml_path = root / ".specbridge.yaml"
    if yaml_path.exists():
        data = cls._try_read_yaml(yaml_path)
        if data:
            config = cls._merge_dict(config, data)

    return config
```

### 2.6 設定検証（`config --validate`）✨ v1.0 新機能

`specbridge config --validate` コマンドは以下をチェックします：

| チェック | 説明 |
|-------|-------------|
| `spec_dirs` が空でない | 少なくとも1つの仕様ディレクトリが必要 |
| `source_dirs` が空でない | 少なくとも1つのソースディレクトリが必要 |
| ディレクトリが存在する | 設定されたすべてのディレクトリがディスク上に存在すること |
| `min_confidence` の範囲 | 0.0〜1.0 の間であること |
| `max_output_nodes` | 1以上であること |

**成功例：**

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

**失敗例：**

```
$ specbridge config --config bad-config.yaml --validate
📋 specbridge config (bad-config.yaml)
========================================
❌ Validation failed:
  • spec_dir 'nonexistent-docs' does not exist at /path/nonexistent-docs
```

### 2.7 設定表示

`specbridge config` コマンドは解決された設定とそのソースを表示します：

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

## 3. 読み取り専用ガード（`guard.py`）

### 3.1 目的

specbridgeは**読み取り専用**のツールであり、仕様やソースコードを決して変更しません。ガードはすべての書き込みパスを検証することでこれを強制します。

### 3.2 許可された書き込みディレクトリ

specbridgeが書き込みできる唯一のディレクトリは、プロジェクトルート内の `.specbridge/` です：

```python
ALLOWED_WRITE_DIR = ".specbridge"
```

### 3.3 検証ロジック

```python
def validate_write_path(target_path, project_root) -> Path:
    """target_path が .specbridge/ 内にあることを検証。

    解決されたパスを返す。ブロックされた場合は PermissionError を送出。
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

    # 2. 仕様ディレクトリ内（docs/, spec/, specs/）→ ブロック
    spec_dirs = {root / d for d in ["docs", "spec", "specs"]}
    for forbidden in spec_dirs:
        try:
            target.relative_to(forbidden)
            raise PermissionError("...")
        except ValueError:
            continue

    # 3. ソースディレクトリ内（src/, lib/, app/, tests/）→ ブロック
    source_dirs = {root / d for d in ["src", "lib", "app", "tests"]}
    for forbidden in source_dirs:
        try:
            target.relative_to(forbidden)
            raise PermissionError("...")
        except ValueError:
            continue

    # 4. プロジェクトルート外 → ブロック
    try:
        target.relative_to(root)
    except ValueError:
        raise PermissionError("...")

    # 5. プロジェクトルート内だが .specbridge/ ではない → ブロック
    raise PermissionError("...")
```

### 3.4 保護対象ディレクトリ

| ディレクトリ | 理由 |
|-----------|--------|
| `docs/`, `spec/`, `specs/` | 仕様ドキュメント — 読み取り専用 |
| `src/`, `lib/`, `app/` | ソースコード — 読み取り専用 |
| `tests/` | テストコード — 読み取り専用 |
| `.specbridge/` | **唯一**書き込み可能なディレクトリ |
| プロジェクトルート外 | 誤った書き込みを防止 |

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
# drift.py save_snapshot() 内:
from specbridge.guard import validate_write_path
validate_write_path(path, root)
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(...)

# cache.py save_cache() 内 ✨ v1.0:
from specbridge.guard import validate_write_path
validate_write_path(path, root)
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(...)
```

## 4. キャッシュモジュール (`cache.py`) ✨ v1.0新機能
<!-- @impl specbridge/cache.py -->
<!-- @impl specbridge/cache.py::load_cache -->
<!-- @impl specbridge/cache.py::save_cache -->
<!-- @impl specbridge/cache.py::filter_cached -->
<!-- @impl specbridge/cache.py::resolve_file_list -->
<!-- @impl specbridge/cache.py::clear_cache -->

新しいファイルハッシュキャッシュモジュールで、ファイルのコンテンツハッシュを追跡して繰り返しの分析を高速化します。

### 主要関数

| 関数 | 目的 |
|----------|---------|
| `load_cache()` | `.specbridge/cache.json` からキャッシュを読み込み |
| `save_cache()` | キャッシュをディスクに永続化（ガード保護） |
| `filter_cached()` | ファイルハッシュをキャッシュと比較し、変更されたファイルのみを返す |
| `resolve_file_list()` | 指定された拡張子に一致するファイルをソースディレクトリ内から再帰的にリスト |
| `clear_cache()` | キャッシュファイルを削除（設定変更後など） |

### キャッシュ形式

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

キャッシュは2段階のチェックを使用します：**mtime優先**（高速、I/Oなし）、その後 **SHA256ハッシュ**（信頼性、ファイルコンテンツベース）。ファイルは、mtimeとハッシュの両方がキャッシュと一致する場合にのみ変更なしと見なされます。

### 統合ステータス

キャッシュモジュールはプログラムでの使用が可能です。ディスカバリパイプラインへの完全な統合は将来のリリースで計画されています。現在、`filter_cached()` は直接呼び出すことができます：

```python
from specbridge.cache import filter_cached, load_cache, save_cache

# ソースファイルのリストを取得
files = resolved_file_list("myproject", extensions={".py"}, source_dirs=["src"])

# 変更されたファイルを確認
changed, updated = filter_cached("myproject", files)

# キャッシュを更新
cache = load_cache("myproject")
cache.update(updated)
save_cache("myproject", cache)
```

## 5. まとめ

階層的な設定と厳格な書き込みガードの組み合わせにより、以下が保証されます：

- **仕様やソースコードへの誤書き込みなし**
- **書き込みが読み取り専用ポリシーに違反する場合の明確なエラーメッセージ**
- **YAMLまたはpyproject.tomlによる柔軟な設定**と適切なデフォルト値
- **設定の容易なデバッグ**（`specbridge config` で解決済み設定を確認）
- **CIやマルチプロジェクトワークフロー向けの明示的な設定パス**（`--config`）
- **設定エラーを早期に発見する検証**（`config --validate`）
