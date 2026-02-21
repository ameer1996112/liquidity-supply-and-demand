import os
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

url = os.environ.get("SUPABASE_URL")
anon_key = os.environ.get("SUPABASE_ANON_KEY")
service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

print(f"URL: {url}")
print(f"Anon Key length: {len(anon_key) if anon_key else 0}")
print(f"Service Key length: {len(service_key) if service_key else 0}")

# Test Anon Key
print("\nTesting Anon Key...")
headers_anon = {
    "apikey": anon_key,
    "Authorization": f"Bearer {anon_key}",
    "Content-Type": "application/json"
}
resp_anon = requests.get(f"{url}/rest/v1/trading_signals?select=id&limit=1", headers=headers_anon)
print(f"Anon Key status: {resp_anon.status_code} {resp_anon.text}")

# Test Service Key
print("\nTesting Service Key...")
headers_service = {
    "apikey": service_key,
    "Authorization": f"Bearer {service_key}",
    "Content-Type": "application/json"
}
resp_service = requests.get(f"{url}/rest/v1/trading_signals?select=id&limit=1", headers=headers_service)
print(f"Service Key status: {resp_service.status_code} {resp_service.text}")
