# CLIコマンドリファレンス

> **日付:** 2026-07-26
> **バージョン:** 0.0.1.dev0

## 1. 概要

specbridgeはClickベースのCLIを提供し、トレーサビリティ分析、ドリフト検出、プロジェクト管理のための9つのコマンドを持ちます。

```
Usage: specbridge [OPTIONS] COMMAND [ARGS]...

  Spec ↔ Code bridge: 読み取り専用トレーサビリティ分析ツール

Options:
  --version  バージョンを表示
  --help     ヘルプを表示

Commands:
  analyze            プロジェクトを分析しトレースグラフを構築
  impact             指定された仕様を実装するものを検索
  coverage           仕様カバレッジ統計を表示
  snapshot           仕様とコードの構造的スナップショットを取得
  drift              スナップショットと現在の状態の変化を検出
  validate-boundary  コード参照が宣言された_Boundary:_内にあるか検証
  config             現在のspecbridge設定を表示
  watch              プロジェクトの変更を監視し自動再分析
  plugins            インストール済みのアダプタプラグインを一覧表示
```

## 2. コマンド

### 2.1 `analyze`

プロジェクトのトレースグラフを構築します。主要コマンド。

```
Usage: specbridge analyze [OPTIONS]

  プロジェクトを分析しトレースグラフを構築

Options:
  -d, --dir TEXT      分析するプロジェクトディレクトリ  [default: .]
  --format TEXT       出力形式 (text, json, html)  [default: text]
  -m, --merge         一致する全アダプタの結果をマージ
  --top INTEGER       カテゴリごとに上位N件のみ表示（デフォルト：すべて）
  --deps              インポートからコード依存関係グラフを構築
  --help              ヘルプを表示
```

**例:**

```
# 基本分析
$ specbridge analyze

# JSON出力（パイプ処理用）
$ specbridge analyze --format json | jq '.edges'

# インタラクティブHTMLグラフ
$ specbridge analyze --format html

# 全アダプタをマージ
$ specbridge analyze --merge

# カテゴリごとに上位5件のみ表示
$ specbridge analyze --top 5

# コード依存関係グラフを含める
$ specbridge analyze --deps
```

**動作:**

1. プロジェクトに最適なアダプタを検出（`--merge` の場合は全アダプタ）
2. アダプタの `analyze()` を実行して TraceGraph を構築
3. オプションでコード依存関係グラフを構築（`--deps`）
4. 選択された形式で出力

### 2.2 `impact`

特定の仕様を実装するコード/テストファイルを検索します。**あいまい検索**に対応しており、完全な階層IDを知らなくても検索できます。

```
Usage: specbridge impact [OPTIONS]

  指定された仕様を実装するものを検索

Options:
  -d, --dir TEXT      プロジェクトディレクトリ  [default: .]
  --spec-id TEXT      分析する仕様IDまたはタイトル（例："1.1", "TraceNode"）[必須]
  --format TEXT       出力形式 (text, json)  [default: text]
  --help              ヘルプを表示
```

**検索解決順序:**

| 優先度 | 方法 | 入力例 → マッチ結果 |
|--------|------|---------------------|
| 1 | ID完全一致 | `docs.en.02-data-model.1.2.1` |
| 2 | `spec::` 接頭辞 | `1.1` → `spec::1.1` |
| 3 | ID後方一致 | `1.2.1` → `docs.en.02-data-model.1.2.1` など |
| 4 | タイトル部分一致 | `TraceNode` → タイトルに "TraceNode" を含むspec |
| 5 | 見出しテキスト | `build_heuristic_graph` → 見出しに含むspec |

複数のspecがマッチした場合、すべての結果と実装アーティファクトが表示されます。

**例:**

```
# ID後方一致（1.2.1 で終わる全specを検索）
$ specbridge impact --spec-id 1.2.1
📄 docs.en.02-data-model.1.2.1: TraceNode
📄 docs.en.03-adapter-plugin-system.1.2.1: Contract
...

# タイトル検索
$ specbridge impact --spec-id TraceNode
📄 docs.en.02-data-model.1.2.1: TraceNode
  [INFERRED] specbridge/core/__init__.py  (implements)
            ∵ heuristic:funcname: function 'TraceNode' matches spec 'TraceNode'

# 完全IDで検索
$ specbridge impact --spec-id docs.en.02-data-model.1.2.1

# 関数レベル結果も表示
$ specbridge impact --spec-id build_heuristic_graph
📄 docs.en.05-heuristic-matching.1.2: Algorithm: `build_heuristic_graph()`
  [INFERRED] specbridge/infer/__init__.py  (implements)
            ∵ heuristic:funcname: function 'build_heuristic_graph' matches spec

# JSON出力（複数マッチも処理）
$ specbridge impact --spec-id 1.2.1 --format json
```

### 2.3 `coverage`

仕様カバレッジ統計を表示します。

```
Usage: specbridge coverage [OPTIONS]

  仕様カバレッジ統計を表示

Options:
  -d, --dir TEXT      プロジェクトディレクトリ  [default: .]
  --format TEXT       出力形式 (text, json)  [default: text]
  --help              ヘルプを表示
```

**例:**

