#!/bin/sh
# specbridge pre-commit hook
# Blocks commits when trace drift is detected between specs and code.
#
# When run inside the specbridge development repository, also:
#   - Validates branch name follows convention (feat/, fix/, ...)
#   - Warns when source code changed but docs/ not updated
#
# Install for downstream users:  specbridge setup
# Install for specbridge devs:    sh scripts/install-hooks.sh

set -e

# ── Detect if we're inside the specbridge development repo ──
# The presence of specbridge/cli.py at the repo root means this is
# the specbridge source repository itself (not a downstream project).
IS_SPECBRIDGE_REPO=0
if [ -f "specbridge/cli.py" ]; then
  IS_SPECBRIDGE_REPO=1
fi

# ── 1. Branch name validation (specbridge repo only) ──
if [ "$IS_SPECBRIDGE_REPO" -eq 1 ]; then
  BRANCH=$(git symbolic-ref --short HEAD 2>/dev/null || echo "detached")

  case "$BRANCH" in
    main|dependabot/*)
      ;; # main is allowed (rare direct commits); dependabot is auto-generated
    feat/*|fix/*|chore/*|docs/*|refactor/*)
      ;; # Convention-compliant
    *)
      echo ""
      echo "❌ Branch name '$BRANCH' doesn't match convention."
      echo "   Allowed patterns:"
      echo "     feat/<desc>     New feature"
      echo "     fix/<desc>      Bug fix"
      echo "     chore/<desc>    CI, maintenance, refactoring"
      echo "     docs/<desc>     Documentation-only changes"
      echo "     refactor/<desc> Code restructuring"
      echo "     main            (direct push exceptions)"
      echo "     dependabot/*    (auto-generated)"
      echo ""
      echo "   Run 'git branch -m <correct-name>' to rename,"
      echo "   or 'git commit --no-verify' to bypass this check."
      echo ""
      exit 1
      ;;
  esac
fi

SNAP=".specbridge/snapshot.json"

# ── 2. Doc sync warning (specbridge repo only) ──
if [ "$IS_SPECBRIDGE_REPO" -eq 1 ]; then
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
fi

# ── 3. Drift gate (universal) ──
if [ ! -f "$SNAP" ]; then
  echo "   📸 No baseline found."
  echo "   Run 'specbridge snapshot && git add .specbridge/' first."
  exit 0
fi

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
