#!/bin/bash
# claude-batch.sh — Run Claude Code headlessly for retry-able batch operations
#
# Usage:
#   ./scripts/claude-batch.sh "your task description"
#   ./scripts/claude-batch.sh --file scripts/tasks/my-task.md
#   ./scripts/claude-batch.sh --retry 3 "refactor optimizer.py"
#
# Examples:
#   ./scripts/claude-batch.sh "Update MODULE_MAP.md to reflect current backend structure"
#   ./scripts/claude-batch.sh --retry 2 "Split optimizer.py into config, browser, analysis, runner modules"
#   ./scripts/claude-batch.sh --file scripts/tasks/pine-audit.md

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/scripts/batch-logs"
mkdir -p "$LOG_DIR"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$LOG_DIR/batch_${TIMESTAMP}.log"

RETRY=1
PROMPT=""
TASK_FILE=""
MAX_TURNS=30

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --retry)
      RETRY="$2"; shift 2 ;;
    --turns)
      MAX_TURNS="$2"; shift 2 ;;
    --file)
      TASK_FILE="$2"; shift 2 ;;
    *)
      PROMPT="$1"; shift ;;
  esac
done

if [ -n "$TASK_FILE" ]; then
  if [ ! -f "$TASK_FILE" ]; then
    echo "❌ Task file not found: $TASK_FILE"
    exit 1
  fi
  PROMPT=$(cat "$TASK_FILE")
fi

if [ -z "$PROMPT" ]; then
  echo "Usage: $0 [--retry N] [--turns N] [--file path] \"task description\""
  exit 1
fi

echo "📋 Task: ${PROMPT:0:120}..."
echo "🔄 Max retries: $RETRY"
echo "📝 Log: $LOG_FILE"
echo ""

ATTEMPT=0
SUCCESS=false

while [ $ATTEMPT -lt $RETRY ]; do
  ATTEMPT=$((ATTEMPT + 1))
  echo "▶️  Attempt $ATTEMPT/$RETRY — $(date)"

  if claude \
    --print \
    --max-turns "$MAX_TURNS" \
    --allowedTools "Edit,Read,Write,Bash,Glob,Grep,MultiEdit" \
    "$PROMPT" 2>&1 | tee -a "$LOG_FILE"; then
    SUCCESS=true
    echo ""
    echo "✅ Completed on attempt $ATTEMPT — $(date)"
    break
  else
    EXIT_CODE=$?
    echo "⚠️  Attempt $ATTEMPT failed (exit $EXIT_CODE)"
    if [ $ATTEMPT -lt $RETRY ]; then
      echo "   Retrying in 5 seconds..."
      sleep 5
    fi
  fi
done

if [ "$SUCCESS" = false ]; then
  echo ""
  echo "❌ All $RETRY attempts failed. Check log: $LOG_FILE"
  exit 1
fi

echo ""
echo "📝 Full log saved to: $LOG_FILE"
