# Local Chart Stack Launcher Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the local chart stack launcher reliably reuse only script-owned, current provider and tunnel processes, while adding a clean `--fresh` restart path.

**Architecture:** Keep the existing two-script operator flow and harden the trust model inside `scripts/run_local_chart_stack.sh`. The launcher should classify provider state from tracked PID files plus a strict `/chart-context` contract probe, refuse unmanaged listeners on `127.0.0.1:8765`, and restart tracked provider/tunnel cleanly when `--fresh` is requested.

**Tech Stack:** Bash, `curl`, `grep`, `sed`, `lsof`, existing TradingView debug launcher, project `venv` Python, `cloudflared`

---

## File Structure

- Modify: `scripts/run_local_chart_stack.sh`
  - Add argument parsing, tracked-process validation, provider contract inspection, conflict detection, tunnel reuse hardening, and `--fresh`.
- Reuse: `scripts/stop_local_chart_stack.sh`
  - Keep the tracked PID stop behavior as the clean restart primitive and day-to-day stop command.

### Task 1: Harden runtime helpers and argument parsing

**Files:**
- Modify: `scripts/run_local_chart_stack.sh`

- [ ] **Step 1: Add `--fresh` argument parsing near the top of the script**

```bash
FRESH_RESTART=0
case "${1:-}" in
  "")
    ;;
  --fresh)
    FRESH_RESTART=1
    ;;
  *)
    echo "[chart-stack] unknown argument: ${1}"
    echo "[chart-stack] usage: ./scripts/run_local_chart_stack.sh [--fresh]"
    exit 1
    ;;
esac
```

- [ ] **Step 2: Add a port-listener helper for unmanaged conflict detection**

```bash
get_listener_pid() {
  local port="$1"
  lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | head -n 1
}
```

- [ ] **Step 3: Add a tracked-PID reader helper so later checks stay consistent**

```bash
read_pid_file() {
  local pid_file="$1"
  [ -f "$pid_file" ] || return 1
  tr -d '[:space:]' < "$pid_file"
}
```

- [ ] **Step 4: Add a helper that stops only tracked processes for `--fresh`**

```bash
stop_tracked_pid() {
  local name="$1"
  local pid_file="$2"
  if ! pid_is_running "$pid_file"; then
    rm -f "$pid_file"
    return 0
  fi

  local pid
  pid="$(read_pid_file "$pid_file")"
  kill "$pid"
  echo "[chart-stack] stopped tracked $name (PID $pid)"
  rm -f "$pid_file"
}
```

- [ ] **Step 5: Add a `fresh_restart` helper before the provider/tunnel startup flow**

```bash
fresh_restart() {
  echo "[chart-stack] --fresh requested, restarting tracked provider and tunnel"
  stop_tracked_pid "cloudflared" "$CLOUDFLARED_PID_FILE"
  stop_tracked_pid "provider" "$PROVIDER_PID_FILE"
  rm -f "$STATE_FILE"
}
```

- [ ] **Step 6: Wire the new mode into the main flow before `ensure_cdp`**

```bash
if [ "$FRESH_RESTART" -eq 1 ]; then
  fresh_restart
fi
```

- [ ] **Step 7: Syntax-check the script after the helper changes**

Run:

```bash
bash -n scripts/run_local_chart_stack.sh
```

Expected:

- No output
- Exit code `0`

- [ ] **Step 8: Commit the helper and `--fresh` scaffolding**

```bash
git add scripts/run_local_chart_stack.sh
git commit -m "DEV-125: add launcher restart scaffolding"
```

### Task 2: Add strict provider contract validation and conflict classification

**Files:**
- Modify: `scripts/run_local_chart_stack.sh`

- [ ] **Step 1: Add a provider probe helper that captures the JSON response**

```bash
probe_provider() {
  curl -fsS "http://127.0.0.1:8765/chart-context?symbol=VANTAGE:AUDUSD&timeframe=5m"
}
```

- [ ] **Step 2: Add a contract validator that requires the current chart-context shape**

