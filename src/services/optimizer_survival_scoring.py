from __future__ import annotations

from typing import Any


def classify_pair_result(
    *,
    forward_metrics: dict[str, Any],
    stress_metrics: list[dict[str, Any]],
    pair_dd_limit: float,
    pair_daily_limit: float,
) -> dict[str, str]:
    if float(forward_metrics["max_drawdown_pct"]) > pair_dd_limit:
        return {"status": "REJECT", "reason": "Forward max drawdown exceeded internal gate"}

    if float(forward_metrics["max_daily_loss_pct"]) > pair_daily_limit:
        return {"status": "REJECT", "reason": "Forward daily drawdown exceeded internal gate"}

    if (
        float(forward_metrics["net_profit"]) <= 0
        or float(forward_metrics["profit_factor"]) < 1.10
        or int(forward_metrics["total_trades"]) < 15
    ):
        return {"status": "REJECT", "reason": "Forward survival gate failed"}

    stressed_failure = any(
        item["status"] == "failed" or float(item.get("metrics", {}).get("max_drawdown_pct", 0)) > pair_dd_limit
        for item in stress_metrics
    )
    if stressed_failure:
        return {"status": "REDUCE_RISK", "reason": "Stress result approached or broke internal tolerance"}

    return {"status": "PASS", "reason": "Forward and stress gates passed"}
