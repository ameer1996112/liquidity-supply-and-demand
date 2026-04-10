Create a bug ticket on the Kanban board for the issue described in $ARGUMENTS.

Steps:
1. Determine the best values for: title, component, priority, description based on $ARGUMENTS and what you know about the bug.
   - component must be one of: "Pine Script", "Python Backend", "Supabase / DB", "Frontend (React)", "MT5 / Broker", "AI / ML Pipeline", "Infrastructure"
   - priority must be one of: critical, high, medium, low
2. Call the board API to create the ticket:

```bash
curl -s -X POST http://localhost:3000/api/board/create-ticket \
  -H "Content-Type: application/json" \
  -d '{
    "type": "bug",
    "title": "<title>",
    "component": "<component>",
    "priority": "<priority>",
    "description": "<description>",
    "agent_name": "Claude Agent"
  }'
```

3. Report back: "Created **BUG-XXX** — <title> [<priority>/<component>]"

If the curl fails (frontend not running), still report the intended ticket so the user can create it manually.
