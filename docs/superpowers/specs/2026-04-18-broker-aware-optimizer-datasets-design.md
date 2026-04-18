# DEV-137 Broker-Aware Optimizer Datasets

## Goal

Allow the optimizer workflow to run against a selected broker and persist the resulting dataset into a broker-specific optimizer results file so results can be compared later across brokers.

The first supported brokers are:

- `vantage`
- `oanda`
- `fxcm`

The initial implementation targets forex only, but the data model should be shaped so futures can be added later without redesigning the optimizer run schema.

## Problem

Today the optimizer workflow treats results as a single shared dataset. That makes it hard to answer questions like:

- What are the best 33-pair results on Vantage?
- How do those same pairs perform on OANDA?
- Which parameter sets are stable across brokers?

Because the optimizer results are effectively shared, broker-specific comparisons are error-prone and easy to overwrite.

## Non-Goals

- No changes to live trade execution logic
- No changes to alert setup behavior in this first step
- No futures UI yet
- No historical multi-run append-only dataset archive in this first step

## User Experience

### Optimizer Run Launcher

Add a new `Broker` dropdown to the optimizer run launcher with:

- `Vantage`
- `OANDA`
- `FXCM`

Default selection:

- `Vantage`

Keep existing pair selection behavior:

- `All pairs` remains available
- `All pairs` remains the default
- Manual pair entry continues to work unchanged

The first version does not expose a `Market` selector in the UI. The system stores `market = forex` behind the scenes.

### Run History / Details

Each optimizer run should display its broker in:

- run history list/cards
- active run details
- any selected run metadata shown in the workspace

Older runs without a broker value should remain readable. The UI can display a fallback such as `Unknown` for legacy records.

## Data Model

### Optimizer Run Request

Add:

- `broker: str`

Accepted values:

- `vantage`
- `oanda`
- `fxcm`

The backend also stores:

- `market: "forex"`

even though the frontend does not yet expose market selection.

### Optimizer Run Persistence

Each optimizer run record should persist:

- `broker`
- `market`

This allows later filtering, comparison, and extension to futures.

Legacy records may have these fields missing or null. The read path must tolerate that.

## Result File Naming

Completed optimizer output should be written to broker-specific files:

- `scripts/optimization_results/parallel_results_vantage.json`
- `scripts/optimization_results/parallel_results_oanda.json`
- `scripts/optimization_results/parallel_results_fxcm.json`

In this first step, the broker file should be treated as the current dataset for that broker and replaced by the latest completed run for that broker.

This is intentionally simpler than keeping a historical append-only broker file.

## Execution Flow

1. User opens optimizer page
2. User chooses broker
3. User chooses `All pairs` or manual pairs
4. User starts optimizer run
5. Frontend sends broker in create-run payload
6. API validates broker
7. Service stores run with broker and `market = forex`
8. Local agent / runner receives broker context
9. Completed run writes results into the matching broker-specific output file
10. Run summary and history show which broker was used

## Runner Behavior

The local optimizer pipeline must receive broker context as part of the run payload.

That broker value should control which output file is produced when the run finishes.

The runner should not mix results between brokers.

## Backward Compatibility

- Existing runs without broker must still load in the dashboard
- Existing shared optimizer behavior should keep working until the new broker-aware path is wired through fully
- Any code still reading the old shared output should continue to work unless explicitly migrated in a follow-up

## Futures Readiness

This first step stores:

- `market = forex`
- `broker = vantage|oanda|fxcm`

That allows a future extension to:

- add a `Market` dropdown
- support futures-specific pair universes/providers
- write files like `parallel_results_futures_<provider>.json`

The key point is that the backend model becomes `market + broker`, even though only broker is exposed in the first UI version.

## Risks

### Schema mismatch

If the optimizer runs table does not yet support `broker` and `market`, create-run will fail until the schema is updated or the persistence layer is made tolerant.

### Partial wiring

If broker is added to the UI and API but not passed into the runner output path, users may think they are generating isolated broker datasets while still overwriting a shared file.

### Legacy consumers

Any downstream flow still reading only `parallel_results.json` will not automatically become broker-aware.

## Testing

### Backend

- create optimizer run with each supported broker
- reject unsupported broker values
- verify persisted runs include broker and market
- verify completed run summary identifies the broker-specific output path

### Frontend

- broker selector defaults to `Vantage`
- submitted payload includes selected broker
- run details render broker value

### Integration

- run a Vantage optimizer job and confirm it writes `parallel_results_vantage.json`
- run an OANDA optimizer job and confirm it writes `parallel_results_oanda.json`
- verify files do not overwrite each other

## Follow-Up Work

Not part of this task, but enabled by it:

- broker-aware alert setup sourcing
- broker-aware top-pairs comparison views
- market selector with futures support
- richer historical dataset comparisons across runs
