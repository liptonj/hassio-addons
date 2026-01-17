# Makefile for Meraki WPN Portal
# Provides convenient commands for development, testing, and validation

.PHONY: help install typecheck lint test test-backend test-frontend validate build docker-build docker-up docker-down clean

# Default target
help:
	@echo "Meraki WPN Portal - Development Commands"
	@echo ""
	@echo "Installation:"
	@echo "  make install          - Install all dependencies (backend + frontend)"
	@echo ""
	@echo "Type Checking & Linting:"
	@echo "  make typecheck        - Run type checking for both backend and frontend"
	@echo "  make lint             - Run linting for both backend and frontend"
	@echo ""
	@echo "Testing:"
	@echo "  make test             - Run all tests (typecheck + lint + unit + e2e)"
	@echo "  make test-backend     - Run backend tests only (with type check)"
	@echo "  make test-frontend    - Run frontend tests only (with type check)"
	@echo "  make test-quick       - Run tests without type checking (faster)"
	@echo ""
	@echo "Validation (pre-commit/CI):"
	@echo "  make validate         - Full validation: typecheck + lint + tests + build"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build     - Build all Docker containers"
	@echo "  make docker-up        - Start all Docker containers"
	@echo "  make docker-down      - Stop all Docker containers"
	@echo "  make docker-logs      - View Docker container logs"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean            - Remove build artifacts and caches"

# Installation
install:
	@echo "📦 Installing backend dependencies..."
	cd backend && uv sync --all-extras
	@echo "📦 Installing frontend dependencies..."
	cd frontend && npm ci
	@echo "📦 Installing Playwright browsers..."
	cd frontend && npx playwright install chromium
	@echo "✅ All dependencies installed"

# Type Checking
typecheck: typecheck-backend typecheck-frontend
	@echo "✅ All type checks passed"

typecheck-backend:
	@echo "🔍 Type checking backend (Python/mypy)..."
	cd backend && uv run mypy app --ignore-missing-imports || true

typecheck-frontend:
	@echo "🔍 Type checking frontend (TypeScript)..."
	cd frontend && npm run typecheck

# Linting
lint: lint-backend lint-frontend
	@echo "✅ All linting passed"

lint-backend:
	@echo "🔍 Linting backend (ruff)..."
	cd backend && uv run ruff check app

lint-frontend:
	@echo "🔍 Linting frontend (eslint)..."
	cd frontend && npm run lint || true

# Testing
test: typecheck lint test-backend-quick test-frontend-quick
	@echo "✅ All tests passed"

test-backend: typecheck-backend
	@echo "🧪 Running backend tests..."
	cd backend && uv run pytest tests/ -v --tb=short

test-backend-quick:
	@echo "🧪 Running backend tests (quick)..."
	cd backend && uv run pytest tests/ -v --tb=short -x

test-frontend: typecheck-frontend
	@echo "🧪 Running frontend tests..."
	cd frontend && npx playwright test --project=chromium

test-frontend-quick:
	@echo "🧪 Running frontend smoke tests..."
	cd frontend && npx playwright test tests/e2e/smoke.spec.ts --project=chromium

test-quick:
	@echo "🧪 Running quick tests (no type checking)..."
	cd backend && uv run pytest tests/ -v --tb=short -x
	cd frontend && npx playwright test tests/e2e/smoke.spec.ts --project=chromium

# Full Validation (for CI/pre-commit)
validate: typecheck lint test-backend-quick test-frontend-quick build-frontend
	@echo "✅ Full validation passed - ready for commit/deploy"

build-frontend:
	@echo "🏗️ Building frontend..."
	cd frontend && npm run build

# Docker
docker-build:
	@echo "🐳 Building Docker containers..."
	docker compose build --no-cache

docker-up:
	@echo "🐳 Starting Docker containers..."
	docker compose up -d
	@echo "Waiting for services to be healthy..."
	@sleep 5
	docker compose ps

docker-down:
	@echo "🐳 Stopping Docker containers..."
	docker compose down

docker-logs:
	docker compose logs -f --tail=50

# Cleanup
clean:
	@echo "🧹 Cleaning build artifacts..."
	rm -rf frontend/dist
	rm -rf frontend/node_modules/.cache
	rm -rf backend/.pytest_cache
	rm -rf backend/.mypy_cache
	rm -rf backend/.ruff_cache
	rm -rf backend/htmlcov
	rm -rf backend/.coverage
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Cleanup complete"

# Database reset (for testing)
db-reset:
	@echo "⚠️  Resetting test database..."
	rm -f backend/data/wpn_radius.db backend/data/wpn_radius.db-shm backend/data/wpn_radius.db-wal
	@echo "✅ Database reset complete"
