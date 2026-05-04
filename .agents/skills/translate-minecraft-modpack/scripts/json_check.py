#!/usr/bin/env python3
"""
JSON validation script.
Uses Python's built-in json module to verify JSON files.
Usage:
    python json_check.py <file.json> [file2.json ...]
    python json_check.py --recursive <directory>
"""

import argparse
import json
import sys
from pathlib import Path


def validate_json(content: str, filename: str = "<input>"):
    """
    Validates JSON content using Python's json module.
    Returns a list of error messages.
    """
    errors = []
    try:
        json.loads(content)
    except json.JSONDecodeError as exc:
        errors.append(f"{filename}:{exc.lineno}:{exc.colno}: {exc.msg}")
    return errors


def main():
    parser = argparse.ArgumentParser(
        description="Validate JSON files for syntax errors."
    )
    parser.add_argument("paths", nargs="+", help="Files or directories to check")
    parser.add_argument(
        "-r", "--recursive", action="store_true", help="Recursively scan directories"
    )
    parser.add_argument(
        "-e", "--ext", default=".json", help="File extension to look for in recursive mode (default: .json)"
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
        errs = validate_json(text, str(f))
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
