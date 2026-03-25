<purpose>
Start a new Jira sprint directly from the terminal so that newly created tickets map automatically to the active board instead of falling into the backlog.
</purpose>

<process>

<step name="determine_name">
Determine the sprint name from arguments or generate a contextual name based on the current GSD Phase constraints:

```bash
FOCUS=$(grep "Current focus:" .planning/STATE.md 2>/dev/null | sed -e 's/.*\*\*Current focus:\*\* //' -e 's/.*Current focus: //' | sed 's/^[ \t]*//' || echo "")
if [ -n "$FOCUS" ]; then
  RAW_NAME="${ARGUMENTS:-[Sprint] $FOCUS}"
  SPRINT_NAME=$(echo "$RAW_NAME" | cut -c1-30 | sed 's/ *$//')
  SPRINT_GOAL="Execute: $FOCUS"
else
  SPRINT_NAME="${ARGUMENTS:-Sprint $(date +%Y-%m-%d)}"
  SPRINT_GOAL="General backlog execution"
fi
```
</step>

<step name="create_sprint">
Call the backend API to create and start the contextual sprint natively:

```bash
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST http://localhost:8000/api/tickets/sprints/start \
  -H "Content-Type: application/json" \
  -d "{\"name\": \"$SPRINT_NAME\", \"goal\": \"$SPRINT_GOAL\"}")

BODY=$(echo "$RESPONSE" | sed '$d')
STATUS=$(echo "$RESPONSE" | tail -n1)

if [ "$STATUS" -eq 201 ] || [ "$STATUS" -eq 200 ]; then
  SPRINT_ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('sprint_id', ''))" 2>/dev/null)
  echo "✅ Successfully created and started sprint: $SPRINT_NAME (ID: $SPRINT_ID)"
else
  echo "❌ Failed to start sprint ($STATUS): $BODY"
  echo "⚠️ Make sure the FastAPI backend is running on port 8000."
fi
```
</step>

</process>

<success_criteria>
- [ ] Sprint name is parsed or auto-generated.
- [ ] Direct call made to `/api/tickets/sprints/start`.
- [ ] Logs success with sprint ID, or fails gracefully if the backend is down.
</success_criteria>
