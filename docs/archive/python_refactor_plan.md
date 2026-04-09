# Python Backend Refactor Plan
> **Goal:** Every source file ≤ 300 lines. Optimized for AI token context — each file loads as a single coherent unit of responsibility.  
> **Approach:** Surgical extraction only. Zero behaviour changes. All existing tests must pass after each phase.  
> **Constraint:** The Pine ↔ Python webhook contract (`docs/pine_webhook_contract.md`) is frozen. No field renames.

---

## Current State — Monolith Inventory

| File | Lines | Status | Problem |
|------|-------|--------|---------|
| `src/worker.py` | **2,068** | 🔴 Critical | Everything: guards, queue loop, AI pipeline, account routing |
| `src/ai/brain.py` | **1,554** | 🔴 Critical | RF inference + LLM + ensemble + feature eng all mixed |
| `src/api.py` | **1,091** | 🔴 Critical | App factory + lifecycle + webhook + AI config endpoints |
| `src/adapters/execution/meta_api_adapter.py` | **974** | 🔴 Critical | HTTP retry + order mgmt + account info + position reader |
| `src/logic.py` | **946** | 🟡 High | Entry exec + exit handler + broker helpers + filter |
| `src/core/guard_rails/correlation.py` | **697** | 🟡 High | Currency utils + manager + DB helpers all in one |
| `src/core/risk_engine.py` | **601** | 🟡 High | Models + position sizer + RiskGuardian in one file |
| `src/services/notification_service.py` | **449** | 🟡 Medium | Formatter + sender + channel logic mixed |
| `src/core/dynamic_config.py` | **388** | 🟡 Medium | DB CRUD + cache + time rules all mixed |
| `src/services/liquidity_scorer.py` | **385** | 🟡 Medium | Scoring + thresholds + market adjustments |
| `src/core/safety.py` | **287** | ✅ OK | Under limit — no changes needed |
| `src/agents/supervisor.py` | **134** | ✅ OK | Under limit — no changes needed |

**Total lines to redistribute: ~8,200 across the monoliths above.**

---

## Target Architecture

```
src/
├── api.py                          ← App factory ONLY (~100 lines)
├── worker.py                       ← Queue loop ONLY (~150 lines)
│
├── pipeline/                       ← NEW: trade processing pipeline
│   ├── __init__.py
│   ├── trade_processor.py          ← process_trade orchestrator (~250 lines)
│   ├── account_guards.py           ← _run_account_guards (~200 lines)
│   ├── profile_executor.py         ← _execute_for_profile (~180 lines)
│   ├── signal_filter.py            ← pine_filters + should_forward_alert (~200 lines)
│   ├── trade_entry.py              ← entry execution path from logic.py (~250 lines)
│   ├── trade_exit.py               ← exit handling path from logic.py (~200 lines)
│   ├── idempotency.py              ← claim/exists trade_key (~80 lines)
│   ├── account_state.py            ← daily_pnl, trade_count, positions_from_db (~100 lines)
│   └── audit.py                    ← save_result, log_guard_decision wrappers (~120 lines)
│
├── api_webhook.py                  ← POST /webhook + /webhook/test (~150 lines)
├── api_lifecycle.py                ← _lifespan, startup, shutdown, MetaAPI streaming (~180 lines)
│
├── core/
│   ├── safety.py                   ← DONE (287 lines — no changes needed)
│   ├── risk_models.py              ← NEW: data classes only (~60 lines)
│   ├── position_sizer.py           ← NEW: calculate_max_position_size + _with_spread (~280 lines)
│   ├── risk_guardian.py            ← NEW: RiskGuardian class (~180 lines)
│   ├── symbol_registry.py          ← NEW: _lookup_symbol_overrides + pip helpers (~100 lines)
│   ├── dynamic_config.py           ← TRIM: get/update/reset only (~180 lines)
│   ├── time_rules.py               ← NEW: get_active_time_rules + apply_time_based_rules (~200 lines)
│   └── guard_rails/
│       ├── pine_filters.py         ← NEW: _validate_pine_filters extracted (~280 lines)
│       ├── correlation.py          ← TRIM: CorrelationManager class only (~300 lines)
│       ├── currency_utils.py       ← NEW: extract_currencies, get_correlation_groups (~130 lines)
│       ├── correlation_db.py       ← NEW: get_active_positions_from_db, factory (~100 lines)
│       ├── prop_guard.py           ← OK (no changes)
│       ├── staleness_guard.py      ← OK (no changes)
│       ├── holiday_guard.py        ← OK (no changes)
│       └── pine_guardian.py        ← OK (no changes)
│
├── ai/
│   ├── brain.py                    ← TRIM: re-export shim only (~100 lines)
│   ├── feature_engineer.py         ← NEW: _engineer_features_for_prediction (~150 lines)
│   ├── rf_predictor.py             ← NEW: load_brain, get_prediction, model I/O (~300 lines)
│   ├── llm_client.py               ← NEW: call_llm_with_fallback, call_llm_single, two_tier (~280 lines)
│   ├── ensemble.py                 ← NEW: ensemble_decision (~280 lines)
│   └── rf_threshold.py             ← NEW: compute_dynamic_rf_threshold, feature alignment (~200 lines)
│
├── adapters/
│   └── execution/
│       ├── meta_api_adapter.py     ← TRIM: MetaApiAdapter skeleton, delegates to sub-modules (~120 lines)
│       ├── http_retry.py           ← NEW: _request_with_retry + backoff (~100 lines)
│       ├── order_submitter.py      ← NEW: submit_order, open position (~200 lines)
│       ├── order_manager.py        ← NEW: close_order, modify_sl, modify_tp (~200 lines)
│       ├── account_info.py         ← NEW: get_account_info, get_balance (~120 lines)
│       ├── position_reader.py      ← NEW: get_positions, get_open_orders (~150 lines)
│       └── router.py               ← OK (no changes)
│
└── services/
    ├── notification_service.py     ← TRIM: NotificationService class only (~200 lines)
    ├── notification_formatters.py  ← NEW: format_entry, format_exit, format_guard (~150 lines)
    ├── notification_utils.py       ← NEW: pip divisor, price formatting, AI analysis (~120 lines)
    ├── liquidity_scorer.py         ← TRIM: LiquidityScorer class only (~200 lines)
    └── liquidity_threshold.py      ← NEW: compute_dynamic_departure_threshold (~150 lines)
```

