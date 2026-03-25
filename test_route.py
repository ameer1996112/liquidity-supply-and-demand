from fastapi.testclient import TestClient
from src.api import app

client = TestClient(app)
response = client.post("/api/portfolio-control/accounts/test-connection", json={"meta_api_account_id": "test", "meta_api_token": "test"})
print(response.status_code)
print(response.headers)
print(response.text)
