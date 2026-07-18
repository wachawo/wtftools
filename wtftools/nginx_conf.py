#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tolerant, stdlib-only nginx configuration parser.

Builds a tree of directives with full context so security checks can walk it.
The parser never raises on malformed config content — it records errors and
keeps going, because it runs inside a read-only audit tool against arbitrary
real-world files. It does not validate directive names or argument counts,
expand variables, or evaluate `if` conditions: it is a faithful tokenizer plus
tree builder, nothing more.
"""

import glob
import logging
import os
from dataclasses import dataclass, field
from typing import Iterator, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Directives whose body is not nginx syntax (OpenResty Lua). Their content is
# captured verbatim into raw_body and never parsed as directives.
OPAQUE_BLOCK_SUFFIX = "_by_lua_block"
OPAQUE_BLOCK_NAMES = frozenset()

MAX_INCLUDE_DEPTH = 10
MAX_BLOCK_DEPTH = 128
MAX_FILE_BYTES = 10 * 1024 * 1024

# Standard locations of the main nginx config across distros / package managers.
DEFAULT_CONFIG_PATHS = (
    "/etc/nginx/nginx.conf",
    "/usr/local/nginx/conf/nginx.conf",
    "/usr/local/etc/nginx/nginx.conf",
    "/opt/homebrew/etc/nginx/nginx.conf",
)


def default_config_path() -> Optional[str]:
    """First standard nginx.conf that exists and is readable, or None."""
    for path in DEFAULT_CONFIG_PATHS:
        if os.path.isfile(path) and os.access(path, os.R_OK):
            return path
    return None


@dataclass
class ParseError:
    """A problem tolerated during parsing, with its source location."""

    file: str
    line: int
    message: str


@dataclass(eq=False)
class Directive:
    """One nginx directive. Simple directives have children=None; blocks have a
    list (possibly empty). raw_body holds an opaque (Lua) block body."""

    name: str
    args: List[str] = field(default_factory=list)
    children: Optional[List["Directive"]] = None
    file: str = ""
    line: int = 0
    parent: Optional["Directive"] = None
    raw_body: Optional[str] = None
    quoted: Tuple[bool, ...] = ()

    @property
    def is_block(self) -> bool:
        return self.children is not None

    def __repr__(self) -> str:
        kind = "block" if self.is_block else "directive"
        return f"<Directive {kind} {self.name!r} args={self.args} {self.file}:{self.line}>"


class NginxConfig:
    """Parsed configuration: the directive tree plus tolerated errors."""

    def __init__(self, root: Directive, errors: List[ParseError], files: List[str]):
        self.root = root
        self.errors = errors
        self.files = files

    def walk(self) -> Iterator[Directive]:
        """DFS pre-order over every directive (opaque bodies are not descended)."""
        stack = list(reversed(self.root.children or []))
        while stack:
            node = stack.pop()
            yield node
            if node.children:
                stack.extend(reversed(node.children))

    def find_all(self, name: str) -> Iterator[Directive]:
        """Every directive with the given name, anywhere in the tree."""
        for node in self.walk():
            if node.name == name:
                yield node


def ancestors(node: Directive) -> Iterator[Directive]:
    """Yield parent, grandparent, ... up to (but excluding) the synthetic root."""
    cur = node.parent
    while cur is not None and cur.parent is not None:
        yield cur
        cur = cur.parent


def context(node: Directive) -> Tuple[str, ...]:
    """Ancestor directive names, outermost first, e.g. ('http','server','location')."""
    names = [a.name for a in ancestors(node)]
    names.reverse()
    return tuple(names)


def nearest(node: Directive, name: str) -> Optional[Directive]:
    """Nearest enclosing ancestor with the given name (innermost first)."""
    for a in ancestors(node):
        if a.name == name:
            return a
    return None


def if_condition(node: Directive) -> str:
    """For an `if` directive, its condition with the outer parentheses stripped."""
    text = " ".join(node.args).strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1].strip()
    return text


def _is_opaque(name: str) -> bool:
    return name.endswith(OPAQUE_BLOCK_SUFFIX) or name in OPAQUE_BLOCK_NAMES


def _read_text(path: str) -> str:
    """Read a config file as text, tolerant of encoding and size."""
    size = os.path.getsize(path)
    if size > MAX_FILE_BYTES:
        raise ValueError(f"file too large ({size} bytes)")
    with open(path, "rb") as fh:
        raw = fh.read()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    return raw.decode("utf-8", errors="replace")


def parse_string(text: str, filename: str = "<string>", keep_comments: bool = False) -> Tuple[Directive, List[ParseError]]:
    """Parse config text into a synthetic root directive plus tolerated errors.

    Includes are not resolved here (there is no filesystem prefix); use parse().
    """
    root = Directive(name="", args=[], children=[], file=filename, line=0)
    errors: List[ParseError] = []
    stack: List[Directive] = [root]
    pos = 0
    line = 1
    n = len(text)
    pending: List[str] = []
    pending_quoted: List[bool] = []
    pending_line = 0

    def add_error(ln: int, msg: str) -> None:
        errors.append(ParseError(filename, ln, msg))

    def read_quoted(quote: str) -> str:
        """Read a quoted run starting just after the opening quote at pos."""
        nonlocal pos, line
        buf: List[str] = []
        while pos < n:
            c = text[pos]
            if c == "\\" and pos + 1 < n:
                nxt = text[pos + 1]
                if nxt in ('"', "'", "\\"):
                    buf.append(nxt)
                elif nxt in ("t", "r", "n"):
                    buf.append({"t": "\t", "r": "\r", "n": "\n"}[nxt])
                else:
                    buf.append("\\" + nxt)  # preserve regex escapes like \. \d
                pos += 2
                continue
            if c == quote:
                pos += 1
                return "".join(buf)
            if c == "\n":
                line += 1
            buf.append(c)
            pos += 1
        add_error(line, f"unterminated quoted string in {filename}")
        return "".join(buf)

    def read_word() -> Tuple[str, bool]:
        """Read one word (possibly mixing quoted and unquoted runs). Returns
        (text, was_any_part_quoted). Assumes pos is at a non-space, non-comment,
        non-structural character."""
        nonlocal pos, line
        buf: List[str] = []
        was_quoted = False
        while pos < n:
            c = text[pos]
            if c in ('"', "'"):
                pos += 1
                buf.append(read_quoted(c))
                was_quoted = True
                continue
            if c in " \t\r\n;}":
                break
            if c == "{":
                # A '{' ends the word (opens a block) unless it is a regex
                # quantifier attached to an existing token (e.g. \d{1,3}).
                if buf:
                    quant = _match_quantifier(text, pos)
                    if quant:
                        buf.append(quant)
                        pos += len(quant)
                        continue
                break
            if c == "\\" and pos + 1 < n:
                # Preserve the backslash so regex escapes like \d, \. survive;
                # skipping two chars keeps an escaped ; { } from terminating.
                buf.append(text[pos : pos + 2])
                pos += 2
                continue
            if c == "$" and pos + 1 < n and text[pos + 1] == "{":
                end = text.find("}", pos + 2)
                # A ${name} is a single unbroken token. If a boundary char shows
                # up before the brace it is an unterminated typo — treat '$' as a
                # literal rather than swallowing config up to a later block's '}'.
                if end != -1 and not any(ch in " \t\r\n;{" for ch in text[pos + 2 : end]):
                    buf.append(text[pos : end + 1])
                    pos = end + 1
                    continue
            buf.append(c)
            pos += 1
        return "".join(buf), was_quoted

    def capture_opaque() -> str:
        """Capture a Lua block body verbatim; pos is just after the '{'. Returns
        the body (exclusive of the outer braces) and leaves pos after the '}'."""
        nonlocal pos, line
        start = pos
        depth = 1
        while pos < n:
            c = text[pos]
            if c == "\n":
                line += 1
                pos += 1
                continue
            if c in ('"', "'"):
                quote = c
                pos += 1
                while pos < n and text[pos] != quote:
                    if text[pos] == "\\":
                        pos += 1
                    elif text[pos] == "\n":
                        line += 1
                    pos += 1
                pos += 1
                continue
            if c == "[":
                level = _long_bracket_level(text, pos)
                if level is not None:
                    end, newlines = _skip_long_bracket(text, pos + level + 2, level)
                    line += newlines
                    pos = end
                    continue
            if c == "-" and pos + 1 < n and text[pos + 1] == "-":
                level = _long_bracket_level(text, pos + 2)
                if level is not None:
                    end, newlines = _skip_long_bracket(text, pos + 2 + level + 2, level)
                    line += newlines
                    pos = end
                    continue
                nl = text.find("\n", pos)
                if nl == -1:
                    pos = n
                else:
                    pos = nl
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    body = text[start:pos]
                    pos += 1
                    return body
            pos += 1
        add_error(line, f"unterminated lua block in {filename}")
        return text[start:pos]

    def flush_simple(ln: int) -> None:
        nonlocal pending, pending_quoted
        node = Directive(
            name=pending[0],
            args=pending[1:],
            children=None,
            file=filename,
            line=ln,
            parent=stack[-1],
            quoted=tuple(pending_quoted[1:]),
        )
        stack[-1].children.append(node)
        pending = []
        pending_quoted = []

    while pos < n:
        c = text[pos]
        if c == "\n":
            line += 1
            pos += 1
            continue
        if c in " \t\r":
            pos += 1
            continue
        if c == "#":
            # In the main loop a '#' is always at a token boundary (read_word
            # keeps a mid-token '#' as a literal), so it always opens a comment.
            nl = text.find("\n", pos)
            end = n if nl == -1 else nl
            if keep_comments and not pending:
                stack[-1].children.append(Directive(name="#", args=[text[pos + 1 : end]], children=None, file=filename, line=line, parent=stack[-1]))
            pos = end
            continue
        if c == ";":
            if pending:
                flush_simple(pending_line)
            else:
                add_error(line, "unexpected ';'")
            pos += 1
            continue
        if c == "{":
            if not pending:
                add_error(line, "unexpected '{'")
                block = Directive(name="{", args=[], children=[], file=filename, line=line, parent=stack[-1])
                stack[-1].children.append(block)
                stack.append(block)
                pos += 1
                continue
            name = pending[0]
            block = Directive(
                name=name,
                args=pending[1:],
                children=[],
                file=filename,
                line=pending_line,
                parent=stack[-1],
                quoted=tuple(pending_quoted[1:]),
            )
            pending = []
            pending_quoted = []
            pos += 1
            if _is_opaque(name):
                block.children = None
                block.raw_body = capture_opaque()
                stack[-1].children.append(block)
                continue
            stack[-1].children.append(block)
            if len(stack) >= MAX_BLOCK_DEPTH:
                add_error(line, "maximum block nesting depth exceeded")
            else:
                stack.append(block)
            continue
        if c == "}":
            if pending:
                add_error(pending_line, "missing ';' before '}'")
                flush_simple(pending_line)
            if len(stack) > 1:
                stack.pop()
            else:
                add_error(line, "unexpected '}'")
            pos += 1
            continue
        # A word starts here.
        if not pending:
            pending_line = line
        word, was_quoted = read_word()
        pending.append(word)
        pending_quoted.append(was_quoted)

    if pending:
        add_error(pending_line, "missing ';' at end of file")
        flush_simple(pending_line)
    while len(stack) > 1:
        add_error(stack[-1].line, f"unclosed block '{stack[-1].name}'")
        stack.pop()

    return root, errors


def _long_bracket_level(text: str, i: int) -> Optional[int]:
    """If text[i] opens a Lua long bracket ('[' '='* '['), return its level (the
    number of '=' signs), else None."""
    if i >= len(text) or text[i] != "[":
        return None
    j = i + 1
    while j < len(text) and text[j] == "=":
        j += 1
    if j < len(text) and text[j] == "[":
        return j - i - 1
    return None


def _skip_long_bracket(text: str, i: int, level: int) -> Tuple[int, int]:
    """From i (just past the opening long bracket), find the matching close
    ']' '='*level ']'. Return (index_after_close, newlines_consumed)."""
    close = "]" + "=" * level + "]"
    j = text.find(close, i)
    end = len(text) if j == -1 else j + len(close)
    return end, text.count("\n", i, end)


def _match_quantifier(text: str, pos: int) -> str:
    """If text[pos:] is a regex quantifier like {2}, {1,}, {1,3}, return it."""
    i = pos + 1
    n = len(text)
    digits1 = ""
    while i < n and text[i].isdigit():
        digits1 += text[i]
        i += 1
    if not digits1:
        return ""
    if i < n and text[i] == "}":
        return text[pos : i + 1]
    if i < n and text[i] == ",":
        i += 1
        while i < n and text[i].isdigit():
            i += 1
        if i < n and text[i] == "}":
            return text[pos : i + 1]
    return ""


def parse(path: str, prefix: Optional[str] = None, keep_comments: bool = False) -> NginxConfig:
    """Parse a config file and splice in its includes. Raises only if the root
    file cannot be read; all config-content problems become recorded errors."""
    path = os.path.abspath(path)
    if prefix is None:
        prefix = os.path.dirname(path)
    text = _read_text(path)
    root, errors = parse_string(text, filename=path, keep_comments=keep_comments)
    files = [path]
    _resolve_includes(root, prefix, errors, files, chain=[os.path.realpath(path)], depth=0, keep_comments=keep_comments)
    return NginxConfig(root=root, errors=errors, files=files)


def _resolve_includes(
    node: Directive,
    prefix: str,
    errors: List[ParseError],
    files: List[str],
    chain: List[str],
    depth: int,
    keep_comments: bool,
) -> None:
    """Walk a block's children, expanding include directives in place."""
    if node.children is None:
        return
    expanded: List[Directive] = []
    for child in node.children:
        if child.name == "include" and child.children is None:
            expanded.append(child)
            expanded.extend(_expand_include(child, prefix, errors, files, chain, depth, keep_comments))
            continue
        expanded.append(child)
        if child.children:
            _resolve_includes(child, prefix, errors, files, chain, depth, keep_comments)
    node.children = expanded


