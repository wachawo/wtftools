#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Security checks over a parsed nginx config tree.

Each check walks the Directive tree from nginx_conf and returns Findings for a
well-known class of nginx misconfiguration. The taint checks (ssrf,
http-splitting, origins) use a deliberately simplified variable model — it
catches the common patterns but does not fully emulate a regex state machine;
see the per-check notes.
"""

import logging
import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from wtftools.nginx_conf import Directive, NginxConfig, ancestors, context, if_condition, nearest

logger = logging.getLogger(__name__)

SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1}

INTERESTING_HEADERS = {
    "x-frame-options",
    "x-content-type-options",
    "x-xss-protection",
    "content-security-policy",
    "cache-control",
}

LOCATION_MODIFIERS = ("=", "~", "~*", "^~")

# Built-in variables with the properties the checks care about. slash=value
# always contains '/'; dot=can contain '.'; nl/cr=can carry a raw newline / CR.
BUILTIN_VARS: Dict[str, Dict[str, bool]] = {
    "uri": {"slash": True, "dot": True, "nl": True, "cr": True},
    "document_uri": {"slash": True, "dot": True, "nl": True, "cr": True},
    "request_uri": {"slash": True, "dot": True, "nl": False, "cr": False},
    "args": {"slash": False, "dot": True, "nl": False, "cr": False},
    "query_string": {"slash": False, "dot": True, "nl": False, "cr": False},
    "request": {"slash": False, "dot": True, "nl": False, "cr": False},
}

# Attacker-controlled but charset-bounded (no raw CR/LF): $arg_*, $http_*, $cookie_*.
TAINTED_PREFIXES = ("arg_", "http_", "cookie_")

# Built-ins nginx validates or derives; not attacker-controllable for these checks.
SAFE_BUILTINS = frozenset(
    {
        "host",
        "hostname",
        "server_name",
        "scheme",
        "server_addr",
        "server_port",
        "remote_addr",
        "remote_port",
        "remote_user",
        "server_protocol",
        "request_method",
        "https",
        "status",
        "body_bytes_sent",
        "bytes_sent",
        "connection",
        "connection_requests",
        "msec",
        "pid",
        "request_id",
        "request_length",
        "request_time",
        "time_iso8601",
        "time_local",
        "nginx_version",
        "pipe",
        "proxy_protocol_addr",
        "realpath_root",
        "document_root",
        "fastcgi_path_info",
        "content_type",
        "content_length",
    }
)

FALSE = {"slash": False, "dot": False, "nl": False, "cr": False}

_VAR_RE = re.compile(r"\$\{?(\w+)\}?")


@dataclass
class Finding:
    """One security finding anchored to a config location."""

    check: str
    severity: str  # high | medium | low
    message: str
    file: str
    line: int
    where: str = ""


def _loc(node: Directive) -> str:
    """Compact human context, e.g. 'server > location /files'."""
    parts = list(context(node)) + [node.name]
    label = " > ".join(parts[-3:])
    if node.args:
        label += " " + node.args[0]
    return label


def _finding(check: str, severity: str, message: str, node: Directive) -> Finding:
    return Finding(check=check, severity=severity, message=message, file=node.file, line=node.line, where=_loc(node))


# ---- variable model ----


def _find_vars(text: str) -> List[str]:
    """Variable names referenced in a string ('$name', '${name}', '$1')."""
    return _VAR_RE.findall(text)


def _class_has(body: str, char: str) -> bool:
    """Does a character-class body (between the brackets) include `char`?"""
    i, n = 0, len(body)
    while i < n:
        c = body[i]
        if c == "\\" and i + 1 < n:
            esc = body[i + 1]
            if esc == "s" and char in " \t\n\r\f\v":
                return True
            if esc == "w" and (char.isalnum() or char == "_"):
                return True
            if esc == "W" and not (char.isalnum() or char == "_"):
                return True
            if esc == "d" and char.isdigit():
                return True
            if esc == "D" and not char.isdigit():
                return True
            if {"n": "\n", "r": "\r", "t": "\t"}.get(esc) == char:
                return True
            if esc == char:
                return True
            i += 2
            continue
        if i + 2 < n and body[i + 1] == "-" and body[i + 2] != "]":
            if body[i] <= char <= body[i + 2]:
                return True
            i += 3
            continue
        if c == char:
            return True
        i += 1
    return False


def _sub_can_contain(sub: str, char: str) -> bool:
    """Heuristic: can this regex capture sub-pattern match a string with `char`?

    Approximate: treats '.' as matching any char including newline, and errs
    toward True on unknown constructs to avoid misses.
    """
    i, n = 0, len(sub)
    while i < n:
        c = sub[i]
        if c == "\\" and i + 1 < n:
            esc = sub[i + 1]
            if esc == "W" and char in ".\n\r":
                return True
            if esc == "S" and char == ".":
                return True
            if esc == "D" and char in ".\n\r":
                return True
            if esc == "s" and char in " \t\n\r\f\v":
                return True
            if {"n": "\n", "r": "\r", "t": "\t"}.get(esc) == char:
                return True
            i += 2
            continue
        if c == ".":
            return True
        if c == "[":
            j = i + 1
            neg = j < n and sub[j] == "^"
            if neg:
                j += 1
            body_start = j
            if j < n and sub[j] == "]":
                j += 1
            while j < n and sub[j] != "]":
                if sub[j] == "\\":
                    j += 1
                j += 1
            body = sub[body_start:j]
            if neg:
                if not _class_has(body, char):
                    return True
            elif _class_has(body, char):
                return True
            i = j + 1
            continue
        i += 1
    return False


def _regex_of(node: Directive) -> Optional[str]:
    """The regex a location/if block matches on, or None if not a regex match."""
    if node.name == "location" and node.args:
        if node.args[0] in ("~", "~*") and len(node.args) > 1:
            return node.args[1]
        return None
    if node.name == "if":
        cond = if_condition(node)
        tokens = cond.split()
        for i, tok in enumerate(tokens):
            if tok in ("~", "~*", "!~", "!~*") and i + 1 < len(tokens):
                return tokens[i + 1].strip("\"'")
    return None


def _capture_groups(regex: str) -> Dict[str, str]:
    """Map capture number ('1', '2', ...) and named groups to their sub-pattern."""
    groups: Dict[str, str] = {}
    opens: List[Optional[dict]] = []
    num = 0
    i, n = 0, len(regex)
    while i < n:
        c = regex[i]
        if c == "\\":
            i += 2
            continue
        if c == "[":
            j = i + 1
            if j < n and regex[j] == "^":
                j += 1
            if j < n and regex[j] == "]":
                j += 1
            while j < n and regex[j] != "]":
                if regex[j] == "\\":
                    j += 1
                j += 1
            i = j + 1
            continue
        if c == "(":
            m = re.match(r"\(\?P?<([a-zA-Z_]\w*)>", regex[i:])
            if m:
                num += 1
                opens.append({"num": num, "name": m.group(1), "start": i + m.end()})
                i += m.end()
                continue
            if regex[i : i + 2] == "(?":
                opens.append(None)  # non-capturing / assertion
                i += 1
                continue
            num += 1
            opens.append({"num": num, "name": None, "start": i + 1})
            i += 1
            continue
        if c == ")":
            grp = opens.pop() if opens else None
            if grp:
                sub = regex[grp["start"] : i]
                groups[str(grp["num"])] = sub
                if grp["name"]:
                    groups[grp["name"]] = sub
            i += 1
            continue
        i += 1
    return groups


def _scope_captures(node: Directive) -> Dict[str, str]:
    """Capture groups visible to `node` from its own rewrite regex and the
    nearest enclosing regex location / if."""
    caps: Dict[str, str] = {}
    if node.name == "rewrite" and node.args:
        caps.update(_capture_groups(node.args[0]))
    for anc in ancestors(node):
        regex = _regex_of(anc)
        if regex:
            for k, v in _capture_groups(regex).items():
                caps.setdefault(k, v)
    return caps


def _set_map(cfg: NginxConfig) -> Dict[str, str]:
    """Map user variable name -> defining value expression from `set` directives."""
    sets: Dict[str, str] = {}
    for node in cfg.find_all("set"):
        if len(node.args) >= 2 and node.args[0].startswith("$"):
            sets[node.args[0][1:]] = node.args[1]
    return sets


def _var_props(name: str, node: Directive, sets: Dict[str, str], unknown_tainted: bool, visited: Optional[set] = None) -> Dict[str, bool]:
    """Resolve a variable's taint properties in the scope of `node`."""
    visited = visited or set()
    if name in visited:
        return dict(FALSE)
    visited.add(name)

    caps = _scope_captures(node)
    if name in caps:
        sub = caps[name]
        return {
            "slash": False,
            "dot": _sub_can_contain(sub, "."),
            "nl": _sub_can_contain(sub, "\n"),
            "cr": _sub_can_contain(sub, "\r"),
        }
    if name in BUILTIN_VARS:
        return dict(BUILTIN_VARS[name])
    if name.startswith(TAINTED_PREFIXES):
        return {"slash": False, "dot": True, "nl": False, "cr": False}
    if name in SAFE_BUILTINS:
        return dict(FALSE)
    if name in sets:
        inner = _find_vars(sets[name])
        if not inner:
            return dict(FALSE)  # constant value, not attacker-controlled
        props = dict(FALSE)
        for v in inner:
            p = _var_props(v, node, sets, unknown_tainted, visited)
            for k in props:
                props[k] = props[k] or p[k]
        return props
    if unknown_tainted:
        return {"slash": False, "dot": True, "nl": True, "cr": True}
    return dict(FALSE)


