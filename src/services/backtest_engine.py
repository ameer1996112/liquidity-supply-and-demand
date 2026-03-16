"""
Sprint 4.1: Backtest engine — replays signals in time order, runs pipeline in simulation.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from config import get_settings

from src.services.lookahead_bias_detector import (
    LookAheadBiasError,
    filter_candles_to_time,
    get_decision_ts_from_signal,
)

logger = logging.getLogger(__name__)


def run_backtest(
    backtest_id: int,
    config: Dict[str, Any],
    supabase: Any,
    *,
    on_progress: Optional[Callable[[int, str, Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    """
    Run backtest: load signals, replay in order, run pipeline sim, compute metrics.

    on_progress(percent, message, extra) called for SSE.
    """
    def emit(percent: int, msg: str, extra: Optional[Dict] = None):
        if on_progress:
            on_progress(percent, msg, extra or {})

    try:
        emit(5, "Loading signals")
        signals = _load_signals(supabase, config)
        if not signals:
            emit(100, "No signals in range")
            return _metrics_empty()

        emit(10, f"Replaying {len(signals)} signals")
        trades: List[Dict] = []
        latencies: List[float] = []
        rule_violations = 0
        daily_loss_hits = 0
        equity = float(config.get("initial_cash", 10000))
        peak = equity
        daily_pnl: Dict[str, float] = {}

        for i, sig in enumerate(signals):
            pct = 10 + int(80 * (i + 1) / len(signals))
            emit(pct, f"Processing {i + 1}/{len(signals)}", {"symbol": sig.get("symbol")})

            payload = _signal_to_payload(sig)
            decision_ts = get_decision_ts_from_signal(sig)
            eval_config = _build_eval_config(config, sig, decision_ts)

            t0 = time.perf_counter()
            ai_result = _evaluate_with_cache(supabase, payload, eval_config)
            lat_ms = (time.perf_counter() - t0) * 1000
            latencies.append(lat_ms)

            decision = (ai_result or {}).get("decision", "NO_GO")
            if decision != "GO":
                rule_violations += 1
                continue

            fill = _paper_fill_from_signal(sig, payload)
            if not fill:
                continue
            pnl = fill.get("pnl", 0)
            equity += pnl
            peak = max(peak, equity)
            day = (fill.get("exit_time") or "")
            if day:
                day = day[:10]
                daily_pnl[day] = daily_pnl.get(day, 0) + pnl
                if daily_pnl[day] <= float(config.get("daily_loss_limit", -500)):
                    daily_loss_hits += 1

            trades.append({
                "symbol": payload.get("symbol"),
                "side": payload.get("side"),
                "entry": payload.get("entry"),
                "exit": fill.get("exit_price"),
                "pnl": pnl,
                "outcome": "win" if pnl > 0 else "loss",
            })

        emit(95, "Computing metrics")
        metrics = _compute_metrics(
            trades=trades,
            latencies=latencies,
            rule_violations=rule_violations,
            daily_loss_hits=daily_loss_hits,
            initial_cash=float(config.get("initial_cash", 10000)),
            final_equity=equity,
            peak=peak,
        )
        emit(100, "Done", metrics)
        return metrics
    except Exception as e:
        logger.exception("Backtest failed: %s", e)
        emit(100, "Failed", {"error": str(e)})
        raise


def _load_signals(supabase: Any, config: Dict) -> List[Dict]:
    """Load closed signals from DB in date range."""
    if not supabase:
        return []
    start = config.get("start_date", "2025-01-01")
    end = config.get("end_date", "2026-12-31")
    symbol = config.get("symbol", "")
    try:
        q = (
            supabase.table("trading_signals")
            .select("id, symbol, side, entry, sl, tp, size, zone_id, score, entry_model, created_at, pnl_usd, outcome, exit_price, closed_at")
            .in_("status", ["CLOSED", "closed"])
            .in_("outcome", ["win", "loss"])
            .gte("created_at", f"{start}T00:00:00Z")
            .lte("created_at", f"{end}T23:59:59Z")
        )
        if symbol:
            q = q.eq("symbol", symbol)
        resp = q.order("created_at").execute()
        return resp.data or []
    except Exception as e:
        logger.warning("Failed to load signals: %s", e)
        return []


def _signal_to_payload(sig: Dict) -> Dict:
    """Convert DB row to pipeline payload."""
    return {
        "symbol": sig.get("symbol", "UNKNOWN"),
        "side": sig.get("side", "buy"),
        "entry": float(sig.get("entry") or 0),
        "sl": float(sig.get("sl") or 0),
        "tp": float(sig.get("tp") or 0),
        "size": float(sig.get("size") or 0.01),
        "zone_id": sig.get("zone_id"),
        "score": sig.get("score"),
        "entry_model": sig.get("entry_model"),
        "run_mode": "PAPER",
    }


def _build_eval_config(config: Dict, sig: Dict, decision_ts: float) -> Dict:
    """
    Build config for evaluation with candles filtered to decision time.
    Candles with timestamp > decision_ts cause LookAheadBiasError (strict mode).
    """
    out = dict(config)
    candles = config.get("candles") or []
    if not candles:
        return out
    timeframe = config.get("timeframe", "5m")
    out["candles"] = filter_candles_to_time(
        candles,
        decision_ts,
        timeframe=timeframe,
        time_key="time",
        strict=True,
    )
    return out


def _evaluate_with_cache(supabase: Any, payload: Dict, config: Dict) -> Optional[Dict]:
    """Run ensemble with AI decision cache."""
    from src.services.ai_decision_cache import (
        build_cache_key,
        cache_get,
        cache_set,
        signal_hash,
        candle_context_hash,
    )

    try:
        from src.agents.supervisor import Supervisor
    except ImportError:
        return {"decision": "GO", "rf_prob": 0.5, "reason": "No supervisor"}

    sh = signal_hash(payload)
    ctx_hash = candle_context_hash(config.get("candles", []) or [])
    model = getattr(get_settings(), "ai_deep_model", "") or "default"
    cache_key = build_cache_key(sh, ctx_hash, model)

    cached = cache_get(supabase, cache_key)
    if cached:
        return cached

    supervisor = Supervisor(supabase_client=supabase, redis_client=None)
    result = supervisor.evaluate(payload)
    cache_set(supabase, cache_key, result)
    return result


def _paper_fill_from_signal(sig: Dict, payload: Dict) -> Optional[Dict]:
    """Use actual outcome from signal when available (replay mode)."""
    pnl = sig.get("pnl_usd")
    outcome = (sig.get("outcome") or "").lower()
    if pnl is not None and outcome in ("win", "loss"):
        return {
            "exit_price": sig.get("exit_price") or payload.get("tp") or payload.get("sl"),
            "pnl": float(pnl),
            "exit_time": sig.get("closed_at") or sig.get("created_at") or "",
        }
    # Fallback: deterministic from zone_id
    entry = float(payload.get("entry") or 0)
    sl = float(payload.get("sl") or 0)
    tp = float(payload.get("tp") or 0)
    if not entry or not sl or not tp:
        return None
    zone_id = payload.get("zone_id") or 0
    win = (zone_id % 2) == 0  # deterministic
    side = (payload.get("side") or "buy").upper()
    exit_price = tp if (win and side == "BUY") or (not win and side == "SELL") else sl
    risk = abs(entry - sl)
    reward = abs(tp - entry) if side == "BUY" else abs(entry - tp)
    pnl_val = (reward if win else -risk) * float(payload.get("size", 0.01)) * 100000
    return {
        "exit_price": exit_price,
        "pnl": pnl_val,
        "exit_time": datetime.now(timezone.utc).isoformat(),
    }


def _compute_metrics(
    trades: List[Dict],
    latencies: List[float],
    rule_violations: int,
    daily_loss_hits: int,
    initial_cash: float,
    final_equity: float,
    peak: float,
) -> Dict[str, Any]:
    """Compute backtest metrics."""
    wins = [t for t in trades if t.get("outcome") == "win"]
    losses = [t for t in trades if t.get("outcome") == "loss"]
    n = len(trades)
    win_rate = (len(wins) / n * 100) if n else 0
    avg_r = 0
    if wins and losses:
        avg_win = sum(t.get("pnl", 0) for t in wins) / len(wins)
        avg_loss = abs(sum(t.get("pnl", 0) for t in losses) / len(losses))
        if avg_loss > 0:
            avg_r = avg_win / avg_loss
    max_dd = 0
    if peak > 0:
        max_dd = (peak - min(peak, final_equity)) / peak * 100
    avg_latency_ms = sum(latencies) / len(latencies) if latencies else 0
    return {
        "win_rate": round(win_rate, 2),
        "avg_r": round(avg_r, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "daily_loss_hits": daily_loss_hits,
        "rule_violations": rule_violations,
        "avg_latency_ms": round(avg_latency_ms, 2),
        "total_trades": n,
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "initial_cash": initial_cash,
        "final_equity": round(final_equity, 2),
        "total_return_pct": round((final_equity - initial_cash) / initial_cash * 100, 2),
    }


def _metrics_empty() -> Dict[str, Any]:
    return {
        "win_rate": 0,
        "avg_r": 0,
        "max_drawdown_pct": 0,
        "daily_loss_hits": 0,
        "rule_violations": 0,
        "avg_latency_ms": 0,
        "total_trades": 0,
        "winning_trades": 0,
        "losing_trades": 0,
        "initial_cash": 0,
        "final_equity": 0,
        "total_return_pct": 0,
    }
