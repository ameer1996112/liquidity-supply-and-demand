"""External service connections: Supabase, Discord, Redis, execution, paper."""

from src.adapters.supabase import (
    init_supabase,
    save_alert,
    update_alert_exit,
    update_alert_status,
    get_alert_by_trade_key,
)
import src.adapters.supabase as supabase  # expose module, not Client instance
from src.adapters.redis_queue import get_redis, QUEUE_NAME

__all__ = [
    "init_supabase",
    "save_alert",
    "update_alert_exit",
    "update_alert_status",
    "get_alert_by_trade_key",
    "supabase",  # module
    "get_redis",
    "QUEUE_NAME",
]
