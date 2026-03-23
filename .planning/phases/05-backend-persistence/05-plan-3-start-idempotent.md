---
plan: "05-plan-3-start-idempotent"
phase: "05"
wave: 2
depends_on: ["05-plan-1-launchd"]
files_modified:
  - "start.sh"
requirements:
  - INFRA-03
  - INFRA-04
autonomous: true
---

# Plan 3: Idempotent start.sh + Single-command Full Stack

## Goal
Update `start.sh fullstack` to be idempotent (check if port 8000 is already in use before spawning), use launchd if installed, and fall back gracefully to background processes with PID tracking.

## Tasks

<task id="3.1">
<action>
Read the existing `start.sh` fully. Then add/replace the `fullstack` section so it:

1. Checks if Redis is already running (`redis-cli ping 2>/dev/null || redis-server --daemonize yes`)
2. Checks if port 8000 is already occupied: `lsof -ti:8000 | head -1`
3. If launchd services are installed (`launchctl list | grep com.tradeops.api`), uses them instead of starting manually
4. Otherwise, starts API + Worker as background processes writing to `~/.tradeops/logs/`

The idempotent fullstack block should look like:

```bash
fullstack)
  LOG_DIR="$HOME/.tradeops/logs"
  mkdir -p "$LOG_DIR"

  # Redis
  if redis-cli ping 2>/dev/null | grep -q PONG; then
    echo "✅ Redis already running"
  else
    redis-server --daemonize yes
    echo "✅ Redis started"
  fi

  # API
  if lsof -ti:8000 &>/dev/null; then
    echo "✅ API already running on port 8000"
  elif launchctl list 2>/dev/null | grep -q com.tradeops.api; then
    launchctl start com.tradeops.api
    echo "✅ API started via launchd"
  else
    source venv/bin/activate
    PYTHONPATH=$(pwd) python3 -m uvicorn src.api:app --host 0.0.0.0 --port 8000 \
      >> "$LOG_DIR/api.log" 2>&1 &
    echo $! > /tmp/tradeops-api.pid
    echo "✅ API started (PID $(cat /tmp/tradeops-api.pid)) → logs: $LOG_DIR/api.log"
  fi

  # Worker
  if pgrep -f "src.worker" &>/dev/null; then
    echo "✅ Worker already running"
  elif launchctl list 2>/dev/null | grep -q com.tradeops.worker; then
    launchctl start com.tradeops.worker
    echo "✅ Worker started via launchd"
  else
    source venv/bin/activate
    PYTHONPATH=$(pwd) python3 -m src.worker \
      >> "$LOG_DIR/worker.log" 2>&1 &
    echo $! > /tmp/tradeops-worker.pid
    echo "✅ Worker started (PID $(cat /tmp/tradeops-worker.pid)) → logs: $LOG_DIR/worker.log"
  fi

  # Frontend (unchanged)
  echo "Starting frontend..."
  cd frontend && npm run dev &
  cd ..
  echo ""
  echo "🚀 Full stack running. Logs: $LOG_DIR/"
  ;;
```

Preserve all existing `start.sh` cases (api, worker, frontend, etc.) — only modify/add the fullstack case.
</action>
<read_first>
- start.sh (read the ENTIRE file to understand existing structure before editing)
</read_first>
<acceptance_criteria>
- start.sh contains `lsof -ti:8000` check in the fullstack case
- start.sh contains `redis-cli ping` check
- start.sh contains `launchctl list` check for com.tradeops.api
- start.sh contains `/tmp/tradeops-api.pid` PID file write
- start.sh contains `$LOG_DIR/api.log` log redirection
- `bash -n start.sh` exits 0 (syntax valid)
</acceptance_criteria>
</task>

## Verification

```bash
bash -n start.sh && echo "PASS: start.sh syntax valid"
grep -n "lsof -ti:8000" start.sh && echo "PASS: port check present"
grep -n "redis-cli ping" start.sh && echo "PASS: Redis idempotency present"
grep -n "tradeops-api.pid" start.sh && echo "PASS: PID file present"
```

## Must-Haves
- [ ] Running `./start.sh fullstack` twice shows "already running" on second run
- [ ] Logs go to `~/.tradeops/logs/api.log` and `worker.log`
- [ ] `bash -n start.sh` passes
