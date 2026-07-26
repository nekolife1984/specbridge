#!/bin/sh
# Install specbridge git hooks
# Usage: sh scripts/install-hooks.sh

set -e

HOOK_SRC=".agents/scripts/pre-commit.specbridge.sh"
HOOK_DST=".git/hooks/pre-commit"

# Make sure we're in the project root
if [ ! -d ".git" ]; then
  echo "❌ Run this script from the project root (where .git/ is)."
  exit 1
fi

# Check source exists
if [ ! -f "$HOOK_SRC" ]; then
  echo "❌ $HOOK_SRC not found. Have you run this from the project root?"
  exit 1
fi

# Symlink hook
if [ -f "$HOOK_DST" ] && [ ! -L "$HOOK_DST" ]; then
  echo "⚠️  $HOOK_DST already exists (not a symlink). Backing up to ${HOOK_DST}.bak"
  mv "$HOOK_DST" "${HOOK_DST}.bak"
fi

ln -sf "../../$HOOK_SRC" "$HOOK_DST"
chmod +x "$HOOK_DST"
echo "✅ Installed pre-commit hook: $HOOK_DST → $HOOK_SRC"

# Install Hermes skill (if Hermes skills directory exists)
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
echo "Test it with: git commit --allow-empty -m 'test specbridge hook'"
