from scripts.optimizer.backtest_live_gap_analyzer import (
    DEFAULT_THRESHOLDS,
    analyze_backtest_live_gap,
)
from scripts.optimizer.discord_backtest_ingestor import summarize_discord_backtest_rows
from scripts.optimizer.evidence_permission_recommender import build_evidence_permission_recommendations
from scripts.optimizer.live_trade_log_ingestor import summarize_live_trade_rows


def _backtest_rows(
    *,
    count: int = 40,
    symbol: str = "NQ1!",
    entry_model: str = "Flip",
    hour: int = 8,
    rr: float = 2.0,
) -> list[dict]:
    return [
        {
            "instrument": symbol,
            "hour": str(hour),
            "entry_type": entry_model,
            "side": "Buys",
            "rr": str(rr),
        }
        for _ in range(count)
    ]


def _live_rows(
    *,
    count: int = 40,
    symbol: str = "NQ1!",
    entry_model: str = "FLIP",
    session: str = "LDN",
    status: str = "CLOSED",
    exit_type: str = "sl_hit",
    rr: float = 2.0,
) -> list[dict]:
    return [
        {
            "Date": "2026-05-05 08:00:00",
            "Symbol": symbol,
            "Side": "BUY",
            "Status": status,
            "Entry Model": entry_model,
            "Session": session,
            "Zone Grade": "A+",
            "Exit Type": exit_type,
            "R:R": str(rr),
        }
        for _ in range(count)
    ]


def _summaries(backtest_rows: list[dict], live_rows: list[dict]) -> tuple[dict, dict]:
    return summarize_discord_backtest_rows(backtest_rows), summarize_live_trade_rows(live_rows)


def test_strong_backtest_and_weak_live_is_implementation_gap() -> None:
    backtest, live = _summaries(_backtest_rows(), _live_rows(exit_type="sl_hit"))

    report = analyze_backtest_live_gap(backtest, live, thresholds=DEFAULT_THRESHOLDS)

    assert report["global_status"] == "IMPLEMENTATION_GAP"
    candidate = report["candidates"]["NQ1!"]
    assert candidate["status"] == "IMPLEMENTATION_GAP"
    assert "execution_latency_slippage" in candidate["possible_causes"]
    assert candidate["recommendation"] == "NO_LIVE_TRADING"


def test_strong_backtest_with_no_live_data_is_watch_only() -> None:
    backtest, live = _summaries(_backtest_rows(), [])

    report = analyze_backtest_live_gap(backtest, live, thresholds=DEFAULT_THRESHOLDS)

    assert report["global_status"] == "WATCH_ONLY"
    assert report["candidates"]["NQ1!"]["status"] == "WATCH_ONLY"


def test_weak_backtest_is_rejected() -> None:
    backtest, live = _summaries(_backtest_rows(count=40, rr=-1.0), [])

    report = analyze_backtest_live_gap(backtest, live, thresholds=DEFAULT_THRESHOLDS)

    assert report["global_status"] == "REJECT_RESEARCH"
    assert report["candidates"]["NQ1!"]["status"] == "REJECT_RESEARCH"


def test_high_execution_failures_block_execution_health() -> None:
    live_rows = _live_rows(count=38, exit_type="tp_hit") + _live_rows(count=2, status="EXECUTION_FAILED")
    backtest, live = _summaries(_backtest_rows(), live_rows)

    report = analyze_backtest_live_gap(backtest, live, thresholds=DEFAULT_THRESHOLDS)

    assert report["global_status"] == "NO_TRADE_EXECUTION_HEALTH_FAILED"
    assert report["candidates"]["NQ1!"]["status"] == "NO_TRADE_EXECUTION_HEALTH_FAILED"


def test_timezone_session_mismatch_is_detected() -> None:
    backtest, live = _summaries(_backtest_rows(hour=8), _live_rows(session="Asia", exit_type="tp_hit"))

    report = analyze_backtest_live_gap(backtest, live, thresholds=DEFAULT_THRESHOLDS)

    assert "session_timezone_mismatch" in report["candidates"]["NQ1!"]["detected_gaps"]


def test_entry_model_mismatch_is_detected() -> None:
    backtest, live = _summaries(
        _backtest_rows(entry_model="Flip"),
        _live_rows(entry_model="BREAK_CANDLE", exit_type="tp_hit"),
    )

    report = analyze_backtest_live_gap(backtest, live, thresholds=DEFAULT_THRESHOLDS)

    assert "entry_model_mismatch" in report["candidates"]["NQ1!"]["detected_gaps"]


def test_recommendations_fail_closed() -> None:
    backtest, live = _summaries(_backtest_rows(), _live_rows(exit_type="sl_hit"))
    report = analyze_backtest_live_gap(backtest, live, thresholds=DEFAULT_THRESHOLDS)

    recommendations = build_evidence_permission_recommendations(report)

    assert recommendations["approved_candidates"]["NQ1!"]["candidate_status"] == "WATCH_ONLY"
    assert recommendations["daily_trade_permissions"]["global_decision"] == "NO_TRADE"
    assert recommendations["daily_trade_permissions"]["permissions"] == {}


def test_strong_discord_segments_include_boc_and_key_hours() -> None:
    rows = (
        _backtest_rows(count=40, entry_model="Flip", hour=7)
        + _backtest_rows(count=35, entry_model="BoC", hour=8)
        + _backtest_rows(count=31, entry_model="Directional", hour=13)
        + _backtest_rows(count=30, entry_model="Flip", hour=14)
    )
    backtest, live = _summaries(rows, [])

    report = analyze_backtest_live_gap(backtest, live, thresholds=DEFAULT_THRESHOLDS)

    assert {"FLIP", "BOC"}.issubset(set(report["strong_backtest_segments"]["entry_models"]))
    assert {"7", "8", "13", "14"}.issubset(set(report["strong_backtest_segments"]["hours"]))


def test_stale_rejected_unexecuted_rate_counts_unique_signals() -> None:
    live = summarize_live_trade_rows(
        [
            {
                "Date": "2026-05-05 08:00:00",
                "Symbol": "NQ1!",
                "Side": "BUY",
                "Status": "TRADING_PERMISSION_REJECTED",
                "Entry Model": "FLIP",
                "Session": "LDN",
            },
            {
                "Date": "2026-05-05 08:05:00",
                "Symbol": "NQ1!",
                "Side": "BUY",
                "Status": "CLOSED",
                "Entry Model": "FLIP",
                "Session": "LDN",
                "Exit Type": "tp_hit",
                "R:R": "2",
            },
        ]
    )

    assert live["stale_rejected_unexecuted"] == 1
    assert live["staleness_rejection_rate_pct"] == 50.0
