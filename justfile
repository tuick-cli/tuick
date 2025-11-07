# Tuicker project commands

export FORCE_COLOR := '1'

# Display available recipes
[group('user')]
help:
    @just --list --unsorted

# Install tuick using uv tool
[group('user')]
install:
    uv tool install --refresh-package tuick file://.

# Development workflow: check, test
[group('dev')]
dev: fail_if_claudecode compile
    #!/usr/bin/env bash -euo pipefail
    show () { echo -e "{{ style('command') }}$*{{ NORMAL }}" >&2; }
    safe () { show "$@"; "$@" || status=false; }
    safe uv run --dev ruff format --check {{ python_dirs }}
    safe uv run --dev ruff format --check {{ python_dirs }}
    safe uv run --dev docformatter --check {{ python_dirs }}
    safe uv run --dev ruff check --quiet {{ python_dirs }}
    safe uv run --dev dmypy check {{ python_dirs }}
    safe uv run --dev pytest --no-header --tb=short
    ${status:-true}

# Agent workflow: check, test with minimal output
[group('agent')]
agent: agent-compile agent-check agent-test
    @echo OK

# Clean build files
[group('dev')]
clean:
    rm -rf .venv */__pycache__ */*/__pycache__ build dist */*.so */*/*.so

# Clean non-build caches and run files
[group('dev')]
clean-cache:
    rm -rf .dmypy.json .mypy_cache .pytest_cache .ruff_cache

python_dirs := "src tests"

# Fail if CLAUDECODE is set
[private]
[no-exit-message]
fail_if_claudecode:
    @{{ if env('CLAUDECODE', '') != '' { '! echo "' + style("error") + '⛔️ Denied: use agent recipes' + NORMAL + '" >&2' } else { '' } }}

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
test *ARGS: fail_if_claudecode
    uv run --dev pytest --no-header --tb=short {{ ARGS }}

# Run test suite, with less output
[group('agent')]
[no-exit-message]
agent-test *ARGS:
    #!/usr/bin/env bash -euo pipefail
    quietly () { out=$("$@" >&1) || { local s=$?; echo "$out"; return $s; }; }
    quietly uv run --dev pytest --no-header --quiet --tb=short -p no:icdiff -o truncation_limit_lines=7{{ ARGS }}
    if ! {{ is_dependency() }}; then echo OK; fi

# Static code analysis and style checks
[group('dev')]
check: fail_if_claudecode compile
    #!/usr/bin/env bash -euo pipefail
    show () { echo -e "{{ style('command') }}$*{{ NORMAL }}" >&2; }
    safe () { show "$@"; "$@" || status=false; }
    safe uv run --dev ruff format --check {{ python_dirs }}
    safe uv run --dev docformatter --check {{ python_dirs }}
    safe uv run --dev ruff check --quiet {{ python_dirs }}
    safe uv run --dev dmypy check {{ python_dirs }}
    ${status:-true}

# Interactive code analysis and style checks
[group('dev')]
tuick: fail_if_claudecode compile
    uv run --dev ruff format --check {{ python_dirs }} \
    || read -p "Auto-format? (enter or ctrl-C) " \
    && uv run --dev ruff format {{ python_dirs }}
    uv run --dev docformatter --check {{ python_dirs }} \
    || read -p "Auto-format? (enter or ctrl-C) " \
    && uv run --dev docformatter --in-place {{ python_dirs }}
    uv run --dev tuick -v -- ruff check --quiet {{ python_dirs }}
    uv run --dev tuick -v -- dmypy check {{ python_dirs }}
    uv run --dev tuick -v -- pytest --tb=short --no-header

# Report FIXME, TODO, XXX, HACK comments
[group('dev')]
fixme:
    uv run --dev ruff check --quiet \
    --ignore ALL --select FIX {{ python_dirs }}

concise := "--output-format concise"

# Static code analysis and style checks, with less output
[group('agent')]
[no-exit-message]
agent-check: agent-compile
    @uv run --dev ruff format --check --quiet {{ python_dirs }} \
    || { echo 'Try "just format"' >&2 ; false; }
    @uv run --dev docformatter --check {{ python_dirs }}
    @uv run --dev ruff check --quiet {{ concise }} {{ python_dirs }}
    @uv run --dev dmypy check {{ python_dirs }}
    @{{ is_dependency() }} || echo OK

# Ruff auto-fix
[group('dev')]
ruff-fix *ARGS:
    uv run --dev ruff check --quiet {{ concise }} --fix {{ ARGS }} {{ python_dirs }}

# Reformat code, fail if formatting errors remain
[group('dev')]
format:
    uv run --dev ruff format {{ python_dirs }}
    uv run --dev docformatter --in-place {{ python_dirs }}
