# RD Concepts Research Data Lake Design

## Purpose

Build an offline RD Concepts research data lake that archives Discord history, chart images, setup notes, strategy rules, and candidate signals for future analysis. The goal is not to execute trades. The goal is to learn which pairs, sessions, setups, and rule filters the RD Concepts strategy appears to favor, then use that evidence later to tune the existing PineScript strategy and bot permissions.

The current execution bot already enters trades from the strategy. This project focuses on the missing research layer: collecting and structuring the Discord server's educational and signal history so future analysis can answer what to trade, when to trade, and which setup conditions deserve automation.

## Scope

The pipeline will live in `scripts/rd_concepts_pipeline/`. Generated data will live in `data/rd_concepts/`.

Included:
- Scrape configured RD Concepts Discord channels through Discord API v10.
- Download message attachments and embed images.
- Store raw messages in append/resume-friendly JSONL files.
- Parse trading signals, setup notes, concepts, timeframes, sessions, and chart links.
- Extract rule-like educational content and concept frequencies.
- Build a knowledge base grouped by pair, direction, setup tag, timeframe, session, and channel.
- Provide a Streamlit dashboard for browsing the local data lake.
- Add a channel discovery helper so missing channel IDs can be filled without guessing.

Deferred:
- Live trading changes.
- Broker, MetaApi, worker, guard rail, or execution changes.
- Automatic PineScript modification.
- PineScript signal comparison against OHLCV. That should come after the scraped dataset is clean and after TradingView backtest exports or alert logs are available.

## Non-Goals

- Do not import or call live trading execution paths.
- Do not write Discord credentials to committed files.
- Do not assume parsed Discord text is ground truth without evidence flags.
- Do not rank pairs as profitable without outcome labels or external backtest validation.
- Do not try to clone the full PineScript engine in Python during the first implementation slice.

## Directory Layout

```text
scripts/rd_concepts_pipeline/
├── config.py
├── list_channels.py
├── scraper.py
├── parser.py
├── rules_extractor.py
├── knowledge_base.py
├── dashboard.py
├── run_all.sh
├── requirements.txt
└── README.md

data/rd_concepts/
├── raw/
│   └── <channel>/
│       ├── messages.jsonl
│       ├── manifest.json
│       └── images/
├── processed/
│   ├── signals.csv
│   ├── rules.jsonl
│   ├── concepts.json
│   ├── image_index.csv
│   └── knowledge_base.json
└── reports/
    └── research_summary.md
```

## Configuration

`config.py` will contain settings and channel names, but not secrets. Secrets are loaded from environment variables or a local `.env` file that is not committed.

Required settings:
- `RD_DISCORD_AUTHORIZATION`: Discord API authorization value.
- `RD_DISCORD_SERVER_ID`: RD Concepts server ID.
- `RD_DATA_DIR`: default `data/rd_concepts`.
- `RD_REQUEST_TIMEOUT_SECONDS`, `RD_MAX_RETRIES`, and download retry settings.

Channel names and IDs are configured in `scripts/rd_concepts_pipeline/config.py`.
`list_channels.py` lists visible text/forum channels in the configured server so
the channel map can be completed without guessing.

Incomplete channel IDs are skipped with a warning.

All logs must redact token-like values and authorization headers.

## Raw Scraper

`scraper.py` fetches messages from `GET /api/v10/channels/{channel_id}/messages?limit=100`, paginating with `before=<last_message_id>` until exhausted. It handles:
- `429` by sleeping for Discord's `retry_after` value.
- `403` by logging and skipping the channel.
- transient HTTP/network errors with bounded retries.
- malformed messages by preserving raw message fields where possible and continuing.

Each raw record in `messages.jsonl` includes:
- `id`
- `channel`
- `channel_id`
- `timestamp`
- `author`
- `content`
- `attachments`
- `embeds`
- `images`
- `message_url`
- `raw`

Images include both attachments and embed image/thumbnail URLs. Files are saved under `data/rd_concepts/raw/<channel>/images/` using stable names that include message ID and attachment/embed position. `manifest.json` records counts, first/last message IDs, download failures, and scrape timestamps so runs are resumable and auditable.

## Parser

`parser.py` reads raw messages and emits `processed/signals.csv` plus `processed/image_index.csv`.

