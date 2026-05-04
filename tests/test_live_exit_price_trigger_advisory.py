from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.adapters.execution.interfaces import ExecutionResult


def test_live_tp_exit_webhook_does_not_market_close_broker_position() -> None:
    from src import logic

    class RecordingAdapter:
        def __init__(self) -> None:
            self.close_order = MagicMock(
                return_value=ExecutionResult(
                    status="filled",
                    broker_order_id="90320867",
                    client_order_id="USDJPY|buy|17742|1777881018000",
                    message="closed",
                )
            )

    adapter = RecordingAdapter()
    alert = {
        "id": 538,
        "symbol": "USDJPY",
        "side": "buy",
        "size": 2.85,
        "status": "OPEN",
        "broker_order_id": "90320867",
    }
    payload = {
        "event_type": "exit",
        "symbol": "USDJPY",
        "side": "buy",
        "run_mode": "LIVE",
        "zone_id": 17742,
        "trade_key": "USDJPY|buy|17742|1777881018000",
        "outcome": "win",
        "close_price": 157.136,
        "exit_type": "tp_hit",
        "mae_pips": 0,
        "bars_held": 12,
    }

    with patch("src.logic.init_supabase"), patch(
        "src.logic.get_settings",
        return_value=SimpleNamespace(run_mode="LIVE", live_trading_enabled=True),
    ), patch("src.logic.get_adapter", return_value=adapter), patch(
        "src.logic.get_alert_by_trade_key", return_value=alert
    ), patch("src.logic.get_alert_by_zone_id", return_value=alert), patch(
        "src.logic.update_alert_exit"
    ) as update_exit, patch(
        "src.logic._update_alert_exit_for_signal_id"
    ) as update_exit_by_id, patch(
        "src.logic.log_event"
    ), patch(
        "src.logic.NotificationService"
    ), patch(
        "src.logic.dispatch_payload_async"
    ):
        logic.process_trade(payload, dry_run=False, ai_result=None, profile=None)

    adapter.close_order.assert_not_called()
    update_exit.assert_not_called()
    update_exit_by_id.assert_not_called()
