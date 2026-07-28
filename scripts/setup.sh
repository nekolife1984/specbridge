#!/bin/sh
# specbridge — one‑command setup for a new project
# ==================================================
# Usage:
#   bash <(curl -fsSL https://raw.githubusercontent.com/nekolife1984/specbridge/main/scripts/setup.sh)
#   # or, after pip install:
#   specbridge setup
#
# What it does:
#   1. Install / verify specbridge is available
#   2. Detect source directories (src/, lib/, app/, …)
#   3. Detect spec directories (docs/, spec/, specs/, …)
#   4. Create .specbridge.yaml
#   5. Install pre‑commit drift hook
#   6. Deploy AGENTS.md (AI‑agent workflow guide)
#   7. Deploy Hermes skill (if ~/.hermes/ exists)
#   8. Take initial snapshot
#   9. Offer CI workflow setup
#  10. Offer graphify (AST code graph) install
#
# Safe to re‑run — idempotent.

set -e

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

info()  { printf "${CYAN}ℹ️  ${NC}%s\n" "$*"; }
ok()    { printf "${GREEN}✅${NC} %s\n" "$*"; }
warn()  { printf "${YELLOW}⚠️  ${NC}%s\n" "$*"; }
fail()  { printf "${RED}❌${NC} %s\n" "$*"; exit 1; }
header(){ printf "\n${BOLD}━━━ %s ━━━${NC}\n" "$*"; }

# ── 0. Pre‑flight checks ────────────────────────────────────────────
PROJECT_DIR="${1:-$(pwd)}"
cd "$PROJECT_DIR" 2>/dev/null || fail "Directory '$PROJECT_DIR' not found"

header "specbridge setup — $PROJECT_DIR"

# ── 0.5 Sanitize PATH for this installer ───────────────────────────────────────
# Hermes / uv / venv に入った古い specbridge が PATH 先頭を占拠していると、
# インストーラが最新版を誤探する。pipx / pip --user のバイナリが
# 優先されるように PATH 先頭に追加する。
_prepend_path() {
    case ":$PATH:" in
        *":$1:"*) ;;
        *) export PATH="$1:$PATH" ;;
    esac
}
[ -d "$HOME/.local/bin" ] && _prepend_path "$HOME/.local/bin"
[ -d "$HOME/Library/Python/3.12/bin" ] && _prepend_path "$HOME/Library/Python/3.12/bin"
[ -d "$HOME/Library/Python/3.11/bin" ] && _prepend_path "$HOME/Library/Python/3.11/bin"
[ -d "$HOME/Library/Python/3.10/bin" ] && _prepend_path "$HOME/Library/Python/3.10/bin"
[ -d "$HOME/Library/Python/3.9/bin" ] && _prepend_path "$HOME/Library/Python/3.9/bin"

# Bash caches command locations; clear it so PATH changes take effect.
hash -r 2>/dev/null || true

# ── 1. Install / verify specbridge ────────────────────────────────────────────
header "1. Installing specbridge"
INSTALL_URL="git+https://github.com/nekolife1984/specbridge.git"

_should_install=false
_old_ver=""

if command -v specbridge >/dev/null 2>&1; then
    _old_ver=$(specbridge --version 2>/dev/null || echo "?")
    # Check if it's an old version (1.0.x or 0.x — before PEP 668 fix)
    if echo "$_old_ver" | grep -qE "(version )?(1\.0\.|0\.)" 2>/dev/null; then
        info "Old version ($_old_ver) detected — upgrading …"
        _should_install=true
    else
        ok "specbridge already installed ($_old_ver)"
    fi
else
    _should_install=true
fi

