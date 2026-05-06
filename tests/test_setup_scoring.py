from src.services.setup_scoring import score_rd_setup


def test_score_rd_setup_grades_clean_five_minute_setup() -> None:
    result = score_rd_setup(
        {
            "liq_swept": True,
            "caused_sweep": True,
            "target_swept": False,
            "entry_model": "Directional Close",
            "is_accuracy": True,
            "liquidityCandleCount": 4,
            "liq_candle_count": 4,
            "sweep_to_touch_bars": 3,
            "peak_to_touch_bars": 8,
            "bars_since_zone": 6,
            "base_quality": 0.82,
            "departure_strength": 0.88,
            "liquidity_distance": 0.78,
            "liquidity_spread": 0.74,
            "rr_ratio": 3.0,
            "sl_pips": 6.5,
            "session": 1,
            "zone_grade": "A",
        }
    )

    assert result["setup_score"] >= 85
    assert result["setup_grade"] == "A+"
    assert "multi_candle_liquidity" in result["setup_tags"]
    assert result["setup_score_breakdown"]["liquidity_sweep"]["points"] > 0


def test_score_rd_setup_penalizes_one_candle_or_missing_sweep() -> None:
    result = score_rd_setup(
        {
            "liq_swept": False,
            "caused_sweep": False,
            "target_swept": True,
            "entry_model": "Flip",
            "is_accuracy": False,
            "liq_candle_count": 1,
            "sweep_to_touch_bars": None,
            "bars_since_zone": 40,
            "base_quality": 0.25,
            "departure_strength": 0.20,
            "liquidity_distance": 0.20,
            "liquidity_spread": 0.15,
            "rr_ratio": 1.4,
            "sl_pips": 18,
            "session": 3,
            "zone_grade": "C",
        }
    )

    assert result["setup_score"] < 45
    assert result["setup_grade"] == "D"
    assert "one_candle_liquidity" in result["setup_tags"]
    assert result["setup_score_breakdown"]["liquidity_sweep"]["points"] == 0
