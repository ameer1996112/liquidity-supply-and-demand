from scripts.optimizer.candidate_state import CandidateStateStore


def test_candidate_state_decays_after_weak_periods(tmp_path) -> None:
    store = CandidateStateStore(tmp_path / "candidate_state.json", tmp_path / "history.jsonl")

    assert store.transition("USDCAD", validation_passed=True, reasons=["forward ok"]) == "ACTIVE"
    assert store.transition("USDCAD", latest_30d_weak=True, reasons=["30d weak"]) == "WATCH"
    assert store.transition("USDCAD", latest_30d_weak=True, reasons=["second weak"]) == "PROBATION"
    assert store.transition("USDCAD", validation_failed=True, reasons=["failed"]) == "BLOCKED"

    assert (tmp_path / "history.jsonl").read_text().count("USDCAD") == 4
