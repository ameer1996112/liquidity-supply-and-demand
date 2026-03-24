# Research Summary: Agent Expansion & Multi-Account
*Synthesized from Stack, Architecture, Features, and Pitfalls.*

## Stack Changes
- **Jira Epics**: Natively supported via `/rest/api/3/issue`, but requires querying the `Epic` issuetype ID explicitly natively, along with the custom field ID for `Epic Name` which Atlassian often heavily customizes per board.
- **Discord Alerts**: No external dependency needed. Pure `requests` / `https` POST to Discord Webhook URL with JSON embeds.
- **Multi-Account**: Modifying the Python `asyncio` structure (or threading) inside `worker.py` to iterate an array of connection endpoints via `metaapi_cloud_sdk`.

## Key Features & Differentiators
- **Table Stakes**: Basic iteration of trades over 2+ accounts, Discord pings on crash.
- **Differentiators**: Risk-isolated PropGuard contexts per account directly in Redis; Beautiful embedded Discord widgets highlighting ticket ID / PR Links instead of plain text.

## Architecture Impact
- Python memory consumption might expand linearly per MetaApi connection block. Needs tight garbage collection or unified event loops.
- Agentic UI relies purely on FastAPI polling against Redis transient keys, exposing what the internal agent is building natively.

## Pitfalls & Mitigation
- **Pitfall**: Atlassian Jira Cloud deprecated the `Epic Link` field in favor of `parent` mapping; outdated guides will crash the CLI. **Mitigation**: Strictly use Jira's `parent` field structure.
- **Pitfall**: Dispatching MetaApi trades synchronously across 5 accounts causes severe slippage on Account 5. **Mitigation**: Use `asyncio.gather` for simultaneous trade routing.
