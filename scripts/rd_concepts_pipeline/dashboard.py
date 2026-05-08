from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.rd_concepts_pipeline.config import get_settings

LOGGER = logging.getLogger(__name__)
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
FILE_SUFFIXES = {".csv", ".doc", ".docx", ".pdf", ".ppt", ".pptx", ".txt", ".xls", ".xlsm", ".xlsx"}
DEFAULT_TABLE_ROWS = 250


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (
        pd.errors.EmptyDataError,
        pd.errors.ParserError,
        UnicodeDecodeError,
        OSError,
    ) as exc:
        LOGGER.warning("Could not read RD Concepts CSV %s: %s", path, exc)
        return pd.DataFrame()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
        LOGGER.warning("Could not read RD Concepts JSON %s: %s", path, exc)
        return {}
    if not isinstance(data, dict):
        LOGGER.warning("Ignoring RD Concepts JSON %s because it is not an object", path)
        return {}
    return data


def _read_rules_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    rules: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    row = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    LOGGER.warning(
                        "Could not read RD Concepts JSONL %s line %s: %s",
                        path,
                        line_number,
                        exc,
                    )
                    return []
                if not isinstance(row, dict):
                    LOGGER.warning(
                        "Ignoring RD Concepts JSONL %s line %s because it is not an object",
                        path,
                        line_number,
                    )
                    return []
                rules.append(row)
    except (UnicodeDecodeError, OSError) as exc:
        LOGGER.warning("Could not read RD Concepts JSONL %s: %s", path, exc)
        return []
    return rules


def load_processed_data(
    data_dir: Path,
) -> tuple[pd.DataFrame, list[dict[str, Any]], dict[str, Any], pd.DataFrame]:
    processed_dir = data_dir / "processed"
    signals = _read_csv(processed_dir / "signals.csv")
    image_index = _read_csv(processed_dir / "image_index.csv")
    rules = _read_rules_jsonl(processed_dir / "rules.jsonl")
    knowledge_base = _read_json(processed_dir / "knowledge_base.json")
    return signals, rules, knowledge_base, image_index


