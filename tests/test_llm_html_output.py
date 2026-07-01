#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LLM bridge, HTML output, --output, and the fail2ban check."""

import io
import json
from contextlib import redirect_stdout
from unittest import mock

from wtftools import audit, llm, main, sysinfo


def _capture(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main.main(argv)
    return rc, buf.getvalue()


# ---- LLM bridge ----


def test_ollama_no_binary(monkeypatch):
    monkeypatch.setattr(llm.shutil, "which", lambda _: None)
    text, err = llm.call_ollama("hi")
    assert text is None
    assert "not found" in err


def test_ollama_success(monkeypatch):
    monkeypatch.setattr(llm.shutil, "which", lambda _: "/usr/bin/ollama")
    fake_result = mock.Mock(returncode=0, stdout="hello\n", stderr="")
    monkeypatch.setattr(llm.subprocess, "run", lambda *a, **kw: fake_result)
    text, err = llm.call_ollama("prompt")
    assert text == "hello\n"
    assert err is None


def test_ollama_nonzero_exit(monkeypatch):
    monkeypatch.setattr(llm.shutil, "which", lambda _: "/usr/bin/ollama")
    fake_result = mock.Mock(returncode=1, stdout="", stderr="model not found")
    monkeypatch.setattr(llm.subprocess, "run", lambda *a, **kw: fake_result)
    text, err = llm.call_ollama("prompt")
    assert text is None
    assert "model not found" in err


def test_ollama_timeout(monkeypatch):
    monkeypatch.setattr(llm.shutil, "which", lambda _: "/usr/bin/ollama")

    def boom(*a, **kw):
        raise llm.subprocess.TimeoutExpired(cmd="ollama", timeout=60)

    monkeypatch.setattr(llm.subprocess, "run", boom)
    text, err = llm.call_ollama("prompt")
    assert text is None
    assert "timed out" in err


def test_ollama_generic_exception(monkeypatch):
    monkeypatch.setattr(llm.shutil, "which", lambda _: "/usr/bin/ollama")
    monkeypatch.setattr(llm.subprocess, "run", mock.Mock(side_effect=OSError("boom")))
    text, err = llm.call_ollama("prompt")
    assert text is None
    assert "OSError" in err


def test_claude_no_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    text, err = llm.call_claude("hi")
    assert text is None
    assert "ANTHROPIC_API_KEY" in err


def test_claude_no_sdk(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    # simulate ImportError by removing anthropic from sys.modules and ensuring
    # __import__ raises
    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

    def fake_import(name, *a, **kw):
        if name == "anthropic":
            raise ImportError("not installed")
        return real_import(name, *a, **kw)

    monkeypatch.setattr("builtins.__import__", fake_import)
    text, err = llm.call_claude("hi")
    assert text is None
    assert "anthropic SDK" in err


def test_claude_success(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    fake_block = mock.Mock(spec=["text"])
    fake_block.text = "diagnosis here"
    fake_response = mock.Mock(content=[fake_block])
    fake_client = mock.Mock()
    fake_client.messages.create = mock.Mock(return_value=fake_response)
    fake_anthropic = mock.Mock(Anthropic=mock.Mock(return_value=fake_client))

    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

    def fake_import(name, *a, **kw):
        if name == "anthropic":
            return fake_anthropic
        return real_import(name, *a, **kw)

    monkeypatch.setattr("builtins.__import__", fake_import)
    text, err = llm.call_claude("hi")
    assert text == "diagnosis here"
    assert err is None


def test_claude_api_error(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    fake_anthropic = mock.Mock()
    fake_anthropic.Anthropic = mock.Mock(side_effect=RuntimeError("rate limit"))

    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

    def fake_import(name, *a, **kw):
        if name == "anthropic":
            return fake_anthropic
        return real_import(name, *a, **kw)

    monkeypatch.setattr("builtins.__import__", fake_import)
    text, err = llm.call_claude("hi")
    assert text is None
    assert "rate limit" in err


def test_openai_no_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    text, err = llm.call_openai("hi")
    assert text is None
    assert "OPENAI_API_KEY" in err


def test_openai_no_sdk(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake")
    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

    def fake_import(name, *a, **kw):
        if name == "openai":
            raise ImportError
        return real_import(name, *a, **kw)

    monkeypatch.setattr("builtins.__import__", fake_import)
    text, err = llm.call_openai("hi")
    assert text is None
    assert "openai SDK" in err


def test_openai_success(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake")
    fake_choice = mock.Mock()
    fake_choice.message.content = "answer"
    fake_response = mock.Mock(choices=[fake_choice])
    fake_client = mock.Mock()
    fake_client.chat.completions.create = mock.Mock(return_value=fake_response)
    fake_openai = mock.Mock(OpenAI=mock.Mock(return_value=fake_client))

    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

    def fake_import(name, *a, **kw):
        if name == "openai":
            return fake_openai
        return real_import(name, *a, **kw)

    monkeypatch.setattr("builtins.__import__", fake_import)
    text, err = llm.call_openai("hi")
    assert text == "answer"


def test_openai_api_error(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake")
    fake_openai = mock.Mock()
    fake_openai.OpenAI = mock.Mock(side_effect=RuntimeError("api error"))
    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

    def fake_import(name, *a, **kw):
        if name == "openai":
            return fake_openai
        return real_import(name, *a, **kw)

    monkeypatch.setattr("builtins.__import__", fake_import)
    text, err = llm.call_openai("hi")
    assert text is None
    assert "api error" in err


def test_call_llm_unknown_backend():
    text, err = llm.call_llm("nope", "hi")
    assert text is None
    assert "unknown backend" in err


def test_call_llm_dispatch(monkeypatch):
    captured = {}

    def fake_ollama(prompt, model=None, timeout=60):
        captured["called"] = True
        return "ok", None

    monkeypatch.setitem(llm._BACKENDS, "ollama", fake_ollama)
    text, info = llm.call_llm("ollama", "hi")
    assert text == "ok"


def test_call_llm_auto_first_succeeds(monkeypatch):
    def fake_ok(prompt, model=None, timeout=60):
        return "ok-output", None

    monkeypatch.setitem(llm._BACKENDS, "ollama", fake_ok)
    text, info = llm.call_llm("auto", "hi")
    assert text == "ok-output"
    assert "ollama" in info


def test_call_llm_auto_falls_through(monkeypatch):
    monkeypatch.setitem(llm._BACKENDS, "ollama", lambda p, model=None, timeout=60: (None, "no ollama"))
    monkeypatch.setitem(llm._BACKENDS, "claude", lambda p, model=None, timeout=60: (None, "no claude"))
    monkeypatch.setitem(llm._BACKENDS, "openai", lambda p, model=None, timeout=60: (None, "no openai"))
    text, err = llm.call_llm("auto", "hi")
    assert text is None
    assert "no LLM backend available" in err


# ---- CLI integration of --llm ----


def test_cli_explain_llm_success(monkeypatch):
    monkeypatch.setattr(
        audit,
        "run_audit",
        lambda names=None, ignore=None: [
            audit.CheckResult("swap", "fail", "99%"),
        ],
    )
    monkeypatch.setattr(main.llm_mod, "call_llm", lambda backend, prompt, model=None, timeout=None: ("diagnosis text", "via ollama"))
    rc, out = _capture(["explain", "--llm", "ollama"])
    assert rc == 0
    assert "diagnosis text" in out


def test_cli_explain_llm_failure(monkeypatch):
    monkeypatch.setattr(
        audit,
        "run_audit",
        lambda names=None, ignore=None: [
            audit.CheckResult("swap", "fail", "99%"),
        ],
    )
    monkeypatch.setattr(main.llm_mod, "call_llm", lambda backend, prompt, model=None, timeout=None: (None, "api error"))
    rc, out = _capture(["explain", "--llm", "claude"])
    assert rc == 2
    assert "api error" in out


def test_cli_explain_llm_json(monkeypatch):
    monkeypatch.setattr(
        audit,
        "run_audit",
        lambda names=None, ignore=None: [
            audit.CheckResult("x", "fail", "y"),
        ],
    )
    monkeypatch.setattr(main.llm_mod, "call_llm", lambda backend, prompt, model=None, timeout=None: ("answer", "via ollama"))
    rc, out = _capture(["explain", "--llm", "ollama", "--format", "json"])
    data = json.loads(out)
    assert data["backend"] == "ollama"
    assert data["advice"] == "answer"


def test_cli_explain_llm_json_error(monkeypatch):
    monkeypatch.setattr(
        audit,
        "run_audit",
        lambda names=None, ignore=None: [
            audit.CheckResult("x", "fail", "y"),
        ],
    )
    monkeypatch.setattr(main.llm_mod, "call_llm", lambda backend, prompt, model=None, timeout=None: (None, "key missing"))
    rc, out = _capture(["explain", "--llm", "openai", "--format", "json"])
    data = json.loads(out)
    assert "error" in data


# ---- HTML output ----


def test_render_html_basic():
    results = [
        audit.CheckResult("uptime", "ok", "3d"),
        audit.CheckResult("swap", "fail", "99%"),
    ]
    out = audit.render_html(results, host="myhost")
    assert "<!doctype html>" in out
    assert "myhost" in out
    assert "uptime" in out
    assert "swap" in out
    assert "background:#d9534f" in out  # fail color
    assert "background:#5cb85c" in out  # ok color


def test_render_html_with_detail():
    r = audit.CheckResult("x", "warn", "msg", detail=["d1", "d2"])
    out = audit.render_html([r])
    assert "<details>" in out
    assert "d1" in out
    assert "d2" in out


def test_render_html_escapes():
    r = audit.CheckResult("disk </boom>", "fail", "<script>alert(1)</script>")
    out = audit.render_html([r])
    # The HTML escape must neutralize the script tag.
    assert "<script>alert(1)" not in out
    assert "&lt;script&gt;" in out


def test_audit_html_via_cli(monkeypatch):
    monkeypatch.setattr(
        audit,
        "run_audit",
        lambda names=None, ignore=None: [
            audit.CheckResult("x", "ok", "y"),
        ],
    )
    rc, out = _capture(["audit", "--format", "html"])
    assert "<!doctype html>" in out
    assert "<table" in out


# ---- --output flag ----


def test_audit_output_to_file(monkeypatch, tmp_path):
    monkeypatch.setattr(
        audit,
        "run_audit",
        lambda names=None, ignore=None: [
            audit.CheckResult("x", "ok", "fine"),
        ],
    )
    target = tmp_path / "audit.txt"
    rc, out = _capture(["audit", "--output", str(target)])
    assert rc == 0
    assert target.exists()
    body = target.read_text()
    assert "AUDIT" in body
    # No ANSI escapes when writing to file.
    assert "\033[" not in body


def test_audit_output_html_file(monkeypatch, tmp_path):
    monkeypatch.setattr(
        audit,
        "run_audit",
        lambda names=None, ignore=None: [
            audit.CheckResult("x", "ok", "fine"),
        ],
    )
    target = tmp_path / "audit.html"
    rc, _ = _capture(["audit", "--format", "html", "--output", str(target)])
    assert rc == 0
    text = target.read_text()
    assert "<!doctype html>" in text


def test_audit_output_unwritable(monkeypatch):
    monkeypatch.setattr(audit, "run_audit", lambda names=None, ignore=None: [audit.CheckResult("x", "ok", "")])
    rc, out = _capture(["audit", "--output", "/nonexistent/dir/x.txt"])
    assert rc == 1
    assert "cannot write" in out


# ---- fail2ban check ----


def test_get_fail2ban_no_binary(monkeypatch):
    monkeypatch.setattr(sysinfo.shutil, "which", lambda _: None)
    assert sysinfo.get_fail2ban_jails() is None


def test_get_fail2ban_daemon_down(monkeypatch):
    monkeypatch.setattr(sysinfo.shutil, "which", lambda _: "/usr/bin/fail2ban-client")
    monkeypatch.setattr(sysinfo, "run", lambda cmd, **_: (1, "", "could not connect"))
    assert sysinfo.get_fail2ban_jails() is None


def test_get_fail2ban_no_jails(monkeypatch):
    monkeypatch.setattr(sysinfo.shutil, "which", lambda _: "/usr/bin/fail2ban-client")
    monkeypatch.setattr(sysinfo, "run", lambda cmd, **_: (0, "Status\n|- Number of jail:\t0\n", ""))
    assert sysinfo.get_fail2ban_jails() == []


def test_get_fail2ban_parses_jails(monkeypatch):
    list_out = "Status\n|- Number of jail:\t2\n`- Jail list:\tsshd, recidive\n"
    sshd_out = "Status for the jail: sshd\n" "|- Currently failed: 3\n" "|- Total failed:     50\n" "`- Currently banned: 2\n" "   Total banned:     17\n"
    recidive_out = "Status for the jail: recidive\n" "`- Currently banned: 0\n" "   Total banned:     5\n"

    def fake_run(cmd, **_):
        if cmd[-1] == "status":
            return (0, list_out, "")
        if cmd[-1] == "sshd":
            return (0, sshd_out, "")
        if cmd[-1] == "recidive":
            return (0, recidive_out, "")
        return (1, "", "")

    monkeypatch.setattr(sysinfo.shutil, "which", lambda _: "/usr/bin/fail2ban-client")
    monkeypatch.setattr(sysinfo, "run", fake_run)
    jails = sysinfo.get_fail2ban_jails()
    assert len(jails) == 2
    by_name = {j["name"]: j for j in jails}
    assert by_name["sshd"]["banned"] == 2
    assert by_name["sshd"]["total"] == 17
    assert by_name["recidive"]["banned"] == 0


def test_get_fail2ban_jail_query_fails(monkeypatch):
    list_out = "Status\n`- Jail list:\tonly_one\n"

    def fake_run(cmd, **_):
        if cmd[-1] == "status":
            return (0, list_out, "")
        return (1, "", "jail not running")

    monkeypatch.setattr(sysinfo.shutil, "which", lambda _: "/usr/bin/fail2ban-client")
    monkeypatch.setattr(sysinfo, "run", fake_run)
    assert sysinfo.get_fail2ban_jails() == []


def test_check_fail2ban_skip(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_fail2ban_jails", lambda: None)
    assert audit._check_fail2ban().status == "skip"


def test_check_fail2ban_no_jails(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_fail2ban_jails", lambda: [])
    r = audit._check_fail2ban()
    assert r.status == "ok"
    assert "no jails" in r.message


def test_check_fail2ban_active(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_fail2ban_jails", lambda: [{"name": "sshd", "banned": 3, "total": 100}])
    r = audit._check_fail2ban()
    assert r.status == "ok"
    assert "3 IP(s)" in r.message


def test_fail2ban_in_registry():
    assert "fail2ban" in audit.list_check_names()
