.PHONY: all formatcheck check mypy pytest
all: formatcheck check mypy pytest
formatcheck:
	uv run tuick --format -- ruff format --check
check:
	uv run tuick --format -- ruff check --quiet # --output-format=concise
mypy:
	uv run tuick --format -- mypy
pytest:
	uv run tuick --format -- pytest --tb=short # --no-header --no-summary --exitfirst --failed-first
