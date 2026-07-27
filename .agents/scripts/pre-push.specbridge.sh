#!/bin/sh
# specbridge pre-push hook
# Blocks direct push to main — all changes must go through a PR.
#
# Install: sh scripts/install-hooks.sh
#   or ln -sf ../../.agents/scripts/pre-push.specbridge.sh .git/hooks/pre-push

set -e

echo "🔍 specbridge: Checking push destination..."

z40=0000000000000000000000000000000000000000

while read local_ref local_sha remote_ref remote_sha; do
  case "$remote_ref" in
    refs/heads/main|refs/heads/master)
      # Allow if this is a new branch push (delete marker)
      if [ "$local_sha" = "$z40" ]; then
        continue
      fi
      echo ""
      echo "❌ Direct push to main/master is not allowed."
      echo "   All changes must go through a pull request:"
      echo "     1. Create a feature branch: git checkout -b feat/your-change"
      echo "     2. Commit your changes"
      echo "     3. Push: git push origin feat/your-change"
      echo "     4. Open a PR on GitHub"
      echo ""
      echo "   To bypass this check (emergency only): git push --no-verify origin main"
      echo ""
      exit 1
      ;;
  esac
done

echo "✅ Push allowed."
exit 0
