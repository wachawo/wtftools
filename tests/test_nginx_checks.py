#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""nginx security checks: detection of well-known config misconfigurations."""

from wtftools import audit, nginx_checks
from wtftools.nginx_conf import parse_string


def _run(text, check=None):
    root, _ = parse_string(text, filename="t.conf")

    class _Cfg:
        def __init__(self, root):
            self.root = root

        def walk(self):
            from wtftools.nginx_conf import NginxConfig

            return NginxConfig(self.root, [], []).walk()

        def find_all(self, name):
            from wtftools.nginx_conf import NginxConfig

            return NginxConfig(self.root, [], []).find_all(name)

    cfg = _Cfg(root)
    if check:
        return nginx_checks.CHECKS[check](cfg)
    return nginx_checks.analyze(cfg)


def _checks(findings):
    return {f.check for f in findings}


# ---- alias_traversal ----


def test_alias_traversal_vulnerable():
    f = _run("location /files {\n  alias /home/;\n}", "alias-traversal")
    assert len(f) == 1
    assert f[0].severity == "high"


def test_alias_traversal_safe_trailing_slash():
    f = _run("location /files/ {\n  alias /home/;\n}", "alias-traversal")
    assert f == []


def test_alias_traversal_regex_location_skipped():
    f = _run("location ~ /files {\n  alias /home/;\n}", "alias-traversal")
    assert f == []


def test_alias_traversal_medium_when_alias_no_slash():
    f = _run("location /files {\n  alias /home;\n}", "alias-traversal")
    assert len(f) == 1
    assert f[0].severity == "medium"


def test_alias_traversal_named_location_skipped():
    # Named (@) locations are internal-only — no client-facing traversal.
    f = _run("location @fallback {\n  alias /var/www/data/;\n}", "alias-traversal")
    assert f == []


# ---- host_spoofing ----


def test_host_spoofing_vulnerable():
    f = _run("location / {\n  proxy_set_header Host $http_host;\n}", "host-spoofing")
    assert len(f) == 1
    assert f[0].severity == "medium"


def test_host_spoofing_arg():
    f = _run("location / {\n  proxy_set_header Host $arg_host;\n}", "host-spoofing")
    assert len(f) == 1


def test_host_spoofing_safe():
    f = _run("location / {\n  proxy_set_header Host $host;\n}", "host-spoofing")
    assert f == []


def test_host_spoofing_other_header_ignored():
    f = _run("location / {\n  proxy_set_header X-Forwarded-Host $http_host;\n}", "host-spoofing")
    assert f == []


def test_host_spoofing_brace_form():
    # ${http_host} / ${arg_x} are equivalent to the bare forms in nginx.
    f = _run("location / {\n  proxy_set_header Host ${http_host};\n}", "host-spoofing")
    assert len(f) == 1
    g = _run("location / {\n  proxy_set_header Host ${arg_h};\n}", "host-spoofing")
    assert len(g) == 1


# ---- valid_referers ----


def test_valid_referers_none():
    f = _run("location / {\n  valid_referers none server_names;\n}", "valid-referers")
    assert len(f) == 1
    assert f[0].severity == "high"


def test_valid_referers_safe():
    f = _run("location / {\n  valid_referers server_names *.example.com;\n}", "valid-referers")
    assert f == []


def test_valid_referers_substring_not_matched():
    f = _run("location / {\n  valid_referers none.example.com;\n}", "valid-referers")
    assert f == []


# ---- add_header_redefinition ----


def test_add_header_redefinition_vulnerable():
    text = "server {\n  add_header X-Frame-Options DENY;\n  location / {\n    add_header Cache-Control no-store;\n  }\n}"
    f = _run(text, "add-header-redefinition")
    assert len(f) == 1
    assert "x-frame-options" in f[0].message


def test_add_header_redefinition_safe_when_redeclared():
    text = "server {\n  add_header X-Frame-Options DENY;\n  location / {\n    add_header Cache-Control no-store;\n    add_header X-Frame-Options DENY;\n  }\n}"
    f = _run(text, "add-header-redefinition")
    assert f == []


def test_add_header_redefinition_ignores_noninteresting():
    text = "server {\n  add_header X-Custom foo;\n  location / {\n    add_header Cache-Control no-store;\n  }\n}"
    f = _run(text, "add-header-redefinition")
    assert f == []


# ---- add_header_multiline ----


def test_add_header_multiline_vulnerable():
    text = "location / {\n  add_header Content-Security-Policy \"\n    default-src 'none';\";\n}"
    f = _run(text, "add-header-multiline")
    assert len(f) == 1
    assert f[0].severity == "low"


def test_add_header_multiline_safe_single_line():
    text = "location / {\n  add_header Content-Security-Policy \"default-src 'none';\";\n}"
    f = _run(text, "add-header-multiline")
    assert f == []


# ---- ssrf ----


def test_ssrf_arg_dest():
    f = _run("location /proxy/ {\n  proxy_pass $arg_dest;\n}", "ssrf")
    assert len(f) == 1
    assert f[0].severity == "high"


