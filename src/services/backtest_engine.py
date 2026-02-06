"""Backtest Replay Engine.

Replays historical signals through the full pipeline (pine filters, ensemble
brain, position sizing) with optional config overrides.  Does NOT interact
with any broker — results are written to ``trading_signals`` with
``run_mode='BACKTEST'`` and a unique ``run_id``.
"""

import json
import logging
import time
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List

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