if $_should_install; then
    _installed=false

    # Strategy A: pipx (best for global CLI tools)
    if command -v pipx >/dev/null 2>&1; then
        if [ -n "$_old_ver" ]; then
            # アップグレード: pipx upgrade で最新を取得させる
            info "Upgrading via pipx (from $_old_ver) …"
            if pipx upgrade specbridge 2>&1 | tail -3; then
                _installed=true
            fi
        fi
        if ! $_installed; then
            info "Installing via pipx …"
            if pipx install "$INSTALL_URL" --force 2>&1 | tail -1; then
                _installed=true
            fi
        fi
        # pipxインストール後、pipxのバイナリパスをPATH先頭に追加
        # (そうしないとHermes venvなどにある古い specbridge が優先される)
        if $_installed; then
            PIPX_BIN=""
            for _pb in "$HOME/.local/bin/specbridge" "$HOME/.local/share/pipx/venvs/specbridge/bin/specbridge"; do
                if [ -f "$_pb" ]; then
                    PIPX_BIN="$_pb"
                    break
                fi
            done
            if [ -n "$PIPX_BIN" ]; then
                _prepend_path "$(dirname "$PIPX_BIN")"
                hash -r 2>/dev/null || true
                PV=$(specbridge --version 2>/dev/null || echo "?")
                ok "specbridge upgraded via pipx ($PV)"
            fi
        fi
    fi

    # Strategy B: pip inside a virtual environment
    if ! $_installed && [ -n "${VIRTUAL_ENV:-}" ]; then
        info "Installing via pip (inside venv) …"
        if pip install "$INSTALL_URL" 2>&1 | tail -1; then
            _installed=true
        fi
    fi

    # Strategy C: pip --user (bypasses PEP 668 on most systems)
    if ! $_installed; then
        info "Installing via pip --user …"
        if pip3 install --user "$INSTALL_URL" 2>&1 | tail -1; then
            _installed=true
        fi
    fi

    # Strategy D: pip --user --break-system-packages (bypasses Homebrew PEP 668)
    if ! $_installed; then
        info "Installing via pip --user --break-system-packages …"
        if pip3 install --user --break-system-packages "$INSTALL_URL" 2>&1 | tail -1; then
            _installed=true
        fi
    fi

    if $_installed; then
        # pipxでインストールした場合、pipxのバイナリパスが最新版から使えるようにPATH先頭に追加
        if command -v pipx >/dev/null 2>&1; then
            PIPX_BIN=""
            for _pb in "$HOME/.local/bin/specbridge" "$HOME/.local/share/pipx/venvs/specbridge/bin/specbridge"; do
                if [ -f "$_pb" ]; then
                    PIPX_BIN="$_pb"
                    break
                fi
            done
            if [ -n "$PIPX_BIN" ]; then
                _prepend_path "$(dirname "$PIPX_BIN")"
                hash -r 2>/dev/null || true
            fi
        fi
        if command -v specbridge >/dev/null 2>&1; then
            ok "specbridge installed ($(specbridge --version 2>/dev/null || echo "?"))"
        else
            # Try common pip --user binary paths
            for _p in "$HOME/.local/bin" "$HOME/Library/Python/3.12/bin" "$HOME/Library/Python/3.11/bin" "$HOME/Library/Python/3.10/bin" "$HOME/Library/Python/3.9/bin"; do
                if [ -f "$_p/specbridge" ]; then
                    _prepend_path "$_p"
                    hash -r 2>/dev/null || true
                    break
                fi
            done
            if command -v specbridge >/dev/null 2>&1; then
                ok "specbridge found via PATH update"
            else
                warn "specbridge installed but not in PATH."
                warn "  Run this to add pip --user binaries to your PATH:"
                warn "    export PATH=\"\$HOME/Library/Python/3.*/bin:\$PATH\""
                warn "  Or try: python3 -m specbridge --help"
            fi
        fi
    else
        warn "All install methods failed. Try manually:"
        warn "  pip3 install --user $INSTALL_URL"
        warn "  # or"
        warn "  pipx install $INSTALL_URL"
    fi
fi

# ── 2. Detect project structure ────────────────────────────────────────────────
header "2. Detecting project structure"
detect_dir() {
    for d in "$@"; do [ -d "$d" ] && echo "$d" && return 0; done
    return 0
}

SPEC_DIRS="$(detect_dir docs spec specs design)"
SOURCE_DIRS="$(detect_dir src lib app)"

[ -z "$SPEC_DIRS" ]   && SPEC_DIRS="docs"     && info "No spec dir found → default: docs/"
[ -z "$SOURCE_DIRS" ] && SOURCE_DIRS="src"    && info "No source dir found → default: src/"

ok "Spec dirs:   $SPEC_DIRS"
ok "Source dirs: $SOURCE_DIRS"

