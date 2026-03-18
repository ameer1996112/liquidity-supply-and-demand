from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any

from src.adapters.supabase_api import get_api_supabase
from src.services.prop_firm_detector import PropFirmDetector

router = APIRouter(prefix="/api/v1/prop-firm", tags=["Prop Firm"])

def get_detector(supabase=Depends(get_api_supabase)) -> PropFirmDetector:
    return PropFirmDetector(supabase)

@router.get("/challenge-status/{account_id}")
async def get_challenge_status(account_id: str, supabase=Depends(get_api_supabase)):
    """Get the current challenge status including metrics and rules."""
    profile_resp = supabase.table("broker_profiles").select("*, meta_api_server_name").eq("account_id", account_id).execute()
    if not profile_resp.data:
        raise HTTPException(status_code=404, detail="Broker profile not found")
        
    profile = profile_resp.data[0]
    server_name = profile.get("meta_api_server_name", "")
    challenge_type = profile.get("challenge_type", "phase_1")
    
    detector = PropFirmDetector(supabase)
    rules = detector.get_firm_and_rules(server_name, challenge_type)
    
    metrics_resp = supabase.table("prop_firm_metrics").select("*").eq("account_name", profile.get("account_name", "")).order("snapshot_time", desc=True).limit(1).execute()
    metrics = metrics_resp.data[0] if metrics_resp.data else None
    
    return {
        "status": "active",
        "firm_detected": bool(rules),
        "firm_info": rules,
        "metrics": metrics
    }

@router.patch("/challenge-config/{account_id}")
async def update_challenge_config(account_id: str, config: Dict[str, Any], supabase=Depends(get_api_supabase)):
    """Update challenge configuration (e.g. challenge_type) for an account."""
    if "challenge_type" not in config:
        raise HTTPException(status_code=400, detail="Missing challenge_type")
        
    challenge_type = config["challenge_type"]
    if challenge_type not in ["phase_1", "phase_2", "funded"]:
        raise HTTPException(status_code=400, detail="Invalid challenge_type")
        
    resp = supabase.table("broker_profiles").update({"challenge_type": challenge_type}).eq("account_id", account_id).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Broker profile not found")
        
    return {"status": "success", "updated": resp.data[0]}
