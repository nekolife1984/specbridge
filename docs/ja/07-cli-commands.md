# CLIコマンドリファレンス

> **日付:** 2026-07-27
> **バージョン:** 1.0.0

## 1. 概要

specbridgeはClickベースのCLIを提供し、トレーサビリティ分析、ドリフト検出、プロジェクト管理のための**17のコマンド**を持ちます。

```
Usage: specbridge [OPTIONS] COMMAND [ARGS]...

  Spec ↔ Code bridge: 読み取り専用トレーサビリティ分析ツール（SSD向け）

Options:
  --version  バージョンを表示
  --help     ヘルプを表示

Commands:
  analyze            プロジェクトを分析しトレースグラフを構築
  impact             指定された仕様を実装するものを検索
  init               対話的設定ジェネレーター（.specbridge.yaml）
  coverage           仕様カバレッジ統計を表示
  snapshot           仕様とコードの構造的スナップショットを取得
  drift              スナップショットと現在の状態の変化を検出
  status             プロジェクト状態ダッシュボード（設定、スナップショット、カバレッジ、ドリフト）を表示
  validate-boundary  コード参照が宣言された_Boundary:_内にあるか検証
  config             現在のspecbridge設定を表示/検証
  watch              プロジェクトの変更を監視し自動再分析
  plugins            インストール済みのアダプタプラグインを一覧表示
  serve              AIエージェント統合用のMCPサーバーを起動
  call-graph         コールグラフを構築し推移的（間接）影響を表示
  setup              ワンコマンドセットアップ（設定、フック、AGENTS.md、スナップショット）
  shell-completion   シェル補完スクリプトを生成またはインストール
  diff               2つのスナップショット間の差分を表示
  suggest            孤立specに対するコードファイルを提案
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
  -m, --merge         一致する全アダプタの結果をマージ（最適なものだけでなく）
  --top INTEGER       カテゴリごとに上位N件のみ表示（デフォルト：すべて）
  --deps              インポートからコード依存関係グラフを構築（DEPENDSエッジを追加）
  -c, --call-graph    推移的影響分析のためのコールグラフを構築
  --fast              関数レベルマッチングをスキップ [デフォルト: on, --func-matchで有効化]
  --func-match        関数レベルマッチングを有効化（大規模プロジェクトでは低速）
  --dry-run           `.specbridge/`への出力ファイル書き込みなしで分析
  --summary-only      CI対応の1行カバレッジサマリーのみ表示
  --help              ヘルプを表示
```

**v1.1の新オプション:**

| オプション | 目的 |
|-----------|------|
| `--dry-run` | `.specbridge/trace.html`へのHTML出力書き込みをスキップ |
| `--summary-only` | `🟢 Coverage: 60.7% (259/427)` のようなCI対応の1行を表示 |

**進捗表示:** 長時間実行される分析操作では、Richプログレスバーによるスピナーが表示されます。

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

# CI対応の1行サマリー
$ specbridge analyze --summary-only
🟢 Coverage: 83.3% (10/12)

# ドライラン（HTML保存なしでプレビュー）
$ specbridge analyze --format html --dry-run
   📄 HTML output generated (--dry-run, not saved)
```

### 2.2 `impact`

特定の仕様を実装するコード/テストファイルを検索するか、ファイル変更の影響を受ける仕様を調査します。2つのモードがあります：

- **フォワード影響**（`--spec-id`）: 仕様 → 実装コードファイル
- **リバース影響**（`--file`）: コードファイル → 影響を受ける仕様（v1.1新機能）

```
Usage: specbridge impact [OPTIONS]

  仕様とコードの間の影響を分析

Options:
  -d, --dir TEXT      プロジェクトディレクトリ  [default: .]
  --spec-id TEXT      分析する仕様ID（例："1.1"）
  --file TEXT         リバース影響用ファイルパス：このファイルの変更が
                      影響する仕様を検索
  --format TEXT       出力形式 (text, json)  [default: text]
  -c, --call-graph    コールグラフによる推移的（間接）影響を含める
  --max-depth INTEGER コールグラフ探索の最大深さ  [default: 3]
  --help              ヘルプを表示
