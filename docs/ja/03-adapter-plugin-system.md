# アダプタ＆プラグインシステム

> **日付:** 2026-07-26
> **バージョン:** 0.0.1.dev0

## 1. 概要

specbridgeは**アダプタパターン**を使用して複数のSSD（Spec-Driven Development）フレームワークをサポートします。各アダプタは特定のフレームワークのプロジェクト構造を検出・分析する方法を把握しています。このシステムはPythonのエントリポイントを介して拡張可能で、サードパーティパッケージがspecbridge本体を変更せずに独自のアダプタを登録できます。

```
┌──────────────────────────────────────────────┐
│               アダプタレイヤー                 │
│                                                │
│  ┌──────────────┐   ┌──────────────┐          │
│  │ ヒューリス   │   │  Spectra     │          │
│  │ ティック     │   │  (内蔵)      │          │
│  │ (内蔵)       │   │              │          │
│  └──────┬───────┘   └──────┬───────┘          │
│         │                  │                   │
│         ▼                  ▼                   │
│  ┌──────────────────────────────────────────┐  │
│  │       ProjectAdapter (ABC)                │  │
│  │  ┌─ detect(directory) → float            │  │
│  │  └─ analyze(directory) → TraceGraph      │  │
│  └──────────────────────────────────────────┘  │
│         │                                       │
│         ▼                                       │
│  ┌──────────────────────────────────────────┐  │
│  │       プラグイン発見                       │  │
│  │  entry_points(group="specbridge.adapters")│  │
│  └──────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
```

## 2. 抽象基底クラス: `ProjectAdapter`

すべてのアダプタは `adapters/_base.py` の `ProjectAdapter` を継承します：

```python
class ProjectAdapter(ABC):

    @abstractmethod
    def detect(self, directory: str) -> float:
        """このアダプタが*directory*を処理できる信頼度スコア(0.0〜1.0)を返す。
        アダプタは信頼度の高い順に試行され、最初に>0を返したものが使用される。
        高速である必要がある — すべてのanalyze/impact/coverage呼び出しで実行される。"""

    @abstractmethod
    def analyze(self, directory: str) -> TraceGraph:
        """プロジェクト全体の分析。すべてのノードとエッジを含むTraceGraphを返す。"""
```

### 契約

- **`detect()` は高速でなければならない** — CLI起動のたびに実行される。ファイルシステムの走査は数回のstat＋1回の小さなファイル読み取り程度に抑える。
- **`analyze()` は耐障害性を持つこと** — パースエラーを適切にハンドリングし、クラッシュではなく有効な（空でもよい）`TraceGraph` を返す。
- **ツールは読み取り専用** — 仕様やソースディレクトリには決して書き込まない。すべての出力は `guard.py` → `.specbridge/` を経由する。
- **0.0〜1.0のスコアを返す** — 0.0は「このプロジェクトは処理できない」を意味する。高いスコアが優先される。

## 3. 標準搭載アダプタ

### 3.1 HeuristicAdapter（プライマリ）

**ファイル:** `adapters/heuristic.py`

Markdownの仕様書とソースコードがある**あらゆる**プロジェクトで動作するデフォルトアダプタ。タグやアノテーションは不要。

```python
@register
class HeuristicAdapter(ProjectAdapter):
    detect():
        # 戻り値:
        #   0.8: docs/（または spec/）と src/（または lib/, app/）の両方がある場合
        #   0.4: docs/ または src/ のみの場合
        #   0.0: それ以外

    analyze():
        # infer/build_heuristic_graph() に委譲:
        #   1. discover_specs() → Markdown見出しを解析 → SpecCandidate[]
        #   2. discover_code() → ソースディレクトリをスキャン → CodeCandidate[]
        #   3. 4つのヒューリスティック信号で spec ↔ code をマッチング
        #   4. TraceGraph を返す
```

**設計根拠:** HeuristicAdapterは意図的にシンプルで広く適用可能です。**プライマリ**アダプタとして最初にロードされます。タグベースのアダプタはオプションの拡張としてその上にレイヤーされます。

### 3.2 SpectraAdapter

**ファイル:** `adapters/spectra.py`

