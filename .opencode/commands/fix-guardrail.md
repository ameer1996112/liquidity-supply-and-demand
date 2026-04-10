# /fix-guardrail

Fix or modify a guard rail implementation.

## Usage
`/fix-guardrail <guard-name>`

## Procedure

1. Read `src/core/guard_rails/<guard-name>.py`
2. Read `src/core/guard_rails/__init__.py` for registration
3. Read `src/core/guard_rails/guard_registry.py` for ordering
4. Search `tests/` for existing guard tests
5. Read `.planning/codebase/CONCERNS.md` for known guard rail issues

## Output

Propose the fix with:
- Exact code changes (minimal diff)
- Updated or new test covering the fix
- Impact analysis on other guards in the chain

## Constraints
- Do NOT modify other guard files unless the fix requires it
- Do NOT change guard ordering without explicit approval
- Do NOT skip the test update
- **STOP and wait for user approval** before applying changes
