# specbridge — AI Agent Guide

This project is **specbridge** itself: a spec↔code traceability tool.  
We practice what we preach — specs and code must stay in sync.

---

## 🔴 絶対ルール（Spec-First Development）

```
コードを変更する前に → 仕様書を確認・更新する
コードを変更したら  → specbridge drift で解離がないか確認する
```

1. **仕様書が先、コードは後**
2. **解離があれば設計書を直す。コードだけ直してコミットしない**
3. **pre-commit hook が解離を検出したら、`--no-verify` で逃げない**

---

## ✅ ワークフロー（コード変更のたびに必ず実行）

### ① 変更前にスナップショット

```bash
specbridge snapshot --reason "変更内容の説明"
```

### ② コードを書く（仕様書も同時に更新）

- 新しい機能を追加 → `docs/` に仕様を追加
- 既存の動作を変更 → `docs/` の該当箇所を更新
- Agentは `specbridge impact --spec-id <id>` で影響範囲を事前確認すること

### ③ 変更後にドリフトチェック

```bash
specbridge drift
# 解離があれば: 「📝 設計書更新あり」→ 設計書を直す
# 解離がなければ: ✅ OK
```

### ④ コミット前（hook が自動実行）

```bash
git commit
# → pre-commit hook が specbridge drift --git-base HEAD --gate を実行
# → ❌ 解離あり → commit ブロック（設計書を直してから再実行）
# → ✅ 解離なし → commit 成功
```

---

## 📋 よく使うコマンド

| 目的 | コマンド |
|------|---------|
| プロジェクト全体の分析 | `specbridge analyze --merge` |
| 依存グラフ含む | `specbridge analyze --merge --deps` |
| コールグラフ含む | `specbridge analyze --merge --deps --call-graph` |
| 影響分析 | `specbridge impact --spec-id <id>` |
| 推移的影響 | `specbridge impact --spec-id <id> --call-graph` |
| カバレッジ確認 | `specbridge coverage` |
| スナップショット | `specbridge snapshot --reason "..."` |
| ドリフト検出 | `specbridge drift` |
| CIゲート | `specbridge drift --git-base HEAD --gate` |
| HTML可視化 | `specbridge analyze --merge --format html` |

---

## 🔗 Hermes Agent スキル

Hermes を使っている場合は以下でスキルをロード：

```
skill_view(name='software-development/specbridge')
```

スキルには全コマンドの詳細な説明とトラブルシューティングが含まれている。

---

## 🔖 @impl タグの埋め方

コードと仕様書の対応を明示するには `@impl` タグをソースコードに埋め込む。
specbridge の SpectraAdapter が自動的に読み取って TraceGraph に反映する。

### 構文

| 言語 | 構文 | 例 |
|------|------|-----|
| Python / Ruby / Shell | `# @impl <spec-id>` | `# @impl 1.1` |
| TypeScript / Go / Rust / Java / C# / C++ | `// @impl <spec-id>` | `// @impl 1.1` |
| Markdown（仕様書→コード参照） | `<!-- @impl <file>::<symbol> -->` | `<!-- @impl specbridge/cli.py::main -->` |

### ルール

- **`<spec-id>`** は `docs/en/XX-filename.md` の見出し番号（例: `1.2.3`）
- **複数指定**: `# @impl 1.1, 1.2, 1.3`（カンマ区切り）
- **コードを変更したら、対応する `@impl` タグも必ず更新すること**
- **新しい機能を追加したら、対応する仕様書のセクションに `<!-- @impl path::symbol -->` を追加すること**

### 具体例

```python
# specbridge/adapters/_base.py
@register
def all_adapters() -> list[type[ProjectAdapter]]:  # @impl 3.1
    ...
```

```markdown
<!-- docs/en/03-adapter-plugin-system.md -->
## 3.1 HeuristicAdapter (Primary)
<!-- @impl specbridge/adapters/heuristic.py::HeuristicAdapter -->
<!-- @impl specbridge/adapters/heuristic.py::HeuristicAdapter.analyze -->
```

---

## 🏗 プロジェクト構造（知っておくべき重要パス）

| パス | 内容 |
|------|------|
| `docs/en/` | 設計書（英語） |
| `docs/ja/` | 設計書（日本語） |
| `specbridge/` | コアライブラリ |
| `tests/` | テスト |
| `.specbridge/` | specbridge の出力（git管理） |
| `.agents/scripts/pre-commit.specbridge.sh` | pre-commit hook |
| `.agents/skills/specbridge/SKILL.md` | Hermes スキル |
| `ROADMAP.md` | 開発ロードマップ |

---

## ⚠️ 補足

- **設計書を編集したら必ず `@impl` タグも更新すること**
- `specbridge analyze --merge` でカバレッジが **60%未満**なら設計書かコードに問題がある可能性大
- pre-commit hook に `--no-verify` は禁止（CIで弾かれる）
