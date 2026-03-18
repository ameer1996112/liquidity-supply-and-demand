import pytest
from datetime import datetime, timezone
import pytz
from unittest.mock import MagicMock, patch
import asyncio

from src.services.prop_firm_tracker import get_ny_midnight_utc, PropFirmTracker
from src.services.mtm_guardian import MTMGuardian

def test_ny_midnight_utc():
    # Test that get_ny_midnight_utc returns a datetime with 00:00:00 in NY time
    result = get_ny_midnight_utc()
    ny_tz = pytz.timezone("America/New_York")
    ny_time = result.astimezone(ny_tz)
    
    assert ny_time.hour == 0
    assert ny_time.minute == 0
    assert ny_time.second == 0
    assert result.tzinfo == timezone.utc

def test_prop_firm_tracker_drawdown_denominator():
    mock_supabase = MagicMock()
    mock_settings = MagicMock()
    mock_settings.account_balance = 100000.0
    mock_settings.phase1_max_daily_loss = 5000.0
    mock_settings.phase1_max_drawdown_pct = 10.0
    mock_settings.funded_max_daily_loss = 5000.0
    mock_settings.funded_max_drawdown_pct = 10.0
    mock_settings.evaluation_mode = True
    mock_settings.evaluation_phase = "phase1"
    
    tracker = PropFirmTracker(mock_supabase, mock_settings)
    
    # Mock MTMGuardian and database responses
    with patch("src.services.mtm_guardian.MTMGuardian") as mock_mtm:
        mock_mtm_instance = mock_mtm.return_value
        mock_mtm_instance.get_real_time_equity.return_value = {
            "closed_pnl": 0.0,
            "floating_pnl": -5000.0,
            "current_equity": 95000.0
        }
        
        mock_response = MagicMock()
        mock_response.data = [{
            "daily_start_balance": 100000.0,
            "daily_high_water_mark": 100000.0,
            "max_historical_equity": 105000.0
        }]
        
        # Deep mock strategy to avoid mock attribute errors
        mock_supabase.table.return_value.select.return_value.eq.return_value.gte.return_value.order.return_value.limit.return_value.execute.return_value = mock_response
        
        # Test Phase 1
        metrics_phase1 = asyncio.run(tracker.get_current_metrics("test", "phase1"))
        assert metrics_phase1.trailing_drawdown_pct == 5.0
        
        # Test Funded 
        metrics_funded = asyncio.run(tracker.get_current_metrics("test", "funded"))
        assert round(metrics_funded.trailing_drawdown_pct, 2) == 9.52

def test_mtm_guardian_dynamic_jpy():
    mock_supabase = MagicMock()
    mock_settings = MagicMock()
    mock_settings.account_balance = 100000.0
    
    guardian = MTMGuardian(mock_supabase, mock_settings)
    
    mock_response = MagicMock()
    mock_response.data = [{
        "id": 1,
        "symbol": "USDJPY",
        "side": "buy",
        "entry": 150.0,
        "size": 1.0,
        "filled_entry_price": 150.0,
        "sl": 149.0,
        "tp": 151.0,
        "status": "active"
    }]
    
    guardian._apply_account_filter = MagicMock()
    guardian._apply_account_filter.return_value.execute.return_value = mock_response
    
    # Also mock the 'closed' query
    mock_closed_response = MagicMock()
    mock_closed_response.data = []
    
    mock_closed_query = MagicMock()
    mock_closed_query.execute.return_value = mock_closed_response
    
    mock_open_query = MagicMock()
    mock_open_query.execute.return_value = mock_response
    
    guardian._apply_account_filter.side_effect = [mock_closed_query, mock_open_query]
    
    with patch("src.adapters.market_data.get_current_price") as mock_price:
        mock_price.return_value = 149.0
        
        equity = guardian.get_real_time_equity("test")
        
        pnl = equity["floating_pnl"]
        # Expected: -666.67
        assert -667.0 < pnl < -666.0
