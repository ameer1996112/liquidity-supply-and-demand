from __future__ import annotations

import pandas as pd

from scripts.rd_concepts_pipeline.knowledge_base import build_knowledge_base


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
