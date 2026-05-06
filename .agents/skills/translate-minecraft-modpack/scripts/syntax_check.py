#!/usr/bin/env python3
"""
Syntax checker for JSON and SNBT files.

Usage:
    python3 syntax_check.py file1.snbt file2.json ...
    python3 syntax_check.py -r directory ...

Recursively scans directories when -r is given, otherwise checks
specific files. File type is detected by extension.
"""

import argparse
import json
import sys
from enum import Enum, auto
from pathlib import Path


# ---------------------------------------------------------------------------
# JSON checker
# ---------------------------------------------------------------------------

def validate_json(content: str, filename: str = "<input>"):
    """Validates JSON content using Python's json module."""
    errors = []
    try:
        json.loads(content)
    except json.JSONDecodeError as exc:
        errors.append(f"{filename}:{exc.lineno}:{exc.colno}: {exc.msg}")
    return errors


# ---------------------------------------------------------------------------
# SNBT checker
# ---------------------------------------------------------------------------

class State(Enum):
    DEFAULT = auto()
    IN_DOUBLE_STRING = auto()
    DOUBLE_STRING_ESCAPE = auto()
    IN_SINGLE_STRING = auto()
    SINGLE_STRING_ESCAPE = auto()
    COMMENT = auto()
    AFTER_STRING = auto()


def validate_snbt(content: str, filename: str = "<input>"):
    """
    Validates SNBT content for mismatched brackets and quotes.
    Returns a list of error messages.
    """
    errors = []
    # stack holds tuples: (char, line, col)
    bracket_stack = []

    state = State.DEFAULT
    last_string_close = (-1, -1)  # (line, col) of the quote that closed the string
    after_string_whitespace = False

    line_num = 1
    col_num = 0

    for ch in content:
        if ch == "\n":
            line_num += 1
            col_num = 0
        else:
            col_num += 1

        # COMMENT state
        if state is State.COMMENT:
            if ch == "\n":
                state = State.DEFAULT
            continue

        # AFTER_STRING state: validate what follows a closed string
        if state is State.AFTER_STRING:
            if ch in " \t\r\n":
                after_string_whitespace = True
                continue
            if ch in ",:;{}[]()#":
                state = State.DEFAULT
                after_string_whitespace = False
                if ch == "#":
                    state = State.COMMENT
                    continue
                # Fall through to DEFAULT handling for structural chars
            elif ch in "'\"":
                # Another string immediately after – could be valid in lists/arrays,
                # so treat it leniently and let DEFAULT handle the quote.
                state = State.DEFAULT
                after_string_whitespace = False
                # Fall through to DEFAULT handling
            else:
                if not after_string_whitespace:
                    # The string was immediately followed by a bare word with
                    # no whitespace – the closing quote was probably unescaped.
                    sl, sc = last_string_close
                    errors.append(
                        f"{filename}:{line_num}:{col_num}: unexpected character '{ch}' "
                        f"after string (closed at {sl}:{sc})"
                    )
                state = State.DEFAULT
                after_string_whitespace = False
                # Fall through to DEFAULT handling for the current char

        if state is State.DEFAULT:
            if ch in "([{":
                bracket_stack.append((ch, line_num, col_num))
            elif ch in ")]}":
                if not bracket_stack:
                    errors.append(
                        f"{filename}:{line_num}:{col_num}: unexpected closing '{ch}'"
                    )
                else:
                    top, top_line, top_col = bracket_stack.pop()
                    expected = {"(": ")", "[": "]", "{": "}"}.get(top)
                    if expected != ch:
                        errors.append(
                            f"{filename}:{line_num}:{col_num}: mismatched bracket: "
                            f"expected '{expected}' to close '{top}' from {top_line}:{top_col}, got '{ch}'"
                        )
            elif ch == '"':
                state = State.IN_DOUBLE_STRING
            elif ch == "'":
                state = State.IN_SINGLE_STRING
            elif ch == "#":
                state = State.COMMENT
            continue

        if state is State.IN_DOUBLE_STRING:
            if ch == "\\":
                state = State.DOUBLE_STRING_ESCAPE
            elif ch == '"':
                state = State.AFTER_STRING
                after_string_whitespace = False
                last_string_close = (line_num, col_num)
            elif ch == "\n":
                errors.append(
                    f"{filename}:{line_num}:{col_num}: newline in double-quoted string"
                )
                state = State.DEFAULT
            continue

        if state is State.DOUBLE_STRING_ESCAPE:
            state = State.IN_DOUBLE_STRING
            continue

        if state is State.IN_SINGLE_STRING:
            if ch == "\\":
                state = State.SINGLE_STRING_ESCAPE
            elif ch == "'":
                state = State.AFTER_STRING
                after_string_whitespace = False
                last_string_close = (line_num, col_num)
            elif ch == "\n":
                errors.append(
                    f"{filename}:{line_num}:{col_num}: newline in single-quoted string"
                )
                state = State.DEFAULT
            continue

        if state is State.SINGLE_STRING_ESCAPE:
            state = State.IN_SINGLE_STRING
            continue

    # End-of-file checks
    if state in (State.IN_DOUBLE_STRING, State.DOUBLE_STRING_ESCAPE):
        errors.append(f"{filename}: unclosed double-quoted string")
    elif state in (State.IN_SINGLE_STRING, State.SINGLE_STRING_ESCAPE):
        errors.append(f"{filename}: unclosed single-quoted string")

    for ch, line, col in bracket_stack:
        errors.append(f"{filename}:{line}:{col}: unclosed bracket '{ch}'")

    return errors


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