```

`--spec-id` と `--file` は排他 — どちらか一方のみを指定します。

**フォワード影響の例：**

```bash
# spec 1.1 を実装するものを検索
$ specbridge impact --spec-id 1.1

# コールグラフによる推移的影響付き
$ specbridge impact --spec-id 1.1 --call-graph --max-depth 3
```

**リバース影響の例（v1.1+）：**

```bash
# ファイル変更の影響を受ける仕様を検索
$ specbridge impact --file src/auth/login.py

# 推移的影響付き
$ specbridge impact --file specbridge/cli.py --call-graph
```

### 2.3 `coverage`

色分けインジケータ付きで仕様カバレッジ統計を表示します。

```
Usage: specbridge coverage [OPTIONS]

  仕様カバレッジ統計を表示

Options:
  -d, --dir TEXT          プロジェクトディレクトリ  [default: .]
  --format TEXT           出力形式 (text, json)  [default: text]
  --gate                  カバレッジが min_coverage 閾値未満の場合に
                          終了コード1で終了
  --min-coverage FLOAT    --gate の閾値を上書き（デフォルト: configから）
  --help                  ヘルプを表示
```

**出力例:**

```
$ specbridge coverage
📊 Spec Coverage  🟢
========================================
  Total specs:  12
  Covered:      10
  Orphan specs: 2
  Coverage:     83.3%
```

カバレッジは色分けされます：🟢 ≥80%、🟡 ≥50%、🔴 <50%。

**カバレッジゲート（CIモード）:**

```
$ specbridge coverage --gate
✅ Coverage gate passed: 83.3% >= 50.0% (10/12 specs covered)
$ echo $?
0

$ specbridge coverage --gate --min-coverage 90
❌ Coverage gate FAILED: 83.3% < 90.0% (10/12 specs covered)
$ echo $?
1
```

`--gate` フラグは `specbridge coverage` をCIゲートに変えます：カバレッジが閾値以上なら終了コード0、未満なら1で終了します。`--min-coverage` で設定ファイルの閾値を1回だけ上書きできます。`drift --gate` と組み合わせることで、完全なpre-commit/CI品質ゲートになります。

### 2.4 `snapshot`

後続のドリフト比較のため、現在のプロジェクト状態の構造的スナップショットを取得します。

```
Usage: specbridge snapshot [OPTIONS]

  仕様とコードの構造的スナップショットを取得

Options:
  -d, --dir TEXT      プロジェクトディレクトリ  [default: .]
  --config TEXT       設定ファイルへのパス（デフォルト: .specbridge.yaml / pyproject.toml を自動検出）
  --reason TEXT       スナップショットを取った理由の説明
  --dry-run           スナップショットをディスクに書き込まずに構築
  --help              ヘルプを表示
```

**v1.0の新オプション:**

| オプション | 目的 |
|-----------|------|
| `--config` | 自動検出の代わりにカスタム設定ファイルパスを使用 |
| `--dry-run` | `.specbridge/snapshot.json`に保存せずにスナップショットをメモリ上で構築 |

**HTMLカバレッジレポート（v1.1+）:**

```
$ specbridge analyze --merge --report
```

`.specbridge/report.html` にリッチな自己完結型HTMLカバレッジレポートを生成します：
- カバレッジプログレスバー + パス/フェイルゲート表示
- タブビュー：すべて / カバー済み / 部分（コードのみ） / 未カバー
- Spec IDまたはタイトルで検索/フィルタ
- 色分け行（🟢/🟡/🔴）
- 孤立コードファイル一覧
- インタラクティブなJavaScriptフィルタリング（ビルド不要）

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
  --config TEXT           設定ファイルへのパス（デフォルト: .specbridge.yaml / pyproject.toml を自動検出）
  --snapshot TEXT         スナップショットファイルへのパス（デフォルト：.specbridge/snapshot.json）
  --gate                  ドリフト検出時に終了コード1で終了
  --format TEXT           出力形式 (text, json)  [default: text]
  --git-base TEXT         gitベース参照（スナップショット比較の代替）
  --help                  ヘルプを表示
```

### 2.6 `status` ✨ v1.0新機能

設定、スナップショットステータス、現在のカバレッジ、ドリットチェックを1つのコマンドで表示する統合プロジェクト状態ダッシュボード。