---

## Phase 1 — Split `src/worker.py` (2,068 → ~150 lines)

**Priority: Highest.** Most dangerous monolith — one bad merge corrupts the entire pipeline.

### New Files

#### `src/pipeline/signal_filter.py` (~200 lines)
**Source:** `worker.py:674–942` (`_validate_pine_filters`)

```python
def validate_pine_filters(payload: Dict[str, Any]) -> Optional[str]:
    """Returns rejection reason or None.
    Reads: zone_grade, score, session, trend, htf_trend, freshness,
    touch_count, atr_ratio, rsi, rvol, adx, liq_swept, target_swept,
    caused_sweep, is_accuracy, departure_strength, return_strength,
    liquidity_distance_pips."""
```

#### `src/pipeline/account_state.py` (~100 lines)
**Source:** `worker.py:942–1015`

```python
def get_account_daily_pnl(profile: Optional[Dict]) -> float: ...
def get_account_daily_trade_count(profile: Optional[Dict]) -> int: ...
def get_account_positions_from_db(profile: Optional[Dict]) -> list: ...
```

#### `src/pipeline/account_guards.py` (~200 lines)
**Source:** `worker.py:1016–1200` (`_run_account_guards`)

```python
def run_account_guards(
    payload: Dict[str, Any],
    profile: Optional[Dict],
    s,
    current_equity_global: float,
) -> Optional[str]:
    """Returns rejection reason or None.
    Fail-closed on LIVE for: Redis kill-switch, MTM Guardian,
    circuit breaker, adaptive trade limit (BUG-06)."""
```

#### `src/pipeline/profile_executor.py` (~180 lines)
**Source:** `worker.py:1203–1290` (`_execute_for_profile`)

```python
def execute_for_profile(
    payload: Dict[str, Any],
    profile: Optional[Dict],
    ai_result: Dict[str, Any],
    dry_run: bool,
    s,
    current_equity_global: float,
) -> None:
    """Idempotency check → half-risk enforcement → run_account_guards → logic."""
```

#### `src/pipeline/trade_processor.py` (~250 lines)
**Source:** `worker.py:1291–1755` (`process_trade`)

```python
def process_trade(payload: Dict[str, Any]) -> None:
    """Full entry pipeline:
    1. check_env_kill_switch        (safety.py)
    2. run_global_guards            (safety.py)
    3. symbol_whitelist
    4. staleness_guard
    5. holiday_guard
    6. validate_pine_filters        (signal_filter.py)
    7. AI Supervisor                (agents/supervisor.py)
    8. per-account fan-out          (profile_executor.py)
    Exit signals bypass all above and go direct to logic.process_trade."""
```

