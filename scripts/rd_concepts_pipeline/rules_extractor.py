from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
from typing import Any

from scripts.rd_concepts_pipeline.common import ensure_dir, extract_setup_tags, get_logger, read_jsonl, write_jsonl
from scripts.rd_concepts_pipeline.config import get_settings

LOGGER = get_logger("rd_concepts.rules")
RULE_KEYWORDS = [
    "rule",
    "setup",
    "entry",
    "confluence",
    "structure",
    "mechanical",
    "condition",
    "must",
    "always",
    "never",
    "5m",
    "ema",
    "fib",
    "liquidity",
    "bos",
    "choch",
    "sweep",
    "displacement",
    "imbalance",
    "ob",
    "order block",
    "fair value gap",
    "fvg",
    "pd array",
]
KEYWORD_PATTERNS = {
    keyword: re.compile(rf"\b{re.escape(keyword)}\b", re.IGNORECASE)
    for keyword in RULE_KEYWORDS
}


def keyword_hits(content: str) -> list[str]:
    return sorted({keyword for keyword, pattern in KEYWORD_PATTERNS.items() if pattern.search(content)})


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
