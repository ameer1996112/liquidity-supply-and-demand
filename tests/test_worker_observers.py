"""
Tests for the Observer-based worker pipeline (P0-1).

Covers:
  - TradeEvent is immutable (frozen dataclass)
  - WorkerSubject emits SIGNAL_RECEIVED then ORDER_SUBMITTED on success
  - WorkerSubject emits SIGNAL_RECEIVED then ERROR on process_fn failure
  - correlation_id is injected into the payload and matches both events
  - Multiple observers all receive every event
  - Observer that raises does NOT interrupt the pipeline or other observers
  - AuditorObserver calls log_event with correlation_id + event_type
  - Stub observers (Risk, Executor, Metrics) do not raise
  - Integration: full SIGNAL_RECEIVED → ORDER_SUBMITTED lifecycle with
    a real process_fn mock — verifies event ordering and payload fields
"""

import time
import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import MagicMock, call, patch

from src.core.observers.base import (
    ERROR,
    ORDER_SUBMITTED,
    SIGNAL_RECEIVED,
    Observer,
    TradeEvent,
    WorkerSubject,
)
from src.core.observers.auditor import AuditorObserver
from src.core.observers.executor import ExecutorObserver
from src.core.observers.metrics import MetricsObserver
from src.core.observers.risk_observer import RiskObserver


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_payload(**extra):
    return {
        "symbol": "XAUUSD",
        "side": "buy",
        "entry": 2500.0,
        "sl": 2490.0,
        "tp": 2530.0,
        "size": 0.1,
        "run_mode": "PAPER",
        **extra,
    }


class _CapturingObserver(Observer):
    """Records every event it receives."""

    def __init__(self):
        self.events = []

    def on_event(self, event: TradeEvent) -> None:
        self.events.append(event)


class _BrokenObserver(Observer):
    """Always raises — used to test swallowing."""

    def on_event(self, event: TradeEvent) -> None:
        raise RuntimeError("observer exploded")


# ═══════════════════════════════════════════════════════════════
# TradeEvent
# ═══════════════════════════════════════════════════════════════


class TradeEventTests(unittest.TestCase):
    def _make(self, **kw):
        defaults = dict(
            event_type=SIGNAL_RECEIVED,
            correlation_id="abc123",
            payload={"symbol": "XAUUSD"},
            timestamp=time.time(),
            metadata={},
        )
        defaults.update(kw)
        return TradeEvent(**defaults)

    def test_is_frozen(self):
        evt = self._make()
        with self.assertRaises((FrozenInstanceError, TypeError)):
            evt.event_type = "MUTATED"  # type: ignore[misc]

    def test_fields_accessible(self):
        evt = self._make(correlation_id="cid1", metadata={"k": "v"})
        self.assertEqual(evt.correlation_id, "cid1")
        self.assertEqual(evt.metadata["k"], "v")

    def test_default_metadata_is_empty_dict(self):
        evt = TradeEvent(
            event_type=SIGNAL_RECEIVED,
            correlation_id="x",
            payload={},
            timestamp=0.0,
        )
        self.assertEqual(evt.metadata, {})


# ═══════════════════════════════════════════════════════════════
# WorkerSubject — event emission
# ═══════════════════════════════════════════════════════════════


class WorkerSubjectEventTests(unittest.TestCase):
    def _subject_with_capture(self, process_fn):
        cap = _CapturingObserver()
        s = WorkerSubject(process_fn=process_fn)
        s.attach(cap)
        return s, cap

    def test_success_emits_received_then_submitted(self):
        s, cap = self._subject_with_capture(lambda p: None)
        s.process_signal(_make_payload())

        self.assertEqual(len(cap.events), 2)
        self.assertEqual(cap.events[0].event_type, SIGNAL_RECEIVED)
        self.assertEqual(cap.events[1].event_type, ORDER_SUBMITTED)

    def test_failure_emits_received_then_error(self):
        def boom(payload):
            raise ValueError("process failed")

        s, cap = self._subject_with_capture(boom)
        with self.assertRaises(ValueError):
            s.process_signal(_make_payload())

        self.assertEqual(len(cap.events), 2)
        self.assertEqual(cap.events[0].event_type, SIGNAL_RECEIVED)
        self.assertEqual(cap.events[1].event_type, ERROR)

    def test_error_event_contains_exception_text(self):
        def boom(payload):
            raise RuntimeError("kaboom")

        s, cap = self._subject_with_capture(boom)
        with self.assertRaises(RuntimeError):
            s.process_signal(_make_payload())

        err_event = cap.events[1]
        self.assertIn("kaboom", err_event.metadata["error"])
        self.assertEqual(err_event.metadata["error_type"], "RuntimeError")

    def test_exception_propagates_after_error_event(self):
        def boom(payload):
            raise KeyError("missing field")

        s, cap = self._subject_with_capture(boom)
        with self.assertRaises(KeyError):
            s.process_signal(_make_payload())

    def test_process_fn_called_with_payload(self):
        received = []
        s, _ = self._subject_with_capture(lambda p: received.append(dict(p)))
        payload = _make_payload()
        s.process_signal(payload)
        self.assertEqual(received[0]["symbol"], "XAUUSD")

    def test_timestamps_are_monotone(self):
        s, cap = self._subject_with_capture(lambda p: None)
        s.process_signal(_make_payload())
        self.assertLessEqual(cap.events[0].timestamp, cap.events[1].timestamp)


