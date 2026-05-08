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
from pathlib import Path

from snbt_parser import SnbtError, parse


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
# SNBT checker (via snbt_parser)
# ---------------------------------------------------------------------------


def validate_snbt(content: str, filename: str = "<input>"):
    try:
        parse(content)
        return []
    except SnbtError as exc:
        return [f"{filename}:{exc}"]


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
