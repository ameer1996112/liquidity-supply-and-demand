"""
Prop Firm Detector Service
Matches an account_name or MetaAPI server name to a prop firm.
Retrieves rules configured in the database.
"""

from typing import Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)

class PropFirmDetector:
    def __init__(self, supabase_client):
        self.supabase = supabase_client

    def detect_firm_by_server(self, server_name: str) -> Optional[Dict[str, Any]]:
        """Match server prefix to a firm."""
        if not server_name:
            return None

        try:
            response = self.supabase.table("prop_firm_server_mappings").select("*").execute()
            mappings = response.data if response.data else []

            for mapping in mappings:
                if server_name.upper().startswith(mapping["server_prefix"].upper()):
                    return {
                        "firm_id": mapping["firm_id"],
                        "firm_display_name": mapping["firm_display_name"]
                    }
        except Exception as e:
            err_str = str(e)
            # PGRST205 = table not found in schema cache (migration not yet run)
            if "PGRST205" in err_str or "prop_firm_server_mappings" in err_str:
                logger.warning(
                    "prop_firm_server_mappings table not found — run migration 047 in Supabase SQL editor. "
                    "Skipping firm detection until then."
                )
            else:
                logger.error(f"Error fetching prop firm mappings: {e}")

        return {"firm_detected": False}

    def get_rules_for_firm(self, firm_id: str, challenge_type: str) -> Optional[Dict[str, Any]]:
        """Get trading rules for a specific firm and challenge phase."""
        try:
            response = self.supabase.table("prop_firm_rules").select("*")\
                .eq("firm_id", firm_id)\
                .eq("challenge_type", challenge_type)\
                .execute()
                
            if response.data:
                return response.data[0]
        except Exception as e:
            err_str = str(e)
            if "PGRST205" in err_str or "prop_firm_rules" in err_str:
                logger.warning(
                    "prop_firm_rules table not found — run migration 047 in Supabase SQL editor."
                )
            else:
                logger.error(f"Error fetching prop firm rules: {e}")

        return None

    def get_firm_and_rules(self, server_name: str, challenge_type: str) -> Optional[Dict[str, Any]]:
        """Combined method to detect firm and fetch rules."""
        firm = self.detect_firm_by_server(server_name)
        if not firm or firm.get("firm_detected") is False:
            return None
            
        rules = self.get_rules_for_firm(firm["firm_id"], challenge_type)
        if rules:
            return {**firm, **rules}
        return firm

    def auto_detect_challenge_type(self, server_name: str, account_name: str) -> str:
        """Dynamically determine the phase based on server and account name strings."""
        server = (server_name or "").upper()
        acc_name = (account_name or "").upper()
        
        # 1. Server explicitly indicates LIVE/FUNDED (but not DEMO)
        if ("LIVE" in server or "SERVER" in server) and "DEMO" not in server:
            return "funded"
            
        # 2. Account name regex/keyword matching for funded
        if any(kw in acc_name for kw in ["FUNDED", "MASTER", "LIVE", "STEP 3"]):
            return "funded"
            
        # 3. Account name parsing for Phase 2
        if any(kw in acc_name for kw in ["PHASE 2", "P2", "STEP 2", "VERIF"]):
            return "phase_2"
            
        # 4. Account name parsing for Phase 1
        if any(kw in acc_name for kw in ["PHASE 1", "P1", "STEP 1", "EVAL"]):
            return "phase_1"
            
        # Default to phase_1 if we only know it's a Demo server but no explicit name
        return "phase_1"
