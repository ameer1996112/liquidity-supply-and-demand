"""Tests for consumer-side payload validation (P0-3).

Verifies:
  - Invalid JSON in queue  → dead-lettered + audit event, returns None
  - Schema violation       → dead-lettered + audit event, returns None
  - Valid entry payload    → returns parsed dict, no dead-letter
  - Valid exit payload     → returns parsed dict, no dead-letter
  - Audit event carries error_code + payload_hash
  - Dead-letter / audit failures are swallowed (never raise)
"""

import hashlib
import json
import unittest

from src.core.consumer_validator import _payload_hash, validate_dequeued_message
from src.core.transport import InMemoryTransport


def _make_audit_spy():
    """Return (spy_fn, calls_list) — collects log_event calls."""
    calls = []

    def spy(signal_id, event_type, stage, metadata=None):
        calls.append({"signal_id": signal_id, "event_type": event_type, "stage": stage, "metadata": metadata or {}})

    return spy, calls


VALID_ENTRY = {
    "symbol": "XAUUSD",
    "side": "buy",
    "entry": 2500.0,
    "sl": 2490.0,
    "tp": 2530.0,
    "size": 0.1,
}

VALID_EXIT = {
    "event_type": "exit",
    "zone_id": 12345,
    "outcome": "win",
    "bars_held": 8,
    "close_price": 2530.0,
    "exit_type": "tp",
    "mae_pips": 3.2,
}


class PayloadHashTests(unittest.TestCase):
    def test_deterministic(self):
        raw = '{"symbol":"XAUUSD"}'
        self.assertEqual(_payload_hash(raw), _payload_hash(raw))

    def test_length_16(self):
        self.assertEqual(len(_payload_hash("anything")), 16)

    def test_matches_sha256(self):
        raw = '{"symbol":"EURUSD"}'
        expected = hashlib.sha256(raw.encode()).hexdigest()[:16]
        self.assertEqual(_payload_hash(raw), expected)

    def test_different_payloads_different_hashes(self):
        self.assertNotEqual(_payload_hash('{"a":1}'), _payload_hash('{"a":2}'))


class InvalidJsonTests(unittest.TestCase):
    def setUp(self):
        self.transport = InMemoryTransport()
        self.spy, self.calls = _make_audit_spy()

    def _run(self, raw: str):
        return validate_dequeued_message(raw, self.transport, log_event_fn=self.spy)

    def test_returns_none_for_bad_json(self):
        self.assertIsNone(self._run("{not valid json"))

    def test_dead_letters_bad_json(self):
        self._run("{not valid json")
        self.assertEqual(len(self.transport.dead_letters), 1)
        self.assertIn("INVALID_JSON", self.transport.dead_letters[0]["error"])

    def test_audit_event_for_bad_json(self):
        self._run("{not valid json")
        self.assertEqual(len(self.calls), 1)
        evt = self.calls[0]
        self.assertEqual(evt["event_type"], "consumer_validation_failed")
        self.assertEqual(evt["stage"], "consumer_validator")
        self.assertEqual(evt["metadata"]["error_code"], "INVALID_JSON")
        self.assertIn("payload_hash", evt["metadata"])
        self.assertEqual(len(evt["metadata"]["payload_hash"]), 16)

    def test_completely_empty_string(self):
        self.assertIsNone(self._run(""))
        self.assertEqual(len(self.transport.dead_letters), 1)

    def test_non_object_json(self):
        self.assertIsNone(self._run("[1, 2, 3]"))
        self.assertEqual(len(self.transport.dead_letters), 1)

    def test_queue_stays_empty_after_rejection(self):
        self._run("{bad")
        self.assertEqual(self.transport.queue_size, 0)


