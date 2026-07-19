from scripts.rd_concepts_pipeline.models import EvidenceClass
from scripts.rd_concepts_pipeline.sources import CHANNEL_SOURCES, classify_video_title


def test_registry_contains_the_six_approved_channels() -> None:
    assert [source.source_id for source in CHANNEL_SOURCES] == [
        "rd_forex",
        "arger_fx",
        "mangoe",
        "rt_futures",
        "charney_fx",
        "trirex",
    ]
    assert [source.priority for source in CHANNEL_SOURCES] == [2, 3, 3, 3, 4, 5]


def test_title_classifier_separates_rules_edges_and_operations() -> None:
    assert (
        classify_video_title("FULL course for LIQUIDITY supply and demand")
        is EvidenceClass.RULE_SOURCE
    )
    assert (
        classify_video_title("Why I Skipped These 2 Trades")
        is EvidenceClass.EDGE_EVIDENCE
    )
    assert (
        classify_video_title("Supply & Demand Liquidity Bot: Fully Automated")
        is EvidenceClass.OPERATIONS_EVIDENCE
    )
    assert (
        classify_video_title("A Year From Now You'll Wish You Started")
        is EvidenceClass.NON_RULE
    )


def test_relevant_strategy_titles_are_not_silently_dropped() -> None:
    assert (
        classify_video_title(
            "How I Increased My Win Rate Using Liquidity Supply & Demand Strategy"
        )
        is EvidenceClass.EDGE_EVIDENCE
    )
    assert (
        classify_video_title("This Is What A Perfect Supply & Demand Setup Looks Like")
        is EvidenceClass.EDGE_EVIDENCE
    )
