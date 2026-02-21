import json
from src.ai.brain import ensemble_decision, load_brain

# Initialize AI Brain (loads the ML models if they exist locally)
load_brain()

# Let's mock a payload that passes RF threshold to see if LLM runs
payload = {
    "symbol": "USDJPY",
    "score": 95,
    "entry_model": "FLIP",
    "liquidity_distance": 10,
    "zone_type": "demand",
    "side": "buy"
}

res = ensemble_decision(payload)
print(json.dumps({k: v for k, v in res.items() if k not in ["features"]}, indent=2))
