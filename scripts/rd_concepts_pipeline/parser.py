from __future__ import annotations

import argparse
import csv
from pathlib import Path
import re
from typing import Any

from scripts.rd_concepts_pipeline.common import (
    detect_session,
    ensure_dir,
    extract_setup_tags,
    get_logger,
    read_jsonl,
)
from scripts.rd_concepts_pipeline.config import get_settings


LOGGER = get_logger("rd_concepts.parser")

SIGNAL_COLUMNS = [
    "signal_id",
    "message_id",
    "timestamp",
    "channel",
    "pair",
    "direction",
    "timeframe",
    "entry",
    "stop_loss",
    "take_profit",
    "rr_ratio",
    "setup_notes",
    "setup_tags",
    "confluence_tags",
    "session",
    "has_chart",
    "chart_paths",
    "quality_flags",
    "raw_message",
    "message_url",
]
IMAGE_INDEX_COLUMNS = [
    "message_id",
    "timestamp",
    "channel",
    "image_path",
    "pair",
    "direction",
    "setup_tags",
]

PAIRS = {
    "EURUSD",
    "GBPUSD",
    "AUDUSD",
    "NZDUSD",
    "USDJPY",
    "EURJPY",
    "GBPJPY",
    "NZDJPY",
    "AUDJPY",
    "USDCAD",
    "USDCHF",
    "XAUUSD",
    "XAGUSD",
    "GOLD",
    "NAS100",
    "US100",
    "SPX500",
    "US30",
}
PAIR_PATTERN = "|".join(sorted(PAIRS, key=len, reverse=True))

PAIR_RE = re.compile(rf"\b({PAIR_PATTERN})\b", re.IGNORECASE)
DIRECTION_RE = re.compile(r"\b(LONG|SHORT|BUY|SELL|BULLISH|BEARISH)\b", re.IGNORECASE)
TIMEFRAME_RE = re.compile(r"\b(5m|15m|30m|1h|4h|daily)\b", re.IGNORECASE)
PRICE_RE = r"\d+(?:\.\d+)?"

PATTERN_A = re.compile(
    rf"\b(?P<pair>{PAIR_PATTERN})\b\s+"
    r"(?P<direction>LONG|SHORT)\b"
    rf".*?\bentry\s*:?\s*(?P<entry>{PRICE_RE})"
    rf".*?\bSL\s*:?\s*(?P<sl>{PRICE_RE})"
    rf".*?\bTP\s*:?\s*(?P<tp>{PRICE_RE})",
    re.IGNORECASE | re.DOTALL,
)
PATTERN_B = re.compile(
    rf"\b(?P<pair>{PAIR_PATTERN})\b\s+"
    r"(?P<direction>BUY|SELL)\b"
    rf"\s*@\s*(?P<entry>{PRICE_RE})"
    rf".*?\bStop\s+(?P<sl>{PRICE_RE})"
    rf".*?\bTarget\s+(?P<tp>{PRICE_RE})",
    re.IGNORECASE | re.DOTALL,
)


def normalize_pair(pair: str | None) -> str:
    if not pair:
        return ""
    upper = pair.upper()
    if upper == "GOLD":
        return "XAUUSD"
    return upper if upper in PAIRS else ""


def normalize_direction(direction: str | None) -> str:
    value = (direction or "").upper()
    if value in {"LONG", "BUY", "BULLISH"}:
        return "long"
    if value in {"SHORT", "SELL", "BEARISH"}:
        return "short"
    return ""


def compute_rr(
    entry: float | None,
    stop_loss: float | None,
    take_profit: float | None,
) -> float | None:
    if entry is None or stop_loss is None or take_profit is None:
        return None
    risk = abs(entry - stop_loss)
    if risk == 0:
        return None
    reward = abs(take_profit - entry)
    return round(reward / risk, 2)


def _first_group(pattern: re.Pattern[str], text: str, group: int | str = 1) -> str:
    match = pattern.search(text)
    if not match:
        return ""
    return match.group(group)


def _float_group(match: re.Match[str] | None, group: str) -> float | None:
    if not match:
        return None
    return float(match.group(group))


def parse_message(row: dict[str, Any]) -> dict[str, Any]:
    content = str(row.get("content") or "")
    match = PATTERN_A.search(content) or PATTERN_B.search(content)

    pair = normalize_pair(
        match.group("pair") if match else _first_group(PAIR_RE, content)
    )
    direction = normalize_direction(
        match.group("direction") if match else _first_group(DIRECTION_RE, content)
    )
    entry = _float_group(match, "entry")
    stop_loss = _float_group(match, "sl")
    take_profit = _float_group(match, "tp")
    timeframe = _first_group(TIMEFRAME_RE, content).lower()
    images = list(row.get("images") or [])

    quality_flags: list[str] = []
    if not match:
        quality_flags.append("loose_match")
    if entry is None or stop_loss is None or take_profit is None:
        quality_flags.append("missing_levels")
    if images:
        quality_flags.append("chart_backed")

    timestamp = str(row.get("timestamp") or "")
    setup_tags = extract_setup_tags(content)

    return {
        "signal_id": f"{row.get('channel', '')}:{row.get('id', '')}",
        "message_id": row.get("id", ""),
        "timestamp": timestamp,
        "channel": row.get("channel", ""),
        "pair": pair,
        "direction": direction,
        "timeframe": timeframe,
        "entry": entry,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "rr_ratio": compute_rr(entry, stop_loss, take_profit),
        "setup_notes": content[:500],
        "setup_tags": setup_tags,
        "confluence_tags": setup_tags,
        "session": detect_session(timestamp) if timestamp else "",
        "has_chart": bool(images),
        "chart_paths": images,
        "quality_flags": quality_flags,
        "raw_message": content,
        "message_url": row.get("message_url", ""),
    }


def parse_raw_files(
    paths: list[Path],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    signals: list[dict[str, Any]] = []
    image_index: list[dict[str, Any]] = []

    for path in paths:
        for row in read_jsonl(path):
            parsed = parse_message(row)
            if parsed["pair"] or parsed["setup_tags"]:
                signals.append(parsed)

            for image_path in row.get("images") or []:
                image_index.append(
                    {
                        "message_id": row.get("id", ""),
                        "timestamp": row.get("timestamp", ""),
                        "channel": row.get("channel", ""),
                        "image_path": image_path,
                        "pair": parsed["pair"],
                        "direction": parsed["direction"],
                        "setup_tags": parsed["setup_tags"],
                    }
                )

    return signals, image_index


def write_outputs(
    signals: list[dict[str, Any]],
    image_index: list[dict[str, Any]],
    processed_dir: Path,
) -> None:
    import pandas as pd

    output_dir = ensure_dir(processed_dir)
    pd.DataFrame(signals, columns=SIGNAL_COLUMNS).to_csv(
        output_dir / "signals.csv",
        index=False,
        quoting=csv.QUOTE_MINIMAL,
    )
    pd.DataFrame(image_index, columns=IMAGE_INDEX_COLUMNS).to_csv(
        output_dir / "image_index.csv",
        index=False,
        quoting=csv.QUOTE_MINIMAL,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Parse RD Concepts raw messages into signal and image indexes."
    )
    parser.parse_args()

    settings = get_settings()
    raw_paths = sorted((settings.data_dir / "raw").glob("*/messages.jsonl"))
    signals, image_index = parse_raw_files(raw_paths)

    write_outputs(signals, image_index, settings.data_dir / "processed")
    LOGGER.info("Parsed %s signals and %s images", len(signals), len(image_index))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
