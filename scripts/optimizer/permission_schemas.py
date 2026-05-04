from __future__ import annotations

DECISIONS = ("TRADE_NORMAL_RISK", "TRADE_REDUCED_RISK", "WATCH_ONLY", "NO_TRADE")

APPROVED_CANDIDATES_SCHEMA = {
    "schema_version": 1,
    "required_top_level_keys": ["schema_version", "generated_at", "human_review_required", "candidates"],
    "candidate_statuses": ["RESEARCH_APPROVED"],
}

DAILY_TRADE_PERMISSIONS_SCHEMA = {
    "schema_version": 1,
    "required_top_level_keys": ["schema_version", "generated_at", "account_profile", "global_decision", "permissions", "blocked"],
    "decisions": list(DECISIONS),
}

EMERGENCY_STOP_SCHEMA = {
    "schema_version": 1,
    "required_top_level_keys": ["active", "reason", "updated_at"],
}
