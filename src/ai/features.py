"""Feature engineering for ML: extract features from signal payload."""

import re
from typing import Any, Dict

import pandas as pd


def build_feature_frame(payload: Dict[str, Any], feature_names: list) -> Dict[str, float]:
    """Build a feature dict with all keys in feature_names set to 0.0, then fill from payload."""
    features = {col: 0.0 for col in feature_names}
    signal_str = str(payload.get("signal", ""))
    matches = re.findall(r"F:([a-zA-Z_]+)=([0-9.]+)", signal_str)
    for key, val in matches:
        try:
            val_f = float(val)
            if key in features:
                features[key] = val_f
            if f"f_{key}" in features:
                features[f"f_{key}"] = val_f
        except ValueError:
            pass
    if features.get("signal_encoded", 0) == 0:
        features["signal_encoded"] = features.get("score", 0)
    if features.get("f_signal_encoded", 0) == 0:
        features["f_signal_encoded"] = features.get("f_score", 0)
    return features


def encode_asset_id(symbol: str, encoders: Dict) -> int | None:
    """Encode symbol to asset_id if encoders have asset_id. Returns None if not found."""
    if not encoders or "asset_id" not in encoders:
        return None
    if symbol not in encoders["asset_id"].classes_:
        return None
    return encoders["asset_id"].transform([symbol])[0]
