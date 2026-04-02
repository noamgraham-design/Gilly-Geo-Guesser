#!/usr/bin/env bash
# deploy.sh — Copy game files to the deployment repo and push.
#
# Usage: ./deploy.sh [commit message]
#   ./deploy.sh
#   ./deploy.sh "Add daily challenge improvements"

set -euo pipefail

DEPLOY_REPO="https://github.com/gillyisraelquiz/Gilly-Israel-Quiz.git"
DEPLOY_FILES=(index.html towns.js sw.js manifest.json)
TMPDIR_NAME="$(mktemp -d)"
SOURCE_COMMIT="$(git rev-parse --short HEAD)"
SOURCE_BRANCH="$(git rev-parse --abbrev-ref HEAD)"

# Use provided message or auto-generate from latest commit
if [ $# -ge 1 ]; then
  MSG="$1"
else
  MSG="$(git log -1 --pretty=%s) (from ${SOURCE_BRANCH}@${SOURCE_COMMIT})"
fi

cleanup() { rm -rf "$TMPDIR_NAME"; }
trap cleanup EXIT

echo "→ Cloning deployment repo..."
git clone --depth=1 "$DEPLOY_REPO" "$TMPDIR_NAME"

echo "→ Copying files: ${DEPLOY_FILES[*]}"
for f in "${DEPLOY_FILES[@]}"; do
  if [ ! -f "$f" ]; then
    echo "ERROR: $f not found in source repo" >&2
    exit 1
  fi
  cp "$f" "$TMPDIR_NAME/$f"
done

echo "→ Committing..."
cd "$TMPDIR_NAME"
git add "${DEPLOY_FILES[@]}"

if git diff --cached --quiet; then
  echo "Nothing changed — deployment repo is already up to date."
  exit 0
fi

git commit -m "$MSG"

echo "→ Pushing to deployment repo..."
git push origin HEAD

echo "✓ Deployed: $MSG"
