#!/usr/bin/env python3
"""
Ingest the Mangoe Futures strategy document into Supabase RAG (documents table).

Run from project root:
  python scripts/ingest_mangoe_futures_rag.py

Requires .env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, OPENAI_API_KEY.
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

DOC_PATH = project_root / "docs" / "strategies" / "mangoe_futures.md"
RAG_METADATA = {
    "strategy": "mangoe_futures",
    "timeframe": "5m",
    "source": "mangoe_futures.md",
}


def main() -> None:
    if not DOC_PATH.exists():
        print(f"❌ Document not found: {DOC_PATH}")
        sys.exit(1)

    content = DOC_PATH.read_text(encoding="utf-8").strip()
    if not content:
        print("❌ Document is empty.")
        sys.exit(1)

    print("📄 Mangoe Futures RAG ingest")
    print(f"   File: {DOC_PATH}")
    print(f"   Metadata: {RAG_METADATA}")
    print()

    try:
        try:
            from dotenv import load_dotenv
            load_dotenv(project_root / ".env")
        except ImportError:
            pass  # .env may already be loaded or set in environment

        from src.ai.rag_engine import RagEngine

        engine = RagEngine.from_settings()
        engine.ingest_rule(content, metadata=RAG_METADATA, chunk=True, min_chunk_len=30)
        print("✅ Ingested into Supabase (documents table). RAG will use this for Mangoe Futures context.")
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("   Install project deps:  pip install -r requirements.txt")
        print("   Or minimal:            pip install openai supabase langchain langchain-community python-dotenv yfinance")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Ingest failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
