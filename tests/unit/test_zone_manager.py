"""
Unit tests for ZoneManager (NumPy-based zone tracking).

Tests:
- Zone creation and capacity management
- Priming logic
- Liquidity sweep detection
- Circular buffer overflow handling
- Numba-compiled functions

Run with: pytest tests/unit/test_zone_manager.py -v
"""

import pytest
import numpy as np

from app.zone_manager import (
    ZoneManager,
    ZONE_DTYPE,
    find_primed_zones_numba,
    check_zone_touch_numba,
    prime_zone_numba,
    update_zone_touch_numba,
    update_liquidity_sweep_numba,
    check_priming_conditions_numba,
)


class TestZoneManager:
    """Test suite for ZoneManager class."""

    def test_initialization(self):
        """Test ZoneManager initializes correctly."""
        zm = ZoneManager(max_zones=100)

        assert len(zm.zones) == 100
        assert zm.zone_count == 0
        assert zm.next_zone_id == 1
        assert zm.max_zones == 100

    def test_create_zone_demand(self):
        """Test creating a demand zone."""
        zm = ZoneManager()

        zone_idx = zm.create_zone(
            top=2050.0,
            bottom=2045.0,
            is_demand=True,
            bar_idx=10,
            base_timestamp=1234567890,
            score=75.0,
            leg_candles=2,
            candles_in_base=1,
        )

        assert zone_idx == 0
        assert zm.zone_count == 1

        z = zm.zones[zone_idx]
        assert z['id'] == 1
        assert z['top'] == 2050.0
        assert z['bottom'] == 2045.0
        assert z['is_demand'] == True
        assert z['active'] == True
        assert z['created_bar'] == 10
        assert z['score'] == 75.0
        assert z['primed'] == False

    def test_create_zone_supply(self):
        """Test creating a supply zone."""
        zm = ZoneManager()

        zone_idx = zm.create_zone(
            top=2055.0,
            bottom=2050.0,
            is_demand=False,
            bar_idx=15,
            base_timestamp=1234567891,
            score=80.0,
        )

        assert zone_idx == 0
        z = zm.zones[zone_idx]
        assert z['is_demand'] == False
        assert z['active'] == True

    def test_duplicate_base_timestamp(self):
        """Test that duplicate base timestamps are rejected."""
        zm = ZoneManager()

        # Create first zone
        zone_idx1 = zm.create_zone(
            top=2050.0,
            bottom=2045.0,
            is_demand=True,
            bar_idx=10,
            base_timestamp=1234567890,
        )
        assert zone_idx1 == 0

        # Try to create duplicate (same base_timestamp)
        zone_idx2 = zm.create_zone(
            top=2055.0,
            bottom=2050.0,
            is_demand=True,
            bar_idx=12,
            base_timestamp=1234567890,  # Duplicate
        )
        assert zone_idx2 is None
        assert zm.zone_count == 1  # Still only 1 zone

    def test_different_direction_same_timestamp(self):
        """Test that same timestamp is allowed for demand and supply (different sets)."""
        zm = ZoneManager()

        # Create demand zone
        zone_idx1 = zm.create_zone(
            top=2050.0,
            bottom=2045.0,
            is_demand=True,
            bar_idx=10,
            base_timestamp=1234567890,
        )
        assert zone_idx1 == 0

        # Create supply zone with same timestamp (different direction)
        zone_idx2 = zm.create_zone(
            top=2055.0,
            bottom=2050.0,
            is_demand=False,
            bar_idx=10,
            base_timestamp=1234567890,  # Same timestamp
        )
        assert zone_idx2 == 1  # Should succeed
        assert zm.zone_count == 2

    def test_circular_buffer_overflow(self):
        """Test circular buffer behavior when capacity is reached."""
        zm = ZoneManager(max_zones=3)  # Small capacity for testing

        # Create 3 zones
        for i in range(3):
            zm.create_zone(
                top=2050.0 + i,
                bottom=2045.0 + i,
                is_demand=True,
                bar_idx=i,
                base_timestamp=1000 + i,
                score=50.0,
            )
        assert zm.zone_count == 3

        # Mitigate first zone (make it inactive)
        zm.mitigate_zone(0)
        assert zm.zones[0]['active'] == False

        # Create 4th zone (should replace oldest inactive)
        zone_idx = zm.create_zone(
            top=2053.0,
            bottom=2048.0,
            is_demand=True,
            bar_idx=10,
            base_timestamp=1010,
            score=60.0,
        )
        assert zone_idx == 0  # Replaced zone 0
        assert zm.zone_count == 3  # Count unchanged
        assert zm.zones[0]['active'] == True
        assert zm.zones[0]['top'] == 2053.0  # New zone data

    def test_mitigate_zone(self):
        """Test zone mitigation (marking as inactive)."""
        zm = ZoneManager()

        zone_idx = zm.create_zone(
            top=2050.0,
            bottom=2045.0,
            is_demand=True,
            bar_idx=10,
            base_timestamp=1000,
        )

        assert zm.zones[zone_idx]['active'] == True

        zm.mitigate_zone(zone_idx)
        assert zm.zones[zone_idx]['active'] == False

    def test_get_primed_zones(self):
        """Test getting primed zones."""
        zm = ZoneManager()

        # Create 3 demand zones
        for i in range(3):
            zm.create_zone(
                top=2050.0 + i,
                bottom=2045.0 + i,
                is_demand=True,
                bar_idx=i,
                base_timestamp=1000 + i,
            )

        # Prime zone 1
        zm.zones[1]['primed'] = True

        # Get primed demand zones
        primed_indices = zm.get_primed_zones(is_demand=True)
        assert len(primed_indices) == 1
        assert primed_indices[0] == 1

    def test_get_primed_zones_filters_historical(self):
        """Test that get_primed_zones filters out historical zones."""
        zm = ZoneManager()

        # Create historical zone (primed)
        zm.create_zone(
            top=2050.0,
            bottom=2045.0,
            is_demand=True,
            bar_idx=0,
            base_timestamp=1000,
            is_historical=True,
        )
        zm.zones[0]['primed'] = True

        # Create regular zone (primed)
        zm.create_zone(
            top=2055.0,
            bottom=2050.0,
            is_demand=True,
            bar_idx=10,
            base_timestamp=1010,
            is_historical=False,
        )
        zm.zones[1]['primed'] = True

        primed_indices = zm.get_primed_zones(is_demand=True)
        assert len(primed_indices) == 1
        assert primed_indices[0] == 1  # Only non-historical

    def test_get_active_count(self):
        """Test getting active zone counts."""
        zm = ZoneManager()

        # Create 2 demand, 1 supply
        zm.create_zone(top=2050.0, bottom=2045.0, is_demand=True, bar_idx=0, base_timestamp=1000)
        zm.create_zone(top=2055.0, bottom=2050.0, is_demand=True, bar_idx=1, base_timestamp=1001)
        zm.create_zone(top=2060.0, bottom=2055.0, is_demand=False, bar_idx=2, base_timestamp=1002)

        demand_count, supply_count = zm.get_active_count()
        assert demand_count == 2
        assert supply_count == 1

        # Mitigate one demand zone
        zm.mitigate_zone(0)
        demand_count, supply_count = zm.get_active_count()
        assert demand_count == 1
        assert supply_count == 1

    def test_reset(self):
        """Test resetting zone manager."""
        zm = ZoneManager()

        # Create zones
        zm.create_zone(top=2050.0, bottom=2045.0, is_demand=True, bar_idx=0, base_timestamp=1000)
        zm.create_zone(top=2055.0, bottom=2050.0, is_demand=False, bar_idx=1, base_timestamp=1001)
        assert zm.zone_count == 2

        # Reset
        zm.reset()
        assert zm.zone_count == 0
        assert zm.next_zone_id == 1
        assert len(zm.used_base_times_demand) == 0
        assert len(zm.used_base_times_supply) == 0


