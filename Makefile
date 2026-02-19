.PHONY: install dev test lint format check build run clean

# Install production dependencies
install:
	poetry install --no-dev

# Install all dependencies including dev
dev:
	poetry install --with dev

# Run tests
test:
	poetry run pytest tests/ -v --cov=src --cov-report=term-missing

# Run unit tests only
test-unit:
	poetry run pytest tests/unit/ -v

# Run integration tests only
test-integration:
	poetry run pytest tests/integration/ -v

# Run linter
lint:
	poetry run ruff check src/ tests/
	poetry run mypy src/

# Format code
format:
	poetry run ruff format src/ tests/
	poetry run ruff check --fix src/ tests/

# Run all checks
check: lint test

# Build Docker image
build:
	docker build -t ai-release-guardian .

# Run the application locally
run:
	poetry run uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000

# Start all services with Docker Compose
up:
	docker-compose up -d

# Stop all services
down:
	docker-compose down

# View logs
logs:
	docker-compose logs -f

# Clean up
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Seed baselines
seed:
	poetry run python scripts/seed_baselines.py

# Train risk weights
train:
	poetry run python scripts/train_risk_weights.py

# Simulate a release
simulate:
	poetry run python scripts/simulate_release.py

# Export audit log
export-audit:
	poetry run python scripts/export_audit_log.py
