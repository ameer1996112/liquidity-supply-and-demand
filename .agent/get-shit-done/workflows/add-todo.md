<purpose>
Capture an idea, task, or issue that surfaces during a GSD session as a structured todo for later work. Enables "thought → capture → continue" flow without losing context.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.
</required_reading>

<process>

<step name="init_context">
Load todo context:

```bash
INIT=$(node ".agent/get-shit-done/bin/gsd-tools.cjs" init todos)
if [[ "$INIT" == @file:* ]]; then INIT=$(cat "${INIT#@file:}"); fi
```

Extract from init JSON: `commit_docs`, `date`, `timestamp`, `todo_count`, `todos`, `pending_dir`, `todos_dir_exists`.

Ensure directories exist:
```bash
mkdir -p .planning/todos/pending .planning/todos/done
```

Note existing areas from the todos array for consistency in infer_area step.
</step>

<step name="extract_content">
**With arguments:** Use as the title/focus.
- `/gsd-add-todo Add auth token refresh` → title = "Add auth token refresh"

**Without arguments:** Analyze recent conversation to extract:
- The specific problem, idea, or task discussed
- Relevant file paths mentioned
- Technical details (error messages, line numbers, constraints)

Formulate:
- `title`: 3-10 word descriptive title (action verb preferred)
- `problem`: What's wrong or why this is needed
- `solution`: Approach hints or "TBD" if just an idea
- `files`: Relevant paths with line numbers from conversation
</step>

<step name="infer_area">
Infer area from file paths:

| Path pattern | Area |
|--------------|------|
| `src/api/*`, `api/*` | `api` |
| `src/components/*`, `src/ui/*` | `ui` |
| `src/auth/*`, `auth/*` | `auth` |
| `src/db/*`, `database/*` | `database` |
| `tests/*`, `__tests__/*` | `testing` |
| `docs/*` | `docs` |
| `.planning/*` | `planning` |
| `scripts/*`, `bin/*` | `tooling` |
| No files or unclear | `general` |

Use existing area from step 2 if similar match exists.
</step>

<step name="check_duplicates">
```bash
# Search for key words from title in existing todos
grep -l -i "[key words from title]" .planning/todos/pending/*.md 2>/dev/null
```

If potential duplicate found:
1. Read the existing todo
2. Compare scope

If overlapping, use AskUserQuestion:
- header: "Duplicate?"
- question: "Similar todo exists: [title]. What would you like to do?"
- options:
  - "Skip" — keep existing todo
  - "Replace" — update existing with new context
  - "Add anyway" — create as separate todo
</step>

<step name="create_file">
Use values from init context: `timestamp` and `date` are already available.

Generate slug for the title:
```bash
slug=$(node ".agent/get-shit-done/bin/gsd-tools.cjs" generate-slug "$title" --raw)
```

Write to `.planning/todos/pending/${date}-${slug}.md`:

```markdown
---
created: [timestamp]
title: [title]
area: [area]
ticket_id: ""
files:
  - [file:lines]
---

## Problem

[problem description - enough context for future Claude to understand weeks later]

## Solution

[approach hints or "TBD"]
```
</step>

<step name="create_jira_ticket">
After writing the todo file, create a Jira ticket with rich structured content.

First, fetch the active sprint so the ticket lands in the right sprint:

```bash
SPRINT=$(curl -s http://localhost:8000/api/tickets/active-sprint 2>/dev/null || echo '{"sprint_id":null}')
SPRINT_ID=$(echo "$SPRINT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('sprint_id') or '')" 2>/dev/null || echo "")

if [ -z "$SPRINT_ID" ] || [ "$SPRINT_ID" == "null" ]; then
  # Auto-start a new sprint if none exists
  echo "No active sprint found. Auto-starting a new sprint so this ticket is visible..."
  SPRINT_NAME="Sprint $(date +%Y-%m-%d)"
  curl -s -X POST http://localhost:8000/api/tickets/sprints/start \
    -H "Content-Type: application/json" \
    -d "{\"name\": \"$SPRINT_NAME\"}" > /dev/null
  
  # Re-fetch sprint ID
  SPRINT=$(curl -s http://localhost:8000/api/tickets/active-sprint 2>/dev/null || echo '{"sprint_id":null}')
  SPRINT_ID=$(echo "$SPRINT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('sprint_id') or '')" 2>/dev/null || echo "")
fi
```