# ── 3. Create .specbridge.yaml ─────────────────────────────────────────────────
SBRIDGE_YAML=".specbridge.yaml"
header "3. Creating $SBRIDGE_YAML"
if [ -f "$SBRIDGE_YAML" ]; then
    ok "$SBRIDGE_YAML already exists"
else
    cat > "$SBRIDGE_YAML" <<YAML
# specbridge configuration — auto‑generated by setup.sh
spec_dirs:
  - ${SPEC_DIRS% *}
source_dirs:
  - ${SOURCE_DIRS% *}
exclude_dirs:
  - .git
  - node_modules
  - .venv
  - __pycache__
  - dist
  - build
  - .specbridge
  - .egg-info
min_confidence: 0.15
max_output_nodes: 40
min_coverage: 50.0
session_check:
  hooks: []
YAML
    ok "$SBRIDGE_YAML created"
fi

# ── 4. Install pre-commit drift hook ───────────────────────────────────────────
header "4. Installing pre-commit hook"
GIT_DIR=".git"
HOOK_URL="https://raw.githubusercontent.com/nekolife1984/specbridge/main/.agents/scripts/pre-commit.specbridge.sh"
HOOK_FILE="$GIT_DIR/hooks/pre-commit"

if [ ! -d "$GIT_DIR" ]; then
    warn "No .git directory found — skipping pre-commit hook"
else
    if [ -f "$HOOK_FILE" ]; then
        ok "pre-commit hook already exists"
    else
        if curl -fsSL "$HOOK_URL" -o "$HOOK_FILE" 2>/dev/null; then
            chmod +x "$HOOK_FILE"
            ok "Pre-commit hook downloaded and installed"
        else
            warn "Could not download pre-commit hook"
        fi
    fi
fi

# ── 5. Deploy AGENTS.md ────────────────────────────────────────────────────────
header "5. Deploying AGENTS.md"
AGENTS_SRC="AGENTS.md"
SENTINEL_MARKER="<!-- specbridge -->"

AGENTS_SPEC_SECTION='<!-- specbridge -->
<!-- This section is auto‑managed by `specbridge setup`. Do not remove the marker. -->

## specbridge — Spec↔Code Traceability

This project uses **specbridge** for spec↔code traceability.

### 🔴 必須ルール（コード変更前後）

```
コードを変更する前に → 仕様書を確認・更新する
コードを変更したら  → specbridge drift で解離がないか確認する
```

### 🚀 セッションライフサイクル（AIエージェント用）

**セッション開始時:**
```bash
specbridge snapshot --reason "Session: <今回やること>"
```

**セッション終了時:**
```bash
specbridge drift
```

drift があれば → 先に設計書を直すこと。コードだけ直してコミットしない。

1. `specbridge snapshot --reason "変更内容"` で現状を保存
2. コードを書く
3. `specbridge drift` で解離チェック
4. 解離があれば設計書を先に直す
5. `git commit`（pre-commit hook が自動チェック）

### 📋 よく使うコマンド

| 目的 | コマンド |
|------|---------|
| 分析 | `specbridge analyze --merge` |
| 影響調査 | `specbridge impact --spec-id <id>` |
| カバレッジ | `specbridge coverage` |
| スナップショット | `specbridge snapshot --reason "..."` |
| ドリフト検出 | `specbridge drift` |
| CIゲート | `specbridge drift --git-base HEAD --gate` |
'

if [ -f "$AGENTS_SRC" ]; then
    if grep -qF "$SENTINEL_MARKER" "$AGENTS_SRC" 2>/dev/null; then
        ok "AGENTS.md already contains specbridge section (marker found, skipping)"
    else
        printf "\n%s\n" "$AGENTS_SPEC_SECTION" >> "$AGENTS_SRC"
        ok "AGENTS.md updated with specbridge section (appended)"
    fi
else
    cat > "$AGENTS_SRC" <<AGENTS
