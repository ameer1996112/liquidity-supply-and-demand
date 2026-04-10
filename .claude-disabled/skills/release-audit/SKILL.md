---
name: release-audit
description: Review a branch or change-set for production readiness, regressions, and missing safeguards.
disable-model-invocation: true
argument-hint: [branch or change]
allowed-tools: Read, Grep, Glob, Bash(git diff *), Bash(git status *), Bash(pytest *), Bash(python *), Bash(npm test *), Bash(pnpm test *), Bash(yarn test *)
---

# Release Audit

Audit: $ARGUMENTS

## Review

- frontend regressions
- backend contract changes
- state management regressions
- trading/risk logic changes
- missing tests
- missing docs
- stale status risks
- unsafe migrations
- logging gaps

## Verdict

Return:

- merge-ready or not
- top risks
- missing checks
- exact must-fix items
