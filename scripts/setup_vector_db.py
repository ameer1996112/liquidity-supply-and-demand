"""
Setup script for Supabase pgvector RAG infrastructure.

This script:
- Verifies Supabase connectivity using the Python client.
- Prints the SQL needed to enable the `vector` extension and create
  the `documents` table + `match_documents` function.

Run locally (with .env configured) to sanity-check connectivity:
    python scripts/setup_vector_db.py

Then paste the printed SQL into the Supabase SQL Editor and run it
against your primary database.
"""

import os
import textwrap
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client, Client


ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")


def get_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_KEY) "
            "must be set in environment variables."
        )
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def main() -> None:
    print("🔧 Supabase pgvector setup")
    client = None
    try:
        client = get_client()
        # Simple health check – does not perform DDL
        client.table("trading_signals").select("id").limit(1).execute()
        print("✅ Supabase connection OK.")
    except Exception as e:
        print(f"⚠️ Supabase connection check failed: {e}")
        print("   Continuing to print SQL – run it manually in Supabase SQL Editor.")

    sql = textwrap.dedent(
        """
        -- Enable pgvector extension (idempotent)
        create extension if not exists vector;

        -- Documents table for RAG
        create table if not exists documents (
            id uuid primary key default gen_random_uuid(),
            content text,
            metadata jsonb,
            embedding vector(1536)  -- OpenAI embedding size (text-embedding-3-small)
        );

        -- Similarity search function using pgvector
        -- 3-arg version (useful for manual SQL / future extensions)
        create or replace function match_documents(
            query_embedding vector(1536),
            match_count int,
            filter jsonb default '{}'::jsonb
        )
        returns table(
            id uuid,
            content text,
            metadata jsonb,
            similarity float
        )
        language plpgsql
        as $$
        begin
            return query
            select
                d.id,
                d.content,
                d.metadata,
                1 - (d.embedding <=> query_embedding) as similarity
            from documents d
            where d.metadata @> filter
            order by d.embedding <=> query_embedding
            limit match_count;
        end;
        $$;

        -- 1-arg wrapper version for PostgREST / LangChain SupabaseVectorStore
        -- This matches an RPC call body like: {"query_embedding": [...]}
        create or replace function match_documents(
            query_embedding vector(1536)
        )
        returns table(
            id uuid,
            content text,
            metadata jsonb,
            similarity float
        )
        language plpgsql
        as $$
        begin
            return query
            select
                d.id,
                d.content,
                d.metadata,
                1 - (d.embedding <=> query_embedding) as similarity
            from documents d
            order by d.embedding <=> query_embedding
            limit 5;
        end;
        $$;
        """
    ).strip()

    print("\n📋 Run the following SQL in the Supabase SQL Editor (primary database):\n")
    print(sql)
    print(
        "\n✅ After this migration, the `documents` table and `match_documents` "
        "function will be ready for LangChain's SupabaseVectorStore."
    )


if __name__ == "__main__":
    main()