class TestNumbaFunctions:
    """Test suite for Numba-compiled functions."""

    def test_find_primed_zones_numba(self):
        """Test vectorized primed zone search."""
        zones = np.zeros(5, dtype=ZONE_DTYPE)

        # Set up test zones
        zones[0]['active'] = True
        zones[0]['primed'] = True
        zones[0]['is_demand'] = True
        zones[0]['is_historical'] = False

        zones[1]['active'] = True
        zones[1]['primed'] = False  # Not primed
        zones[1]['is_demand'] = True
        zones[1]['is_historical'] = False

        zones[2]['active'] = True
        zones[2]['primed'] = True
        zones[2]['is_demand'] = True
        zones[2]['is_historical'] = True  # Historical (should be filtered)

        zones[3]['active'] = False  # Inactive
        zones[3]['primed'] = True
        zones[3]['is_demand'] = True
        zones[3]['is_historical'] = False

        zones[4]['active'] = True
        zones[4]['primed'] = True
        zones[4]['is_demand'] = False  # Supply
        zones[4]['is_historical'] = False

        # Find primed demand zones
        primed_demand = find_primed_zones_numba(zones, is_demand=True)
        assert len(primed_demand) == 1
        assert primed_demand[0] == 0  # Only zone 0 qualifies

        # Find primed supply zones
        primed_supply = find_primed_zones_numba(zones, is_demand=False)
        assert len(primed_supply) == 1
        assert primed_supply[0] == 4

    def test_check_zone_touch_numba_demand(self):
        """Test zone touch detection for demand zones."""
        zone = np.zeros(1, dtype=ZONE_DTYPE)[0]
        zone['is_demand'] = True
        zone['bottom'] = 2045.0
        zone['top'] = 2050.0

        tick_size = 0.01

        # Touch: low inside zone
        assert check_zone_touch_numba(zone, bar_high=2055.0, bar_low=2047.0, tick_size=tick_size) == True

        # Touch: low at bottom boundary
        assert check_zone_touch_numba(zone, bar_high=2060.0, bar_low=2045.0, tick_size=tick_size) == True

        # No touch: low below zone
        assert check_zone_touch_numba(zone, bar_high=2055.0, bar_low=2040.0, tick_size=tick_size) == False

        # No touch: low above zone
        assert check_zone_touch_numba(zone, bar_high=2060.0, bar_low=2052.0, tick_size=tick_size) == False

    def test_check_zone_touch_numba_supply(self):
        """Test zone touch detection for supply zones."""
        zone = np.zeros(1, dtype=ZONE_DTYPE)[0]
        zone['is_demand'] = False
        zone['bottom'] = 2050.0
        zone['top'] = 2055.0

        tick_size = 0.01

        # Touch: high inside zone
        assert check_zone_touch_numba(zone, bar_high=2052.0, bar_low=2045.0, tick_size=tick_size) == True

        # Touch: high at top boundary
        assert check_zone_touch_numba(zone, bar_high=2055.0, bar_low=2040.0, tick_size=tick_size) == True

        # No touch: high above zone
        assert check_zone_touch_numba(zone, bar_high=2060.0, bar_low=2045.0, tick_size=tick_size) == False

        # No touch: high below zone
        assert check_zone_touch_numba(zone, bar_high=2048.0, bar_low=2040.0, tick_size=tick_size) == False

    def test_prime_zone_numba(self):
        """Test zone priming function."""
        zones = np.zeros(1, dtype=ZONE_DTYPE)

        prime_zone_numba(
            zones, zone_idx=0, bar_idx=100,
            bar_close=2047.5, bar_high=2048.0, bar_low=2047.0
        )

        assert zones[0]['primed'] == True
        assert zones[0]['primed_bar'] == 100
        assert zones[0]['primed_ref_close'] == 2047.5
        assert zones[0]['primed_ref_high'] == 2048.0
        assert zones[0]['primed_ref_low'] == 2047.0

    def test_update_zone_touch_numba(self):
        """Test touch count increment."""
        zones = np.zeros(1, dtype=ZONE_DTYPE)
        zones[0]['touch_count'] = 0
        zones[0]['last_touch_bar'] = -1

        update_zone_touch_numba(zones, zone_idx=0, bar_idx=50)

        assert zones[0]['touch_count'] == 1
        assert zones[0]['last_touch_bar'] == 50

        # Touch again
        update_zone_touch_numba(zones, zone_idx=0, bar_idx=75)
        assert zones[0]['touch_count'] == 2
        assert zones[0]['last_touch_bar'] == 75

    def test_update_liquidity_sweep_numba(self):
        """Test liquidity sweep detection and update."""
        zones = np.zeros(2, dtype=ZONE_DTYPE)

        # Demand zone
        zones[0]['active'] = True
        zones[0]['is_demand'] = True
        zones[0]['liquidity_swept'] = False
        zones[0]['target_swept'] = False

        # Supply zone
        zones[1]['active'] = True
        zones[1]['is_demand'] = False
        zones[1]['liquidity_swept'] = False
        zones[1]['target_swept'] = False

        # Sweep occurs (current low sweeps below lookback low)
        update_liquidity_sweep_numba(
            zones,
            zone_count=2,
            current_high=2055.0,
            current_low=2044.0,  # Sweeps below 2045
            lookback_high=2050.0,
            lookback_low=2045.0,
            bar_idx=100
        )

        # Demand zone should be marked as swept
        assert zones[0]['liquidity_swept'] == True
        assert zones[0]['caused_sweep'] == True
        assert zones[0]['liq_low'] == 2045.0

        # Supply zone not swept (current high didn't sweep above lookback high)
        assert zones[1]['liquidity_swept'] == False

    def test_check_priming_conditions_numba(self):
        """Test priming condition check."""
        zone = np.zeros(1, dtype=ZONE_DTYPE)[0]

        # Not primed (missing conditions)
        zone['liquidity_swept'] = False
        zone['target_swept'] = False
        zone['caused_sweep'] = False
        assert check_priming_conditions_numba(zone) == False

        # Partially primed
        zone['liquidity_swept'] = True
        assert check_priming_conditions_numba(zone) == False

        # Fully primed
        zone['target_swept'] = True
        zone['caused_sweep'] = True
        assert check_priming_conditions_numba(zone) == True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
