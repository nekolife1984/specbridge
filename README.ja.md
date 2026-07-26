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

---

## クイックスタート（3分）

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
```

---

## 何に使える？

| ユースケース | コマンド | 効果 |
|-------------|---------|------|
| **カバレッジ監査** | `specbridge coverage` | コードのない設計書を発見 |
| **影響分析** | `specbridge impact --spec-id 1.1` | 設計書の変更で影響を受けるコードを特定 |
| **乖離検出** | `specbridge drift --git-base main` | コードと設計書が乖離していないか確認 |
| **CIゲート** | `specbridge drift --gate` | 乖離のあるPRをブロック |
| **境界検証** | `specbridge validate-boundary` | コード参照が宣言スコープ内に収まっているか確認 |
| **タグ不要** | `specbridge analyze --merge` | SSDタグのないプロジェクトでも動作 |
| **AIエージェント連携** | `specbridge serve` | MCPプロトコルでAIエージェントからトレーサビリティ参照 |

---

## 主な特徴

- **読み取り専用**: 設計書やコードを一切変更しません。出力は `.specbridge/` にのみ書き込みます。
- **デュアルモード**: タグベース（spectra `@impl`、`@verifies`）**と** ヒューリスティック（ファイル名/シンボルマッチ、タグ不要）の両方をサポート。
- **多言語対応**: Python、TypeScript、Go、Rust、Java、Ruby、C/C++、C#、Swift、Kotlin、Dart、PHP — 18言語。
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

```
specbridge/
├── specbridge/         # コアライブラリ
│   ├── cli.py          # ClickベースのCLI（10コマンド）
│   ├── core/           # データモデル（TraceNode, TraceEdge, TraceGraph）
│   ├── adapters/       # プラグインレジストリ + ビルトインアダプター
│   ├── infer/          # ヒューリスティックマッチングエンジン
│   ├── discovery/      # 設計書/コードファイルスキャン（18言語）
│   ├── analyzers/      # カバレッジ、乖離検出、インポートグラフ
│   ├── outputs/        # テキスト、JSON、HTML レンダリング
│   ├── guard.py        # 読み取り専用書き込みバリデーション
│   ├── config.py       # .specbridge.yaml ローダー
│   └── mcp_server.py   # AIエージェント向けMCPサーバー
├── examples/
│   └── todo-app/       # 実行可能なデモプロジェクト
├── docs/               # 設計書（日本語 + 英語、11カテゴリ）
└── tests/              # 169+ テスト
```

---

## セットアップ

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

## Pre-commit Hook（ドリフトゲート）

specbridge には **pre-commit hook** が同梱されています。コミットのたびに自動でトレースドリフトをチェックし、コードと設計書の乖離を防止します。

```
git commit ─→ specbridge drift --git-base HEAD --gate ─→ driftなし → コミットOK
                                                     └→ driftあり → ❌ コミットブロック
```

**インストール方法:**

```bash
# ワンコマンドインストーラー（hook + Hermes スキルをシンボリックリンク）:
bash scripts/install-hooks.sh

# 手動:
ln -sf ../../.agents/scripts/pre-commit.specbridge.sh .git/hooks/pre-commit
```

**ドリフト検出時の表示:**

```text
❌ specbridge: Drift detected between snapshot and your changes!
   Run 'specbridge drift' to see details.
   If changes are intentional, run 'specbridge snapshot' to update baseline
   and include .specbridge/snapshot.json in your commit.
```

hook は **git-base モード**（`drift --git-base HEAD`）を使用 — 前回コミットから変更があったファイルだけを分析するので、大規模プロジェクトでも軽量です。

**初回ベースライン設定:**

```bash
specbridge snapshot          # 初期スナップショット作成
git add .specbridge/         # ベースラインを追跡
```

---

## AIエージェントスキル

specbridge には **AIエージェントスキル** が `.agents/skills/specbridge/SKILL.md` に同梱されています。このスキルはAIエージェントにツールの使い方（インストール、分析、ドリフトチェック、CI設定、MCPサーバー連携）を教えます。

**Hermes Agent へのインストール:**

```bash
bash scripts/install-hooks.sh
```

これで pre-commit hook とスキルの両方が `~/.hermes/skills/` にシンボリックリンクされます。エージェントは `specbridge` スキルをロードして使い方のドキュメントを参照できます。

**手動インストール（その他のエージェント）:**

```bash
ln -sf "$(pwd)/.agents/skills/specbridge" ~/.hermes/skills/software-development/specbridge
```

またはスキルファイルを直接 `.agents/skills/specbridge/SKILL.md` から参照してください。

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

詳細設計書は [`docs/`](docs/) にあります（日本語 + 英語、11カテゴリ）：

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
