import os
from dotenv import load_dotenv

load_dotenv(override=True)

anon = os.environ.get("SUPABASE_ANON_KEY")
service = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

print(f"ANON_KEY: {anon[:10] if anon else 'None'}...")
print(f"SERVICE_KEY: {service[:10] if service else 'None'}...")
