"""
AI Copilot API — natural language queries over live trading data.

POST /api/copilot/chat
- Receives a free-form question + optional conversation history
- Builds compact context from live signals, positions, analytics, risk status
- Calls the configured LLM (Claude/OpenAI) for a prose answer
- Falls back gracefully if the LLM or data sources are unavailable
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from config import get_settings
from src.adapters.supabase_api import get_api_supabase

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/copilot", tags=["copilot"])


# ── Request / Response Models ──────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str   # "user" | "assistant"
    content: str


class CopilotChatRequest(BaseModel):
    question: str
    history: list[ChatMessage] = []


class CopilotChatResponse(BaseModel):
    answer: str
    context_used: list[str] = []
    model_used: Optional[str] = None


# ── Context Builder ────────────────────────────────────────────────────────────

def _build_context() -> tuple[str, list[str]]:
    """
    Fetch live trading context and return (context_text, list_of_sources).
    Never raises — returns best-effort data on any error.
    """
    parts: list[str] = []
    sources: list[str] = []

    try:
        sb = get_api_supabase()

        # ── Recent signals (last 30) ──────────────────────────────────
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
            result = (
                sb.table("trading_signals")
                .select(
                    "id, symbol, side, entry, sl, tp, size, pnl_usd, pnl_r, "
                    "outcome, status, filter_reason, ai_confidence, zone_type, "
                    "entry_model, rr_ratio, created_at, closed_at, run_mode"
                )
                .gte("created_at", cutoff)
                .order("created_at", desc=True)
                .limit(30)
                .execute()
            )
            signals = result.data or []

            if signals:
                closed = [s for s in signals if s.get("status") == "closed"]
                active = [s for s in signals if s.get("status") in ("active", "executed")]
                rejected = [s for s in signals if s.get("status") in ("ai_rejected", "filtered")]

                # Summary stats
                pnls = [s["pnl_usd"] for s in closed if s.get("pnl_usd") is not None]
                wins = [p for p in pnls if p > 0]
                total_pnl = sum(pnls)
                win_rate = (len(wins) / len(pnls) * 100) if pnls else 0

                parts.append(
                    f"## Recent Signals (last 30 days)\n"
                    f"Total signals: {len(signals)} | "
                    f"Closed trades: {len(closed)} | "
                    f"Active: {len(active)} | "
                    f"Rejected/Filtered: {len(rejected)}\n"
                    f"Closed trade stats: Win rate={win_rate:.1f}%, "
                    f"Total PnL=${total_pnl:.2f}, "
                    f"Avg PnL=${total_pnl/len(pnls):.2f}" if pnls else
                    f"Closed trade stats: No closed trades with PnL data"
                )
                sources.append("recent_signals")

                # Recent 10 signals table
                rows = []
                for s in signals[:10]:
                    pnl_str = f"${s['pnl_usd']:.2f}" if s.get("pnl_usd") is not None else "open"
                    rows.append(
                        f"  - {s.get('symbol','?')} {s.get('side','?').upper()} | "
                        f"status={s.get('status','?')} | "
                        f"pnl={pnl_str} | "
                        f"model={s.get('entry_model','?')} | "
                        f"ai_conf={s.get('ai_confidence','?')} | "
                        f"reason={s.get('filter_reason','') or ''}"
                    )
                parts.append("Last 10 signals:\n" + "\n".join(rows))

                # Symbol breakdown
                sym_map: dict[str, dict] = {}
                for s in closed:
                    sym = s.get("symbol", "?")
                    if sym not in sym_map:
                        sym_map[sym] = {"count": 0, "wins": 0, "pnl": 0.0}
                    sym_map[sym]["count"] += 1
                    p = s.get("pnl_usd") or 0
                    sym_map[sym]["pnl"] += p
                    if p > 0:
                        sym_map[sym]["wins"] += 1
                if sym_map:
                    sym_rows = sorted(sym_map.items(), key=lambda x: -x[1]["count"])
                    sym_lines = [
                        f"  {sym}: {d['count']} trades, "
                        f"{d['wins']/d['count']*100:.0f}% WR, "
                        f"${d['pnl']:.2f} PnL"
                        for sym, d in sym_rows
                    ]
                    parts.append("Symbol breakdown:\n" + "\n".join(sym_lines))

        except Exception as e:
            logger.warning("Copilot: failed to fetch signals: %s", e)

        # ── Active positions ───────────────────────────────────────────
        try:
            pos_result = (
                sb.table("trading_signals")
                .select("symbol, side, entry, size, pnl_usd, status, created_at")
                .in_("status", ["active", "executed"])
                .order("created_at", desc=True)
                .limit(10)
                .execute()
            )
            positions = pos_result.data or []
            if positions:
                pos_lines = [
                    f"  - {p.get('symbol')} {p.get('side','?').upper()} "
                    f"@ {p.get('entry','?')} | size={p.get('size','?')} | "
                    f"floating=${p.get('pnl_usd') or 0:.2f}"
                    for p in positions
                ]
                parts.append(
                    f"## Open Positions ({len(positions)} active)\n" +
                    "\n".join(pos_lines)
                )
                sources.append("open_positions")
        except Exception as e:
            logger.warning("Copilot: failed to fetch positions: %s", e)

        # ── Prop firm status (latest snapshot) ────────────────────────
        try:
            pf_result = (
                sb.table("prop_firm_metrics")
                .select(
                    "daily_drawdown_pct, trailing_drawdown_pct, daily_pnl_total, "
                    "current_equity, daily_loss_breach, drawdown_breach, "
                    "kill_switch_engaged, evaluation_phase, snapshot_time"
                )
                .order("snapshot_time", desc=True)
                .limit(1)
                .execute()
            )
            pf = (pf_result.data or [None])[0]
            if pf:
                parts.append(
                    f"## Prop Firm Status\n"
                    f"Phase: {pf.get('evaluation_phase','?')} | "
                    f"Daily DD: {pf.get('daily_drawdown_pct',0):.2f}% | "
                    f"Trailing DD: {pf.get('trailing_drawdown_pct',0):.2f}% | "
                    f"Daily PnL: ${pf.get('daily_pnl_total',0):.2f} | "
                    f"Equity: ${pf.get('current_equity',0):.2f} | "
                    f"Safe to trade: {not (pf.get('daily_loss_breach') or pf.get('drawdown_breach'))}"
                )
                sources.append("prop_firm_metrics")
        except Exception as e:
            logger.warning("Copilot: failed to fetch prop firm data: %s", e)

    except Exception as e:
        logger.warning("Copilot: context build failed: %s", e)

    context_text = "\n\n".join(parts) if parts else "No live data available."
    return context_text, sources


# ── System Prompt ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are TradeOps Copilot, an expert trading assistant embedded in a live algorithmic trading dashboard.

You have access to real-time trading data and should give precise, actionable answers.

Guidelines:
- Be concise and direct. Use **bold** for key numbers and insights.
- For P&L, always include the $ sign and + or - prefix.
- Highlight risks clearly (e.g. drawdown approaching limits).
- If the data shows a pattern worth noting (e.g. losing on Fridays), mention it proactively.
- Keep answers under 200 words unless the question requires more detail.
- Use bullet points for multi-item answers.
- Do not mention that you are an AI or that you are using a language model.
- If data is missing or unavailable, say so clearly and suggest what the user can check.
"""


