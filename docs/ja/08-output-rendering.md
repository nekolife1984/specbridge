# 出力レンダリング

> **日付:** 2026-07-26
> **バージョン:** 0.0.1.dev0

## 1. 概要

`outputs/` モジュールは `TraceGraph` を3つの形式にレンダリングします。CLIの `--format` オプションで選択されるか、プログラムから使用されます。

```
TraceGraph
    │
    ├──▶ render_text()  → 人間可読なターミナル出力
    ├──▶ render_json()  → ツール（jq, CI, API）のための構造化データ
    └──▶ render_html()  → インタラクティブD3.jsフォース指向グラフ
```

## 2. テキスト出力 (`outputs/text.py`)

デフォルトの出力形式。グラフを人間可読なターミナルレポートとしてレンダリングします。

**出力構造:**

```
specbridge — Trace Graph
========================================
Nodes: 28 | Edges: 34
Coverage: 83.3% (10/12)

📄 Specs:
  auth.auth.1.1         [2 refs]  User Authentication
  auth.auth.1.2         [1 refs]  Login
  auth.auth.2           [0 refs]  Password Reset

📁 Code refs:
  src/auth/login.py                   → auth.auth.1.1, auth.auth.1.2
  src/auth/register.py                → auth.auth.2
  src/lib/utils.py                     (unlinked)

🧪 Test refs:
  tests/test_auth.py                  → auth.auth.1.1
```

**`--top N` 使用時:**

`max_nodes` が設定されている場合、カテゴリごとに上位N件のみが表示され、切り捨て注釈が付きます：

```
  ... and 3 more specs
  ... and 5 more code files
```

## 3. JSON出力 (`outputs/json_out.py`)

機械処理向けの構造化JSON。

**出力構造:**

```json
{
  "specbridge_version": "0.0.1.dev0",
  "nodes": [
    {
      "id": "auth.auth.1.1",
      "type": "spec",
      "title": "User Authentication",
      "source": {
        "file": "docs/auth/auth.md",
        "line": 3,
        "column": null,
        "label": null
      },
      "framework_origin": "heuristic",
      "confidence": 0.8,
      "metadata": {
        "heading_depth": 2,
        "heading_text": "1.1 User Authentication"
      }
    }
  ],
  "edges": [
    {
      "src_id": "src/auth/login.py",
      "dst_id": "auth.auth.1.1",
      "relation": "implements",
      "strength": "inferred",
      "evidence": [
        {
          "kind": "heuristic:dirname",
          "value": "dir 'auth' matches",
          "source": { "file": "docs/auth/auth.md", "line": 3, "column": null, "label": null }
        }
      ]
    }
  ]
}
```

**実装:**

```python
def render_json(graph: TraceGraph, indent: int = 2) -> str:
    payload = {
        "specbridge_version": "0.0.1.dev0",
        "nodes": [_node_dict(n) for n in graph.nodes.values()],
        "edges": [_edge_dict(e) for e in graph.edges],
    }
    return json.dumps(payload, indent=indent, ensure_ascii=False, default=str)
```

列挙値は `.value` 文字列表現にシリアライズされます。

## 4. HTML出力 (`outputs/html.py`)

インタラクティブなD3.jsフォース指向グラフを含む自己完結型のHTMLページを生成します。

### 機能

- **タイプ別色分けノード**（SPEC = 青, CODE = 緑, TEST = 黄, DESIGN = 紫）
- **タイプ別形状ノード**（SPEC = 矩形, CODE = 円, TEST = 菱形, DESIGN = 三角形）
- **矢印付きエッジ** と関係ラベル（implements, verifies, satisfies, depends）
- **インタラクティブドラッグ** — ノードをドラッグ可能
- **ズームとパン** — マウスホイールズーム、ドラッグでパン
- **クリックでハイライト** — ノードクリックで無関係なノードを暗転
- **ホバーツールチップ** — ID、タイプ、ファイル、フレームワークを表示
- **凡例** — 左下の色/形状リファレンス
- **ヘッダー** — 仕様/コード/テスト/エッジ数を表示

### D3.jsの実装

HTMLはCDN（`https://d3js.org/d3.v7.min.js`）から読み込まれるD3.js v7を使用します。グラフは以下を使用：

- `d3.forceSimulation` with:
  - `forceLink`（間隔: 120px）
  - `forceManyBody`（強度: -300）
  - `forceCenter`（ビューポート中央）
  - `forceCollide`（半径30px）
- 関係タイプごとのSVGマーカー（矢印用）
- ハイライト効果用のCSSトランジション

### 出力場所

HTMLファイルは `.specbridge/trace.html` に保存され、デフォルトブラウザで自動的に開かれます：

```python
out_path = root / ".specbridge" / "trace.html"
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(html, encoding="utf-8")
webbrowser.open(f"file://{out_path.resolve()}")
```

### ノードの色と形状マップ

```python
NODE_COLORS = {
    NodeType.SPEC:   "#4A90D9",  # 青
    NodeType.CODE:   "#50B86C",  # 緑
    NodeType.TEST:   "#F5A623",  # 黄/オレンジ
    NodeType.DESIGN: "#9B59B6",  # 紫
    NodeType.TASK:   "#7F8C8D",  # グレー
}
```

**HTML出力を使用するタイミング:**
- トレース関係を視覚的に探索する場合
- プレゼンテーションやコードレビュー
- ヒューリスティックマッチング結果のデバッグ
- プロジェクト構造を一目で理解する場合

## 5. 証拠の表示

3つの出力形式すべてに証拠情報が含まれます：

| 形式 | 証拠の表示 |
|------|------------|
| **テキスト** | 各エッジの下に `∵ kind: value` 行 |
| **JSON** | 各エッジオブジェクトの `evidence` 配列 |
| **HTML** | ホバーツールチップ + エッジラベル |

## 6. テキスト vs JSON vs HTML

| 機能 | テキスト | JSON | HTML |
|------|---------|------|------|
| **人間の可読性** | ★★★ | ★ | ★★★（インタラクティブ） |
| **機械解析** | ★ | ★★★ | ★ |
| **ファイルサイズ** | 小 | 中 | 大（約30KB） |
| **外部依存** | なし | なし | D3.js（CDN） |
| **出力場所** | stdout | stdout | `.specbridge/trace.html` |
| **パイプ連鎖** | ✓ | ✓ (jq) | ✗ |
| **CI対応** | ✓（テキスト解析） | ✓（JSONパーサー） | ✗ |