def _expand_include(
    inc: Directive,
    prefix: str,
    errors: List[ParseError],
    files: List[str],
    chain: List[str],
    depth: int,
    keep_comments: bool,
) -> List[Directive]:
    """Return the top-level directives from every file an include resolves to."""
    if not inc.args:
        errors.append(ParseError(inc.file, inc.line, "include with no path"))
        return []
    if depth >= MAX_INCLUDE_DEPTH:
        errors.append(ParseError(inc.file, inc.line, "maximum include depth exceeded"))
        return []
    pattern = inc.args[0]
    if not os.path.isabs(pattern):
        pattern = os.path.join(prefix, pattern)
    is_glob = any(ch in pattern for ch in "*?[")
    if is_glob:
        targets = sorted(glob.glob(pattern))
    else:
        targets = [pattern]

    result: List[Directive] = []
    for target in targets:
        real = os.path.realpath(target)
        if real in chain:
            errors.append(ParseError(inc.file, inc.line, f"include cycle at {target}"))
            continue
        try:
            text = _read_text(target)
        except OSError as exc:
            if not is_glob:
                errors.append(ParseError(inc.file, inc.line, f"cannot read include {target}: {type(exc).__name__}"))
            continue
        except ValueError as exc:
            errors.append(ParseError(inc.file, inc.line, f"include {target}: {exc}"))
            continue
        files.append(target)
        sub_root, sub_errors = parse_string(text, filename=target, keep_comments=keep_comments)
        errors.extend(sub_errors)
        _resolve_includes(sub_root, prefix, errors, files, chain + [real], depth + 1, keep_comments)
        for node in sub_root.children or []:
            node.parent = inc.parent
            result.append(node)
    return result
