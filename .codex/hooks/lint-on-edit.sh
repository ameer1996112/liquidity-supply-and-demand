#!/bin/bash
# Auto-lint hook: runs after Edit/Write tool calls
# Checks Python compilation and TypeScript type errors

FILE="${CLAUDE_TOOL_INPUT_FILE_PATH:-}"

if [ -z "$FILE" ]; then
  exit 0
fi

# Python: check compilation
if echo "$FILE" | grep -q '\.py$'; then
  RESULT=$(python3 -m py_compile "$FILE" 2>&1)
  if [ -n "$RESULT" ]; then
    echo "⚠️  Python compile error in $FILE:"
    echo "$RESULT" | head -5
  fi
fi

# TypeScript: run type check (project-wide, skip lib to keep it fast)
if echo "$FILE" | grep -qE '\.(ts|tsx)$'; then
  cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading
  RESULT=$(npx tsc --noEmit --skipLibCheck 2>&1 | head -10)
  if [ -n "$RESULT" ]; then
    echo "⚠️  TypeScript errors after editing $FILE:"
    echo "$RESULT"
  fi
fi

exit 0
