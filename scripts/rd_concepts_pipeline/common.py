from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
from typing import Any, Iterable, Iterator


TOKEN_RE = re.compile(
    r"([A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{20,}|token=)\S+"
)
FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")

TAG_PATTERNS: dict[str, tuple[str, ...]] = {
    "liquidity": ("liquidity", "liq", "sweep", "sweeps", "swept"),
    "sweep": ("sweep", "sweeps", "swept"),
    "bos": ("bos", "break of structure"),
    "choch": ("choch", "change of character"),
    "displacement": ("displacement", "impulse"),
    "imbalance": ("imbalance",),
    "fvg": ("fvg", "fair value gap"),
    "order_block": ("order block", "ob"),
    "ema": ("ema",),
    "fib": ("fib", "fibonacci"),
    "mechanical": ("mechanical",),
    "structure": ("structure",),
    "inducement": ("inducement",),
    "compression": ("compression",),
}


def _contains_phrase(text: str, phrase: str) -> bool:
    return bool(re.search(rf"(?<![A-Za-z0-9]){re.escape(phrase)}(?![A-Za-z0-9])", text))


def get_logger(name: str) -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    return logging.getLogger(name)


def redact(text: str) -> str:
    return TOKEN_RE.sub("[REDACTED]", text)


def safe_filename(value: str) -> str:
    cleaned = FILENAME_RE.sub("_", value).strip("._")
    return cleaned or "file"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def detect_session(timestamp: str) -> str:
    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    hour = parsed.astimezone(timezone.utc).hour
    if 0 <= hour < 7:
        return "asia"
    if 7 <= hour < 12:
        return "london"
    if 12 <= hour < 17:
        return "ny_overlap"
    if 17 <= hour < 22:
        return "new_york"
    return "off_session"


def extract_setup_tags(text: str) -> list[str]:
    lower = text.lower()
    tags = [
        tag
        for tag, patterns in TAG_PATTERNS.items()
        if any(_contains_phrase(lower, pattern) for pattern in patterns)
    ]
    return sorted(tags)
