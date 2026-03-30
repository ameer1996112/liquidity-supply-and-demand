import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock
from src.services.digest_service import DigestService

def test_aggregate_performance_zero_trades():
    # Mock supabase returning empty data
    mock_supabase = MagicMock()
    mock_supabase.table().select().in_().gte().lte().execute.return_value = MagicMock(data=[])
    
    service = DigestService(supabase=mock_supabase)
    report = service.aggregate_daily_performance()
    
    assert report is None

def test_aggregate_performance_math():
    mock_supabase = MagicMock()
    # Provide mocking for 3 trades on "Account A" and 1 trade on "Account B"
    mock_exit_time = datetime.now(timezone.utc).isoformat()
    mock_supabase.table().select().in_().gte().lte().execute.return_value = MagicMock(data=[
        {"account_name": "Account A", "pnl_usd": 100, "commission": -5, "swap": -2, "exit_price": 1.1}, # Win
        {"account_name": "Account A", "pnl_usd": -50, "commission": -2, "swap": 0, "exit_price": 1.1},   # Loss
        {"account_name": "Account A", "pnl_usd": 200, "commission": -10, "swap": 5, "exit_price": 1.1},  # Win
        {"account_name": "Account B", "pnl_usd": -100, "commission": -5, "swap": 0, "exit_price": 1.1},  # Loss
    ])
    
    service = DigestService(supabase=mock_supabase)
    report = service.aggregate_daily_performance()
    
    assert report is not None
    assert "Account A" in report
    assert "Account B" in report
    
    # Account A Math: Net PnL = (100-5-2) + (-50-2) + (200-10+5) = 93 - 52 + 195 = 236
    assert report["Account A"]["net_pnl"] == 236.0
    assert report["Account A"]["win_rate_pct"] == (2 / 3) * 100
    assert report["Account A"]["total_trades"] == 3
    assert report["Account A"]["best_trade_pnl"] == 195.0
    assert report["Account A"]["worst_trade_pnl"] == -52.0

    # Account B Math: Net PnL = -105
    assert report["Account B"]["net_pnl"] == -105.0
    assert report["Account B"]["win_rate_pct"] == 0.0
    assert report["Account B"]["total_trades"] == 1
    assert report["Account B"]["best_trade_pnl"] == -105.0
    assert report["Account B"]["worst_trade_pnl"] == -105.0
