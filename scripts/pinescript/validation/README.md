# RD Forex LAB Validation Artifacts

This directory holds repository-side validation support for the frozen RD Forex five-minute detector plan.

## Debug Event Collection

`POST /webhook/rd-forex/debug` persists validated non-execution LAB events to:

- `scripts/pinescript/validation/artifacts/<run_id>/events.jsonl`
- `scripts/pinescript/validation/artifacts/<run_id>/events.csv`

The endpoint does not enqueue Redis messages, write trade rows, or enable execution. Override the artifact directory with `RD_FOREX_DEBUG_ARTIFACT_DIR`.

## Fixture Schema

Reference fixtures are JSON arrays. Each row must be manually labeled from protected-reference Bar Replay evidence and include screenshot/evidence metadata. Do not fabricate protected-reference labels.

Required comparison fields:

- `symbol`, `feed`, `timeframe`
- `zone_id`, `model`, `zone_type`
- `origin_time`, `detection_time`, `confirmation_time`
- `top`, `bottom`
- `liquidity_price`, `liquidity_bar_index`, `liquidity_swept`, `target_swept`, `touched`
- `evidence`

Liquidity tie-break semantics for this phase are deterministic: choose the closest qualifying liquidity candidate by price distance to the zone edge, then the earliest pivot bar when distance ties, then the smallest residual price distance after tick normalization. Future bars and already-consumed levels are not valid candidates.

## Comparator

Run:

```bash
PYTHONPATH=. python scripts/pinescript/validation/rd_forex_compare.py \
  --fixture scripts/pinescript/validation/fixtures/rd_forex_reference_schema.example.json \
  --actual scripts/pinescript/validation/artifacts/<run_id>/events.jsonl \
  --report scripts/pinescript/validation/artifacts/<run_id>/comparison_report.json
```

The comparator reports missing, extra, boundary, timestamp, lifecycle, and repaint discrepancies. It is a repository-side artifact only; visual parity still requires real TradingView/reference fixtures.