# ---- tree checks (no taint) ----


def check_alias_traversal(cfg: NginxConfig) -> List[Finding]:
    """alias in a prefix location whose path lacks a trailing '/': ../ escape."""
    findings: List[Finding] = []
    for alias in cfg.find_all("alias"):
        loc = nearest(alias, "location")
        if loc is None or not loc.args:
            continue
        if loc.args[0] in LOCATION_MODIFIERS:
            modifier = loc.args[0]
            path = loc.args[1] if len(loc.args) > 1 else ""
        else:
            modifier = ""
            path = loc.args[0]
        if modifier not in ("", "^~"):
            continue
        if path.startswith("@"):
            continue  # named locations are internal-only; no client-facing URI
        if path.endswith("/"):
            continue
        severity = "high" if (alias.args and alias.args[0].endswith("/")) else "medium"
        findings.append(
            _finding(
                "alias-traversal",
                severity,
                f'location "{path}" has no trailing "/" but uses alias — a request like "{path}../" escapes the aliased directory',
                loc,
            )
        )
    return findings


def check_host_spoofing(cfg: NginxConfig) -> List[Finding]:
    """proxy_set_header Host from the client-controlled $http_host / $arg_*."""
    findings: List[Finding] = []
    for node in cfg.find_all("proxy_set_header"):
        if len(node.args) < 2:
            continue
        header, value = node.args[0], node.args[1]
        if header.lower() != "host":
            continue
        var = "$" + value[2:-1] if value.startswith("${") and value.endswith("}") else value
        if var == "$http_host" or var.startswith("$arg_"):
            findings.append(
                _finding(
                    "host-spoofing",
                    "medium",
                    f'proxy_set_header Host {value} forwards the client-supplied Host verbatim — use "$host" instead',
                    node,
                )
            )
    return findings


