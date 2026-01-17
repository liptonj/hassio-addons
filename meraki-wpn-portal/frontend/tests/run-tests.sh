#!/bin/bash
# Test runner script for frontend tests

set -e

echo "=========================================="
echo "Running Frontend Test Suite"
echo "=========================================="

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

cd "$(dirname "$0")/.."

# Run unit tests
echo -e "\n${YELLOW}Running unit tests...${NC}"
if npm run test:unit; then
    echo -e "${GREEN}✓ Unit tests passed${NC}"
else
    echo -e "${RED}✗ Unit tests failed${NC}"
    exit 1
fi

# Run e2e tests
echo -e "\n${YELLOW}Running e2e tests...${NC}"
if npm run test:e2e; then
    echo -e "${GREEN}✓ E2E tests passed${NC}"
else
    echo -e "${RED}✗ E2E tests failed${NC}"
    exit 1
fi

echo -e "\n${GREEN}=========================================="
echo "All tests passed!"
echo "==========================================${NC}"