def load_file_artifacts(data_dir: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    raw_dir = data_dir / "raw"
    if not raw_dir.exists():
        return pd.DataFrame(columns=["channel", "file_path", "name", "suffix", "size_mb"])

    for path in sorted(raw_dir.glob("*/files/*")):
        if not path.is_file() or path.suffix.lower() not in FILE_SUFFIXES:
            continue
        try:
            size_mb = round(path.stat().st_size / (1024 * 1024), 2)
        except OSError:
            size_mb = 0.0
        rows.append(
            {
                "channel": path.parent.parent.name,
                "file_path": str(path),
                "name": path.name,
                "suffix": path.suffix.lower(),
                "size_mb": size_mb,
            }
        )
    return pd.DataFrame(rows)


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


def _non_blank_frame(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    if frame.empty or column not in frame.columns:
        return frame.iloc[0:0].copy()
    values = frame[column].fillna("").astype(str).str.strip()
    return frame[values.ne("") & values.ne("unknown")]


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


def _rules_frame(rules: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for rule in rules:
        content = str(rule.get("content", ""))
        rows.append(
            {
                "timestamp": rule.get("timestamp", ""),
                "channel": rule.get("channel", ""),
                "author": rule.get("author", ""),
                "concept_tags": ", ".join(rule.get("concept_tags") or []),
                "keyword_hits": ", ".join(rule.get("keyword_hits") or []),
                "content": content[:500],
                "message_url": rule.get("message_url", ""),
            }
        )
    return pd.DataFrame(rows)


def _is_complete_signal_frame(frame: pd.DataFrame) -> pd.Series:
    if frame.empty:
        return pd.Series(dtype=bool)
    mask = pd.Series(True, index=frame.index)
    for column in ("pair", "direction", "entry", "stop_loss", "take_profit"):
        if column not in frame.columns:
            return pd.Series(False, index=frame.index)
        values = frame[column].fillna("").astype(str).str.strip()
        mask &= values.ne("") & values.ne("None") & values.ne("nan")
    return mask


def _safe_image_path(raw_path: Any, data_dir: Path) -> Path | None:
    if raw_path is None:
        return None
    try:
        if bool(pd.isna(raw_path)):
            return None
    except (TypeError, ValueError):
        return None

    path_text = str(raw_path).strip()
    if not path_text:
        return None

    candidate = Path(path_text)
    if candidate.suffix.lower() not in IMAGE_SUFFIXES:
        return None

    data_root = data_dir.resolve()
    resolved = (
        candidate.resolve()
        if candidate.is_absolute()
        else (data_root / candidate).resolve()
    )

    try:
        resolved.relative_to(data_root)
    except ValueError:
        return None

    return resolved


def _knowledge_base_pair_count(knowledge_base: dict[str, Any]) -> int:
    pairs = knowledge_base.get("pairs")
    return len(pairs) if isinstance(pairs, dict) else 0


def main() -> None:
    import streamlit as st

    @st.cache_data
    def load_cached_processed_data(
        data_dir_text: str,
    ) -> tuple[pd.DataFrame, list[dict[str, Any]], dict[str, Any], pd.DataFrame, pd.DataFrame]:
        data_dir = Path(data_dir_text)
        signals, rules, knowledge_base, image_index = load_processed_data(data_dir)
        files = load_file_artifacts(data_dir)
        return signals, rules, knowledge_base, image_index, files

    settings = get_settings()
    signals, rules, knowledge_base, image_index, files = load_cached_processed_data(
        str(settings.data_dir)
    )
    pair_count = _knowledge_base_pair_count(knowledge_base)

    st.set_page_config(page_title="RD Concepts Data Lake", layout="wide")

    st.title("RD Concepts Evidence Lake")
    st.caption(f"Data directory: {settings.data_dir} | Knowledge-base pairs: {pair_count}")

    metric_cols = st.columns(5)
    metric_cols[0].metric("Parsed rows", f"{len(signals):,}")
    metric_cols[1].metric("Complete signals", f"{int(_is_complete_signal_frame(signals).sum()):,}")
    metric_cols[2].metric("Rules", f"{len(rules):,}")
    metric_cols[3].metric("Images", f"{len(image_index):,}")
    metric_cols[4].metric("Files", f"{len(files):,}")

    overview_tab, signals_tab, rules_tab, files_tab, images_tab = st.tabs(
        ["Overview", "Signals", "Rules", "Files", "Images"]
    )

    with overview_tab:
        include_unknown_pairs = st.checkbox("Include unknown pairs in pair chart", value=False)
        chart_signals = signals if include_unknown_pairs else _non_blank_frame(signals, "pair")
        channel_counts = _count_by_column(signals, "channel")
        pair_counts = _count_by_column(chart_signals, "pair")

        chart_col, pair_col = st.columns(2)
        with chart_col:
            st.subheader("Rows by Channel")
            if channel_counts.empty:
                st.info("No channel data found.")
            else:
                st.bar_chart(channel_counts.head(30), x="channel", y="count")

        with pair_col:
            st.subheader("Pair Breakdown")
            if pair_counts.empty:
                st.info("No pair data found.")
            else:
                st.bar_chart(pair_counts.head(30), x="pair", y="count")

        if not files.empty:
            st.subheader("Downloaded Files by Channel")
            st.bar_chart(_count_by_column(files, "channel").head(30), x="channel", y="count")

    with signals_tab:
        st.subheader("Signals")
        only_complete = st.checkbox("Show only complete trade signals", value=True)
        filtered_signals = signals[_is_complete_signal_frame(signals)].copy() if only_complete else signals.copy()

        filter_cols = st.columns(5)
        with filter_cols[0]:
            selected_pairs = st.multiselect(
                "Pair",
                _sorted_options(filtered_signals, "pair"),
                default=[],
            )
        with filter_cols[1]:
            selected_directions = st.multiselect(
                "Direction",
                _sorted_options(filtered_signals, "direction"),
                default=[],
            )
        with filter_cols[2]:
            selected_channels = st.multiselect(
                "Channel",
                _sorted_options(filtered_signals, "channel"),
                default=[],
            )
        with filter_cols[3]:
            max_rows = st.number_input(
                "Rows",
                min_value=50,
                max_value=5000,
                value=DEFAULT_TABLE_ROWS,
                step=50,
            )
        with filter_cols[4]:
            timestamps = _timestamp_series(filtered_signals).dropna()
            date_range = None
            if timestamps.empty:
                st.text_input("Date", value="No dated rows", disabled=True)
            else:
                date_range = st.date_input(
                    "Date",
                    value=(timestamps.min().date(), timestamps.max().date()),
                )

        filtered_signals = _filter_by_values(filtered_signals, "pair", selected_pairs)
        filtered_signals = _filter_by_values(filtered_signals, "direction", selected_directions)
        filtered_signals = _filter_by_values(filtered_signals, "channel", selected_channels)
        filtered_signals = _filter_by_date(filtered_signals, date_range)

        st.caption(f"Showing {min(len(filtered_signals), int(max_rows)):,} of {len(filtered_signals):,} rows")
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
                (filtered_signals[preferred_columns] if preferred_columns else filtered_signals).head(int(max_rows)),
                use_container_width=True,
                hide_index=True,
            )

    with rules_tab:
        st.subheader("Strategy Rules And Education")
        query = st.text_input("Search rules/content")
        matched_rules = _filter_rules(rules, query)
        rules_frame = _rules_frame(matched_rules)
        max_rules = st.number_input(
            "Rule rows",
            min_value=50,
            max_value=5000,
            value=DEFAULT_TABLE_ROWS,
            step=50,
        )
        st.caption(f"Showing {min(len(rules_frame), int(max_rules)):,} of {len(rules_frame):,} matched rules")
        if rules_frame.empty:
            st.info("No rules found.")
        else:
            st.dataframe(rules_frame.head(int(max_rules)), use_container_width=True, hide_index=True)

    with files_tab:
        st.subheader("Downloaded Spreadsheets And Docs")
        if files.empty:
            st.info("No downloaded document/spreadsheet files found.")
        else:
            file_cols = st.columns(4)
            with file_cols[0]:
                file_channels = st.multiselect("File channel", _sorted_options(files, "channel"), default=[])
            with file_cols[1]:
                file_suffixes = st.multiselect("Type", _sorted_options(files, "suffix"), default=[])
            with file_cols[2]:
                min_size = st.number_input("Min MB", min_value=0.0, value=0.0, step=1.0)
            with file_cols[3]:
                max_files = st.number_input("File rows", min_value=25, max_value=2000, value=250, step=25)
            filtered_files = _filter_by_values(files.copy(), "channel", file_channels)
            filtered_files = _filter_by_values(filtered_files, "suffix", file_suffixes)
            if "size_mb" in filtered_files.columns:
                filtered_files = filtered_files[filtered_files["size_mb"] >= min_size]
            st.caption(f"Showing {min(len(filtered_files), int(max_files)):,} of {len(filtered_files):,} files")
            st.dataframe(
                filtered_files.sort_values("size_mb", ascending=False).head(int(max_files)),
                use_container_width=True,
                hide_index=True,
            )

    with images_tab:
        st.subheader("Chart Images")
        if image_index.empty:
            st.info("No chart images found.")
        else:
            image_filter_cols = st.columns(4)
            with image_filter_cols[0]:
                image_pairs = st.multiselect("Image pair", _sorted_options(image_index, "pair"), default=[])
            with image_filter_cols[1]:
                image_channels = st.multiselect("Image channel", _sorted_options(image_index, "channel"), default=[])
            with image_filter_cols[2]:
                max_images = st.number_input("Image rows", min_value=25, max_value=1000, value=100, step=25)
            with image_filter_cols[3]:
                render_images = st.checkbox("Render thumbnails", value=False)

            filtered_images = _filter_by_values(image_index.copy(), "pair", image_pairs)
            filtered_images = _filter_by_values(filtered_images, "channel", image_channels)

            st.caption(f"Showing {min(len(filtered_images), int(max_images)):,} of {len(filtered_images):,} images")
            st.dataframe(filtered_images.head(int(max_images)), use_container_width=True, hide_index=True)
            if render_images and "image_path" in filtered_images.columns:
                for _, row in filtered_images.head(min(int(max_images), 24)).iterrows():
                    raw_path = row["image_path"]
                    path = _safe_image_path(raw_path, settings.data_dir)
                    label_parts = [
                        str(row[column])
                        for column in ("timestamp", "channel", "pair", "direction")
                        if column in row.index
                        and pd.notna(row[column])
                        and str(row[column])
                    ]
                    st.caption(" | ".join(label_parts) or str(raw_path))
                    if path is None:
                        st.code(str(raw_path))
                    elif path.exists():
                        try:
                            st.image(str(path), use_container_width=True)
                        except Exception as exc:  # pragma: no cover - Streamlit UI guard
                            LOGGER.warning("Could not render image %s: %s", path, exc)
                            st.code(str(raw_path))
                    else:
                        st.code(str(raw_path))


if __name__ == "__main__":
    main()
