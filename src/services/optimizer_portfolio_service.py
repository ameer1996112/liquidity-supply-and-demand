from __future__ import annotations

from typing import Any


def _initial_weight_for_status(status: str) -> float:
    status_weights = {
        "PASS": 1.0,
        "REDUCE_RISK": 0.5,
        "REJECT": 0.0,
    }
    return status_weights.get(status, 0.0)


def _curve_drawdown(drawdown_curve: list[float]) -> float:
    if not drawdown_curve:
        return 0.0
    return abs(min(float(point) for point in drawdown_curve))


def _curve_daily_drawdown(drawdown_curve: list[float]) -> float:
    if not drawdown_curve:
        return 0.0

    points = [float(point) for point in drawdown_curve]
    if len(points) == 1:
        return abs(points[0])

    return max(abs(current - previous) for previous, current in zip(points, points[1:]))


def _combined_metric(
    ordered_pairs: list[dict[str, Any]],
    weights: dict[str, float],
    metric_getter: Any,
) -> float:
    return sum(
        metric_getter(row.get("drawdown_curve", [])) * weights[row["symbol"]]
        for row in ordered_pairs
        if row["symbol"] in weights
    )


def allocate_portfolio_weights(
    pairs: list[dict[str, Any]],
    portfolio_dd_limit: float,
    portfolio_daily_limit: float,
) -> dict[str, Any]:
    weights: dict[str, float] = {}
    ordered = sorted(pairs, key=lambda row: float(row["safety_rank"]), reverse=True)

    for pair in ordered:
        symbol = str(pair["symbol"])
        proposed_weight = _initial_weight_for_status(str(pair.get("status", "")))
        candidate_weights = [proposed_weight]
        if proposed_weight == 1.0:
            candidate_weights.append(0.5)
        if candidate_weights[-1] != 0.0:
            candidate_weights.append(0.0)

        for candidate_weight in candidate_weights:
            weights[symbol] = candidate_weight
            combined_dd = _combined_metric(ordered, weights, _curve_drawdown)
            combined_daily = _combined_metric(ordered, weights, _curve_daily_drawdown)
            if combined_dd <= portfolio_dd_limit and combined_daily <= portfolio_daily_limit:
                break

    final_combined_dd = _combined_metric(ordered, weights, _curve_drawdown)
    # Daily risk is derived from the worst step-down in each curve, which is conservative
    # when we only have drawdown trajectories rather than per-day PnL slices.
    final_combined_daily = _combined_metric(ordered, weights, _curve_daily_drawdown)
    return {
        "weights": weights,
        "combined_max_drawdown_pct": final_combined_dd,
        "combined_daily_drawdown_pct": final_combined_daily,
    }
