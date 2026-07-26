# MCP統合

> **日付:** 2026-07-26
> **バージョン:** 0.0.1.dev0

## 1. 概要

specbridgeはMCP（Model Context Protocol）サーバを提供し、その分析機能をAIエージェント向けのツールとして公開します。これにより、MCPプロトコルをサポートするIDE、チャットインターフェース、自動化ワークフローとの統合が可能になります。

```
┌────────────────────┐
│   AI Agent         │
│ (Claude, Hermes,  │
│  Cursor, etc.)     │
└────────┬───────────┘
         │ MCP Protocol (stdio)
         ▼
┌────────────────────┐
│  specbridge MCP    │
│  Server            │
│  (mcp_server.py)   │
│                    │
│  ツール:          │
│  - analyze        │
│  - impact         │
│  - coverage       │
│  - drift          │
│  - validate_      │
│    boundary       │
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│  プロジェクトDir   │
│  (読み取り専用)    │
└────────────────────┘
```

## 2. アーキテクチャ

### 2.1 サーバ初期化

```python
def create_mcp_server(project_dir: str = ".") -> object:
    """MCPサーバインスタンスを作成。"""
    from mcp.server import Server
    root = Path(project_dir).resolve()
    server = Server("specbridge")
    # ... ツール登録 ...
    return server
```

### 2.2 トランスポート

サーバは**stdioトランスポート**を使用 — stdin/stdoutを介してAIエージェントと通信：

```python
async def run_mcp_server(project_dir: str = ".") -> None:
    from mcp.server.stdio import stdio_server
    server = create_mcp_server(project_dir)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
```

### 2.3 依存関係

MCPサーバには `mcp` Pythonパッケージが必要（オプション依存）：

```
pip install specbridge[mcp]
```

## 3. 公開ツール

### 3.1 `analyze`

プロジェクトの完全なspec-codeトレース分析を実行。

- **入力パラメータなし**
- **戻り値**: ノード数とカバレッジ率を含むサマリーテキスト
- **ユースケース**: エージェントがトレーサビリティ状況の概要を確認

### 3.2 `impact`

指定された仕様を実装するものを検索。

- **必須パラメータ**: `spec_id` — 例："1.1" または "spec::1.1"
- **戻り値**: 信頼度と証拠付きの実装コード/テストファイルのリスト
- **ユースケース**: エージェントが「spec 1.1を実装しているものは？」

### 3.3 `coverage`

仕様カバレッジ統計を取得。

- **入力パラメータなし**
- **戻り値**: カバレッジ率、孤立仕様とコードファイル（最大5件）
- **ユースケース**: エージェントが変更前後のカバレッジを確認

### 3.4 `drift`

スナップショットと現在の状態の間の変更を検出。

- **オプションパラメータ**: `take_snapshot`（真偽値、デフォルト: false）
  - `true`: 新しいスナップショットを取得（比較なし）
  - `false`: 現在の状態を最後のスナップショットと比較
- **戻り値**: ドリフトレポートテキスト
- **ユースケース**: エージェントが「最後のスナップショットからドリフトは？」

### 3.5 `validate_boundary`

コード参照が宣言された `_Boundary:_` マーカー内にあるかチェック。

- **入力パラメータなし**
- **戻り値**: 違反のリストまたは「すべてクリア」
- **ユースケース**: エージェントがコード変更後にバウンダリ準拠を検証

## 4. ツール定義（MCPスキーマ）

```python
@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    return [
        Tool(
            name="analyze",
            description="プロジェクトの完全なspec-codeトレース分析を実行",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="impact",
            description="指定された仕様を実装するものを検索",
            inputSchema={
                "type": "object",
                "properties": {
                    "spec_id": {
                        "type": "string",
                        "description": "仕様ID（例：'1.1' または 'spec::1.1'）",
                    },
                },
                "required": ["spec_id"],
            },
        ),
        # ... coverage, drift, validate_boundary ...
    ]
```

## 5. 内部フロー

各ツールコールは以下の内部フローに従います：

```
ツールコール受信
    │
    ├──▶ detect_all(root) を実行 → 一致するアダプタのリスト
    ├──▶ 各 adapter.analyze(root) を実行 → TraceGraph のリスト
    ├──▶ merge_graphs(graphs) → 単一のマージ済み TraceGraph
    │
    ├──▶ analyze用: グラフから統計情報を抽出
    ├──▶ impact用: specノード + エッジを検索
    ├──▶ coverage用: coverage_summary + 孤立を計算
    ├──▶ drift用: スナップショット読み込み + compute_drift（または新規スナップショット）
    └──▶ validate_boundary用: _Boundary:_ マーカーに対してコード参照をチェック
        │
        ▼
    TextContent レスポンスを返す
```

## 6. 統合パターン

### パターン1: CI/CDパイプライン

```yaml
# GitHub Action: デプロイ前仕様チェック
steps:
  - run: pip install specbridge[mcp]
  - run: specbridge snapshot --reason "デプロイ前チェック"
  - run: specbridge drift --gate
```

MCPを使用すると、エージェントは：
```python
# エージェントがマージ承認前にドリフトチェックを委任
result = await call_mcp_tool("drift", {})
if result.has_drift:
    comment_on_pr("⚠️ ドリフト検出 — レビューが必要です")
```

### パターン2: IDE統合

MCPをサポートするエディタ（Cursor、拡張機能付きVS Codeなど）では、specbridgeツールが通常のIDEツールと並んで表示されます。エージェントは以下が可能：

1. 仕様ドキュメントを開く
2. `impact` を実行して該当するコードをすべて検索
3. 関連するソースファイルにナビゲート

### パターン3: 自動バウンダリ施行

```python
# エージェントが自動コード生成後にバウンダリチェックを実行
result = await call_mcp_tool("validate_boundary", {})
if "violation" in result:
    raise Exception("コード生成がバウンダリ違反を発生させました")
```

## 7. エラーハンドリング

| 状況 | 応答 |
|------|------|
| アダプタが見つからない | `"認識されたSSDフレームワークが見つかりません"` |
| スナップショットがない（drift） | 最初に `take_snapshot=true` で実行するように指示 |
| アダプタのパースエラー | 空のTraceGraphを返す（アダプタが処理する必要あり） |
| 無効なspec_id | `"Spec 'X' が見つかりません"` メッセージ |

## 8. 対話例

```
ユーザー: 「このプロジェクトでカバーされている仕様は？」

エージェント (MCP経由):
  → specbridge.analyze() を呼び出し
  ← Project: /Users/me/project
     Nodes: 28 | Edges: 34
     Specs: 12 | Code refs: 15 | Tests: 3
     Coverage: 83.3% (10/12)

ユーザー: 「spec 1.1を実装しているものを調べて」

エージェント (MCP経由):
  → specbridge.impact({"spec_id": "1.1"}) を呼び出し
  ← Spec auth.auth.1.1: User Authentication
     [EXPLICIT] src/auth/login.py (implements)
     [EXPLICIT] tests/test_auth.py (verifies)
```