class SchemaViolationTests(unittest.TestCase):
    def setUp(self):
        self.transport = InMemoryTransport()
        self.spy, self.calls = _make_audit_spy()

    def _run(self, data: dict):
        return validate_dequeued_message(json.dumps(data), self.transport, log_event_fn=self.spy)

    def test_missing_required_field_returns_none(self):
        bad = {k: v for k, v in VALID_ENTRY.items() if k != "symbol"}
        self.assertIsNone(self._run(bad))

    def test_missing_required_field_dead_letters(self):
        bad = {k: v for k, v in VALID_ENTRY.items() if k != "sl"}
        self._run(bad)
        self.assertEqual(len(self.transport.dead_letters), 1)
        self.assertIn("SCHEMA_VIOLATION", self.transport.dead_letters[0]["error"])

    def test_audit_event_for_schema_violation(self):
        bad = {k: v for k, v in VALID_ENTRY.items() if k != "tp"}
        self._run(bad)
        self.assertEqual(len(self.calls), 1)
        evt = self.calls[0]
        self.assertEqual(evt["event_type"], "consumer_validation_failed")
        self.assertEqual(evt["metadata"]["error_code"], "SCHEMA_VIOLATION")

    def test_invalid_side_value(self):
        bad = {**VALID_ENTRY, "side": "long"}
        self.assertIsNone(self._run(bad))
        self.assertEqual(self.calls[0]["metadata"]["error_code"], "SCHEMA_VIOLATION")

    def test_invalid_exit_missing_zone_id(self):
        bad = {k: v for k, v in VALID_EXIT.items() if k != "zone_id"}
        self.assertIsNone(self._run(bad))
        self.assertEqual(self.transport.dead_letters[0]["error"].split(":")[0], "SCHEMA_VIOLATION")

    def test_payload_hash_stable_across_whitespace(self):
        raw = json.dumps(VALID_ENTRY)
        self.spy2, calls2 = _make_audit_spy()
        bad = json.dumps({k: v for k, v in VALID_ENTRY.items() if k != "symbol"})
        validate_dequeued_message(bad, self.transport, log_event_fn=self.spy)
        h = self.calls[0]["metadata"]["payload_hash"]
        self.assertEqual(h, _payload_hash(bad))


class ValidPayloadTests(unittest.TestCase):
    def setUp(self):
        self.transport = InMemoryTransport()
        self.spy, self.calls = _make_audit_spy()

    def _run(self, data: dict):
        return validate_dequeued_message(json.dumps(data), self.transport, log_event_fn=self.spy)

    def test_valid_entry_returns_dict(self):
        result = self._run(VALID_ENTRY)
        self.assertIsNotNone(result)
        self.assertEqual(result["symbol"], "XAUUSD")
        self.assertEqual(result["side"], "buy")

    def test_valid_entry_no_dead_letter(self):
        self._run(VALID_ENTRY)
        self.assertEqual(len(self.transport.dead_letters), 0)

    def test_valid_entry_no_audit_event(self):
        self._run(VALID_ENTRY)
        self.assertEqual(len(self.calls), 0)

    def test_valid_exit_returns_dict(self):
        result = self._run(VALID_EXIT)
        self.assertIsNotNone(result)
        self.assertEqual(result["event_type"], "exit")
        self.assertEqual(result["zone_id"], 12345)

    def test_valid_exit_no_dead_letter(self):
        self._run(VALID_EXIT)
        self.assertEqual(len(self.transport.dead_letters), 0)

    def test_extra_fields_are_preserved(self):
        payload = {**VALID_ENTRY, "score": 85, "zone_grade": "A"}
        result = self._run(payload)
        self.assertIsNotNone(result)
        self.assertEqual(result["score"], 85)
        self.assertEqual(result["zone_grade"], "A")


class RobustnessTests(unittest.TestCase):
    """Validator must never raise even if transport/audit fails."""

    def test_dead_letter_failure_is_swallowed(self):
        class BrokenTransport:
            def dead_letter(self, *a, **kw):
                raise RuntimeError("transport exploded")

        def silent_audit(*a, **kw):
            pass

        result = validate_dequeued_message(
            "{not json}", BrokenTransport(), log_event_fn=silent_audit
        )
        self.assertIsNone(result)

    def test_audit_failure_is_swallowed(self):
        transport = InMemoryTransport()

        def broken_audit(*a, **kw):
            raise RuntimeError("audit exploded")

        result = validate_dequeued_message(
            "{not json}", transport, log_event_fn=broken_audit
        )
        self.assertIsNone(result)
        self.assertEqual(len(transport.dead_letters), 1)


if __name__ == "__main__":
    unittest.main()