#### `src/pipeline/idempotency.py` (~80 lines)
**Source:** `worker.py:338–380`

```python
def claim_trade_key(trade_key: str, broker_profile_id: Optional[int], ttl: int = 300) -> bool: ...
def exists_trade_key(trade_key: str, broker_profile_id: Optional[int]) -> bool: ...
```

#### `src/pipeline/audit.py` (~120 lines)
**Source:** `worker.py:499–623`

```python
def save_result(payload, status, note, win_prob, **kwargs) -> None: ...
def build_ml_rejection_reasoning(payload, win_prob, features_used, note) -> Dict: ...
def notify_guard_activation(reason: str, symbol: str, payload: Dict) -> None: ...
```

### `src/worker.py` after Phase 1 (~150 lines)
Retains only:
- Global constants (`PROFITABLE_SYMBOLS`, `MAX_OPEN_POSITIONS`)
- `init_connections()` — Redis, Supabase, AI brain, correlation manager
- `run()` — the Redis BLPOP polling loop with reconnect logic

---

## Phase 2 — Split `src/ai/brain.py` (1,554 → ~100 lines)

#### `src/ai/feature_engineer.py` (~150 lines)
**Source:** `brain.py:25–162`

```python
def engineer_features_for_prediction(df: pd.DataFrame) -> pd.DataFrame:
    """Compute all derived features from raw market data for RF model input."""
```

#### `src/ai/llm_client.py` (~280 lines)
**Source:** `brain.py:256–540`

```python
def call_llm_with_fallback(prompt, system_prompt, settings) -> Dict: ...
def call_llm_single(prompt, model_id, settings, timeout) -> Dict: ...
def call_llm_two_tier(prompt, system_prompt, settings) -> Dict: ...
# Internal: _monitor_llm_failure, _extract_llm_error_meta, _is_model_not_found_error
```

#### `src/ai/rf_threshold.py` (~200 lines)
**Source:** `brain.py:599–809`

```python
def compute_dynamic_rf_threshold(payload: Dict, settings) -> tuple[float, Dict]: ...
def align_features_for_inference(raw_features: Dict, expected_spec) -> np.ndarray: ...
def get_expected_feature_spec() -> tuple[List[str], Optional[int], str]: ...
```

#### `src/ai/rf_predictor.py` (~300 lines)
**Source:** `brain.py:843–1089`

```python
def load_brain() -> None:
    """Load RF model + metadata from disk. Called once at worker startup."""

def get_prediction(payload: Dict) -> tuple[float, str, Dict]:
    """Returns (win_probability, decision_label, features_used_dict)."""
```

#### `src/ai/ensemble.py` (~280 lines)
**Source:** `brain.py:1123–1534`

```python
def ensemble_decision(payload: Dict) -> Dict[str, Any]:
    """Run RF fast-path or full RF+LLM ensemble.
    Returns: {decision, rf_prob, llm_vote, reasoning, features_used}"""
```

### `src/ai/brain.py` after Phase 2 (~100 lines)
Re-export shim only. Imports from sub-modules and re-exports:
- `load_brain` ← `rf_predictor`
- `get_prediction` ← `rf_predictor`
- `ensemble_decision` ← `ensemble`

---

## Phase 3 — Split `src/api.py` (1,091 → ~100 lines)

#### `src/api_lifecycle.py` (~180 lines)
**Source:** `api.py:151–395`

```python
@asynccontextmanager
async def lifespan(app: FastAPI): ...      # startup + shutdown

async def start_metaapi_streaming() -> None: ...
def stop_metaapi_streaming() -> None: ...
def fail_fast_config(): ...                # Redis ping + strategy validation
def shutdown_worker(): ...
```

#### `src/api_webhook.py` (~150 lines)
**Source:** `api.py:397–888`

```python
def validate_webhook_secret(request, secret) -> None: ...
def parse_body(raw: bytes) -> dict: ...
async def get_webhook_payload(request, x_webhook_secret) -> dict: ...

@router.post("/webhook")
async def webhook(request, payload) -> JSONResponse: ...

@router.post("/webhook/test")
async def webhook_test(request, x_webhook_secret) -> JSONResponse: ...
```

### `src/api.py` after Phase 3 (~100 lines)
Only:
- FastAPI app instantiation with `lifespan=lifespan` from `api_lifecycle`
- CORS middleware setup
- `include_router()` calls for all 30+ sub-routers
- `_build_cors_origins()` helper

---

