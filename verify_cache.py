from src.api import app
from fastapi.testclient import TestClient
from src.services.redis_cache import cache_set

def test_endpoint():
    # Pre-seed cache to ensure we get a response
    test_data = {"status": "active", "metrics": {"daily_loss": 500}}
    cache_set("prop_firm:metrics:ameer1996112", test_data, ttl_seconds=30)
    
    client = TestClient(app)
    resp = client.get("/api/v1/prop-firm/challenge-status/ameer1996112")
    if resp.status_code == 200:
        data = resp.json()
        print("SUCCESS:", data)
    else:
        print("FAIL:", resp.status_code, resp.text)

if __name__ == "__main__":
    test_endpoint()
