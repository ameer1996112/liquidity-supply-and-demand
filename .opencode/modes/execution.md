# Execution Mode

You are executing an approved plan from `.planning/proposals/`.

## Prerequisites

- A plan file exists in `.planning/proposals/<name>.md`
- The user has explicitly approved the plan
- A Jira ticket has been created (or explicitly skipped)

## Workflow

1. Follow the approved plan step by step
2. Make changes in the order specified by the plan
3. Run tests after each logical change:
   ```bash
   PYTHONPATH=. pytest tests/ -v        # Backend
   cd frontend && npx vitest run          # Frontend (if applicable)
   ```
4. Run lint check before finishing:
   ```bash
   ruff check src/ config/ tests/
   ```
5. Close the Jira ticket when done
6. Update `.planning/codebase/CONCERNS.md` if you discovered new issues
7. Mark the plan as completed in `.planning/proposals/<name>.md`

## Constraints

- Do NOT deviate from the approved plan without asking
- Do NOT touch files not listed in the plan
- Do NOT skip test runs
- If you discover a problem that requires plan changes, **STOP and report**
