#!/usr/bin/env bash
set -euo pipefail

# Test Suite Runner for CI
# Runs unit, integration, and e2e tests with proper Redis lifecycle management

export TRINITY_ENV=test

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG_DIR="logs"
mkdir -p "$LOG_DIR"

TEST_LOG="$LOG_DIR/test_suite_${TIMESTAMP}.log"
DOCKER_LOG="$LOG_DIR/docker_${TIMESTAMP}.log"

# Track test failures
FAILED=0

cleanup() {
    echo ""
    echo "==== Collecting docker logs -> $DOCKER_LOG ===="
    docker compose -f docker-compose.test.yml logs --no-color > "$DOCKER_LOG" 2>&1 || true

    echo "==== Tearing down Redis ===="
    docker compose -f docker-compose.test.yml down -v --remove-orphans >> "$TEST_LOG" 2>&1 || true

    echo ""
    echo "Test log:   $TEST_LOG"
    echo "Docker log: $DOCKER_LOG"

    exit $FAILED
}
trap cleanup EXIT

log() {
    echo "$@" | tee -a "$TEST_LOG"
}

run_pytest() {
    local marker="$1"
    log ""
    log "==== Running pytest -m $marker ===="
    # Use --color=no to disable ANSI colors, capture both stdout and stderr
    if ! pytest -m "$marker" -v --color=no >> "$TEST_LOG" 2>&1; then
        log "FAILED: pytest -m $marker"
        FAILED=1
    else
        log "PASSED: pytest -m $marker"
    fi
}

log "==== START $(date) ===="
log "TEST_LOG=$TEST_LOG"
log "TRINITY_ENV=$TRINITY_ENV"
log "======================="

# Start only Redis
log ""
log "==== Starting Redis ===="
docker compose -f docker-compose.test.yml up -d redis >> "$TEST_LOG" 2>&1

# Wait for Redis to be ready
log "Waiting for Redis to be ready..."
MAX_RETRIES=30
RETRY_COUNT=0
while ! docker compose -f docker-compose.test.yml exec -T redis redis-cli ping >> "$TEST_LOG" 2>&1; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        log "ERROR: Redis failed to become ready after $MAX_RETRIES attempts"
        FAILED=1
        exit 1
    fi
    log "Redis not ready yet, retrying ($RETRY_COUNT/$MAX_RETRIES)..."
    sleep 1
done
log "Redis is ready!"

# Run tests in order: unit, integration, e2e
run_pytest "unit"
run_pytest "integration"
run_pytest "e2e"

log ""
log "==== DONE $(date) ===="

if [ $FAILED -ne 0 ]; then
    log "Some tests FAILED"
else
    log "All tests PASSED"
fi
