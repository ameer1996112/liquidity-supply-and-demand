from __future__ import annotations

import json

import pandas as pd

from scripts.rd_concepts_pipeline.knowledge_base import _as_list, build_knowledge_base


def test_build_knowledge_base_summarizes_dashboard_fields() -> None:
    signals = pd.DataFrame(
        [
            {
                "pair": "EURUSD",
                "side": "long",
                "timeframe": "5m",
                "channel": "5m-signals",
                "session": "london",
                "setup_tags": ["liquidity", "fvg"],
                "chart_paths": ["a.png"],
            },
            {
                "pair": "EURUSD",
                "side": "short",
                "timeframe": "5m",
                "channel": "5m-signals",
                "session": "ny_overlap",
                "setup_tags": ["bos"],
                "chart_paths": [],
            },
            {
                "pair": "GBPUSD",
                "side": "short",
                "timeframe": "30m",
                "channel": "30m-signals",
                "session": "ny_overlap",
                "setup_tags": ["order_block"],
                "chart_paths": [],
            },
        ]
    )
    rules = [{"concept_tags": ["liquidity"], "rule_id": "rules:1"}]
    concepts = {"liquidity": {"count": 2, "examples": ["rules:1"]}}

    kb = build_knowledge_base(signals, rules, concepts)

    assert kb["pairs"]["EURUSD"]["total_signals"] == 2
    assert kb["pairs"]["EURUSD"]["long_percent"] == 50.0
    assert kb["timeframes"]["5m"] == 2
    assert kb["concepts"]["liquidity"]["count"] == 2


def test_as_list_parses_common_parser_shapes() -> None:
    assert _as_list("['liquidity', 'fvg']") == ["liquidity", "fvg"]
    assert _as_list("liquidity, fvg") == ["liquidity", "fvg"]
    assert _as_list("") == []
    assert _as_list("   ") == []
    assert _as_list(pd.NA) == []
    assert _as_list(float("nan")) == []


def test_build_knowledge_base_skips_blank_grouping_keys_and_is_json_serializable() -> None:
    signals = pd.DataFrame(
        [
            {
                "pair": pd.NA,
                "side": "long",
                "timeframe": "",
                "channel": float("nan"),
                "session": "",
                "setup_tags": "",
                "chart_paths": "",
            },
            {
                "pair": "EURUSD",
                "side": "long",
                "timeframe": "5m",
                "channel": "5m-signals",
                "session": pd.NA,
                "setup_tags": "liquidity, fvg",
                "chart_paths": "a.png, b.png",
            },
        ]
    )

    kb = build_knowledge_base(signals, [], {})

    assert "nan" not in kb["pairs"]
    assert "" not in kb["pairs"]
    assert kb["pairs"]["EURUSD"]["setup_tags"] == ["fvg", "liquidity"]
    assert kb["pairs"]["EURUSD"]["chart_paths"] == ["a.png", "b.png"]
    assert kb["timeframes"] == {"5m": 1}
    assert kb["channels"] == {"5m-signals": 1}
    json.dumps(kb)
