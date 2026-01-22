#!/bin/bash

# Test Suite Setup Script
# Installs dependencies and configures environment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Trading System Test Suite Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Step 1: Check Python version
echo -e "${BLUE}Step 1: Checking Python version...${NC}"
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d ' ' -f 2 | cut -d '.' -f 1,2)
    echo -e "${GREEN}✓ Python 3 found: $(python3 --version)${NC}"
else
    echo -e "${RED}✗ Python 3 not found${NC}"
    echo "Please install Python 3.9 or higher"
    exit 1
fi

# Step 2: Install dependencies
echo ""
echo -e "${BLUE}Step 2: Installing dependencies...${NC}"
if [ -f "requirements-test.txt" ]; then
    pip3 install -r requirements-test.txt
    echo -e "${GREEN}✓ Dependencies installed${NC}"
else
    echo -e "${RED}✗ requirements-test.txt not found${NC}"
    exit 1
fi

# Step 3: Create .env file
echo ""
echo -e "${BLUE}Step 3: Creating .env configuration...${NC}"
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${GREEN}✓ Created .env from template${NC}"
        echo -e "${YELLOW}⚠️  Please edit .env and add your credentials${NC}"
        echo ""
        echo "Required variables:"
        echo "  - WEBHOOK_PASSPHRASE"
        echo "  - SUPABASE_URL"
        echo "  - SUPABASE_ANON_KEY"
        echo "  - DISCORD_WEBHOOK_URL (optional)"
    else
        echo -e "${RED}✗ .env.example not found${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠️  .env already exists, skipping${NC}"
fi

# Step 4: Make scripts executable
echo ""
echo -e "${BLUE}Step 4: Making scripts executable...${NC}"
chmod +x quick_test.sh 2>/dev/null || true
chmod +x e2e_test.py 2>/dev/null || true
echo -e "${GREEN}✓ Scripts are executable${NC}"

# Step 5: Verify configuration
echo ""
echo -e "${BLUE}Step 5: Verifying configuration...${NC}"
if [ -f ".env" ]; then
    source .env

    if [ -z "$WEBHOOK_PASSPHRASE" ] || [ "$WEBHOOK_PASSPHRASE" = "YOUR_WEBHOOK_PASSPHRASE" ]; then
        echo -e "${RED}✗ WEBHOOK_PASSPHRASE not set in .env${NC}"
        CONFIG_VALID=false
    else
        echo -e "${GREEN}✓ WEBHOOK_PASSPHRASE configured${NC}"
    fi

    if [ -z "$SUPABASE_URL" ] || [ "$SUPABASE_URL" = "https://your-project.supabase.co" ]; then
        echo -e "${RED}✗ SUPABASE_URL not set in .env${NC}"
        CONFIG_VALID=false
    else
        echo -e "${GREEN}✓ SUPABASE_URL configured${NC}"
    fi

    if [ -z "$SUPABASE_ANON_KEY" ] || [ "$SUPABASE_ANON_KEY" = "your_supabase_anon_key_here" ]; then
        echo -e "${RED}✗ SUPABASE_ANON_KEY not set in .env${NC}"
        CONFIG_VALID=false
    else
        echo -e "${GREEN}✓ SUPABASE_ANON_KEY configured${NC}"
    fi

    if [ -z "$DISCORD_WEBHOOK_URL" ]; then
        echo -e "${YELLOW}⚠️  DISCORD_WEBHOOK_URL not set (optional)${NC}"
    else
        echo -e "${GREEN}✓ DISCORD_WEBHOOK_URL configured${NC}"
    fi
fi

# Summary
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Setup Complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

if [ "$CONFIG_VALID" = false ]; then
    echo -e "${YELLOW}⚠️  Configuration incomplete${NC}"
    echo "Please edit .env and add your credentials:"
    echo "  nano .env"
    echo ""
    echo "Then run tests:"
    echo "  python3 e2e_test.py"
else
    echo -e "${GREEN}✓ All checks passed${NC}"
    echo ""
    echo "Run tests with:"
    echo "  ${GREEN}python3 e2e_test.py${NC}    (full suite)"
    echo "  ${GREEN}./quick_test.sh${NC}        (quick check)"
fi

echo ""
