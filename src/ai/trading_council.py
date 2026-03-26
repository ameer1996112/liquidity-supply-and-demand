"""
Trading Council — Multi-Agent Decision Pipeline

Directly inspired by TradingAgents (TauricResearch) architecture, adapted for
forex / indices / metals / crypto instruments.

Pipeline (9 stages):
  Stage 1: Market Analyst      — live price action + technical report   (quick LLM)
  Stage 2: Setup Analyst       — S&D zone quality + entry structure      (quick LLM)
  Stage 3: Bull Researcher     — bullish thesis using reports + memory   (quick LLM)
  Stage 4: Bear Researcher     — bearish thesis using reports + memory   (quick LLM)
  Stage 5: Research Manager    — debate synthesis → investment plan       (deep LLM)
  Stage 6: Aggressive Debater  — reward-focused risk perspective          (quick LLM)
  Stage 7: Conservative Debater— risk-first perspective                   (quick LLM)
  Stage 8: Neutral Debater     — balanced risk perspective                (quick LLM)
  Stage 9: Risk Judge          — APPROVE / REJECT final decision          (deep LLM)

Outputs dict compatible with run_debate() (backward-compat) plus:
  council_decision    : "APPROVE" | "REJECT"
  council_confidence  : 0-100
  council_report      : per-stage text reports
  council_transcript  : list of {role, content}

Config env vars (all optional, have defaults):
  AI_COUNCIL_ENABLED   (bool, default True)  — master toggle
  AI_COUNCIL_SHADOW    (bool, default True)  — shadow mode (log only, never blocks)
  AI_QUICK_MODEL       — fast model (default: ai_quick_model from settings)
  AI_DEEP_MODEL        — deep model (default: ai_deep_model from settings)
  AI_COUNCIL_CACHE_TTL (int, default 900)   — Redis cache TTL in seconds
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_CACHE_PREFIX = "council:v1:"
_CACHE_TTL = int(os.environ.get("AI_COUNCIL_CACHE_TTL", "900"))


# ─────────────────────────────────────────────────────────────────────────────
# LLM client helpers
# ─────────────────────────────────────────────────────────────────────────────


def _build_client(model_override: Optional[str] = None):
    """Create a fresh (uncached) LLM client with the specified model."""
    try:
        from config import get_settings
        from src.ai.llm_client import AnthropicClient, OpenAIClient

        s = get_settings()
        provider = (s.ai_provider or "anthropic").lower()
        api_key = s.ai_api_key.get_secret_value() if s.ai_api_key else ""
        base_url = (s.ai_base_url or "").strip() or None
        model = model_override or s.ai_model or "claude-3-5-sonnet-20241022"

        if provider == "anthropic":
            return AnthropicClient(api_key=api_key, model=model)
        else:
            return OpenAIClient(api_key=api_key, base_url=base_url, model=model)
    except Exception as exc:
        logger.warning("Failed to build LLM client: %s", exc)
        return None


def _get_models() -> Tuple[str, str]:
    """Return (quick_model, deep_model) from settings."""
    try:
        from config import get_settings

        s = get_settings()
        quick = (
            os.environ.get("AI_QUICK_MODEL")
            or getattr(s, "ai_quick_model", "")
            or s.ai_model
            or "claude-3-5-haiku-20241022"
        )
        deep = (
            os.environ.get("AI_DEEP_MODEL")
            or getattr(s, "ai_deep_model", "")
            or s.ai_model
            or "claude-3-5-sonnet-20241022"
        )
        return quick, deep
    except Exception:
        return "claude-3-5-haiku-20241022", "claude-3-5-sonnet-20241022"


def _call(
    client,
    prompt: str,
    system: str,
    max_tokens: int = 600,
    temperature: float = 0.15,
    timeout: float = 25.0,
) -> str:
    """Single LLM call. Returns raw text or '' on any error."""
    if client is None:
        return ""
    try:
        return (
            client._raw_complete(
                prompt,
                system_prompt=system,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            )
            or ""
        )
    except Exception as exc:
        logger.warning("Council LLM call failed: %s", exc)
        return ""


def _parse_vote(raw: str, default_vote: str) -> Tuple[str, str]:
    """
    Extract (argument_text, vote) from an agent response.
    Handles JSON at the end of prose, or plain text fallback.
    """
    if not raw:
        return "[No response]", default_vote
    # Try to find a trailing JSON block
    start = raw.rfind("{")
    end = raw.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            data = json.loads(raw[start:end])
            arg = str(data.get("argument", raw[:start].strip() or raw[:350]))[:500]
            raw_vote = str(data.get("vote", default_vote)).lower().strip()
            vote = "allow" if raw_vote == "allow" else "block"
            return arg, vote
        except (json.JSONDecodeError, Exception):
            pass
    return raw[:450], default_vote


# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: Market Analyst
# ─────────────────────────────────────────────────────────────────────────────


def _stage_market_analyst(payload: Dict[str, Any], client) -> str:
    """
    Fetch live market data for the symbol and produce a technical analysis report.
    Uses get_market_narrative() which already maps forex/indices/crypto to Yahoo Finance.
    """
    symbol = payload.get("symbol", "UNKNOWN")
    session_map = {0: "Asian", 1: "London", 2: "New York", 3: "Off-hours"}
    session = payload.get("session")
    trend = payload.get("trend")
    htf_trend = payload.get("htf_trend")
    rsi = payload.get("rsi")
    adx = payload.get("adx")
    rvol = payload.get("rvol")
    side = (payload.get("side") or "buy").upper()

    try:
        from src.adapters.market_data import get_market_narrative

        narrative = get_market_narrative(symbol)
    except Exception as exc:
        logger.debug("Market narrative failed for %s: %s", symbol, exc)
        narrative = f"{symbol}: market data unavailable."

    prompt = (
        f"You are a Market Analyst covering {symbol} for a {side} trade decision.\n\n"
        f"LIVE MARKET DATA:\n{narrative}\n\n"
        f"SIGNAL CONTEXT:\n"
        f"- Session: {session_map.get(session, 'Unknown')}\n"
        f"- Pine short-term trend: {'Bullish' if trend == 1 else 'Bearish' if trend == 0 else 'N/A'}\n"
        f"- Higher-timeframe trend: {'Bullish' if htf_trend == 1 else 'Bearish' if htf_trend == 0 else 'N/A'}\n"
        f"- RSI: {rsi if rsi is not None else 'N/A'}\n"
        f"- ADX (trend strength): {adx if adx is not None else 'N/A'}\n"
        f"- Relative Volume: {rvol if rvol is not None else 'N/A'}\n\n"
        f"Write a MARKET ANALYSIS REPORT (3-4 sentences) covering:\n"
        f"1. Current trend and momentum state\n"
        f"2. Session suitability for this instrument\n"
        f"3. Key technical observations\n"
        f"4. Overall market bias for a {side} trade"
    )
    system = (
        "You are a quantitative market analyst for forex, indices, metals, and crypto. "
        "Write a concise, data-driven market report. No JSON needed — plain text."
    )
    result = _call(client, prompt, system, max_tokens=350)
    return result or f"Market analysis unavailable for {symbol}. Treat as neutral."


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: Setup Analyst
# ─────────────────────────────────────────────────────────────────────────────


def _stage_setup_analyst(payload: Dict[str, Any], client) -> str:
    """
    Analyse the Supply & Demand zone quality and entry structure.
    Replaces TradingAgents' Fundamentals Analyst — adapted for S&D forex strategy.
    """
    symbol = payload.get("symbol", "UNKNOWN")
    side = (payload.get("side") or "buy").upper()
    score = payload.get("score")
    grade = payload.get("zone_grade") or payload.get("grade", "N/A")
    entry_model = payload.get("entry_model", "N/A")
    freshness = payload.get("freshness")
    liq_swept = payload.get("liq_swept", False)
    caused_sweep = payload.get("caused_sweep", False)
    dep_str = payload.get("departure_strength")
    ret_str = payload.get("return_strength")
    atr_ratio = payload.get("atr_ratio")
    touch_count = payload.get("touch_count", 0)
    is_accuracy = payload.get("is_accuracy", False)
    entry = payload.get("entry")
    sl = payload.get("sl")
    tp = payload.get("tp")

    rr_str = "N/A"
    try:
        if entry and sl and tp:
            rr = abs(float(tp) - float(entry)) / abs(float(entry) - float(sl))
            rr_str = f"{rr:.2f}x"
    except Exception:
        pass

    freshness_label = (
        "First touch (freshest)" if freshness == 1 else "Retrace (used)" if freshness == 0 else "N/A"
    )

    prompt = (
        f"You are a Setup Quality Analyst evaluating an S&D zone for {symbol} {side}.\n\n"
        f"ZONE METRICS:\n"
        f"- Quality Score: {score}/100  (>60 acceptable, >75 strong, >85 excellent)\n"
        f"- Grade: {grade}  (A+=best … C=weakest)\n"
        f"- Entry Model: {entry_model}  (FLIP=reversal, DIR_CLOSE=directional, BREAK_CANDLE=BOC)\n"
        f"- Freshness: {freshness_label}\n"
        f"- Is Accuracy Zone: {is_accuracy}\n"
        f"- Touch Count: {touch_count}  (first touch = most potent)\n\n"
        f"LIQUIDITY STRUCTURE (Inducement Rule):\n"
        f"- Liquidity Swept: {liq_swept}  (MUST be True for valid S&D setup)\n"
        f"- Zone Caused Sweep: {caused_sweep}\n\n"
        f"PRICE ACTION QUALITY:\n"
        f"- Departure Strength: {dep_str}/100  (<40=compressed/bad, >60=aggressive/good)\n"
        f"- Return Strength:    {ret_str}/100  (<30=slow grind, >50=V-shape)\n"
        f"- ATR Ratio: {atr_ratio}\n\n"
        f"TRADE PARAMETERS:\n"
        f"- Entry: {entry} | SL: {sl} | TP: {tp} | R:R: {rr_str}\n\n"
        f"Write a SETUP QUALITY REPORT (3-4 sentences) covering:\n"
        f"1. Zone validity (inducement sweep, freshness, quality score)\n"
        f"2. Arrival quality (departure + return strength)\n"
        f"3. Entry structure (model + R:R)\n"
        f"4. Overall rating: STRONG / MODERATE / WEAK"
    )
    system = (
        "You are a Supply & Demand zone specialist. "
        "Write a concise, rules-based setup quality assessment. No JSON."
    )
    result = _call(client, prompt, system, max_tokens=350)
    return result or "Setup analysis unavailable."


# ─────────────────────────────────────────────────────────────────────────────
# Stage 3: Bull Researcher
# ─────────────────────────────────────────────────────────────────────────────


def _stage_bull_researcher(
    payload: Dict[str, Any],
    market_report: str,
    setup_report: str,
    client,
    memory,
) -> Tuple[str, str]:
    """Argue FOR the trade. Uses both analyst reports + BM25 bull memory."""
    symbol = payload.get("symbol", "UNKNOWN")
    side = (payload.get("side") or "buy").upper()

    query = (
        f"{symbol} {side} score={payload.get('score')} "
        f"model={payload.get('entry_model')} liq={payload.get('liq_swept')}"
    )
    mem_block = memory.get("bull_researcher").format_for_prompt(query)

    prompt = (
        f"You are the BULL RESEARCHER. Argue the strongest possible case FOR taking this trade.\n\n"
        f"MARKET ANALYSIS:\n{market_report}\n\n"
        f"SETUP ANALYSIS:\n{setup_report}\n\n"
        f"INSTRUMENT: {symbol} | DIRECTION: {side}"
        f"{mem_block}\n\n"
        f"Provide a bullish thesis (3-4 sentences) focusing on:\n"
        f"- Technical alignment with market structure\n"
        f"- Zone strength and liquidity setup\n"
        f"- Favorable risk/reward opportunity\n"
        f"- Any supporting conditions\n\n"
        f'End with JSON vote: {{"argument": "your thesis", "vote": "allow" or "block"}}'
    )
    system = (
        "You are a bull-side trading researcher. "
        "Write a persuasive bullish thesis then append a JSON vote. "
        "Vote 'allow' if you support taking the trade, 'block' if not."
    )
    raw = _call(client, prompt, system, max_tokens=500)
    return _parse_vote(raw, "allow")


# ─────────────────────────────────────────────────────────────────────────────
# Stage 4: Bear Researcher
# ─────────────────────────────────────────────────────────────────────────────


def _stage_bear_researcher(
    payload: Dict[str, Any],
    market_report: str,
    setup_report: str,
    client,
    memory,
) -> Tuple[str, str]:
    """Argue AGAINST the trade. Uses both analyst reports + BM25 bear memory."""
    symbol = payload.get("symbol", "UNKNOWN")
    side = (payload.get("side") or "buy").upper()

    query = (
        f"{symbol} {side} score={payload.get('score')} "
        f"dep={payload.get('departure_strength')} liq={payload.get('liq_swept')}"
    )
    mem_block = memory.get("bear_researcher").format_for_prompt(query)

    prompt = (
        f"You are the BEAR RESEARCHER. Argue the strongest possible case AGAINST this trade.\n\n"
        f"MARKET ANALYSIS:\n{market_report}\n\n"
        f"SETUP ANALYSIS:\n{setup_report}\n\n"
        f"INSTRUMENT: {symbol} | DIRECTION: {side}"
        f"{mem_block}\n\n"
        f"Provide a bearish thesis (3-4 sentences) focusing on:\n"
        f"- Technical risks and market headwinds\n"
        f"- Zone weaknesses or invalidation risks\n"
        f"- Unfavorable conditions or timing\n"
        f"- Potential downside scenarios\n\n"
        f'End with JSON vote: {{"argument": "your thesis", "vote": "allow" or "block"}}'
    )
    system = (
        "You are a bear-side trading researcher. "
        "Write a rigorous bearish critique then append a JSON vote. "
        "Vote 'block' if you think the trade should not be taken, 'allow' if risks are manageable."
    )
    raw = _call(client, prompt, system, max_tokens=500)
    return _parse_vote(raw, "block")


# ─────────────────────────────────────────────────────────────────────────────
# Stage 5: Research Manager (deep LLM)
# ─────────────────────────────────────────────────────────────────────────────


def _stage_research_manager(
    payload: Dict[str, Any],
    market_report: str,
    setup_report: str,
    bull_arg: str,
    bear_arg: str,
    client,
    memory,
) -> str:
    """
    Deep-LLM synthesis of the bull/bear debate.
    Produces an investment plan with a directional GO/NO_GO recommendation.
    """
    symbol = payload.get("symbol", "UNKNOWN")
    side = (payload.get("side") or "buy").upper()

    query = f"{symbol} {side} {market_report[:200]}"
    mem_block = memory.get("research_manager").format_for_prompt(query)

    prompt = (
        f"You are the RESEARCH MANAGER with final authority over the investment decision.\n\n"
        f"MARKET ANALYSIS:\n{market_report}\n\n"
        f"SETUP ANALYSIS:\n{setup_report}\n\n"
        f"BULL THESIS:\n{bull_arg}\n\n"
        f"BEAR THESIS:\n{bear_arg}\n\n"
        f"TRADE: {symbol} {side}"
        f"{mem_block}\n\n"
        f"Produce an INVESTMENT PLAN (4-5 sentences) that:\n"
        f"1. Weighs the bull vs bear arguments objectively\n"
        f"2. States your directional recommendation: GO or NO_GO\n"
        f"3. Identifies the single most important risk factor\n"
        f"4. Sets a conviction level: HIGH / MEDIUM / LOW\n"
        f"5. Provides the core reasoning in one clear sentence"
    )
    system = (
        "You are a seasoned trading research director. "
        "Synthesize the bull/bear debate into a decisive, concise investment plan. No JSON needed."
    )
    result = _call(client, prompt, system, max_tokens=450, timeout=30.0)
    return result or f"Research manager unavailable. Bull: {bull_arg[:100]}. Bear: {bear_arg[:100]}."


# ─────────────────────────────────────────────────────────────────────────────
# Stages 6-8: Risk Debaters
# ─────────────────────────────────────────────────────────────────────────────


def _stage_aggressive_debater(
    payload: Dict[str, Any],
    investment_plan: str,
    client,
) -> Tuple[str, str]:
    """Champions risk-taking and reward potential."""
    symbol = payload.get("symbol", "UNKNOWN")
    side = (payload.get("side") or "buy").upper()

    prompt = (
        f"You are the AGGRESSIVE RISK DEBATER. Champion the reward potential of this trade.\n\n"
        f"INVESTMENT PLAN:\n{investment_plan}\n\n"
        f"TRADE: {symbol} {side}\n\n"
        f"Argue (2-3 sentences) from an aggressive risk-taking perspective:\n"
        f"- Why the potential reward justifies the risk\n"
        f"- Why being too conservative means missing this opportunity\n"
        f"- The asymmetric upside of acting on this signal\n\n"
        f'End with JSON: {{"argument": "your stance", "vote": "allow" or "block"}}'
    )
    system = "You are an aggressive risk advocate. Respond with argument + JSON vote."
    raw = _call(client, prompt, system, max_tokens=350)
    return _parse_vote(raw, "allow")


def _stage_conservative_debater(
    payload: Dict[str, Any],
    investment_plan: str,
    client,
) -> Tuple[str, str]:
    """Emphasises risk management and capital preservation."""
    symbol = payload.get("symbol", "UNKNOWN")
    side = (payload.get("side") or "buy").upper()
    drawdown_pct = None
    try:
        from config import get_settings

        s = get_settings()
        drawdown_pct = getattr(s, "trinity_max_daily_loss_pct", None)
    except Exception:
        pass

    prop_line = ""
    if drawdown_pct:
        prop_line = f"- Prop firm daily loss limit: {drawdown_pct}% (must be preserved)\n"

    prompt = (
        f"You are the CONSERVATIVE RISK DEBATER. Prioritise capital preservation.\n\n"
        f"INVESTMENT PLAN:\n{investment_plan}\n\n"
        f"TRADE: {symbol} {side}\n"
        f"{prop_line}\n"
        f"Argue (2-3 sentences) from a capital-preservation perspective:\n"
        f"- Why the risk factors should make us cautious\n"
        f"- Prop firm drawdown rules and account safety\n"
        f"- Whether the setup is mature enough for risk deployment\n\n"
        f'End with JSON: {{"argument": "your stance", "vote": "allow" or "block"}}'
    )
    system = "You are a conservative risk manager. Respond with argument + JSON vote."
    raw = _call(client, prompt, system, max_tokens=350)
    return _parse_vote(raw, "block")


def _stage_neutral_debater(
    payload: Dict[str, Any],
    investment_plan: str,
    client,
) -> Tuple[str, str]:
    """Provides a balanced risk/reward assessment."""
    symbol = payload.get("symbol", "UNKNOWN")
    side = (payload.get("side") or "buy").upper()

    prompt = (
        f"You are the NEUTRAL RISK DEBATER. Provide a balanced assessment.\n\n"
        f"INVESTMENT PLAN:\n{investment_plan}\n\n"
        f"TRADE: {symbol} {side}\n\n"
        f"Argue (2-3 sentences) from a balanced perspective:\n"
        f"- Weigh the aggressive and conservative positions\n"
        f"- What the evidence supports on balance\n"
        f"- Your neutral recommendation with key caveats\n\n"
        f'End with JSON: {{"argument": "your stance", "vote": "allow" or "block"}}'
    )
    system = "You are a neutral risk evaluator. Respond with argument + JSON vote."
    raw = _call(client, prompt, system, max_tokens=350)
    return _parse_vote(raw, "allow")


# ─────────────────────────────────────────────────────────────────────────────
# Stage 9: Risk Judge (deep LLM)
# ─────────────────────────────────────────────────────────────────────────────


def _stage_risk_judge(
    payload: Dict[str, Any],
    investment_plan: str,
    aggressive_arg: str,
    conservative_arg: str,
    neutral_arg: str,
    aggressive_vote: str,
    conservative_vote: str,
    neutral_vote: str,
    client,
    memory,
) -> Tuple[str, int, str]:
    """
    Deep-LLM final decision.
    Returns (decision: 'APPROVE'|'REJECT', confidence: int, reasoning: str).
    """
    symbol = payload.get("symbol", "UNKNOWN")
    side = (payload.get("side") or "buy").upper()

    vote_tally = sum(
        1 for v in [aggressive_vote, conservative_vote, neutral_vote] if v == "allow"
    )
    query = f"{symbol} {side} {investment_plan[:150]}"
    mem_block = memory.get("risk_judge").format_for_prompt(query)

    prompt = (
        f"You are the RISK JUDGE with final authority to APPROVE or REJECT this trade.\n\n"
        f"INVESTMENT PLAN:\n{investment_plan}\n\n"
        f"RISK DEBATE:\n"
        f"- Aggressive (vote={aggressive_vote}): {aggressive_arg}\n"
        f"- Conservative (vote={conservative_vote}): {conservative_arg}\n"
        f"- Neutral (vote={neutral_vote}): {neutral_arg}\n\n"
        f"Risk vote tally: {vote_tally}/3 allow\n\n"
        f"TRADE: {symbol} {side}"
        f"{mem_block}\n\n"
        f"Synthesise all perspectives and render your final verdict.\n"
        f"Respond ONLY with this JSON:\n"
        f'{{"decision": "APPROVE" or "REJECT", "confidence": 0-100, '
        f'"reasoning": "1-2 sentence explanation", '
        f'"key_risks": ["risk1", "risk2"]}}'
    )
    system = (
        "You are the chief risk officer making final trade approval decisions. "
        "Respond ONLY with valid JSON — no other text."
    )
    raw = _call(client, prompt, system, max_tokens=350, timeout=35.0)

    # Parse structured output
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(raw[start:end])
            decision = str(data.get("decision", "APPROVE")).upper()
            if decision not in ("APPROVE", "REJECT"):
                decision = "APPROVE"
            confidence = max(0, min(100, int(data.get("confidence", 60))))
            reasoning = str(data.get("reasoning", ""))[:400]
            return decision, confidence, reasoning
    except Exception as exc:
        logger.debug("Risk judge parse failed: %s  raw=%s", exc, raw[:200])

    # Fallback: derive from vote tally
    fallback_decision = "APPROVE" if vote_tally >= 2 else "REJECT"
    return fallback_decision, 50, f"Risk judge parse error — derived from {vote_tally}/3 allow votes."


# ─────────────────────────────────────────────────────────────────────────────
# Redis caching helpers
# ─────────────────────────────────────────────────────────────────────────────


def _cache_key(payload: Dict[str, Any]) -> str:
    symbol = (payload.get("symbol") or "UNKNOWN").upper()
    side = (payload.get("side") or "buy").upper()
    entry = round(float(payload.get("entry") or 0), 4)
    return f"{_CACHE_PREFIX}{symbol}:{side}:{entry}"


def _from_cache(redis_client, key: str) -> Optional[Dict[str, Any]]:
    if not redis_client:
        return None
    try:
        raw = redis_client.get(key)
        if raw:
            return json.loads(raw)
    except Exception:
        pass
    return None


def _to_cache(redis_client, key: str, value: Dict[str, Any]) -> None:
    if not redis_client:
        return
    try:
        redis_client.setex(key, _CACHE_TTL, json.dumps(value, default=str))
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Main public entry point
# ─────────────────────────────────────────────────────────────────────────────


def run_trading_council(
    payload: Dict[str, Any],
    *,
    supabase=None,
    redis_client=None,
) -> Dict[str, Any]:
    """
    Run the full 9-stage Trading Council pipeline for a trade signal.

    Returns a dict backward-compatible with run_debate() plus council-specific fields:
      recommendation    : "allow" | "block"   ← from Risk Judge decision
      confidence        : 0-100
      reason_codes      : list of strings
      memo              : short summary
      votes             : {bull, bear, aggressive, conservative, neutral, judge}
      transcript        : [{role, content}, ...]
      council_decision  : "APPROVE" | "REJECT"
      council_confidence: 0-100
      council_report    : {market, setup, investment_plan}

    Cache key: (symbol, side, entry_price).  TTL: AI_COUNCIL_CACHE_TTL seconds.
    """
    # ── check master toggle ───────────────────────────────────────────────
    try:
        enabled = os.environ.get("AI_COUNCIL_ENABLED", "true").lower() not in ("false", "0", "no")
    except Exception:
        enabled = True

    if not enabled:
        return _fallback_result("Council disabled via AI_COUNCIL_ENABLED=false")

    # -- Rubric Engine composite score pre-gate ---------------------------
    # composite_score < 70  -> council skipped entirely (fallback result)
    # composite_score 70-77 -> council fires in shadow mode (recommendation always "allow")
    # composite_score >= 78 -> council can block execution (full mode)
    _rubric_shadow: bool = True  # default: shadow until proven otherwise
    try:
        from src.rubric_engine import score_signal as _score_signal
        _rubric = _score_signal(payload)
        if _rubric.hard_veto:
            logger.info(
                "Trading Council skipped: rubric hard veto -- %s", _rubric.veto_reason
            )
            return _fallback_result(f"Rubric hard veto: {_rubric.veto_reason}")
        if _rubric.composite_score < 70:
            logger.info(
                "Trading Council skipped: composite_score=%.1f < 70 (rubric gate)",
                _rubric.composite_score,
            )
            return _fallback_result(
                f"Rubric gate: composite_score={_rubric.composite_score:.1f} < 70"
            )
        _rubric_shadow = not _rubric.can_block  # shadow if 70 <= score < 78
        logger.info(
            "Rubric gate PASSED: composite_score=%.1f shadow=%s",
            _rubric.composite_score,
            _rubric_shadow,
        )
    except Exception as _re:
        logger.warning("Rubric engine failed (skipping gate, running council): %s", _re)

    # -- Redis cache -------------------------------------------------------
    ckey = _cache_key(payload)
    cached = _from_cache(redis_client, ckey)
    if cached:
        logger.info("Trading Council: cache hit for %s", ckey)
        return cached

    symbol = payload.get("symbol", "UNKNOWN")
    side = (payload.get("side") or "buy").upper()
    logger.info("Trading Council: starting 9-stage pipeline for %s %s", symbol, side)

    # ── Build LLM clients ─────────────────────────────────────────────────
    quick_model, deep_model = _get_models()
    quick_client = _build_client(quick_model)
    deep_client = _build_client(deep_model)

    # ── Load memory ───────────────────────────────────────────────────────
    from src.ai.council_memory import get_council_memory

    memory = get_council_memory()

    transcript: List[Dict[str, str]] = []

    # ── Stage 1: Market Analyst ────────────────────────────────────────────
    market_report = _stage_market_analyst(payload, quick_client)
    transcript.append({"role": "market_analyst", "content": market_report})
    logger.debug("Council Stage 1 (Market): %s…", market_report[:80])

    # ── Stage 2: Setup Analyst ─────────────────────────────────────────────
    setup_report = _stage_setup_analyst(payload, quick_client)
    transcript.append({"role": "setup_analyst", "content": setup_report})
    logger.debug("Council Stage 2 (Setup): %s…", setup_report[:80])

    # ── Stage 3: Bull Researcher ───────────────────────────────────────────
    bull_arg, bull_vote = _stage_bull_researcher(
        payload, market_report, setup_report, quick_client, memory
    )
    transcript.append({"role": "bull_researcher", "content": bull_arg})
    logger.debug("Council Stage 3 (Bull %s): %s…", bull_vote, bull_arg[:80])

    # ── Stage 4: Bear Researcher ───────────────────────────────────────────
    bear_arg, bear_vote = _stage_bear_researcher(
        payload, market_report, setup_report, quick_client, memory
    )
    transcript.append({"role": "bear_researcher", "content": bear_arg})
    logger.debug("Council Stage 4 (Bear %s): %s…", bear_vote, bear_arg[:80])

    # ── Stage 5: Research Manager (deep) ──────────────────────────────────
    investment_plan = _stage_research_manager(
        payload, market_report, setup_report, bull_arg, bear_arg, deep_client, memory
    )
    transcript.append({"role": "research_manager", "content": investment_plan})
    logger.debug("Council Stage 5 (ResearchMgr): %s…", investment_plan[:80])

    # ── Stage 6-8: Risk Debaters ───────────────────────────────────────────
    agg_arg, agg_vote = _stage_aggressive_debater(payload, investment_plan, quick_client)
    transcript.append({"role": "aggressive_debater", "content": agg_arg})

    con_arg, con_vote = _stage_conservative_debater(payload, investment_plan, quick_client)
    transcript.append({"role": "conservative_debater", "content": con_arg})

    neu_arg, neu_vote = _stage_neutral_debater(payload, investment_plan, quick_client)
    transcript.append({"role": "neutral_debater", "content": neu_arg})

    logger.debug(
        "Council Stages 6-8 (Risk Debate): agg=%s con=%s neu=%s",
        agg_vote,
        con_vote,
        neu_vote,
    )

    # ── Stage 9: Risk Judge (deep) ─────────────────────────────────────────
    judge_decision, judge_confidence, judge_reasoning = _stage_risk_judge(
        payload,
        investment_plan,
        agg_arg,
        con_arg,
        neu_arg,
        agg_vote,
        con_vote,
        neu_vote,
        deep_client,
        memory,
    )
    transcript.append({"role": "risk_judge", "content": judge_reasoning})

    logger.info(
        "Trading Council FINAL: %s (confidence=%d) — %s",
        judge_decision,
        judge_confidence,
        judge_reasoning[:100],
    )

    # -- Build result ------------------------------------------------------
    # Shadow mode: rubric_score in [70, 78) -- council ran but cannot block
    if _rubric_shadow and judge_decision == "REJECT":
        logger.info(
            "Trading Council: shadow mode override -- REJECT -> APPROVE "
            "(composite_score below block threshold)"
        )
        recommendation = "allow"
    else:
        recommendation = "allow" if judge_decision == "APPROVE" else "block"
    votes_tally = sum(
        1 for v in [bull_vote, agg_vote, neu_vote, con_vote] if v == "allow"
    ) + (1 if judge_decision == "APPROVE" else 0)

    reason_codes: List[str] = []
    if judge_decision == "REJECT":
        reason_codes.append("risk_judge_reject")
    if bull_vote == "block":
        reason_codes.append("bull_no_conviction")
    if bear_vote == "allow":
        reason_codes.append("bear_allows")
    if con_vote == "block":
        reason_codes.append("conservative_block")

    result: Dict[str, Any] = {
        # ── backward-compat with run_debate() ──
        "recommendation": recommendation,
        "confidence": judge_confidence,
        "reason_codes": reason_codes,
        "memo": f"[Council] {judge_reasoning[:200]}",
        "votes": {
            "bull": bull_vote,
            "bear": bear_vote,
            "aggressive": agg_vote,
            "conservative": con_vote,
            "neutral": neu_vote,
            "judge": recommendation,
        },
        "transcript": transcript,
        # ── council-specific ──
        "council_decision": judge_decision,
        "council_confidence": judge_confidence,
        "council_report": {
            "market": market_report,
            "setup": setup_report,
            "investment_plan": investment_plan,
        },
        "votes_tally": f"{votes_tally}/5 allow",
    }

    _to_cache(redis_client, ckey, result)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Reflection: called after trade closes
# ─────────────────────────────────────────────────────────────────────────────


def reflect_on_trade(
    symbol: str,
    side: str,
    pnl_usd: float,
    trade_summary: str,
    *,
    supabase=None,
    llm_client=None,
) -> None:
    """
    Called after a trade closes. Generates lessons and stores them in all
    agent memories so future similar setups benefit from past experience.

    Args:
        symbol       : e.g. "EURUSD"
        side         : "buy" | "sell"
        pnl_usd      : final P&L in USD (positive=win, negative=loss)
        trade_summary: brief description of the setup (zone score, entry model, etc.)
        supabase     : optional Supabase client for persistence
        llm_client   : optional pre-built LLM client (will auto-create if None)
    """
    if llm_client is None:
        try:
            from src.ai.llm_client import get_ai_client

            llm_client = get_ai_client()
        except Exception:
            return

    outcome = "winning" if pnl_usd > 0 else "losing"
    prompt = (
        f"A {outcome} trade on {symbol} {side} just closed. P&L: ${pnl_usd:.2f}\n\n"
        f"TRADE SUMMARY:\n{trade_summary[:800]}\n\n"
        f"In 2 sentences, state:\n"
        f"1. What setup characteristics contributed most to this {outcome} outcome\n"
        f"2. What to remember for future similar setups\n\n"
        f'Respond with JSON only: {{"situation": "brief setup description", "lesson": "key takeaway"}}'
    )
    system = "You are a professional trading coach. Respond with valid JSON only."

    raw = _call(llm_client, prompt, system, max_tokens=200, timeout=20.0)
    if not raw:
        return

    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start < 0 or end <= start:
            return
        data = json.loads(raw[start:end])
        situation = str(data.get("situation", f"{symbol} {side} {outcome}"))[:300]
        lesson = str(data.get("lesson", f"Trade was {outcome}, P&L ${pnl_usd:.2f}"))[:300]

        from src.ai.council_memory import get_council_memory

        memory = get_council_memory()
        roles_to_update = ["bull_researcher", "bear_researcher", "research_manager", "risk_judge"]
        for role in roles_to_update:
            memory.add_reflection(
                role,
                situation,
                lesson,
                symbol=symbol,
                outcome_pnl=pnl_usd,
                supabase=supabase,
            )

        logger.info(
            "Council reflection stored: %s %s %s P&L=$%.2f — '%s'",
            symbol,
            side,
            outcome,
            pnl_usd,
            lesson[:80],
        )
    except Exception as exc:
        logger.debug("reflect_on_trade failed: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────


def _fallback_result(reason: str) -> Dict[str, Any]:
    return {
        "recommendation": "allow",
        "confidence": 50,
        "reason_codes": ["council_skipped"],
        "memo": reason,
        "votes": {},
        "transcript": [],
        "council_decision": "APPROVE",
        "council_confidence": 50,
        "council_report": {},
        "votes_tally": "N/A",
    }


def load_council_memories_from_supabase(supabase) -> int:
    """
    Call on worker startup to hydrate in-process BM25 memory from Supabase.
    Returns number of memories loaded.
    """
    from src.ai.council_memory import get_council_memory

    memory = get_council_memory()
    count = memory.load_from_supabase(supabase)
    if count:
        logger.info("Trading Council: loaded %d memories from Supabase", count)
    return count