# ═══════════════════════════════════════════════════════════════
# WorkerSubject — correlation_id
# ═══════════════════════════════════════════════════════════════


class CorrelationIdTests(unittest.TestCase):
    def test_both_events_share_correlation_id(self):
        cap = _CapturingObserver()
        s = WorkerSubject(process_fn=lambda p: None)
        s.attach(cap)
        s.process_signal(_make_payload())

        cid0 = cap.events[0].correlation_id
        cid1 = cap.events[1].correlation_id
        self.assertEqual(cid0, cid1)
        self.assertTrue(len(cid0) == 32)   # uuid4().hex

    def test_distinct_signals_get_distinct_correlation_ids(self):
        cids = []

        class CidCapture(Observer):
            def on_event(self, event):
                if event.event_type == SIGNAL_RECEIVED:
                    cids.append(event.correlation_id)

        s = WorkerSubject(process_fn=lambda p: None)
        s.attach(CidCapture())
        s.process_signal(_make_payload())
        s.process_signal(_make_payload())

        self.assertNotEqual(cids[0], cids[1])

    def test_correlation_id_injected_into_payload(self):
        captured_payload = {}

        def capture(p):
            captured_payload.update(p)

        s = WorkerSubject(process_fn=capture)
        s.process_signal(_make_payload())
        self.assertIn("_correlation_id", captured_payload)
        self.assertEqual(len(captured_payload["_correlation_id"]), 32)


# ═══════════════════════════════════════════════════════════════
# WorkerSubject — observer fan-out
# ═══════════════════════════════════════════════════════════════


class FanOutTests(unittest.TestCase):
    def test_multiple_observers_all_receive_events(self):
        caps = [_CapturingObserver(), _CapturingObserver(), _CapturingObserver()]
        s = WorkerSubject(process_fn=lambda p: None)
        for c in caps:
            s.attach(c)
        s.process_signal(_make_payload())

        for cap in caps:
            self.assertEqual(len(cap.events), 2)

    def test_broken_observer_does_not_stop_pipeline(self):
        broken = _BrokenObserver()
        good = _CapturingObserver()
        s = WorkerSubject(process_fn=lambda p: None)
        s.attach(broken)
        s.attach(good)

        s.process_signal(_make_payload())   # must not raise
        # good observer still got all events
        self.assertEqual(len(good.events), 2)

    def test_broken_observer_does_not_prevent_process_fn_from_running(self):
        called = []
        broken = _BrokenObserver()
        s = WorkerSubject(process_fn=lambda p: called.append(1))
        s.attach(broken)
        s.process_signal(_make_payload())
        self.assertEqual(called, [1])

    def test_detach_removes_observer(self):
        cap = _CapturingObserver()
        s = WorkerSubject(process_fn=lambda p: None)
        s.attach(cap)
        s.detach(cap)
        s.process_signal(_make_payload())
        self.assertEqual(len(cap.events), 0)


# ═══════════════════════════════════════════════════════════════
# AuditorObserver
# ═══════════════════════════════════════════════════════════════


class AuditorObserverTests(unittest.TestCase):
    def _run(self, process_fn, log_mock):
        auditor = AuditorObserver()
        s = WorkerSubject(process_fn=process_fn)
        s.attach(auditor)
        with patch("src.core.observers.auditor.log_event", log_mock):
            try:
                s.process_signal(_make_payload())
            except Exception:
                pass

    def test_logs_signal_received(self):
        mock = MagicMock()
        self._run(lambda p: None, mock)
        calls = [c for c in mock.call_args_list if "signal_received" in str(c)]
        self.assertTrue(len(calls) >= 1)

    def test_logs_order_submitted(self):
        mock = MagicMock()
        self._run(lambda p: None, mock)
        calls = [c for c in mock.call_args_list if "order_submitted" in str(c)]
        self.assertTrue(len(calls) >= 1)

    def test_logs_error_on_failure(self):
        mock = MagicMock()
        self._run(lambda p: (_ for _ in ()).throw(RuntimeError("bad")), mock)
        calls = [c for c in mock.call_args_list if "error" in str(c)]
        self.assertTrue(len(calls) >= 1)

    def test_correlation_id_in_metadata(self):
        captured_meta = []

        def capturing_log(signal_id, event_type, stage, metadata=None):
            capturing_meta = metadata or {}
            if "correlation_id" in capturing_meta:
                captured_meta.append(capturing_meta["correlation_id"])

        self._run(lambda p: None, capturing_log)
        self.assertTrue(len(captured_meta) >= 1)
        self.assertEqual(len(captured_meta[0]), 32)

    def test_auditor_never_raises(self):
        def broken_log(*a, **kw):
            raise RuntimeError("db down")

        auditor = AuditorObserver()
        evt = TradeEvent(
            event_type=SIGNAL_RECEIVED,
            correlation_id="abc",
            payload={},
            timestamp=time.time(),
            metadata={},
        )
        with patch("src.core.observers.auditor.log_event", broken_log):
            auditor.on_event(evt)  # must not raise