```bash
provider_has_current_contract() {
  local response="$1"
  printf '%s' "$response" | grep -q '"provider_timestamp"' &&
    printf '%s' "$response" | grep -q '"zones"' &&
    printf '%s' "$response" | grep -q '"pine_labels"' &&
    printf '%s' "$response" | grep -q '"indicator_values"' &&
    printf '%s' "$response" | grep -q '"setup_evidence"'
}
```

- [ ] **Step 3: Add a provider-state classifier**

```bash
provider_state() {
  cleanup_stale_pid "$PROVIDER_PID_FILE"

  local tracked_pid=""
  local listener_pid=""
  local response=""

  if pid_is_running "$PROVIDER_PID_FILE"; then
    tracked_pid="$(read_pid_file "$PROVIDER_PID_FILE")"
  fi

  listener_pid="$(get_listener_pid 8765 || true)"

  if [ -n "$tracked_pid" ] && [ "$tracked_pid" = "${listener_pid:-}" ]; then
    response="$(probe_provider 2>/dev/null || true)"
    if [ -z "$response" ]; then
      echo down
      return 0
    fi
    if provider_has_current_contract "$response"; then
      echo healthy
    else
      echo stale
    fi
    return 0
  fi

  if [ -n "${listener_pid:-}" ]; then
    echo conflict
    return 0
  fi

  echo down
}
```

- [ ] **Step 4: Rewrite `ensure_provider()` to use the classifier instead of “anything on 8765”**

```bash
ensure_provider() {
  local state
  state="$(provider_state)"

  case "$state" in
    healthy)
      echo "[chart-stack] provider healthy, reusing tracked process"
      return 0
      ;;
    stale)
      echo "[chart-stack] provider stale: missing setup_evidence; rerun with --fresh"
      exit 1
      ;;
    conflict)
      echo "[chart-stack] provider conflict on 8765: unmanaged PID $(get_listener_pid 8765)"
      echo "[chart-stack] stop the unmanaged process or rerun after clearing the port"
      exit 1
      ;;
    down)
      echo "[chart-stack] provider down, starting tracked process"
      : > "$PROVIDER_LOG"
      PYTHONPATH=. "$VENV_PYTHON" -m uvicorn src.local_chart_provider_app:app --host 127.0.0.1 --port 8765 \
        >> "$PROVIDER_LOG" 2>&1 &
      echo $! > "$PROVIDER_PID_FILE"
      ;;
    *)
      echo "[chart-stack] unknown provider state: $state"
      exit 1
      ;;
  esac

  local response=""
  for _ in $(seq 1 20); do
    response="$(probe_provider 2>/dev/null || true)"
    if [ -n "$response" ] && provider_has_current_contract "$response"; then
      echo "[chart-stack] provider ready with current contract"
      return 0
    fi
    sleep 1
  done

  echo "[chart-stack] provider failed to satisfy current contract; see $PROVIDER_LOG"
  exit 1
}
```

- [ ] **Step 5: Verify normal startup from a clean tracked state**

Run:

```bash
./scripts/stop_local_chart_stack.sh
./scripts/run_local_chart_stack.sh --fresh
```

Expected:

- Output includes `provider down, starting tracked process` or `provider ready with current contract`
- Output does not say `provider already available`
- `.runtime/chart-stack/provider.pid` exists

- [ ] **Step 6: Verify stale-provider detection with a manual old listener simulation**

Run:

```bash
./venv/bin/python -m http.server 8765 >/tmp/dev125-stale.log 2>&1 &
STALE_PID=$!
./scripts/run_local_chart_stack.sh
kill "$STALE_PID"
```

Expected:

- Launcher exits non-zero
- Output includes `provider conflict on 8765: unmanaged PID`

- [ ] **Step 7: Commit the provider hardening**

```bash
git add scripts/run_local_chart_stack.sh
git commit -m "DEV-125: harden provider reuse checks"
```

### Task 3: Harden tunnel reuse and end-to-end operator verification

**Files:**
- Modify: `scripts/run_local_chart_stack.sh`

- [ ] **Step 1: Add a tracked tunnel-state helper**

```bash
tunnel_state() {
  cleanup_stale_pid "$CLOUDFLARED_PID_FILE"

  if pid_is_running "$CLOUDFLARED_PID_FILE"; then
    if extract_tunnel_url >/dev/null 2>&1; then
      echo healthy
    else
      echo stale
    fi
    return 0
  fi

  echo down
}
```

