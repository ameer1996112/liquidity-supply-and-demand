---
plan: "05-plan-2-redis-precheck"
phase: "05"
wave: 1
depends_on: []
files_modified:
  - "src/api.py"
requirements:
  - INFRA-02
  - INFRA-03
autonomous: true
---

# Plan 2: Redis Pre-check + Log Persistence

## Goal
Add a Redis liveness check to `src/api.py` startup so a clear error is logged if Redis is down. Ensure the API logs to `~/.tradeops/logs/api.log` when started via launchd.

## Tasks

<task id="2.1">
<action>
In `src/api.py`, find the startup section (near the `@app.on_event("startup")` handler or at module level after app creation). Add a Redis connectivity check that logs a clear error and raises if Redis is unreachable:

```python
import os
import redis as redis_lib

@app.on_event("startup")
async def check_redis_on_startup():
    """Fail fast if Redis is not reachable — prevents silent queue failures."""
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    try:
        r = redis_lib.from_url(redis_url, socket_connect_timeout=3)
        r.ping()
        logger.info("Redis connection OK: %s", redis_url)
    except Exception as exc:
        logger.error(
            "❌ Redis not reachable at %s: %s\n"
            "Start Redis with: redis-server --daemonize yes",
            redis_url, exc
        )
        raise RuntimeError(f"Redis required but unavailable: {exc}") from exc
```

If a startup handler already exists, add the Redis check at the top of the existing handler body. Do NOT add a duplicate `@app.on_event("startup")` decorator.
</action>
<read_first>
- src/api.py (find existing startup handlers, logger name, existing Redis client usage)
- config/settings.py (find REDIS_URL setting name)
</read_first>
<acceptance_criteria>
- src/api.py contains `check_redis_on_startup` function or the ping logic inside existing startup handler
- src/api.py contains `r.ping()` inside the startup section
- src/api.py contains `redis-server --daemonize yes` hint in the error log message
- `python3 -c "import ast; ast.parse(open('src/api.py').read()); print('OK')"` exits 0
</acceptance_criteria>
</task>

## Verification

```bash
python3 -c "import ast; ast.parse(open('src/api.py').read()); print('PASS: syntax OK')"
grep -n "r.ping()" src/api.py && echo "PASS: Redis ping present"
grep -n "daemonize" src/api.py && echo "PASS: error hint present"
```

## Must-Haves
- [ ] API logs a clear error message if Redis is unavailable at startup
- [ ] The startup check uses a 3-second connect timeout
- [ ] Python syntax validation passes
