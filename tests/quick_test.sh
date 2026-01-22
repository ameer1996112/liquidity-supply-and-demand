#!/bin/bash

# Quick E2E Test Script
# Usage: ./tests/quick_test.sh

set -e

# Load environment variables if .env exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

BASE_URL="${WEBHOOK_URL:-https://grand-learning-production-bc96.up.railway.app}"
PASSPHRASE="${WEBHOOK_PASSPHRASE}"
ZONE_ID=99999

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Running Quick E2E Tests${NC}"
echo "Target: $BASE_URL"
echo ""

# Check if passphrase is set
if [ -z "$PASSPHRASE" ] || [ "$PASSPHRASE" = "YOUR_WEBHOOK_PASSPHRASE" ]; then
    echo -e "${RED}❌ ERROR: WEBHOOK_PASSPHRASE not set${NC}"
    echo "Set it with: export WEBHOOK_PASSPHRASE=your_passphrase"
    exit 1
fi

# Test 1: Health Check
echo -e "${BLUE}Test 1: Health Check${NC}"
HEALTH_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/health")
if [ "$HEALTH_RESPONSE" = "200" ]; then
  echo -e "${GREEN}✅ PASS: Health check returned 200${NC}"
else
  echo -e "${RED}❌ FAIL: Health check returned $HEALTH_RESPONSE${NC}"
  exit 1
fi

# Test 2: Entry Webhook
echo -e "${BLUE}Test 2: Entry Webhook${NC}"
ENTRY_RESPONSE=$(curl -s -X POST "$BASE_URL/webhook" \
  -H "Content-Type: application/json" \
  -d "{
    \"passphrase\": \"$PASSPHRASE\",
    \"symbol\": \"EURUSD\",
    \"side\": \"buy\",
    \"entry\": 1.08500,
    \"sl\": 1.08400,
    \"tp\": 1.08700,
    \"size\": 0.10,
    \"zone_id\": $ZONE_ID,
    \"zone_type\": \"demand\",
    \"zone_top\": 1.08520,
    \"zone_bottom\": 1.08480,
    \"rr_ratio\": 2.0,
    \"sl_pips\": 10.0,
    \"entry_model\": \"FLIP\",
    \"liq_swept\": true,
    \"target_swept\": true,
    \"caused_sweep\": true,
    \"is_accuracy\": false,
    \"score\": 75.5,
    \"freshness\": 1,
    \"session\": 2,
    \"atr_ratio\": 0.85,
    \"trend\": 1,
    \"rsi\": 58.5,
    \"htf_trend\": 1,
    \"rvol\": 1.35,
    \"adx\": 28.3,
    \"touch_count\": 1,
    \"base_quality\": 82.0,
    \"departure_strength\": 78.5,
    \"liquidity_distance\": 15.2,
    \"liquidity_spread\": 45.8,
    \"return_strength\": 88.5
  }")

if echo "$ENTRY_RESPONSE" | grep -q "success"; then
  echo -e "${GREEN}✅ PASS: Entry webhook accepted${NC}"
  echo "Response: $ENTRY_RESPONSE"
else
  echo -e "${RED}❌ FAIL: Entry webhook rejected${NC}"
  echo "Response: $ENTRY_RESPONSE"
  exit 1
fi

# Wait for DB write
echo -e "${YELLOW}⏳ Waiting 2 seconds for database write...${NC}"
sleep 2

# Test 3: Exit Webhook
echo -e "${BLUE}Test 3: Exit Webhook${NC}"
EXIT_RESPONSE=$(curl -s -X POST "$BASE_URL/webhook/exit" \
  -H "Content-Type: application/json" \
  -d "{
    \"event_type\": \"exit\",
    \"passphrase\": \"$PASSPHRASE\",
    \"zone_id\": $ZONE_ID,
    \"outcome\": \"win\",
    \"bars_held\": 18,
    \"close_price\": 1.08700,
    \"pnl_r\": 2.0,
    \"exit_type\": \"tp_hit\",
    \"mae_pips\": 3.5,
    \"close_time\": \"2026-01-22 12:00:00\"
  }")

if echo "$EXIT_RESPONSE" | grep -q "success"; then
  echo -e "${GREEN}✅ PASS: Exit webhook accepted${NC}"
  echo "Response: $EXIT_RESPONSE"
else
  echo -e "${RED}❌ FAIL: Exit webhook rejected${NC}"
  echo "Response: $EXIT_RESPONSE"
  exit 1
fi

echo ""
echo -e "${GREEN}✅ ALL BASIC TESTS PASSED${NC}"
echo -e "${YELLOW}ℹ️  Run 'python tests/e2e_test.py' for full test suite with database validation${NC}"
exit 0
