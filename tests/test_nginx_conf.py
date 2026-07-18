#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tolerant nginx config parser: tokenizing, blocks, includes, recovery."""

from wtftools.nginx_conf import context, if_condition, parse, parse_string


def _tree(text):
    root, errors = parse_string(text, filename="t.conf")
    return root, errors


# ---- simple directives and blocks ----


def test_simple_directive():
    root, errors = _tree("worker_processes auto;")
    assert not errors
    assert len(root.children) == 1
    d = root.children[0]
    assert d.name == "worker_processes"
    assert d.args == ["auto"]
    assert d.children is None


def test_nested_blocks():
    root, errors = _tree("http {\n  server {\n    listen 80;\n  }\n}")
    assert not errors
    http = root.children[0]
    assert http.name == "http" and http.is_block
    server = http.children[0]
    assert server.name == "server"
    listen = server.children[0]
    assert listen.name == "listen" and listen.args == ["80"]
    assert context(listen) == ("http", "server")


def test_block_with_args():
    root, _ = _tree("location /api { proxy_pass http://x; }")
    loc = root.children[0]
    assert loc.name == "location"
    assert loc.args == ["/api"]
    assert loc.is_block


def test_brace_without_space():
    root, errors = _tree("server{listen 80;}")
    assert not errors
    assert root.children[0].name == "server"
    assert root.children[0].children[0].name == "listen"


def test_empty_block_vs_simple():
    root, _ = _tree("events { }\ndaemon off;")
    events = root.children[0]
    daemon = root.children[1]
    assert events.children == []  # empty block
    assert daemon.children is None  # simple directive


def test_multiline_directive_line_number():
    root, _ = _tree("\n\nlog_format main\n  '$remote_addr'\n  '$status';")
    d = root.children[0]
    assert d.name == "log_format"
    assert d.line == 3  # line of the name token, not the terminator


# ---- quotes, comments, escapes ----


def test_quoted_arg_with_spaces_and_specials():
    root, _ = _tree('return 200 "a; b { c } # d";')
    d = root.children[0]
    assert d.args == ["200", "a; b { c } # d"]
    assert d.quoted == (False, True)


def test_escapes_in_quotes():
    root, _ = _tree(r'add_header X "line1\nline2\ttab\\bs";')
    assert root.children[0].args[1] == "line1\nline2\ttab\\bs"


def test_hash_inside_quotes_is_literal():
    root, _ = _tree('proxy_pass "http://h/#frag";')
    assert root.children[0].args == ["http://h/#frag"]


def test_full_line_and_trailing_comments():
    root, _ = _tree("# a comment\nlisten 80; # trailing\nroot /srv;")
    names = [c.name for c in root.children]
    assert names == ["listen", "root"]


def test_comment_with_braces_and_semicolons():
    root, errors = _tree("# TODO close } here ;\nlisten 80;")
    assert not errors
    assert [c.name for c in root.children] == ["listen"]


def test_hash_mid_token_is_literal():
    root, _ = _tree("set $x a#b;")
    assert root.children[0].args == ["$x", "a#b"]


def test_unterminated_quote_records_error():
    root, errors = _tree('return 200 "oops;')
    assert any("unterminated" in e.message for e in errors)


# ---- regex / variable heuristics ----


def test_unquoted_regex_quantifier():
    root, errors = _tree("location ~ ^/v\\d{1,3}$ { }")
    assert not errors
    loc = root.children[0]
    assert loc.args == ["~", "^/v\\d{1,3}$"]
    assert loc.is_block


def test_brace_var_in_arg():
    root, _ = _tree("proxy_pass http://up_${host}/x;")
    assert root.children[0].args == ["http://up_${host}/x"]


def test_quoted_regex_location():
    root, errors = _tree('location ~ "^/api/v[0-9]{1,2}$" { return 200; }')
    assert not errors
    loc = root.children[0]
    assert loc.args == ["~", "^/api/v[0-9]{1,2}$"]


# ---- if condition helper ----


def test_if_condition_helper():
    root, _ = _tree("if ($http_origin ~ example) { return 403; }")
    node = root.children[0]
    assert node.name == "if"
    assert if_condition(node) == "$http_origin ~ example"


# ---- map / geo entries ----


def test_map_block_entries_are_directives():
    root, _ = _tree("map $uri $d {\n  default a;\n  ~^/x b;\n  hostnames;\n}")
    m = root.children[0]
    keys = [c.name for c in m.children]
    assert keys == ["default", "~^/x", "hostnames"]
    assert m.children[0].args == ["a"]
    assert m.children[2].args == []


# ---- opaque lua blocks ----


