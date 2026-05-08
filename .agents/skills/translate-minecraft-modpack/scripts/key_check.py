#!/usr/bin/env python3
"""
Key diff tool for JSON and SNBT files.
Compares keys between a source file and a target file (or directories).

Usage:
    python3 key_check.py <source> <target>
    python3 key_check.py -r <source_dir> <target_dir>

Reports keys present in source but missing from target, and vice versa.
"""

import argparse
import json
import sys
from pathlib import Path

from snbt_parser import AstNode, CompoundNode, ListNode, parse_snbt

# ---------------------------------------------------------------------------
# JSON key extraction
# ---------------------------------------------------------------------------


def extract_json_keys(data, prefix: str = "") -> set[str]:
    """Recursively extract dotted keys from a parsed JSON object."""
    keys: set[str] = set()
    if isinstance(data, dict):
        for k, v in data.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            keys.add(key)
            keys.update(extract_json_keys(v, key))
    elif isinstance(data, list):
        for i, v in enumerate(data):
            key = f"{prefix}[{i}]" if prefix else f"[{i}]"
            keys.update(extract_json_keys(v, key))
    return keys


# ---------------------------------------------------------------------------
# SNBT key extraction (via snbt_parser AST)
# ---------------------------------------------------------------------------


def _walk_ast_keys(node: AstNode, prefix: str = "") -> set[str]:
    keys: set[str] = set()
    if isinstance(node, CompoundNode):
        for entry in node.entries:
            key = f"{prefix}.{entry.key}" if prefix else entry.key
            keys.add(key)
            keys.update(_walk_ast_keys(entry.value, key))
    elif isinstance(node, ListNode):
        for i, element in enumerate(node.elements):
            key = f"{prefix}[{i}]" if prefix else f"[{i}]"
            keys.update(_walk_ast_keys(element, key))
    return keys


def extract_snbt_keys(content: str) -> set[str]:
    ast = parse_snbt(content)
    return _walk_ast_keys(ast)


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

SUPPORTED_EXTS = {".json", ".snbt"}


def get_keys(filepath: Path) -> set[str]:
    ext = filepath.suffix.lower()
    if ext not in SUPPORTED_EXTS:
        raise ValueError(f"Unsupported file type: {ext}")
    content = filepath.read_text(encoding="utf-8")
    if ext == ".json":
        data = json.loads(content)
        return extract_json_keys(data)
    else:
        return extract_snbt_keys(content)


# ---------------------------------------------------------------------------
# Diff logic
# ---------------------------------------------------------------------------


def diff_files(source: Path, target: Path) -> int:
    try:
        source_keys = get_keys(source)
        target_keys = get_keys(target)
    except Exception as exc:
        print(f"Error reading {source} or {target}: {exc}", file=sys.stderr)
        return 1

    only_in_source = sorted(source_keys - target_keys)
    only_in_target = sorted(target_keys - source_keys)

    if not only_in_source and not only_in_target:
        print(f"OK: {source} and {target} keys match.")
        return 0

    print(f"--- {source}")
    print(f"+++ {target}")
    if only_in_source:
        print("Only in source:")
        for k in only_in_source:
            print(f"  - {k}")
    if only_in_target:
        print("Only in target:")
        for k in only_in_target:
            print(f"  + {k}")
    return 1


def diff_dirs(source_dir: Path, target_dir: Path) -> int:
    source_files = sorted(
        p
        for p in source_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS
    )
    total_diffs = 0
    checked = 0

    for src_file in source_files:
        rel = src_file.relative_to(source_dir)
        tgt_file = target_dir / rel
        if not tgt_file.exists():
            print(f"Only in source: {rel}")
            total_diffs += 1
            continue
        if tgt_file.suffix.lower() != src_file.suffix.lower():
            print(f"Type mismatch: {rel} ({src_file.suffix} vs {tgt_file.suffix})")
            total_diffs += 1
            continue
        if diff_files(src_file, tgt_file) != 0:
            total_diffs += 1
        checked += 1

    target_files = sorted(
        p
        for p in target_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS
    )
    for tgt_file in target_files:
        rel = tgt_file.relative_to(target_dir)
        src_file = source_dir / rel
        if not src_file.exists():
            print(f"Only in target: {rel}")
            total_diffs += 1

    if total_diffs == 0:
        print(f"OK: all {checked} file(s) have matching keys.")
    else:
        print(f"\n{total_diffs} difference(s) found.")
    return total_diffs


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Diff keys between source and target JSON/SNBT files or directories."
    )
    parser.add_argument("source", help="Source file or directory")
    parser.add_argument("target", help="Target file or directory")
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Treat inputs as directories and compare recursively",
    )
    args = parser.parse_args()

    source = Path(args.source)
    target = Path(args.target)

    if args.recursive:
        if not source.is_dir() or not target.is_dir():
            parser.error("With -r, both source and target must be directories")
        ret = diff_dirs(source, target)
        sys.exit(1 if ret else 0)

    if source.is_dir() and target.is_dir():
        ret = diff_dirs(source, target)
        sys.exit(1 if ret else 0)
    elif source.is_file() and target.is_file():
        ret = diff_files(source, target)
        sys.exit(ret)
    else:
        parser.error("Source and target must both be files or both be directories")


if __name__ == "__main__":
    main()
