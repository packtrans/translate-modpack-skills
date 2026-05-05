#!/usr/bin/env python3
"""
SNBT validation script.
Checks for mismatched brackets and quotes in SNBT files.
Usage:
    python snbt_check.py <file.snbt> [file2.snbt ...]
    python snbt_check.py --recursive <directory>
"""

import argparse
import sys
from enum import Enum, auto
from pathlib import Path


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


def main():
    parser = argparse.ArgumentParser(
        description="Validate SNBT files for matching quotes and brackets."
    )
    parser.add_argument("paths", nargs="+", help="Files or directories to check")
    parser.add_argument(
        "-r", "--recursive", action="store_true", help="Recursively scan directories"
    )
    parser.add_argument(
        "-e",
        "--ext",
        default=".snbt",
        help="File extension to look for in recursive mode (default: .snbt)",
    )
    args = parser.parse_args()

    files = []
    for p in args.paths:
        path = Path(p)
        if path.is_dir():
            if args.recursive:
                files.extend(path.rglob(f"*{args.ext}"))
            else:
                sys.stderr.write(f"Error: {p} is a directory; use --recursive\n")
                sys.exit(1)
        elif path.is_file():
            files.append(path)
        else:
            sys.stderr.write(f"Error: {p} not found\n")
            sys.exit(1)

    if not files:
        sys.stderr.write("No files to check.\n")
        sys.exit(0)

    all_errors = []
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except Exception as exc:
            sys.stderr.write(f"Error reading {f}: {exc}\n")
            continue
        errs = validate_snbt(text, str(f))
        all_errors.extend(errs)

    if all_errors:
        for e in all_errors:
            print(e)
        sys.exit(1)
    else:
        print(f"All {len(files)} file(s) passed validation.")
        sys.exit(0)


if __name__ == "__main__":
    main()
