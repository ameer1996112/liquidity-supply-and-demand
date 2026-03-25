---
status: awaiting_human_verify
trigger: "MetaAPI calls to get_open_positions and get_account_information are failing intermittently with HTTP 500 and HTTP 504"
created: 2026-03-25T00:00:00Z
updated: 2026-03-25T00:00:00Z
---

## Current Focus
<!-- OVERWRITE on each update - reflects NOW -->

hypothesis: H1 confirmed — 504 errors caused by MetaAPI connection/region timeout are NOT retried (the retry loop only retries 5xx codes but 504 IS 5xx, however the retry backoff is too short for "account not connected" wake-up, AND the 500 "Failed to execute a callable" is a different transient MetaAPI-side error that does get retried but the backoff [1,3,5,10s] may be insufficient for broker connection establishment). The deeper problem: no reconnection health check before polling calls, and callers (account_sync_service, api_positions) call get_open_positions/get_account_information in tight loops without checking if broker is actually connected first.
test: Examined _request_with_retry logic, retry backoff values, callers, and connection check pattern
expecting: Confirm both 500 and 504 are 5xx and DO enter the retry path, but backoff schedule [1,3,5,10s] is insufficient for MetaAPI cold-start/reconnect (which can take 30-60s). Also confirm no pre-flight connection check exists.
next_action: Apply fix — add 504 awareness with longer backoff for broker-connection errors

## Symptoms
<!-- Written during gathering, then IMMUTABLE -->

expected: MetaAPI calls to get_open_positions and get_account_information succeed and return data
actual: Mix of HTTP 500 ("Failed to execute a callable") and HTTP 504 ("It seems like the account is not connected to broker yet or request URL you use does not match the account region")
errors: |
  MetaApi get_open_positions failed: HTTP 500 {"error":"Error","message":"Failed to execute a callable"}
  MetaApi get_account_information failed: HTTP 500 {"error":"Error","message":"Failed to execute a callable"}
  MetaApi get_account_information failed: HTTP 504 {"error":"TimeoutError","message":"It seems like the account f69d493c-5adb-4f39-b16a-e5275dac977d is not connected to broker yet or request URL you use does not match the account region."}
  MetaApi get_open_positions failed: HTTP 504 {"error":"TimeoutError","message":"It seems like the account f69d493c-5adb-4f39-b16a-e5275dac977d is not connected to broker yet or request URL you use does not match the account region."}
reproduction: Observed in production backend service logs on 2026-03-24, multiple times between 14:32 and 16:10 UTC
started: 2026-03-24, unknown if intermittent or persistent
account_id: f69d493c-5adb-4f39-b16a-e5275dac977d

## Eliminated
<!-- APPEND only - prevents re-investigating -->

## Evidence
<!-- APPEND only - facts discovered -->

- timestamp: 2026-03-25T00:01Z
  checked: meta_api_adapter.py _request_with_retry (lines 70-113)
  found: MAX_RETRIES=4, RETRY_BACKOFF=(1.0, 3.0, 5.0, 10.0). Retries on 5xx (500-599) AND on timeout/ConnectionError. 504 is a 5xx code so it DOES enter the retry branch. However total wait before giving up = 1+3+5+10 = 19s, then the 5th attempt. MetaAPI "account not connected" (504) requires broker reconnection which can take 30-120s — all retries exhaust and the call returns the 504 response to the caller.
  implication: The 4 retry attempts with 19s total backoff are insufficient for MetaAPI broker reconnect timeouts. After exhaustion, the non-200 response is returned and the caller logs the error.

- timestamp: 2026-03-25T00:02Z
  checked: meta_api_adapter.py get_account_information and get_open_positions (lines 211-308)
  found: Both methods call _request_with_retry with timeout=30. On non-200 response they log an error and return empty/zero data. No special handling for 504 "not connected" vs 500 "callable failed". Both errors are treated identically (log and fail).
  implication: The adapter makes no distinction between transient "callable failed" (500) and "broker not connected" (504). The 504 message explicitly says "account not connected to broker yet OR wrong region" — these need different handling.