- [ ] **Step 2: Rewrite `ensure_tunnel()` to reuse only tracked healthy tunnels**

```bash
ensure_tunnel() {
  local state
  state="$(tunnel_state)"

  case "$state" in
    healthy)
      echo "[chart-stack] tunnel healthy, reusing tracked process"
      return 0
      ;;
    stale|down)
      require_command cloudflared
      rm -f "$CLOUDFLARED_PID_FILE"
      : > "$CLOUDFLARED_LOG"
      echo "[chart-stack] starting cloudflared tunnel"
      cloudflared tunnel --url http://127.0.0.1:8765 >> "$CLOUDFLARED_LOG" 2>&1 &
      echo $! > "$CLOUDFLARED_PID_FILE"
      ;;
    *)
      echo "[chart-stack] unknown tunnel state: $state"
      exit 1
      ;;
  esac

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

- [ ] **Step 3: Keep the operator output aligned with the new state model**

```bash
echo "[chart-stack] CDP:        http://127.0.0.1:9222"
echo "[chart-stack] Provider:   http://127.0.0.1:8765"
echo "[chart-stack] Tunnel:     $TUNNEL_URL"
echo "[chart-stack] Logs:       .runtime/chart-stack/"
echo "[chart-stack] Note:       tunnel may take a few seconds to become reachable"
```

Expected:

- Startup logs now clearly distinguish healthy reuse from fresh starts and hard failures.

- [ ] **Step 4: Verify the tracked happy path and the public provider contract**

Run:

```bash
./scripts/run_local_chart_stack.sh --fresh
source .runtime/chart-stack/state.env
curl "http://127.0.0.1:8765/chart-context?symbol=VANTAGE:AUDUSD&timeframe=5m" | grep -q '"setup_evidence"'
curl "$TUNNEL_URL/chart-context?symbol=VANTAGE:AUDUSD&timeframe=5m" | grep -q '"setup_evidence"'
```

Expected:

- Both `grep` commands exit `0`
- The tunnel request returns the current provider contract including `setup_evidence`

- [ ] **Step 5: Verify safe reuse on a second run**

Run:

```bash
./scripts/run_local_chart_stack.sh
```

Expected:

- Output includes `provider healthy, reusing tracked process`
- Output includes `tunnel healthy, reusing tracked process`

- [ ] **Step 6: Verify the clean shutdown path still works**

Run:

```bash
./scripts/stop_local_chart_stack.sh
bash -n scripts/run_local_chart_stack.sh
bash -n scripts/stop_local_chart_stack.sh
```

Expected:

- Stop script reports tracked provider/tunnel shutdown
- Both syntax checks exit `0`

- [ ] **Step 7: Commit the tunnel hardening and verification-ready launcher**

```bash
git add scripts/run_local_chart_stack.sh
git commit -m "DEV-125: harden chart stack launcher reuse"
```

## Final Verification

- [ ] **Step 1: Run the shell validation sequence**

```bash
bash -n scripts/run_local_chart_stack.sh
bash -n scripts/stop_local_chart_stack.sh
./scripts/run_local_chart_stack.sh --fresh
./scripts/run_local_chart_stack.sh
./scripts/stop_local_chart_stack.sh
```

Expected:

- No syntax errors
- `--fresh` performs a clean tracked restart
- Normal rerun safely reuses only tracked healthy provider/tunnel processes

- [ ] **Step 2: Inspect the runtime state files**

Run:

```bash
cat .runtime/chart-stack/state.env
test -f .runtime/chart-stack/provider.pid
test -f .runtime/chart-stack/cloudflared.pid
```

Expected:

- `state.env` contains `TUNNEL_URL`, `PROVIDER_URL`, and `CDP_URL`
- PID files exist after startup and are removed by the stop script

- [ ] **Step 3: Create the final implementation commit**

```bash
git add scripts/run_local_chart_stack.sh scripts/stop_local_chart_stack.sh
git commit -m "DEV-125: harden chart stack launcher reliability"
```
