# Local Chart Stack Launcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one-command local scripts that start and stop the TradingView chart-aware sidecar stack: TradingView CDP, local provider, and Cloudflare tunnel.

**Architecture:** Add two focused shell scripts under `scripts/` that manage only the local chart sidecar stack and store runtime state in `.runtime/chart-stack/`. Reuse the existing TradingView debug launcher, launch the local provider with `uvicorn`, launch `cloudflared` against `127.0.0.1:8765`, and keep PID/log management isolated from the rest of the app.

**Tech Stack:** Bash, existing TradingView debug launcher, Python `uvicorn`, `cloudflared`, `curl`, `grep`, `sed`

---

## File Structure

- Create: `scripts/run_local_chart_stack.sh`
  - Foreground launcher for TradingView CDP, local provider, and Cloudflare tunnel.
- Create: `scripts/stop_local_chart_stack.sh`
  - Stop script for provider and tunnel, with PID cleanup.
- Modify: `tests/` only if a lightweight shell verification approach is introduced later. No formal automated shell tests are required in v1.

### Task 1: Build the stop script first

**Files:**
- Create: `scripts/stop_local_chart_stack.sh`

- [ ] **Step 1: Write the script skeleton**

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="$ROOT_DIR/.runtime/chart-stack"
PROVIDER_PID_FILE="$RUNTIME_DIR/provider.pid"
CLOUDFLARED_PID_FILE="$RUNTIME_DIR/cloudflared.pid"
```

- [ ] **Step 2: Add PID-based stop helpers**

```bash
stop_pid_file() {
  local name="$1"
  local pid_file="$2"
  if [ ! -f "$pid_file" ]; then
    echo "[chart-stack] $name not running (no pid file)"
    return
  fi

  local pid
  pid="$(cat "$pid_file")"
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid"
    echo "[chart-stack] stopped $name (PID $pid)"
  else
    echo "[chart-stack] removing stale $name pid file"
  fi
  rm -f "$pid_file"
}
```

- [ ] **Step 3: Finish the stop flow**

```bash
mkdir -p "$RUNTIME_DIR"
stop_pid_file "cloudflared" "$CLOUDFLARED_PID_FILE"
stop_pid_file "provider" "$PROVIDER_PID_FILE"
echo "[chart-stack] TradingView left running by default"
```

- [ ] **Step 4: Make the script executable**

Run:

```bash
chmod +x scripts/stop_local_chart_stack.sh
```

Expected:

- `scripts/stop_local_chart_stack.sh` is executable.

- [ ] **Step 5: Commit the stop script**

```bash
git add scripts/stop_local_chart_stack.sh
git commit -m "DEV-123: add chart stack stop script"
```

### Task 2: Build the runtime helpers in the launcher

**Files:**
- Create: `scripts/run_local_chart_stack.sh`

- [ ] **Step 1: Write the launcher skeleton and runtime paths**

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="$ROOT_DIR/.runtime/chart-stack"
PROVIDER_LOG="$RUNTIME_DIR/provider.log"
CLOUDFLARED_LOG="$RUNTIME_DIR/cloudflared.log"
PROVIDER_PID_FILE="$RUNTIME_DIR/provider.pid"
CLOUDFLARED_PID_FILE="$RUNTIME_DIR/cloudflared.pid"
STATE_FILE="$RUNTIME_DIR/state.env"

mkdir -p "$RUNTIME_DIR"
cd "$ROOT_DIR"
export PYTHONPATH="$ROOT_DIR:${PYTHONPATH:-}"
```

- [ ] **Step 2: Add common helpers**

```bash
require_command() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "[chart-stack] missing required command: $cmd"
    exit 1
  fi
}

wait_for_url() {
  local url="$1"
  local attempts="${2:-20}"
  for _ in $(seq 1 "$attempts"); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}
```

- [ ] **Step 3: Add PID validation helpers**

```bash
pid_is_running() {
  local pid_file="$1"
  [ -f "$pid_file" ] || return 1
  local pid
  pid="$(cat "$pid_file")"
  kill -0 "$pid" 2>/dev/null
}

cleanup_stale_pid() {
  local pid_file="$1"
  if [ -f "$pid_file" ] && ! pid_is_running "$pid_file"; then
    rm -f "$pid_file"
  fi
}
```

- [ ] **Step 4: Make the script executable**

Run:

```bash
chmod +x scripts/run_local_chart_stack.sh
```

Expected:

- `scripts/run_local_chart_stack.sh` is executable.

- [ ] **Step 5: Commit the launcher skeleton**

```bash
git add scripts/run_local_chart_stack.sh
git commit -m "DEV-123: add chart stack launcher skeleton"
```

### Task 3: Add TradingView CDP verification and provider startup

**Files:**
- Modify: `scripts/run_local_chart_stack.sh`

- [ ] **Step 1: Add CDP verification logic**

```bash
ensure_cdp() {
  if curl -fsS "http://127.0.0.1:9222/json/version" >/dev/null 2>&1; then
    echo "[chart-stack] CDP already available"
    return 0
  fi

  echo "[chart-stack] launching TradingView with CDP"
  "$ROOT_DIR/mcp/tradingview-mcp/scripts/launch_tv_debug_mac.sh"

  if ! wait_for_url "http://127.0.0.1:9222/json/version" 20; then
    echo "[chart-stack] CDP did not become available"
    exit 1
  fi
}
```

- [ ] **Step 2: Add local provider startup**

