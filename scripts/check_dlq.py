#!/usr/bin/env python3
"""Check dead letter queue for failed signals."""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.adapters.redis_queue import get_dead_letters, DEAD_LETTER_QUEUE, get_redis
import json
from datetime import datetime

def main():
    """Display all dead letter items."""
    print(f"\n{'='*80}")
    print(f"Dead Letter Queue: {DEAD_LETTER_QUEUE}")
    print(f"{'='*80}\n")

    # Get queue length
    r = get_redis()
    dlq_count = r.llen(DEAD_LETTER_QUEUE)
    print(f"Total items in DLQ: {dlq_count}\n")

    if dlq_count == 0:
        print("✅ No failed items in queue!")
        return

    # Get all dead letters
    dead_letters = get_dead_letters(limit=100)

    for i, dl in enumerate(dead_letters, 1):
        print(f"{'─'*80}")
        print(f"Item #{i} - ID: {dl.get('id')}")
        print(f"{'─'*80}")

        # Parse timestamp
        failed_at = dl.get('failed_at')
        if failed_at:
            dt = datetime.fromtimestamp(failed_at)
            print(f"Failed at:  {dt.strftime('%Y-%m-%d %H:%M:%S')}")

        print(f"Attempt:    {dl.get('attempt', 'N/A')}")
        print(f"Error:      {dl.get('error', 'N/A')}")

        # Show payload details
        payload = dl.get('payload', {})
        if isinstance(payload, dict):
            print(f"\nPayload Details:")
            print(f"  Symbol:     {payload.get('symbol', 'N/A')}")
            print(f"  Direction:  {payload.get('direction', 'N/A')}")
            print(f"  Size:       {payload.get('size', 'N/A')}")
            print(f"  Entry:      {payload.get('entry', 'N/A')}")
            print(f"  SL:         {payload.get('sl', 'N/A')}")
            print(f"  TP:         {payload.get('tp', 'N/A')}")
            print(f"  Run Mode:   {payload.get('run_mode', 'N/A')}")

        print(f"\nFull Payload:\n{json.dumps(payload, indent=2)}")
        print()

    print(f"\n{'='*80}")
    print(f"To clear items from DLQ:")
    print(f"  1. Fix the underlying issue causing failures")
    print(f"  2. Use pop_dead_letter_by_id() to remove specific items")
    print(f"  3. Or manually clear Redis: redis-cli DEL {DEAD_LETTER_QUEUE}")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    main()