Build the rich payload including:
- `problem`: the full problem statement (from ## Problem section)
- `solution`: approach hints (from ## Solution section)
- `files`: list of referenced file paths
- `acceptance_criteria`: 3 auto-inferred criteria if none specified
- `story_points`: estimate (1=trivial, 2=small, 3=medium, 5=large, 8=very large)
- `priority`: infer from severity ("high" for bugs/blockers, "medium" for features/tasks)
- `sprint_id`: from active sprint fetch above

```bash
# Infer story_points from title/problem complexity (default: 3)
STORY_POINTS=3
PRIORITY="medium"
# Bugs and blockers → high priority
if echo "$title $problem" | grep -qi "bug\|error\|crash\|broken\|fail\|blocked"; then
  PRIORITY="high"
  STORY_POINTS=3
fi

# Build JSON payload using python3 for proper escaping
PAYLOAD=$(python3 -c "
import json, sys
d = {
  'title': '''$title''',
  'problem': '''$problem''',
  'solution': '''$solution''',
  'files': $(echo "$files" | python3 -c "import sys,json; lines=[l.strip() for l in sys.stdin.read().split('\n') if l.strip()]; print(json.dumps(lines))" 2>/dev/null || echo '[]'),
  'acceptance_criteria': [
    'Issue is resolved and verified',
    'No regression in related functionality',
    'Code reviewed and tests pass'
  ],
  'type': 'task',
  'status': 'todo',
  'priority': '$PRIORITY',
  'story_points': $STORY_POINTS,
}
if '$SPRINT_ID' and '$SPRINT_ID' != 'null':
    d['sprint_id'] = int('$SPRINT_ID')
print(json.dumps(d))
")

TICKET=$(curl -s -X POST http://localhost:8000/api/tickets \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD")
```

The endpoint is **idempotent**: same title → returns existing ticket (HTTP 200).

Extract the `id` from the response. If successful:
1. Update the todo file frontmatter: replace `ticket_id: ""` with `ticket_id: "[id]"`
2. Log: `🎫 Jira ticket: [id] (sprint: [sprint name or backlog], [story_points]pts, priority:[priority])`

If API unavailable:
- Skip silently — log: `⚠️ Jira API unavailable — run backend to enable auto-ticketing.`
</step>


<step name="update_state">
If `.planning/STATE.md` exists:

1. Use `todo_count` from init context (or re-run `init todos` if count changed)
2. Update "### Pending Todos" under "## Accumulated Context"
</step>

<step name="git_commit">
Commit the todo and any updated state:

```bash
node ".agent/get-shit-done/bin/gsd-tools.cjs" commit "docs: capture todo - [title]" --files .planning/todos/pending/[filename] .planning/STATE.md
```

Tool respects `commit_docs` config and gitignore automatically.

Confirm: "Committed: docs: capture todo - [title]"
</step>

<step name="confirm">
```
Todo saved: .planning/todos/pending/[filename]

  [title]
  Area: [area]
  Files: [count] referenced

---

Would you like to:

1. Continue with current work
2. Add another todo
3. View all todos (/gsd-check-todos)
```
</step>

</process>

<success_criteria>
- [ ] Directory structure exists
- [ ] Todo file created with valid frontmatter (including ticket_id field)
- [ ] Problem section has enough context for future Claude
- [ ] No duplicates (checked and resolved)
- [ ] Area consistent with existing todos
- [ ] Jira ticket created (ticket_id stored in frontmatter, or API unavailable note logged)
- [ ] STATE.md updated if exists
- [ ] Todo and state committed to git
</success_criteria>
