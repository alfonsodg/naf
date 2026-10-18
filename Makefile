.PHONY: dev test lint typecheck fmt migrations dev-up dev-down

# Run API in development
dev:
	uv run uvicorn app.main:app --reload --port 8000

# Run all tests
test:
	uv run pytest tests/ -v

# Lint
lint:
	uv run ruff check app tests

# Type check
typecheck:
	uv run mypy app

# Format
fmt:
	uv run ruff format app tests
	uv run ruff check --fix app tests

# Generate migration
migration:
	uv run alembic revision --autogenerate -m "$(m)"

# Apply migrations
migrate:
	uv run alembic upgrade head
