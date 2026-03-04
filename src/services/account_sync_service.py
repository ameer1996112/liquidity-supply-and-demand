"""
Account Sync Service

Syncs account status and positions from MetaAPI to database.
Handles reconciliation between broker positions and DB positions.

Author: Trading System - Multi-Account Module
Date: 2026-02-09
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config import get_settings

logger = logging.getLogger(__name__)


class AccountSyncService:
    """
    Syncs account data from MetaAPI to database.

    Features:
    - Fetch and cache account balance/equity/margin
    - Fetch and cache open positions
    - Reconcile broker positions with DB positions
    - Update connection status
    """

    def __init__(self, supabase_client):
        """
        Initialize sync service.

        Args:
            supabase_client: Supabase client instance
        """
        self.client = supabase_client
        self.settings = get_settings()

    def sync_account_status(self, account_name: str) -> bool:
        """
        Sync account balance, equity, margin from MetaAPI.

        Fetches current account status and saves to account_status_snapshots table.

        Args:
            account_name: Account name from account_strategies

        Returns:
            True if sync succeeded, False otherwise
        """
        try:
            # Get account configuration
            account = self.client.table("account_strategies").select(
                "*, broker_profile_id, meta_api_account_id, meta_api_token_env_key"
            ).eq("account_name", account_name).eq("is_active", True).single().execute()

            if not account.data:
                logger.warning(f"Account {account_name} not found or inactive")
                return False

            account_data = account.data
            broker_profile_id = account_data.get("broker_profile_id")
            meta_api_account_id = account_data.get("meta_api_account_id")

            # Get MetaAPI adapter
            adapter = self._get_adapter_for_account(account_data)
            if not adapter:
                logger.warning(f"No MetaAPI adapter available for {account_name}")
                return False

            # Fetch account status from MetaAPI
            start_time = time.time()
            account_status = adapter.get_account_status()
            sync_latency_ms = int((time.time() - start_time) * 1000)

            # Determine connection status
            connection_status = "connected"
            if account_status.get("connectionStatus") == "circuit_breaker_open":
                connection_status = "error"
            elif account_status.get("balance", 0) == 0 and account_status.get("equity", 0) == 0:
                connection_status = "disconnected"

            # Save snapshot to database
            snapshot_data = {
                "account_name": account_name,
                "broker_profile_id": broker_profile_id,
                "balance": float(account_status.get("balance", 0)),
                "equity": float(account_status.get("equity", 0)),
                "margin": float(account_status.get("margin", 0)),
                "free_margin": float(account_status.get("freeMargin", 0)),
                "margin_level_pct": float(account_status.get("marginLevel", 0)),
                "credit": float(account_status.get("credit", 0)),
                "leverage": account_status.get("leverage"),
                "server_name": account_status.get("server"),
                "platform_type": account_status.get("platform"),
                "connection_status": connection_status,
                "sync_latency_ms": sync_latency_ms,
                "snapshot_time": datetime.now(timezone.utc).isoformat(),
            }

            self.client.table("account_status_snapshots").insert(snapshot_data).execute()

            # Update account_strategies with last sync time and connection status
            self.client.table("account_strategies").update({
                "last_sync_time": datetime.now(timezone.utc).isoformat(),
                "connection_status": connection_status,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("account_name", account_name).execute()

            logger.info(
                f"Synced account {account_name}: balance=${account_status.get('balance', 0):.2f}, "
                f"equity=${account_status.get('equity', 0):.2f}, latency={sync_latency_ms}ms"
            )

            return True

        except ValueError as ve:
            if str(ve) == "METAAPI_TOKEN_MISSING":
                logger.warning(f"Skipping sync for {account_name}: MetaAPI token is missing")
                try:
                    self.client.table("account_strategies").update({
                        "connection_status": "not_configured",
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }).eq("account_name", account_name).execute()
                except Exception:
                    pass
            return False
        except PermissionError as pe:
            if str(pe) == "METAAPI_AUTH_FAILED":
                logger.error(f"Authentication failed for {account_name}. Token may be invalid or expired.")
                try:
                    self.client.table("account_strategies").update({
                        "connection_status": "error",
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }).eq("account_name", account_name).execute()
                except Exception:
                    pass
            return False
        except Exception as e:
            logger.exception(f"Failed to sync account status for {account_name}: {e}")
            # Update connection status to error
            try:
                self.client.table("account_strategies").update({
                    "connection_status": "error",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }).eq("account_name", account_name).execute()
            except Exception:
                pass
            return False

    def sync_account_positions(self, account_name: str) -> bool:
        """
        Sync open positions from MetaAPI and reconcile with DB.

        Fetches positions from broker and saves to position_snapshots table.
        Runs reconciliation to detect orphaned positions.

        Args:
            account_name: Account name from account_strategies

        Returns:
            True if sync succeeded, False otherwise
        """
        try:
            # Get account configuration
            account = self.client.table("account_strategies").select(
                "*, broker_profile_id"
            ).eq("account_name", account_name).eq("is_active", True).single().execute()

            if not account.data:
                logger.warning(f"Account {account_name} not found or inactive")
                return False

            account_data = account.data
            broker_profile_id = account_data.get("broker_profile_id")

            # Get MetaAPI adapter
            adapter = self._get_adapter_for_account(account_data)
            if not adapter:
                logger.warning(f"No MetaAPI adapter available for {account_name}")
                return False

            # Fetch open positions from MetaAPI
            positions = adapter.get_open_positions()

            snapshot_time = datetime.now(timezone.utc).isoformat()

            # Save each position to position_snapshots
            for pos in positions:
                # Map MetaAPI position type to side
                side = "buy" if pos.get("type") == "POSITION_TYPE_BUY" else "sell"

                position_data = {
                    "account_name": account_name,
                    "broker_profile_id": broker_profile_id,
                    "broker_position_id": str(pos.get("id", "")),
                    "symbol": pos.get("symbol", ""),
                    "side": side,
                    "volume": float(pos.get("volume", 0)),
                    "open_price": float(pos.get("openPrice", 0)),
                    "current_price": float(pos.get("currentPrice", 0)),
                    "sl": pos.get("stopLoss"),
                    "tp": pos.get("takeProfit"),
                    "profit": float(pos.get("profit", 0)),
                    "swap": float(pos.get("swap", 0)),
                    "commission": float(pos.get("commission", 0)),
                    "magic_number": pos.get("magic"),
                    "comment": pos.get("comment"),
                    "open_time": pos.get("time"),
                    "update_time": pos.get("updateTime"),
                    "snapshot_time": snapshot_time,
                    "reconciliation_status": "pending",
                }

                # Try to insert (will fail silently if duplicate)
                try:
                    self.client.table("position_snapshots").insert(position_data).execute()
                except Exception as e:
                    # Duplicate snapshot is OK (unique constraint will prevent it)
                    if "unique" not in str(e).lower():
                        logger.warning(f"Failed to insert position snapshot: {e}")

            # Run reconciliation
            self._reconcile_positions(account_name, snapshot_time)

            logger.info(
                f"Synced positions for {account_name}: {len(positions)} positions from broker"
            )

            return True

        except ValueError as ve:
            if str(ve) == "METAAPI_TOKEN_MISSING":
                logger.warning(f"Skipping positions sync for {account_name}: MetaAPI token missing")
                try:
                    self.client.table("account_strategies").update({
                        "connection_status": "not_configured",
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }).eq("account_name", account_name).execute()
                except Exception:
                    pass
            return False
        except PermissionError as pe:
            if str(pe) == "METAAPI_AUTH_FAILED":
                logger.error(f"Authentication failed for {account_name} during positions sync. Token may be invalid or expired.")
                try:
                    self.client.table("account_strategies").update({
                        "connection_status": "error",
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }).eq("account_name", account_name).execute()
                except Exception:
                    pass
            return False
        except Exception as e:
            logger.exception(f"Failed to sync positions for {account_name}: {e}")
            return False

    def sync_all_active_accounts(self) -> Dict[str, bool]:
        """
        Sync all active accounts (status + positions).

        Returns:
            Dict mapping account_name to success status
        """
        try:
            # Get all active accounts
            accounts = self.client.table("account_strategies").select(
                "account_name"
            ).eq("is_active", True).execute()

            if not accounts.data:
                logger.info("No active accounts to sync")
                return {}

            results = {}
            for account in accounts.data:
                account_name = account["account_name"]

                # Sync status
                status_ok = self.sync_account_status(account_name)

                # Sync positions
                positions_ok = self.sync_account_positions(account_name)

                results[account_name] = status_ok and positions_ok

            success_count = sum(1 for v in results.values() if v)
            logger.info(
                f"Synced {success_count}/{len(results)} accounts successfully"
            )

            return results

        except Exception as e:
            logger.exception(f"Failed to sync all accounts: {e}")
            return {}

    def _get_adapter_for_account(self, account_data: Dict[str, Any]):
        """
        Get MetaAPI adapter for an account.

        Args:
            account_data: Account row from account_strategies

        Returns:
            MetaApiAdapter instance or None
        """
        from src.adapters.execution.meta_api_adapter import MetaApiAdapter
        import os

        # Check if MetaAPI is configured
        broker_profile_id = account_data.get("broker_profile_id")
        meta_api_account_id = account_data.get("meta_api_account_id")

        if not meta_api_account_id and not broker_profile_id:
            return None

        # Get token from env
        token_env_key = account_data.get("meta_api_token_env_key", "META_API_TOKEN")
        token = os.getenv(token_env_key, "").strip()

        # Safe diagnostics string
        token_present = bool(token)
        token_length = len(token)
        token_prefix = token[:3] + "..." if token_present else "None"
        
        logger.info(
            f"MetaAPI Auth Check | Account: {account_data.get('account_name')} | "
            f"EnvKey: {token_env_key} | Present: {token_present} | "
            f"Length: {token_length} | Prefix: {token_prefix}"
        )

        if not token:
            logger.warning(f"MetaAPI token not found or empty in env var {token_env_key}")
            raise ValueError("METAAPI_TOKEN_MISSING")

        # Get account ID (prefer meta_api_account_id, fallback to broker_profile lookup)
        account_id = meta_api_account_id

        if not account_id and broker_profile_id:
            # Look up meta_api_account_id from broker_profiles
            try:
                profile = self.client.table("broker_profiles").select(
                    "meta_api_account_id"
                ).eq("id", broker_profile_id).single().execute()

                if profile.data:
                    account_id = profile.data.get("meta_api_account_id")
            except Exception as e:
                logger.warning(f"Failed to fetch broker_profile: {e}")

        if not account_id:
            return None

        return MetaApiAdapter(
            token=token,
            account_id=account_id,
            account_name=account_data.get("account_name")
        )

    def _reconcile_positions(self, account_name: str, snapshot_time: str):
        """
        Reconcile broker positions with DB positions for a single account snapshot.

        Drift types:
          - DB ACTIVE but broker missing   → MISSING_ON_BROKER
          - Broker position not in DB     → EXTERNAL
          - Broker order exists but DB missing → EXTERNAL_ORDER (reserved for future order-level checks)
        """
        try:
            broker_positions = self.client.table("position_snapshots").select(
                "*, id"
            ).eq("account_name", account_name).eq(
                "snapshot_time", snapshot_time
            ).execute()

            db_positions = self.client.table("trading_signals").select(
                "*, id"
            ).eq("account_name", account_name).in_(
                "status", ["active", "executed"]
            ).execute()

            broker_pos_list = broker_positions.data or []
            db_pos_list = db_positions.data or []

            drift_count = 0

            # Broker → DB: classify EXTERNAL vs matched
            for broker_pos in broker_pos_list:
                matched_signal_id = None
                reconciliation_status = "orphaned"
                reconciliation_note = None

                for db_pos in db_pos_list:
                    if db_pos.get("broker_order_id") == str(broker_pos.get("broker_position_id")) \
                       or db_pos.get("broker_position_id") == str(broker_pos.get("broker_position_id")):
                        matched_signal_id = db_pos["id"]
                        reconciliation_status = "matched"
                        reconciliation_note = "Matched by broker_order_id or broker_position_id"

                        if db_pos.get("status", "").upper() == "PENDING":
                            self.client.table("trading_signals").update({
                                "status": "OPEN",
                                "opened_at": datetime.now(timezone.utc).isoformat(),
                            }).eq("id", matched_signal_id).execute()
                        break

                if not matched_signal_id:
                    broker_symbol = broker_pos.get("symbol")
                    broker_side = broker_pos.get("side")
                    broker_open = float(broker_pos.get("open_price", 0) or 0)

                    for db_pos in db_pos_list:
                        if db_pos.get("symbol") == broker_symbol and db_pos.get("side") == broker_side:
                            db_entry = float(db_pos.get("entry", 0) or 0)
                            tolerance = 0.01 if "JPY" in (broker_symbol or "") else 0.0001

                            if abs(broker_open - db_entry) <= tolerance:
                                matched_signal_id = db_pos["id"]
                                reconciliation_status = "matched"
                                reconciliation_note = "Fuzzy matched by symbol/side/entry"
                                if db_pos.get("status", "").upper() == "PENDING":
                                    self.client.table("trading_signals").update({
                                        "status": "OPEN",
                                        "opened_at": datetime.now(timezone.utc).isoformat(),
                                    }).eq("id", matched_signal_id).execute()
                                break

                if matched_signal_id is None:
                    reconciliation_status = "orphaned"
                    reconciliation_note = "EXTERNAL: broker position not found in trading_signals"
                    drift_count += 1
                    try:
                        from src.services.trade_events import log_event
                        log_event(
                            None,
                            "reconcile_external_position",
                            "reconciler",
                            {
                                "account_name": account_name,
                                "symbol": broker_pos.get("symbol"),
                                "broker_position_id": broker_pos.get("broker_position_id"),
                                "drift_type": "EXTERNAL",
                            },
                        )
                    except Exception:
                        pass

                self.client.table("position_snapshots").update({
                    "matched_signal_id": matched_signal_id,
                    "reconciliation_status": reconciliation_status,
                    "reconciliation_note": reconciliation_note,
                }).eq("id", broker_pos["id"]).execute()

            # DB → Broker: classify MISSING_ON_BROKER
            broker_pos_ids = {
                str(p.get("broker_position_id"))
                for p in broker_pos_list
                if p.get("broker_position_id")
            }
            fuzzy_broker_identities = {
                f"{p.get('symbol')}_{p.get('side')}" for p in broker_pos_list
            }

            for db_pos in db_pos_list:
                status = (db_pos.get("status") or "").upper()
                db_broker_order_id = (
                    str(db_pos.get("broker_order_id", "")) if db_pos.get("broker_order_id") else ""
                )

                if status in ("OPEN", "ACTIVATED", "ACTIVE", "EXECUTED"):
                    if db_broker_order_id.startswith("paper_"):
                        continue

                    is_missing_on_broker = False

                    if db_broker_order_id:
                        if db_broker_order_id not in broker_pos_ids:
                            is_missing_on_broker = True
                    else:
                        db_identity = f"{db_pos.get('symbol')}_{db_pos.get('side')}"
                        if db_identity not in fuzzy_broker_identities:
                            created_at_str = db_pos.get("created_at")
                            if created_at_str:
                                try:
                                    from dateutil.parser import isoparse
                                    dt = isoparse(created_at_str)
                                    if (datetime.now(timezone.utc) - dt).total_seconds() > 180:
                                        is_missing_on_broker = True
                                except Exception:
                                    pass

                    if is_missing_on_broker:
                        drift_count += 1
                        reason = "MISSING_ON_BROKER: DB shows open position but broker snapshot has no matching position"
                        logger.warning(
                            "Reconcile drift MISSING_ON_BROKER: db_id=%s symbol=%s account=%s",
                            db_pos["id"],
                            db_pos.get("symbol"),
                            account_name,
                        )
                        try:
                            from src.services.trade_events import log_event
                            log_event(
                                db_pos.get("id"),
                                "reconcile_missing_on_broker",
                                "reconciler",
                                {
                                    "account_name": account_name,
                                    "symbol": db_pos.get("symbol"),
                                    "drift_type": "MISSING_ON_BROKER",
                                    "status": status,
                                },
                            )
                        except Exception:
                            pass

                        self.client.table("trading_signals").update({
                            "status": "MISSING_ON_BROKER",
                            "notes": reason,
                        }).eq("id", db_pos["id"]).execute()

            # Persist per-account reconciliation metadata
            try:
                now_iso = datetime.now(timezone.utc).isoformat()
                self.client.table("account_strategies").update({
                    "last_reconcile_time": now_iso,
                    "last_reconcile_drift_count": drift_count,
                    "updated_at": now_iso,
                }).eq("account_name", account_name).execute()
            except Exception:
                pass

            logger.info(
                "Reconciled %d broker positions for %s (drift_count=%d)",
                len(broker_pos_list),
                account_name,
                drift_count,
            )

        except Exception as e:
            logger.exception(f"Reconciliation failed for {account_name}: {e}")
