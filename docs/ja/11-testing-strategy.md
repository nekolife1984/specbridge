# テスト戦略

> **日付:** 2026-07-27
> **バージョン:** 1.0.0

## 1. 概要

specbridgeのテストスイートは `pytest` を使用し、すべての主要モジュールを単体テスト、統合テスト、規模テスト、エッジケーステスト、競合アクセステストでカバーします。

**テスト場所:** `tests/`

**現在のテスト数:** 220テスト（全件成功）

## 2. テストファイル

| ファイル | テスト対象モジュール | 焦点 |
|---------|---------------------|------|
| `test_ast.py` | `discovery/ast.py` | Tree-sitter AST抽出 |
| `test_code_discovery.py` | `discovery/code.py` | コード候補抽出（18言語） |
| `test_extract.py` | `core/extract.py` | spec・ソースファイルからのタグ抽出 |
| `test_heuristic_adapter.py` | `adapters/heuristic.py`, `infer/` | ヒューリスティックマッチングエンジン |
| `test_spectra_adapter.py` | `adapters/spectra.py` | Spectraフレームワークアダプター |
| `test_adapter_merge.py` | `adapters/_base.py` | アダプター検出、グラフマージ、spec:: ID正規化 |
| `test_analyzers.py` | `analyzers/__init__.py` | カバレッジ、孤立検出 |
| `test_drift.py` | `analyzers/drift.py` | スナップショットとドリフト検出 |
| `test_import_graph.py` | `analyzers/graph.py` | コード依存関係グラフ |
| `test_boundary.py` | `cli.py` | 境界値検証 |
| `test_guard.py` | `guard.py` | 読み取り専用書き込みパス強制 |
| `test_config.py` | `config.py` | YAML/pyproject.tomlからの設定読み込み、エッジケース設定 |
| `test_plugin_discovery.py` | `adapters/_base.py` | エントリポイント経由のプラグイン発見 |
| `test_large_scale.py` ✨ | 全パイプライン | 50+ specファイル・200+ コードファイルの規模テスト |
| `test_edge_cases.py` ✨ | 全パイプライン | Unicodeパス、空白、バイナリファイル、空ファイル、巨大見出し |
| `test_concurrent.py` ✨ | `analyzers/drift.py` | 分析中のスナップショット保存/読み込み競合 |

## 3. テストカテゴリ

### 3.1 単体テスト

個々の関数やクラスを独立してテストします。

**例:**
- `discovery/spec.py`: `_split_sections()`, `_auto_id()`, `_clean_title()`
- `core/extract.py`: 各種言語の `extract_tags_from_file()`
- `infer/__init__.py`: `_score_edge()`, `_tokenize()`
- `config.py`: YAML、TOML、デフォルトからの読み込み

### 3.2 統合テスト

モジュールが連携して動作することをテストします。

**例:**
- 実際のプロジェクトディレクトリ構造を使用した `build_heuristic_graph()`
- `discover_specs()` + `discover_code()` + `build_heuristic_graph()` のエンドツーエンド
- ドリフト検出：スナップショット→変更→ドリフト→レポート
- アダプターマージ：複数アダプターの検出＋分析＋マージ

### 3.3 境界テスト

エッジケースとエラーハンドリングをテストします。

**例:**
- 空のプロジェクトディレクトリ（specなし、コードなし）
- 見出しのないSpecファイル
- シンタックスエラーのあるソースファイル
- 無効なYAML/TOML設定ファイル
- プロジェクトルート外のファイル
- ファイル名と内容のUnicode
- `_Boundary:_` 違反
- 空白、絵文字、250文字以上のファイル名 ✨
- specディレクトリ内のバイナリファイルと空ファイル ✨
- 誤った値の型（safe_float/safe_int フォールバック） ✨

## 4. テストフィクスチャ（`tests/conftest.py`）

テストスイートは共有フィクスチャを使用してボイラープレートを削減します。

**代表的なフィクスチャ:**
- `tmp_project`: spec（仕様）とコードを含む一時ディレクトリ構造
- `empty_project`: specもコードもない一時ディレクトリ
- `spectra_project`: `.spectra/trace-mapping.yaml` を含むディレクトリ
- `sample_specs`: 事前解析済みの `SpecCandidate[]` フィクスチャ
- `sample_codes`: 事前解析済みの `CodeCandidate[]` フィクスチャ
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

`pyproject.toml` より:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers"
```

## 7. リンターと型チェック

プロジェクトは以下も強制します:

- **Ruff** — リンター（ルールセット: E, F, W, I, B, UP, C4, SIM）
- **Mypy** — 厳格モードの型チェック

両方ともCIの一部として実行され、ローカルでも実行可能です:

```bash
ruff check .
mypy specbridge/
```

## 8. CI統合

GitHub Actions（`/.github/workflows/ci.yml`）:

```yaml
- run: pip install -e ".[dev,ast]"
- run: ruff check .
- run: mypy specbridge/
- run: pytest --cov=specbridge
```

## 9. テスト原則

1. **公開APIをテスト** — プライベートメソッドではなく、公開関数シグネチャを通してテスト
2. **現実的なフィクスチャ** — 最小限だが代表的なプロジェクト構造を使用
3. **決定論的** — 毎回同じ結果を生成（ネットワーク呼び出しなし）
4. **分離** — 各テストは独自の一時ディレクトリを作成・破棄
5. **読み取り専用** — 一時ディレクトリ以外の実際のファイルシステムに書き込まない
6. **カバレッジ** — コアモジュール（core/, infer/, adapters/）で80%以上のカバレッジを目指す
