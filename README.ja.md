# specbridge

> **Spec ↔ Code bridge.** フレームワーク非依存の読み取り専用トレーサビリティ解析ツール。

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
[![ci](https://github.com/nekolife1984/specbridge/actions/workflows/ci.yml/badge.svg)](https://github.com/nekolife1984/specbridge/actions)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

`specbridge` は仕様書とソースコードの関係を **読み取り専用で** マッピングします。設計書やコードを一切変更せずに、カバレッジ・乖離・影響範囲・境界違反を検出します。

---

## インストール（限定公開）

```bash
pip install git+https://github.com/nekolife1984/specbridge.git
```

またはローカルで clone & install：

```bash
git clone https://github.com/nekolife1984/specbridge.git
cd specbridge
pip install -e .
```

インストール後、最も速いセットアップ方法：

```bash
# 対話的セットアップ：ディレクトリ検出、hookインストール、AGENTS.md配置
specbridge setup
```

またはスタンドアロンスクリプト（事前インストール不要）：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/nekolife1984/specbridge/main/scripts/setup.sh)
```

---

## クイックスタート（3分）

### 0. ワンコマンドセットアップ

```bash
specbridge setup
```

これで `.specbridge.yaml` の作成、pre-commit drift hookのインストール、AIエージェント向け `AGENTS.md` の配置、初回スナップショットの取得までを一括で行います。

### 1. サンプルプロジェクトで試す

```bash
cd examples/todo-app
specbridge analyze --merge
```

以下のような出力が出ます：

```
Nodes: 9 | Edges: 16
Coverage: 100.0%
```

Markdownで書かれた設計書（`docs/tasks.md`）とPythonコード（`src/tasks/service.py`）の関係を、`@impl` タグとファイル名ヒューリスティックで自動マッピングしています。

### 2. 自分のプロジェクトで試す

プロジェクトルートに `.specbridge.yaml` を作成：

```yaml
spec_dirs:
  - docs           # 設計書ディレクトリ
source_dirs:
  - src            # ソースコードディレクトリ
  - tests          # （任意）テストファイル
```

そして実行：

```bash
specbridge analyze --merge
```

### 3. 他のコマンド

```bash
specbridge coverage                  # カバレッジ集計
specbridge impact --spec-id 1.1      # 指定specの実装コード
specbridge snapshot                  # スナップショット保存
specbridge drift --git-base main     # gitベースとの乖離検出
specbridge validate-boundary         # _Boundary:_ マーカーの検証
specbridge impact --spec-id 1.1 --call-graph  # 推移的（間接）影響
specbridge call-graph --spec-id 1.1  # コールグラフ解析
specbridge setup                     # ワンコマンドセットアップ
```

---

## 何に使える？

| ユースケース | コマンド | 効果 |
|-------------|---------|------|
| **カバレッジ監査** | `specbridge coverage` | コードのない設計書を発見 |
| **影響分析** | `specbridge impact --spec-id 1.1` | 設計書変更の影響を受けるコードを特定 |
| **推移的影響** | `specbridge impact --spec-id 1.1 --call-graph` | 関数呼び出し経由の間接影響ファイル |
| **コールグラフ** | `specbridge call-graph --spec-id 1.1` | スタンドアロンコールグラフ解析 |
| **乖離検出** | `specbridge drift --git-base main` | コードと設計書の乖離を確認 |
| **CIゲート** | `specbridge drift --gate` | 乖離のあるPRをブロック |
| **境界検証** | `specbridge validate-boundary` | コード参照が宣言スコープ内に収まっているか確認 |
| **タグ不要** | `specbridge analyze --merge` | SSDタグのないプロジェクトでも動作 |
| **MCP / AIエージェント** | `specbridge serve` | AIエージェントからトレーサビリティ参照 |
| **ワンコマンドセットアップ** | `specbridge setup` | 30秒でプロジェクト設定完了 |

---

## 主な特徴

- **読み取り専用**: 設計書やコードを一切変更しません。出力は `.specbridge/` にのみ書き込みます。
- **デュアルモード**: タグベース（spectra `@impl`、`@verifies`）**と** ヒューリスティック（ファイル名/シンボルマッチ、タグ不要）の両方をサポート。
- **多言語対応**: Python、TypeScript、Go、Rust、Java、Ruby、C/C++、C#、Swift、Kotlin、Dart、PHP — 18言語（**tree-sitter** によるASTベース関数抽出、オプション: `pip install specbridge[ast]`）。
- **コールグラフ**: 関数レベルコールグラフによる推移的（間接）影響分析（`--call-graph` フラグ）。
- **Graphifyアダプター**（オプション）: `graphify` CLIによる深いASTベースコードグラフ（`pipx install graphifyy`、その後 `specbridge analyze --merge`）。
- **3つの出力形式**: text（ターミナル）、JSON（jq/CI）、HTML（インタラクティブD3.jsグラフ）。
- **プラグインSDK**: カスタムアダプターをpipインストール可能なパッケージとして作成可能。

---

## デモ

```bash
# Clone
git clone https://github.com/nekolife1984/specbridge.git
cd specbridge
pip install -e .

# サンプルプロジェクトを解析
specbridge analyze --dir examples/todo-app --merge

# カバレッジを表示
specbridge coverage --dir examples/todo-app

# HTMLグラフ（.specbridge/trace.html をブラウザで開く）
specbridge analyze --dir examples/todo-app --merge --format html

# ウォッチモード（ファイル変更を検出して自動再解析）
specbridge watch --dir examples/todo-app --merge
```

---

## プロジェクト構造

```text
specbridge/
├── specbridge/         # コアライブラリ
│   ├── cli.py          # ClickベースのCLI（12コマンド）
│   ├── core/           # データモデル（TraceNode, TraceEdge, TraceGraph）
│   ├── adapters/       # プラグインレジストリ + ビルトインアダプター
│   ├── infer/          # ヒューリスティックマッチングエンジン
│   ├── discovery/      # 設計書/コードファイルスキャン（18言語）
│   ├── analyzers/      # カバレッジ、乖離検出、インポートグラフ、コールグラフ
│   ├── outputs/        # テキスト、JSON、HTML レンダリング
│   ├── guard.py        # 読み取り専用書き込みバリデーション
│   ├── config.py       # .specbridge.yaml ローダー
│   └── mcp_server.py   # AIエージェント向けMCPサーバー
├── examples/
│   └── todo-app/       # 実行可能なデモプロジェクト
├── docs/               # 設計書（日本語 + 英語、12カテゴリ）
├── scripts/
│   ├── setup.sh        # スタンドアロンセットアップスクリプト
│   └── install-hooks.sh # pre-commit + pre-push hook インストール
├── .agents/
│   ├── scripts/
│   │   ├── pre-commit.specbridge.sh   # ブランチ名 + drift gate
│   │   └── pre-push.specbridge.sh     # main直接push防止
│   └── skills/
│       └── specbridge/
│           └── SKILL.md             # AIエージェントスキル
├── AGENTS.md            # AIエージェントワークフローガイド
└── tests/              # 198+ テスト
```

---

## 必要なセットアップ

各プロジェクトに `.specbridge.yaml`（または `pyproject.toml` の `[tool.specbridge]`）が必要です：

```yaml
spec_dirs:
  - docs
  - specs
source_dirs:
  - src
  - lib
  - app
exclude_dirs:
  - .git
  - node_modules
  - .venv
  - .specbridge
min_confidence: 0.15
max_output_nodes: 40
```

タグやアノテーションは不要です — specbridge は初期状態でも推論可能な関係を自動で発見します。

---

## Git Hooks

specbridge は **2つの対象者** 向けに git hook を提供しています：

| 対象者 | インストール方法 | インストールされるもの |
|--------|----------------|----------------------|
| **specbridge開発者**（このリポジトリ） | `sh scripts/install-hooks.sh` | pre-commit（ブランチ検証 + drift）+ pre-push（main直接push防止） |
| **下流ユーザー**（あなたのプロジェクト） | `specbridge setup` | pre-commit（drift gate のみ） |

```text
# specbridge開発 — フル適用
git commit       → pre-commit: ブランチ名OK？ + drift clean？ → ✅
git push main    → pre-push: ブロック ❌（PRを使ってください）

# 下流プロジェクト — drift gate のみ
git commit       → pre-commit: drift clean？ → ✅
git push main    → hookなし（各自のワークフロー）
```

### 🔧 specbridge開発者向け

```bash
sh scripts/install-hooks.sh
```

以下の2つのhookがインストールされます：

- **pre-commit**: ブランチ名が `feat/` / `fix/` / `chore/` / `docs/` / `refactor/` に従っているか検証し、その後 trace drift をチェック
- **pre-push**: `main` への直接pushをブロック — すべての変更はPR経由

### 📦 下流ユーザー向け

```bash
specbridge setup
```

**drift gate のみ** の簡略化された pre-commit hook がインストールされます。ブランチ命名規則や push 保護は含まれません。hook は自動的に specbridge リポジトリ内かどうかを検出し、specbridge固有のチェックをスキップします。

**ドリフト検出時の表示：**

```text
❌ specbridge: Drift detected between snapshot and your changes!
   Run 'specbridge drift' to see details.
   If changes are intentional, run 'specbridge snapshot' to update baseline
   and include .specbridge/snapshot.json in your commit.
```

hook は **git-base モード**（`drift --git-base HEAD`）を使用 — 前回コミットから変更があったファイルだけを分析するので、大規模プロジェクトでも軽量です。

**初回ベースライン設定：**

```bash
specbridge snapshot          # 初期スナップショット作成
git add .specbridge/         # ベースラインを追跡
```

---

## AIエージェントスキル

specbridge には **AIエージェントスキル** が `.agents/skills/specbridge/SKILL.md` に同梱されています。このスキルはAIエージェントにツールの使い方（インストール、分析、ドリフトチェック、CI設定、MCPサーバー連携）を教えます。

**Hermes Agent へのインストール：**

```bash
# 推奨: specbridge setup が自動処理
specbridge setup

# または手動:
bash scripts/install-hooks.sh
```

これで pre-commit hook とスキルの両方が `~/.hermes/skills/` にシンボリックリンクされます。エージェントは `specbridge` スキルをロードして使い方のドキュメントを参照できます。

**手動インストール（その他のエージェント）：**

```bash
ln -sf "$(pwd)/.agents/skills/specbridge" ~/.hermes/skills/software-development/specbridge
```

またはスキルファイルを直接 `.agents/skills/specbridge/SKILL.md` から参照してください。

### プロジェクトに AGENTS.md を設定する

**任意のAIエージェント**（Hermes、Claude Code、OpenCode、Cursor、Codex）に specbridge の規約を守らせるには、プロジェクトルートに `AGENTS.md` を追加します：

```markdown
# プロジェクトガイド

このプロジェクトは **specbridge** を使用して spec↔code トレーサビリティを管理しています。

## 必須ルール（コード変更前後）

1. `specbridge snapshot --reason "..."` — 変更前の状態を保存
2. コードを書く（必要に応じて設計書も更新）
3. `specbridge drift` — 乖離がないか確認
4. 乖離があれば設計書を先に修正
5. `git commit`（pre-commit hook が自動チェック）
```

完全な例は specbridge リポジトリの [AGENTS.md](AGENTS.md) を参照してください。

---

## アーキテクチャ

```text
┌──────────────────────────────────────────────┐
│  SSD フレームワーク（spectra, heuristic, …） │
└──────────────┬───────────────────────────────┘
               │ 読み取り（入力）
               ▼
┌──────────────────────────────────────────────┐
│  ★ specbridge ★                               │
│  ├─ adapters/  （レジストリ + フレームワーク）│
│  ├─ infer/     （ヒューリスティック推論）     │
│  ├─ core/      （モデル + タグ抽出）          │
│  ├─ discovery/ （設計書/コード候補抽出）       │
│  ├─ analyzers/ （カバレッジ、乖離、孤立）      │
│  └─ guard/     （読み取り専用パス検証）        │
└──────────────┬───────────────────────────────┘
               │ テキスト / JSON / 終了コード
               ▼
┌──────────────────────────────────────────────┐
│  CLI 出力 / .specbridge/snapshot.json        │
└──────────────────────────────────────────────┘
```

---

## ドキュメント

詳細設計書は [`docs/`](docs/) にあります（日本語 + 英語、12カテゴリ）：

| 設計書 | 説明 |
|--------|------|
| [アーキテクチャ](docs/ja/01-architecture.md) | 全体設計とデータフロー |
| [データモデル](docs/ja/02-data-model.md) | TraceNode, TraceEdge, TraceGraph |
| [アダプター/プラグインシステム](docs/ja/03-adapter-plugin-system.md) | プラグインSDK、ビルトインアダプター |
| [探索エンジン](docs/ja/04-discovery-engine.md) | 設計書/コードスキャン、シンボル抽出 |
| [ヒューリスティックマッチング](docs/ja/05-heuristic-matching.md) | タグ不要推論アルゴリズム |
| [乖離検出](docs/ja/06-drift-detection.md) | スナップショット、乖離、リネーム検出 |
| [CLIコマンド](docs/ja/07-cli-commands.md) | 全10コマンドのリファレンス |
| [出力レンダリング](docs/ja/08-output-rendering.md) | テキスト、JSON、HTML出力形式 |
| [設定](docs/ja/09-configuration.md) | .specbridge.yaml、階層的設定 |
| [MCP統合](docs/ja/10-mcp-integration.md) | AIエージェント連携 |
| [テスト戦略](docs/ja/11-testing-strategy.md) | テストアーキテクチャ |
| [ブランチ戦略](docs/ja/12-branching-strategy.md) | ブランチ規約、PRワークフロー、リリースプロセス |

---

## フィードバック（限定公開）

このツールはプライベートベータです。バグ報告やフィードバックをお待ちしています：

- **GitHub Issues**: https://github.com/nekolife1984/specbridge/issues
- **メール**: nekolife@gmail.com

報告時は以下を含めてください：

```bash
specbridge --version
specbridge config
```

---

## ライセンス

MIT
