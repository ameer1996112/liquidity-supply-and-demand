from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
import json
import logging

from src.adapters.supabase_api import get_api_supabase
from src.services.prop_firm_detector import PropFirmDetector
from src.services.redis_cache import cache_get, cache_set

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/v1/prop-firm", tags=["Prop Firm"])

def get_detector(supabase=Depends(get_api_supabase)) -> PropFirmDetector:
    return PropFirmDetector(supabase)

@router.get("/challenge-status/{account_name}")
async def get_challenge_status(account_name: str, supabase=Depends(get_api_supabase)):
    """Get the current challenge status including metrics and rules."""
    # Guard: reject placeholder account names
    if not account_name or account_name == "default":
        return {"status": "inactive", "firm_detected": False, "firm_info": None, "metrics": None}

    try:
        cache_key = f"prop_firm:metrics:{account_name}"
        
        # Try Redis cache first
        cached = cache_get(cache_key)
        if cached is not None:
            try:
                return json.loads(cached) if isinstance(cached, str) else cached
            except Exception:
                pass
                
        # 1. Get broker_profile_id from account_strategies
        acc_resp = supabase.table("account_strategies").select("broker_profile_id, account_type").eq("account_name", account_name).execute()
        if not acc_resp.data:
            return {"status": "inactive", "firm_detected": False, "firm_info": None, "metrics": None}
            
        acc_data = acc_resp.data[0]
        broker_profile_id = acc_data.get("broker_profile_id")
        
        server_name = ""
        db_challenge_type = None
        
        if broker_profile_id:
            profile_resp = supabase.table("broker_profiles").select("*").eq("id", broker_profile_id).execute()
            if profile_resp.data:
                profile = profile_resp.data[0]
                server_name = profile.get("meta_api_server_name", "") or profile.get("server", "")
                db_challenge_type = profile.get("challenge_type")
                
        # 2. Fallback to live snapshots if server_name is missing
        if not server_name:
            snap_resp = supabase.table("account_status_snapshots").select("server_name").eq("account_name", account_name).order("snapshot_time", desc=True).limit(1).execute()
            if snap_resp.data and snap_resp.data[0].get("server_name"):
                server_name = snap_resp.data[0]["server_name"]
                
        detector = PropFirmDetector(supabase)
        # Use DB value if set, else auto-detect
        challenge_type = db_challenge_type if db_challenge_type else detector.auto_detect_challenge_type(server_name, account_name)
        rules = detector.get_firm_and_rules(server_name, challenge_type)
        
        metrics = None
        try:
            metrics_resp = supabase.table("prop_firm_metrics").select("*").eq("account_name", account_name).order("snapshot_time", desc=True).limit(1).execute()
            metrics = metrics_resp.data[0] if metrics_resp.data else None
        except Exception:
            pass
        
        # Enrich rules with broker_profile data as fallback
        # When prop_firm_rules has no entry (e.g. ACG), use the values the
        # user configured in ChallengeTab (profit_target, max_daily_loss_pct, etc.)
        try:
            bp_resp = supabase.table("broker_profiles")\
                .select("profit_target, starting_balance, max_daily_loss_pct, max_drawdown_pct, min_trading_days, consistency_enabled, evaluation_mode, name")\
                .eq("id", broker_profile_id)\
                .limit(1)\
                .execute() if broker_profile_id else None

            if bp_resp and bp_resp.data:
                bp = bp_resp.data[0]
                starting_balance = float(bp.get("starting_balance") or 0)
                profit_target_usd = float(bp.get("profit_target") or 0)

                # Compute profit_target_pct from configured dollar amounts
                profile_profit_target_pct = (
                    round((profit_target_usd / starting_balance) * 100, 2)
                    if starting_balance > 0 and profit_target_usd > 0 else 0
                )

                # If rules dict exists, fill in any missing fields from broker profile
                if rules:
                    if not rules.get("profit_target_pct") and profile_profit_target_pct > 0:
                        rules["profit_target_pct"] = profile_profit_target_pct
                    if not rules.get("max_daily_loss_pct") and bp.get("max_daily_loss_pct"):
                        rules["max_daily_loss_pct"] = float(bp["max_daily_loss_pct"])
                    if not rules.get("max_drawdown_pct") and bp.get("max_drawdown_pct"):
                        rules["max_drawdown_pct"] = float(bp["max_drawdown_pct"])
                    if not rules.get("min_trading_days") and bp.get("min_trading_days"):
                        rules["min_trading_days"] = int(bp["min_trading_days"])
                    if "consistency_enabled" not in rules and "consistency_enabled" in bp:
                        rules["consistency_enabled"] = bp["consistency_enabled"]
                else:
                    # No firm rules at all — build from broker profile directly
                    if profile_profit_target_pct > 0 or bp.get("max_daily_loss_pct"):
                        rules = {
                            "firm_id": "custom",
                            "firm_display_name": bp.get("name") or account_name,
                            "profit_target_pct": profile_profit_target_pct,
                            "max_daily_loss_pct": float(bp.get("max_daily_loss_pct") or 0),
                            "max_drawdown_pct": float(bp.get("max_drawdown_pct") or 0),
                            "min_trading_days": int(bp.get("min_trading_days") or 0),
                            "consistency_enabled": bp.get("consistency_enabled", True),
                        }
        except Exception as enrich_err:
            logger.warning("Could not enrich firm rules from broker profile: %s", enrich_err)

        res = {
            "status": "active",
            "firm_detected": bool(rules),
            "firm_info": rules,
            "metrics": metrics
        }
        
        try:
            cache_set(cache_key, res, ttl_seconds=30)
        except Exception:
            pass
            
        return res
    except HTTPException:
        raise
    except Exception as e:
        # Return clean JSON instead of 500 to avoid CORS issues
        return {"status": "error", "firm_detected": False, "firm_info": None, "metrics": None, "error": str(e)}

