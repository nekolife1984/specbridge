#!/bin/sh
# specbridge pre-commit hook
# Blocks commits when trace drift is detected.
#
# Uses git-base mode: compares working-tree changes against HEAD
# so only touched files are analysed (lightweight).
#
# Install: sh scripts/install-hooks.sh
#   or ln -sf ../../.agents/scripts/pre-commit.specbridge.sh .git/hooks/pre-commit

set -e

SNAP=".specbridge/snapshot.json"

echo "🔍 specbridge: Checking trace drift against HEAD..."

# ── Doc sync check: if code changed, docs should too ──
CHANGED=$(git diff --cached --name-only)
CODE_CHANGED=$(echo "$CHANGED" | grep -c "^specbridge/\|^tests/" || true)
DOCS_CHANGED=$(echo "$CHANGED" | grep -c "^docs/en/\|^docs/ja/" || true)
if [ "$CODE_CHANGED" -gt 0 ] && [ "$DOCS_CHANGED" -eq 0 ]; then
  echo "   ⚠️  Code/tests changed but no docs/ updated!"
  echo "      Run 'git diff --cached --name-only' to see what changed."
  echo "      ➡  Update docs/en/ and docs/ja/ to match the code changes."
  echo "      (Use --no-verify to bypass this warning)"
  echo ""
fi

# No baseline yet — ask user to create one
if [ ! -f "$SNAP" ]; then
  echo "   📸 No baseline found."
  echo "   Run 'specbridge snapshot && git add .specbridge/' first."
  exit 0
fi

# Git-based drift: compare working tree against committed snapshot via HEAD
if ! specbridge drift --git-base HEAD --gate > /dev/null 2>&1; then
  echo ""
  echo "❌ specbridge: Drift detected between snapshot and your changes!"
  echo "   Run 'specbridge drift' to see details."
  echo "   If changes are intentional, run 'specbridge snapshot' to update baseline"
  echo "   and include .specbridge/snapshot.json in your commit."
  echo ""
  exit 1
fi

echo "✅ specbridge: No drift detected — good to commit."
exit 0