```
Usage: specbridge status [OPTIONS]

  設定、スナップショット、カバレッジ、ドリフトを1つのビューで表示

Options:
  -d, --dir TEXT      プロジェクトディレクトリ  [default: .]
  --format TEXT       出力形式 (text, json)  [default: text]
  --help              ヘルプを表示
```

**出力例:**

```
$ specbridge status
📋 specbridge Status
==================================================

🔧 Configuration:
   spec_dirs:        ['docs', 'spec']
   source_dirs:      ['src', 'lib']
   exclude_dirs:     15 patterns
   min_confidence:   0.15

📸 Snapshot:
   Taken:           2026-07-27T10:30:00
   Reason:          Before auth refactor
   Coverage:        83.3%
   Specs (snap):    12
   Code files:      45

📊 Current Coverage:
   Coverage:        83.3%
   Total specs:     12
   Covered:         10
   Orphan specs:    2
   Orphan code:     1

✅ No drift detected — project state matches snapshot.
```

**ユースケース:**

- **クイックヘルスチェック** — 1つのコマンドでプロジェクトの状態を確認
- **CI診断** — `status --format json` で機械処理
- **変更前/後比較** — 変更の前後に実行して影響を確認

### 2.7 `shell-completion` ✨ 新機能

シェル補完スクリプト（Bash/Zsh/Fish）を生成またはインストールします。

```
Usage: specbridge shell-completion [OPTIONS]

  Generate or install shell completion scripts.

  specbridge uses Click's built-in shell completion.  After installing,
  press TAB to auto-complete commands, options, and arguments.

  Quick start:   specbridge shell-completion --install

  Or manually:   eval "$(specbridge shell-completion --show --shell bash)"

Options:
  --shell [bash|zsh|fish]  ターゲットシェル（デフォルト: SHELL環境変数から自動検出）
  --install                補完を永続的にインストール（シェルrcファイルに追記）
  --show                   補完スクリプトをstdoutに出力（手動インストール用）
  --help                   このメッセージを表示
```

**使用例:**

```bash
# シェルを自動検出して手順を表示
$ specbridge shell-completion

# 永続的にインストール
$ specbridge shell-completion --install

# 特定のシェルを指定してセットアップ
$ eval "$(specbridge shell-completion --show --shell zsh)"
```

**動作仕組み:**

specbridgeは Click 8.1+ のビルトインシェル補完を `_SPECBRIDGE_COMPLETE` 環境変数経由で使用します。この変数が設定されてCLIが呼び出されると、Clickはコマンド実行の代わりに補完スクリプトを出力します。

**シェル別サポート:**

| シェル | RCファイル | 補完環境変数 |
|-------|-----------|-------------|
| Bash | `~/.bashrc` | `_SPECBRIDGE_COMPLETE=bash_source` |
| Zsh | `~/.zshrc` | `_SPECBRIDGE_COMPLETE=zsh_source` |
| Fish | `~/.config/fish/config.fish` | `_SPECBRIDGE_COMPLETE=fish_source` |

インストール後、TABキーでコマンドやオプションを補完できます：

```
$ specbridge [TAB]
analyze       call-graph    config        coverage      drift
impact        plugins       serve         setup         shell-completion
snapshot      status        validate-boundary  watch

$ specbridge analyze --[TAB]
--call-graph  --config    --deps      --dir       --dry-run
--fast        --format    --func-match  --help      --merge     --summary-only
--top
```

### 2.8 `validate-boundary`

すべてのコード参照が仕様書で宣言された `_Boundary:_` マーカー内にあることをチェックします。

```
Usage: specbridge validate-boundary [OPTIONS]

  コード参照が宣言された_Boundary:_内にあるか検証

Options:
  -d, --dir TEXT      プロジェクトディレクトリ  [default: .]
  --help              ヘルプを表示
```

### 2.9 `config`

現在のspecbridge設定とそのソースを表示または検証します。

```
Usage: specbridge config [OPTIONS]

  現在のspecbridge設定を表示

Options:
  -d, --dir TEXT      プロジェクトディレクトリ  [default: .]
  --config TEXT       設定ファイルへのパス（デフォルト: .specbridge.yaml / pyproject.toml を自動検出）
  --yaml              設定をYAMLとして出力
  --validate          設定の正しさを検証
  --help              ヘルプを表示
```

