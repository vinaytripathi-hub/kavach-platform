#!/usr/bin/env bash
# Pre-push hook helper: verify the latest commit on main is GPG-signed.
#
# Per ADR-0006 (Block C) and docs/engineering-handbook.md (Block E), every
# commit on main MUST be GPG-signed. This hook fires on `git push` and
# refuses the push if the latest commit on main is unsigned.
#
# Feature branches (anything other than main) are not enforced here; signing
# on feature branches is recommended but optional.

set -euo pipefail

current_branch=$(git rev-parse --abbrev-ref HEAD)

if [[ "$current_branch" != "main" ]]; then
  echo "Not on main branch (current: $current_branch); skipping GPG signature enforcement."
  exit 0
fi

latest_commit=$(git rev-parse HEAD)

if git verify-commit "$latest_commit" 2>/dev/null; then
  echo "✓ Latest commit ($latest_commit) on main has a Good GPG signature."
  exit 0
else
  echo "✗ Latest commit ($latest_commit) on main is NOT GPG-signed or signature is invalid."
  echo ""
  echo "Per ADR-0006 and docs/engineering-handbook.md, every commit on main"
  echo "must be GPG-signed by an authorized contributor (vinay@aurviaglobal.com"
  echo "during the solo founder phase)."
  echo ""
  echo "To fix:"
  echo "  git commit --amend --no-edit -S    # re-sign the latest commit"
  echo "  git push                            # retry"
  exit 1
fi
