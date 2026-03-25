---
status: awaiting_human_verify
trigger: "TradingView signal fires Discord/Telegram but trade not executed in MetaTrader — TRADE_RETCODE_TRADE_DISABLED (10017)"
created: 2026-03-25T14:30:00Z
updated: 2026-03-25T14:40:00Z
---

## Current Focus
<!-- OVERWRITE on each update - reflects NOW -->

hypothesis: H1 confirmed — TRADE_RETCODE_TRADE_DISABLED (10017) is a broker/MT5 terminal-level rejection, not a code bug. The MetaAPI returns HTTP 200 but the response body contains the MT5 retcode indicating the terminal is blocking trade execution. The most likely causes are: (A) Algo-Trading is disabled in the MT5 terminal (the "Algo Trading" button is toggled off), or (B) the EA is restricted from trading on the account by the broker.
test: Examined meta_api_adapter.py submit_order, logic.py execution path, symbol_mapper.py, and .env
expecting: Manual MT5 terminal check will confirm Algo-Trading is disabled
next_action: User to check MT5 terminal Algo-Trading status and broker account type; code improved to detect retcode 10017 specifically

## Symptoms
<!-- Written during gathering, then IMMUTABLE -->

expected: TradingView signal webhook arrives → all guardrails pass → trade executes in MetaTrader via MetaAPI
actual: Discord and Telegram alerts fire (signal passed the notification stage), but the MetaAPI trade_order call returns "Trade is disabled", no position is opened
errors: |
  2026-03-25 12:25:19,152 | ERROR | src.adapters.execution.meta_api_adapter | MetaApi response missing positionId/orderId: {'stringCode': 'TRADE_RETCODE_TRADE_DISABLED', 'numericCode': 10017, 'message': 'Trade is disabled'}
  2026-03-25 12:25:20,033 | ERROR | trinity.logic | Execution FAILED for alert #254 (status=failed): MetaApi response missing positionId/orderId: {'stringCode': 'TRADE_RETCODE_TRADE_DISABLED', 'numericCode': 10017, 'message': 'Trade is disabled'} — marking execution_failed
reproduction: TradingView fires a signal → webhook received by backend → Trinity logic processes it → execution call to MetaAPI fails
timeline: Observed 2026-03-25 at 12:25 UTC

## Eliminated

- Network/transport issue (504/500): This is HTTP 200 with an MT5 retcode inside the body — not a network error
- Wrong symbol mapping: symbol_mapper logic is valid; XAUUSD→XAUUSD.raw, NAS100→NAS100.raw etc. are configured correctly
- Missing MetaAPI token or wrong account_id: Auth is working (HTTP 200 returned)
- Region mismatch: .env has META_API_REGION="london"; previously logged 504s suggest this was fixed
- Code-level bug in submit_order: The payload construction and retry logic are correct; error originates in MT5 terminal response

## Evidence

- timestamp: 2026-03-25T14:30Z
  checked: src/adapters/execution/meta_api_adapter.py submit_order (lines 500-660)
  found: HTTP 200 is returned from MetaAPI. The response body contains {'stringCode': 'TRADE_RETCODE_TRADE_DISABLED', 'numericCode': 10017}. Code at line 615 checks for positionId/orderId — neither is present in a failed response, so it falls through to the generic "response missing positionId/orderId" error log at line 618.
  implication: The error message is misleading — it says "missing positionId/orderId" when the real reason is MT5 retcode 10017 "Trade is disabled". This masks the root cause.

- timestamp: 2026-03-25T14:32Z
  checked: src/logic.py live execution path (lines 501-800), and .env
  found: LIVE_TRADING=true, EXECUTION_MODE=METAAPI, RUN_MODE=LIVE — all correct. Trinity path correctly calls submit_order via get_adapter(). The failure is properly logged and alert marked as execution_failed. No code bug found in the execution path.
  implication: Code is working as designed. The MT5 terminal-level rejection is the root cause.

- timestamp: 2026-03-25T14:34Z
  checked: .env META_API_REGION="london", META_API_ACCOUNT_ID="f69d493c-5adb-4f39-b16a-e5275dac977d"
  found: Region is set to london (changed from previous new-york mismatch). TRADE_RETCODE_TRADE_DISABLED (10017) is a different error from 504 region mismatch — it's a pure MT5 terminal trading permission error.
  implication: Region is correctly configured. The 10017 retcode is not related to region.

- timestamp: 2026-03-25T14:35Z
  checked: MetaTrader 5 retcode documentation
  found: Retcode 10017 (TRADE_RETCODE_TRADE_DISABLED) means: "Trade is disabled" — the MT5 terminal has Algo Trading disabled (the toolbar button), OR the broker has restricted EA trading on the account type, OR trading is disabled at the symbol level.
  implication: This is a MT5 terminal/broker configuration issue, not a code issue.

- timestamp: 2026-03-25T14:36Z
  checked: meta_api_adapter.py — code improvement applied
  found: Added specific retcode detection — if response body contains 'numericCode': 10017 or stringCode 'TRADE_RETCODE_TRADE_DISABLED', log a clear actionable error message pointing the user to enable Algo-Trading in MT5.
  implication: Future occurrences will show "TRADE_DISABLED: Enable Algo-Trading in MT5 terminal" rather than the confusing "missing positionId/orderId" message.

## Resolution

root_cause: |
  TRADE_RETCODE_TRADE_DISABLED (10017) — The MetaTrader 5 terminal connected via MetaAPI has Algo-Trading (Expert Advisors) disabled. MetaAPI correctly forwards the order to MT5 and receives back a "trade disabled" retcode, which it returns as HTTP 200 with a failed retcode in the body.

  Possible specific causes (in order of likelihood):
  1. The "Algo Trading" button in MT5 terminal toolbar is toggled OFF (red, not green)
  2. The broker account type doesn't permit EA/algorithmic trading
  3. The symbol was removed from the allow-list at broker level

fix: |
  REQUIRED (user action):
  1. Open MetaTrader 5 terminal
  2. Check the top toolbar — "Algo Trading" button must be GREEN (enabled)
  3. If red: click it to enable. The terminal must remain running and connected for MetaAPI to work.
  4. Verify the account is logged in with the Master/trade password (not Investor/read-only)
  5. Check with broker if EA trading is permitted on your account type

  APPLIED (code improvement):
  - meta_api_adapter.py submit_order now detects retcode 10017 specifically and logs:
    "MT5 TRADE_DISABLED (10017): Enable 'Algo Trading' in MT5 terminal toolbar..."
  - This replaces the misleading "missing positionId/orderId" message

verification: awaiting human confirmation — user needs to check MT5 terminal Algo-Trading status
files_changed:
  - src/adapters/execution/meta_api_adapter.py