def test_lua_block_body_not_parsed():
    text = 'content_by_lua_block {\n  local s = "}"\n  -- } stray comment\n  ngx.say("hi")\n}\nlisten 80;'
    root, errors = _tree(text)
    assert not errors
    lua = root.children[0]
    assert lua.name == "content_by_lua_block"
    assert lua.children is None
    assert "ngx.say" in lua.raw_body
    # The block must terminate correctly so the following directive is parsed.
    assert root.children[1].name == "listen"


def test_lua_long_bracket_string_with_brace():
    text = 'content_by_lua_block {\n  local t = [[ a } b ]]\n  ngx.say("ok")\n}\nlisten 80;'
    root, errors = _tree(text)
    assert not errors
    lua = root.children[0]
    assert lua.name == "content_by_lua_block"
    assert "ngx.say" in lua.raw_body  # not truncated at the '}' inside [[ ]]
    assert root.children[1].name == "listen"


def test_lua_long_comment_with_brace():
    text = "access_by_lua_block {\n  --[[ multi\n  line } comment ]]\n  ngx.exit(403)\n}\nlisten 80;"
    root, errors = _tree(text)
    assert not errors
    assert root.children[0].name == "access_by_lua_block"
    assert root.children[1].name == "listen"


# ---- recovery ----


def test_stray_close_brace():
    root, errors = _tree("listen 80;\n}")
    assert any("unexpected '}'" in e.message for e in errors)
    assert root.children[0].name == "listen"


def test_missing_semicolon_before_brace():
    root, errors = _tree("server {\n  listen 80\n}")
    assert any("missing ';'" in e.message for e in errors)
    assert root.children[0].children[0].name == "listen"


def test_unclosed_block_at_eof():
    root, errors = _tree("http {\n  server {\n    listen 80;")
    assert any("unclosed block" in e.message for e in errors)


def test_unterminated_brace_var_does_not_swallow_block():
    from wtftools.nginx_conf import NginxConfig

    root, errors = parse_string("proxy_pass http://${backend;\nserver { listen 80; }", filename="t.conf")
    cfg = NginxConfig(root, errors, [])
    # A malformed '${' must not absorb the following block into one argument;
    # the server/listen directives stay visible to the tree walk.
    assert any(s.name == "server" for s in cfg.find_all("server"))
    assert any(d.name == "listen" for d in cfg.find_all("listen"))
    assert max(len(a) for node in cfg.walk() for a in node.args) < 20


# ---- includes ----


def test_include_glob_spliced(tmp_path):
    (tmp_path / "conf.d").mkdir()
    (tmp_path / "conf.d" / "a.conf").write_text("server { listen 8001; }\n")
    (tmp_path / "conf.d" / "b.conf").write_text("server { listen 8002; }\n")
    main = tmp_path / "nginx.conf"
    main.write_text("http {\n  include conf.d/*.conf;\n}\n")

    cfg = parse(str(main))
    assert not cfg.errors
    listens = sorted(d.args[0] for d in cfg.find_all("listen"))
    assert listens == ["8001", "8002"]
    # Spliced server blocks report http as their context.
    for server in cfg.find_all("server"):
        assert context(server) == ("http",)


def test_include_missing_literal_errors(tmp_path):
    main = tmp_path / "nginx.conf"
    main.write_text("http {\n  include does-not-exist.conf;\n}\n")
    cfg = parse(str(main))
    assert any("cannot read include" in e.message for e in cfg.errors)


def test_include_glob_no_match_is_silent(tmp_path):
    main = tmp_path / "nginx.conf"
    main.write_text("http {\n  include conf.d/*.conf;\n}\n")
    cfg = parse(str(main))
    assert not cfg.errors


def test_include_cycle_detected(tmp_path):
    a = tmp_path / "a.conf"
    b = tmp_path / "b.conf"
    a.write_text("include b.conf;\n")
    b.write_text("include a.conf;\n")
    cfg = parse(str(a))
    assert any("cycle" in e.message for e in cfg.errors)


# ---- encoding tolerance ----


def test_bom_and_crlf(tmp_path):
    main = tmp_path / "nginx.conf"
    main.write_bytes(b"\xef\xbb\xbfworker_processes 1;\r\nevents { }\r\n")
    cfg = parse(str(main))
    assert not cfg.errors
    assert cfg.root.children[0].name == "worker_processes"


def test_invalid_utf8_does_not_crash(tmp_path):
    main = tmp_path / "nginx.conf"
    main.write_bytes(b"server_name \xff\xfe.example;\n")
    cfg = parse(str(main))
    assert cfg.root.children[0].name == "server_name"
