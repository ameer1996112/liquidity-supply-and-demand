import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.pinescript.validation.rd_forex_compare import compare_events, load_events
from src.services.rd_forex_debug_collector import append_debug_event


VALID_EVENT = {
    "event": "ZONE_CONFIRMED_NON_EXECUTABLE",
    "run_id": "OANDA:EURUSD-5-replay-1",
    "symbol": "EURUSD",
    "feed": "OANDA",
    "timeframe": "5",
    "replay_session": "tv-bar-replay-2026-07-11",
    "zone_id": 101,
    "model": "ACC_STANDARD",
    "zone_type": "demand",
    "origin_bar": 100,
    "origin_time": 1000,
    "detection_time": 1060,
    "confirmation_bar": 104,
    "confirmation_time": 1120,
    "top": 1.101,
    "bottom": 1.099,
    "liquidity_swept": False,
    "target_swept": False,
    "touched": False,
}


class RdForexDebugCollectorTests(unittest.TestCase):
    def test_append_debug_event_writes_jsonl_and_csv_by_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch(
                "src.services.rd_forex_debug_collector.get_settings",
                return_value=SimpleNamespace(rd_forex_debug_artifact_dir=tmp),
            ):
                artifacts = append_debug_event(dict(VALID_EVENT))

            jsonl_path = Path(artifacts["jsonl_path"])
            csv_path = Path(artifacts["csv_path"])

            self.assertTrue(jsonl_path.exists())
            self.assertTrue(csv_path.exists())
            self.assertEqual(jsonl_path.parent.name, "OANDA_EURUSD-5-replay-1")

            jsonl_event = json.loads(jsonl_path.read_text(encoding="utf-8").strip())
            self.assertEqual(jsonl_event["run_id"], VALID_EVENT["run_id"])
            self.assertEqual(jsonl_event["replay_session"], VALID_EVENT["replay_session"])
            self.assertIn("received_at", jsonl_event)
            csv_text = csv_path.read_text(encoding="utf-8")
            self.assertIn("received_at,event,run_id", csv_text)
            self.assertIn("ZONE_CONFIRMED_NON_EXECUTABLE", csv_text)


class RdForexComparatorTests(unittest.TestCase):
    def test_compare_events_reports_boundary_timestamp_lifecycle_missing_and_extra(self) -> None:
        expected = [
            {
                **VALID_EVENT,
                "zone_id": "reference-1",
                "evidence": {"screenshot": "reference.png"},
            },
            {
                **VALID_EVENT,
                "origin_time": 2000,
                "zone_id": "reference-2",
                "evidence": {"screenshot": "missing.png"},
            },
        ]
        actual = [
            {
                **VALID_EVENT,
                "top": 1.1025,
                "confirmation_time": 1180,
                "liquidity_swept": True,
            },
            {
                **VALID_EVENT,
                "origin_time": 3000,
            },
        ]

        report = compare_events(expected, actual, tick_size=0.0001)

        self.assertEqual(report["summary"]["expected"], 2)
        self.assertEqual(report["summary"]["actual_confirmed"], 2)
        self.assertEqual(report["summary"]["missing"], 1)
        self.assertEqual(report["summary"]["extra"], 1)
        mismatch_types = {item["type"] for item in report["mismatches"]}
        self.assertIn("boundary", mismatch_types)
        self.assertIn("timestamp", mismatch_types)
        self.assertIn("lifecycle", mismatch_types)

    def test_compare_events_reports_duplicate_actual_confirmed_event_as_extra(self) -> None:
        expected = [
            {
                **VALID_EVENT,
                "zone_id": "reference-1",
                "evidence": {"screenshot": "reference.png"},
            }
        ]
        actual = [dict(VALID_EVENT), {**VALID_EVENT, "zone_id": 102}]

        report = compare_events(expected, actual, tick_size=0.0001)

        self.assertEqual(report["summary"]["expected"], 1)
        self.assertEqual(report["summary"]["actual_confirmed"], 2)
        self.assertEqual(report["summary"]["missing"], 0)
        self.assertEqual(report["summary"]["extra"], 1)
        self.assertEqual(report["summary"]["duplicate_actuals"], 1)
        self.assertEqual(report["extra"][0]["zone_id"], 102)
        self.assertEqual(report["duplicate_actuals"][0]["actual_count"], 2)

    def test_compare_events_reports_duplicate_fixture_key_error(self) -> None:
        expected = [
            {
                **VALID_EVENT,
                "zone_id": "reference-1",
                "evidence": {"screenshot": "reference.png"},
            },
            {
                **VALID_EVENT,
                "zone_id": "reference-duplicate",
                "evidence": {"screenshot": "reference-duplicate.png"},
            },
        ]

        report = compare_events(expected, [dict(VALID_EVENT)], tick_size=0.0001)

        self.assertEqual(report["summary"]["missing"], 1)
        self.assertIn("duplicate_fixture_key", {error["error"] for error in report["fixture_errors"]})

    def test_load_events_accepts_jsonl_exports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            path.write_text(json.dumps(VALID_EVENT) + "\n", encoding="utf-8")

            self.assertEqual(load_events(path)[0]["run_id"], VALID_EVENT["run_id"])


if __name__ == "__main__":
    unittest.main()