def check_valid_referers(cfg: NginxConfig) -> List[Finding]:
    """valid_referers ... none ...: referer-less requests bypass the check."""
    findings: List[Finding] = []
    for node in cfg.find_all("valid_referers"):
        if "none" in node.args:
            findings.append(
                _finding(
                    "valid-referers",
                    "high",
                    'valid_referers includes "none", so requests without a Referer header pass validation',
                    node,
                )
            )
    return findings


def _header_names(block: Directive) -> set:
    """Lowercased names of add_header directives declared directly in a block."""
    names = set()
    for child in block.children or []:
        if child.name == "add_header" and child.args:
            names.add(child.args[0].lower())
    return names


def check_add_header_redefinition(cfg: NginxConfig) -> List[Finding]:
    """A nested add_header drops security headers set at an outer level."""
    findings: List[Finding] = []
    for block in cfg.walk():
        if block.name not in ("server", "location", "if") or block.children is None:
            continue
        actual = _header_names(block)
        if not actual:
            continue
        parent_headers: set = set()
        for anc in ancestors(block):
            anc_headers = _header_names(anc)
            if anc_headers:
                parent_headers = anc_headers
                break
        dropped = (parent_headers - actual) & INTERESTING_HEADERS
        if dropped:
            names = ", ".join(sorted(dropped))
            findings.append(
                _finding(
                    "add-header-redefinition",
                    "medium",
                    f"nested add_header drops inherited security header(s): {names}",
                    block,
                )
            )
    return findings


