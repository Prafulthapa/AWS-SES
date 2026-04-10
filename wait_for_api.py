import time
import urllib.request

url = "http://api:8000/health"

print("⏳ Waiting for API /health...")

for i in range(1, 91):
    try:
        urllib.request.urlopen(url, timeout=2).read()
        print("✅ API is ready")
        raise SystemExit(0)
    except Exception:
        print(f"...not ready yet ({i}/90)")
        time.sleep(2)

print("❌ API not ready after retries")
raise SystemExit(1)
