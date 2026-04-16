"""
Sprint 3.3: Debate guardrail (Bull vs Bear) in SHADOW MODE.

Pipeline:
  1. Bull argues for taking the trade
  2. Bear argues against
  3. Risk agents assess with prop constraints
  4. Chair summarizes + final vote

Output: structured JSON with recommendation, confidence, reason_codes, memo, votes.
AI_MODE=shadow: never blocks execution — log-only.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from config import get_settings

logger = logging.getLogger(__name__)


# ── Pydantic schemas for structured output ───────────────────────────────────


class AgentVote(BaseModel):
    """Single agent vote: allow or block."""

    vote: str = Field(..., description="allow or block")


class ChairOutput(BaseModel):
    """Final chair output — must match spec exactly."""

    recommendation: str = Field(..., description="allow or block")
    confidence: int = Field(..., ge=0, le=100, description="0-100")
    reason_codes: List[str] = Field(default_factory=list, description="Array of reason codes")
    memo: str = Field(default="", description="Short text summary")
    votes: Dict[str, str] = Field(
        default_factory=dict,
        description="Votes per agent: bull, bear, risk, chair",
    )


# ── Trade context builder ───────────────────────────────────────────────────


def _build_trade_context(
    payload: Dict[str, Any],
    enriched_context: Optional[Dict[str, Any]] = None,
) -> str:
    """Build a concise trade context string for prompts."""
    symbol = payload.get("symbol", "UNKNOWN")
    side = (payload.get("side") or "buy").upper()
    entry = payload.get("entry")
    sl = payload.get("sl")
    tp = payload.get("tp")
    size = payload.get("size")
    zone_id = payload.get("zone_id")
    zone_grade = payload.get("zone_grade")
    entry_model = payload.get("entry_model")
    score = payload.get("score")

    lines = [
        f"Symbol: {symbol} | Side: {side}",
        f"Entry: {entry} | SL: {sl} | TP: {tp} | Size: {size}",
    ]
    if zone_id is not None:
        lines.append(f"Zone: {zone_id} | Grade: {zone_grade or 'N/A'} | Entry: {entry_model or 'N/A'}")
    if score is not None:
        lines.append(f"Zone Score: {score}")
    if enriched_context:
        chart_status = enriched_context.get("chart_context", {}).get("status", "unknown")
        pine_name = enriched_context.get("pine_context", {}).get("script_name", "N/A")
        lines.append(f"Chart Context Status: {chart_status}")
        lines.append(f"Pine Script: {pine_name}")
    return "\n".join(lines)


# ── Debate agents (LLM calls) ──────────────────────────────────────────────


def _call_agent(
    client: Any,
    role: str,
    prompt: str,
    system: str,
    model: str = "claude-3-5-sonnet-20241022",
) -> Optional[str]:
    """Call LLM and return raw text. Returns None on error."""
    if client is None:
        return None
    try:
        raw = client._raw_complete(
            prompt,
            system_prompt=system,
            temperature=0.2,
            max_tokens=512,
            timeout=15.0,
        )
        return (raw or "").strip()
    except Exception as e:
        logger.warning("[DEBATE] %s agent call failed: %s", role, e)
        return None


def _run_bull(client: Any, trade_ctx: str, model: str) -> tuple[str, str]:
    """Bull argues FOR taking the trade. Returns (argument, vote)."""
    prompt = (
        f"Trade context:\n{trade_ctx}\n\n"
        "You are the BULL. Argue briefly (2-3 sentences) why this trade SHOULD be taken. "
        "Focus on technical setup, zone quality, and favorable risk/reward. "
        "Then respond with a JSON object: {\"argument\": \"...\", \"vote\": \"allow\" or \"block\"}."
    )
    raw = _call_agent(
        client,
        "bull",
        prompt,
        "You are a trading analyst. Respond with valid JSON only.",
        model,
    )
    if not raw:
        return ("[Bull: no response]", "allow")
    try:
        data = json.loads(raw)
        arg = data.get("argument", raw[:200])
        vote = "allow" if str(data.get("vote", "allow")).lower() == "allow" else "block"
        return (str(arg)[:500], vote)
    except json.JSONDecodeError:
        return (raw[:300], "allow")


def _run_bear(client: Any, trade_ctx: str, model: str) -> tuple[str, str]:
    """Bear argues AGAINST taking the trade. Returns (argument, vote)."""
    prompt = (
        f"Trade context:\n{trade_ctx}\n\n"
        "You are the BEAR. Argue briefly (2-3 sentences) why this trade should NOT be taken. "
        "Focus on risks, weak setup, or unfavorable conditions. "
        "Then respond with a JSON object: {\"argument\": \"...\", \"vote\": \"allow\" or \"block\"}."
    )
    raw = _call_agent(
        client,
        "bear",
        prompt,
        "You are a trading analyst. Respond with valid JSON only.",
        model,
    )
    if not raw:
        return ("[Bear: no response]", "block")
    try:
        data = json.loads(raw)
        arg = data.get("argument", raw[:200])
        vote = "allow" if str(data.get("vote", "allow")).lower() == "allow" else "block"
        return (str(arg)[:500], vote)
    except json.JSONDecodeError:
        return (raw[:300], "block")


def _run_risk(client: Any, payload: Dict[str, Any], model: str, supabase: Any) -> tuple[str, str]:
    """Risk agent assesses prop constraints (drawdown, exposure). Returns (assessment, vote)."""
    from src.agents.risk_agent import RiskAgent

    symbol = payload.get("symbol", "UNKNOWN")
    risk_agent = RiskAgent(supabase)
    risk_result = risk_agent.evaluate(symbol)
    vote = "allow" if risk_result.get("vote") == "YES" else "block"
    reason = risk_result.get("reason", "Risk check completed")
    return (reason[:500], vote)


def _run_chair(
    client: Any,
    trade_ctx: str,
    bull_arg: str,
    bear_arg: str,
    risk_arg: str,
    bull_vote: str,
    bear_vote: str,
    risk_vote: str,
    model: str,
) -> ChairOutput:
    """Chair summarizes and produces final structured output."""
    prompt = (
        f"Trade context:\n{trade_ctx}\n\n"
        f"Bull (for trade): {bull_arg}\nVote: {bull_vote}\n\n"
        f"Bear (against trade): {bear_arg}\nVote: {bear_vote}\n\n"
        f"Risk (prop constraints): {risk_arg}\nVote: {risk_vote}\n\n"
        "You are the CHAIR. Summarize the debate and cast the final vote. "
        "Respond with a JSON object:\n"
        '{"recommendation": "allow" or "block", "confidence": 0-100, '
        '"reason_codes": ["code1", "code2"], "memo": "short summary", '
        '"votes": {"bull": "allow", "bear": "block", "risk": "allow", "chair": "allow"}}'
    )
    raw = _call_agent(
        client,
        "chair",
        prompt,
        "You are a trading committee chair. Respond with valid JSON only.",
        model,
    )
    if not raw:
        return ChairOutput(
            recommendation="allow",
            confidence=50,
            reason_codes=["debate_error"],
            memo="Chair: no response — fail-open",
            votes={
                "bull": bull_vote,
                "bear": bear_vote,
                "risk": risk_vote,
                "chair": "allow",
            },
        )
    try:
        data = json.loads(raw)
        rec = str(data.get("recommendation", "allow")).lower()
        if rec not in ("allow", "block"):
            rec = "allow"
        conf = int(data.get("confidence", 50))
        conf = max(0, min(100, conf))
        codes = data.get("reason_codes", [])
        if not isinstance(codes, list):
            codes = []
        memo = str(data.get("memo", ""))[:500]
        votes = data.get("votes", {})
        if not isinstance(votes, dict):
            votes = {}
        votes.setdefault("bull", bull_vote)
        votes.setdefault("bear", bear_vote)
        votes.setdefault("risk", risk_vote)
        votes.setdefault("chair", rec)
        return ChairOutput(
            recommendation=rec,
            confidence=conf,
            reason_codes=[str(c) for c in codes[:10]],
            memo=memo,
            votes=votes,
        )
    except (json.JSONDecodeError, Exception) as e:
        logger.warning("[DEBATE] Chair parse failed: %s", e)
        return ChairOutput(
            recommendation="allow",
            confidence=50,
            reason_codes=["chair_parse_error"],
            memo=f"Chair parse error: {e}",
            votes={"bull": bull_vote, "bear": bear_vote, "risk": risk_vote, "chair": "allow"},
        )


# ── Main entry point ────────────────────────────────────────────────────────


def run_debate(
    payload: Dict[str, Any],
    *,
    client: Optional[Any] = None,
    supabase: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Run the full Bull/Bear/Risk/Chair debate pipeline.

    Returns dict with:
      - recommendation: "allow" | "block"
      - confidence: 0-100
      - reason_codes: list
      - memo: str
      - votes: dict
      - transcript: list of {role, content}
    """
    settings = get_settings()
    model = getattr(settings, "ai_deep_model", None) or getattr(settings, "ai_model", "claude-3-5-sonnet-20241022")

    if client is None:
        try:
            from src.ai.llm_client import get_ai_client
            client = get_ai_client()
        except Exception:
            client = None

    trade_ctx = _build_trade_context(payload)
    # Sprint 4.3: Add similar past situations when MEMORY_ENABLED
    if supabase and getattr(settings, "memory_enabled", False):
        try:
            from src.services.memory_retrieval import (
                retrieve_similar_reflections,
                format_reflections_for_prompt,
            )
            k = getattr(settings, "memory_top_k", 3)
            reflections = retrieve_similar_reflections(supabase, payload, k=k)
            if reflections:
                trade_ctx += "\n\n" + format_reflections_for_prompt(reflections)
        except Exception as e:
            logger.debug("Memory retrieval skipped: %s", e)

    transcript: List[Dict[str, str]] = []

    # 1. Bull
    bull_arg, bull_vote = _run_bull(client, trade_ctx, model)
    transcript.append({"role": "bull", "content": bull_arg})

    # 2. Bear
    bear_arg, bear_vote = _run_bear(client, trade_ctx, model)
    transcript.append({"role": "bear", "content": bear_arg})

    # 3. Risk
    risk_arg, risk_vote = _run_risk(client, payload, model, supabase)
    transcript.append({"role": "risk", "content": risk_arg})

    # 4. Chair
    chair = _run_chair(
        client,
        trade_ctx,
        bull_arg,
        bear_arg,
        risk_arg,
        bull_vote,
        bear_vote,
        risk_vote,
        model,
    )
    transcript.append({"role": "chair", "content": chair.memo})

    return {
        "recommendation": chair.recommendation,
        "confidence": chair.confidence,
        "reason_codes": chair.reason_codes,
        "memo": chair.memo,
        "votes": chair.votes,
        "transcript": transcript,
    }
