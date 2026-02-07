"""Backtest Replay Engine.

Replays historical signals through the full pipeline (pine filters, ensemble
brain, position sizing) with optional config overrides.  Does NOT interact
with any broker — results are written to ``trading_signals`` with
``run_mode='BACKTEST'`` and a unique ``run_id``.

Also provides equity curve and drawdown from existing signals (LIVE or BACKTEST).
"""

import json
import logging
import time
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_supabase = None


def _get_supabase():
    global _supabase
    if _supabase is not None:
        return _supabase
    from config import get_settings
    from supabase import create_client

    s = get_settings()
    key = (s.supabase_service_role_key or s.supabase_key or "").strip()
    if s.supabase_url and key:
        _supabase = create_client(s.supabase_url, key)
    return _supabase


class BacktestEngine:
    """Replay signals through pine filters + ensemble + sizing."""

    def __init__(self, config_overrides: Dict[str, Any], run_id: str):
        self.config_overrides = config_overrides
        self.run_id = run_id

    def run(self, signals: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute backtest on a list of signal payloads.  Returns summary."""
        from src.ai.brain import load_brain

        load_brain()

        results: List[Dict[str, Any]] = []
        wins = 0
        losses = 0
        total_pnl_r = 0.0

        for signal in signals:
            result = self._process_single(deepcopy(signal))
            results.append(result)

            outcome = result.get("outcome")
            if outcome == "win":
                wins += 1
                total_pnl_r += float(result.get("pnl_r") or 0)
            elif outcome == "loss":
                losses += 1
                total_pnl_r += float(result.get("pnl_r") or 0)

        total = wins + losses
        summary: Dict[str, Any] = {
            "run_id": self.run_id,
            "total_signals": len(signals),
            "accepted": sum(1 for r in results if r.get("status") == "accepted"),
            "rejected": sum(1 for r in results if r.get("status") != "accepted"),
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / total * 100, 1) if total > 0 else 0,
            "total_pnl_r": round(total_pnl_r, 2),
            "config_overrides": self.config_overrides,
        }

        # Update backtest_runs row
        try:
            sb = _get_supabase()
            if sb:
                sb.table("backtest_runs").update(
                    {
                        "status": "completed",
                        "signal_count": len(signals),
                        "result_summary": json.dumps(summary),
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    }
                ).eq("run_id", self.run_id).execute()
        except Exception as exc:
            logger.error("Failed to update backtest_runs: %s", exc)

        return summary

    # ── Single signal replay ─────────────────────────────────

    def _process_single(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        payload["run_mode"] = "BACKTEST"
        payload["run_id"] = self.run_id

        # 1. Pine pre-filters
        try:
            from src.worker import _validate_pine_filters, _validate_flip_timing

            flip_err = _validate_flip_timing(payload)
            if flip_err:
                self._save_bt(payload, "filtered", f"flip: {flip_err}")
                return {"status": "rejected", "reason": f"flip: {flip_err}", "outcome": None}

            pine_err = _validate_pine_filters(payload)
            if pine_err:
                self._save_bt(payload, "filtered", f"pine: {pine_err}")
                return {"status": "rejected", "reason": f"pine: {pine_err}", "outcome": None}
        except Exception as exc:
            logger.debug("Pine filter error in backtest: %s", exc)

        # 2. Ensemble brain
        try:
            from src.ai.brain import ensemble_decision

            ai_result = ensemble_decision(payload)
            decision = str(ai_result.get("decision", "NO_GO")).upper()
            if decision == "NO_GO":
                self._save_bt(payload, "ai_rejected", ai_result.get("reason", "AI rejected"))
                return {
                    "status": "rejected",
                    "reason": ai_result.get("reason", "AI rejected"),
                    "outcome": None,
                    "rf_prob": ai_result.get("rf_prob"),
                }
            payload["ai_reasoning"] = ai_result
            payload["ai_confidence"] = round(float(ai_result.get("rf_prob", 0)) * 100, 1)
        except Exception as exc:
            logger.debug("Ensemble decision error in backtest: %s", exc)

        # 3. Outcome from the original signal (if it already went through live)
        outcome = payload.get("outcome")
        pnl_r = payload.get("pnl_r", 0)
        pnl_usd = payload.get("pnl_usd")

        # 4. Save to DB as BACKTEST signal
        alert_id = self._save_bt(payload, "closed" if outcome else "active", None)
        if outcome and alert_id:
            try:
                sb = _get_supabase()
                if sb:
                    sb.table("trading_signals").update(
                        {
                            "status": "closed",
                            "outcome": outcome,
                            "pnl_r": pnl_r,
                            "pnl_usd": pnl_usd,
                        }
                    ).eq("id", alert_id).execute()
            except Exception:
                pass

        return {
            "status": "accepted",
            "outcome": outcome,
            "pnl_r": pnl_r,
            "rf_prob": (payload.get("ai_reasoning") or {}).get("rf_prob"),
            "ai_decision": "GO",
        }

    def _save_bt(self, payload: Dict[str, Any], status: str, note: str | None) -> int | None:
        """Save a backtest signal row.  Returns alert_id or None."""
        try:
            from src.adapters.supabase import save_alert

            alert_id = save_alert(
                payload,
                mode="backtest",
                filter_reasons=[note] if note else None,
            )
            if note:
                from src.adapters.supabase import update_alert_status

                update_alert_status(alert_id, status, notes=note)
            return alert_id
        except Exception as exc:
            logger.debug("Backtest save failed: %s", exc)
            return None


# ── Equity curve & drawdown from existing signals ──────────────────────


def get_equity_curve_and_drawdown(
    run_mode: str = "BACKTEST",
    run_id: Optional[str] = None,
    starting_equity: float = 0.0,
) -> Dict[str, Any]:
    """
    Load closed signals for the given run_mode/run_id, sort by created_at,
    and compute cumulative PnL (equity curve) and max drawdown.

    Returns:
        {
            "equity_curve": [{"created_at": "...", "cumulative_pnl": float, "equity": float}, ...],
            "max_drawdown": float,
            "max_drawdown_pct": float,
            "total_pnl": float,
            "closed_count": int,
            "win_rate": float,
        }
    """
    sb = _get_supabase()
    if not sb:
        return {
            "equity_curve": [],
            "max_drawdown": 0.0,
            "max_drawdown_pct": 0.0,
            "total_pnl": 0.0,
            "closed_count": 0,
            "win_rate": 0.0,
        }
    try:
        query = (
            sb.table("trading_signals")
            .select("id, created_at, pnl_usd, pnl, outcome")
            .eq("status", "closed")
            .eq("run_mode", run_mode)
            .order("created_at")
        )
        if run_id:
            query = query.eq("run_id", run_id)
        rows = query.execute().data or []
    except Exception as exc:
        logger.error("get_equity_curve_and_drawdown query failed: %s", exc)
        return {
            "equity_curve": [],
            "max_drawdown": 0.0,
            "max_drawdown_pct": 0.0,
            "total_pnl": 0.0,
            "closed_count": 0,
            "win_rate": 0.0,
        }

    cumulative = starting_equity
    peak = cumulative
    max_dd = 0.0
    max_dd_pct = 0.0
    curve: List[Dict[str, Any]] = []
    wins = 0
    losses = 0

    for r in rows:
        pnl = r.get("pnl_usd")
        if pnl is None:
            pnl = r.get("pnl")
        if pnl is not None:
            pnl = float(pnl)
        else:
            pnl = 0.0
        cumulative += pnl
        if cumulative > peak:
            peak = cumulative
        dd = peak - cumulative
        if dd > max_dd:
            max_dd = dd
        if peak > 0 and dd > 0:
            pct = dd / peak * 100
            if pct > max_dd_pct:
                max_dd_pct = pct
        outcome = (r.get("outcome") or "").lower()
        if outcome == "win":
            wins += 1
        elif outcome == "loss":
            losses += 1
        curve.append({
            "created_at": r.get("created_at"),
            "cumulative_pnl": round(cumulative - starting_equity, 2),
            "equity": round(cumulative, 2),
        })

    total_closed = wins + losses
    win_rate = (wins / total_closed * 100) if total_closed > 0 else 0.0
    total_pnl = cumulative - starting_equity

    return {
        "equity_curve": curve,
        "max_drawdown": round(max_dd, 2),
        "max_drawdown_pct": round(max_dd_pct, 2),
        "total_pnl": round(total_pnl, 2),
        "closed_count": len(rows),
        "win_rate": round(win_rate, 1),
    }