## Phase 4 — Split `src/logic.py` (946 → ~120 lines)

#### `src/pipeline/signal_forward.py` (~100 lines)
**Source:** `logic.py:83–112`

```python
def should_forward_alert(data: Dict) -> tuple[bool, List[str], Dict]:
    """Pre-execution filter. Checks run_mode, size, RR ratio, and active positions."""
```

#### `src/pipeline/trade_entry.py` (~250 lines)
**Source:** `logic.py:113–650` (entry path)

```python
def execute_entry(
    payload: Dict,
    dry_run: bool,
    ai_result: Optional[Dict],
    profile: Optional[Dict],
) -> None:
    """Position sizing → broker order submission → DB write → notification."""
```

#### `src/pipeline/trade_exit.py` (~200 lines)
**Source:** `logic.py:650–900` (exit path)

```python
def execute_exit(
    payload: Dict,
    dry_run: bool,
    profile: Optional[Dict],
) -> None:
    """Fetch open position → close at broker → update DB → PnL notification."""
```

### `src/logic.py` after Phase 4 (~120 lines)
- `_get_cached_balance()` — broker balance with watermark cache
- `_get_paper_trader_instance()` — paper trading singleton
- `process_trade()` — thin dispatcher routing to `execute_entry` or `execute_exit`

---

## Phase 5 — Split `src/adapters/execution/meta_api_adapter.py` (974 → ~120 lines)

#### `src/adapters/execution/http_retry.py` (~100 lines)
```python
def request_with_retry(method: str, url: str, timeout: int, **kwargs) -> Optional[Response]:
    """Retry with exponential backoff. MAX_RETRIES=3. Returns None on exhaustion."""
```

#### `src/adapters/execution/order_submitter.py` (~200 lines)
```python
def submit_order(token, account_id, request: OrderRequest) -> ExecutionResult: ...
```

#### `src/adapters/execution/order_manager.py` (~200 lines)
```python
def close_order(token, account_id, request: CloseRequest) -> ExecutionResult: ...
def modify_sl(token, account_id, position_id: str, new_sl: float) -> ExecutionResult: ...
def modify_tp(token, account_id, position_id: str, new_tp: float) -> ExecutionResult: ...
```

#### `src/adapters/execution/account_info.py` (~120 lines)
```python
def get_account_info(token: str, account_id: str) -> Dict: ...
def get_balance(token: str, account_id: str, fallback: float) -> float: ...
```

#### `src/adapters/execution/position_reader.py` (~150 lines)
```python
def get_positions(token: str, account_id: str) -> List[Dict]: ...
def get_open_orders(token: str, account_id: str) -> List[Dict]: ...
```

### `src/adapters/execution/meta_api_adapter.py` after Phase 5 (~120 lines)
`MetaApiAdapter` class skeleton: stores `token`, `account_id` and delegates every method call to the sub-modules above.

---

## Phase 6 — Split `src/core/risk_engine.py` (601 → ~60 lines)

#### `src/core/risk_models.py` (~60 lines)
```python
class RiskRejectionReason(str, Enum): ...
class RiskCheckResult(BaseModel): ...
class TradeRiskParams(BaseModel): ...
```

#### `src/core/position_sizer.py` (~280 lines)
```python
def calculate_max_position_size(payload: Dict, symbol_overrides=None) -> float: ...
def calculate_position_size_with_spread(payload: Dict, spread_pips: float, ...) -> float: ...
```

#### `src/core/risk_guardian.py` (~180 lines)
```python
class RiskGuardian:
    def check_daily_loss(self, daily_pnl: float) -> RiskCheckResult: ...
    def check_max_drawdown(self, equity: float, balance: float) -> RiskCheckResult: ...
    def check_position_risk(self, payload: Dict) -> RiskCheckResult: ...
```

### `src/core/risk_engine.py` after Phase 6 (~60 lines)
Re-export shim only — imports all public symbols from the 3 new files for backward compatibility.

---

## Phase 7 — Trim remaining files

### `src/core/guard_rails/correlation.py` (697 → 300 lines)

**Extract to `src/core/guard_rails/currency_utils.py`** (~130 lines):
```python
def extract_currencies(symbol: str) -> tuple[Optional[str], Optional[str]]: ...
def get_correlation_groups(symbol: str) -> List[str]: ...
```

**Extract to `src/core/guard_rails/correlation_db.py`** (~100 lines):
```python
def get_active_positions_from_db() -> List[ActivePosition]: ...
def create_correlation_manager_from_settings() -> CorrelationManager: ...
```

