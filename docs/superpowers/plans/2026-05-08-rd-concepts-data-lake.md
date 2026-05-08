# RD Concepts Data Lake Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an offline RD Concepts Discord research data lake that archives messages/images, extracts setup and rule records, and exposes the data through files plus a local dashboard.

**Architecture:** Add an isolated utility package under `scripts/rd_concepts_pipeline/` and write generated data to `data/rd_concepts/`. Keep Discord access, parsing, rules extraction, knowledge-base aggregation, and dashboard browsing as separate standalone scripts that share only config and small file/logging helpers. Do not import live trading worker, broker, risk, or execution modules.

**Tech Stack:** Python 3.11+, requests, pandas, streamlit, plotly, pytest fixtures, JSONL/CSV/JSON outputs, pathlib, re, logging.

---

## Scope Check

This plan implements the first offline research data lake. It does not modify PineScript, execute trades, call MetaApi, rank profitability, or clone TradingView strategy behavior. PineScript tuning comes after this data lake can produce clean evidence files.

## File Structure

- Create `scripts/rd_concepts_pipeline/__init__.py`: marks the utility package.
- Create `scripts/rd_concepts_pipeline/config.py`: environment-backed settings, channel map, local `.env` loading, incomplete channel filtering.
- Create `scripts/rd_concepts_pipeline/common.py`: shared logging, JSONL helpers, redaction, safe filenames, pair/session/tag helpers.
- Create `scripts/rd_concepts_pipeline/list_channels.py`: Discord guild channel discovery helper.
- Create `scripts/rd_concepts_pipeline/scraper.py`: Discord pagination, rate-limit handling, image download, manifests, raw JSONL output.
- Create `scripts/rd_concepts_pipeline/parser.py`: signal/setup parser and image index builder.
- Create `scripts/rd_concepts_pipeline/rules_extractor.py`: educational/rule message extractor and concept frequency builder.
- Create `scripts/rd_concepts_pipeline/knowledge_base.py`: combines processed files into dashboard-ready summaries.
- Create `scripts/rd_concepts_pipeline/dashboard.py`: Streamlit browser for processed data and image gallery.
- Create `scripts/rd_concepts_pipeline/run_all.sh`: runs offline processing phases in order.
- Create `scripts/rd_concepts_pipeline/requirements.txt`: utility-specific dependencies.
- Create `scripts/rd_concepts_pipeline/README.md`: setup, auth, channel discovery, run commands, safety notes.
- Create `tests/rd_concepts_pipeline/fixtures/*.jsonl`: small synthetic Discord raw-message fixtures.
- Create `tests/rd_concepts_pipeline/test_config.py`: config and channel filtering tests.
- Create `tests/rd_concepts_pipeline/test_common.py`: helper tests.
- Create `tests/rd_concepts_pipeline/test_parser.py`: signal/setup extraction tests.
- Create `tests/rd_concepts_pipeline/test_rules_extractor.py`: rule extraction tests.
- Create `tests/rd_concepts_pipeline/test_knowledge_base.py`: aggregation tests.
- Create `tests/rd_concepts_pipeline/test_scraper_units.py`: rate limit, message normalization, and image URL tests using mocked responses.
- Modify `.gitignore`: ignore `data/rd_concepts/` and local RD `.env` files while keeping fixtures tracked.
- Modify `docs/worklog.md`: add implementation summary after completion.

## Task 1: Skeleton, Config, And Shared Helpers

**Files:**
- Create: `scripts/rd_concepts_pipeline/__init__.py`
- Create: `scripts/rd_concepts_pipeline/config.py`
- Create: `scripts/rd_concepts_pipeline/common.py`
- Create: `scripts/rd_concepts_pipeline/requirements.txt`
- Create: `tests/rd_concepts_pipeline/test_config.py`
- Create: `tests/rd_concepts_pipeline/test_common.py`
- Modify: `.gitignore`

- [ ] **Step 1: Write config tests**

Create `tests/rd_concepts_pipeline/test_config.py`:

```python
from pathlib import Path

import pytest

from scripts.rd_concepts_pipeline.config import PipelineSettings, configured_channels


def test_configured_channels_skips_incomplete_ids() -> None:
    settings = PipelineSettings(
        discord_authorization="secret",
        discord_server_id="1160558784314343484",
        data_dir=Path("data/rd_concepts"),
        channels={
            "5m-charts-mechanical": "1240929130980053052",
            "main-pairs": "PASTE_ID",
            "blank": "",
        },
    )

    assert configured_channels(settings) == {
        "5m-charts-mechanical": "1240929130980053052"
    }


def test_settings_requires_authorization_for_live_calls() -> None:
    settings = PipelineSettings(
        discord_authorization="",
        discord_server_id="1160558784314343484",
        data_dir=Path("data/rd_concepts"),
        channels={"5m-charts-mechanical": "1240929130980053052"},
    )

    with pytest.raises(ValueError, match="RD_DISCORD_AUTHORIZATION"):
        settings.require_discord_authorization()
```

- [ ] **Step 2: Write common helper tests**

Create `tests/rd_concepts_pipeline/test_common.py`:

```python
from pathlib import Path

from scripts.rd_concepts_pipeline.common import (
    detect_session,
    extract_setup_tags,
    redact,
    safe_filename,
    write_jsonl,
    read_jsonl,
)


def test_redact_masks_token_like_values() -> None:
    text = "Authorization: aaaaaaaaaaaaaaaaaaaa.bbbbbb.cccccccccccccccccccccc and token=secret"
    assert "aaaaaaaaaaaaaaaaaaaa.bbbbbb.cccccccccccccccccccccc" not in redact(text)
    assert "secret" not in redact(text)


def test_safe_filename_removes_path_characters() -> None:
    assert safe_filename("EUR/USD setup: long.png") == "EUR_USD_setup_long.png"


def test_jsonl_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "messages.jsonl"
    rows = [{"id": "1", "content": "EURUSD long"}, {"id": "2", "content": "rule"}]
    write_jsonl(path, rows)

    assert list(read_jsonl(path)) == rows


def test_detect_session_london_from_utc_timestamp() -> None:
    assert detect_session("2026-05-08T08:30:00+00:00") == "london"


def test_extract_setup_tags_finds_core_rd_concepts() -> None:
    tags = extract_setup_tags("EURUSD sweep into OB with displacement and FVG")
    assert {"liquidity", "sweep", "order_block", "displacement", "fvg"} <= set(tags)
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
PYTHONPATH=. pytest tests/rd_concepts_pipeline/test_config.py tests/rd_concepts_pipeline/test_common.py -v
```

Expected: FAIL because `scripts.rd_concepts_pipeline.config` and `scripts.rd_concepts_pipeline.common` do not exist yet.

- [ ] **Step 4: Implement package skeleton and config**

Create `scripts/rd_concepts_pipeline/__init__.py` with:

```python
"""Offline RD Concepts Discord research data lake tools."""
```

Create `scripts/rd_concepts_pipeline/config.py` with these public names:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
from typing import Mapping

from dotenv import load_dotenv