Signal detection uses multiple patterns:
- Explicit forms such as `PAIR LONG/SHORT entry SL x TP y`.
- Buy/sell forms such as `PAIR BUY/SELL @ price, Stop x, Target y`.
- Looser setup forms where a known pair appears near directional bias, timeframe, and levels.

The parser extracts:
- `signal_id`, `message_id`, `timestamp`, `channel`, `pair`, `direction`, `timeframe`
- `entry`, `stop_loss`, `take_profit`, `rr_ratio`
- `setup_notes`, `setup_tags`, `confluence_tags`
- `session`
- `has_chart`, `chart_paths`
- `quality_flags`
- `raw_message`

Setup and confluence tags include liquidity, sweep, BOS, CHOCH, displacement, imbalance, FVG, order block, EMA, fib, mechanical, structure, inducement, trend, compression, and session references.

The parser marks ambiguous rows instead of dropping them. Rows with pair/setup evidence but missing levels are still useful for the future data lake.

## Rules Extractor

`rules_extractor.py` reads education-heavy channels such as webinars, market breakdowns, daily forecasts, mechanical chart channels, and analysis channels. It searches for strategy language and saves matching messages to `processed/rules.jsonl`.

Keyword families include:
- rule language: rule, setup, entry, condition, must, always, never
- structure language: structure, BOS, CHOCH, displacement, imbalance
- liquidity language: liquidity, sweep, inducement
- S&D language: order block, OB, fair value gap, FVG, PD array
- mechanical language: mechanical, 5m, 30m, EMA, fib

Each rule record includes:
- `rule_id`
- `message_id`
- `timestamp`
- `channel`
- `author`
- `content`
- `keyword_hits`
- `concept_tags`
- `images`
- `message_url`

The extractor also builds `processed/concepts.json`, including frequency counts and example message IDs for the most common concepts.

## Knowledge Base

`knowledge_base.py` combines signals, rules, concepts, and image metadata into `processed/knowledge_base.json`.

It summarizes:
- signals per pair
- long/short split by pair
- active channels by pair
- timeframe breakdown
- session breakdown
- setup tag frequency by pair and direction
- chart image paths grouped by pair, setup, direction, and outcome label when available
- rule/concept examples for each setup family
- evidence quality counts: clear, ambiguous, chart-backed, rule-backed, outcome-known

The first implementation does not claim profitability. It ranks evidence strength and research usefulness, not expected return.

## Dashboard

`dashboard.py` is a local Streamlit app for browsing the data lake. It shows:
- total parsed signals per channel
- pair and timeframe breakdowns
- setup/confluence tag frequencies
- searchable rules viewer
- signal table with filters for pair, direction, timeframe, date range, channel, session, and tag
- chart image gallery grouped by pair and setup tag
- raw message drilldown when a row is selected

Win/loss charts remain optional until outcome labels exist. The dashboard should show `unknown` explicitly rather than inventing results.

## Future PineScript Tuning Flow

After the data lake is built, a later phase can compare the discovered RD operating envelope with the current PineScript strategy:
- Which pairs RD emphasizes or avoids.
- Which sessions and timeframes dominate clean examples.
- Which confluences appear most often before valid entries.
- Which filters are framed as mandatory or no-trade conditions.
- Which setup families have enough examples to justify Pine input tuning.

Inputs for that future phase should be TradingView backtest exports, Pine alert logs, or broker/bot trade history, not Binance OHLCV by default. This preserves alignment with TradingView data and avoids unsupported FX/metals symbols.

## Error Handling

All scripts must:
- use timestamped logging
- continue past bad messages, failed image downloads, and unknown channels
- write enough manifest data to diagnose partial runs
- avoid printing secrets
- return nonzero only for configuration failures or unrecoverable output write failures

## Testing and Verification

Initial verification:
- `python scripts/rd_concepts_pipeline/list_channels.py --help`
- `python scripts/rd_concepts_pipeline/scraper.py --dry-run`
- parser/rules/knowledge-base scripts run against small fixture JSONL files
- dashboard imports without loading credentials

Implementation tests should use fixtures rather than real Discord data where possible.

## Open Implementation Notes

- The authorization value must be rotated if it was previously pasted into chat or logs.
- `requirements.txt` for this utility can be local to `scripts/rd_concepts_pipeline/`.
- The implementation should stage only the new pipeline files and avoid existing dirty `scripts/optimization_results` changes.
