#!/bin/sh
# Install specbridge git hooks
# Usage: sh scripts/install-hooks.sh

set -e

# Make sure we're in the project root
if [ ! -d ".git" ]; then
  echo "❌ Run this script from the project root (where .git/ is)."
  exit 1
fi

# ── Helper: install a single hook ──
install_hook() {
  SRC="$1"
  NAME=$(basename "$SRC" .specbridge.sh)  # e.g., "pre-commit.specbridge.sh" → "pre-commit"
  DST=".git/hooks/$NAME"

  if [ ! -f "$SRC" ]; then
    echo "❌ $SRC not found. Have you run this from the project root?"
    exit 1
  fi

  if [ -f "$DST" ] && [ ! -L "$DST" ]; then
    echo "⚠️  $DST already exists (not a symlink). Backing up to ${DST}.bak"
    mv "$DST" "${DST}.bak"
  fi

  ln -sf "../../$SRC" "$DST"
  chmod +x "$DST"
  echo "✅ Installed $NAME hook: $DST → $SRC"
}

install_hook ".agents/scripts/pre-commit.specbridge.sh"
install_hook ".agents/scripts/pre-push.specbridge.sh"

# ── Install Hermes skill (if Hermes skills directory exists) ──
SKILL_SRC=".agents/skills/specbridge"
SKILL_DST="$HOME/.hermes/skills/software-development/specbridge"
if [ -d "$HOME/.hermes/skills" ]; then
  mkdir -p "$HOME/.hermes/skills/software-development"
  if [ -L "$SKILL_DST" ] || [ ! -e "$SKILL_DST" ]; then
    ln -sf "$(pwd)/$SKILL_SRC" "$SKILL_DST"
    echo "✅ Installed Hermes skill: $SKILL_DST → $(pwd)/$SKILL_SRC"
  else
    echo "⚠️  $SKILL_DST already exists (not a symlink). Skipping."
  fi
fi

echo ""
echo "📋 Active hooks:"
ls -la .git/hooks/ | grep -E "pre-commit|pre-push" || true
echo ""
echo "Test pre-commit:  git commit --allow-empty -m 'test specbridge hook'"
echo "Test pre-push:    git push origin main (should be blocked)"