DEFAULT_CHANNELS: dict[str, str] = {
    "5m-charts-mechanical": "1240929130980053052",
    "main-pairs": "PASTE_ID",
    "5m-charts-analysis": "PASTE_ID",
    "alt-pairs": "PASTE_ID",
    "30m-signals": "PASTE_ID",
    "5m-signals": "PASTE_ID",
    "6-months-chat": "PASTE_ID",
    "wins": "PASTE_ID",
    "webinars-and-extras": "PASTE_ID",
    "market-breakdowns": "PASTE_ID",
    "daily-forecast": "PASTE_ID",
}

INCOMPLETE_CHANNEL_VALUES = {"", "PASTE_ID", "MISSING", "UNKNOWN"}


@dataclass(frozen=True)
class PipelineSettings:
    discord_authorization: str
    discord_server_id: str
    data_dir: Path = Path("data/rd_concepts")
    channels: Mapping[str, str] = field(default_factory=lambda: DEFAULT_CHANNELS.copy())
    request_timeout_seconds: int = 30
    max_retries: int = 3
    page_limit: int = 100

    def require_discord_authorization(self) -> str:
        if not self.discord_authorization.strip():
            raise ValueError("RD_DISCORD_AUTHORIZATION is required for Discord API calls")
        return self.discord_authorization.strip()


def get_settings() -> PipelineSettings:
    load_dotenv()
    return PipelineSettings(
        discord_authorization=os.getenv("RD_DISCORD_AUTHORIZATION", ""),
        discord_server_id=os.getenv("RD_DISCORD_SERVER_ID", "1160558784314343484"),
        data_dir=Path(os.getenv("RD_DATA_DIR", "data/rd_concepts")),
        channels=DEFAULT_CHANNELS.copy(),
        request_timeout_seconds=int(os.getenv("RD_REQUEST_TIMEOUT_SECONDS", "30")),
        max_retries=int(os.getenv("RD_MAX_RETRIES", "3")),
        page_limit=int(os.getenv("RD_PAGE_LIMIT", "100")),
    )


def configured_channels(settings: PipelineSettings) -> dict[str, str]:
    return {
        name: channel_id
        for name, channel_id in settings.channels.items()
        if channel_id.strip() not in INCOMPLETE_CHANNEL_VALUES
    }
```

- [ ] **Step 5: Implement shared helpers**

Create `scripts/rd_concepts_pipeline/common.py` with helpers named in the tests:

```python
from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
from typing import Any, Iterable, Iterator


TOKEN_RE = re.compile(r"([A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{20,}|token=)[^\\s]+")
FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")

TAG_PATTERNS: dict[str, tuple[str, ...]] = {
    "liquidity": ("liquidity", "liq"),
    "sweep": ("sweep", "swept"),
    "bos": ("bos", "break of structure"),
    "choch": ("choch", "change of character"),
    "displacement": ("displacement", "impulse"),
    "imbalance": ("imbalance",),
    "fvg": ("fvg", "fair value gap"),
    "order_block": ("order block", "ob "),
    "ema": ("ema",),
    "fib": ("fib", "fibonacci"),
    "mechanical": ("mechanical",),
    "structure": ("structure",),
    "inducement": ("inducement",),
    "compression": ("compression",),
}


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
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\\n")


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
    lower = f" {text.lower()} "
    tags = [
        tag
        for tag, patterns in TAG_PATTERNS.items()
        if any(pattern in lower for pattern in patterns)
    ]
    return sorted(tags)
```

- [ ] **Step 6: Add requirements and ignores**

Create `scripts/rd_concepts_pipeline/requirements.txt`:

```text
python-dotenv>=1.0.1
requests>=2.32.3
pandas>=2.2.3
streamlit>=1.41.1
plotly>=5.24.1
pytest>=8.3.4
```

Modify `.gitignore` to include these exact lines if absent:

```gitignore
# RD Concepts local data lake
data/rd_concepts/
scripts/rd_concepts_pipeline/.env
```

- [ ] **Step 7: Run tests and commit**

Run:

```bash
PYTHONPATH=. pytest tests/rd_concepts_pipeline/test_config.py tests/rd_concepts_pipeline/test_common.py -v
```

Expected: PASS.

Commit:

```bash
git add .gitignore scripts/rd_concepts_pipeline tests/rd_concepts_pipeline/test_config.py tests/rd_concepts_pipeline/test_common.py
git commit -m "DEV-323: add RD Concepts pipeline foundation"
```

## Task 2: Channel Discovery Helper

**Files:**
- Create: `scripts/rd_concepts_pipeline/list_channels.py`
- Create: `tests/rd_concepts_pipeline/test_list_channels.py`

- [ ] **Step 1: Write channel normalization tests**

Create `tests/rd_concepts_pipeline/test_list_channels.py`:

```python
from scripts.rd_concepts_pipeline.list_channels import normalize_channel


