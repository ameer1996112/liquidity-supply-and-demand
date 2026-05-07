from src.adapters import supabase as supabase_module


class _InsertRecorder:
    def __init__(self) -> None:
        self.payload = None

    def insert(self, payload):
        self.payload = payload
        return self

    def execute(self):
        return type("Response", (), {"data": [{"id": 123}]})()


class _Client:
    def __init__(self) -> None:
        self.recorder = _InsertRecorder()

    def table(self, name: str):
        assert name == "trading_signals"
        return self.recorder


def test_save_alert_persists_setup_evidence_without_image_url(monkeypatch) -> None:
    client = _Client()
    monkeypatch.setattr(supabase_module, "supabase", client)

    alert_id = supabase_module.save_alert(
        {
            "symbol": "VANTAGE:AUDUSD",
            "side": "BUY",
            "entry": 0.7156,
            "sl": 0.7148,
            "tp": 0.7172,
            "size": 0.25,
            "setup_evidence": {
                "status": "ok",
                "focus_zone": {"label": "Demand", "low": 0.7149, "high": 0.7153},
                "focus_image": {"url": "https://provider.example/setup.png"},
                "pine_snapshot": {"zone_count": 1, "label_count": 2, "top_labels": ["LONG"]},
                "reason": "",
            },
        }
    )

    assert alert_id == 123
    assert client.recorder.payload["setup_evidence"]["status"] == "ok"
    assert client.recorder.payload["setup_evidence"]["focus_image"] is None
    assert client.recorder.payload["image_url"] is None


def test_save_alert_persists_backend_setup_score(monkeypatch) -> None:
    client = _Client()
    monkeypatch.setattr(supabase_module, "supabase", client)

    supabase_module.save_alert(
        {
            "symbol": "VANTAGE:GBPJPY",
            "side": "SELL",
            "entry": 193.50,
            "sl": 193.58,
            "tp": 193.26,
            "size": 0.25,
            "setup_score": 87.5,
            "setup_grade": "A+",
            "setup_score_breakdown": {"liquidity_sweep": {"points": 15.0}},
            "setup_tags": ["multi_candle_liquidity", "grade_aplus"],
            "setup_score_version": "rd_setup_score_v2",
            "setup_asset_class": "jpy",
            "setup_sl_band": "jpy_3_7",
            "setup_strengths": ["liquidity_sweep"],
            "setup_weaknesses": ["flip_entry_model"],
        }
    )

    assert client.recorder.payload["setup_score"] == 87.5
    assert client.recorder.payload["setup_grade"] == "A+"
    assert client.recorder.payload["setup_score_breakdown"]["liquidity_sweep"]["points"] == 15.0
    assert client.recorder.payload["setup_tags"] == ["multi_candle_liquidity", "grade_aplus"]
    assert client.recorder.payload["setup_score_version"] == "rd_setup_score_v2"
    assert client.recorder.payload["setup_asset_class"] == "jpy"
    assert client.recorder.payload["setup_sl_band"] == "jpy_3_7"
    assert client.recorder.payload["setup_strengths"] == ["liquidity_sweep"]
    assert client.recorder.payload["setup_weaknesses"] == ["flip_entry_model"]
