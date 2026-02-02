"""External service connections: Supabase, Discord, Redis, execution, paper."""

from src.adapters.supabase import (
    init_supabase,
    save_alert,
    update_alert_exit,
    update_alert_status,
    get_alert_by_trade_key,
    supabase,
)
from src.adapters.redis_queue import get_redis, QUEUE_NAME

__all__ = [
    "init_supabase",
    "save_alert",
    "update_alert_exit",
    "update_alert_status",
    "get_alert_by_trade_key",
    "supabase",
    "get_redis",
    "QUEUE_NAME",
]
