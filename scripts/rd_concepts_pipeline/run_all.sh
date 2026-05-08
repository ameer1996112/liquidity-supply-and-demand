#!/usr/bin/env bash
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

python scripts/rd_concepts_pipeline/scraper.py
python scripts/rd_concepts_pipeline/parser.py
python scripts/rd_concepts_pipeline/rules_extractor.py
python scripts/rd_concepts_pipeline/knowledge_base.py

echo "RD Concepts data lake complete. Run: streamlit run scripts/rd_concepts_pipeline/dashboard.py"
