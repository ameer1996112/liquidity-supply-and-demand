import asyncio
from fastapi.testclient import TestClient
from src.api import app

client = TestClient(app)

response = client.get("/api/portfolio-control/accounts/trade-copy-rules")
print("Status Code Trade Copy:", response.status_code)

response = client.get("/api/portfolio-control/accounts/allocation-suggest?total_capital=100000&goal=maximize_sharpe")
print("Status Code Allocation:", response.status_code)
