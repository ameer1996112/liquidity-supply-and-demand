# RD Concepts Pipeline

Offline Discord research data lake for RD Concepts strategy analysis. The pipeline collects configured Discord channel history, parses research signals and images, extracts strategy concepts, and builds local knowledge-base artifacts for review in Streamlit.

## Safety

This pipeline is research-only. It does not execute trades, call MetaApi, import the worker, or modify live bot state. It writes local research files under `data/rd_concepts` by default.

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

These files are local research artifacts only. They are not read by the live trading worker and do not change bot state.
