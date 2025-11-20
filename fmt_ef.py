#!/usr/bin/env python3
r"""Format errorformat JSONL output for testing.

Usage:
    # Show compact summary
    errorformat -w=jsonl PATTERNS < input.txt | python3 fmt_ef.py

    # Show matched lines with visible delimiters
    errorformat -w=jsonl PATTERNS < input.txt | python3 fmt_ef.py --lines

Examples:
    cat output.txt | errorformat -w=jsonl '%E%f:%l: %m' '%+C  %.%#' '%G%.%#' \\
        | python3 fmt_ef.py

    echo 'file.py:10: error' | errorformat -w=jsonl '%f:%l: %m' \\
        | python3 fmt_ef.py --lines

Output format:
    f='filename' l=line c=col v=valid #=nlines

With --lines:
    Shows matched lines with visible \n delimiters
"""
import json
import sys

show_lines = "--lines" in sys.argv

# ruff: noqa: T201


for line in sys.stdin:
    if not line.strip():
        continue
    d = json.loads(line)
    f = d.get("filename", "")
    lnum = d.get("lnum", 0)
    col = d.get("col", 0)
    valid = d.get("valid", False)
    typ = d.get("type", "")
    typ_char = chr(typ) if typ else ""
    text = d.get("text", "")
    lines = d.get("lines", [])
    nlines = len(lines)
    print(
        f"f={f!r} l={lnum!r} c={col!r} t={typ_char!r} v={valid!r} #={nlines!r}"
    )
    if show_lines and lines:
        for i, matched_line in enumerate(lines):
            print(f"  [{i}]: {matched_line!r}")