```bash
ensure_provider() {
  cleanup_stale_pid "$PROVIDER_PID_FILE"

  if curl -fsS "http://127.0.0.1:8765/chart-context?symbol=VANTAGE:AUDUSD&timeframe=5m" >/dev/null 2>&1; then
    echo "[chart-stack] provider already available"
    return 0
  fi

  echo "[chart-stack] starting local provider"
  PYTHONPATH=. python3 -m uvicorn src.local_chart_provider_app:app --host 127.0.0.1 --port 8765 \
    >> "$PROVIDER_LOG" 2>&1 &
  echo $! > "$PROVIDER_PID_FILE"

  if ! wait_for_url "http://127.0.0.1:8765/chart-context?symbol=VANTAGE:AUDUSD&timeframe=5m" 20; then
    echo "[chart-stack] provider failed to start; see $PROVIDER_LOG"
    exit 1
  fi
}
```

- [ ] **Step 3: Wire the prerequisite calls into main flow**

```bash
require_command curl
require_command python3
ensure_cdp
ensure_provider
```

- [ ] **Step 4: Verify the provider path manually**

Run:

```bash
scripts/run_local_chart_stack.sh
```

Expected:

- TradingView CDP is available.
- Provider starts or is reused.
- `provider.log` is created under `.runtime/chart-stack/`.

- [ ] **Step 5: Commit the CDP/provider logic**

```bash
git add scripts/run_local_chart_stack.sh
git commit -m "DEV-123: add chart stack provider startup"
```

### Task 4: Add cloudflared startup and URL extraction

**Files:**
- Modify: `scripts/run_local_chart_stack.sh`

- [ ] **Step 1: Add tunnel URL extraction helper**

```bash
extract_tunnel_url() {
  if [ ! -f "$CLOUDFLARED_LOG" ]; then
    return 1
  fi
  grep -Eo 'https://[a-zA-Z0-9.-]+\.trycloudflare\.com' "$CLOUDFLARED_LOG" | tail -1
}
```

- [ ] **Step 2: Add cloudflared startup logic**

```bash
ensure_tunnel() {
  cleanup_stale_pid "$CLOUDFLARED_PID_FILE"

  if pid_is_running "$CLOUDFLARED_PID_FILE"; then
    echo "[chart-stack] cloudflared already running"
    return 0
  fi

  require_command cloudflared
  : > "$CLOUDFLARED_LOG"
  echo "[chart-stack] starting cloudflared tunnel"
  cloudflared tunnel --url http://127.0.0.1:8765 >> "$CLOUDFLARED_LOG" 2>&1 &
  echo $! > "$CLOUDFLARED_PID_FILE"

  for _ in $(seq 1 20); do
    if extract_tunnel_url >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done

  echo "[chart-stack] tunnel URL not detected; see $CLOUDFLARED_LOG"
  exit 1
}
```

- [ ] **Step 3: Persist the discovered URL**

```bash
write_state() {
  local tunnel_url="$1"
  cat > "$STATE_FILE" <<EOF
TUNNEL_URL=$tunnel_url
PROVIDER_URL=http://127.0.0.1:8765
CDP_URL=http://127.0.0.1:9222
EOF
}
```

- [ ] **Step 4: Print the final summary**

```bash
ensure_tunnel
TUNNEL_URL="$(extract_tunnel_url)"
write_state "$TUNNEL_URL"

echo "[chart-stack] CDP:        http://127.0.0.1:9222"
echo "[chart-stack] Provider:   http://127.0.0.1:8765"
echo "[chart-stack] Tunnel:     $TUNNEL_URL"
echo "[chart-stack] Logs:       .runtime/chart-stack/"
```

- [ ] **Step 5: Commit the tunnel management**

```bash
git add scripts/run_local_chart_stack.sh
git commit -m "DEV-123: add chart stack tunnel startup"
```

### Task 5: End-to-end verification and stop flow

**Files:**
- Modify: `scripts/run_local_chart_stack.sh` only if tiny fixes are needed
- Modify: `scripts/stop_local_chart_stack.sh` only if tiny fixes are needed

- [ ] **Step 1: Run the launcher end to end**

Run:

```bash
scripts/run_local_chart_stack.sh
```

Expected:

- A summary prints with:
  - CDP URL
  - provider URL
  - public `trycloudflare` URL
  - logs directory

- [ ] **Step 2: Verify the local provider URL**

Run:

```bash
curl "http://127.0.0.1:8765/chart-context?symbol=VANTAGE:AUDUSD&timeframe=5m"
```

Expected:

- JSON payload with `provider_timestamp`, `pine_labels`, `zones`, and `indicator_values`.

- [ ] **Step 3: Verify the public tunnel URL**

Run:

```bash
source .runtime/chart-stack/state.env && curl "$TUNNEL_URL/chart-context?symbol=VANTAGE:AUDUSD&timeframe=5m"
```

Expected:

- The same chart-context JSON is returned through the tunnel.

- [ ] **Step 4: Verify the stop script**

Run:

```bash
scripts/stop_local_chart_stack.sh
```

Expected:

- provider and cloudflared are stopped
- PID files are removed
- TradingView remains running

- [ ] **Step 5: Commit the verified launcher**

```bash
git add scripts/run_local_chart_stack.sh scripts/stop_local_chart_stack.sh
git commit -m "DEV-123: add local chart stack launcher"
```

## Self-Review

- Spec coverage:
  - launcher script: Tasks 2-4
  - stop script: Task 1 and Task 5
  - runtime folder and PID/log handling: Tasks 1, 2, and 4
  - CDP/provider/tunnel reuse: Tasks 3 and 4
  - printed tunnel summary: Task 4
- Placeholder scan:
  - no TBD/TODO placeholders remain
- Type and naming consistency:
  - plan consistently uses `.runtime/chart-stack/`, `run_local_chart_stack.sh`, `stop_local_chart_stack.sh`, `provider.pid`, `cloudflared.pid`, and `state.env`