[spectra](https://github.com/nekolife1984/spectra) フレームワークを使用するプロジェクトを処理します。

```python
@register
class SpectraAdapter(ProjectAdapter):
    detect():
        # 戻り値:
        #   0.95: .spectra/trace-mapping.yaml が存在する場合
        #   0.70: ソースファイルに @impl タグが検出された場合
        #   0.50: .spectra/ ディレクトリは存在するがマッピングがない場合
        #   0.00: それ以外

    analyze():
        # 1. .spectra/trace-mapping.yaml を読み込み → spec + code ノード + マッピングエッジ
        # 2. ソースファイルから @impl, @verifies タグをスキャン
        # 3. Markdownファイルから <!-- @spec -->, <!-- @satisfies -->, _Boundary:_ をスキャン
        # 4. マージされた TraceGraph を返す
```

**サポートするタグ構文:**

| タグ | 場所 | 目的 |
|-----|------|------|
| `# @impl 1.1` / `// @impl 1.1` | ソースコード | コードを仕様にリンク |
| `# @verifies 1.1` / `// @verifies 1.1` | テストコード | テストを仕様にリンク |
| `<!-- @spec 1 -->` | Markdown仕様書 | 仕様セクションを宣言 |
| `<!-- @satisfies AUTH-1 -->` | Markdown設計書 | 設計→仕様エッジ |
| `_Boundary:_ src/path/` | Markdown仕様書 | 許可される実装パスを宣言 |

## 4. アダプタ登録

### 4.1 `@register` デコレータ

内蔵アダプタは `@register` デコレータを使用します：

```python
from specbridge.adapters._base import register, ProjectAdapter

@register
class MyAdapter(ProjectAdapter):
    ...
```

デコレータは**冪等**です — 同じクラスを2回登録しても何も起こりません。

### 4.2 エントリポイント登録（プラグインSDK）

サードパーティパッケージは `pyproject.toml` を介してアダプタを登録します：

```toml
[project.entry-points."specbridge.adapters"]
my_adapter = "my_package.my_adapter:MyAdapter"
```

プラグインクラスは `ProjectAdapter` を継承する必要があります。`@register` デコレータは**不要**です — エントリポイントローダーが自動的に `register()` を呼び出します。

プラグイン発見は**遅延ロード**です — `all_adapters()` または `detect_adapter()` への最初のアクセス時に1回だけ実行されます。

## 5. アダプタ選択

### 5.1 単一アダプタ（デフォルト）

```python
def detect_adapter(directory: str) -> ProjectAdapter | None:
    """登録された全アダプタを試行し、最適なものを返す。"""
    for cls in _ADAPTERS:
        inst = cls()
        score = inst.detect(directory)
        if score > 0:
            scored.append((score, inst))
    scored.sort(key=lambda x: -x[0])
    return scored[0][1] if scored else None
```

呼び出し元: `analyze`, `impact`, `coverage`, `validate-boundary`, `drift --git-base`

### 5.2 マージモード

```python
def detect_all(directory: str) -> list[tuple[float, ProjectAdapter]]:
    """スコアが正の全アダプタを降順で返す。"""

def merge_graphs(graphs: list[TraceGraph]) -> TraceGraph:
    """ノードの和集合 + エッジの連結。
    後続のアダプタのノードが、同じIDの先行ノードを上書きする。"""
```

呼び出し元: `analyze --merge`, `watch`, MCPサーバ

**マージのセマンティクス:**
- ノード: IDによる和集合（後続が先行を上書き）
- エッジ: すべてのグラフの全エッジを追加
- 重複除去は行わない — 同じソース/宛先/関係のエッジが複数存在する可能性あり

## 6. プラグイン発見のライフサイクル

```
┌─────────────┐
│ Python起動   │
└──────┬──────┘
       │
       ▼
┌──────────────────┐
│ adapters/ を     │
│ インポート       │
│ → heuristic.py   │  ← @register 発火
│   を先行インポート│
│ → spectra.py     │  ← @register 発火
│   を先行インポート│
└──────┬──────────┘
       │
       ▼  (最初の all_adapters() または detect_adapter() 呼び出し時)
┌──────────────────────┐
│ _ensure_plugins_     │
│ discovered()         │
│  → discover_plugins()│
│    → importlib       │
│      entry_points()  │
│        "specbridge.  │
│         adapters"    │
│    → ep.load()       │
│    → register(cls)   │
└──────────────────────┘
       │
       ▼
┌──────────────────┐
│ 全アダプタが     │
│ 選択可能に       │
└──────────────────┘
```

## 7. プラグイン作成手順

1. **Pythonパッケージを作成**（`pyproject.toml` を含む）
2. **`ProjectAdapter` を継承** — `detect()` と `analyze()` を実装
3. **エントリポイントを宣言**（`pyproject.toml`）:
   ```toml
   [project.entry-points."specbridge.adapters"]
   my_adapter = "my_package.my_adapter:MyAdapter"
   ```
4. **パッケージをインストール**（specbridgeと同じPython環境に）
5. **読み込みを確認**: `specbridge plugins` → 自分のアダプタが表示される

### プラグインのベストプラクティス

- `detect()` は**高速に保つ** — すべての呼び出しで実行される
- パースエラーは適切に処理 — クラッシュではなく空の `TraceGraph()` を返す
- 配布可能なパッケージにはエントリポイント機構を使用（`@register` ではなく）
- 完全な動作例は `examples/example-plugin/` を参照

## 8. アダプタ比較

| 機能 | HeuristicAdapter | SpectraAdapter |
|------|-----------------|----------------|
| **検出方法** | docs/ + src/ ディレクトリの存在 | `.spectra/trace-mapping.yaml` または `@impl` タグ |
| **タグ必須** | いいえ | 任意（マッピングファイルのみでも可） |
| **信頼度** | 0.4–0.8 | 0.5–0.95 |
| **言語対応** | 18言語 | 18言語（タグ抽出） |
| **エッジソース** | ヒューリスティック（4信号） | 明示的タグ + マッピングファイル |
| **境界検証** | なし | あり（`_Boundary:_` マーカー経由） |
| **設計→仕様エッジ** | なし | あり（`@satisfies`） |
| **ユースケース** | docs + code がある任意のプロジェクト | spectraフレームワークを使用するプロジェクト |