```
$ specbridge coverage
📊 Spec Coverage
========================================
  Total specs:  12
  Covered:      10
  Orphan specs: 2
  Coverage:     83.3%

🟡 Orphan specs (no code ref):
   - docs.auth.auth.3.1
   - docs.auth.auth.4.0
```

### 2.4 `snapshot`

後続のドリフト比較のため、現在のプロジェクト状態の構造的スナップショットを取得します。

```
Usage: specbridge snapshot [OPTIONS]

  仕様とコードの構造的スナップショットを取得

Options:
  -d, --dir TEXT      プロジェクトディレクトリ  [default: .]
  --reason TEXT       スナップショットを取った理由の説明
  --help              ヘルプを表示
```

**例:**

```
$ specbridge snapshot --reason "認証リファクタリング前"
📸 Snapshotting /Users/me/project ...
   Specs: 12 | Code files: 45
   Coverage: 83.3%
   Saved: .specbridge/snapshot.json
```

### 2.5 `drift`

保存されたスナップショットと現在のプロジェクト状態の間の変更を検出します。

```
Usage: specbridge drift [OPTIONS]

  スナップショットと現在の状態の変化を検出

Options:
  -d, --dir TEXT          プロジェクトディレクトリ  [default: .]
  --snapshot TEXT         スナップショットファイルへのパス（デフォルト：.specbridge/snapshot.json）
  --gate                  ドリフト検出時に終了コード1で終了
  --format TEXT           出力形式 (text, json)  [default: text]
  --git-base TEXT         gitベース参照（スナップショット比較の代替）
  --help                  ヘルプを表示
```

**例:**

```
# 保存されたスナップショットと比較
$ specbridge drift

# JSONレポート
$ specbridge drift --format json

# CIゲート（ドリフト時にexit 1）
$ specbridge drift --gate

# gitベース比較（スナップショット不要）
$ specbridge drift --git-base main

# 特定のスナップショットファイルを使用
$ specbridge drift --snapshot ./backups/snapshot-2026-01.json
```

### 2.6 `validate-boundary`

すべてのコード参照が仕様書で宣言された `_Boundary:_` マーカー内にあることをチェックします。

```
Usage: specbridge validate-boundary [OPTIONS]

  コード参照が宣言された_Boundary:_内にあるか検証

Options:
  -d, --dir TEXT      プロジェクトディレクトリ  [default: .]
  --help              ヘルプを表示
```

**例:**

```
$ specbridge validate-boundary
⚠️  2 boundary violation(s):
  auth.auth.1.1 in docs/auth/auth.md
    declares boundaries: src/auth/
    but tests/test_external_api.py is outside

Tip: Add _Boundary:_ src/path/ or move the @impl to a file inside the boundary.
```

### 2.7 `config`

現在のspecbridge設定とそのソースを表示します。

```
Usage: specbridge config [OPTIONS]

  現在のspecbridge設定を表示

Options:
  -d, --dir TEXT      プロジェクトディレクトリ  [default: .]
  --yaml              設定をYAMLとして出力
  --help              ヘルプを表示
```

**例:**

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

### 2.8 `watch`

プロジェクトディレクトリのファイル変更を監視し、自動的に再分析します。`watchdog` パッケージが必要。

```
Usage: specbridge watch [OPTIONS]

  プロジェクトの変更を監視し自動再分析

  オプションの'watch'エクストラが必要：pip install specbridge[watch]

Options:
  -d, --dir TEXT          プロジェクトディレクトリ  [default: .]
  --interval FLOAT        デバウンス間隔（秒）  [default: 2.0]
  --help                  ヘルプを表示
```

**動作:**

- `watchdog.observers.Observer` を使用したファイルシステム監視
- 急激な変更をデバウンス（デフォルト：2秒間隔）
- `.specbridge/` ディレクトリの変更は無視（再トリガーループを回避）
- 検出された各変更に対してフル分析を実行
- トリガーごとにターミナルをクリアして出力を再レンダリング

### 2.9 `plugins`

インストールされているすべてのアダプタプラグイン（内蔵およびサードパーティ）を一覧表示します。

```
Usage: specbridge plugins [OPTIONS]

  インストール済みのアダプタプラグインを一覧表示

Options:
  --refresh       インストール済みパッケージを再スキャン
  --help          ヘルプを表示
```

**例:**

```
$ specbridge plugins
🔌 Built-in adapters:
   HeuristicAdapter
   SpectraAdapter

🔌 Plugin adapters (0):
   (none)
```

## 3. 終了コード

| コード | 意味 |
|--------|------|
| 0 | 成功（または `--gate` でドリフトなし） |
| 1 | ドリフト検出（`drift --gate`）、アダプタが見つからない、または実行時エラー |

## 4. プラグインSDK（`specbridge plugins`）

`plugins` コマンドはPythonエントリポイントを介して登録されたアダプタを検出します：

```
$ pip install my-specbridge-plugin
$ specbridge plugins --refresh
🔌 Plugin adapters (1):
   MyAdapter (from my-specbridge-plugin)
```

## 5. ヘルプ

すべてのコマンドが `--help` をサポート：

```
$ specbridge analyze --help
$ specbridge drift --help
```

トップレベルのヘルプで全コマンドを表示：

```
$ specbridge --help
```