def test_normalize_channel_keeps_text_channel_fields() -> None:
    raw = {"id": "123", "name": "main-pairs", "type": 0, "parent_id": "999"}
    assert normalize_channel(raw) == {
        "id": "123",
        "name": "main-pairs",
        "type": 0,
        "parent_id": "999",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=. pytest tests/rd_concepts_pipeline/test_list_channels.py -v
```

Expected: FAIL because `list_channels.py` does not exist.

- [ ] **Step 3: Implement helper**

Create `scripts/rd_concepts_pipeline/list_channels.py` with:

```python
from __future__ import annotations

import argparse
import json
from typing import Any

import requests

from scripts.rd_concepts_pipeline.common import get_logger, redact
from scripts.rd_concepts_pipeline.config import get_settings

LOGGER = get_logger("rd_concepts.list_channels")
DISCORD_API = "https://discord.com/api/v10"
VISIBLE_CHANNEL_TYPES = {0, 5, 10, 11, 12, 15, 16}


def normalize_channel(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(raw.get("id", "")),
        "name": str(raw.get("name", "")),
        "type": int(raw.get("type", -1)),
        "parent_id": raw.get("parent_id"),
    }


def fetch_channels() -> list[dict[str, Any]]:
    settings = get_settings()
    authorization = settings.require_discord_authorization()
    url = f"{DISCORD_API}/guilds/{settings.discord_server_id}/channels"
    response = requests.get(
        url,
        headers={"Authorization": authorization},
        timeout=settings.request_timeout_seconds,
    )
    if response.status_code >= 400:
        raise RuntimeError(redact(f"Discord channel list failed {response.status_code}: {response.text[:500]}"))
    channels = [normalize_channel(item) for item in response.json()]
    return [channel for channel in channels if channel["type"] in VISIBLE_CHANNEL_TYPES]


def main() -> int:
    parser = argparse.ArgumentParser(description="List visible Discord channels for RD Concepts.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text.")
    args = parser.parse_args()
    channels = sorted(fetch_channels(), key=lambda item: item["name"])
    if args.json:
        print(json.dumps(channels, indent=2, sort_keys=True))
    else:
        for channel in channels:
            print(f"{channel['name']}: {channel['id']} (type={channel['type']})")
    LOGGER.info("Listed %s visible channels", len(channels))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests and help command**

Run:

```bash
PYTHONPATH=. pytest tests/rd_concepts_pipeline/test_list_channels.py -v
python scripts/rd_concepts_pipeline/list_channels.py --help
```

Expected: pytest PASS, help text prints without requiring credentials.

- [ ] **Step 5: Commit**

```bash
git add scripts/rd_concepts_pipeline/list_channels.py tests/rd_concepts_pipeline/test_list_channels.py
git commit -m "DEV-323: add RD Concepts channel discovery"
```

## Task 3: Scraper Unit Functions

**Files:**
- Create: `scripts/rd_concepts_pipeline/scraper.py`
- Create: `tests/rd_concepts_pipeline/test_scraper_units.py`

- [ ] **Step 1: Write scraper unit tests**

Create `tests/rd_concepts_pipeline/test_scraper_units.py`:

```python
from scripts.rd_concepts_pipeline.scraper import (
    extract_image_urls,
    next_before_id,
    normalize_message,
)


def test_extract_image_urls_from_attachments_and_embeds() -> None:
    message = {
        "id": "42",
        "attachments": [
            {"id": "a1", "url": "https://cdn/x.png", "content_type": "image/png"},
            {"id": "a2", "url": "https://cdn/readme.txt", "content_type": "text/plain"},
        ],
        "embeds": [
            {"image": {"url": "https://cdn/embed.jpg"}},
            {"thumbnail": {"url": "https://cdn/thumb.webp"}},
        ],
    }

    assert [item["url"] for item in extract_image_urls(message)] == [
        "https://cdn/x.png",
        "https://cdn/embed.jpg",
        "https://cdn/thumb.webp",
    ]


def test_normalize_message_preserves_required_fields() -> None:
    raw = {
        "id": "100",
        "timestamp": "2026-05-08T08:00:00+00:00",
        "author": {"id": "7", "username": "mentor"},
        "content": "EURUSD long from demand",
        "attachments": [],
        "embeds": [],
    }

    normalized = normalize_message(raw, "main-pairs", "123", [])

    assert normalized["id"] == "100"
    assert normalized["channel"] == "main-pairs"
    assert normalized["author"] == {"id": "7", "username": "mentor"}
    assert normalized["content"] == "EURUSD long from demand"
    assert normalized["images"] == []
    assert normalized["message_url"].endswith("/123/100")


def test_next_before_id_uses_last_message_id() -> None:
    assert next_before_id([{"id": "3"}, {"id": "2"}]) == "2"
    assert next_before_id([]) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=. pytest tests/rd_concepts_pipeline/test_scraper_units.py -v
```

Expected: FAIL because `scraper.py` does not yet define the tested functions.

- [ ] **Step 3: Implement scraper pure functions**

Create `scripts/rd_concepts_pipeline/scraper.py` with pure helpers first:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from typing import Any
from urllib.parse import urlparse

import requests

from scripts.rd_concepts_pipeline.common import ensure_dir, get_logger, now_iso, redact, safe_filename, write_jsonl
from scripts.rd_concepts_pipeline.config import PipelineSettings, configured_channels, get_settings

LOGGER = get_logger("rd_concepts.scraper")
DISCORD_API = "https://discord.com/api/v10"
IMAGE_CONTENT_PREFIX = "image/"


def extract_image_urls(message: dict[str, Any]) -> list[dict[str, str]]:
    images: list[dict[str, str]] = []
    for index, attachment in enumerate(message.get("attachments") or []):
        content_type = str(attachment.get("content_type", ""))
        url = str(attachment.get("url", ""))
        if url and content_type.startswith(IMAGE_CONTENT_PREFIX):
            images.append({"source": "attachment", "index": str(index), "url": url})
    for index, embed in enumerate(message.get("embeds") or []):
        for key in ("image", "thumbnail"):
            url = str((embed.get(key) or {}).get("url", ""))
            if url:
                images.append({"source": f"embed_{key}", "index": str(index), "url": url})
    return images


def normalize_message(
    raw: dict[str, Any],
    channel_name: str,
    channel_id: str,
    image_paths: list[str],
) -> dict[str, Any]:
    author = raw.get("author") or {}
    message_id = str(raw.get("id", ""))
    return {
        "id": message_id,
        "channel": channel_name,
        "channel_id": channel_id,
        "timestamp": raw.get("timestamp"),
        "author": {
            "id": str(author.get("id", "")),
            "username": str(author.get("username", "")),
        },
        "content": raw.get("content", ""),
        "attachments": raw.get("attachments") or [],
        "embeds": raw.get("embeds") or [],
        "images": image_paths,
        "message_url": f"https://discord.com/channels/@me/{channel_id}/{message_id}",
        "raw": raw,
    }


def next_before_id(messages: list[dict[str, Any]]) -> str | None:
    if not messages:
        return None
    return str(messages[-1].get("id", "")) or None
```

- [ ] **Step 4: Run unit tests**

Run:

```bash
PYTHONPATH=. pytest tests/rd_concepts_pipeline/test_scraper_units.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/rd_concepts_pipeline/scraper.py tests/rd_concepts_pipeline/test_scraper_units.py
git commit -m "DEV-323: add RD Concepts scraper helpers"
```

## Task 4: Live Scraper Pagination, Downloads, And Manifests

**Files:**
- Modify: `scripts/rd_concepts_pipeline/scraper.py`
- Modify: `tests/rd_concepts_pipeline/test_scraper_units.py`

- [ ] **Step 1: Add tests for rate-limit and image filenames**

Append to `tests/rd_concepts_pipeline/test_scraper_units.py`:

```python
from scripts.rd_concepts_pipeline.scraper import build_image_filename, should_retry_status


def test_build_image_filename_uses_message_source_and_extension() -> None:
    filename = build_image_filename("123", {"source": "embed_image", "index": "0", "url": "https://cdn/chart.png?x=1"})
    assert filename == "123_embed_image_0.png"


def test_should_retry_status_marks_rate_limits_and_server_errors() -> None:
    assert should_retry_status(429) is True
    assert should_retry_status(500) is True
    assert should_retry_status(403) is False
```

- [ ] **Step 2: Run focused tests**

Run:

```bash
PYTHONPATH=. pytest tests/rd_concepts_pipeline/test_scraper_units.py -v
```

Expected: FAIL because `build_image_filename` and `should_retry_status` do not exist.

- [ ] **Step 3: Implement scraper runtime functions**

Extend `scraper.py` with:

```python
def should_retry_status(status_code: int) -> bool:
    return status_code == 429 or 500 <= status_code <= 599


def build_image_filename(message_id: str, image: dict[str, str]) -> str:
    parsed = urlparse(image["url"])
    suffix = Path(parsed.path).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        suffix = ".img"
    base = safe_filename(f"{message_id}_{image['source']}_{image['index']}")
    return f"{base}{suffix}"


def request_json_with_retries(
    url: str,
    settings: PipelineSettings,
    params: dict[str, Any] | None = None,
) -> tuple[int, Any]:
    headers = {"Authorization": settings.require_discord_authorization()}
    for attempt in range(1, settings.max_retries + 1):
        response = requests.get(url, headers=headers, params=params, timeout=settings.request_timeout_seconds)
        if response.status_code == 429:
            retry_after = float(response.json().get("retry_after", 1.0))
            LOGGER.warning("Rate limited for %.2fs on %s", retry_after, redact(url))
            time.sleep(retry_after)
            continue
        if response.status_code == 403:
            return response.status_code, None
        if should_retry_status(response.status_code) and attempt < settings.max_retries:
            time.sleep(min(attempt * 2, 10))
            continue
        if response.status_code >= 400:
            raise RuntimeError(redact(f"Discord request failed {response.status_code}: {response.text[:500]}"))
        return response.status_code, response.json()
    raise RuntimeError(redact(f"Discord request exhausted retries: {url}"))


def download_image(url: str, output_path: Path, settings: PipelineSettings) -> bool:
    ensure_dir(output_path.parent)
    headers = {"Authorization": settings.require_discord_authorization()}
    for attempt in range(1, settings.max_retries + 1):
        response = requests.get(url, headers=headers, timeout=settings.request_timeout_seconds)
        if response.status_code == 429:
            retry_after = float(response.json().get("retry_after", 1.0))
            time.sleep(retry_after)
            continue
        if should_retry_status(response.status_code) and attempt < settings.max_retries:
            time.sleep(min(attempt * 2, 10))
            continue
        if response.status_code >= 400:
            LOGGER.warning("Image download failed %s for %s", response.status_code, redact(url))
            return False
        output_path.write_bytes(response.content)
        return True
    return False
```

Then add channel scraping:

```python
def scrape_channel(channel_name: str, channel_id: str, settings: PipelineSettings, dry_run: bool = False) -> dict[str, Any]:
    channel_dir = settings.data_dir / "raw" / channel_name
    image_dir = channel_dir / "images"
    ensure_dir(image_dir)
    url = f"{DISCORD_API}/channels/{channel_id}/messages"
    before: str | None = None
    all_rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    page = 0

    while True:
        params = {"limit": settings.page_limit}
        if before:
            params["before"] = before
        status_code, messages = request_json_with_retries(url, settings, params=params)
        if status_code == 403:
            LOGGER.warning("Skipping %s: Discord returned 403", channel_name)
            return {"channel": channel_name, "status": "forbidden", "message_count": 0}
        if not messages:
            break
        page += 1
        LOGGER.info("%s page %s fetched %s messages", channel_name, page, len(messages))
        for raw in messages:
            image_paths: list[str] = []
            for image in extract_image_urls(raw):
                filename = build_image_filename(str(raw.get("id", "")), image)
                output_path = image_dir / filename
                if dry_run or output_path.exists() or download_image(image["url"], output_path, settings):
                    image_paths.append(str(output_path))
                else:
                    failures.append({"message_id": str(raw.get("id", "")), "url": image["url"]})
            all_rows.append(normalize_message(raw, channel_name, channel_id, image_paths))
        before = next_before_id(messages)
        if dry_run:
            break

    write_jsonl(channel_dir / "messages.jsonl", all_rows)
    manifest = {
        "channel": channel_name,
        "channel_id": channel_id,
        "status": "ok",
        "scraped_at": now_iso(),
        "message_count": len(all_rows),
        "image_failures": failures,
    }
    (channel_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest
```

Add `main()`:

```python
def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape RD Concepts Discord messages and images.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch one page per configured channel without downloading images.")
    parser.add_argument("--channel", help="Only scrape one configured channel name.")
    args = parser.parse_args()
    settings = get_settings()
    channels = configured_channels(settings)
    if args.channel:
        channels = {args.channel: channels[args.channel]}
    summaries = [scrape_channel(name, channel_id, settings, dry_run=args.dry_run) for name, channel_id in channels.items()]
    LOGGER.info("Scrape summary: %s", json.dumps(summaries, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests and dry-run help**

Run:

```bash
PYTHONPATH=. pytest tests/rd_concepts_pipeline/test_scraper_units.py -v
python scripts/rd_concepts_pipeline/scraper.py --help
```

Expected: pytest PASS, help text prints without requiring credentials.

- [ ] **Step 5: Commit**

```bash
git add scripts/rd_concepts_pipeline/scraper.py tests/rd_concepts_pipeline/test_scraper_units.py
git commit -m "DEV-323: add RD Concepts scraper runtime"
```

## Task 5: Signal Parser And Image Index

**Files:**
- Create: `scripts/rd_concepts_pipeline/parser.py`
- Create: `tests/rd_concepts_pipeline/fixtures/raw_messages.jsonl`
- Create: `tests/rd_concepts_pipeline/test_parser.py`

- [ ] **Step 1: Create parser fixture**

Create `tests/rd_concepts_pipeline/fixtures/raw_messages.jsonl`:

```jsonl
{"id":"1","channel":"5m-signals","timestamp":"2026-05-08T08:30:00+00:00","author":{"id":"a","username":"mentor"},"content":"EURUSD LONG entry 1.0750 SL: 1.0725 TP: 1.0825 liquidity sweep into FVG 5m","images":["data/rd_concepts/raw/5m-signals/images/1.png"],"embeds":[],"message_url":"https://discord.com/channels/@me/1/1"}
{"id":"2","channel":"30m-signals","timestamp":"2026-05-08T13:00:00+00:00","author":{"id":"a","username":"mentor"},"content":"GBPUSD SELL @ 1.2600, Stop 1.2640, Target 1.2480 after BOS and order block","images":[],"embeds":[],"message_url":"https://discord.com/channels/@me/2/2"}
{"id":"3","channel":"main-pairs","timestamp":"2026-05-08T20:00:00+00:00","author":{"id":"b","username":"student"},"content":"Watching XAUUSD bullish if it sweeps lows and reclaims 5m structure","images":["data/rd_concepts/raw/main-pairs/images/3.png"],"embeds":[],"message_url":"https://discord.com/channels/@me/3/3"}
```

- [ ] **Step 2: Write parser tests**

Create `tests/rd_concepts_pipeline/test_parser.py`:

```python
from pathlib import Path

from scripts.rd_concepts_pipeline.parser import parse_message, parse_raw_files


def test_parse_pattern_a_long_signal() -> None:
    row = {
        "id": "1",
        "channel": "5m-signals",
        "timestamp": "2026-05-08T08:30:00+00:00",
        "content": "EURUSD LONG entry 1.0750 SL: 1.0725 TP: 1.0825 liquidity sweep into FVG 5m",
        "images": ["chart.png"],
    }

    parsed = parse_message(row)

    assert parsed["pair"] == "EURUSD"
    assert parsed["direction"] == "long"
    assert parsed["entry"] == 1.075
    assert parsed["stop_loss"] == 1.0725
    assert parsed["take_profit"] == 1.0825
    assert parsed["rr_ratio"] == 3.0
    assert parsed["has_chart"] is True
    assert {"liquidity", "sweep", "fvg"} <= set(parsed["setup_tags"])


def test_parse_pattern_b_short_signal() -> None:
    row = {
        "id": "2",
        "channel": "30m-signals",
        "timestamp": "2026-05-08T13:00:00+00:00",
        "content": "GBPUSD SELL @ 1.2600, Stop 1.2640, Target 1.2480 after BOS and order block",
        "images": [],
    }

    parsed = parse_message(row)

    assert parsed["pair"] == "GBPUSD"
    assert parsed["direction"] == "short"
    assert parsed["rr_ratio"] == 3.0
    assert {"bos", "order_block"} <= set(parsed["setup_tags"])


def test_parse_loose_setup_keeps_ambiguous_record() -> None:
    row = {
        "id": "3",
        "channel": "main-pairs",
        "timestamp": "2026-05-08T20:00:00+00:00",
        "content": "Watching XAUUSD bullish if it sweeps lows and reclaims 5m structure",
        "images": ["chart.png"],
    }

    parsed = parse_message(row)

    assert parsed["pair"] == "XAUUSD"
    assert parsed["direction"] == "long"
    assert "missing_levels" in parsed["quality_flags"]


def test_parse_raw_files_returns_signals_and_image_index() -> None:
    fixture = Path("tests/rd_concepts_pipeline/fixtures/raw_messages.jsonl")
    signals, images = parse_raw_files([fixture])

    assert len(signals) == 3
    assert len(images) == 2
```

- [ ] **Step 3: Run parser tests to verify they fail**

Run:

```bash
PYTHONPATH=. pytest tests/rd_concepts_pipeline/test_parser.py -v
```

Expected: FAIL because `parser.py` does not exist.

- [ ] **Step 4: Implement parser**

Create `scripts/rd_concepts_pipeline/parser.py` with:

```python
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import re
from typing import Any

import pandas as pd

from scripts.rd_concepts_pipeline.common import detect_session, ensure_dir, extract_setup_tags, get_logger, read_jsonl
from scripts.rd_concepts_pipeline.config import get_settings

LOGGER = get_logger("rd_concepts.parser")
PAIR_RE = re.compile(r"\\b(EURUSD|GBPUSD|AUDUSD|NZDUSD|USDJPY|EURJPY|GBPJPY|NZDJPY|AUDJPY|USDCAD|USDCHF|XAUUSD|XAGUSD|GOLD|NAS100|US100|SPX500|US30)\\b", re.I)
DIRECTION_RE = re.compile(r"\\b(LONG|SHORT|BUY|SELL|BULLISH|BEARISH)\\b", re.I)
TIMEFRAME_RE = re.compile(r"\\b(5m|15m|30m|1h|4h|daily)\\b", re.I)
PATTERN_A = re.compile(r"(?P<pair>[A-Z]{6}|XAUUSD|XAGUSD|GOLD|NAS100|US100|SPX500|US30)\\s+(?P<direction>LONG|SHORT)\\s+.*?entry\\s*:??\\s*(?P<entry>\\d+(?:\\.\\d+)?).*?SL\\s*:??\\s*(?P<sl>\\d+(?:\\.\\d+)?).*?TP\\s*:??\\s*(?P<tp>\\d+(?:\\.\\d+)?)", re.I | re.S)
PATTERN_B = re.compile(r"(?P<pair>[A-Z]{6}|XAUUSD|XAGUSD|GOLD|NAS100|US100|SPX500|US30)\\s+(?P<direction>BUY|SELL)\\s*@\\s*(?P<entry>\\d+(?:\\.\\d+)?).*?Stop\\s+(?P<sl>\\d+(?:\\.\\d+)?).*?Target\\s+(?P<tp>\\d+(?:\\.\\d+)?)", re.I | re.S)


def normalize_pair(pair: str | None) -> str:
    if not pair:
        return ""
    upper = pair.upper()
    return "XAUUSD" if upper == "GOLD" else upper


def normalize_direction(direction: str | None) -> str:
    value = (direction or "").upper()
    if value in {"LONG", "BUY", "BULLISH"}:
        return "long"
    if value in {"SHORT", "SELL", "BEARISH"}:
        return "short"
    return ""


def compute_rr(entry: float | None, stop_loss: float | None, take_profit: float | None) -> float | None:
    if entry is None or stop_loss is None or take_profit is None:
        return None
    risk = abs(entry - stop_loss)
    reward = abs(take_profit - entry)
    if risk == 0:
        return None
    return round(reward / risk, 2)


def parse_message(row: dict[str, Any]) -> dict[str, Any]:
    content = str(row.get("content", ""))
    match = PATTERN_A.search(content) or PATTERN_B.search(content)
    pair = normalize_pair(match.group("pair") if match else (PAIR_RE.search(content).group(1) if PAIR_RE.search(content) else ""))
    direction = normalize_direction(match.group("direction") if match else (DIRECTION_RE.search(content).group(1) if DIRECTION_RE.search(content) else ""))
    entry = float(match.group("entry")) if match else None
    stop_loss = float(match.group("sl")) if match else None
    take_profit = float(match.group("tp")) if match else None
    timeframe_match = TIMEFRAME_RE.search(content)
    images = row.get("images") or []
    quality_flags: list[str] = []
    if not match:
        quality_flags.append("loose_match")
    if entry is None or stop_loss is None or take_profit is None:
        quality_flags.append("missing_levels")
    if images:
        quality_flags.append("chart_backed")
    return {
        "signal_id": f"{row.get('channel', '')}:{row.get('id', '')}",
        "message_id": row.get("id", ""),
        "timestamp": row.get("timestamp", ""),
        "channel": row.get("channel", ""),
        "pair": pair,
        "direction": direction,
        "timeframe": timeframe_match.group(1).lower() if timeframe_match else "",
        "entry": entry,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "rr_ratio": compute_rr(entry, stop_loss, take_profit),
        "setup_notes": content[:500],
        "setup_tags": extract_setup_tags(content),
        "confluence_tags": extract_setup_tags(content),
        "session": detect_session(str(row.get("timestamp", ""))) if row.get("timestamp") else "",
        "has_chart": bool(images),
        "chart_paths": images,
        "quality_flags": quality_flags,
        "raw_message": content,
        "message_url": row.get("message_url", ""),
    }


def parse_raw_files(paths: list[Path]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    signals: list[dict[str, Any]] = []
    image_index: list[dict[str, Any]] = []
    for path in paths:
        for row in read_jsonl(path):
            parsed = parse_message(row)
            if parsed["pair"] or parsed["setup_tags"]:
                signals.append(parsed)
            for image_path in row.get("images") or []:
                image_index.append({
                    "message_id": row.get("id", ""),
                    "timestamp": row.get("timestamp", ""),
                    "channel": row.get("channel", ""),
                    "image_path": image_path,
                    "pair": parsed["pair"],
                    "direction": parsed["direction"],
                    "setup_tags": parsed["setup_tags"],
                })
    return signals, image_index


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse RD Concepts raw messages into signal and image indexes.")
    args = parser.parse_args()
    settings = get_settings()
    raw_paths = sorted((settings.data_dir / "raw").glob("*/messages.jsonl"))
    signals, image_index = parse_raw_files(raw_paths)
    processed_dir = ensure_dir(settings.data_dir / "processed")
    pd.DataFrame(signals).to_csv(processed_dir / "signals.csv", index=False)
    pd.DataFrame(image_index).to_csv(processed_dir / "image_index.csv", index=False, quoting=csv.QUOTE_MINIMAL)
    LOGGER.info("Parsed %s signals and %s images", len(signals), len(image_index))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run tests and commit**

Run:

```bash
PYTHONPATH=. pytest tests/rd_concepts_pipeline/test_parser.py -v
```

Expected: PASS.

Commit:

```bash
git add scripts/rd_concepts_pipeline/parser.py tests/rd_concepts_pipeline/fixtures/raw_messages.jsonl tests/rd_concepts_pipeline/test_parser.py
git commit -m "DEV-323: parse RD Concepts setup records"
```

## Task 6: Rules Extractor And Concept Frequencies

**Files:**
- Create: `scripts/rd_concepts_pipeline/rules_extractor.py`
- Create: `tests/rd_concepts_pipeline/test_rules_extractor.py`

- [ ] **Step 1: Write rule extraction tests**

Create `tests/rd_concepts_pipeline/test_rules_extractor.py`:

```python
from pathlib import Path

from scripts.rd_concepts_pipeline.rules_extractor import extract_rule_record, extract_rules_from_files


def test_extract_rule_record_matches_must_and_liquidity() -> None:
    row = {
        "id": "10",
        "channel": "webinars-and-extras",
        "timestamp": "2026-05-08T09:00:00+00:00",
        "author": {"username": "mentor"},
        "content": "Rule: price must sweep liquidity before entry into order block.",
        "images": ["chart.png"],
        "message_url": "https://discord.com/channels/@me/10/10",
    }

    record = extract_rule_record(row)

    assert record is not None
    assert "must" in record["keyword_hits"]
    assert {"liquidity", "sweep", "order_block"} <= set(record["concept_tags"])


def test_extract_rules_from_files_counts_concepts() -> None:
    rules, concepts = extract_rules_from_files([Path("tests/rd_concepts_pipeline/fixtures/raw_messages.jsonl")])

    assert isinstance(rules, list)
    assert "liquidity" in concepts
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONPATH=. pytest tests/rd_concepts_pipeline/test_rules_extractor.py -v
```

Expected: FAIL because `rules_extractor.py` does not exist.

- [ ] **Step 3: Implement rules extractor**

Create `scripts/rd_concepts_pipeline/rules_extractor.py` with:

```python
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from typing import Any

from scripts.rd_concepts_pipeline.common import ensure_dir, extract_setup_tags, get_logger, read_jsonl, write_jsonl
from scripts.rd_concepts_pipeline.config import get_settings

LOGGER = get_logger("rd_concepts.rules")
RULE_KEYWORDS = [
    "rule", "setup", "entry", "confluence", "structure", "mechanical",
    "condition", "must", "always", "never", "5m", "ema", "fib",
    "liquidity", "bos", "choch", "sweep", "displacement", "imbalance",
    "ob", "order block", "fair value gap", "fvg", "pd array",
]


def keyword_hits(content: str) -> list[str]:
    lower = content.lower()
    return sorted({keyword for keyword in RULE_KEYWORDS if keyword in lower})


def extract_rule_record(row: dict[str, Any]) -> dict[str, Any] | None:
    content = str(row.get("content", ""))
    hits = keyword_hits(content)
    tags = extract_setup_tags(content)
    if not hits and not tags:
        return None
    return {
        "rule_id": f"{row.get('channel', '')}:{row.get('id', '')}",
        "message_id": row.get("id", ""),
        "timestamp": row.get("timestamp", ""),
        "channel": row.get("channel", ""),
        "author": (row.get("author") or {}).get("username", ""),
        "content": content,
        "keyword_hits": hits,
        "concept_tags": tags,
        "images": row.get("images") or [],
        "message_url": row.get("message_url", ""),
    }


def extract_rules_from_files(paths: list[Path]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    examples: dict[str, list[str]] = defaultdict(list)
    counts: Counter[str] = Counter()
    for path in paths:
        for row in read_jsonl(path):
            record = extract_rule_record(row)
            if record is None:
                continue
            rules.append(record)
            for tag in record["concept_tags"] + record["keyword_hits"]:
                counts[tag] += 1
                if len(examples[tag]) < 5:
                    examples[tag].append(record["rule_id"])
    concepts = {
        key: {"count": count, "examples": examples[key]}
        for key, count in counts.most_common()
    }
    return rules, concepts


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract RD Concepts strategy rule messages.")
    parser.parse_args()
    settings = get_settings()
    raw_paths = sorted((settings.data_dir / "raw").glob("*/messages.jsonl"))
    rules, concepts = extract_rules_from_files(raw_paths)
    processed_dir = ensure_dir(settings.data_dir / "processed")
    write_jsonl(processed_dir / "rules.jsonl", rules)
    (processed_dir / "concepts.json").write_text(json.dumps(concepts, indent=2, sort_keys=True), encoding="utf-8")
    LOGGER.info("Extracted %s rules and %s concepts", len(rules), len(concepts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests and commit**

Run:

```bash
PYTHONPATH=. pytest tests/rd_concepts_pipeline/test_rules_extractor.py -v
```

Expected: PASS.

Commit:

```bash
git add scripts/rd_concepts_pipeline/rules_extractor.py tests/rd_concepts_pipeline/test_rules_extractor.py
git commit -m "DEV-323: extract RD Concepts strategy rules"
```

## Task 7: Knowledge Base Builder

**Files:**
- Create: `scripts/rd_concepts_pipeline/knowledge_base.py`
- Create: `tests/rd_concepts_pipeline/test_knowledge_base.py`

- [ ] **Step 1: Write knowledge-base tests**

Create `tests/rd_concepts_pipeline/test_knowledge_base.py`:

```python
import pandas as pd

from scripts.rd_concepts_pipeline.knowledge_base import build_knowledge_base


def test_build_knowledge_base_summarizes_pairs_and_timeframes() -> None:
    signals = pd.DataFrame(
        [
            {"pair": "EURUSD", "direction": "long", "timeframe": "5m", "channel": "5m-signals", "session": "london", "setup_tags": ["liquidity", "fvg"], "chart_paths": ["a.png"]},
            {"pair": "EURUSD", "direction": "short", "timeframe": "5m", "channel": "5m-signals", "session": "ny_overlap", "setup_tags": ["bos"], "chart_paths": []},
            {"pair": "GBPUSD", "direction": "short", "timeframe": "30m", "channel": "30m-signals", "session": "ny_overlap", "setup_tags": ["order_block"], "chart_paths": []},
        ]
    )
    rules = [{"concept_tags": ["liquidity"], "rule_id": "rules:1"}]
    concepts = {"liquidity": {"count": 2, "examples": ["rules:1"]}}

    kb = build_knowledge_base(signals, rules, concepts)

    assert kb["pairs"]["EURUSD"]["total_signals"] == 2
    assert kb["pairs"]["EURUSD"]["long_percent"] == 50.0
    assert kb["timeframes"]["5m"] == 2
    assert kb["concepts"]["liquidity"]["count"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=. pytest tests/rd_concepts_pipeline/test_knowledge_base.py -v
```

Expected: FAIL because `knowledge_base.py` does not exist.

- [ ] **Step 3: Implement knowledge-base builder**

Create `scripts/rd_concepts_pipeline/knowledge_base.py` with:

```python
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.rd_concepts_pipeline.common import ensure_dir, get_logger, read_jsonl
from scripts.rd_concepts_pipeline.config import get_settings

LOGGER = get_logger("rd_concepts.knowledge_base")


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if pd.isna(value):
        return []
    if isinstance(value, str):
        try:
            parsed = json.loads(value.replace("'", '"'))
            return parsed if isinstance(parsed, list) else [value]
        except json.JSONDecodeError:
            return [part.strip() for part in value.split(",") if part.strip()]
    return [value]


def build_knowledge_base(signals: pd.DataFrame, rules: list[dict[str, Any]], concepts: dict[str, Any]) -> dict[str, Any]:
    pairs: dict[str, Any] = {}
    if not signals.empty:
        for pair, group in signals.groupby("pair"):
            if not pair:
                continue
            total = int(len(group))
            long_count = int((group["direction"] == "long").sum()) if "direction" in group else 0
            short_count = int((group["direction"] == "short").sum()) if "direction" in group else 0
            setup_counter: Counter[str] = Counter()
            chart_paths: list[str] = []
            for _, row in group.iterrows():
                setup_counter.update(_as_list(row.get("setup_tags", [])))
                chart_paths.extend(str(item) for item in _as_list(row.get("chart_paths", [])) if item)
            pairs[pair] = {
                "total_signals": total,
                "long_percent": round((long_count / total) * 100, 2) if total else 0.0,
                "short_percent": round((short_count / total) * 100, 2) if total else 0.0,
                "channels_active": sorted(set(str(item) for item in group.get("channel", pd.Series(dtype=str)).dropna())),
                "sessions": group.get("session", pd.Series(dtype=str)).value_counts().to_dict(),
                "setup_tags": dict(setup_counter.most_common()),
                "chart_paths": chart_paths,
            }
    return {
        "pairs": pairs,
        "timeframes": signals.get("timeframe", pd.Series(dtype=str)).value_counts().to_dict() if not signals.empty else {},
        "channels": signals.get("channel", pd.Series(dtype=str)).value_counts().to_dict() if not signals.empty else {},
        "rules_total": len(rules),
        "concepts": concepts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build RD Concepts strategy knowledge base.")
    parser.parse_args()
    settings = get_settings()
    processed_dir = ensure_dir(settings.data_dir / "processed")
    signals_path = processed_dir / "signals.csv"
    rules_path = processed_dir / "rules.jsonl"
    concepts_path = processed_dir / "concepts.json"
    signals = pd.read_csv(signals_path) if signals_path.exists() else pd.DataFrame()
    rules = list(read_jsonl(rules_path))
    concepts = json.loads(concepts_path.read_text(encoding="utf-8")) if concepts_path.exists() else {}
    kb = build_knowledge_base(signals, rules, concepts)
    (processed_dir / "knowledge_base.json").write_text(json.dumps(kb, indent=2, sort_keys=True), encoding="utf-8")
    LOGGER.info("Knowledge base written with %s pairs", len(kb["pairs"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests and commit**

Run:

```bash
PYTHONPATH=. pytest tests/rd_concepts_pipeline/test_knowledge_base.py -v
```

Expected: PASS.

Commit:

```bash
git add scripts/rd_concepts_pipeline/knowledge_base.py tests/rd_concepts_pipeline/test_knowledge_base.py
git commit -m "DEV-323: build RD Concepts knowledge base"
```

## Task 8: Dashboard

**Files:**
- Create: `scripts/rd_concepts_pipeline/dashboard.py`
- Create: `tests/rd_concepts_pipeline/test_dashboard_import.py`

- [ ] **Step 1: Write import smoke test**

Create `tests/rd_concepts_pipeline/test_dashboard_import.py`:

```python
import importlib


def test_dashboard_imports_without_credentials() -> None:
    module = importlib.import_module("scripts.rd_concepts_pipeline.dashboard")
    assert hasattr(module, "load_processed_data")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=. pytest tests/rd_concepts_pipeline/test_dashboard_import.py -v
```

Expected: FAIL because `dashboard.py` does not exist.

- [ ] **Step 3: Implement dashboard module**

Create `scripts/rd_concepts_pipeline/dashboard.py` with:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from scripts.rd_concepts_pipeline.common import read_jsonl
from scripts.rd_concepts_pipeline.config import get_settings


def load_processed_data(data_dir: Path) -> tuple[pd.DataFrame, list[dict[str, Any]], dict[str, Any], pd.DataFrame]:
    processed_dir = data_dir / "processed"
    signals_path = processed_dir / "signals.csv"
    image_index_path = processed_dir / "image_index.csv"
    rules_path = processed_dir / "rules.jsonl"
    kb_path = processed_dir / "knowledge_base.json"
    signals = pd.read_csv(signals_path) if signals_path.exists() else pd.DataFrame()
    image_index = pd.read_csv(image_index_path) if image_index_path.exists() else pd.DataFrame()
    rules = list(read_jsonl(rules_path))
    kb = json.loads(kb_path.read_text(encoding="utf-8")) if kb_path.exists() else {}
    return signals, rules, kb, image_index


def main() -> None:
    settings = get_settings()
    st.set_page_config(page_title="RD Concepts Data Lake", layout="wide")
    st.title("RD Concepts Data Lake")
    signals, rules, kb, image_index = load_processed_data(settings.data_dir)

    left, right = st.columns(2)
    with left:
        st.subheader("Signals by Channel")
        if not signals.empty and "channel" in signals:
            counts = signals["channel"].value_counts().reset_index()
            counts.columns = ["channel", "count"]
            st.plotly_chart(px.bar(counts, x="channel", y="count"), use_container_width=True)
        else:
            st.info("No parsed signals found.")
    with right:
        st.subheader("Pair Breakdown")
        if not signals.empty and "pair" in signals:
            counts = signals["pair"].value_counts().reset_index()
            counts.columns = ["pair", "count"]
            st.plotly_chart(px.bar(counts, x="pair", y="count"), use_container_width=True)
        else:
            st.info("No pair data found.")

    st.subheader("Signal Table")
    filtered = signals.copy()
    if not filtered.empty:
        pair_options = sorted(item for item in filtered.get("pair", pd.Series(dtype=str)).dropna().unique() if item)
        selected_pairs = st.multiselect("Pair", pair_options, default=pair_options)
        if selected_pairs:
            filtered = filtered[filtered["pair"].isin(selected_pairs)]
        st.dataframe(filtered, use_container_width=True)

    st.subheader("Strategy Rules")
    query = st.text_input("Search rules")
    visible_rules = [
        rule for rule in rules
        if not query or query.lower() in str(rule.get("content", "")).lower()
    ]
    st.dataframe(pd.DataFrame(visible_rules), use_container_width=True)

    st.subheader("Chart Images")
    if not image_index.empty:
        st.dataframe(image_index, use_container_width=True)
        for image_path in image_index.get("image_path", pd.Series(dtype=str)).dropna().head(24):
            path = Path(image_path)
            if path.exists():
                st.image(str(path), caption=str(path))
    st.caption(f"Knowledge-base pairs: {len(kb.get('pairs', {})) if isinstance(kb, dict) else 0}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run smoke test and commit**

Run:

```bash
PYTHONPATH=. pytest tests/rd_concepts_pipeline/test_dashboard_import.py -v
python -m py_compile scripts/rd_concepts_pipeline/dashboard.py
```

Expected: PASS and compile succeeds.

Commit:

```bash
git add scripts/rd_concepts_pipeline/dashboard.py tests/rd_concepts_pipeline/test_dashboard_import.py
git commit -m "DEV-323: add RD Concepts data dashboard"
```

## Task 9: Run-All Script And README

**Files:**
- Create: `scripts/rd_concepts_pipeline/run_all.sh`
- Create: `scripts/rd_concepts_pipeline/README.md`

- [ ] **Step 1: Create run script**

Create `scripts/rd_concepts_pipeline/run_all.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

python scripts/rd_concepts_pipeline/scraper.py
python scripts/rd_concepts_pipeline/parser.py
python scripts/rd_concepts_pipeline/rules_extractor.py
python scripts/rd_concepts_pipeline/knowledge_base.py

echo "RD Concepts data lake complete. Run: streamlit run scripts/rd_concepts_pipeline/dashboard.py"
```

Run:

```bash
chmod +x scripts/rd_concepts_pipeline/run_all.sh
```

- [ ] **Step 2: Create README**

Create `scripts/rd_concepts_pipeline/README.md` with:

```markdown
# RD Concepts Pipeline

Offline Discord research data lake for RD Concepts strategy analysis.

## Safety

This tool does not execute trades, call MetaApi, import the worker, or change live bot state. It writes local research files under `data/rd_concepts/`.

Do not commit Discord authorization values. Put local credentials in `.env`:

```bash
RD_DISCORD_AUTHORIZATION=your_local_authorization_value
RD_DISCORD_SERVER_ID=1160558784314343484
```

If an authorization value was pasted into chat or logs, rotate it before running long scrapes.

## Install

```bash
source ./venv/bin/activate
pip install -r scripts/rd_concepts_pipeline/requirements.txt
```

## Discover Channels

```bash
python scripts/rd_concepts_pipeline/list_channels.py
```

Copy channel IDs into `scripts/rd_concepts_pipeline/config.py`.

## Run

```bash
python scripts/rd_concepts_pipeline/scraper.py --dry-run
python scripts/rd_concepts_pipeline/scraper.py
python scripts/rd_concepts_pipeline/parser.py
python scripts/rd_concepts_pipeline/rules_extractor.py
python scripts/rd_concepts_pipeline/knowledge_base.py
streamlit run scripts/rd_concepts_pipeline/dashboard.py
```

Or:

```bash
scripts/rd_concepts_pipeline/run_all.sh
```

## Outputs

- `data/rd_concepts/raw/<channel>/messages.jsonl`
- `data/rd_concepts/raw/<channel>/images/`
- `data/rd_concepts/raw/<channel>/manifest.json`
- `data/rd_concepts/processed/signals.csv`
- `data/rd_concepts/processed/rules.jsonl`
- `data/rd_concepts/processed/concepts.json`
- `data/rd_concepts/processed/image_index.csv`
- `data/rd_concepts/processed/knowledge_base.json`
```

- [ ] **Step 3: Verify commands and commit**

Run:

```bash
bash -n scripts/rd_concepts_pipeline/run_all.sh
python scripts/rd_concepts_pipeline/list_channels.py --help
python scripts/rd_concepts_pipeline/scraper.py --help
```

Expected: shell syntax OK, help commands print usage.

Commit:

```bash
git add scripts/rd_concepts_pipeline/run_all.sh scripts/rd_concepts_pipeline/README.md
git commit -m "DEV-323: document RD Concepts pipeline"
```

## Task 10: End-To-End Fixture Verification And Worklog

**Files:**
- Modify: `docs/worklog.md`

- [ ] **Step 1: Run all unit tests for the pipeline**

Run:

```bash
PYTHONPATH=. pytest tests/rd_concepts_pipeline -v
```

Expected: all RD Concepts pipeline tests PASS.

- [ ] **Step 2: Run processors against fixture data in a temporary data directory**

Run:

```bash
tmpdir="$(mktemp -d)"
mkdir -p "$tmpdir/raw/fixture"
cp tests/rd_concepts_pipeline/fixtures/raw_messages.jsonl "$tmpdir/raw/fixture/messages.jsonl"
RD_DATA_DIR="$tmpdir" PYTHONPATH=. python scripts/rd_concepts_pipeline/parser.py
RD_DATA_DIR="$tmpdir" PYTHONPATH=. python scripts/rd_concepts_pipeline/rules_extractor.py
RD_DATA_DIR="$tmpdir" PYTHONPATH=. python scripts/rd_concepts_pipeline/knowledge_base.py
test -f "$tmpdir/processed/signals.csv"
test -f "$tmpdir/processed/rules.jsonl"
test -f "$tmpdir/processed/knowledge_base.json"
```

Expected: all commands exit 0 and the three processed output files exist.

- [ ] **Step 3: Run lint for pipeline files only**

Run:

```bash
ruff check scripts/rd_concepts_pipeline tests/rd_concepts_pipeline
```

Expected: PASS.

- [ ] **Step 4: Update worklog**

Append a dated entry to `docs/worklog.md`:

```markdown
## 2026-05-08 - RD Concepts Research Data Lake Implementation

**Problem:** The trading bot needed an offline evidence layer for RD Concepts pair, setup, session, and rule research before PineScript tuning.

**Solution:**
- Added the isolated `scripts/rd_concepts_pipeline/` utility package
- Added Discord channel discovery, scraping, parsing, rule extraction, knowledge-base aggregation, and Streamlit browsing
- Wrote fixture-driven tests under `tests/rd_concepts_pipeline/`
- Kept generated Discord archives under ignored `data/rd_concepts/`
```

- [ ] **Step 5: Commit final verification docs**

Run:

```bash
git add docs/worklog.md
git commit -m "DEV-323: record RD Concepts pipeline implementation"
```

## Final Verification Before Handoff

- [ ] Run:

```bash
git status --short
```

Expected: only pre-existing unrelated dirty files remain, especially the existing `scripts/optimization_results` deletions. No new unstaged RD Concepts files should remain.

- [ ] Run:

```bash
PYTHONPATH=. pytest tests/rd_concepts_pipeline -v
python scripts/rd_concepts_pipeline/list_channels.py --help
python scripts/rd_concepts_pipeline/scraper.py --help
bash -n scripts/rd_concepts_pipeline/run_all.sh
```

Expected: tests pass, help text prints, shell script syntax is valid.

- [ ] Do not run a full Discord scrape until `RD_DISCORD_AUTHORIZATION` is set locally and the user confirms the channel IDs.

## Self-Review Notes

- Spec coverage: config, channel discovery, scraping, image downloads, raw JSONL, parsing, rules, concepts, knowledge base, dashboard, README, and run-all are each covered by a task.
- Credential safety: plan uses environment variables and ignored local `.env`; it never commits authorization values.
- Execution safety: plan does not touch `src/worker.py`, `src/logic.py`, MetaApi, broker adapters, or live trading state.
- Data integrity: raw archive, manifest, processed CSV/JSON/JSONL, and image index are all represented.
