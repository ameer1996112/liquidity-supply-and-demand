from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any

from src.adapters.supabase_api import get_api_supabase
from src.services.prop_firm_detector import PropFirmDetector
from src.services.redis_cache import cache_get, cache_set
import json

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
                
        # Fallback to DB
        profile_resp = supabase.table("broker_profiles").select("*").eq("account_name", account_name).execute()
        if not profile_resp.data:
            return {"status": "inactive", "firm_detected": False, "firm_info": None, "metrics": None}
            
        profile = profile_resp.data[0]
        server_name = profile.get("meta_api_server_name", "")
        if not server_name:
            server_name = profile.get("server", "")
        
        detector = PropFirmDetector(supabase)
        challenge_type = detector.auto_detect_challenge_type(server_name, account_name)
        rules = detector.get_firm_and_rules(server_name, challenge_type)
        
        metrics = None
        try:
            metrics_resp = supabase.table("prop_firm_metrics").select("*").eq("account_name", profile.get("account_name", "")).order("snapshot_time", desc=True).limit(1).execute()
            metrics = metrics_resp.data[0] if metrics_resp.data else None
        except Exception:
            pass
        
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
    if "challenge_type" not in config:
        raise HTTPException(status_code=400, detail="Missing challenge_type")
        
    challenge_type = config["challenge_type"]
    if challenge_type not in ["phase_1", "phase_2", "funded"]:
        raise HTTPException(status_code=400, detail="Invalid challenge_type")
        
    resp = supabase.table("broker_profiles").update({"challenge_type": challenge_type}).eq("account_name", account_name).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Broker profile not found")
        
    return {"status": "success", "updated": resp.data[0]}
