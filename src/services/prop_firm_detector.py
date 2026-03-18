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
