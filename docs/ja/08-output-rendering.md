# 出力レンダリング

> **日付:** 2026-07-27
> **バージョン:** 1.0.0

## 1. 概要
<!-- @impl specbridge/adapters/_base.py::merge_graphs -->
<!-- @impl specbridge/analyzers/__init__.py::coverage_summary -->
<!-- @impl specbridge/analyzers/__init__.py::find_orphan_code -->
<!-- @impl tests/test_adapter_merge.py::TestMergeCLI -->

`outputs/` モジュールは `TraceGraph` を3つの形式にレンダリングします。CLIの `--format` オプションで選択されるか、プログラムから使用されます。

```
TraceGraph
    │
    ├──▶ render_text()  → 人間可読なターミナル出力
    ├──▶ render_json()  → ツール（jq, CI, API）のための構造化データ
    └──▶ render_html()  → インタラクティブD3.jsフォース指向グラフ
```

さらに、v1.0での新機能：

- **色分けカバレッジ** — 🟢🟡🔴 インジケータでカバレッジ率を表示
- **1行CIサマリー** — `--summary-only` モードのための `render_one_line_coverage()`
- **Rich進捗表示** — `rich_utils.py` がスピナーとプログレスバーのヘルパーを提供

## 2. テキスト出力 (`outputs/text.py`)
<!-- @impl specbridge/outputs/text.py::render_text -->

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

**関数レベルマッチング使用時:**

`build_heuristic_graph()` 使用時（ヒューリスティックアダプタ）は、関数レベルのノードが専用セクションに表示されます：

```
🔧 Function refs:
  specbridge/core/__init__.py::TraceNode      → docs.en.02-data-model.1.2.1
  specbridge/infer/__init__.py::_tokenize     → docs.en.05-heuristic-matching.1.4
```

関数ノードはIDに `::` を含む（`file.py::function_name`）ことで識別されます。ファイルレベルのエッジと共に表示され、`heuristic:funcname` マッチのエビデンスを含みます。

**`--top N` 使用時:**

`max_nodes` が設定されている場合、カテゴリごとに上位N件のみが表示され、切り捨て注釈が付きます：

```
  ... and 3 more specs
  ... and 5 more code files
```

### 2.1 色分けカバレッジ
<!-- @impl specbridge/outputs/text.py::render_one_line_coverage -->

カバレッジ統計に視覚インジケータが含まれるようになりました：

| カバレッジ | インジケータ | 意味 |
|-----------|------------|------|
| ≥ 80% | 🟢 緑 | 良好なカバレッジ |
| ≥ 50% | 🟡 黄 | 中程度のカバレッジ |
| < 50% | 🔴 赤 | 低いカバレッジ |

```
📊 Spec Coverage  🟢
========================================
  Total specs:  12
  Covered:      10
  Orphan specs: 2
  Coverage:     83.3%
```

### 2.2 1行CIサマリー

`render_one_line_coverage()` 関数は、CI対応のコンパクトな1行を生成します：

```
🟢 Coverage: 83.3% (10/12) | Specs: 12 | Code refs: 45 | 🟡 3 total orphans
```

`specbridge analyze --summary-only` で使用されます。

## 3. JSON出力 (`outputs/json_out.py`)
<!-- @impl specbridge/outputs/json_out.py::render_json -->

機械処理向けの構造化JSON。

**出力構造:**

```json
{
  "specbridge_version": "1.0.0",
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
        "specbridge_version": "1.0.0",
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
- **`--dry-run` サポート** — ディスクに保存せずにプレビュー

### D3.jsの実装
<!-- @impl specbridge/outputs/html.py::render_html -->

HTMLはCDN（`https://d3js.org/d3.v7.min.js`）から読み込まれるD3.js v7を使用します。グラフは以下を使用：

- `d3.forceSimulation` with:
  - `forceLink`（間隔: 120px）
  - `forceManyBody`（強度: -300）
  - `forceCenter`（ビューポート中央）
  - `forceCollide`（半径30px）
- 関係タイプごとのSVGマーカー（矢印用）
- ハイライト効果用のCSSトランジション

### 出力場所
<!-- @impl specbridge/outputs/html.py::write_html_output -->

HTMLファイルは `.specbridge/trace.html` に保存されます（`--dry-run` が設定されていない場合）：

```python
if dry_run:
    click.echo("   📄 HTML output generated (--dry-run, not saved)", err=True)
else:
    out_path = root / ".specbridge" / "trace.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    webbrowser.open(f"file://{out_path.resolve()}")
```

## 5. Rich進捗ユーティリティ (`outputs/rich_utils.py`) ✨ v1.0新機能
<!-- @impl specbridge/outputs/rich_utils.py -->
<!-- @impl specbridge/outputs/rich_utils.py::progress_spinner -->
<!-- @impl specbridge/outputs/rich_utils.py::progress_bar -->
<!-- @impl specbridge/outputs/rich_utils.py::get_console -->

長時間実行操作のためのRichベースの進捗表示を提供する新しいモジュール。

### スピナー

不確定な進捗用：

```python
with progress_spinner("🔍 プロジェクトをスキャン中..."):
    # 長時間操作
    result = do_work()
```

### プログレスバー

既知のステップ数がある確定進捗用：

```python
with progress_bar("ファイルを分析中...", total=len(files)) as (progress, task):
    for f in files:
        # ファイルを処理
        progress.advance(task)
```

### コンソール

スタイル付き出力のための共有Rich Consoleインスタンス（デフォルトでstderr）：

```python
from specbridge.outputs.rich_utils import get_console
console = get_console()
```

## 6. 証拠の表示

3つの出力形式すべてに証拠情報が含まれます：

| 形式 | 証拠の表示 |
|------|------------|
| **テキスト** | 各エッジの下に `∵ kind: value` 行 |
| **JSON** | 各エッジオブジェクトの `evidence` 配列 |
| **HTML** | ホバーツールチップ + エッジラベル |

## 7. テキスト vs JSON vs HTML

| 機能 | テキスト | JSON | HTML |
|------|---------|------|------|
| **人間の可読性** | ★★★ | ★ | ★★★（インタラクティブ） |
| **機械解析** | ★ | ★★★ | ★ |
| **ファイルサイズ** | 小 | 中 | 大（約30KB） |
| **外部依存** | なし | なし | D3.js（CDN） |
| **出力場所** | stdout | stdout | `.specbridge/trace.html` |
| **パイプ連鎖** | ✓ | ✓ (jq) | ✗ |
| **CI対応** | ✓（テキスト解析） | ✓（JSONパーサー） | ✗ |
| **サマリー専用モード** | ✓ | N/A | N/A |
