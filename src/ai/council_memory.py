"""
Per-agent BM25 memory for the Trading Council.

Adapted from TradingAgents FinancialSituationMemory pattern.

Each agent role maintains a rolling store of (situation, recommendation) pairs.
Retrieval uses BM25 lexical similarity (rank-bm25 package).
Optional Supabase persistence via 'trading_agent_memories' table.

Table schema (create if not exists):
    CREATE TABLE IF NOT EXISTS trading_agent_memories (
        id          bigserial PRIMARY KEY,
        agent_role  text NOT NULL,
        situation_text      text NOT NULL,
        recommendation_text text NOT NULL,
        symbol      text,
        outcome_pnl float,
        created_at  timestamptz DEFAULT now()
    );
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[=\-/,._]+")


def _tokenize(text: str) -> List[str]:
    """Split on whitespace and common delimiters so 'score=75' → ['score', '75']."""
    return [t for t in _TOKEN_RE.sub(" ", text.lower()).split() if t]


_ROLES = [
    "market_analyst",
    "setup_analyst",
    "bull_researcher",
    "bear_researcher",
    "research_manager",
    "risk_judge",
]


class AgentMemory:
    """BM25 in-process memory for a single agent role."""

    def __init__(self, role: str, max_size: int = 100):
        self.role = role
        self._situations: List[str] = []
        self._recommendations: List[str] = []
        self._max = max_size
        self._bm25 = None  # lazy-built index

    def add(self, situation: str, recommendation: str) -> None:
        """Add a situation–recommendation pair. Evicts oldest if over max_size."""
        self._situations.append(situation)
        self._recommendations.append(recommendation)
        if len(self._situations) > self._max:
            self._situations = self._situations[-self._max :]
            self._recommendations = self._recommendations[-self._max :]
        self._bm25 = None  # invalidate cached index

    def retrieve(self, query: str, top_k: int = 3) -> List[Tuple[str, str]]:
        """Return top-k (situation, recommendation) pairs by BM25 similarity."""
        if not self._situations:
            return []
        try:
            from rank_bm25 import BM25Okapi  # type: ignore

            if self._bm25 is None:
                corpus = [_tokenize(s) for s in self._situations]
                self._bm25 = BM25Okapi(corpus)
            scores = self._bm25.get_scores(_tokenize(query))
            top_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[
                :top_k
            ]
            return [
                (self._situations[i], self._recommendations[i])
                for i in top_idx
                if scores[i] > 0
            ]
        except ImportError:
            logger.debug("rank-bm25 not installed; memory retrieval skipped")
            return []
        except Exception as exc:
            logger.debug("Memory retrieval error: %s", exc)
            return []

    def format_for_prompt(self, query: str, top_k: int = 3) -> str:
        """Return a formatted memory block to inject into an agent prompt."""
        memories = self.retrieve(query, top_k)
        if not memories:
            return ""
        lines = ["\n### Lessons from Similar Past Setups:"]
        for i, (sit, rec) in enumerate(memories, 1):
            lines.append(f"{i}. Setup: {sit[:200]}")
            lines.append(f"   Lesson: {rec[:200]}")
        return "\n".join(lines)

    def __len__(self) -> int:
        return len(self._situations)


class CouncilMemory:
    """Multi-role memory store for the Trading Council."""

    def __init__(self) -> None:
        self._store: dict[str, AgentMemory] = {r: AgentMemory(r) for r in _ROLES}

    def get(self, role: str) -> AgentMemory:
        if role not in self._store:
            self._store[role] = AgentMemory(role)
        return self._store[role]

    def add_reflection(
        self,
        role: str,
        situation: str,
        recommendation: str,
        symbol: Optional[str] = None,
        outcome_pnl: Optional[float] = None,
        supabase=None,
    ) -> None:
        """Add a reflection to in-process memory and optionally persist to Supabase."""
        self.get(role).add(situation, recommendation)
        if supabase:
            try:
                row: dict = {
                    "agent_role": role,
                    "situation_text": situation[:2000],
                    "recommendation_text": recommendation[:2000],
                }
                if symbol:
                    row["symbol"] = symbol
                if outcome_pnl is not None:
                    row["outcome_pnl"] = outcome_pnl
                supabase.table("trading_agent_memories").insert(row).execute()
            except Exception as exc:
                logger.debug("Memory persist to Supabase failed: %s", exc)

    def load_from_supabase(self, supabase) -> int:
        """Load persisted memories from Supabase on startup. Returns count loaded."""
        count = 0
        try:
            for role in _ROLES:
                result = (
                    supabase.table("trading_agent_memories")
                    .select("situation_text,recommendation_text")
                    .eq("agent_role", role)
                    .order("created_at", desc=True)
                    .limit(100)
                    .execute()
                )
                for row in result.data or []:
                    self.get(role).add(
                        row["situation_text"], row["recommendation_text"]
                    )
                    count += 1
        except Exception as exc:
            logger.debug("Memory load from Supabase failed: %s", exc)
        return count

    def stats(self) -> dict:
        return {role: len(mem) for role, mem in self._store.items()}


# ── Module-level singleton (survives across signals in same process) ─────────

_GLOBAL: Optional[CouncilMemory] = None


def get_council_memory() -> CouncilMemory:
    """Return the process-level CouncilMemory singleton."""
    global _GLOBAL
    if _GLOBAL is None:
        _GLOBAL = CouncilMemory()
    return _GLOBAL
