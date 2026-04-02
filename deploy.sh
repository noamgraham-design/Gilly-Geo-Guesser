#!/usr/bin/env bash
# deploy.sh — Push game files to the deployment repo and open a PR.
#
# Requires: DEPLOY_GITHUB_TOKEN env var (PAT for gillyisraelquiz account,
#           with Contents + Pull Requests read/write permissions)
#
# Usage:
#   ./deploy.sh                        # auto-generates PR title from latest commit
#   ./deploy.sh "Add daily challenge"  # custom PR title

set -euo pipefail

DEPLOY_OWNER="gillyisraelquiz"
DEPLOY_REPO="Gilly-Israel-Quiz"
DEPLOY_FILES=(index.html towns.js sw.js manifest.json)
BASE_BRANCH="main"

# ── Auth check ────────────────────────────────────────────────────────────────
if [ -z "${DEPLOY_GITHUB_TOKEN:-}" ]; then
  echo "ERROR: DEPLOY_GITHUB_TOKEN is not set." >&2
  echo "Create a PAT at https://github.com/settings/tokens with Contents + Pull Requests permissions," >&2
  echo "then: export DEPLOY_GITHUB_TOKEN=your_token" >&2
  exit 1
fi

API="https://api.github.com"
AUTH_HEADER="Authorization: Bearer $DEPLOY_GITHUB_TOKEN"
SOURCE_COMMIT="$(git rev-parse --short HEAD)"
SOURCE_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
DEPLOY_BRANCH="deploy/${SOURCE_BRANCH}-${SOURCE_COMMIT}"

# PR title: provided arg or auto-generated from latest commit
if [ $# -ge 1 ]; then
  PR_TITLE="$1"
else
  PR_TITLE="$(git log -1 --pretty=%s)"
fi

# ── Helper: call GitHub API ───────────────────────────────────────────────────
gh_api() {
  local method="$1" path="$2"
  shift 2
  curl -sf -X "$method" \
    -H "$AUTH_HEADER" \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "$API$path" "$@"
}

# ── 1. Get the SHA of the base branch HEAD ───────────────────────────────────
echo "→ Getting base branch SHA..."
BASE_SHA=$(gh_api GET "/repos/$DEPLOY_OWNER/$DEPLOY_REPO/git/ref/heads/$BASE_BRANCH" \
  | grep -o '"sha":"[^"]*"' | head -1 | cut -d'"' -f4)

# ── 2. Create the deploy branch ──────────────────────────────────────────────
echo "→ Creating branch $DEPLOY_BRANCH..."
gh_api POST "/repos/$DEPLOY_OWNER/$DEPLOY_REPO/git/refs" \
  -d "{\"ref\":\"refs/heads/$DEPLOY_BRANCH\",\"sha\":\"$BASE_SHA\"}" > /dev/null

# ── 3. Push each file ─────────────────────────────────────────────────────────
CHANGED=0
for f in "${DEPLOY_FILES[@]}"; do
  if [ ! -f "$f" ]; then
    echo "ERROR: $f not found in source repo" >&2
    exit 1
  fi

  CONTENT=$(base64 < "$f" | tr -d '\n')

  # Get current file SHA in deploy repo (needed for updates)
  FILE_SHA=$(gh_api GET "/repos/$DEPLOY_OWNER/$DEPLOY_REPO/contents/$f?ref=$DEPLOY_BRANCH" \
    2>/dev/null | grep -o '"sha":"[^"]*"' | head -1 | cut -d'"' -f4 || true)

  if [ -n "$FILE_SHA" ]; then
    PAYLOAD="{\"message\":\"Update $f\",\"content\":\"$CONTENT\",\"sha\":\"$FILE_SHA\",\"branch\":\"$DEPLOY_BRANCH\"}"
  else
    PAYLOAD="{\"message\":\"Add $f\",\"content\":\"$CONTENT\",\"branch\":\"$DEPLOY_BRANCH\"}"
  fi

  echo "  → Uploading $f..."
  gh_api PUT "/repos/$DEPLOY_OWNER/$DEPLOY_REPO/contents/$f" -d "$PAYLOAD" > /dev/null
  CHANGED=1
done

if [ "$CHANGED" -eq 0 ]; then
  echo "Nothing to deploy."
  exit 0
fi

# ── 4. Open the PR ────────────────────────────────────────────────────────────
echo "→ Opening PR..."
PR_BODY="Deployed from \`${SOURCE_BRANCH}@${SOURCE_COMMIT}\` in noamgraham-design/Gilly-Geo-Guesser.

Files updated: ${DEPLOY_FILES[*]}"

PR_URL=$(gh_api POST "/repos/$DEPLOY_OWNER/$DEPLOY_REPO/pulls" \
  -d "{\"title\":$(echo "$PR_TITLE" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read().strip()))'),\"body\":$(echo "$PR_BODY" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read().strip()))'),\"head\":\"$DEPLOY_BRANCH\",\"base\":\"$BASE_BRANCH\"}" \
  | grep -o '"html_url":"[^"]*pulls[^"]*"' | cut -d'"' -f4)

echo "✓ PR opened: $PR_URL"
