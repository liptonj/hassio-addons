#!/bin/bash
# Test runner script for FreeRADIUS tests

set -e

echo "=========================================="
echo "Running FreeRADIUS Test Suite"
echo "=========================================="

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Run unit tests
echo -e "\n${YELLOW}Running unit tests...${NC}"
if pytest tests/unit -v --cov=radius_app --cov-report=term-missing --cov-report=html -m unit; then
    echo -e "${GREEN}✓ Unit tests passed${NC}"
else
    echo -e "${RED}✗ Unit tests failed${NC}"
    exit 1
fi

# Run integration tests
echo -e "\n${YELLOW}Running integration tests...${NC}"
if pytest tests/integration -v -m integration; then
    echo -e "${GREEN}✓ Integration tests passed${NC}"
else
    echo -e "${RED}✗ Integration tests failed${NC}"
    exit 1
fi

# Run e2e tests (if DATABASE_URL is set)
if [ -n "$DATABASE_URL" ]; then
    echo -e "\n${YELLOW}Running e2e tests...${NC}"
    if pytest tests/e2e -v -m e2e; then
        echo -e "${GREEN}✓ E2E tests passed${NC}"
    else
        echo -e "${RED}✗ E2E tests failed${NC}"
        exit 1
    fi
else
    echo -e "\n${YELLOW}Skipping e2e tests (DATABASE_URL not set)${NC}"
fi

echo -e "\n${GREEN}=========================================="
echo "All tests passed!"
echo "==========================================${NC}"
