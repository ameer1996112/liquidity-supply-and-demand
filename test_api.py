import asyncio
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

response = client.get("/api/portfolio-control/accounts/trade-copy-rules")
print("Status Code:", response.status_code)
if response.status_code != 200:
    print("Response:", response.text)

response = client.get("/api/portfolio-control/accounts/allocation-suggest?total_capital=100000&goal=maximize_sharpe")
print("Status Code Allocation:", response.status_code)
if response.status_code != 200:
    print("Response:", response.text)

