# Codebase Concerns

**Analysis Date:** 2026-04-09

## Known Active Bugs (Tracked)

**BUG-06: Per-Account Redis Kill-Switch Issues**
- Files: `src/core/safety.py`, `src/worker.py`
- Issue: Kill-switch logic for per-account Redis management is incomplete
- Status: Partially addressed with comments indicating workarounds in place

**BUG-05: ENV Kill-Switch Guard Issues**
- File: `src/core/safety.py`
- Issue: Environment-based kill switch guards have edge cases
- Status: Documented with workaround code

**BUG-02, BUG-03: Fail-Closed Policies for LIVE Accounts**
- Files: `src/core/safety.py`, `src/worker.py`
- Issue: Safety policies for live trading accounts need hardening
- Status: Partially implemented with known gaps

## TODO/FIXME Items

**High Priority:**
- `src/api_portfolio.py:135` - Fetch live equity instead of using `settings.account_balance` (currently using hardcoded/config value)
- `src/services/account_orchestrator.py:300` - Calculate `max_drawdown_pct` from equity curve (currently hardcoded to 0.0)

**Medium Priority:**
- `src/services/position_optimizer.py:238` - Implement quadratic programming optimization for position sizing
- `src/services/position_optimizer.py:262` - Implement portfolio rebalancing logic
- `src/services/daily_reset_scheduler.py:63` - Multi-account broker_profiles fetch (currently single-account only)

**Frontend API Gaps:**
- `frontend/src/lib/api.ts:639-681` - 6 backend endpoints need implementation:
  - `GET /api/risk/settings/:accountId`
  - `PUT /api/risk/settings/:accountId`
  - `GET /api/risk/equity-threshold/:accountId`
  - `PUT /api/risk/equity-threshold/:accountId`
  - `GET /api/risk/positions/:accountId`
  - `PUT /api/risk/positions/:accountId`

## Code Complexity & Maintainability

**Oversized Files (Maintainability Risk):**
- `src/api_portfolio_control.py` - 2,433 lines (exceeds recommended 500-line limit)
- `src/worker.py` - 2,068 lines (main worker loop needs decomposition)
- `src/ai/brain.py` - 1,554 lines (AI agent logic should be modularized)
- `src/adapters/discord.py` - 1,108 lines
- `src/adapters/supabase.py` - 1,098 lines
- `src/api.py` - 1,091 lines

**Impact:** Large files increase cognitive load, make testing harder, and increase risk of merge conflicts.
**Fix approach:** Extract cohesive modules into separate services/utilities.

## Security Concerns

**Bare Exception Handlers (Error Handling Anti-Pattern):**
Files with multiple bare `except Exception:` patterns:
- `src/worker.py` - 15+ instances (lines 158, 193, 224, 392, 407, 787, 809, 925, 956, 979, 1063, 1613, 1655, 1875, 2036, 2055, 2061)
- `src/api_tickets.py` - 4 instances (lines 679, 685, 712, 755)
- `src/pipeline/audit.py` - 2 instances (lines 31, 212)
- `src/pipeline/account_state.py` - 2 instances (lines 49, 81)
- `src/pipeline/account_guards.py` - 2 instances (lines 98, 255)
- `src/api_rules.py` - 3 instances (lines 71, 94, 114)

**Risk:** Bare exceptions can mask critical errors, make debugging difficult, and potentially swallow exceptions that should halt execution (especially concerning in a financial trading system).
**Fix approach:** Use specific exception types, add logging, and implement proper error propagation.

**Environment Configuration:**
- `.env` file exists (7,206 bytes) - Contains active credentials
- Token storage: Tokens stored in database `broker_profiles.token` field and retrieved dynamically
- Token masking implemented in `api_broker_profiles.py` (shows only last 8 characters)

## Frontend Issues

**Debug Code in Production:**
- Multiple `console.log`, `console.error`, `console.warn` statements throughout frontend code
- Debug utilities present in `frontend/src/hooks/useTradingSignals.ts`
- Risk: Information leakage in production builds

**Fix approach:** Implement proper logging service that disables console output in production.

## Missing Implementations

**Position Optimizer:**
- Quadratic programming solver not implemented (placeholder only)
- Portfolio rebalancing logic not implemented

**Daily Reset Scheduler:**
- Multi-account support pending (affects scalability for multiple trading accounts)

**Risk Management API:**
- 6 risk settings endpoints not implemented in backend
- Frontend has stubs ready but backend returns 404

## Performance Concerns

**File Size Impact:**
- Large Python files may impact cold-start times if running serverless
- Worker.py at 2,068 lines suggests tight coupling in main processing loop

**API Response Times:**
- Portfolio control API at 2,433 lines suggests complex business logic may introduce latency

## Error Handling Gaps

**Worker Resilience:**
- `src/worker.py` has multiple bare exception handlers around critical trade execution paths
- Risk: A swallowed exception could cause a trade to appear successful when it failed, or vice versa

**Position Closing Logic:**
- `src/logic.py` has bugfix comments at lines 145, 301, 840 indicating recent fixes to position closing and broker order handling
- Suggests this area has been problematic and may need additional hardening

## Documentation Gaps

**No inline documentation for:**
- AI/ML guardrail decision criteria
- Trading Council multi-agent debate logic
- MetaApi error code handling strategy
- Kill-switch state machine transitions

## Scalability Concerns

**Single-Account Limitations:**
- Daily reset scheduler only supports single account currently
- Position optimizer may not handle portfolio-level constraints across multiple accounts

**Redis Dependency:**
- Worker relies on Redis for queue processing - no documented fallback if Redis unavailable
- Rate limiting also depends on Redis

## Architectural Concerns

**Tight Coupling:**
- `worker.py` combines queue consumption, AI guardrails, trade execution, and state management
- Should be decomposed into: queue consumer → guardrail service → execution service → state service

**MetaApi Integration:**
- All broker communication goes through single adapter - no circuit breaker pattern evident
- If MetaApi has issues, system may queue up signals without backpressure mechanism

## Test Coverage Gaps

- No obvious test files found in initial scan for the large/complex modules
- Risk: 2,000+ line files without comprehensive test coverage

## Recommended Priorities

1. **Critical:** Fix bare exception handlers in trading execution paths
2. **High:** Implement missing risk API endpoints or remove frontend stubs
3. **High:** Add live equity fetching (remove hardcoded balance)
4. **Medium:** Decompose oversized files into testable modules
5. **Medium:** Remove debug console statements from production frontend
6. **Low:** Add comprehensive error logging and monitoring hooks

---

*Concerns audit: 2026-04-09*
