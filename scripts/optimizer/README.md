# Optimizer README

## Goal

Run TradingView optimizer with managed restart/watchdog flow and predictable tab count.

Current recommended workflow:
- screening run: `4` workers, `80` trials
- deep run later: top pairs only, `150`+ trials

## Before Start

1. Start Chrome with optimizer profile:

```bash
bash /Users/ameeramer/dev/projects/galilsoftware/sources/trading/scripts/optimizer/start-chrome.sh
```

2. Make sure TradingView login works in that Chrome profile.
3. Use single-chart tabs only. No multi-chart layout.
4. Keep chart tab count equal worker count.

## Recommended Start

### Screening Run

Fast parallel screen for all pairs:

```bash
bash /Users/ameeramer/dev/projects/galilsoftware/sources/trading/scripts/optimizer/run.sh --managed --parallel --workers 4 --bayesian --n-trials 80
```

### Deep Run

Use after screening. Re-run only best pairs:

```bash
bash /Users/ameeramer/dev/projects/galilsoftware/sources/trading/scripts/optimizer/run.sh --managed --parallel --workers 4 --bayesian --pairs EURUSD,GBPUSD,USDCAD,USDCHF --n-trials 150
```

## Status / Monitoring

### Watch managed status

```bash
python3 -m scripts.optimizer.watchdog status
```

or:

```bash
bash /Users/ameeramer/dev/projects/galilsoftware/sources/trading/scripts/optimizer/run.sh --status
```

### Watch live log

```bash
tail -f /Users/ameeramer/dev/projects/galilsoftware/sources/trading/scripts/optimization_results/run_*.log
```

If you want one specific run:

```bash
tail -f /Users/ameeramer/dev/projects/galilsoftware/sources/trading/scripts/optimization_results/run_YYYYMMDD_HHMMSS.log
```

## Stop / Restart

### Stop managed run

```bash
bash /Users/ameeramer/dev/projects/galilsoftware/sources/trading/scripts/optimizer/run.sh --stop-managed
```

### Force restart managed run

```bash
bash /Users/ameeramer/dev/projects/galilsoftware/sources/trading/scripts/optimizer/run.sh --force-restart
```

## Result Files

Main output folder:

```text
/Users/ameeramer/dev/projects/galilsoftware/sources/trading/scripts/optimization_results
```

Important files:
- `run_*.log` — human log
- `optimizer_status_current.json` — current machine status
- `optimizer_worker_*_<runid>.jsonl` — per-worker machine log
- `parallel_results_vantage.json` — latest completed Vantage forex dataset
- `parallel_results_oanda.json` — latest completed OANDA forex dataset
- `parallel_results_fxcm.json` — latest completed FXCM forex dataset
- `parallel_results.json` — legacy mirror of the most recently written broker dataset for compatibility

## Which Log To Trust

Trust order:
1. `optimizer_worker_*_<runid>.jsonl`
2. TradingView tab Strategy Tester
3. shared stdout log

Why:
- shared stdout can look mixed under parallel writes
- worker JSONL keeps worker id, symbol, hashes, metrics

## What Good Run Looks Like

- worker count matches chart tab count
- workers start on different pairs
- `verified_symbol` matches expected symbol in worker JSONL
- `results_hash_before` and `results_hash_after` change on fresh trials
- no flood of:
  - `Page.evaluate: Target page, context or browser has been closed`
  - repeated stale warnings on same worker

## Known Rules

- use Chrome, not TradingView desktop app, for now
- current automation built for Chrome CDP on port `9222`
- keep other heavy apps closed if CPU high
- do not close optimizer tabs while run active

## Current Best Practice

- screen all pairs first with `80` trials
- deep-run only winners later
- prefer `4` workers over `6` until stability proven
