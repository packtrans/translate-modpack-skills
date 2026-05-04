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
from pathlib import Path


def validate_snbt(content: str, filename: str = "<input>"):
    """
    Validates SNBT content for mismatched brackets and quotes.
    Returns a list of error messages.
    """
    errors = []
    # stack holds tuples: (char, line, col)
    bracket_stack = []
    in_string = None  # None, '"', or "'"
    escape_next = False
    skip_to_eol = False

    line_num = 1
    col_num = 0

    for ch in content:
        if ch == "\n":
            line_num += 1
            col_num = 0
            skip_to_eol = False
            continue
        col_num += 1

        if skip_to_eol:
            continue

        if in_string:
            if escape_next:
                escape_next = False
                continue
            if ch == "\\":
                escape_next = True
                continue
            if ch == in_string:
                in_string = None
                continue
            continue

        # Outside of string
        if ch in ('"', "'"):
            in_string = ch
            continue

        # Comments start with # and go to end of line
        if ch == "#":
            skip_to_eol = True
            continue

        if ch in "([{":
            bracket_stack.append((ch, line_num, col_num))
        elif ch in ")]}":
            if not bracket_stack:
                errors.append(
                    f"{filename}:{line_num}:{col_num}: unexpected closing '{ch}'"
                )
                continue
            top, top_line, top_col = bracket_stack.pop()
            expected = {"(": ")", "[": "]", "{": "}"}.get(top)
            if expected != ch:
                errors.append(
                    f"{filename}:{line_num}:{col_num}: mismatched bracket: "
                    f"expected '{expected}' to close '{top}' from {top_line}:{top_col}, got '{ch}'"
                )

    for ch, line, col in bracket_stack:
        errors.append(f"{filename}:{line}:{col}: unclosed bracket '{ch}'")

    if in_string:
        errors.append(f"{filename}: unclosed string starting with {in_string}")

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
