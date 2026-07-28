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
if [ -d "$HOME/.local/bin" ]; then
    export PATH="$HOME/.local/bin:$PATH"
fi
if [ -d "$HOME/Library/Python/3.12/bin" ]; then
    export PATH="$HOME/Library/Python/3.12/bin:$PATH"
fi
if [ -d "$HOME/Library/Python/3.11/bin" ]; then
    export PATH="$HOME/Library/Python/3.11/bin:$PATH"
fi
if [ -d "$HOME/Library/Python/3.10/bin" ]; then
    export PATH="$HOME/Library/Python/3.10/bin:$PATH"
fi
if [ -d "$HOME/Library/Python/3.9/bin" ]; then
    export PATH="$HOME/Library/Python/3.9/bin:$PATH"
fi

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
            for _pb in "$HOME/.local/bin" "$HOME/.local/share/pipx/venvs/specbridge/bin"; do
                if [ -f "$_pb/specbridge" ]; then
                    PIPX_BIN="$_pb"
                    break
                fi
            done
            if [ -n "$PIPX_BIN" ]; then
                export PATH="$(dirname "$PIPX_BIN"):$PATH"
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
            for _pb in "$HOME/.local/bin" "$HOME/.local/share/pipx/venvs/specbridge/bin"; do
                if [ -f "$_pb/specbridge" ]; then
                    PIPX_BIN="$_pb"
                    break
                fi
            done
            if [ -n "$PIPX_BIN" ]; then
                export PATH="$(dirname "$PIPX_BIN"):$PATH"
            fi
        fi
        if command -v specbridge >/dev/null 2>&1; then
            ok "specbridge installed ($(specbridge --version 2>/dev/null || echo "?"))"
        else
            # Try common pip --user binary paths
            for _p in "$HOME/.local/bin" "$HOME/Library/Python/3.12/bin" "$HOME/Library/Python/3.11/bin" "$HOME/Library/Python/3.10/bin" "$HOME/Library/Python/3.9/bin"; do
                if [ -f "$_p/specbridge" ]; then
                    export PATH="$(dirname "$_p"):$PATH"
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
    return 1
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
    ok "$SBRIDGE_YAML already exists (skipping)"
else
    cat > "$SBRIDGE_YAML" <<EOF
# specbridge configuration — auto‑generated by setup.sh
spec_dirs:
  - $SPEC_DIRS
source_dirs:
  - $SOURCE_DIRS
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
EOF
    ok "$SBRIDGE_YAML created"
fi

# ── 4. Install pre‑commit hook ─────────────────────────────────────────────────
header "4. Installing pre-commit hook"
HOOK_SRC=".agents/scripts/pre-commit.specbridge.sh"
HOOK_DST=".git/hooks/pre-commit"

if [ ! -d ".git" ]; then
    warn "Not a git repository — skipping hook (run 'git init' first)"
elif [ -f "$HOOK_SRC" ]; then
    # specbridge repo itself — local install
    mkdir -p ".git/hooks"
    ln -sf "../../$HOOK_SRC" "$HOOK_DST"
    chmod +x "$HOOK_DST"
    ok "Pre-commit hook installed ($HOOK_DST → $HOOK_SRC)"
else
    # Downstream project — download hook
    mkdir -p ".git/hooks" ".agents/scripts"
    HOOK_URL="https://raw.githubusercontent.com/nekolife1984/specbridge/main/.agents/scripts/pre-commit.specbridge.sh"
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL "$HOOK_URL" -o ".agents/scripts/pre-commit.specbridge.sh"
    elif command -v wget >/dev/null 2>&1; then
        wget -q "$HOOK_URL" -O ".agents/scripts/pre-commit.specbridge.sh"
    else
        fail "Need curl or wget to download the hook"
    fi
    chmod +x ".agents/scripts/pre-commit.specbridge.sh"
    ln -sf "../../.agents/scripts/pre-commit.specbridge.sh" "$HOOK_DST"
    ok "Pre-commit hook downloaded and installed"
fi

# ── 5. Deploy AGENTS.md ────────────────────────────────────────────────────────
header "5. Deploying AGENTS.md"
AGENTS_SRC="AGENTS.md"
SENTINEL_MARKER="<!-- specbridge -->"