CHECKERS = {
    ".json": validate_json,
    ".snbt": validate_snbt,
}


def check_file(filepath: Path) -> list[str]:
    """Check a single file, dispatching to the right checker by extension."""
    ext = filepath.suffix.lower()
    checker = CHECKERS.get(ext)
    if checker is None:
        return [f"{filepath}: unsupported file type '{ext}'"]
    try:
        content = filepath.read_text(encoding="utf-8")
    except OSError as e:
        return [f"{filepath}: {e}"]
    return checker(content, str(filepath))


def collect_files(paths: list[Path], recursive: bool) -> list[Path]:
    """Expand paths into a list of files, optionally recursing into dirs."""
    supported_exts = set(CHECKERS.keys())
    files: list[Path] = []
    for p in paths:
        if p.is_file():
            if p.suffix.lower() in supported_exts:
                files.append(p)
            else:
                print(
                    f"Warning: unsupported file type '{p.suffix}' for {p}",
                    file=sys.stderr,
                )
        elif p.is_dir():
            if recursive:
                for ext in supported_exts:
                    files.extend(p.rglob(f"*{ext}"))
            else:
                print(
                    f"Warning: {p} is a directory; use -r to recurse",
                    file=sys.stderr,
                )
        else:
            print(f"Error: {p} not found", file=sys.stderr)
            sys.exit(1)
    return sorted(set(files))


def main() -> None:
    parser = argparse.ArgumentParser(description="Check syntax of JSON and SNBT files")
    parser.add_argument("paths", nargs="+", help="Files or directories to check")
    parser.add_argument(
        "-r", "--recursive", action="store_true", help="Recursively scan directories"
    )
    args = parser.parse_args()

    files = collect_files([Path(p) for p in args.paths], args.recursive)
    if not files:
        print("No files to check.", file=sys.stderr)
        sys.exit(0)

    total_errors = 0
    for f in files:
        errors = check_file(f)
        for e in errors:
            print(e)
            total_errors += 1

    if total_errors:
        print(f"\n{total_errors} error(s) found.", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"OK: {len(files)} file(s) passed syntax check.")
        sys.exit(0)


if __name__ == "__main__":
    main()