def _multiline_values(node: Directive) -> List[str]:
    """Header value strings an add_header / more_set_headers directive emits."""
    if node.name == "add_header":
        return [node.args[1]] if len(node.args) >= 2 else []
    values: List[str] = []
    skip_next = False
    for arg in node.args:
        if skip_next:
            skip_next = False
            continue
        if arg in ("-s", "-t"):
            skip_next = True
            continue
        if arg.startswith("-"):
            continue
        values.append(arg)
    return values


def check_add_header_multiline(cfg: NginxConfig) -> List[Finding]:
    """Folded (multi-line) header values are deprecated and misparsed by some clients."""
    findings: List[Finding] = []
    for name in ("add_header", "more_set_headers"):
        for node in cfg.find_all(name):
            for value in _multiline_values(node):
                if "\n " in value or "\n\t" in value:
                    findings.append(
                        _finding(
                            "add-header-multiline",
                            "low",
                            f"{name} has a multi-line (folded) value — deprecated by RFC 7230 and misparsed by some clients",
                            node,
                        )
                    )
                    break
    return findings


# ---- taint checks ----


def check_ssrf(cfg: NginxConfig) -> List[Finding]:
    """proxy_pass whose scheme/host is built from attacker-controllable input."""
    findings: List[Finding] = []
    sets = _set_map(cfg)
    host_re = re.compile(r"(?P<scheme>[^?#/)]+://)?(?P<host>[^?#/)]+)")
    for node in cfg.find_all("proxy_pass"):
        if not node.args:
            continue
        loc = nearest(node, "location")
        if loc is not None and any(c.name == "internal" for c in (loc.children or [])):
            continue
        m = host_re.match(node.args[0])
        if not m:
            continue
        for part in (m.group("scheme"), m.group("host")):
            if not part:
                continue
            hit = _taint_scan_ssrf(part, node, sets)
            if hit:
                findings.append(hit)
                break  # at most one finding per proxy_pass
    return findings


def _taint_scan_ssrf(part: str, node: Directive, sets: Dict[str, str]) -> Optional[Finding]:
    """Inspect a scheme/host substring: safe if a slash-forced var appears;
    otherwise flag the first dot-capable variable."""
    tainted: Optional[str] = None
    for name in _find_vars(part):
        props = _var_props(name, node, sets, unknown_tainted=True)
        if props["slash"]:
            return None  # forced to contain '/', cannot be smuggled into host/scheme
        if props["dot"] and tainted is None:
            tainted = name
    if tainted:
        return _finding(
            "ssrf",
            "high",
            f'proxy_pass target uses "${tainted}", which can carry attacker-controlled input into the scheme/host (SSRF)',
            node,
        )
    return None


