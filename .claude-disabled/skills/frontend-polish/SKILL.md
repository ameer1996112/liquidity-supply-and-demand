---
name: frontend-polish
description: Upgrade a screen, flow, or component to a more professional frontend with consistent UX, states, clarity, and visual hierarchy.
argument-hint: [page/component/flow]
allowed-tools: Read, Edit, Write, Grep, Glob, Bash(npm *), Bash(pnpm *), Bash(yarn *), Bash(git diff *)
---

# Frontend Polish

Improve: $ARGUMENTS

## Audit first

Inspect:

- layout and spacing
- typography hierarchy
- color consistency
- button and input consistency
- loading, empty, success, and error states
- table/card readability
- status clarity
- mobile/responsive behavior
- duplicated components or windows

## Then improve

1. Keep existing behavior unless clearly broken.
2. Refactor toward reusable components.
3. Remove visual ambiguity.
4. Make important states obvious:
   - pending
   - active
   - blocked
   - failed
   - completed
5. Ensure the result looks production-ready.

## Output

Return:

- UI issues found
- what changed
- any remaining UX debt
