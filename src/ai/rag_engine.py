"""
RAG Engine backed by Supabase pgvector.

Design goals:
- Stateless, cloud-native (Supabase + pgvector).
- No local vector DBs (no Chroma). All embeddings live in Postgres.

This module wires:
- Supabase Python client
- OpenAI embeddings
- LangChain SupabaseVectorStore
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from openai import OpenAI
from supabase import Client, create_client

from langchain_community.vectorstores import SupabaseVectorStore
from langchain_core.embeddings import Embeddings
from langchain_core.documents import Document

from config import get_settings


logger = logging.getLogger(__name__)


# ── Chunking helper ──────────────────────────────────────────────────
import re as _re

_BULLET_RE = _re.compile(
    r"^(?:"                       # start of line
    r"\s*[-•*]\s+"                # bullet: - / • / *
    r"|\s*\d+[.)]\s+"            # numbered: 1. / 2) / 3.
    r"|\s*[A-Z][.)]\s+"          # lettered: A. / B)
    r")",
)


def _split_into_rules(text: str, min_len: int = 30) -> list[str]:
    """Split a bulleted / numbered document into individual rules.

    Consecutive non-bullet lines are merged into the preceding bullet.
    If the text has no bullets at all, it is returned as a single chunk.
    """
    lines = text.strip().splitlines()
    chunks: list[str] = []
    current: list[str] = []

    has_bullets = any(_BULLET_RE.match(line) for line in lines)
    if not has_bullets:
        # No structure to split on – return the whole text
        return [text.strip()] if len(text.strip()) >= min_len else []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if _BULLET_RE.match(line) and current:
            # Start of new bullet → flush previous
            merged = " ".join(current).strip()
            if len(merged) >= min_len:
                chunks.append(merged)
            current = [stripped.lstrip("-•* ").lstrip("0123456789.)").strip()]
        else:
            current.append(stripped.lstrip("-•* ").lstrip("0123456789.)").strip())

    # Flush last chunk
    if current:
        merged = " ".join(current).strip()
        if len(merged) >= min_len:
            chunks.append(merged)

    return chunks


class OpenAIEmbeddingAdapter(Embeddings):
    """Minimal adapter around OpenAI embeddings for LangChain.

    Uses the official `openai` client and exposes the Embeddings interface
    expected by LangChain vector stores.
    """

    def __init__(
        self,
        # Use 1536-dim model to match `vector(1536)` in Supabase.
        # If you change the DB dimension, update this accordingly.
        model: str = "text-embedding-3-small",
        api_key: Optional[str] = None,
    ) -> None:
        self.model = model
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY") or "")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        resp = self.client.embeddings.create(model=self.model, input=texts)
        return [d.embedding for d in resp.data]

    def embed_query(self, text: str) -> List[float]:
        resp = self.client.embeddings.create(model=self.model, input=[text])
        return resp.data[0].embedding


@dataclass
class RagEngine:
    """RAG wrapper over SupabaseVectorStore (pgvector).

    - Ingests rules/knowledge into the `documents` table.
    - Retrieves relevant rules for a given context via similarity search.
    """

    client: Client
    vector_store: SupabaseVectorStore

    @classmethod
    def from_settings(
        cls,
        table_name: str = "documents",
        query_name: str = "match_documents",
        embedding_model: str = "text-embedding-3-small",
    ) -> "RagEngine":
        """Factory that builds RagEngine from config Settings."""
        s = get_settings()
        url = s.supabase_url
        key = (s.supabase_service_role_key or s.supabase_key).strip()
        if not url or not key:
            raise RuntimeError("Supabase URL/key missing in settings.")

        client = create_client(url, key)
        embeddings = OpenAIEmbeddingAdapter(model=embedding_model)

        # Vector store handle – assumes `documents` + `match_documents` already exist
        vector_store = SupabaseVectorStore(
            client=client,
            embedding=embeddings,
            table_name=table_name,
            query_name=query_name,
        )

        logger.info("RagEngine initialized with Supabase table '%s'.", table_name)
        return cls(client=client, vector_store=vector_store)

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def ingest_rule(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        *,
        chunk: bool = True,
        min_chunk_len: int = 30,
    ) -> None:
        """Ingest a rule / document into the vector store.

        When *chunk* is True (default), the text is split on bullet
        points / numbered items so each rule gets its own embedding.
        This dramatically improves retrieval precision versus embedding
        an entire multi-paragraph document as a single vector.

        Short fragments (< *min_chunk_len* chars) are skipped.
        """
        if not text or not text.strip():
            return

        md = metadata or {}

        # ── Chunk into individual rules ──────────────────────────
        if chunk:
            chunks = _split_into_rules(text, min_chunk_len)
        else:
            chunks = [text.strip()]

        if not chunks:
            logger.warning("No chunks to ingest (text too short or empty after splitting).")
            return

        self.vector_store.add_texts(chunks, metadatas=[md] * len(chunks))
        logger.info(
            "Ingested %d chunk(s) into Supabase vector store (total chars=%s).",
            len(chunks),
            sum(len(c) for c in chunks),
        )

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def query_rules(
        self,
        context: str,
        k: int = 4,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[Document]:
        """Retrieve top-k rules relevant to the given context string."""
        if not context or not context.strip():
            return []

        search_kwargs = {}
        if filter:
            # SupabaseVectorStore passes these to the match function as metadata filter
            search_kwargs["filter"] = filter

        docs = self.vector_store.similarity_search(
            context,
            k=k,
            **search_kwargs,
        )
        logger.info("RagEngine retrieved %d rules for context.", len(docs))
        return docs


__all__ = ["RagEngine"]