_SPLIT_DIRECTIVES = ("rewrite", "return", "add_header", "proxy_set_header", "proxy_pass")


def check_http_splitting(cfg: NginxConfig) -> List[Finding]:
    """A variable that can carry raw CR/LF is interpolated into a header/redirect."""
    findings: List[Finding] = []
    sets = _set_map(cfg)
    for name in _SPLIT_DIRECTIVES:
        for node in cfg.find_all(name):
            value = _split_value(node)
            if value is None:
                continue
            server_side = name.startswith("proxy_")
            hit = _taint_scan_split(value, node, sets, server_side)
            if hit:
                findings.append(hit)
    return findings


def _split_value(node: Directive) -> Optional[str]:
    """The argument HTTP-splitting inspects: proxy_pass arg 0, else arg 1."""
    if node.name == "proxy_pass":
        return node.args[0] if node.args else None
    return node.args[1] if len(node.args) >= 2 else None


def _taint_scan_split(value: str, node: Directive, sets: Dict[str, str], server_side: bool) -> Optional[Finding]:
    for name in _find_vars(value):
        props = _var_props(name, node, sets, unknown_tainted=False)
        if props["nl"]:
            return _finding("http-splitting", "high", f'"${name}" can contain a newline (\\n), enabling HTTP splitting/header injection', node)
        if not server_side and props["cr"]:
            return _finding("http-splitting", "high", f'"${name}" can contain a carriage return (\\r), enabling HTTP splitting/header injection', node)
    return None


def check_origins(cfg: NginxConfig) -> List[Finding]:
    """Weak referer/origin validation regex in an `if` (unanchored / unescaped
    dot / unterminated host)."""
    findings: List[Finding] = []
    for node in cfg.find_all("if"):
        cond = if_condition(node)
        tokens = cond.split(None, 2)
        if len(tokens) < 3:
            continue
        var, op, pattern = tokens[0], tokens[1], tokens[2]
        if op not in ("~", "~*", "!~", "!~*"):
            continue
        if var not in ("$http_referer", "$http_origin"):
            continue
        pattern = pattern.strip("\"'")
        weakness = _origin_weakness(pattern)
        if weakness:
            severity = "high" if var == "$http_origin" else "medium"
            findings.append(
                _finding(
                    "origins",
                    severity,
                    f"{var} validation regex is weak ({weakness}) — an attacker-controlled origin can satisfy it",
                    node,
                )
            )
    return findings


def _origin_weakness(pattern: str) -> Optional[str]:
    """Name the structural weakness in an origin/referer regex, or None."""
    body = pattern
    if body.startswith("^"):
        body = body[1:]
    else:
        return "not anchored at the start"
    if not (body.endswith("$") or body.endswith("/")):
        return "host not terminated (attacker can append .evil.com)"
    core = body[:-1]
    unescaped_dot = re.search(r"(?<!\\)\.", core)
    if unescaped_dot:
        return "unescaped '.' matches any character"
    return None


CHECKS: Dict[str, Callable[[NginxConfig], List[Finding]]] = {
    "alias-traversal": check_alias_traversal,
    "host-spoofing": check_host_spoofing,
    "valid-referers": check_valid_referers,
    "add-header-redefinition": check_add_header_redefinition,
    "add-header-multiline": check_add_header_multiline,
    "ssrf": check_ssrf,
    "http-splitting": check_http_splitting,
    "origins": check_origins,
}


def analyze(cfg: NginxConfig) -> List[Finding]:
    """Run every check; return findings sorted by severity (highest first)."""
    findings: List[Finding] = []
    for fn in CHECKS.values():
        try:
            findings.extend(fn(cfg))
        except Exception as exc:
            logger.warning(f"nginx check {fn.__name__} failed: {type(exc).__name__}: {exc}")
    findings.sort(key=lambda f: (-SEVERITY_RANK.get(f.severity, 0), f.file, f.line))
    return findings
