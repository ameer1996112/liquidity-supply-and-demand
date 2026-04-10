Update a board ticket based on $ARGUMENTS.

Expected format: `<TICKET-ID> <new_status> [optional message]`
Example: `BUG-012 in_progress Root cause isolated to risk_engine.py line 95`
Example: `BUG-012 done Fix applied and tested — dynamic pip value now correct`

Steps:
1. Parse $ARGUMENTS to extract: ticket_id, new_status, message
   - new_status must be one of: backlog, todo, in_progress, done
2. Call the board agent-update API:

```bash
curl -s -X POST http://localhost:3000/api/board/agent-update \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_id": "<TICKET-ID>",
    "new_status": "<new_status>",
    "message": "<message>",
    "agent_name": "Claude Agent"
  }'
```

3. Report back: "Updated **TICKET-ID** → <new_status>"

If no ticket_id is provided, ask the user which ticket to update.
If curl fails, report the intended update so the user can apply it manually.
