import os
import redis
from dotenv import load_dotenv

# Load .env from project root
from pathlib import Path
_root = Path(__file__).resolve().parent.parent
load_dotenv(_root / ".env")

REDIS_URL = os.getenv("REDIS_URL")

def check_redis():
    print("\n🔍 REDIS CONNECTION DIAGNOSTIC")
    print("------------------------------")

    if not REDIS_URL:
        print("❌ ERROR: REDIS_URL is missing from .env (project root)")
        return

    # Mask the password for security
    masked_url = REDIS_URL.split("@")[-1] if "@" in REDIS_URL else "NO_AUTH_FOUND"
    print(f"📡 Target: ...@{masked_url}")

    # 1. ANALYZE URL TYPE
    if "railway.internal" in REDIS_URL:
        print("⚠️  WARNING: You are using an INTERNAL Railway URL.")
        print("   This URL only works if this script runs ON Railway servers.")
        print("   It will FAIL on your local Wi-Fi.")
    else:
        print("✅ URL looks like a Public/External address.")

    # 2. ATTEMPT CONNECTION
    print("\n🔌 Connecting...")
    try:
        r = redis.from_url(REDIS_URL, socket_timeout=5)
        r.ping()
        print("✅ SUCCESS! Connected to Redis.")
        print(f"   Response from Server: {r.ping()}")
        
        # Test Write/Read
        r.set("trinity_test_key", "connected")
        val = r.get("trinity_test_key").decode('utf-8')
        print(f"   Write/Read Test: {val}")
        
    except redis.exceptions.ConnectionError as e:
        print("❌ CONNECTION FAILED.")
        print(f"   Reason: {e}")
        print("\n💡 FIX:")
        print("   1. Go to Railway Dashboard -> Redis Service.")
        print("   2. Click 'Connect' -> 'Public Networking'.")
        print("   3. Copy the 'Public Connection URL'.")
        print("   4. Paste it into your local 'backend/.env' file.")
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")

if __name__ == "__main__":
    check_redis()