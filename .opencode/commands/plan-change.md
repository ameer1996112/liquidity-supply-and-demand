# /plan-change

Write a change plan before modifying any source code.

## Usage
`/plan-change <description-of-change>`

## Procedure

1. Read `.planning/codebase/MODULE_MAP.md` to identify affected modules
2. Read **only** the files in affected modules
3. Read `.planning/codebase/CONVENTIONS.md` for coding rules
4. Write the plan to `.planning/proposals/<name>.md` with:
   - **Goal**: What the change accomplishes
   - **Affected files**: Exact paths with line ranges where possible
   - **New files**: Any files to create
   - **Tests**: Tests to add or update
   - **Jira ticket type**: bug / feature / task
   - **Risk**: Any trading logic or execution paths affected
5. **STOP and wait for user approval** before making changes

## Constraints
- Do NOT edit source code during planning
- Do NOT read more than the affected modules
- Do NOT skip the approval step
- Flag any changes to `src/logic.py`, `src/worker.py`, or `src/core/risk_engine.py` as HIGH RISK
