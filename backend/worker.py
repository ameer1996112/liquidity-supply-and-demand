"""
Trade Executor (Consumer).
Loop: blpop trading_queue -> parse JSON -> logic.process_trade(data).
On failure: log to Supabase as status=FAILED (execution_failed) and continue; worker never crashes.
"""

import json
import logging
import os
import sys
from pathlib import Path

# Ensure backend is on path and .env is loaded
_backend = Path(__file__).resolve().parent
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))
os.chdir(_backend)

from dotenv import load_dotenv
load_dotenv(_backend / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

QUEUE_NAME = "trading_queue"


def run():
    from config import get_settings
    import redis
    import logic
    import supabase_db

    s = get_settings()
    r = redis.from_url(s.redis_url, decode_responses=True)
    logger.info("Worker started; listening on queue=%s", QUEUE_NAME)

    while True:
        try:
            # Block until a message is available
            result = r.blpop(QUEUE_NAME, timeout=30)
            if result is None:
                continue
            _key, payload_str = result
            data = json.loads(payload_str)
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON from queue: %s", e)
            continue
        except Exception as e:
            logger.exception("Queue read error: %s", e)
            continue

        # Broad try/except: never let the worker process crash
        try:
            logic.process_trade(data)
        except Exception as e:
            logger.exception("EXECUTION_FAILED: %s", e)
            try:
                supabase_db.log_execution_failure(data, str(e))
            except Exception as log_err:
                logger.error("Failed to log EXECUTION_FAILED to Supabase: %s", log_err)


if __name__ == "__main__":
    run()
