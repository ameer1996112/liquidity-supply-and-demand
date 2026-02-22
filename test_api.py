import requests
import time

try:
    print("Testing local API...")
    res = requests.get("http://localhost:8000/api/portfolio-control/accounts/comparison")
    print(res.status_code)
    print(res.json())
except Exception as e:
    print(f"Error: {e}")
