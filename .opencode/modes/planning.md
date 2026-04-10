# Planning Mode

You are in planning mode. This is the default operating mode.

## Allowed Actions

- Read files listed in `.planning/codebase/MODULE_MAP.md`
- Read `.planning/codebase/*` reference documents
- Write plans to `.planning/proposals/<name>.md`
- Ask clarifying questions
- Run read-only commands (`cat`, `grep` on specific files, `ruff check --diff`)

## Forbidden Actions

- Edit any source code in `src/`, `frontend/`, `tests/`, `config/`
- Run commands that modify state (`rm`, `mv`, `git commit`, `pip install`)
- Read files not listed in MODULE_MAP without asking permission
- Scan directories with `find .` or `ls -R` from root
- Create new top-level files or directories

## Transition

To enter Execution Mode, the user must explicitly approve a plan from `.planning/proposals/`.
