"""
RAG status / connectivity diagnostic.

Run from project root:

    python scripts/test_rag_status.py

It will:
  - Initialize RagEngine.from_settings()
  - Verify it can talk to Supabase
  - Run a targeted query against the 5m S&D rulebase
  - Print the top 3 matches (if any) in a human-friendly format
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv

# Ensure project root (with `config/` and `src/`) is on sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import get_settings  # type: ignore
from src.ai.rag_engine import RagEngine  # type: ignore


def _format_similarity(meta: Dict[str, Any]) -> str:
    """Best-effort similarity formatting from metadata."""
    sim = meta.get("similarity")
    try:
        if sim is None:
            return "n/a"
        return f"{float(sim):.2f}"
    except Exception:
        return "n/a"


def main() -> None:
    load_dotenv(ROOT / ".env")

    settings = get_settings()

    print("🧠 RAG BRAIN DIAGNOSTIC")
    print("--------------------------------------------------")
    print(
        'Query: "What are the rules for a valid order block entry?"'
    )

    # 1) Initialize RagEngine and check Supabase connectivity
    try:
        rag = RagEngine.from_settings()
        # Simple connectivity check – count documents
        resp = rag.client.table("documents").select("id", count="exact").limit(1).execute()
        total_docs = resp.count or 0
        print(f"Status: ✅ Connected to Supabase (documents: {total_docs})")
    except Exception as e:
        print(f"Status: ❌ FAILED to connect to Supabase/RAG: {e}")
        return

    print("--------------------------------------------------")

    query = "What are the rules for a valid order block entry?"
    try:
        docs = rag.query_rules(query, k=3)
    except Exception as e:
        print(f"⚠️ RAG query failed: {e}")
        return

    if not docs:
        print("⚠️ Brain is empty. Check ingestion.")
        return

    for idx, d in enumerate(docs, start=1):
        meta: Dict[str, Any] = d.metadata or {}
        title = meta.get("title") or "(no title)"
        source = meta.get("source") or ""
        similarity = _format_similarity(meta)
        excerpt = (d.page_content or "").strip().replace("\n", " ")
        if len(excerpt) > 260:
            excerpt = excerpt[:260].rstrip() + "..."

        print(f"[Match {idx}] {title} (Similarity: {similarity})")
        if source:
            print(f"Source: {source}")
        print(f"Excerpt: {excerpt}")
        print("--------------------------------------------------")


if __name__ == "__main__":
    main()

