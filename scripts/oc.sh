#!/usr/bin/env bash
# Smart OpenCode workspace launcher
# Picks the right workspace based on recently modified files

set -euo pipefail

DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=true
  shift
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACES_DIR="$REPO_ROOT/.workspaces"

# Get files changed since last commit (staged + unstaged)
CHANGED_FILES=$(git -C "$REPO_ROOT" diff --name-only HEAD 2>/dev/null || true)
CHANGED_FILES+=$'\n'$(git -C "$REPO_ROOT" diff --name-only 2>/dev/null || true)
CHANGED_FILES+=$'\n'$(git -C "$REPO_ROOT" diff --cached --name-only 2>/dev/null || true)

# Detect which domains were touched
HIT_API=false
HIT_WORKER=false
HIT_FRONTEND=false
HIT_OPTIMIZER=false

while IFS= read -r f; do
  [[ -z "$f" ]] && continue
  if [[ "$f" =~ ^src/api.*\.py$ ]] || [[ "$f" =~ ^src/core/ ]] || [[ "$f" =~ ^src/schemas/ ]]; then
    HIT_API=true
  fi
  if [[ "$f" =~ ^src/worker\.py$ ]] || [[ "$f" =~ ^src/services/ ]] || [[ "$f" =~ ^src/adapters/ ]]; then
    HIT_WORKER=true
  fi
  if [[ "$f" =~ ^frontend/ ]]; then
    HIT_FRONTEND=true
  fi
  if [[ "$f" =~ ^scripts/ ]]; then
    HIT_OPTIMIZER=true
  fi
done <<< "$CHANGED_FILES"

# Count how many domains matched
DOMAINS=()
$HIT_API      && DOMAINS+=("api")
$HIT_WORKER   && DOMAINS+=("worker")
$HIT_FRONTEND && DOMAINS+=("frontend")
$HIT_OPTIMIZER && DOMAINS+=("optimizer")

pick_workspace() {
  local ws="$1"
  echo "→ Launching workspace: $ws (${2})"
  cd "$WORKSPACES_DIR/$ws"
  exec opencode "$@" 2>/dev/null || exec opencode
}

launch() {
  local ws="$1"
  local reason="$2"
  echo "→ Would launch workspace: $ws ($reason)"
  echo "  Workspace dir: $WORKSPACES_DIR/$ws"
  if [[ "$DRY_RUN" == "true" ]]; then
    echo "[dry-run] opencode would be launched here."
    exit 0
  fi
  cd "$WORKSPACES_DIR/$ws"
  exec opencode
}

ask_user() {
  echo "Multiple (or no) domains detected. Pick a workspace:"
  echo "  1) api       — src/api*.py, src/core/**, src/schemas/**"
  echo "  2) worker    — src/worker.py, src/services/**, src/adapters/**"
  echo "  3) frontend  — frontend/src/**"
  echo "  4) optimizer — scripts/optimize_pairs.py"
  echo ""
  if [[ "$DRY_RUN" == "true" ]]; then
    echo "[dry-run] Would prompt user to select workspace."
    exit 0
  fi
  read -rp "Enter number [1-4]: " choice
  case "$choice" in
    1) launch "api" "user selected" ;;
    2) launch "worker" "user selected" ;;
    3) launch "frontend" "user selected" ;;
    4) launch "optimizer" "user selected" ;;
    *) echo "Invalid choice. Exiting." && exit 1 ;;
  esac
}

if [[ ${#DOMAINS[@]} -eq 1 ]]; then
  launch "${DOMAINS[0]}" "detected from git diff"
elif [[ ${#DOMAINS[@]} -eq 0 ]]; then
  echo "No recently modified files detected."
  ask_user
else
  echo "Changed domains: ${DOMAINS[*]}"
  ask_user
fi
