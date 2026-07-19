# RD Concepts Pipeline

Offline Discord and YouTube research data lake for RD Concepts strategy analysis. The pipeline collects configured Discord history, inventories the six approved YouTube channels, caches timestamped English subtitles, extracts candidate evidence spans, and validates versioned five-minute strategy rules and benchmark cases.

## Safety

This pipeline is research-only. It does not execute trades, call MetaApi, import the worker, or modify live bot state. It writes local research files under `data/rd_concepts` by default.

Full transcripts remain under ignored `data/rd_concepts`; they are never committed as rule definitions. Versioned rules contain paraphrases, source IDs, and exact evidence timestamps. The protected indicator is comparison evidence, not a source of executable rules.

Do not put trading execution logic in this package. Keep it separate from `src/logic.py`, `src/worker.py`, broker adapters, and live account services.

## Credentials

Discord credentials can be provided in `scripts/rd_concepts_pipeline/.env` or as environment variables:

```bash
RD_DISCORD_AUTHORIZATION=...
RD_DISCORD_SERVER_ID=...
RD_DATA_DIR=data/rd_concepts
```

Do not commit authorization values or tokens. If an authorization value is pasted into chat, shell history, or logs, rotate it before using the pipeline again.

## Install

From the repository root:

```bash
source ./venv/bin/activate
pip install -r scripts/rd_concepts_pipeline/requirements.txt
```

## Configure Channels

Use `list_channels.py` to discover Discord channel IDs:

```bash
python scripts/rd_concepts_pipeline/list_channels.py
```

Fill channel IDs in `scripts/rd_concepts_pipeline/config.py`. Channels still set to `PASTE_ID` or another incomplete value are skipped until they are filled in.

## Run

### YouTube Evidence

Inventory all six approved channels without downloading video media:

```bash
python scripts/rd_concepts_pipeline/youtube_sync.py inventory
```

Cache timestamped English subtitles for rule and edge-evidence videos:

```bash
python scripts/rd_concepts_pipeline/youtube_sync.py transcripts
```

Extract local candidate evidence spans:

```bash
python scripts/rd_concepts_pipeline/youtube_sync.py evidence
```

Run all YouTube stages:

```bash
python scripts/rd_concepts_pipeline/youtube_sync.py all
```

Use `--source rd_forex` to limit a run, `--refresh` to replace cached subtitles, and `--include-operations` to include automation/performance videos. Without the latter flag, transcript collection is limited to `RULE_SOURCE` and `EDGE_EVIDENCE`.

Video title classification has four research classes:

- `RULE_SOURCE`: courses, guides, checklists, and direct strategy definitions.
- `EDGE_EVIDENCE`: backtests, breakdowns, skipped trades, losses, and missed setups.
- `OPERATIONS_EVIDENCE`: bots, automation, portfolios, and drawdown reports.
- `NON_RULE`: videos that do not supply strategy evidence.

Rule authority is manual rulings first, latest applicable RD Forex rules second, Arger/Mangoe/RT corroboration third, Charney filters fourth, Trirex operations evidence fifth, and protected-indicator comparison last. Unresolved conflicts fail closed and cannot become executable rules.

### Discord Research

Dry-run the scraper without writing downloaded data:

```bash
python scripts/rd_concepts_pipeline/scraper.py --dry-run
```

Run the full scraper:

```bash
python scripts/rd_concepts_pipeline/scraper.py
```

Parse scraped messages and images:

```bash
python scripts/rd_concepts_pipeline/parser.py
```

Extract rules:

```bash
python scripts/rd_concepts_pipeline/rules_extractor.py
```

Build the knowledge base:

```bash
python scripts/rd_concepts_pipeline/knowledge_base.py
```

Open the dashboard:

```bash
streamlit run scripts/rd_concepts_pipeline/dashboard.py
```

Run the complete offline pipeline:

```bash
scripts/rd_concepts_pipeline/run_all.sh
```

The shell entrypoint remains Discord-only by default. Include the YouTube sync explicitly:

```bash
RD_INCLUDE_YOUTUBE=1 scripts/rd_concepts_pipeline/run_all.sh
```

## Outputs

Default outputs are written under `data/rd_concepts`:

- Raw Discord messages: `raw/<channel>/messages.jsonl`
- Raw downloaded images: `raw/<channel>/images/`
- Scrape manifest: `raw/<channel>/manifest.json`
- Processed signals: `processed/signals.csv`
- Image index: `processed/image_index.csv`
- Extracted rules: `processed/rules.jsonl`
- Extracted concepts: `processed/concepts.json`
- Knowledge base: `processed/knowledge_base.json`
- YouTube inventory: `youtube/inventory.jsonl`
- Timestamped transcript cache: `youtube/transcripts/*.json3`
- Candidate evidence spans: `youtube/evidence_candidates.jsonl`
- YouTube sync manifest: `youtube/manifest.json`

Committed validation inputs live under `scripts/rd_concepts_pipeline/reference`. `rd_5m_rules.jsonl` is checked for evidence, status, precedence, supersession, and unresolved conflicts. `rd_5m_cases.jsonl` distinguishes `PROVISIONAL` observations from `APPROVED` exact-OHLC release fixtures.

These files are local research artifacts only. They are not read by the live trading worker and do not change bot state.

## Detector Benchmark

Run the deterministic reference detector against the committed case catalog:

```bash
PYTHONPATH=. ./venv/bin/python -m scripts.rd_concepts_pipeline.benchmark_cases
```

Use `--price-tolerance` only when the approved label defines a feed-specific rounding tolerance:

```bash
PYTHONPATH=. ./venv/bin/python -m scripts.rd_concepts_pipeline.benchmark_cases \
  --price-tolerance 0.001
```

The report pairs zones by direction, origin bar time, and confirmation bar time. It separately reports missing zones, unexpected zones, classification or bound mismatches, lifecycle mismatches, and labeled rejection mismatches. Drawing order and local zone IDs do not affect matching.

Statuses are strict:

- `PASSED` means every `APPROVED` case matched within the explicit tolerance.
- `FAILED` means at least one approved label disagreed with the detector.
- `NO_APPROVED_CASES` means the catalog contains only provisional evidence and cannot support an accuracy result.

`PROVISIONAL` screenshots never count as passing labels. Promote one to `APPROVED` only after exact 5-minute OHLC, feed, symbol, bar timestamps, expected geometry, and applicable rule IDs have been recorded and manually reviewed. A passing finite corpus proves agreement with that corpus; it is not a claim of universal or future trading accuracy.