@router.patch("/challenge-config/{account_name}")
async def update_challenge_config(account_name: str, config: Dict[str, Any], supabase=Depends(get_api_supabase)):
    """Update challenge configuration (e.g. challenge_type) for an account."""
    if "challenge_type" not in config and "evaluation_phase" not in config:
        raise HTTPException(status_code=400, detail="Missing challenge_type or evaluation_phase")
        
    challenge_type = config.get("challenge_type", config.get("evaluation_phase"))
    if challenge_type not in ["phase_1", "phase_2", "funded", "phase1", "phase2"]:
        raise HTTPException(status_code=400, detail="Invalid challenge_type")
        
    update_data = {}
    
    # Map challenge_type correctly
    db_challenge_type = challenge_type
    if challenge_type == "phase1": db_challenge_type = "phase_1"
    if challenge_type == "phase2": db_challenge_type = "phase_2"
    update_data["challenge_type"] = db_challenge_type
    update_data["evaluation_phase"] = challenge_type if challenge_type in ["phase1", "phase2", "funded"] else challenge_type.replace("_", "")
    
    # Map other fields if they exist
    allowed_fields = [
        "starting_balance", "profit_target", "max_daily_loss_pct", 
        "max_drawdown_pct", "min_trading_days", "consistency_limit_pct"
    ]
    for field in allowed_fields:
        if field in config:
            update_data[field] = float(config[field]) if field != "min_trading_days" else int(config[field])
            
    if "consistency_enabled" in config:
        update_data["consistency_enabled"] = bool(config["consistency_enabled"]) if config["consistency_enabled"] is not None else None
        
    # Get broker_profile_id from account_strategies
    acc_resp = supabase.table("account_strategies").select("broker_profile_id").eq("account_name", account_name).execute()
    if not acc_resp.data or not acc_resp.data[0].get("broker_profile_id"):
        raise HTTPException(status_code=404, detail="Account not found or no broker profile attached")
        
    broker_profile_id = acc_resp.data[0]["broker_profile_id"]
    
    resp = supabase.table("broker_profiles").update(update_data).eq("id", broker_profile_id).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Broker profile not found")
        
    return {"status": "success", "updated": resp.data[0]}
