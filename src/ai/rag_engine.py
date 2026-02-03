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

    def ingest_rule(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Ingest a single rule / document into the vector store.

        Uses `SupabaseVectorStore.from_texts` on first call, then `add_texts`
        for subsequent ingests.
        """
        if not text or not text.strip():
            return

        md = metadata or {}

        if self.vector_store is None:
            # First-time bootstrap – from_texts will create the table rows
            self.vector_store = SupabaseVectorStore.from_texts(
                texts=[text],
                embedding=self.vector_store._embedding,  # type: ignore[attr-defined]
                client=self.client,
                table_name=self.vector_store.table_name,  # type: ignore[attr-defined]
                query_name=self.vector_store.query_name,  # type: ignore[attr-defined]
                metadatas=[md],
            )
        else:
            self.vector_store.add_texts([text], metadatas=[md])

        logger.info("Ingested rule into Supabase vector store (len(text)=%s).", len(text))

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