**v1.0の新オプション:**

| オプション | 目的 |
|-----------|------|
| `--config` | 特定の設定ファイルを読み込んで表示/検証 |
| `--validate` | 仕様ディレクトリとソースディレクトリが存在し、数値が有効範囲内かをチェック |

**検証チェック:**

* `spec_dirs` と `source_dirs` が空でない
* `spec_dirs` と `source_dirs` の全ディレクトリが実際にディスク上に存在する
* `min_confidence` が0.0〜1.0の範囲内
* `max_output_nodes` が1以上

**例:**

```
$ specbridge config --validate
📋 specbridge config (.specbridge.yaml)
========================================
  ✅ Configuration is valid.

  spec_dirs:        ['docs', 'spec', 'specs']
  source_dirs:      ['src', 'lib', 'app']
  ...
```

### 2.10 `watch`

プロジェクトディレクトリのファイル変更を監視し、自動的に再分析します。`watchdog` パッケージが必要。

```
Usage: specbridge watch [OPTIONS]

  プロジェクトの変更を監視し自動再分析

  オプションの'watch'エクストラが必要：pip install specbridge[watch]

Options:
  -d, --dir TEXT          プロジェクトディレクトリ  [default: .]
  --interval FLOAT        デバウンス間隔（秒）  [default: 2.0]
  --fast                  関数レベルマッチングをスキップ [デフォルト: on]
  --func-match            関数レベルマッチングを有効化（大規模プロジェクトでは低速）
  --help                  ヘルプを表示
```

### 2.11 `plugins`

インストールされているすべてのアダプタプラグイン（内蔵およびサードパーティ）を一覧表示します。

```
Usage: specbridge plugins [OPTIONS]

  インストール済みのアダプタプラグインを一覧表示

Options:
  --refresh       インストール済みパッケージを再スキャン
  --help          ヘルプを表示
```

### 2.12 `call-graph`

関数レベルのコールグラフを構築し、specに対する推移的（間接）影響を分析します。

```
Usage: specbridge call-graph [OPTIONS]

  コールグラフを構築し推移的（間接）影響を表示

Options:
  -d, --dir TEXT       プロジェクトディレクトリ  [default: .]
  --spec-id TEXT       分析する仕様ID（例：1.1）[必須]
  --max-depth INTEGER  コールグラフ探索の最大深さ  [default: 3]
  --format TEXT        出力形式 (text, json)  [default: text]
  --help               ヘルプを表示
```

### 2.13 `serve`

AIエージェント統合用のMCPサーバーを起動します。

```
Usage: specbridge serve [OPTIONS]

  AIエージェント統合用のMCPサーバーを起動

  specbridgeツール（analyze, impact, coverage, drift, validate_boundary）を
  Model Context Protocol 経由で公開。必要：pip install specbridge[mcp]

Options:
  -d, --dir TEXT   プロジェクトディレクトリ  [default: .]
  --help           ヘルプを表示
```

### 2.14 `setup`

ワンコマンドでプロジェクトをブートストラップ。設定作成、フックインストール、AIエージェント用ファイル展開、初回スナップショットを自動実行します。

```
Usage: specbridge setup [OPTIONS]

  ワンコマンドセットアップ：フックインストール、設定作成、AGENTS.md展開

Options:
  -d, --dir TEXT   セットアップするプロジェクトディレクトリ  [default: .]
  --ci             GitHub Actions CIワークフローも作成
  --help           ヘルプを表示
```

### 2.15 `init` ✨ 新機能

対話的に `.specbridge.yaml` を生成する設定ジェネレーターです。

```
Usage: specbridge init [OPTIONS]

  Interactive config generator — create .specbridge.yaml step by step.

  Scans the project for spec directories (docs/, spec/, specs/, ...) and
  source directories (src/, lib/, app/, tests/, ...), then guides you
  through selecting which to include and writing the config file.

Options:
  -d, --dir TEXT   プロジェクトディレクトリ  [default: .]
  --force          既存の .specbridge.yaml を確認なしで上書き
  --help           ヘルプを表示
```

**対話フロー:**

