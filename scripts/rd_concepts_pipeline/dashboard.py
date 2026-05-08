from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.rd_concepts_pipeline.common import read_jsonl
from scripts.rd_concepts_pipeline.config import get_settings


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def load_processed_data(
    data_dir: Path,
) -> tuple[pd.DataFrame, list[dict[str, Any]], dict[str, Any], pd.DataFrame]:
    processed_dir = data_dir / "processed"
    signals = _read_csv(processed_dir / "signals.csv")
    image_index = _read_csv(processed_dir / "image_index.csv")
    rules = list(read_jsonl(processed_dir / "rules.jsonl"))
    knowledge_base = _read_json(processed_dir / "knowledge_base.json")
    return signals, rules, knowledge_base, image_index


def _count_by_column(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    if frame.empty or column not in frame.columns:
        return pd.DataFrame(columns=[column, "count"])
    counts = (
        frame[column]
        .fillna("")
        .astype(str)
        .str.strip()
        .replace("", "unknown")
        .value_counts()
        .rename_axis(column)
        .reset_index(name="count")
    )
    return counts


def _sorted_options(frame: pd.DataFrame, column: str) -> list[str]:
    if frame.empty or column not in frame.columns:
        return []
    values = frame[column].dropna().astype(str).str.strip()
    return sorted(value for value in values.unique() if value)


def _filter_by_values(
    frame: pd.DataFrame,
    column: str,
    selected: list[str],
) -> pd.DataFrame:
    if not selected or column not in frame.columns:
        return frame
    return frame[frame[column].fillna("").astype(str).isin(selected)]


def _timestamp_series(frame: pd.DataFrame) -> pd.Series:
    if "timestamp" not in frame.columns:
        return pd.Series(dtype="datetime64[ns, UTC]")
    return pd.to_datetime(frame["timestamp"], errors="coerce", utc=True)


def _filter_by_date(frame: pd.DataFrame, date_range: Any) -> pd.DataFrame:
    timestamps = _timestamp_series(frame)
    if frame.empty or timestamps.empty or not date_range:
        return frame

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start, end = date_range
    else:
        return frame

    if start is None or end is None:
        return frame

    start_ts = pd.Timestamp(start).tz_localize("UTC")
    end_ts = pd.Timestamp(end).tz_localize("UTC") + pd.Timedelta(days=1)
    return frame[(timestamps >= start_ts) & (timestamps < end_ts)]


def _filter_rules(rules: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    if not query.strip():
        return rules
    lower_query = query.lower()
    return [
        rule
        for rule in rules
        if lower_query in json.dumps(rule, default=str, sort_keys=True).lower()
    ]


def _image_path(data_dir: Path, value: Any) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else data_dir / path


def main() -> None:
    import streamlit as st

    settings = get_settings()
    signals, rules, knowledge_base, image_index = load_processed_data(settings.data_dir)
    pair_count = len((knowledge_base.get("pairs") or {}))

    st.set_page_config(page_title="RD Concepts Data Lake", layout="wide")

    st.title("RD Concepts Data Lake")
    st.caption(
        "Offline research dashboard. "
        f"Knowledge base covers {pair_count} pairs."
    )
    st.caption(
        f"Data directory: {settings.data_dir} | Knowledge-base pairs: {pair_count}"
    )

    channel_counts = _count_by_column(signals, "channel")
    pair_counts = _count_by_column(signals, "pair")

    chart_col, pair_col = st.columns(2)
    with chart_col:
        st.subheader("Signals by Channel")
        if channel_counts.empty:
            st.info("No signal channel data found.")
        else:
            st.bar_chart(channel_counts, x="channel", y="count")

    with pair_col:
        st.subheader("Pair Breakdown")
        if pair_counts.empty:
            st.info("No pair data found.")
        else:
            st.bar_chart(pair_counts, x="pair", y="count")

    st.subheader("Signals")
    filtered_signals = signals.copy()

    filter_cols = st.columns(4)
    with filter_cols[0]:
        selected_pairs = st.multiselect(
            "Pair",
            _sorted_options(signals, "pair"),
            default=[],
        )
    with filter_cols[1]:
        selected_directions = st.multiselect(
            "Direction",
            _sorted_options(signals, "direction"),
            default=[],
        )
    with filter_cols[2]:
        selected_channels = st.multiselect(
            "Channel",
            _sorted_options(signals, "channel"),
            default=[],
        )
    with filter_cols[3]:
        timestamps = _timestamp_series(signals).dropna()
        date_range = None
        if timestamps.empty:
            st.text_input("Date", value="No dated rows", disabled=True)
        else:
            date_range = st.date_input(
                "Date",
                value=(timestamps.min().date(), timestamps.max().date()),
            )

    filtered_signals = _filter_by_values(filtered_signals, "pair", selected_pairs)
    filtered_signals = _filter_by_values(
        filtered_signals,
        "direction",
        selected_directions,
    )
    filtered_signals = _filter_by_values(filtered_signals, "channel", selected_channels)
    filtered_signals = _filter_by_date(filtered_signals, date_range)

    if filtered_signals.empty:
        st.info("No signals match the current filters.")
    else:
        preferred_columns = [
            column
            for column in (
                "timestamp",
                "channel",
                "pair",
                "direction",
                "timeframe",
                "entry",
                "stop_loss",
                "take_profit",
                "rr_ratio",
                "setup_tags",
                "message_url",
            )
            if column in filtered_signals.columns
        ]
        st.dataframe(
            filtered_signals[preferred_columns] if preferred_columns else filtered_signals,
            use_container_width=True,
            hide_index=True,
        )

    rules_tab, images_tab = st.tabs(["Strategy Rules", "Chart Images"])

    with rules_tab:
        query = st.text_input("Search rules")
        matched_rules = _filter_rules(rules, query)
        st.caption(f"{len(matched_rules)} of {len(rules)} rules")
        if not matched_rules:
            st.info("No rules found.")
        else:
            for index, rule in enumerate(matched_rules, start=1):
                title = str(
                    rule.get("title")
                    or rule.get("concept")
                    or rule.get("rule")
                    or f"Rule {index}"
                )
                with st.expander(title):
                    st.json(rule)

    with images_tab:
        if image_index.empty:
            st.info("No chart images found.")
        else:
            image_filter_cols = st.columns(2)
            with image_filter_cols[0]:
                image_pairs = st.multiselect(
                    "Image pair",
                    _sorted_options(image_index, "pair"),
                    default=[],
                )
            with image_filter_cols[1]:
                image_channels = st.multiselect(
                    "Image channel",
                    _sorted_options(image_index, "channel"),
                    default=[],
                )

            filtered_images = _filter_by_values(image_index.copy(), "pair", image_pairs)
            filtered_images = _filter_by_values(
                filtered_images,
                "channel",
                image_channels,
            )

            st.dataframe(filtered_images, use_container_width=True, hide_index=True)
            if "image_path" in filtered_images.columns:
                for _, row in filtered_images.head(50).iterrows():
                    path = _image_path(settings.data_dir, row["image_path"])
                    label_parts = [
                        str(row[column])
                        for column in ("timestamp", "channel", "pair", "direction")
                        if column in row.index
                        and pd.notna(row[column])
                        and str(row[column])
                    ]
                    st.caption(" | ".join(label_parts) or str(row["image_path"]))
                    if path.exists():
                        st.image(str(path), use_container_width=True)
                    else:
                        st.code(str(row["image_path"]))


if __name__ == "__main__":
    main()
