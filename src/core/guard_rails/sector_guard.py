"""
Sector Exposure Guard

Prevents excessive concentration in specific market sectors.
"""

import logging
from typing import Dict, List, Tuple

from src.services.position_optimizer import PositionOptimizer

logger = logging.getLogger(__name__)


class SectorExposureGuard:
    """
    Guard that enforces sector exposure limits.

    Prevents trades that would cause excessive concentration in a single
    sector (e.g., forex majors, JPY crosses, indices, etc.).
    """

    def __init__(self):
        """Initialize the sector guard."""
        self.optimizer = PositionOptimizer()

    def check(
        self,
        new_signal: Dict,
        current_positions: List[Dict],
        sector_limits: Dict[str, float],
        total_equity: float
    ) -> Tuple[bool, str]:
        """
        Check if adding a new position would violate sector limits.

        Args:
            new_signal: New signal with symbol, size, entry
            current_positions: List of current active positions
            sector_limits: Dict of {sector: max_exposure_pct} (0.0-1.0)
            total_equity: Total account equity in USD

        Returns:
            (passes_check, reason)
        """
        if total_equity == 0:
            return False, "Cannot calculate sector exposure: equity is zero"

        # Calculate new position notional value
        symbol = new_signal.get("symbol", "")
        size = new_signal.get("size", 0.0)
        entry = new_signal.get("entry", 0.0)
        side = new_signal.get("side", "long")

        new_notional = self.optimizer.calculate_notional_value(
            symbol, side, size, entry
        )

        new_position_dict = {
            "symbol": symbol,
            "notional_value": new_notional
        }

        # Check sector limits
        passes, reason = self.optimizer.check_sector_limits(
            positions=current_positions,
            new_signal=new_position_dict,
            sector_limits=sector_limits,
            total_equity=total_equity
        )

        if not passes:
            logger.warning(f"Sector exposure limit violated: {reason}")

        return passes, reason

    def get_sector_utilization(
        self,
        current_positions: List[Dict],
        sector_limits: Dict[str, float],
        total_equity: float
    ) -> Dict[str, Dict[str, float]]:
        """
        Get current utilization of sector limits.

        Args:
            current_positions: List of current active positions
            sector_limits: Dict of {sector: max_exposure_pct}
            total_equity: Total account equity

        Returns:
            Dict of {sector: {"exposure_pct": X, "limit_pct": Y, "utilization": Z}}
        """
        if total_equity == 0:
            return {}

        # Calculate sector exposure
        sector_exposure = self.optimizer.calculate_sector_exposure(
            current_positions,
            total_equity
        )

        # Add limit and utilization info
        utilization = {}

        for sector, limit_pct in sector_limits.items():
            current_pct = sector_exposure.get(sector, {}).get("exposure_pct", 0.0)
            limit_pct_value = limit_pct * 100  # Convert to percentage

            util_pct = (current_pct / limit_pct_value * 100) if limit_pct_value > 0 else 0.0

            utilization[sector] = {
                "exposure_pct": current_pct,
                "limit_pct": limit_pct_value,
                "utilization": min(util_pct, 100.0),  # Cap at 100%
                "exposure_usd": sector_exposure.get(sector, {}).get("exposure_usd", 0.0)
            }

        return utilization

    def get_available_capacity(
        self,
        current_positions: List[Dict],
        sector: str,
        sector_limits: Dict[str, float],
        total_equity: float
    ) -> float:
        """
        Get available capacity for a specific sector in USD.

        Args:
            current_positions: List of current active positions
            sector: Sector name (e.g., "forex_majors")
            sector_limits: Dict of {sector: max_exposure_pct}
            total_equity: Total account equity

        Returns:
            Available capacity in USD
        """
        if total_equity == 0 or sector not in sector_limits:
            return 0.0

        # Calculate current sector exposure
        sector_exposure = self.optimizer.calculate_sector_exposure(
            current_positions,
            total_equity
        )

        current_exposure_usd = sector_exposure.get(sector, {}).get("exposure_usd", 0.0)
        max_exposure_usd = total_equity * sector_limits[sector]

        available = max_exposure_usd - current_exposure_usd

        return max(0.0, available)

    def list_sectors_at_risk(
        self,
        current_positions: List[Dict],
        sector_limits: Dict[str, float],
        total_equity: float,
        warning_threshold: float = 0.8
    ) -> List[Dict[str, any]]:
        """
        List sectors that are approaching or exceeding limits.

        Args:
            current_positions: List of current active positions
            sector_limits: Dict of {sector: max_exposure_pct}
            total_equity: Total account equity
            warning_threshold: Utilization threshold for warnings (0.8 = 80%)

        Returns:
            List of sectors at risk with details
        """
        utilization = self.get_sector_utilization(
            current_positions,
            sector_limits,
            total_equity
        )

        at_risk = []

        for sector, data in utilization.items():
            util_pct = data["utilization"] / 100.0  # Convert to 0-1

            if util_pct >= warning_threshold:
                status = "exceeded" if util_pct >= 1.0 else "warning"

                at_risk.append({
                    "sector": sector,
                    "status": status,
                    "utilization": data["utilization"],
                    "exposure_pct": data["exposure_pct"],
                    "limit_pct": data["limit_pct"],
                    "exposure_usd": data["exposure_usd"]
                })

        # Sort by utilization descending
        at_risk.sort(key=lambda x: x["utilization"], reverse=True)

        return at_risk
