# Tuicker project commands

export FORCE_COLOR := '1'

# Display available recipes
[group('user')]
help:
    @just --list --unsorted

# Install tuick using uv tool
[group('user')]
install:
    uv tool install --force --no-cache file://.

# Development workflow: check, test
[group('dev')]
dev: compile check test

# Agent workflow: check, test with minimal output
[group('agent')]
agent: agent-compile agent-check agent-test
    @echo OK

# Clean generated files
[group('dev')]
clean:
    rm -rf .dmypy.json .mypy_cache .pytest_cache .ruff_cache .venv \
    .vscode */__pycache__ dist
    # hatch-mypyc, which gets invoked by "uv sync" leaves .so files in src
    rm -rf src/*.so

python_dirs := "src tests"

# Compile python files, quick test for valid syntax
[private]
[group('dev')]
compile:
    uv run -m compileall -q {{ python_dirs }}

# Compile python files, with less output
[private]
[group('agent')]
[no-exit-message]
agent-compile:
    @uv run -m compileall -q {{ python_dirs }}

run-dev := "uv run --dev"

# Run test suite
[group('dev')]
test *ARGS:
    uv run --dev pytest --no-header {{ ARGS }}

# Run test suite in agent mode (less output)
[group('agent')]
[no-exit-message]
agent-test *ARGS:
    #!/usr/bin/env bash -euo pipefail
    fail_with () { local s=$?; "$@"; return $s; }
    quietly () { output=$("$@" >&1) || fail_with echo "$output"; }
    quietly uv run --dev pytest --no-header --quiet --tb=short -p no:icdiff {{ ARGS }}
    if ! {{ is_dependency() }}; then echo OK; fi


# Static code analysis and style checks
[group('dev')]
check: compile
    uv run --dev ruff format --check {{ python_dirs }}
    uv run --dev docformatter --check {{ python_dirs }}
    uv run --dev ruff check --quiet {{ python_dirs }}
    uv run --dev mypy {{ python_dirs }}

[group('dev')]
tuick: compile
    uv run --dev ruff format --check {{ python_dirs }} \
    || read -p "Auto-format? (enter or ctrl-C) " \
    && uv run --dev ruff format {{ python_dirs }}
    uv run --dev docformatter --check {{ python_dirs }} \
    || read -p "Auto-format? (enter or ctrl-C) " \
    && uv run --dev docformatter --in-place {{ python_dirs }}
    uv run --dev tuick -- ruff check --quiet {{ python_dirs }}
    uv run --dev tuick -- mypy {{ python_dirs }}
    uv run --dev tuick -- pytest --no-header


# Report FIXME, TODO, XXX, HACK comments
[group('dev')]
fixme:
    uv run --dev ruff check --quiet \
    --ignore ALL --select FIX {{ python_dirs }}

concise := "--output-format concise"

[private]
[group('agent')]
[no-exit-message]
agent-check: agent-compile
    @uv run --dev ruff format --check --quiet {{ python_dirs }} \
    || { echo 'Try "just format"' >&2 ; false; }
    @uv run --dev docformatter --check {{ python_dirs }}
    @uv run --dev ruff check --quiet {{ concise }} {{ python_dirs }}
    @uv run --dev mypy {{ python_dirs }}
    @if ! {{ is_dependency() }}; then echo OK; fi


# Ruff auto-fix
[group('dev')]
ruff-fix *ARGS:
    uv run --dev ruff check --fix {{ ARGS }} {{ python_dirs }}

# Reformat code, fail if formatting errors remain
[group('dev')]
format:
    uv run --dev ruff format {{ python_dirs }}
    uv run --dev docformatter --in-place {{ python_dirs }}
