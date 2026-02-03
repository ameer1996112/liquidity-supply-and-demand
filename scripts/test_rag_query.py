"""
Quick sanity check for the Supabase RAG pipeline.

Run from project root:

    python scripts/test_rag_query.py

It will:
  - Connect to Supabase using `config.Settings`
  - Count how many documents exist in the `documents` table
  - Run a sample similarity search via RagEngine and print the top hits
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

# Ensure project root (with `config/` and `src/`) is on sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import get_settings  # type: ignore
from src.ai.rag_engine import RagEngine  # type: ignore


def main() -> None:
    load_dotenv(ROOT / ".env")

    settings = get_settings()
    print("Supabase URL:", settings.supabase_url)

    rag = RagEngine.from_settings()

    # Count documents in the vector store
    try:
        resp = rag.client.table("documents").select("id", count="exact").limit(1).execute()
        total = resp.count or 0
        print(f"✅ documents in vector store: {total}")
    except Exception as e:
        print("⚠️ Failed to count documents:", e)

    # Sample query
    query = "liquidity supply and demand trading entry and risk management rules"
    print(f"\n🔎 RAG similarity search for:\n  {query!r}\n")

    try:
        docs = rag.query_rules(query, k=5)
        if not docs:
            print("⚠️ No matching documents returned.")
            return

        for i, d in enumerate(docs, start=1):
            meta = d.metadata or {}
            title = meta.get("title") or "(no title)"
            source = meta.get("source") or ""
            snippet = d.page_content[:200].replace("\n", " ")
            print(f"[{i}] {title}")
            if source:
                print(f"    source: {source}")
            print(f"    snippet: {snippet}...\n")
    except Exception as e:
        print("⚠️ RAG query failed:", e)


if __name__ == "__main__":
    main()