```
$ specbridge init

🔍 Scanning /home/user/myproject ...

📁 Spec directories found:
    docs/  (12 .md files)
    specs/  (3 .md files)
   Include all of them? [Y/n] y

🔧 Source directories found:
    src/  (45 source files)
    lib/  (12 source files)
    tests/  (18 source files)
   Include all of them? [Y/n] y

📝 Config preview:
    spec_dirs:        ['docs', 'specs']
    source_dirs:      ['src', 'lib', 'tests']
    min_confidence:   0.15
    max_output_nodes: 20

   Write .specbridge.yaml? [Y/n] y

✅ .specbridge.yaml created in /home/user/myproject

💡 Next steps:
   1. Run 'specbridge setup' to install pre-commit hook and AGENTS.md
   2. Run 'specbridge snapshot' to create the initial baseline
   3. Run 'specbridge analyze' to see your trace graph
```

### 2.16 `diff` ✨ 新機能

2つのスナップショットファイルを比較し、要約差分を表示します。spec版の `git diff --stat` のようなものです。

```
Usage: specbridge diff [OPTIONS] BEFORE AFTER

  Compare two snapshot files and show a summary diff.

  BEFORE and AFTER are paths to .specbridge/snapshot.json files.

Options:
  --format [text|json]  出力フォーマット  [default: text]
  --help                ヘルプを表示
```

**出力例:**

```
$ specbridge diff snapshots/baseline.json snapshots/current.json
📊 specbridge snapshot diff
==================================================

📊 Coverage trend:
   Before:  65.2% (28/43)
   After:   78.7% (37/47)
   Change:  +13.5%

📄 Spec changes:
   + 3 added
       + "Rate Limiting"
       + "OAuth Flow"
   - 1 removed
   ~ 2 titles changed

📁 Code changes:
   + 12 files added
   - 1 file removed
   ⚡ 3 functions changed

🟡 Orphan changes:
   Before:  12 orphan specs
   After:   5 orphan specs
   Resolved: 7 orphan specs covered
```

### 2.17 `suggest` ✨ 新機能

カバレッジのない孤立specに対して、実装候補となるコードファイルを提案します。

```
Usage: specbridge suggest [OPTIONS]

  Suggest code files that may implement uncovered specs.

Options:
  -d, --dir TEXT        プロジェクトディレクトリ  [default: .]
  --top INTEGER         表示する提案数  [default: 5]
  --format [text|json]  出力フォーマット  [default: text]
  --threshold FLOAT     類似度スコアの閾値 (0.0-1.0)  [default: 0.1]
  --help                ヘルプを表示
```

**出力例:**

```
$ specbridge suggest
📋 specbridge suggest — 3 orphan spec(s)
==================================================

1. docs.api.2.3 "Rate Limiting" (docs/api/api.md)
   → 3 candidate(s), top 2:
     📁 src/api/middleware/rate_limiter.py  (score: 0.45)
     🔤 src/api/handler.py                  (score: 0.28)

2. docs.auth.1.2 "OAuth Flow" (docs/auth/auth.md)
   → 2 candidate(s), top 2:
     📁 src/auth/oauth.py  (score: 0.52)
     🔧 src/auth/oauth.py::handle_oauth     (score: 0.38)

3. docs.db.3.1 "Migration Strategy" (docs/db/db.md)
   → No matching code files found (threshold: 0.1)
     💡 Check that source_dirs in .specbridge.yaml covers the implementation
```

## 3. 改善されたエラーメッセージ（v1.0）

specbridgeがサポート対象のプロジェクト構造を見つけられない場合、**実行可能なヒント**を提供するようになりました：

```
❌ No recognized SSD framework found.
   Hints:
     • Ensure you are in a project with Markdown spec docs and source code.
     • Default spec dirs: docs/, spec/, specs/
     • Default source dirs: src/, lib/, app/
     • Create .specbridge.yaml to configure custom directories.
     • Run 'specbridge config' to see current discovered settings.
```

## 4. 終了コード

| コード | 意味 |
|-------|------|
| 0 | 成功（または `--gate` でドリフトなし、`coverage --gate` でカバレッジ閾値以上） |
| 1 | ドリフト検出（`drift --gate`）、カバレッジが閾値未満（`coverage --gate`）、アダプタが見つからない、設定検証失敗、または実行時エラー |
