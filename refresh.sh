#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# Local refresh — pulls fresh Asana data, rebuilds index.html, commits & pushes.
# Use when you need an immediate update instead of waiting for the next
# auto-refresh tick (every 2h on weekdays, 8am–6pm ET).
#
# Requires:
#   - .env in this directory with ASANA_PAT=...
#   - Git remote `origin` writable from this machine.
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# Resolve script's own directory and cd there (so it works from anywhere).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

bold()  { printf "\033[1m%s\033[0m\n" "$1"; }
green() { printf "\033[32m%s\033[0m\n" "$1"; }
red()   { printf "\033[31m%s\033[0m\n" "$1" >&2; }
gray()  { printf "\033[90m%s\033[0m\n" "$1"; }

bold "→ Local CoE refresh"
gray "  $(date '+%Y-%m-%d %H:%M:%S %Z')"

# Sanity: .env present
if [[ ! -f .env ]]; then
  red "Missing .env — copy .env.example to .env and add your ASANA_PAT."
  exit 1
fi

# Sanity: git working tree clean except for output/ (we'll commit those).
if [[ -n "$(git status --porcelain | grep -v '^.. output/' || true)" ]]; then
  red "Working tree has uncommitted changes outside output/. Commit or stash first."
  git status --short
  exit 1
fi

# Pull first so we don't fight a concurrent CI push.
gray "  pulling latest…"
git pull --rebase --autostash origin main

# Run the refresh (loads .env, fetches Asana, renders, archives snapshot).
bold "→ Running run.py"
python3 run.py

# Stage just the artefacts the CI bot stages.
git add output/index.html output/history/

if git diff --staged --quiet; then
  green "✓ No changes — dashboard already up to date."
  exit 0
fi

# Commit & push using the same message format as CI.
ts=$(TZ=America/New_York date +'%Y-%m-%d %H:%M ET')
git commit -m "manual-refresh ${ts}"

# Retry loop in case CI pushed during run.
for attempt in 1 2 3; do
  if git push; then
    green "✓ Pushed on attempt $attempt — auto-deploy in ~30s."
    exit 0
  fi
  gray "  push rejected, rebasing and retrying…"
  git pull --rebase --autostash origin main
done

red "Push failed after 3 attempts."
exit 1
