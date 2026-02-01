#!/usr/bin/env bash
set -euo pipefail

mkdir -p logs
TS="$(date +%Y%m%d_%H%M%S)"
TEST_LOG="logs/test_suite_${TS}.log"
DOCKER_LOG="logs/docker_${TS}.log"

export TRINITY_ENV=test

{
  echo "==== START $(date) ===="
  echo "TEST_LOG=$TEST_LOG"
  echo "TRINITY_ENV=$TRINITY_ENV"
  echo "======================="
  echo

  echo "==== Starting Redis ===="
  docker compose -f docker-compose.test.yml up -d

  # Always collect docker logs + teardown, even if pytest fails
  cleanup() {
    echo
    echo "==== Collecting docker logs -> $DOCKER_LOG ===="
    docker compose -f docker-compose.test.yml logs --no-color > "$DOCKER_LOG" 2>&1 || true
    echo "==== Tearing down Redis ===="
    docker compose -f docker-compose.test.yml down -v || true
  }
  trap cleanup EXIT

  echo "Waiting for Redis to be ready..."
  # If your compose service is named "redis", this works reliably:
  for i in {1..30}; do
    if docker compose -f docker-compose.test.yml exec -T redis redis-cli ping >/dev/null 2>&1; then
      echo "Redis is ready!"
      break
    fi
    sleep 0.2
  done

  echo
  echo "==== Running pytest -m unit ===="
  pytest -m unit

  echo
  echo "==== Running pytest -m integration ===="
  pytest -m integration

  echo
  echo "==== Running pytest -m e2e ===="
  pytest -m e2e

  echo
  echo "==== DONE $(date) ===="
  echo "All tests PASSED"
  echo
  echo "Test log:   $TEST_LOG"
  echo "Docker log: $DOCKER_LOG"
} 2>&1 | tee "$TEST_LOG"