# ═══════════════════════════════════════════════════════════════
# Stub observers (should not raise on any event type)
# ═══════════════════════════════════════════════════════════════


class StubObserverTests(unittest.TestCase):
    def _all_events(self):
        return [
            TradeEvent(et, "cid", {"symbol": "XAUUSD"}, time.time(), {})
            for et in (SIGNAL_RECEIVED, ORDER_SUBMITTED, ERROR)
        ]

    def test_risk_observer_does_not_raise(self):
        obs = RiskObserver()
        for evt in self._all_events():
            obs.on_event(evt)

    def test_executor_observer_does_not_raise(self):
        obs = ExecutorObserver()
        for evt in self._all_events():
            obs.on_event(evt)

    def test_metrics_observer_does_not_raise(self):
        obs = MetricsObserver()
        for evt in self._all_events():
            obs.on_event(evt)


# ═══════════════════════════════════════════════════════════════
# Integration: full pipeline lifecycle
# ═══════════════════════════════════════════════════════════════


class PipelineIntegrationTests(unittest.TestCase):
    """Simulates what happens in the worker loop after P0-1.

    process_fn is a mock — verifies that the observer layer passes the
    correct payload through and produces the right event sequence.
    """

    def test_happy_path_event_sequence(self):
        """SIGNAL_RECEIVED → process_fn called → ORDER_SUBMITTED."""
        events = []
        process_mock = MagicMock()

        class Recorder(Observer):
            def on_event(self, event):
                events.append(event.event_type)

        s = WorkerSubject(process_fn=process_mock)
        s.attach(Recorder())

        payload = _make_payload()
        s.process_signal(payload)

        self.assertEqual(events, [SIGNAL_RECEIVED, ORDER_SUBMITTED])
        process_mock.assert_called_once()
        # payload passed to process_fn must contain the original fields
        called_payload = process_mock.call_args[0][0]
        self.assertEqual(called_payload["symbol"], "XAUUSD")
        self.assertEqual(called_payload["side"], "buy")

    def test_error_path_event_sequence(self):
        """SIGNAL_RECEIVED → process_fn raises → ERROR → exception propagates."""
        events = []

        class Recorder(Observer):
            def on_event(self, event):
                events.append(event.event_type)

        s = WorkerSubject(process_fn=lambda p: (_ for _ in ()).throw(RuntimeError("oops")))
        s.attach(Recorder())

        with self.assertRaises(RuntimeError):
            s.process_signal(_make_payload())

        self.assertEqual(events, [SIGNAL_RECEIVED, ERROR])

    def test_four_observers_in_production_config(self):
        """Same observer set as worker.run() — must complete without error."""
        auditor = AuditorObserver()
        risk = RiskObserver()
        executor = ExecutorObserver()
        metrics = MetricsObserver()

        s = WorkerSubject(process_fn=lambda p: None)
        s.attach(auditor)
        s.attach(risk)
        s.attach(executor)
        s.attach(metrics)

        with patch("src.core.observers.auditor.log_event"):
            s.process_signal(_make_payload())   # must not raise

    def test_correlation_id_links_received_and_submitted_events(self):
        events = []

        class Recorder(Observer):
            def on_event(self, event):
                events.append(event)

        s = WorkerSubject(process_fn=lambda p: None)
        s.attach(Recorder())
        s.process_signal(_make_payload())

        cids = {e.correlation_id for e in events}
        self.assertEqual(len(cids), 1, "All events must share one correlation_id")

    def test_payload_snapshot_in_event_is_independent_of_mutations(self):
        """Mutating the payload after emission must not affect the event's copy."""
        captured_event = []

        class Snapshot(Observer):
            def on_event(self, event):
                if event.event_type == SIGNAL_RECEIVED:
                    captured_event.append(event)

        payload = _make_payload()

        def mutating_process(p):
            p["symbol"] = "MUTATED"   # mutate inside process_fn

        s = WorkerSubject(process_fn=mutating_process)
        s.attach(Snapshot())
        s.process_signal(payload)

        # The snapshot taken at SIGNAL_RECEIVED must still have original symbol
        self.assertEqual(captured_event[0].payload["symbol"], "XAUUSD")


if __name__ == "__main__":
    unittest.main()