if [ -f "$AGENTS_SRC" ]; then
    # 既存ファイル → センチネルマーカーで追跡要否判断
    if grep -qF "$SENTINEL_MARKER" "$AGENTS_SRC" 2>/dev/null; then
        ok "AGENTS.md already contains specbridge section (marker found, skipping)"
    else
        # マーカーなし → 追記
        cat >> "$AGENTS_SRC" <<'AGENTS'

<!-- specbridge -->
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
AGENTS
        ok "AGENTS.md updated with specbridge section (appended)"
    fi
else
    # 新規作成
    cat > "$AGENTS_SRC" <<'AGENTS'
<!-- specbridge -->
<!-- This section is auto‑managed by `specbridge setup`. Do not remove the marker. -->

# Project Guide

This project uses **specbridge** for spec↔code traceability.

## 🔴 必須ルール（コード変更前後）

```
コードを変更する前に → 仕様書を確認・更新する
コードを変更したら  → specbridge drift で解離がないか確認する
```

## 🚀 セッションライフサイクル（AIエージェント用）

### セッション開始時

```bash
specbridge snapshot --reason "Session: <今回やること>"
```

### セッション終了時

```bash
specbridge drift
```

drift があれば → 先に設計書を直すこと。コードだけ直してコミットしない。

1. `specbridge snapshot --reason "変更内容"` で現状を保存
2. コードを書く
3. `specbridge drift` で解離チェック
4. 解離があれば設計書を先に直す
5. `git commit`（pre-commit hook が自動チェック）

## 📋 よく使うコマンド

| 目的 | コマンド |
|------|---------|
| 分析 | `specbridge analyze --merge` |
| 影響調査 | `specbridge impact --spec-id <id>` |
| カバレッジ | `specbridge coverage` |
| スナップショット | `specbridge snapshot --reason "..."` |
| ドリフト検出 | `specbridge drift` |
| CIゲート | `specbridge drift --git-base HEAD --gate` |
AGENTS
    ok "AGENTS.md created"
fi

# ── 6. Deploy Hermes skill ────────────────────────────────────────────────────
header "6. Deploying Hermes skill"
SKILL_DEPLOYED=false
if [ -d "$HOME/.hermes/skills" ]; then
    SKILL_DIR="$HOME/.hermes/skills/software-development/specbridge"
    if [ -d ".agents/skills/specbridge" ]; then
        # specbridge repo itself
        mkdir -p "$HOME/.hermes/skills/software-development"
        ln -sf "$(pwd)/.agents/skills/specbridge" "$SKILL_DIR"
        ok "Hermes skill linked (repo → $SKILL_DIR)"
        SKILL_DEPLOYED=true
    elif command -v curl >/dev/null 2>&1; then
        mkdir -p "$SKILL_DIR"
        SKILL_URL="https://raw.githubusercontent.com/nekolife1984/specbridge/main/.agents/skills/specbridge/SKILL.md"
        curl -fsSL "$SKILL_URL" -o "$SKILL_DIR/SKILL.md"
        if [ -f "$SKILL_DIR/SKILL.md" ]; then
            ok "Hermes skill downloaded → $SKILL_DIR"
            SKILL_DEPLOYED=true
        else
            warn "Download failed — check network or install manually"
        fi
    else
        warn "Cannot download Hermes skill (no curl). Install manually:"
        warn "  mkdir -p ~/.hermes/skills/software-development/specbridge"
        warn "  # Download https://raw.githubusercontent.com/nekolife1984/specbridge/main/.agents/skills/specbridge/SKILL.md"
    fi
else
    warn "~/.hermes/ not found — skipping Hermes skill"
fi

# ── 7. Initial snapshot ────────────────────────────────────────────────────────
header "7. Taking initial snapshot"
SNAP=".specbridge/snapshot.json"
if [ -f "$SNAP" ]; then
    ok "Snapshot already exists (run 'specbridge snapshot' to update)"
else
    if command -v specbridge >/dev/null 2>&1; then
        specbridge snapshot --reason "Initial setup" 2>&1 || warn "snapshot failed — you can run it manually"
        if [ -f "$SNAP" ]; then
            ok "Initial snapshot saved to $SNAP"
        fi
    else
        warn "specbridge not in PATH — run 'specbridge snapshot' manually"
    fi
fi

