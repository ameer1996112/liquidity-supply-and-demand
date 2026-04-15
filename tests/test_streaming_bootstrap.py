from src.services.streaming_bootstrap import ensure_streaming_for_profile


def test_ensure_streaming_for_profile_binance(monkeypatch):
    calls = []

    def _fake(api_key, supabase_client, account_name):
        calls.append((api_key, account_name))

    monkeypatch.setattr(
        "src.services.streaming_bootstrap.ensure_binance_streaming",
        _fake,
        raising=False,
    )

    ensure_streaming_for_profile({"venue": "binance", "api_key": "k", "name": "acc"}, supabase_client=None)
    assert calls == [("k", "acc")]


def test_ensure_streaming_for_profile_bybit(monkeypatch):
    calls = []

    def _fake(api_key, api_secret, supabase_client, account_name):
        calls.append((api_key, api_secret, account_name))

    monkeypatch.setattr(
        "src.services.streaming_bootstrap.ensure_bybit_streaming",
        _fake,
        raising=False,
    )

    ensure_streaming_for_profile({"venue": "bybit", "api_key": "k", "api_secret": "s", "name": "acc"}, supabase_client=None)
    assert calls == [("k", "s", "acc")]

