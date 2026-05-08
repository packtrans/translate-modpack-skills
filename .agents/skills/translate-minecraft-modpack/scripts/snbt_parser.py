#!/usr/bin/env python3
"""
SNBT parser that produces a source-aware AST.

The parser supports vanilla Java SNBT and the FTB-style config extensions
documented in ../snbt.md: line comments starting with '#', single-quoted
strings, and optional commas between multiline compound/list entries.

Use parse_snbt() from other validation scripts, or run this file directly to
parse files and print their AST as JSON.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal


NumberType = Literal["byte", "short", "int", "long", "float", "double"]
NodeKind = Literal["compound", "list", "string", "number", "boolean", "comment"]


_NUMBER_RE = re.compile(
    r"^[+-]?(?:(?:\d+\.\d*)|(?:\.\d+)|(?:\d+))(?:[eE][+-]?\d+)?([bBsSlLfFdD])?$"
)
_INTEGER_RE = re.compile(r"^[+-]?\d+$")
_UNQUOTED_STOP = set(" \t\r\n,;:{}[]()\"'#")


@dataclass(frozen=True)
class Position:
    index: int
    line: int
    column: int


@dataclass(frozen=True)
class Span:
    start: Position
    end: Position


@dataclass
class AstNode:
    span: Span
    kind: NodeKind = field(init=False)


@dataclass
class CompoundEntry:
    key: str
    value: AstNode
    span: Span
    key_quote: str | None = None
    key_raw: str | None = None


@dataclass
class CommentNode(AstNode):
    lines: list[str] = field(default_factory=list)
    line_spans: list[Span] = field(default_factory=list)
    kind: Literal["comment"] = field(default="comment", init=False)


@dataclass
class CompoundNode(AstNode):
    entries: list[CompoundEntry] = field(default_factory=list)
    items: list[CompoundEntry | CommentNode] = field(default_factory=list)
    kind: Literal["compound"] = field(default="compound", init=False)


@dataclass
class ListNode(AstNode):
    elements: list[AstNode] = field(default_factory=list)
    items: list[AstNode] = field(default_factory=list)
    typed_array: Literal["B", "I", "L"] | None = None
    kind: Literal["list"] = field(default="list", init=False)


@dataclass
class StringNode(AstNode):
    value: str = ""
    raw: str = ""
    quote: str | None = None
    kind: Literal["string"] = field(default="string", init=False)


@dataclass
class NumberNode(AstNode):
    value: int | float | str = 0
    raw: str = ""
    number_type: NumberType = "int"
    suffix: str | None = None
    kind: Literal["number"] = field(default="number", init=False)


@dataclass
class BooleanNode(AstNode):
    value: bool = False
    raw: str = ""
    kind: Literal["boolean"] = field(default="boolean", init=False)


class SnbtParseError(ValueError):
    def __init__(self, message: str, filename: str, position: Position):
        self.message = message
        self.filename = filename
        self.position = position
        super().__init__(f"{filename}:{position.line}:{position.column}: {message}")


class SnbtParser:
    def __init__(self, content: str, filename: str = "<input>"):
        self.content = content
        self.filename = filename
        self.i = 0
        self.line = 1
        self.column = 1

    def parse(self) -> AstNode:
        node = self._parse_value()
        self._skip_ws()
        if not self._eof():
            self._error(f"unexpected trailing character {self._peek()!r}")
        return node

    def _parse_value(self) -> AstNode:
        self._skip_ws()
        if self._eof():
            self._error("expected value")
        if self._peek() == "#":
            return self._parse_comment_block()

        ch = self._peek()
        if ch == "{":
            return self._parse_compound()
        if ch == "[":
            return self._parse_list()
        if ch in "'\"":
            return self._parse_quoted_string()
        return self._parse_scalar()

    def _parse_compound(self) -> CompoundNode:
        start = self._position()
        self._expect("{")
        entries: list[CompoundEntry] = []
        items: list[CompoundEntry | CommentNode] = []

        while True:
            self._skip_ws()
            if self._peek_or_none() == "#":
                items.append(self._parse_comment_block())
                continue
            if self._consume_if("}"):
                return CompoundNode(
                    span=Span(start, self._position()),
                    entries=entries,
                    items=items,
                )
            if self._eof():
                self._error("unclosed compound; expected '}'", start)

            entry_start = self._position()
            key, key_quote, key_raw = self._parse_key()
            self._skip_ws()
            self._expect(":")
            value = self._parse_value()
            entry = CompoundEntry(
                key=key,
                key_quote=key_quote,
                key_raw=key_raw,
                value=value,
                span=Span(entry_start, value.span.end),
            )
            entries.append(entry)
            items.append(entry)

            value_end_line = value.span.end.line
            self._skip_ws()
            while self._peek_or_none() == "#":
                items.append(self._parse_comment_block())
                self._skip_ws()
            if self._consume_if(","):
                continue
            if self._peek_or_none() == "}":
                continue
            if self._eof():
                self._error("unclosed compound; expected '}'", start)
            if self.line == value_end_line:
                self._error("expected ',' or '}' after compound entry")

    def _parse_list(self) -> ListNode:
        start = self._position()
        self._expect("[")
        elements: list[AstNode] = []
        items: list[AstNode] = []
        typed_array = self._parse_typed_array_prefix()

        while True:
            self._skip_ws()
            if self._peek_or_none() == "#":
                items.append(self._parse_comment_block())
                continue
            if self._consume_if("]"):
                return ListNode(
                    span=Span(start, self._position()),
                    elements=elements,
                    items=items,
                    typed_array=typed_array,
                )
            if self._eof():
                self._error("unclosed list; expected ']'", start)

            value = self._parse_value()
            elements.append(value)
            items.append(value)

            value_end_line = value.span.end.line
            self._skip_ws()
            while self._peek_or_none() == "#":
                items.append(self._parse_comment_block())
                self._skip_ws()
            if self._consume_if(","):
                continue
            if self._peek_or_none() == "]":
                continue
            if self._eof():
                self._error("unclosed list; expected ']'", start)
            if self.line == value_end_line:
                self._error("expected ',' or ']' after list element")

    def _parse_typed_array_prefix(self) -> Literal["B", "I", "L"] | None:
        self._skip_ws()
        mark = self._mark()
        ch = self._peek_or_none()
        if ch not in {"B", "I", "L"}:
            return None
        self._advance()
        self._skip_ws()
        if self._consume_if(";"):
            return ch  # type: ignore[return-value]
        self._restore(mark)
        return None

    def _parse_key(self) -> tuple[str, str | None, str]:
        if self._peek_or_none() in {"'", '"'}:
            node = self._parse_quoted_string()
            return node.value, node.quote, node.raw

        start = self._position()
        raw = self._read_unquoted_token()
        if not raw:
            self._error("expected compound key", start)
        return raw, None, raw

    def _parse_quoted_string(self) -> StringNode:
        start = self._position()
        quote = self._peek()
        self._advance()
        raw_chars = [quote]
        value_chars: list[str] = []

        while not self._eof():
            ch = self._peek()
            raw_chars.append(ch)
            self._advance()
            if ch == "\n":
                self._error("newline in quoted string", start)
            if ch == "\\":
                if self._eof():
                    self._error("unterminated escape in quoted string", start)
                escaped = self._peek()
                raw_chars.append(escaped)
                self._advance()
                value_chars.append(self._decode_escape(escaped))
                continue
            if ch == quote:
                return StringNode(
                    span=Span(start, self._position()),
                    value="".join(value_chars),
                    raw="".join(raw_chars),
                    quote=quote,
                )
            value_chars.append(ch)

        self._error("unclosed quoted string", start)

    def _parse_scalar(self) -> AstNode:
        start = self._position()
        raw = self._read_unquoted_token()
        if not raw:
            self._error("expected value", start)

        lower = raw.lower()
        if lower == "true":
            return BooleanNode(
                span=Span(start, self._position()),
                value=True,
                raw=raw,
            )
        if lower == "false":
            return BooleanNode(
                span=Span(start, self._position()),
                value=False,
                raw=raw,
            )

        special = self._parse_special_number(raw)
        if special is not None:
            value, number_type, suffix = special
            return NumberNode(
                span=Span(start, self._position()),
                value=value,
                raw=raw,
                number_type=number_type,
                suffix=suffix,
            )

        match = _NUMBER_RE.match(raw)
        if match:
            suffix = match.group(1)
            number_type = self._number_type(raw, suffix)
            return NumberNode(
                span=Span(start, self._position()),
                value=self._convert_number(raw, number_type, suffix),
                raw=raw,
                number_type=number_type,
                suffix=suffix,
            )

        return StringNode(
            span=Span(start, self._position()),
            value=raw,
            raw=raw,
            quote=None,
        )

    def _parse_special_number(
        self, raw: str
    ) -> tuple[float, Literal["float", "double"], str | None] | None:
        suffix = raw[-1] if raw[-1:] in {"f", "F", "d", "D"} else None
        core = raw[:-1] if suffix else raw
        lower = core.lower()
        number_type: Literal["float", "double"] = (
            "float" if suffix in {"f", "F"} else "double"
        )

        if lower in {"nan", "+nan", "-nan"}:
            return math.nan, number_type, suffix
        if core in {"∞", "+∞"} or lower in {"infinity", "+infinity", "inf", "+inf"}:
            return math.inf, number_type, suffix
        if core == "-∞" or lower in {"-infinity", "-inf"}:
            return -math.inf, number_type, suffix
        return None

    def _number_type(self, raw: str, suffix: str | None) -> NumberType:
        if suffix:
            return {
                "b": "byte",
                "s": "short",
                "l": "long",
                "f": "float",
                "d": "double",
            }[suffix.lower()]  # type: ignore[return-value]
        return "int" if _INTEGER_RE.match(raw) else "double"

    def _convert_number(
        self, raw: str, number_type: NumberType, suffix: str | None
    ) -> int | float:
        body = raw[:-1] if suffix else raw
        if number_type in {"byte", "short", "int", "long"}:
            return int(body, 10)
        return float(body)

    def _decode_escape(self, ch: str) -> str:
        return {
            "n": "\n",
            "r": "\r",
            "t": "\t",
            "b": "\b",
            "f": "\f",
            "\\": "\\",
            "'": "'",
            '"': '"',
        }.get(ch, ch)

    def _read_unquoted_token(self) -> str:
        start = self.i
        while not self._eof() and self._peek() not in _UNQUOTED_STOP:
            self._advance()
        return self.content[start : self.i]

    def _skip_ws(self) -> None:
        while not self._eof():
            ch = self._peek()
            if ch in " \t\r\n":
                self._advance()
                continue
            break

    def _parse_comment_block(self) -> CommentNode:
        start = self._position()
        lines: list[str] = []
        line_spans: list[Span] = []

        while self._peek_or_none() == "#":
            line_start = self._position()
            self._expect("#")
            text_start = self.i
            while not self._eof() and self._peek() != "\n":
                self._advance()
            lines.append(self.content[text_start : self.i].strip())
            line_spans.append(Span(line_start, self._position()))

            mark = self._mark()
            self._skip_ws()
            if self._peek_or_none() != "#":
                self._restore(mark)
                break

        return CommentNode(
            span=Span(start, line_spans[-1].end),
            lines=lines,
            line_spans=line_spans,
        )

    def _expect(self, ch: str) -> None:
        if self._peek_or_none() != ch:
            self._error(f"expected {ch!r}")
        self._advance()

    def _consume_if(self, ch: str) -> bool:
        if self._peek_or_none() == ch:
            self._advance()
            return True
        return False

    def _peek(self) -> str:
        return self.content[self.i]

    def _peek_or_none(self) -> str | None:
        return None if self._eof() else self.content[self.i]

    def _advance(self) -> None:
        ch = self.content[self.i]
        self.i += 1
        if ch == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1

    def _position(self) -> Position:
        return Position(index=self.i, line=self.line, column=self.column)

    def _mark(self) -> tuple[int, int, int]:
        return self.i, self.line, self.column

    def _restore(self, mark: tuple[int, int, int]) -> None:
        self.i, self.line, self.column = mark

    def _eof(self) -> bool:
        return self.i >= len(self.content)

    def _error(self, message: str, position: Position | None = None) -> None:
        raise SnbtParseError(message, self.filename, position or self._position())


def parse_snbt(content: str, filename: str = "<input>") -> AstNode:
    """Parse SNBT content into a source-aware AST."""
    return SnbtParser(content, filename).parse()


def ast_to_plain_data(node: AstNode) -> Any:
    """
    Convert an AST to Python primitives for consumers that do not need spans.

    Typed arrays are returned as lists here; inspect ListNode.typed_array on the
    AST when the distinction between [B;...] and [...] matters.
    """
    if isinstance(node, CompoundNode):
        return {entry.key: ast_to_plain_data(entry.value) for entry in node.entries}
    if isinstance(node, ListNode):
        return [ast_to_plain_data(element) for element in node.elements]
    if isinstance(node, (StringNode, NumberNode, BooleanNode)):
        return node.value
    raise TypeError(f"unsupported AST node: {type(node).__name__}")


def ast_to_dict(node: AstNode) -> dict[str, Any]:
    """Convert an AST node to a JSON-serializable dictionary."""
    return asdict(node)


def _json_default(value: Any) -> Any:
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse SNBT files into an AST")
    parser.add_argument("files", nargs="+", type=Path, help="SNBT files to parse")
    parser.add_argument(
        "--plain",
        action="store_true",
        help="print plain data instead of the source-aware AST",
    )
    args = parser.parse_args()

    exit_code = 0
    for path in args.files:
        try:
            content = path.read_text(encoding="utf-8")
            ast = parse_snbt(content, str(path))
            output = ast_to_plain_data(ast) if args.plain else ast_to_dict(ast)
            print(json.dumps(output, indent=2, ensure_ascii=False, default=_json_default))
        except (OSError, SnbtParseError) as exc:
            print(exc, file=sys.stderr)
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