# ── Endpoint ───────────────────────────────────────────────────────────────────

@router.post("/chat", response_model=CopilotChatResponse)
async def copilot_chat(request: CopilotChatRequest) -> CopilotChatResponse:
    """
    Answer a natural language question about live trading data.
    Builds context from signals, positions, and prop firm metrics,
    then calls the configured LLM for a prose answer.
    """
    settings = get_settings()

    # Build context
    context_text, sources = _build_context()

    # Build user prompt with context + question
    # Include last 3 history turns for conversational continuity
    history_text = ""
    if request.history:
        turns = request.history[-6:]  # last 3 exchanges
        history_lines = [f"{m.role.capitalize()}: {m.content}" for m in turns]
        history_text = "\nConversation history:\n" + "\n".join(history_lines) + "\n"

    prompt = (
        f"Live trading data context:\n\n{context_text}\n"
        f"{history_text}\n"
        f"User question: {request.question}\n\n"
        f"Answer the question based on the trading data above. "
        f"Be specific, cite numbers from the data, and give actionable insights."
    )

    # Call LLM
    try:
        from src.ai.llm_client import get_ai_client, AIClientError

        client = get_ai_client()
        answer = client._raw_complete(
            prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.3,
            max_tokens=512,
            timeout=20.0,
        )

        if not answer or not answer.strip():
            raise ValueError("Empty response from LLM")

        model_used = getattr(client, "_model", "unknown")
        return CopilotChatResponse(
            answer=answer.strip(),
            context_used=sources,
            model_used=model_used,
        )

    except Exception as e:
        logger.error("Copilot LLM call failed: %s", e)
        # Graceful fallback — describe what we found in the data
        if sources:
            return CopilotChatResponse(
                answer=(
                    "⚠️ AI response unavailable right now. "
                    f"I loaded context from: {', '.join(sources)}. "
                    "Please check your AI API key in settings."
                ),
                context_used=sources,
            )
        return CopilotChatResponse(
            answer=(
                "⚠️ Unable to answer — both AI and live data are unavailable. "
                "Check that the backend is running and your API key is configured."
            ),
            context_used=[],
        )
