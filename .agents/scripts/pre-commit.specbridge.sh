#!/bin/sh
# specbridge pre-commit hook
# Blocks commits when trace drift is detected.
#
# Install: ln -sf ../../scripts/pre-commit.specbridge.sh .git/hooks/pre-commit
# Or copy: cp .agents/scripts/pre-commit.specbridge.sh .git/hooks/pre-commit

set -e

echo "🔍 specbridge: Checking trace drift..."

# Check if snapshot exists; if not, create one
if [ ! -f .specbridge/snapshot.json ]; then
  echo "   📸 First run — creating baseline snapshot..."
  specbridge snapshot > /dev/null 2>&1
  echo "   ✅ Baseline created. Commit this snapshot with your changes."
  exit 0
fi

# Take a fresh snapshot to compare against the committed baseline
specbridge snapshot > /dev/null 2>&1

# Check for drift against the snapshot
if ! specbridge drift --gate > /dev/null 2>&1; then
  echo ""
  echo "❌ specbridge: Drift detected between snapshot and current state!"
  echo "   Run 'specbridge drift' to see what changed."
  echo "   If changes are intentional, run 'specbridge snapshot' to update the baseline."
  echo ""
  exit 1
fi

echo "✅ specbridge: No drift detected."
exit 0