def test_ssrf_capture_scheme_host():
    f = _run("location ~ /proxy/(.*)/(.*)/(.*)$ {\n  proxy_pass $1://$2/$3;\n}", "ssrf")
    assert len(f) == 1


def test_ssrf_internal_skipped():
    f = _run("location ~ /proxy/(.*)$ {\n  internal;\n  proxy_pass http://backend/$1;\n}", "ssrf")
    assert f == []


def test_ssrf_safe_static_host_with_request_uri():
    f = _run("location /img/ {\n  proxy_pass http://storage.example.com$request_uri;\n}", "ssrf")
    assert f == []


def test_ssrf_set_chain():
    f = _run("location ~ /p/(.*)$ {\n  set $backend $1;\n  proxy_pass http://$backend;\n}", "ssrf")
    assert len(f) == 1


# ---- http_splitting ----


def test_http_splitting_uri_in_return():
    f = _run("location / {\n  return 301 http://$host$uri;\n}", "http-splitting")
    assert len(f) == 1
    assert f[0].severity == "high"


def test_http_splitting_safe_request_uri():
    f = _run("location / {\n  return 301 http://$host$request_uri;\n}", "http-splitting")
    assert f == []


def test_http_splitting_capture():
    f = _run("location ~ /p/(\\W*)$ {\n  set $p $1;\n  proxy_pass http://s/$p;\n}", "http-splitting")
    assert len(f) == 1


def test_http_splitting_return_single_arg_skipped():
    f = _run("location / {\n  return 403;\n}", "http-splitting")
    assert f == []


def test_http_splitting_capture_whitespace_class():
    # \\s matches newline just like \\W — the capture must be flagged.
    f = _run("location ~ /p/(\\s*)$ {\n  set $p $1;\n  proxy_pass http://s/$p;\n}", "http-splitting")
    assert len(f) == 1


# ---- origins ----


def test_origins_unterminated_host():
    text = 'location / {\n  if ($http_origin ~ "^https://example\\.com") {\n    add_header Access-Control-Allow-Origin $http_origin;\n  }\n}'
    f = _run(text, "origins")
    assert len(f) == 1
    assert f[0].severity == "high"


def test_origins_safe_terminated():
    text = 'location / {\n  if ($http_origin ~ "^https://example\\.com/") {\n    add_header Access-Control-Allow-Origin $http_origin;\n  }\n}'
    f = _run(text, "origins")
    assert f == []


def test_origins_referer_is_medium():
    text = 'location / {\n  if ($http_referer ~ "example\\.com") {\n    set $ok 1;\n  }\n}'
    f = _run(text, "origins")
    assert len(f) == 1
    assert f[0].severity == "medium"


def test_origins_unescaped_dot():
    text = 'location / {\n  if ($http_origin ~ "^https://example.com/") {\n    set $ok 1;\n  }\n}'
    f = _run(text, "origins")
    assert len(f) == 1


# ---- registry / analyze ----


def test_analyze_sorts_by_severity():
    text = 'http {\n  server {\n    valid_referers none;\n    location / {\n      add_header Content-Security-Policy "x";\n    }\n  }\n}'
    findings = _run(text)
    severities = [f.severity for f in findings]
    assert severities == sorted(severities, key=lambda s: -nginx_checks.SEVERITY_RANK[s])


def test_all_checks_registered():
    assert set(nginx_checks.CHECKS) == {
        "alias-traversal",
        "host-spoofing",
        "valid-referers",
        "add-header-redefinition",
        "add-header-multiline",
        "ssrf",
        "http-splitting",
        "origins",
    }


# ---- audit check wiring (_check_nginx_config) ----


def test_audit_nginx_config_skip(monkeypatch):
    monkeypatch.setattr(audit.nginx_conf, "default_config_path", lambda: None)
    assert audit._check_nginx_config().status == "skip"


def test_audit_nginx_config_ok(tmp_path, monkeypatch):
    conf = tmp_path / "nginx.conf"
    conf.write_text("http {\n  server { listen 80; }\n}\n")
    monkeypatch.setattr(audit.nginx_conf, "default_config_path", lambda: str(conf))
    assert audit._check_nginx_config().status == "ok"


def test_audit_nginx_config_fail_on_high(tmp_path, monkeypatch):
    conf = tmp_path / "nginx.conf"
    conf.write_text("http {\n  server {\n    location /files {\n      alias /home/;\n    }\n  }\n}\n")
    monkeypatch.setattr(audit.nginx_conf, "default_config_path", lambda: str(conf))
    r = audit._check_nginx_config()
    assert r.status == "fail"
    assert r.detail


def test_audit_nginx_config_warn_on_medium(tmp_path, monkeypatch):
    conf = tmp_path / "nginx.conf"
    conf.write_text("http {\n  server {\n    location / {\n      proxy_set_header Host $http_host;\n    }\n  }\n}\n")
    monkeypatch.setattr(audit.nginx_conf, "default_config_path", lambda: str(conf))
    assert audit._check_nginx_config().status == "warn"


def test_audit_nginx_registered():
    assert "nginx-config" in audit.CHECK_REGISTRY
