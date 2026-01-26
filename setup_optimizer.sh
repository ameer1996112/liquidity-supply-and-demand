#!/bin/bash

# Trading Filter Optimizer - Quick Setup Script
# This script helps you set up the optimizer with minimal manual steps

set -e  # Exit on any error

echo "=================================================="
echo "🚀 Trading Filter Optimizer - Quick Setup"
echo "=================================================="
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${YELLOW}ℹ${NC} $1"
}

# Check if Python is installed
echo "1️⃣  Checking Python installation..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    print_success "Python is installed: $PYTHON_VERSION"
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_VERSION=$(python --version)
    print_success "Python is installed: $PYTHON_VERSION"
    PYTHON_CMD="python"
else
    print_error "Python is not installed"
    echo "   Please install Python 3.8 or higher from https://www.python.org/"
    exit 1
fi
echo ""

# Check if pip is installed
echo "2️⃣  Checking pip installation..."
if command -v pip3 &> /dev/null; then
    print_success "pip is installed"
    PIP_CMD="pip3"
elif command -v pip &> /dev/null; then
    print_success "pip is installed"
    PIP_CMD="pip"
else
    print_error "pip is not installed"
    exit 1
fi
echo ""

# Install dependencies
echo "3️⃣  Installing dependencies..."
print_info "Installing packages from requirements_optimizer.txt..."

if $PIP_CMD install -r requirements_optimizer.txt --quiet; then
    print_success "All dependencies installed successfully"
else
    print_error "Failed to install dependencies"
    echo "   Try running manually: $PIP_CMD install -r requirements_optimizer.txt"
    exit 1
fi
echo ""

# Check for .env file
echo "4️⃣  Checking environment configuration..."
if [ -f .env ]; then
    print_success ".env file already exists"
    print_info "Make sure it contains SUPABASE_URL and SUPABASE_KEY"
else
    print_info ".env file not found"

    # Ask if user wants to create it now
    read -p "   Would you like to create it now? (y/n): " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo ""
        echo "   Please enter your Supabase credentials:"
        echo "   (Find these in: Supabase Dashboard > Settings > API)"
        echo ""

        read -p "   Supabase URL: " SUPABASE_URL
        read -p "   Supabase Key: " SUPABASE_KEY

        # Create .env file
        cat > .env << EOF
# Supabase Configuration
SUPABASE_URL=$SUPABASE_URL
SUPABASE_KEY=$SUPABASE_KEY
EOF

        print_success ".env file created"
    else
        print_info "You can create it manually by copying .env.example:"
        echo "   cp .env.example .env"
        echo "   Then edit .env with your credentials"
    fi
fi
echo ""

# Load environment variables if .env exists
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
    print_success "Environment variables loaded"
else
    print_info "Skipping environment variable loading (no .env file)"
fi
echo ""

# Run validation test
echo "5️⃣  Running setup validation..."
print_info "Testing connection and data structure..."
echo ""

if [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_KEY" ]; then
    print_error "Environment variables not set"
    echo "   Please set SUPABASE_URL and SUPABASE_KEY in .env file or export them:"
    echo "   export SUPABASE_URL='https://your-project.supabase.co'"
    echo "   export SUPABASE_KEY='your-key-here'"
    echo ""
    print_info "Skipping validation test"
else
    if $PYTHON_CMD test_optimizer_setup.py; then
        echo ""
        print_success "Setup validation passed!"
    else
        echo ""
        print_error "Setup validation failed"
        echo "   Please review the errors above and fix them"
        echo "   See OPTIMIZER_GUIDE.md for detailed troubleshooting"
        exit 1
    fi
fi
echo ""

# Summary
echo "=================================================="
echo "✅ Setup Complete!"
echo "=================================================="
echo ""
echo "📋 What's installed:"
echo "   • pandas - Data manipulation"
echo "   • numpy - Numerical operations"
echo "   • optuna - Hyperparameter optimization"
echo "   • supabase - Database connection"
echo ""
echo "📝 Next steps:"
echo ""
echo "   1. Ensure your .env file has correct credentials:"
echo "      export SUPABASE_URL='https://your-project.supabase.co'"
echo "      export SUPABASE_KEY='your-key-here'"
echo ""
echo "   2. Run the test script to validate setup:"
echo "      $PYTHON_CMD test_optimizer_setup.py"
echo ""
echo "   3. Run the optimizer:"
echo "      $PYTHON_CMD optimize_filters.py"
echo ""
echo "   4. Check the results in optimized_filters.json"
echo ""
echo "📖 For detailed usage instructions, see:"
echo "   OPTIMIZER_GUIDE.md"
echo ""
echo "=================================================="
