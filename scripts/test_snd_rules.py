"""
Test script: verify RAG can retrieve Supply & Demand + Liquidity rules.

Run from project root:

    python scripts/test_snd_rules.py

It will:
  - Initialize RagEngine.from_settings()
  - Ask: "How do I identify a valid supply or demand zone with a liquidity sweep?"
  - Retrieve top 3 rules from the RAG knowledge base
  - Print source titles, snippets, and similarity (if available)
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


def _similarity_from_meta(meta: Dict[str, Any]) -> str | None:
    sim = meta.get("similarity")
    try:
        if sim is None:
            return None
        return f"{float(sim):.2f}"
    except Exception:
        return None


def main() -> None:
    load_dotenv(ROOT / ".env")
    _ = get_settings()

    try:
        rag = RagEngine.from_settings()
    except Exception as e:
        print(f"\x1b[31mERROR: Failed to initialize RagEngine: {e}\x1b[0m")
        return

    query = "How do I identify a valid supply or demand zone with a liquidity sweep?"

    print("🧠 SUPPLY & DEMAND KNOWLEDGE CHECK")
    print("--------------------------------------------------")
    print(f"Query: {query!r}")
    print("--------------------------------------------------")

    try:
        docs = rag.query_rules(query, k=3)
    except Exception as e:
        print(f"\x1b[31mERROR: RAG query failed: {e}\x1b[0m")
        return

    if not docs:
        print("\x1b[31mERROR: No S&D + Liquidity rules returned. Check ingestion or filters.\x1b[0m")
        return

    for idx, d in enumerate(docs, start=1):
        meta: Dict[str, Any] = d.metadata or {}
        title = meta.get("title") or "(no title)"
        snippet = (d.page_content or "").strip().replace("\n", " ")
        if len(snippet) > 300:
            snippet = snippet[:300].rstrip() + "..."
        sim_str = _similarity_from_meta(meta)

        print(f"[Match {idx}]")
        print(f"Source Title: {title}")
        if sim_str is not None:
            print(f"Similarity: {sim_str}")
        print(f"Snippet: {snippet}")
        print("--------------------------------------------------")


if __name__ == "__main__":
    main()

