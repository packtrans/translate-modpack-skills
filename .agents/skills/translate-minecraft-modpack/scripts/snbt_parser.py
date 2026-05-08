#!/usr/bin/env python3
"""Parser and formatter for Minecraft SNBT files.

The parser accepts vanilla SNBT plus the common config-file conveniences used by
FTB-style SNBT: `#` comments and newline-delimited compound/list entries.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Sequence, cast


BARE_WORD_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.+∞")
BARE_WORD_RE = re.compile(r"^[A-Za-z0-9_.+\-]+$")
NUMBER_RE = re.compile(
    r"""
    ^
    (?P<body>[+-]?(?:
        (?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?
    ))
    (?P<suffix>[bBsSlLfFdD]?)$
    """,
    re.VERBOSE,
)


class SnbtError(Exception):
    """Base exception for SNBT errors."""


class SnbtSyntaxError(SnbtError):
    """Syntax error with source location."""

    def __init__(self, message: str, line: int, column: int) -> None:
        super().__init__(f"{line}:{column}: {message}")
        self.message = message
        self.line = line
        self.column = column


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    line: int
    column: int


@dataclass
class SnbtNode:
    pass


@dataclass
class SnbtComment(SnbtNode):
    text: list[str] = field(default_factory=list)


@dataclass
class SnbtScalar(SnbtNode):
    value: object = None
    tag_type: str = "string"
    raw: str | None = None


@dataclass
class SnbtList(SnbtNode):
    items: list[SnbtNode] = field(default_factory=list)


@dataclass
class SnbtArray(SnbtNode):
    array_type: str = "I"
    items: list[SnbtScalar | SnbtComment] = field(default_factory=list)


@dataclass
class SnbtEntry:
    key: str
    value: SnbtNode
    key_was_quoted: bool = False


@dataclass
class SnbtCompound(SnbtNode):
    entries: list[SnbtEntry | SnbtComment] = field(default_factory=list)


@dataclass
class SnbtDocument:
    root: SnbtNode
    nodes: list[SnbtNode] = field(default_factory=list)


def tokenize(text: str) -> Iterator[Token]:
    """Yield SNBT tokens from *text*."""

    i = 0
    line = 1
    column = 1

    def advance_char() -> str:
        nonlocal i, line, column
        ch = text[i]
        i += 1
        if ch == "\n":
            line += 1
            column = 1
        else:
            column += 1
        return ch

    while i < len(text):
        ch = text[i]

        if ch in " \t\r":
            advance_char()
            continue

        if ch == "\n":
            yield Token("NEWLINE", "\n", line, column)
            advance_char()
            continue

        if ch == "#":
            start_line, start_col = line, column
            advance_char()
            chars: list[str] = []
            while i < len(text) and text[i] != "\n":
                chars.append(advance_char())
            yield Token("COMMENT", "".join(chars).rstrip(), start_line, start_col)
            continue

        if ch in "{}[]:;,":
            yield Token(ch, ch, line, column)
            advance_char()
            continue

        if ch in "\"'":
            quote = advance_char()
            start_line, start_col = line, column - 1
            chars = []
            while i < len(text):
                current = advance_char()
                if current == quote:
                    yield Token("STRING", "".join(chars), start_line, start_col)
                    break
                if current == "\\":
                    if i >= len(text):
                        raise SnbtSyntaxError("unterminated escape sequence", line, column)
                    escaped = advance_char()
                    chars.append(_decode_escape(escaped, line, column))
                else:
                    chars.append(current)
            else:
                raise SnbtSyntaxError("unterminated string", start_line, start_col)
            continue

        if ch in BARE_WORD_CHARS:
            start_line, start_col = line, column
            chars = []
            while i < len(text) and text[i] in BARE_WORD_CHARS:
                chars.append(advance_char())
            yield Token("BARE", "".join(chars), start_line, start_col)
            continue

        raise SnbtSyntaxError(f"unexpected character {ch!r}", line, column)

    yield Token("EOF", "", line, column)


def _decode_escape(ch: str, line: int, column: int) -> str:
    if ch == "n":
        return "\n"
    if ch == "r":
        return "\r"
    if ch == "t":
        return "\t"
    if ch == "b":
        return "\b"
    if ch == "f":
        return "\f"
    if ch in ('"', "'", "\\"):
        return ch
    # Vanilla SNBT mostly treats unknown escapes literally; keep that behavior.
    return ch


class Parser:
    def __init__(self, text: str) -> None:
        self.tokens = list(tokenize(text))
        self.index = 0
        self.pending_comments: list[str] = []

    @property
    def current(self) -> Token:
        return self.tokens[self.index]

    def advance(self) -> Token:
        token = self.current
        self.index += 1
        return token

    def match(self, *kinds: str) -> Token | None:
        if self.current.kind in kinds:
            return self.advance()
        return None

    def expect(self, kind: str) -> Token:
        token = self.current
        if token.kind != kind:
            raise SnbtSyntaxError(f"expected {kind!r}, got {token.kind!r}", token.line, token.column)
        return self.advance()

    def parse_document(self) -> SnbtDocument:
        leading = self.collect_separators()
        root = self.parse_value()
        trailing = self.collect_separators()
        if self.current.kind != "EOF":
            token = self.current
            raise SnbtSyntaxError("unexpected content after root value", token.line, token.column)
        return SnbtDocument(root=root, nodes=[*leading, root, *trailing])

    def collect_separators(self) -> list[SnbtComment]:
        comments: list[SnbtComment] = []
        current_comment: SnbtComment | None = None
        newlines_after_comment = 0

        while self.current.kind in {"NEWLINE", "COMMENT", ","}:
            if self.current.kind == "COMMENT":
                if current_comment is None or newlines_after_comment > 1:
                    current_comment = SnbtComment()
                    comments.append(current_comment)
                current_comment.text.append(self.advance().value)
                newlines_after_comment = 0
                continue

            if self.current.kind == "NEWLINE":
                self.advance()
                if current_comment is not None:
                    newlines_after_comment += 1
                continue

            self.advance()
            current_comment = None
            newlines_after_comment = 0
        return comments

    def parse_value(self) -> SnbtNode:
        token = self.current

        if token.kind == "{":
            node = self.parse_compound()
        elif token.kind == "[":
            node = self.parse_list_or_array()
        elif token.kind == "STRING":
            node = SnbtScalar(value=self.advance().value, tag_type="string")
        elif token.kind == "BARE":
            node = self.parse_bare_value()
        else:
            raise SnbtSyntaxError(f"expected value, got {token.kind!r}", token.line, token.column)

        return node

    def parse_compound(self) -> SnbtCompound:
        self.expect("{")
        compound = SnbtCompound()

        while True:
            comments = self.collect_separators()
            if self.current.kind == "}":
                compound.entries.extend(comments)
                self.advance()
                return compound

            compound.entries.extend(comments)

            key_token = self.current
            if key_token.kind == "STRING":
                key = self.advance().value
                key_was_quoted = True
            elif key_token.kind == "BARE":
                key = self.advance().value
                key_was_quoted = False
            else:
                raise SnbtSyntaxError("expected compound key", key_token.line, key_token.column)

            self.expect(":")
            compound.entries.extend(self.collect_separators())
            value = self.parse_value()
            compound.entries.append(SnbtEntry(key=key, value=value, key_was_quoted=key_was_quoted))

            if self.current.kind == ",":
                self.advance()
            elif self.current.kind not in {"NEWLINE", "COMMENT", "}"}:
                token = self.current
                raise SnbtSyntaxError("expected comma, newline, comment, or '}'", token.line, token.column)

    def parse_list_or_array(self) -> SnbtNode:
        self.expect("[")
        if self.current.kind == "BARE" and self.current.value in {"B", "I", "L"}:
            marker = self.advance()
            if self.current.kind == ";":
                self.advance()
                return self.parse_typed_array(marker.value)
            # `[B]` is a plain list containing the string B.
            self.index -= 1

        items: list[SnbtNode] = []
        while True:
            items.extend(self.collect_separators())
            if self.current.kind == "]":
                self.advance()
                return SnbtList(items=items)
            items.append(self.parse_value())
            if self.current.kind == ",":
                self.advance()
            elif self.current.kind not in {"NEWLINE", "COMMENT", "]"}:
                token = self.current
                raise SnbtSyntaxError("expected comma, newline, comment, or ']'", token.line, token.column)

    def parse_typed_array(self, array_type: str) -> SnbtArray:
        items: list[SnbtScalar | SnbtComment] = []
        expected = {"B": "byte", "I": "int", "L": "long"}[array_type]

        while True:
            items.extend(self.collect_separators())
            if self.current.kind == "]":
                self.advance()
                return SnbtArray(array_type=array_type, items=items)

            value = self.parse_value()
            if expected == "byte" and isinstance(value, SnbtScalar) and value.tag_type == "boolean":
                value = SnbtScalar(
                    value=1 if value.value else 0,
                    tag_type="byte",
                    raw="1b" if value.value else "0b",
                )
            if not isinstance(value, SnbtScalar) or value.tag_type != expected:
                token = self.current
                raise SnbtSyntaxError(
                    f"typed array [{array_type};...] expects {expected} values",
                    token.line,
                    token.column,
                )
            items.append(value)

            if self.current.kind == ",":
                self.advance()
            elif self.current.kind not in {"NEWLINE", "COMMENT", "]"}:
                token = self.current
                raise SnbtSyntaxError("expected comma, newline, comment, or ']'", token.line, token.column)

    def parse_bare_value(self) -> SnbtScalar:
        token = self.advance()
        raw = token.value
        lower = raw.lower()

        if lower == "true":
            return SnbtScalar(value=True, tag_type="boolean", raw=raw)
        if lower == "false":
            return SnbtScalar(value=False, tag_type="boolean", raw=raw)

        special = _parse_special_float(raw)
        if special is not None:
            return special

        numeric = _parse_number(raw)
        if numeric is not None:
            return numeric

        return SnbtScalar(value=raw, tag_type="string", raw=raw)


def _parse_special_float(raw: str) -> SnbtScalar | None:
    lower = raw.lower()
    if lower in {"nan", "nanf"}:
        return SnbtScalar(value=math.nan, tag_type="float" if lower.endswith("f") else "double", raw=raw)
    if raw in {"∞", "+∞", "-∞", "∞F", "+∞F", "-∞F", "∞f", "+∞f", "-∞f"}:
        sign = -1.0 if raw.startswith("-") else 1.0
        tag_type = "float" if raw.lower().endswith("f") else "double"
        return SnbtScalar(value=sign * math.inf, tag_type=tag_type, raw=raw)
    return None


def _parse_number(raw: str) -> SnbtScalar | None:
    match = NUMBER_RE.match(raw)
    if not match:
        return None

    body = match.group("body")
    suffix = match.group("suffix").lower()
    has_decimal = "." in body or "e" in body.lower()

    if suffix == "b":
        return SnbtScalar(value=int(float(body)), tag_type="byte", raw=raw)
    if suffix == "s":
        return SnbtScalar(value=int(float(body)), tag_type="short", raw=raw)
    if suffix == "l":
        return SnbtScalar(value=int(float(body)), tag_type="long", raw=raw)
    if suffix == "f":
        return SnbtScalar(value=float(body), tag_type="float", raw=raw)
    if suffix == "d":
        return SnbtScalar(value=float(body), tag_type="double", raw=raw)
    if has_decimal:
        return SnbtScalar(value=float(body), tag_type="double", raw=raw)

    try:
        value = int(body)
    except ValueError:
        return None
    if -(2**31) <= value <= 2**31 - 1:
        return SnbtScalar(value=value, tag_type="int", raw=raw)
    return SnbtScalar(value=raw, tag_type="string", raw=raw)


def parse(text: str) -> SnbtDocument:
    return Parser(text).parse_document()


class Formatter:
    def __init__(self, indent: str = "  ", commas: bool = False) -> None:
        self.indent = indent
        self.commas = commas

    def format_document(self, document: SnbtDocument) -> str:
        lines: list[str] = []
        for node in document.nodes:
            self._format_node(node, lines, 0)
        return "\n".join(lines) + "\n"

    def _format_node(self, node: SnbtNode, lines: list[str], depth: int, prefix: str = "") -> None:
        if isinstance(node, SnbtComment):
            for text in node.text:
                lines.append(f"{self.indent * depth}#{text}")
        elif isinstance(node, SnbtCompound):
            self._format_compound(node, lines, depth, prefix)
        elif isinstance(node, SnbtList):
            rendered = self._format_list(node, depth)
            lines.append(f"{self.indent * depth}{prefix}{rendered}")
        elif isinstance(node, SnbtArray):
            rendered = self._format_array(node)
            lines.append(f"{self.indent * depth}{prefix}{rendered}")
        elif isinstance(node, SnbtScalar):
            lines.append(f"{self.indent * depth}{prefix}{format_scalar(node)}")
        else:
            raise TypeError(f"unknown SNBT node: {type(node)!r}")

    def _format_compound(self, node: SnbtCompound, lines: list[str], depth: int, prefix: str = "") -> None:
        lines.append(f"{self.indent * depth}{prefix}{{")
        real_entries = [entry for entry in node.entries if isinstance(entry, SnbtEntry)]
        seen_entries = 0
        for entry in node.entries:
            if isinstance(entry, SnbtComment):
                self._format_node(entry, lines, depth + 1)
                continue
            seen_entries += 1
            entry_prefix = f"{format_key(entry.key)}: "
            self._format_node(entry.value, lines, depth + 1, entry_prefix)
            if self.commas and seen_entries < len(real_entries) and lines:
                lines[-1] += ","
        lines.append(f"{self.indent * depth}}}")

    def _format_list(self, node: SnbtList, depth: int) -> str:
        if not node.items:
            return "[]"
        if any(isinstance(item, (SnbtComment, SnbtCompound)) for item in node.items):
            return self._format_multiline_list(node, depth)
        return "[" + ", ".join(format_node_inline(item) for item in node.items) + "]"

    def _format_multiline_list(self, node: SnbtList, depth: int) -> str:
        lines = ["["]
        for index, item in enumerate(node.items):
            before = len(lines)
            self._format_node(item, lines, depth + 1)
            if self.commas and index < len(node.items) - 1 and len(lines) > before:
                lines[-1] += ","
        lines.append(f"{self.indent * depth}]")
        return "\n".join(lines)

    def _format_array(self, node: SnbtArray) -> str:
        parts = [format_scalar(item) for item in node.items if isinstance(item, SnbtScalar)]
        return f"[{node.array_type};" + ", ".join(parts) + "]"


def format_node_inline(node: SnbtNode) -> str:
    if isinstance(node, SnbtComment):
        return " ".join(f"#{text}" for text in node.text)
    if isinstance(node, SnbtScalar):
        return format_scalar(node)
    if isinstance(node, SnbtArray):
        parts = [format_scalar(item) for item in node.items if isinstance(item, SnbtScalar)]
        return f"[{node.array_type};" + ", ".join(parts) + "]"
    if isinstance(node, SnbtList):
        return "[" + ", ".join(format_node_inline(item) for item in node.items) + "]"
    if isinstance(node, SnbtCompound):
        entries = [entry for entry in node.entries if isinstance(entry, SnbtEntry)]
        return "{" + ", ".join(f"{format_key(entry.key)}: {format_node_inline(entry.value)}" for entry in entries) + "}"
    raise TypeError(f"unknown SNBT node: {type(node)!r}")


def format_key(key: str) -> str:
    return key if BARE_WORD_RE.match(key) else quote_string(key)


def format_scalar(node: SnbtScalar) -> str:
    if node.tag_type == "string":
        return quote_string(str(node.value))
    if node.tag_type == "boolean":
        return "true" if node.value else "false"
    if node.tag_type == "byte":
        return f"{int(cast(int, node.value))}b"
    if node.tag_type == "short":
        return f"{int(cast(int, node.value))}s"
    if node.tag_type == "int":
        return str(int(cast(int, node.value)))
    if node.tag_type == "long":
        return f"{int(cast(int, node.value))}L"
    if node.tag_type == "float":
        return _format_float(float(cast(float, node.value)), "f")
    if node.tag_type == "double":
        return _format_float(float(cast(float, node.value)), "d")
    return quote_string(str(node.value))


def _format_float(value: float, suffix: str) -> str:
    if math.isnan(value):
        return "NaN" + (suffix if suffix == "f" else "")
    if math.isinf(value):
        return ("-" if value < 0 else "") + "∞" + (suffix if suffix == "f" else "")
    text = repr(value)
    if "e" not in text.lower() and "." not in text:
        text += ".0"
    return text + suffix


def quote_string(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
        .replace('"', '\\"')
    )
    return f'"{escaped}"'


def to_plain_value(node: SnbtNode) -> object:
    """Convert the AST into ordinary Python containers.

    Numeric type information is intentionally lost here; use the AST directly
    when a checker needs exact NBT tag types.
    """

    if isinstance(node, SnbtScalar):
        return node.value
    if isinstance(node, SnbtComment):
        return None
    if isinstance(node, SnbtList):
        return [to_plain_value(item) for item in node.items if not isinstance(item, SnbtComment)]
    if isinstance(node, SnbtArray):
        return [item.value for item in node.items if isinstance(item, SnbtScalar)]
    if isinstance(node, SnbtCompound):
        return {entry.key: to_plain_value(entry.value) for entry in node.entries if isinstance(entry, SnbtEntry)}
    raise TypeError(f"unknown SNBT node: {type(node)!r}")


def ast_to_json_obj(value: SnbtDocument | SnbtNode | SnbtEntry) -> dict[str, object]:
    """Convert the parsed AST into a JSON-serializable object."""

    if isinstance(value, SnbtDocument):
        return {
            "type": "document",
            "nodes": [ast_to_json_obj(node) for node in value.nodes],
        }

    if isinstance(value, SnbtEntry):
        return {
            "key": value.key,
            "key_was_quoted": value.key_was_quoted,
            "value": ast_to_json_obj(value.value),
        }

    if isinstance(value, SnbtComment):
        return {
            "type": "comment",
            "text": value.text,
        }

    base: dict[str, object] = {}

    if isinstance(value, SnbtScalar):
        base.update(
            {
                "type": value.tag_type,
                "value": _json_safe_scalar_value(value.value),
                "raw": value.raw,
            }
        )
        return base

    if isinstance(value, SnbtList):
        base.update(
            {
                "type": "list",
                "items": [ast_to_json_obj(item) for item in value.items],
            }
        )
        return base

    if isinstance(value, SnbtArray):
        base.update(
            {
                "type": "array",
                "array_type": value.array_type,
                "items": [ast_to_json_obj(item) for item in value.items],
            }
        )
        return base

    if isinstance(value, SnbtCompound):
        base.update(
            {
                "type": "compound",
                "entries": [ast_to_json_obj(entry) for entry in value.entries],
            }
        )
        return base

    raise TypeError(f"unknown SNBT AST value: {type(value)!r}")


def _json_safe_scalar_value(value: object) -> object:
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
    return value


def print_ast_json(document: SnbtDocument, *, indent: int = 2) -> None:
    """Print a parsed SNBT document's AST as JSON."""

    print(json.dumps(ast_to_json_obj(document), ensure_ascii=False, indent=indent))


def check_file(path: Path) -> None:
    parse(path.read_text(encoding="utf-8"))


def format_file(path: Path, *, write: bool, commas: bool) -> str:
    text = path.read_text(encoding="utf-8")
    formatted = Formatter(commas=commas).format_document(parse(text))
    if write:
        path.write_text(formatted, encoding="utf-8")
    return formatted


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parse, check, and format SNBT files.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="validate SNBT syntax")
    check.add_argument("files", nargs="+", type=Path)

    fmt = subparsers.add_parser("format", help="format SNBT")
    fmt.add_argument("files", nargs="+", type=Path)
    fmt.add_argument("-w", "--write", action="store_true", help="write changes back to files")
    fmt.add_argument("--commas", action="store_true", help="emit commas between multiline entries")

    ast = subparsers.add_parser("ast", help="print parsed AST as JSON")
    ast.add_argument("file", type=Path)
    ast.add_argument("--indent", type=int, default=2, help="JSON indentation width")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    try:
        if args.command == "check":
            for path in args.files:
                check_file(path)
            return 0

        if args.command == "format":
            for path in args.files:
                formatted = format_file(path, write=args.write, commas=args.commas)
                if not args.write:
                    sys.stdout.write(formatted)
            return 0

        if args.command == "ast":
            document = parse(args.file.read_text(encoding="utf-8"))
            print_ast_json(document, indent=args.indent)
            return 0
    except SnbtError as exc:
        print(f"SNBT error: {exc}", file=sys.stderr)
        return 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
