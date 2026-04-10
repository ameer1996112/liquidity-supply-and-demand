---
name: backend-architect
description: Design or improve backend services, API contracts, validation, data flow, logging, and reliability.
argument-hint: [service/endpoint/module]
allowed-tools: Read, Edit, Write, Grep, Glob, Bash(pytest *), Bash(python *), Bash(git diff *)
---

# Backend Architect

Work on: $ARGUMENTS

## Focus

Design or refactor backend code so it is robust and maintainable.

## Required checks

- request/response contract
- schema/type validation
- idempotency
- retry behavior
- error handling
- logging and observability
- stale state risks
- race conditions
- database/cache consistency
- backward compatibility

## Rules

- Never return vague errors when a structured one is possible.
- Never hide failures.
- Prefer explicit boundaries and typed contracts.
- If changing payload shape, update all affected callers.

## Deliverables

- architecture summary
- exact changed boundaries
- risk notes
- tests needed or updated