# ── 8. CI workflow (optional) ─────────────────────────────────────────────────
header "8. CI workflow (GitHub Actions)"
CI_FILE=""
if [ -d ".github/workflows" ]; then
    CI_FILE=".github/workflows/specbridge-trace.yml"
    if [ -f "$CI_FILE" ]; then
        ok "CI workflow already exists ($CI_FILE)"
    elif [ "${CI_SETUP:-}" = "1" ]; then
        # Non‑interactive mode (specbridge setup --ci): auto‑create
        mkdir -p ".github/workflows"
        cat > "$CI_FILE" <<'CIYAML'
name: specbridge trace-gate

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  trace-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install git+https://github.com/nekolife1984/specbridge.git
      - run: specbridge snapshot
      - run: specbridge drift --gate
      - run: specbridge analyze --merge --top 10
CIYAML
        ok "CI workflow created: $CI_FILE"
        printf "\n   ${YELLOW}⚠️   Remember to add 'trace-gate' to branch protection rules!${NC}\n"
    else
        printf "${YELLOW}?${NC} Add specbridge traceability gate to CI? [Y/n] "
        read -r CI_CHOICE
        case "$CI_CHOICE" in
            n|N|no) info "Skipping CI setup" ;;
            *)
                mkdir -p ".github/workflows"
                cat > "$CI_FILE" <<'CIYAML'
name: specbridge trace-gate

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  trace-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install git+https://github.com/nekolife1984/specbridge.git
      - run: specbridge snapshot
      - run: specbridge drift --gate
      - run: specbridge analyze --merge --top 10
CIYAML
                ok "CI workflow created: $CI_FILE"
                printf "\n   ${YELLOW}⚠️   Remember to add 'trace-gate' to branch protection rules!${NC}\n"
                ;;
        esac
    fi
else
    warn "No .github/workflows/ — skipping CI workflow"
fi

# ── 9. Graphify adapter (optional) ─────────────────────────────────────────────
header "9. Graphify adapter (AST code graph)"
if [ "${CI_SETUP:-}" != "1" ]; then
    printf "${YELLOW}?${NC} Install graphify for deeper AST-based code analysis? [y/N] "
    read -r GFX_CHOICE
else
    GFX_CHOICE="n"
fi
case "$GFX_CHOICE" in
    y|Y|yes)
        if command -v pipx >/dev/null 2>&1; then
            if command -v graphify >/dev/null 2>&1 || [ -f "$HOME/.local/bin/graphify" ]; then
                ok "graphify already installed ($(graphify --version 2>/dev/null))"
            else
                info "Installing graphify via pipx …"
                pipx install graphifyy 2>&1 | tail -1
                if command -v graphify >/dev/null 2>&1; then
                    ok "graphify installed ($(graphify --version 2>/dev/null))"
                else
                    warn "pipx install finished but 'graphify' not in PATH."
                    warn "Try: pipx install graphifyy"
                fi
            fi
            info "You can now use graphify with: specbridge analyze --merge"
        else
            warn "pipx not found — install it first: brew install pipx && pipx ensurepath"
            warn "Then run: pipx install graphifyy"
        fi
        ;;
    *) info "Skipping graphify install" ;;
esac

# ── Done ───────────────────────────────────────────────────────────────────────
header "🎉 specbridge setup complete!"
cat <<SUMMARY

  ${BOLD}Next steps:${NC}

    1. Review ${CYAN}.specbridge.yaml${NC} and adjust paths if needed
    2. Run ${CYAN}specbridge analyze --merge${NC} to see your trace graph
    3. Make your first commit — the pre‑commit hook will check drift
    4. (Optional) Add ${CYAN}specbridge impact${NC} to your AI agent workflow

  ${BOLD}Files created:${NC}
$(for f in "$SBRIDGE_YAML" "$AGENTS_SRC" "$SNAP" "$CI_FILE"; do
    [ -f "$f" ] && echo "    • $f"
done)
  ${BOLD}Hooks:${NC}
    • pre-commit → specbridge drift --git-base HEAD --gate

  ${BOLD}AI agents:${NC}
    • AGENTS.md → read by Hermes, OpenCode, Claude Code, Cursor, Codex
$(if [ "$SKILL_DEPLOYED" = "true" ]; then echo "    • Hermes skill → load with: ${CYAN}skill_view(name='specbridge')${NC}"; fi)

SUMMARY
