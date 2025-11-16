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

# Common variables

[private]
_run-dev := 'uv run --dev'
[private]
_python-dirs := "src tests"
[private]
_pytest-opts := "--no-header --tb=short"

# Bash definitions

[private]
_bash-defs := '''
run_dev="''' + _run-dev + '''"
python_dirs="''' + _python-dirs + '''"
full_diff=''' + full-diff + ''';
COMMAND="''' + style('command') + '''"
NORMAL="''' + NORMAL + '''"
safe () { "$@" || status=false; }
end-safe () { ${status:-true}; }
show () { echo "$COMMAND$*$NORMAL"; }
visible () { show "$@"; "$@"; }
report () { local s=$?; show "$@"; echo "$out"; return $s; }
quiet () { out=$("$@" >&1) || report "$@"; }
pytest-agent-filter () {
    $full_diff && while read -r line
    do [[ $line =~ ^===+\ FAILURES\ ===+$ ]] && break; done
    cat
}
'''
# Pytest options.
# Run with full-diff=true for full diffs.

full-diff := 'false'
[private]
_diff-limit-opt := ' -o truncation_limit_lines=7'
[private]
_pytest-diff-opt := if full-diff == 'true' { ' --verbose' } else { ' --quiet' + _diff-limit-opt }
[private]
_pytest-agent-opts := _pytest-opts + " -p no:icdiff" + _pytest-diff-opt

# Development workflow: check, test
[group('dev')]
dev: _fail_if_claudecode compile
    #!/usr/bin/env bash -euo pipefail
    {{ _bash-defs }} {{ _check-body }}
    safe visible {{ _run-dev }} tuick --format -- pytest {{ _pytest-opts }}
    end-safe

# Agent workflow: check, test with minimal output
[group('agent')]
agent *ARGS: agent-compile
    #!/usr/bin/env bash -euo pipefail
    {{ _bash-defs }} {{ _agent-check-body }}
    safe quiet {{ _run-dev }} pytest {{ _pytest-agent-opts }} {{ ARGS }} \
    | pytest-agent-filter \
    || $full_diff || echo 'For full diff: just full-diff=true agent"'
    end-safe && echo OK

# Clean build files
[group('dev')]
clean:
    rm -rf .venv */__pycache__ */*/__pycache__ build dist */*.so */*/*.so

# Clean non-build caches and run files
[group('dev')]
clean-cache:
    rm -rf .dmypy.json .mypy_cache .pytest_cache .ruff_cache

# Fail if CLAUDECODE is set
[no-exit-message]
[private]
_fail_if_claudecode:
    #!/usr/bin/env bash -euo pipefail
    if [ "${CLAUDECODE:-}" != "" ]; then
        echo -e '{{ style("error") }}⛔️ Denied: use agent recipes{{ NORMAL }}'
        exit 1
    fi

# Compile python files, quick test for valid syntax
[group('dev')]
[private]
compile:
    {{ _run-dev }} tuick --format \
    -p '%E*** Error ' -p '%C  File "%f", line %l' -p '%C%m' -p '%Z' \
    -- python3 -m compileall -q {{ _python-dirs }}

# Compile python files, with less output
[group('agent')]
[no-exit-message]
[private]
agent-compile:
    #!/usr/bin/env bash -euo pipefail
    {{ _bash-defs }}
    quiet {{ _run-dev }} -m compileall -q {{ _python-dirs }}

# Run test suite
[group('dev')]
test *ARGS: _fail_if_claudecode
    {{ _run-dev }} tuick --format -- pytest {{ _pytest-opts }} {{ ARGS }}

# Run test suite, with less output
[group('agent')]
[no-exit-message]
agent-test *ARGS:
    #!/usr/bin/env bash -euo pipefail
    {{ _bash-defs }}
    quiet {{ _run-dev }} pytest {{ _pytest-agent-opts }} {{ ARGS }} \
    | pytest-agent-filter \
    && { {{ is_dependency() }} || echo OK; } \
    || { $full_diff || echo 'For full diff: just full-diff=true agent-test';
         false; }

# Static code analysis and style checks
[group('dev')]
check: _fail_if_claudecode compile
    #!/usr/bin/env bash -euo pipefail
    {{ _bash-defs }} {{ _check-body }}
    end-safe

[private]
_check-body := '''
    tuickf="tuick --format"
    safe visible $run_dev $tuickf -- ruff format --check $python_dirs
    safe visible $run_dev $tuickf -p "%E%f" -- docformatter --check $python_dirs
    safe visible $run_dev $tuickf -- ruff check --quiet $python_dirs
    safe visible $run_dev $tuickf -f mypy -- dmypy check $python_dirs
'''

# Auto format and interactive code analysis and style checks
[group('dev')]
tuick: _fail_if_claudecode compile
    {{ _run-dev }} tuick -- just _tuick

[group('dev')]
_tuick:
    #!/usr/bin/env bash -euo pipefail
    {{ _bash-defs }} {{ _format-body }} {{ _check-body }}
    safe visible {{ _run-dev }} pytest {{ _pytest-opts }}
    end-safe

# Report TODO, FIXME, XXX, HACK comments
[group('dev')]
todo:
    {{ _run-dev }} ruff check --quiet --ignore ALL --select FIX \
        {{ _python-dirs }}

# Static code analysis and style checks, with less output
[group('agent')]
[no-exit-message]
agent-check: agent-compile
    #!/usr/bin/env bash -euo pipefail
    {{ _bash-defs }} {{ _agent-check-body }}
    end-safe && { {{ is_dependency() }} ||  echo OK; }

[private]
_agent-check-body := '''
    safe quiet $run_dev ruff format --check --quiet $python_dirs \
    || { echo 'Try "just format"'; status=false; }
    safe quiet $run_dev docformatter --check $python_dirs
    safe quiet $run_dev ruff check --quiet --output-format=concise $python_dirs
    safe quiet $run_dev dmypy check $python_dirs
'''

# Ruff auto-fix
[group('dev')]
ruff-fix *ARGS:
    {{ _run-dev }} ruff check --quiet --output-format=concise --fix \
    {{ ARGS }} {{ _python-dirs }}

# Reformat code, fail if formatting errors remain
[group('dev')]
format:
    #!/usr/bin/env bash -euo pipefail
    {{ _bash-defs }} {{ _format-body }}
    end-safe

[private]
_format-body := '''
    safe visible $run_dev ruff format $python_dirs
    safe visible $run_dev docformatter --in-place $python_dirs
'''
