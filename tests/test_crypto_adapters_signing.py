import hashlib
import hmac
from urllib.parse import urlencode

from src.adapters.execution.binance_adapter import _sign_query
from src.adapters.execution.bybit_adapter import _bybit_sign


def test_binance_sign_query_matches_hmac_sha256():
    secret = "testsecret"
    params = {"symbol": "BTCUSDT", "timestamp": 1700000000000}
    query = urlencode(params)
    expected = hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()
    assert _sign_query(secret, query) == expected


def test_bybit_signature_is_hmac_sha256_hex():
    secret = "testsecret"
    payload = "1700000000000testkey5000{\"foo\":\"bar\"}"
    sig = _bybit_sign(secret, payload)
    assert isinstance(sig, str)
    assert len(sig) == 64