### `src/core/dynamic_config.py` (388 → 180 lines)

**Extract to `src/core/time_rules.py`** (~200 lines):
```python
def get_active_time_rules() -> list: ...
def check_time_rule_trigger(rule: dict) -> tuple[bool, Optional[float]]: ...
def apply_time_based_rules() -> Optional[float]: ...
```

### `src/services/notification_service.py` (449 → 200 lines)

**Extract to `src/services/notification_formatters.py`** (~150 lines):
```python
def format_entry_message(payload: Dict, ai_result: Dict) -> NotificationPayload: ...
def format_exit_message(payload: Dict, pnl: float) -> NotificationPayload: ...
def format_guard_alert(reason: str, payload: Dict) -> NotificationPayload: ...
```

**Extract to `src/services/notification_utils.py`** (~120 lines):
```python
def get_pip_divisor(symbol: str) -> float: ...
def format_price_with_distance(price, distance, unit, is_index) -> str: ...
def format_ai_analysis(ai_result: Optional[dict]) -> Optional[str]: ...
def derive_session(bar_time_iso: Optional[str]) -> Optional[str]: ...
```

### `src/services/liquidity_scorer.py` (385 → 200 lines)

**Extract to `src/services/liquidity_threshold.py`** (~150 lines):
```python
def compute_dynamic_departure_threshold(payload: dict, base: float = 60.0) -> float: ...
def get_dynamic_threshold_info() -> dict: ...
```

---

## Full Dependency Map (post-refactor)

```
Pine Script → POST /webhook
    │
    src/api_webhook.py
    src/api_lifecycle.py
    src/api.py (app factory)
         │ Redis queue
         ▼
    src/worker.py  (polling loop)
         │
         ▼
    src/pipeline/trade_processor.py
         ├── src/core/safety.py                  [global guards]
         ├── src/pipeline/signal_filter.py        [pine filters]
         ├── src/agents/supervisor.py             [AI decision]
         │       ├── src/ai/rf_predictor.py
         │       ├── src/ai/ensemble.py
         │       └── src/ai/llm_client.py
         └── src/pipeline/profile_executor.py     [per-account]
                 ├── src/pipeline/account_guards.py
                 │       ├── src/core/guard_rails/correlation.py
                 │       ├── src/core/guard_rails/prop_guard.py
                 │       └── src/services/mtm_guardian.py
                 └── src/logic.py  (dispatcher)
                         ├── src/pipeline/trade_entry.py
                         │       ├── src/core/position_sizer.py
                         │       └── src/adapters/execution/router.py
                         └── src/pipeline/trade_exit.py

Shared across all layers (no pipeline deps):
    src/pipeline/audit.py          (save_result)
    src/pipeline/idempotency.py    (trade_key dedup)
    src/pipeline/account_state.py  (DB reads)
    src/core/dynamic_config.py     (DB-backed settings)
    src/core/time_rules.py         (time-based risk rules)
    src/services/notification_service.py
```

---

## Guiding Rules for Every Phase

| Rule | Detail |
|------|--------|
| No behaviour changes | Each extraction is a pure move — no logic rewrites |
| Backward-compat shim | Original file re-exports moved symbols for 1 phase before deletion |
| Test gate | `pytest tests/ -v` must show 349 passed before merging each phase |
| One PR per phase | Never combine phases in one merge |
| Guard signature contract | `fn(payload, ...) -> Optional[str]` — `None` on pass, string on block |
| No cross-pipeline imports | `pipeline/` modules import only from `core/`, `ai/`, `adapters/`, `services/` |
| Circular import check | `python3 -c "import src.pipeline.trade_processor"` after each phase |
| Update registry | `docs/registry.md` updated to reflect new module map after each phase |

---

## Execution Summary

| Phase | File | Before | After | New Files |
|-------|------|--------|-------|-----------|
| 1 | `worker.py` | 2,068 | ~150 | 7 new pipeline modules |
| 2 | `ai/brain.py` | 1,554 | ~100 | 4 new AI modules |
| 3 | `api.py` | 1,091 | ~100 | `api_lifecycle.py`, `api_webhook.py` |
| 4 | `logic.py` | 946 | ~120 | 3 new pipeline modules |
| 5 | `meta_api_adapter.py` | 974 | ~120 | 5 new adapter modules |
| 6 | `risk_engine.py` | 601 | ~60 | 3 new core modules |
| 7 | 4 medium files | 1,619 | ~780 | 8 new modules |
| **Total** | | **~8,853** | **~1,430** | **30 new files** |
