# Trading System Test Suite Makefile
#
# Usage:
#   make test-unit       # Run unit tests only (fast, no dependencies)
#   make test-int        # Run integration tests (requires Redis)
#   make test-e2e        # Run E2E tests (requires Redis)
#   make test-all        # Run all tests
#   make test-fast       # Run unit tests + quick integration tests
#
# Setup:
#   make setup-test      # Start test infrastructure (Redis)
#   make teardown-test   # Stop test infrastructure

.PHONY: test-unit test-int test-e2e test-all test test-fast test-ci ci-test setup-test teardown-test clean lint

# Environment
export TRINITY_ENV=test
export TEST_REDIS_URL=redis://localhost:6379

# ══════════════════════════════════════════════════════════
# TEST COMMANDS
# ══════════════════════════════════════════════════════════

test-unit:
	@echo "Running unit tests (no external dependencies)..."
	pytest tests/unit -v -m unit --tb=short

test-int:
	@echo "Running integration tests (requires Redis)..."
	@echo "Make sure Redis is running: make setup-test"
	pytest tests/integration -v -m integration --tb=short

test-e2e:
	@echo "Running E2E tests (requires Redis)..."
	@echo "Make sure Redis is running: make setup-test"
	pytest tests/e2e -v -m e2e --tb=short

test-all:
	@echo "Running ALL tests..."
	pytest tests -v --tb=short

test-fast:
	@echo "Running fast tests (unit + quick integration)..."
	pytest tests -v -m "unit or (integration and not slow)" --tb=short

test:
	@echo "Running full test suite: setup -> unit -> integration -> e2e -> teardown"
	$(MAKE) setup-test
	@$(MAKE) test-unit && $(MAKE) test-int && $(MAKE) test-e2e
	$(MAKE) teardown-test

test-coverage:
	@echo "Running tests with coverage report..."
	pytest tests --cov=backend --cov-report=html --cov-report=term-missing

test-ci:
	@echo "Running CI test suite (logs to logs/ directory)..."
	./scripts/run_test_suite.sh

ci-test: test-ci

# ══════════════════════════════════════════════════════════
# INFRASTRUCTURE COMMANDS
# ══════════════════════════════════════════════════════════

setup-test:
	@echo "Starting test infrastructure..."
	docker compose -f docker-compose.test.yml up -d
	@echo "Waiting for Redis to be ready..."
	@sleep 2
	@docker exec trading_test_redis redis-cli ping || echo "Redis not ready yet..."
	@echo "Test infrastructure ready!"

teardown-test:
	@echo "Stopping test infrastructure..."
	docker compose -f docker-compose.test.yml down
	@echo "Test infrastructure stopped."

check-redis:
	@echo "Checking Redis connection..."
	@docker exec trading_test_redis redis-cli ping && echo "Redis OK!" || echo "Redis not available"

# ══════════════════════════════════════════════════════════
# UTILITY COMMANDS
# ══════════════════════════════════════════════════════════

clean:
	@echo "Cleaning test artifacts..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf htmlcov .coverage 2>/dev/null || true
	@echo "Clean complete."

lint:
	@echo "Running linters..."
	@which ruff > /dev/null && ruff check backend tests || echo "ruff not installed, skipping..."
	@which mypy > /dev/null && mypy backend --ignore-missing-imports || echo "mypy not installed, skipping..."

# ══════════════════════════════════════════════════════════
# HELP
# ══════════════════════════════════════════════════════════

help:
	@echo "Trading System Test Suite"
	@echo ""
	@echo "Test Commands:"
	@echo "  make test-unit      Run unit tests (fast, no dependencies)"
	@echo "  make test-int       Run integration tests (requires Redis)"
	@echo "  make test-e2e       Run E2E tests (requires Redis)"
	@echo "  make test-all       Run all tests"
	@echo "  make test-fast      Run unit + quick integration tests"
	@echo "  make test-coverage  Run tests with coverage report"
	@echo "  make test-ci        Run CI test suite with logging"
	@echo "  make ci-test        Alias for test-ci"
	@echo ""
	@echo "Infrastructure Commands:"
	@echo "  make setup-test     Start test infrastructure (Redis)"
	@echo "  make teardown-test  Stop test infrastructure"
	@echo "  make check-redis    Verify Redis connection"
	@echo ""
	@echo "Utility Commands:"
	@echo "  make clean          Remove test artifacts"
	@echo "  make lint           Run linters"
	@echo ""
	@echo "Quick Start:"
	@echo "  make setup-test && make test-all && make teardown-test"
