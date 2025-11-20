.PHONY: check ruff mypy pytest
check: ruff mypy pytest
ruff:
	tuick --format -f ruff -- uv run ruff check --quiet --output-format=concise
mypy:
	tuick --format -f mypy -- uv run mypy
pytest:
	tuick --format -f pytest -- uv run pytest --tb=short --no-header \
	--exitfirst --failed-first
