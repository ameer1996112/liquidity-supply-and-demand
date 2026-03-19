"""Feature engineering for ML: extract features from signal payload."""

import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional



# ── Session mapping: Pine Script session int → session name string ───────
_SESSION_INT_TO_NAME = {
    0: "Sydney",
    1: "Tokyo",
    2: "London",
    3: "New York",
}

# ── Side/entry-model → type mapping (matches training data) ─────────────
_SIDE_MODEL_TO_TYPE = {
    ("buy", "FLIP"): "flip",
    ("sell", "FLIP"): "flip",
    ("buy", "DIR_CLOSE"): "entry long",
    ("sell", "DIR_CLOSE"): "entry short",
    ("buy", "BREAK_CANDLE"): "boc",
    ("sell", "BREAK_CANDLE"): "boc",
}


def build_feature_frame(payload: Dict[str, Any], feature_names: list, encoders: Optional[Dict] = None) -> Dict[str, float]:
    """Build a feature dict with all keys in feature_names set to 0.0, then fill from payload.

    Improvements over v1:
      - Extracts hour, day_of_week from current UTC time
      - Encodes type_encoded from side + entry_model
      - Encodes session_encoded from Pine session int → session name
      - Encodes source_encoded (always "tradingview" for webhook alerts)
      - Maps liq_distance / f_liq_distance from liquidity_distance
      - Fixes signal_encoded fallback
    """
    features = {col: 0.0 for col in feature_names}
    encoders = encoders or {}

    # ── 1. Extract F:key=value pairs from signal string ──────────────
    signal_str = str(payload.get("signal", ""))
    matches = re.findall(r"F:([a-zA-Z_]+)=([0-9.\-]+)", signal_str)
    for key, val in matches:
        try:
            val_f = float(val)
            if key in features:
                features[key] = val_f
            if f"f_{key}" in features:
                features[f"f_{key}"] = val_f
        except ValueError:
            pass

    # ── 2. Also pull from top-level payload keys (direct JSON fields) ──
    _DIRECT_FIELDS = (
        "score", "freshness", "session", "atr_ratio", "trend", "rsi",
        "htf_trend", "rvol", "adx", "touch_count", "base_quality",
        "departure_strength", "liquidity_distance", "liquidity_spread",
        "return_strength", "zone_type", "is_accuracy",
    )
    for key in _DIRECT_FIELDS:
        val = payload.get(key)
        if val is not None:
            try:
                val_f = float(val) if not isinstance(val, bool) else (1.0 if val else 0.0)
                if key in features:
                    features[key] = val_f
                if f"f_{key}" in features and features[f"f_{key}"] == 0.0:
                    features[f"f_{key}"] = val_f
            except (ValueError, TypeError):
                pass

    # ── 3. Hour and day_of_week from current time ────────────────────
    now = datetime.now(timezone.utc)
    if "hour" in features:
        features["hour"] = float(now.hour)
    if "day_of_week" in features:
        features["day_of_week"] = float(now.weekday())  # 0=Monday, 6=Sunday

    # ── 4. type_encoded: encode side + entry_model ───────────────────
    if "type_encoded" in features:
        side = str(payload.get("side", "")).lower()
        entry_model = str(payload.get("entry_model", "")).upper()
        type_str = _SIDE_MODEL_TO_TYPE.get((side, entry_model), "default")

        type_enc = encoders.get("type")
        if type_enc is not None and type_str in type_enc.classes_:
            features["type_encoded"] = float(type_enc.transform([type_str])[0])

    # ── 5. session_encoded: Pine session int → encoded name ──────────
    session_int = payload.get("session")
    if session_int is None:
        # Try from F: extraction
        session_int = features.get("f_session")

    if session_int is not None:
        session_name = _SESSION_INT_TO_NAME.get(int(session_int), "unknown")
        session_enc = encoders.get("session")
        if session_enc is not None and session_name in session_enc.classes_:
            encoded_val = float(session_enc.transform([session_name])[0])
            if "session_encoded" in features:
                features["session_encoded"] = encoded_val
            if "f_session_encoded" in features:
                features["f_session_encoded"] = encoded_val

    # ── 6. source_encoded: always "tradingview" for webhook ──────────
    source_enc = encoders.get("source")
    if source_enc is not None and "tradingview" in source_enc.classes_:
        encoded_val = float(source_enc.transform(["tradingview"])[0])
        if "source_encoded" in features:
            features["source_encoded"] = encoded_val
        if "f_source_encoded" in features:
            features["f_source_encoded"] = encoded_val

    # ── 7. liquidity_distance → liq_distance mapping ────────────────
    liq_dist = features.get("f_liquidity_distance", 0.0)
    if "liq_distance" in features and features["liq_distance"] == 0.0:
        features["liq_distance"] = liq_dist
    if "f_liq_distance" in features and features["f_liq_distance"] == 0.0:
        features["f_liq_distance"] = liq_dist

    # ── 8. signal_encoded: use f_score as proxy ──────────────────────
    if features.get("signal_encoded", 0) == 0:
        features["signal_encoded"] = features.get("f_score", 0)
    if features.get("f_signal_encoded", 0) == 0:
        features["f_signal_encoded"] = features.get("f_score", 0)

    return features


def encode_asset_id(symbol: str, encoders: Dict) -> int | None:
    """Encode symbol to asset_id if encoders have the symbol encoder.

    Note: The training script stores the encoder under key 'symbol', not 'asset_id'.
    We check both keys for compatibility.
    """
    if not encoders:
        return None

    # The training script stores under "symbol", not "asset_id"
    encoder = encoders.get("symbol") or encoders.get("asset_id")
    if encoder is None:
        return None

    if symbol not in encoder.classes_:
        return None
    return encoder.transform([symbol])[0]