<!-- specbridge -->
<!-- This section is auto‑managed by \`specbridge setup\`. Do not remove the marker. -->

# Project Guide

This project uses **specbridge** for spec↔code traceability.

## 🔴 必須ルール（コード変更前後）

\`\`\`
コードを変更する前に → 仕様書を確認・更新する
コードを変更したら  → specbridge drift で解離がないか確認する
\`\`\`

## 🚀 セッションライフサイクル（AIエージェント用）

### セッション開始時

\`\`\`bash
specbridge snapshot --reason "Session: <今回やること>"
\`\`\`

### セッション終了時

\`\`\`bash
specbridge drift
\`\`\`

drift があれば → 先に設計書を直すこと。コードだけ直してコミットしない。

1. \`specbridge snapshot --reason "変更内容"\` で現状を保存
2. コードを書く
3. \`specbridge drift\` で解離チェック
4. 解離があれば設計書を先に直す
5. \`git commit\`（pre-commit hook が自動チェック）

## 📋 よく使うコマンド

| 目的 | コマンド |
|------|---------|
| 分析 | \`specbridge analyze --merge\` |
| 影響調査 | \`specbridge impact --spec-id <id>\` |
| カバレッジ | \`specbridge coverage\` |
| スナップショット | \`specbridge snapshot --reason "..."\` |
| ドリフト検出 | \`specbridge drift\` |
| CIゲート | \`specbridge drift --git-base HEAD --gate\` |
AGENTS
    ok "AGENTS.md created"
fi

# ── 6. Deploy Hermes skill (if Hermes is installed) ────────────────────────────
header "6. Deploying Hermes skill"
HERMES_SKILLS_DIR="$HOME/.hermes/skills/software-development"
SKILL_URL="https://raw.githubusercontent.com/nekolife1984/specbridge/main/.agents/skills/specbridge/SKILL.md"

if [ ! -d "$HOME/.hermes" ]; then
    info "Hermes not detected — skipping skill deployment"
else
    mkdir -p "$HERMES_SKILLS_DIR/specbridge"
    if curl -fsSL "$SKILL_URL" -o "$HERMES_SKILLS_DIR/specbridge/SKILL.md" 2>/dev/null; then
        ok "Hermes skill downloaded → $HERMES_SKILLS_DIR/specbridge"
    else
        warn "Could not download Hermes skill"
    fi
fi

# ── 7. Take initial snapshot ───────────────────────────────────────────────────
header "7. Taking initial snapshot"
if command -v specbridge >/dev/null 2>&1; then
    if specbridge snapshot --reason "Initial snapshot after setup" 2>&1 | tail -5; then
        ok "Initial snapshot taken"
    else
        warn "Could not take initial snapshot"
    fi
else
    warn "specbridge not in PATH — skipping initial snapshot"
fi

# ── 8. Offer CI workflow setup ─────────────────────────────────────────────────
header "8. CI workflow setup"
CI_DIR=".github/workflows"
CI_FILE="$CI_DIR/specbridge.yml"
CI_URL="https://raw.githubusercontent.com/nekolife1984/specbridge/main/.github/workflows/specbridge.yml"

if [ -f "$CI_FILE" ]; then
    ok "CI workflow already exists"
else
    printf "Add GitHub Actions workflow? [y/N] "
    read -r _ci_answer
    if [ "$_ci_answer" = "y" ] || [ "$_ci_answer" = "Y" ]; then
        mkdir -p "$CI_DIR"
        if curl -fsSL "$CI_URL" -o "$CI_FILE" 2>/dev/null; then
            ok "CI workflow downloaded → $CI_FILE"
        else
            warn "Could not download CI workflow"
        fi
    else
        info "Skipping CI workflow"
    fi
fi

# ── 9. Offer graphify install ──────────────────────────────────────────────────
header "9. Optional: graphify (AST code graph)"
if command -v graphify >/dev/null 2>&1; then
    ok "graphify already installed"
else
    printf "Install graphify for AST-level traceability? [y/N] "
    read -r _gf_answer
    if [ "$_gf_answer" = "y" ] || [ "$_gf_answer" = "Y" ]; then
        if command -v pipx >/dev/null 2>&1; then
            info "Installing graphify via pipx …"
            pipx install graphify 2>&1 | tail -1 || warn "graphify install failed"
        else
            pip3 install --user graphify 2>&1 | tail -1 || warn "graphify install failed"
        fi
    else
        info "Skipping graphify"
    fi
fi

# ── Done ───────────────────────────────────────────────────────────────────────
header "Done"
ok "specbridge setup complete"
info "Next steps:"
echo "  1. Run: specbridge snapshot --reason \"Session: <task>\""
echo "  2. Make code changes"
echo "  3. Run: specbridge drift"
echo "  4. Commit when drift passes"
