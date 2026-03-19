"""
Latency Tracker - Phase 1 Optimization Instrumentation

Provides detailed latency breakdown logging for execution pipeline.
Helps identify bottlenecks and measure optimization impact.

Usage:
    tracker = LatencyTracker()
    tracker.checkpoint("after_staleness_guard")
    tracker.checkpoint("after_ai_supervisor")
    tracker.report()
"""

import logging
import time
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class LatencyTracker:
    """Track execution latency across multiple checkpoints."""

    def __init__(self, enabled: bool = True):
        """
        Initialize latency tracker.

        Args:
            enabled: Whether to track latency (disable in production if too verbose)
        """
        self.enabled = enabled
        self.start_time = time.perf_counter()
        self.checkpoints: Dict[str, float] = {}
        self.metadata: Dict[str, any] = {}

    def checkpoint(self, name: str) -> float:
        """
        Record a checkpoint with current elapsed time.

        Args:
            name: Checkpoint name (e.g., "after_staleness_guard")

        Returns:
            Delta time since last checkpoint in milliseconds
        """
        if not self.enabled:
            return 0.0

        current_time = time.perf_counter() - self.start_time
        self.checkpoints[name] = current_time

        # Calculate delta from previous checkpoint
        if len(self.checkpoints) == 1:
            delta_ms = current_time * 1000
        else:
            prev_time = list(self.checkpoints.values())[-2]
            delta_ms = (current_time - prev_time) * 1000

        return delta_ms

    def set_metadata(self, key: str, value: any) -> None:
        """
        Attach metadata to this execution trace.

        Args:
            key: Metadata key
            value: Metadata value
        """
        self.metadata[key] = value

    def get_total_ms(self) -> float:
        """Get total elapsed time in milliseconds."""
        if not self.enabled:
            return 0.0
        return (time.perf_counter() - self.start_time) * 1000

    def report(self, symbol: Optional[str] = None, log_level: int = logging.INFO) -> None:
        """
        Log detailed latency breakdown.

        Args:
            symbol: Optional symbol name for context
            log_level: Logging level (default: INFO)
        """
        if not self.enabled or not self.checkpoints:
            return

        total_ms = self.get_total_ms()
        symbol_str = f"[{symbol}] " if symbol else ""

        logger.log(log_level, f"{'='*70}")
        logger.log(log_level, f"{symbol_str}LATENCY BREAKDOWN (Total: {total_ms:.0f}ms)")
        logger.log(log_level, f"{'='*70}")

        prev_time = 0.0
        for name, total_time in self.checkpoints.items():
            delta_ms = (total_time - prev_time) * 1000
            total_time_ms = total_time * 1000
            pct = (delta_ms / total_ms * 100) if total_ms > 0 else 0

            # Add visual indicator for slow stages (>500ms)
            indicator = "⚠️ SLOW" if delta_ms > 500 else ("🐌" if delta_ms > 200 else "")

            logger.log(
                log_level,
                f"  {name:30s} +{delta_ms:6.0f}ms ({pct:5.1f}%) → {total_time_ms:6.0f}ms {indicator}"
            )
            prev_time = total_time

        # Add metadata summary
        if self.metadata:
            logger.log(log_level, "\n  Metadata:")
            for key, value in self.metadata.items():
                logger.log(log_level, f"    {key}: {value}")

        logger.log(log_level, f"{'='*70}\n")

    def get_summary(self) -> Dict[str, float]:
        """
        Get summary dict for structured logging.

        Returns:
            Dict with total_ms and checkpoint deltas
        """
        if not self.enabled:
            return {}

        summary = {"total_ms": self.get_total_ms()}

        prev_time = 0.0
        for name, total_time in self.checkpoints.items():
            delta_ms = (total_time - prev_time) * 1000
            summary[f"{name}_delta_ms"] = round(delta_ms, 1)
            prev_time = total_time

        summary.update(self.metadata)
        return summary
