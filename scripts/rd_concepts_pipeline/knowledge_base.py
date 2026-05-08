from __future__ import annotations

import argparse
import ast
from collections import Counter
import json
from typing import Any

import pandas as pd

from scripts.rd_concepts_pipeline.common import ensure_dir, get_logger, read_jsonl
from scripts.rd_concepts_pipeline.config import get_settings

LOGGER = get_logger("rd_concepts.knowledge_base")


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    try:
        result = pd.isna(value)
    except (TypeError, ValueError):
        return False
    if result is pd.NA:
        return True
    try:
        return bool(result)
    except (TypeError, ValueError):
        return False


def _json_value(value: Any) -> Any:
    if _is_blank(value):
        return ""
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _as_list(value: Any) -> list[Any]:
    if _is_blank(value):
        return []
    if isinstance(value, list):
        return [_json_value(item) for item in value if not _is_blank(item)]
    if isinstance(value, (tuple, set)):
        return [_json_value(item) for item in value if not _is_blank(item)]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            parsed = ast.literal_eval(stripped)
        except (SyntaxError, ValueError):
            if "," in stripped:
                return [part.strip() for part in stripped.split(",") if part.strip()]
            return [stripped]
        if isinstance(parsed, (list, tuple, set)):
            return [_json_value(item) for item in parsed if not _is_blank(item)]
        if _is_blank(parsed):
            return []
        return [_json_value(parsed)]
    return [_json_value(value)]


def _column_value(row: pd.Series, column: str) -> Any:
    if column not in row.index:
        return ""
    return row[column]


def _clean_text(value: Any) -> str:
    if _is_blank(value):
        return ""
    return str(_json_value(value)).strip()


def _direction_value(row: pd.Series) -> str:
    direction = _clean_text(_column_value(row, "direction"))
    if direction:
        return direction
    return _clean_text(_column_value(row, "side"))


def _sorted_strings(values: list[Any]) -> list[str]:
    return sorted({str(value) for value in values if not _is_blank(value)})


def build_knowledge_base(
    signals: pd.DataFrame,
    rules: list[dict[str, Any]],
    concepts: dict[str, Any],
) -> dict[str, Any]:
    pair_rows: dict[str, list[pd.Series]] = {}
    timeframe_counts: Counter[str] = Counter()
    channel_counts: Counter[str] = Counter()

    for _, row in signals.iterrows():
        pair = _clean_text(_column_value(row, "pair"))
        timeframe = _clean_text(_column_value(row, "timeframe"))
        channel = _clean_text(_column_value(row, "channel"))

        if pair:
            pair_rows.setdefault(pair, []).append(row)
        if timeframe:
            timeframe_counts[timeframe] += 1
        if channel:
            channel_counts[channel] += 1

    pairs: dict[str, dict[str, Any]] = {}
    for pair, rows in sorted(pair_rows.items()):
        total = len(rows)
        long_count = sum(1 for row in rows if _direction_value(row).lower() == "long")
        short_count = sum(1 for row in rows if _direction_value(row).lower() == "short")
        channels: list[Any] = []
        sessions: list[Any] = []
        setup_tags: list[Any] = []
        chart_paths: list[Any] = []

        for row in rows:
            channels.append(_column_value(row, "channel"))
            sessions.append(_column_value(row, "session"))
            setup_tags.extend(_as_list(_column_value(row, "setup_tags")))
            chart_paths.extend(_as_list(_column_value(row, "chart_paths")))

        pairs[pair] = {
            "total_signals": total,
            "long_percent": round((long_count / total) * 100, 2) if total else 0.0,
            "short_percent": round((short_count / total) * 100, 2) if total else 0.0,
            "channels_active": _sorted_strings(channels),
            "sessions": _sorted_strings(sessions),
            "setup_tags": _sorted_strings(setup_tags),
            "chart_paths": _sorted_strings(chart_paths),
        }

    return {
        "pairs": pairs,
        "timeframes": dict(sorted(timeframe_counts.items())),
        "channels": dict(sorted(channel_counts.items())),
        "rules_total": int(len(rules)),
        "concepts": concepts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build RD Concepts dashboard knowledge base.")
    parser.parse_args()

    settings = get_settings()
    processed_dir = ensure_dir(settings.data_dir / "processed")
    signals_path = processed_dir / "signals.csv"
    rules_path = processed_dir / "rules.jsonl"
    concepts_path = processed_dir / "concepts.json"
    output_path = processed_dir / "knowledge_base.json"

    signals = pd.read_csv(signals_path) if signals_path.exists() else pd.DataFrame()
    rules = list(read_jsonl(rules_path))
    concepts = json.loads(concepts_path.read_text(encoding="utf-8")) if concepts_path.exists() else {}
    knowledge_base = build_knowledge_base(signals, rules, concepts)

    output_path.write_text(
        json.dumps(knowledge_base, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    LOGGER.info("Wrote knowledge base to %s", output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
