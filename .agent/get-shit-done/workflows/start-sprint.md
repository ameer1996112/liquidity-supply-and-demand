<purpose>
Start a new Jira sprint directly from the terminal so that newly created tickets map automatically to the active board instead of falling into the backlog.
</purpose>

<process>

<step name="determine_name">
Determine the sprint name from arguments. If missing, generate a default name based on the current date:

```bash
SPRINT_NAME="${ARGUMENTS:-Sprint $(date +%Y-%m-%d)}"
```
</step>

<step name="create_sprint">
Call the backend API to create and start the sprint natively:

```bash
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST http://localhost:8000/api/tickets/sprints/start \
  -H "Content-Type: application/json" \
  -d "{\"name\": \"$SPRINT_NAME\"}")

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