- timestamp: 2026-03-25T00:03Z
  checked: config/settings.py lines 341-345
  found: meta_api_region defaults to "new-york" and is a single fixed value applied at adapter construction. The base_url is set once in __init__: f"https://mt-client-api-v1.{effective_region}.agiliumtrade.ai". Region is never refreshed after construction.
  implication: If the account's actual region differs from configured region, every call returns 504 "request URL does not match the account region". This is a configuration mismatch bug, not just a transient error.

- timestamp: 2026-03-25T00:04Z
  checked: api_positions.py _cached_get_open_positions (lines 25-33) and _cached_get_account_information (lines 36-44)
  found: Server-side TTL cache: positions=15s, account=30s. Cache stores the RESULT including empty list [] or {balance:0, equity:0} on failure. If MetaAPI fails, the failure result gets cached and subsequent calls return the empty/zero data for up to 15-30s without hitting MetaAPI again. But importantly, if 504 persists, every cache miss will return a new 504 failure.
  implication: The cache does NOT protect against repeated failures hitting MetaAPI — it only reduces load during healthy operation. During outages the cache TTL means stale failure data propagates to the UI.

- timestamp: 2026-03-25T00:05Z
  checked: circuit_breaker.py — is_metaapi_circuit_open only triggers on 429 (rate limit). 500 and 504 do NOT trigger the circuit breaker.
  found: The circuit breaker is only opened on HTTP 429 (lines 94-101 of adapter). HTTP 500 and 504 responses just trigger retries and then log+return failure. No circuit breaker is opened for persistent broker-disconnect 504s.
  implication: During a MetaAPI outage or broker disconnect, every poll (every 15s from api_positions, every 60s from account_sync_service) hammers MetaAPI with 5×retries each, amplifying the failure and potentially causing rate limiting.

- timestamp: 2026-03-25T00:06Z
  checked: git log — commit 0cc8430 "DEV-35 expand MetaAPI 5xx exponential back-off"
  found: DEV-35 only changed backoff from MAX_RETRIES=3/BACKOFF=(1,3,5) to MAX_RETRIES=4/BACKOFF=(1,3,5,10). Still only 4 retries with 19s cumulative wait.
  implication: DEV-35 improved resilience for short broker wake-up (up to ~20s) but is insufficient for longer reconnect events (30-120s).

- timestamp: 2026-03-25T00:07Z
  checked: The 504 error message text: "It seems like the account f69d493c... is not connected to broker yet OR request URL you use does not match the account region."
  found: Two distinct causes in ONE error: (A) broker not connected yet — transient, goes away when MetaAPI reconnects, and (B) wrong region URL — permanent misconfiguration. The current code treats both identically.
  implication: Root cause branches: if region is wrong → permanent 504s until config is fixed. If broker temporarily disconnected → transient 504s that need longer backoff/retry.

## Resolution
<!-- OVERWRITE as understanding evolves -->

root_cause: |
  Two compounding root causes:
  1. HTTP 504 "account not connected / wrong region" is treated identically to transient 500s.
     The retry backoff (1+3+5+10 = 19s total) is insufficient for MetaAPI broker reconnection,
     which can take 30-120s. After 4 retries all fail and the caller logs the error.
  2. No circuit breaker protection for persistent 504/500 failures — every poll cycle (every 15s
     for positions, every 60s for account sync) fires 4 retries × 30s timeout, flooding MetaAPI
     during an outage rather than backing off gracefully.
  Secondary: Region misconfiguration (META_API_REGION mismatch) would cause every call to 504.
fix: |
  In _request_with_retry: detect 504 responses specifically and apply a longer back-off
  (initial 15s, then 30s) rather than the standard 1-10s schedule. Also trigger circuit breaker
  on persistent 504s (after max retries) to prevent poll flooding during broker-disconnect events.
  Add a BROKER_RECONNECT_BACKOFF tuple for 504 distinct from the standard 5xx backoff.
verification: awaiting human confirmation in production logs
files_changed:
  - src/adapters/execution/meta_api_adapter.py
