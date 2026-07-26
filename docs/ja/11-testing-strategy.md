# テスト戦略

> **日付:** 2026-07-26
> **バージョン:** 0.0.1.dev0

## 1. 概要

specbridgeのテストスイートは `pytest` を使用し、すべての主要モジュールを単体テスト、統合テスト、境界テストでカバーします。

**テスト場所:** `tests/`

## 2. テストファイル

| ファイル | テスト対象モジュール | 焦点 |
|---------|---------------------|------|
| `test_ast.py` | `discovery/ast.py` | Tree-sitter AST抽出 |
| `test_code_discovery.py` | `discovery/code.py` | コード候補抽出（18言語） |
| `test_extract.py` | `core/extract.py` | 仕様とソースファイルからのタグ抽出 |
| `test_heuristic_adapter.py` | `adapters/heuristic.py`, `infer/` | ヒューリスティックマッチングエンジン |
| `test_spectra_adapter.py` | `adapters/spectra.py` | Spectraフレームワークアダプタ |
| `test_adapter_merge.py` | `adapters/_base.py` | アダプタ検出とグラフマージ |
| `test_analyzers.py` | `analyzers/__init__.py` | カバレッジ、孤立検出 |
| `test_drift.py` | `analyzers/drift.py` | スナップショットとドリフト検出 |
| `test_import_graph.py` | `analyzers/graph.py` | コード依存関係グラフ |
| `test_boundary.py` | `cli.py` | バウンダリ検証 |
| `test_guard.py` | `guard.py` | 読み取り専用書き込みパスの施行 |
| `test_config.py` | `config.py` | YAML / pyproject.toml からの設定読み込み |
| `test_plugin_discovery.py` | `adapters/_base.py` | エントリポイント経由のプラグイン発見 |

## 3. テストカテゴリ

### 3.1 単体テスト

個々の関数とクラスを独立してテスト。

**例:**
- `discovery/spec.py`: `_split_sections()`, `_auto_id()`, `_clean_title()`
- `core/extract.py`: 様々な言語に対する `extract_tags_from_file()`
- `infer/__init__.py`: `_score_edge()`, `_tokenize()`
- `config.py`: YAML、TOML、デフォルトからの読み込み

### 3.2 統合テスト

モジュールが連携して動作する方法をテスト。

**例:**
- 実際のプロジェクトディレクトリ構造を使用した `build_heuristic_graph()`
- エンドツーエンドの `discover_specs()` + `discover_code()` + `build_heuristic_graph()`
- ドリフト検出：スナップショット → 変更 → ドリフト → レポート
- アダプタマージ：複数アダプタの検出 + 分析 + マージ

### 3.3 境界テスト

エッジケースとエラーハンドリングをテスト。

**例:**
- 空のプロジェクトディレクトリ（仕様なし、コードなし）
- 見出しのない仕様ファイル
- 構文エラーを含むソースファイル
- 無効なYAML/TOML設定ファイル
- プロジェクトルート外のファイル
- ファイル名と内容のUnicode
- `_Boundary:_` 違反

## 4. テストフィクスチャ（`tests/conftest.py`）

テストスイートは共有フィクスチャを使用してボイラープレートを削減。

**典型的なフィクスチャ:**
- `tmp_project`: 仕様とコードを含む一時ディレクトリ構造
- `empty_project`: 仕様もコードもない一時ディレクトリ
- `spectra_project`: `.spectra/trace-mapping.yaml` を含むディレクトリ
- `sample_specs`: 事前パース済み `SpecCandidate[]` フィクスチャ
- `sample_codes`: 事前パース済み `CodeCandidate[]` フィクスチャ
- `snapshot_data`: ドリフトテスト用の事前構築済みスナップショット辞書

## 5. テストの実行

```bash
# 標準テスト実行
pytest

# カバレッジ付き
pytest --cov=specbridge

# 特定のテストファイル
pytest tests/test_drift.py

# 詳細出力
pytest -v

# 最初の失敗で停止
pytest -x
```

## 6. テスト設定

`pyproject.toml` より：

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers"
```

## 7. リンターと型チェック

プロジェクトは以下も強制します：

- **Ruff** — ルールセット E, F, W, I, B, UP, C4, SIM によるリンター
- **Mypy** — 厳格モードの型チェック

両方ともCIの一部として実行され、ローカルでも実行可能：

```bash
ruff check .
mypy specbridge/
```

## 8. CI統合

GitHub Actions（`/.github/workflows/ci.yml`）：

```yaml
- run: pip install -e ".[dev,ast]"
- run: ruff check .
- run: mypy specbridge/
- run: pytest --cov=specbridge
```

## 9. テスト原則

1. **パブリックAPIをテスト** — プライベートメソッドではなく、公開関数シグネチャを通じてテストを優先
2. **現実的なフィクスチャ** — 最小限だが代表的なプロジェクト構造を使用
3. **決定論的** — テストは毎回同じ結果を生成するべき（ネットワークコールなし）
4. **分離された** — 各テストは独自の一時ディレクトリを作成して破棄
5. **読み取り専用** — 一時ディレクトリ以外の実際のファイルシステムに書き込むテストはしない
6. **カバレッジ** — コアモジュール（core/, infer/, adapters/）で80%以上のカバレッジを目標に
