"""
Trade Copier Service

Copies trades from master account to slave accounts with configurable rules.

Features:
- Scale by account balance
- Risk multiplier
- Symbol filtering
- Confidence threshold filtering
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CopySettings:
    """Trade copy settings."""
    scale_by_balance: bool
    risk_multiplier: float
    copy_sl_tp: bool
    min_master_confidence: Optional[float]
    allowed_symbols: Optional[List[str]]


class TradeCopier:
    """Copies trades from master account to slave accounts."""

    def __init__(self, supabase_client):
        """
        Initialize trade copier.

        Args:
            supabase_client: Supabase client
        """
        self.client = supabase_client

    def get_active_copy_rules(self) -> List[dict]:
        """Get all enabled trade copy rules."""
        try:
            result = self.client.table("trade_copy_rules").select("*").eq(
                "enabled", True
            ).execute()

            return result.data or []

        except Exception as e:
            logger.error(f"Failed to fetch trade copy rules: {e}")
            return []

    def should_copy_trade(
        self,
        signal: Dict,
        rule: Dict
    ) -> bool:
        """
        Check if a trade should be copied based on rule filters.

        Args:
            signal: Master trade signal dict
            rule: Trade copy rule dict

        Returns:
            True if trade should be copied
        """
        # Check symbol filter
        allowed_symbols = rule.get("copy_symbols")
        if allowed_symbols:
            symbol = signal.get("symbol", "").upper()
            if symbol not in [s.upper() for s in allowed_symbols]:
                logger.debug(f"Symbol {symbol} not in allowed list, skipping copy")
                return False

        # Check confidence threshold
        min_confidence = rule.get("min_master_confidence")
        if min_confidence is not None:
            confidence = signal.get("ai_confidence", 0)
            if confidence < min_confidence:
                logger.debug(f"Confidence {confidence} below threshold {min_confidence}, skipping copy")
                return False

        return True

    def calculate_copy_size(
        self,
        master_signal: Dict,
        slave_account: Dict,
        rule: Dict
    ) -> float:
        """
        Calculate position size for slave account.

        Args:
            master_signal: Master trade signal
            slave_account: Slave account strategy config
            rule: Trade copy rule

        Returns:
            Position size in lots for slave account
        """
        master_size = float(master_signal.get("size", 0.01))
        master_balance = float(master_signal.get("account_balance", 10000))

        slave_balance = float(slave_account.get("allocated_capital_usd", 10000))

        scale_by_balance = rule.get("scale_by_balance", True)
        risk_multiplier = float(rule.get("risk_multiplier", 1.0))

        if scale_by_balance:
            # Scale proportionally to account size
            size_multiplier = slave_balance / master_balance
            copied_size = master_size * size_multiplier * risk_multiplier
        else:
            # Use same size, just apply risk multiplier
            copied_size = master_size * risk_multiplier

        # Round to 2 decimal places
        return round(copied_size, 2)

    def copy_signal_to_accounts(
        self,
        master_signal: Dict,
        rule: Dict
    ) -> List[int]:
        """
        Copy a master signal to all slave accounts defined in rule.

        Args:
            master_signal: Master trade signal dict
            rule: Trade copy rule dict

        Returns:
            List of created slave signal IDs
        """
        if not self.should_copy_trade(master_signal, rule):
            logger.info("Trade does not meet copy criteria, skipping")
            return []

        slave_account_names = rule.get("slave_account_names", [])
        if not slave_account_names:
            logger.warning("No slave accounts configured in rule")
            return []

        created_signal_ids = []

        for slave_account_name in slave_account_names:
            try:
                # Get slave account config
                slave_account = self.client.table("account_strategies").select("*").eq(
                    "account_name", slave_account_name
                ).eq("is_active", True).single().execute()

                if not slave_account.data:
                    logger.warning(f"Slave account {slave_account_name} not found or inactive")
                    continue

                slave_data = slave_account.data

                # Check if trading is paused for this account
                if slave_data.get("pause_trading", False):
                    logger.info(f"Trading paused for {slave_account_name}, skipping copy")
                    continue

                # Calculate copy size
                copied_size = self.calculate_copy_size(master_signal, slave_data, rule)

                if copied_size <= 0:
                    logger.warning(f"Calculated copy size is {copied_size}, skipping")
                    continue

                # Create copied signal
                copied_signal = self._create_copied_signal(
                    master_signal, slave_data, rule, copied_size
                )

                if copied_signal:
                    created_signal_ids.append(copied_signal)

                    # Log to trade_copy_log
                    self._log_copy(
                        rule["id"],
                        master_signal.get("id"),
                        copied_signal,
                        master_signal.get("account_balance", 0),
                        slave_account_name,
                        master_signal.get("size", 0),
                        copied_size,
                    )

            except Exception as e:
                logger.error(f"Failed to copy trade to {slave_account_name}: {e}")

        logger.info(
            f"Copied master signal {master_signal.get('id')} to {len(created_signal_ids)} slave accounts"
        )

        return created_signal_ids

    def _create_copied_signal(
        self,
        master_signal: Dict,
        slave_account: Dict,
        rule: Dict,
        copied_size: float
    ) -> Optional[int]:
        """
        Create a new trading signal for slave account.

        Args:
            master_signal: Master signal
            slave_account: Slave account config
            rule: Copy rule
            copied_size: Calculated size for slave

        Returns:
            Created signal ID or None
        """
        try:
            # Build copied signal data
            copied_data = {
                "symbol": master_signal.get("symbol"),
                "side": master_signal.get("side"),
                "entry": master_signal.get("entry"),
                "size": copied_size,
                "run_mode": master_signal.get("run_mode", "PAPER"),
                "status": "pending",  # Will be picked up by worker
                "broker_profile_id": slave_account.get("broker_profile_id"),
                "notes": f"Copied from master signal #{master_signal.get('id')}",
            }

            # Copy SL/TP if configured
            if rule.get("copy_sl_tp", True):
                copied_data["sl"] = master_signal.get("sl")
                copied_data["tp"] = master_signal.get("tp")

            # Copy AI reasoning if available
            if master_signal.get("ai_reasoning"):
                copied_data["ai_reasoning"] = master_signal["ai_reasoning"]

            if master_signal.get("ai_confidence"):
                copied_data["ai_confidence"] = master_signal["ai_confidence"]

            # Copy zone/entry model data
            for field in ["zone_id", "zone_type", "zone_grade", "entry_model", "score"]:
                if master_signal.get(field):
                    copied_data[field] = master_signal[field]

            # Create in database
            result = self.client.table("trading_signals").insert(copied_data).execute()

            if result.data:
                signal_id = result.data[0]["id"]
                logger.info(
                    f"Created copied signal {signal_id} for {slave_account['account_name']} "
                    f"(size={copied_size})"
                )
                return signal_id

            return None

        except Exception as e:
            logger.error(f"Failed to create copied signal: {e}")
            return None

    def _log_copy(
        self,
        rule_id: int,
        master_signal_id: int,
        slave_signal_id: int,
        master_account: str,
        slave_account: str,
        master_size: float,
        slave_size: float,
    ):
        """Log trade copy to audit table."""
        try:
            size_multiplier = slave_size / master_size if master_size > 0 else 0.0

            self.client.table("trade_copy_log").insert({
                "rule_id": rule_id,
                "master_signal_id": master_signal_id,
                "slave_signal_id": slave_signal_id,
                "master_account": master_account,
                "slave_account": slave_account,
                "master_size": master_size,
                "slave_size": slave_size,
                "size_multiplier": size_multiplier,
                "success": True,
            }).execute()

        except Exception as e:
            logger.error(f"Failed to log trade copy: {e}")

    def process_new_master_signal(self, master_signal: Dict):
        """
        Check all copy rules and copy trade if applicable.

        This should be called by the worker after a master account executes a trade.

        Args:
            master_signal: Master trade signal dict
        """
        # Get account name from master signal
        # (Assuming master signal has account_name or we can determine from broker_profile_id)
        master_account_name = master_signal.get("account_name")

        if not master_account_name:
            # Try to get from broker_profile_id
            broker_profile_id = master_signal.get("broker_profile_id")
            if broker_profile_id:
                try:
                    profile = self.client.table("broker_profiles").select("name").eq(
                        "id", broker_profile_id
                    ).single().execute()

                    if profile.data:
                        master_account_name = profile.data.get("name")
                except Exception:
                    pass

        if not master_account_name:
            logger.debug("Cannot determine master account name, skipping copy check")
            return

        # Find applicable copy rules
        copy_rules = self.get_active_copy_rules()

        for rule in copy_rules:
            if rule.get("master_account_name") == master_account_name:
                logger.info(
                    f"Found matching copy rule: {rule.get('rule_name')} "
                    f"(master={master_account_name})"
                )

                # Copy to slave accounts
                self.copy_signal_to_accounts(master_signal, rule)
