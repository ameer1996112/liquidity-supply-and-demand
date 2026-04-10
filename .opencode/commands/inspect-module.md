# /inspect-module

Inspect a module before proposing changes.

## Usage
`/inspect-module <module-name>`

## Procedure

1. Read `.planning/codebase/MODULE_MAP.md`
2. Find the named module in the map
3. Read **only** the files listed for that module
4. Cross-reference with `.planning/codebase/CONCERNS.md` for known issues
5. Cross-reference with `.planning/codebase/TESTING.md` for test coverage

## Output

Summarize:
- Current structure and public interfaces
- Known concerns from CONCERNS.md
- Test coverage status
- Dependencies on other modules

## Constraints
- Do NOT read files outside the module
- Do NOT propose changes — inspection only
- Do NOT scan directories — use MODULE_MAP
