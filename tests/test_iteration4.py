#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for iteration 4: PSI, kernel taint, cert expiry, wtf logs, parallel exec."""

import io
import json
import time
from contextlib import redirect_stdout

from wtftools import audit, config, main, sysinfo


def _capture(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main.main(argv)
    return rc, buf.getvalue()


# ---- PSI ----

PSI_SAMPLE = """some avg10=0.50 avg60=0.30 avg300=0.10 total=1234
full avg10=0.10 avg60=0.05 avg300=0.01 total=567
"""


def test_get_pressure_parses(monkeypatch):
    monkeypatch.setattr(sysinfo, "read_file", lambda _: PSI_SAMPLE)
    data = sysinfo.get_pressure("memory")
    assert data is not None
    assert data["some"]["avg10"] == 0.5
    assert data["full"]["avg60"] == 0.05


def test_get_pressure_unknown_resource():
    assert sysinfo.get_pressure("garbage") is None


def test_get_pressure_no_file(monkeypatch):
    monkeypatch.setattr(sysinfo, "read_file", lambda _: "")
    assert sysinfo.get_pressure("cpu") is None


def test_get_pressure_malformed(monkeypatch):
    monkeypatch.setattr(sysinfo, "read_file", lambda _: "garbage no =\n")
    assert sysinfo.get_pressure("cpu") is None


def test_check_psi_ok(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_pressure", lambda r: {"some": {"avg10": 0.1}})
    results = audit._check_psi()
    assert len(results) == 3
    assert all(r.status == "ok" for r in results)


def test_check_psi_warn(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_pressure", lambda r: {"some": {"avg10": 15.0}})
    results = audit._check_psi()
    assert all(r.status == "warn" for r in results)


def test_check_psi_fail(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_pressure", lambda r: {"some": {"avg10": 40.0}})
    results = audit._check_psi()
    assert all(r.status == "fail" for r in results)


def test_check_psi_skip(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_pressure", lambda r: None)
    results = audit._check_psi()
    assert all(r.status == "skip" for r in results)


# ---- kernel taint ----


def test_get_kernel_taint_zero(monkeypatch):
    monkeypatch.setattr(sysinfo, "read_file", lambda _: "0\n")
    assert sysinfo.get_kernel_taint() == 0


def test_get_kernel_taint_nonzero(monkeypatch):
    monkeypatch.setattr(sysinfo, "read_file", lambda _: "0x3001\n")
    # int("0x3001") raises — ensure we handle gracefully.
    # Our parser only accepts decimal; this should return None for hex.
    assert sysinfo.get_kernel_taint() is None


def test_get_kernel_taint_decimal(monkeypatch):
    monkeypatch.setattr(sysinfo, "read_file", lambda _: "12289\n")  # 0x3001
    assert sysinfo.get_kernel_taint() == 12289


def test_get_kernel_taint_unparseable(monkeypatch):
    monkeypatch.setattr(sysinfo, "read_file", lambda _: "garbage\n")
    assert sysinfo.get_kernel_taint() is None


def test_get_kernel_taint_empty(monkeypatch):
    monkeypatch.setattr(sysinfo, "read_file", lambda _: "")
    assert sysinfo.get_kernel_taint() is None


def test_decode_kernel_taint():
    flags = sysinfo.decode_kernel_taint(0)
    assert flags == []
    flags = sysinfo.decode_kernel_taint(1)
    assert "PROPRIETARY_MODULE" in flags
    flags = sysinfo.decode_kernel_taint(1 << 4)
    assert "MACHINE_CHECK" in flags


def test_check_kernel_taint_ok(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_kernel_taint", lambda: 0)
    assert audit._check_kernel_taint().status == "ok"


def test_check_kernel_taint_warn(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_kernel_taint", lambda: 1)  # proprietary module
    r = audit._check_kernel_taint()
    assert r.status == "warn"
    assert "PROPRIETARY_MODULE" in r.message


def test_check_kernel_taint_fail_on_machine_check(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_kernel_taint", lambda: 1 << 4)
    r = audit._check_kernel_taint()
    assert r.status == "fail"
    assert "MACHINE_CHECK" in r.message


def test_check_kernel_taint_skip(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_kernel_taint", lambda: None)
    assert audit._check_kernel_taint().status == "skip"


# ---- cert expiry ----


def test_get_cert_expirations_no_openssl(monkeypatch):
    monkeypatch.setattr(sysinfo.shutil, "which", lambda _: None)
    assert sysinfo.get_certificate_expirations() == []


def test_get_cert_expirations_no_dirs(monkeypatch):
    monkeypatch.setattr(sysinfo.shutil, "which", lambda _: "/usr/bin/openssl")
    monkeypatch.setattr(sysinfo.os.path, "isdir", lambda _: False)
    assert sysinfo.get_certificate_expirations() == []


def test_get_cert_expirations_with_files(monkeypatch, tmp_path):
    cert = tmp_path / "fullchain.pem"
    cert.write_text("dummy")

    monkeypatch.setattr(sysinfo.shutil, "which", lambda _: "/usr/bin/openssl")
    # Walk the tmp_path
    monkeypatch.setattr(sysinfo, "_parse_cert_expiry_days", lambda p: 25)
    results = sysinfo.get_certificate_expirations(roots=[str(tmp_path)])
    assert len(results) == 1
    assert results[0]["days_left"] == 25


def test_get_cert_expirations_skips_private_key(monkeypatch, tmp_path):
    (tmp_path / "privkey.pem").write_text("PRIVATE KEY")
    (tmp_path / "fullchain.pem").write_text("cert")

    monkeypatch.setattr(sysinfo.shutil, "which", lambda _: "/usr/bin/openssl")
    monkeypatch.setattr(sysinfo, "_parse_cert_expiry_days", lambda p: 50)
    results = sysinfo.get_certificate_expirations(roots=[str(tmp_path)])
    assert len(results) == 1
    assert "fullchain.pem" in results[0]["path"]


def test_parse_cert_expiry_days_failure(monkeypatch):
    monkeypatch.setattr(sysinfo, "run", lambda cmd, **_: (1, "", ""))
    assert sysinfo._parse_cert_expiry_days("/any/path") is None


def test_parse_cert_expiry_days_parses(monkeypatch):
    # 2 days in the future at the time of running
    from datetime import datetime, timedelta, timezone

    future = (datetime.now(timezone.utc) + timedelta(days=42)).strftime("%b %d %H:%M:%S %Y GMT")
    monkeypatch.setattr(sysinfo, "run", lambda cmd, **_: (0, f"notAfter={future}", ""))
    days = sysinfo._parse_cert_expiry_days("/any")
    assert days is not None
    assert 41 <= days <= 42


def test_parse_cert_expiry_unparseable_date(monkeypatch):
    monkeypatch.setattr(sysinfo, "run", lambda cmd, **_: (0, "notAfter=not-a-date", ""))
    assert sysinfo._parse_cert_expiry_days("/any") is None


def test_check_cert_expiry_states(monkeypatch):
    monkeypatch.setattr(audit.sysinfo, "get_certificate_expirations", lambda: [])
    assert audit._check_cert_expiry().status == "skip"

    monkeypatch.setattr(audit.sysinfo, "get_certificate_expirations", lambda: [{"path": "/x", "days_left": 100}])
    assert audit._check_cert_expiry().status == "ok"

    monkeypatch.setattr(audit.sysinfo, "get_certificate_expirations", lambda: [{"path": "/x", "days_left": 15}])
    assert audit._check_cert_expiry().status == "warn"

    monkeypatch.setattr(audit.sysinfo, "get_certificate_expirations", lambda: [{"path": "/x", "days_left": 3}])
    assert audit._check_cert_expiry().status == "fail"


# ---- wtf logs ----


def test_cmd_logs_no_journalctl(monkeypatch):
    monkeypatch.setattr(main.shutil, "which", lambda _: None)
    rc, out = _capture(["logs"])
    assert rc == 2
    assert "not available" in out


def test_cmd_logs_no_output(monkeypatch):
    monkeypatch.setattr(main.shutil, "which", lambda _: "/bin/journalctl")
    monkeypatch.setattr(sysinfo, "run", lambda cmd, **_: (0, "", ""))
    rc, out = _capture(["logs"])
    assert rc == 0
    assert "(none)" in out


def test_cmd_logs_journalctl_fails(monkeypatch):
    monkeypatch.setattr(main.shutil, "which", lambda _: "/bin/journalctl")
    monkeypatch.setattr(sysinfo, "run", lambda cmd, **_: (1, "", "err"))
    rc, out = _capture(["logs"])
    assert rc == 1


def test_cmd_logs_groups_by_unit(monkeypatch):
    monkeypatch.setattr(main.shutil, "which", lambda _: "/bin/journalctl")
    journal_out = (
        '{"_SYSTEMD_UNIT":"nginx.service","MESSAGE":"connection refused"}\n'
        '{"_SYSTEMD_UNIT":"nginx.service","MESSAGE":"timeout"}\n'
        '{"_SYSTEMD_UNIT":"postgres.service","MESSAGE":"too many clients"}\n'
    )
    monkeypatch.setattr(sysinfo, "run", lambda cmd, **_: (0, journal_out, ""))
    rc, out = _capture(["logs"])
    assert rc == 0
    assert "nginx" in out
    assert "postgres" in out
    assert "timeout" in out
    assert "2 entries" not in out  # we said total = 3 entries
    assert "3 entries" in out


def test_cmd_logs_json(monkeypatch):
    monkeypatch.setattr(main.shutil, "which", lambda _: "/bin/journalctl")
    journal_out = '{"_SYSTEMD_UNIT":"x.service","MESSAGE":"boom"}\n'
    monkeypatch.setattr(sysinfo, "run", lambda cmd, **_: (0, journal_out, ""))
    rc, out = _capture(["logs", "--format", "json"])
    data = json.loads(out)
    assert "by_unit" in data
    assert "x.service" in data["by_unit"]


def test_cmd_logs_message_as_byte_list(monkeypatch):
    """journalctl JSON sometimes emits MESSAGE as a list of byte values for non-UTF8."""
    monkeypatch.setattr(main.shutil, "which", lambda _: "/bin/journalctl")
    payload = json.dumps({"_SYSTEMD_UNIT": "x.service", "MESSAGE": [104, 105]})
    monkeypatch.setattr(sysinfo, "run", lambda cmd, **_: (0, payload + "\n", ""))
    rc, out = _capture(["logs"])
    assert rc == 0
    assert "hi" in out


def test_cmd_logs_malformed_lines_skipped(monkeypatch):
    monkeypatch.setattr(main.shutil, "which", lambda _: "/bin/journalctl")
    out_text = 'not json\n{"_SYSTEMD_UNIT":"good.service","MESSAGE":"ok"}\n'
    monkeypatch.setattr(sysinfo, "run", lambda cmd, **_: (0, out_text, ""))
    rc, out = _capture(["logs"])
    assert rc == 0
    assert "good" in out


# ---- parallel exec / timeout ----


def test_run_funcs_parallel_preserves_order(monkeypatch):
    def make(name):
        return lambda: audit.CheckResult(name, "ok", "x")

    config.set_config(config.Config(parallel_workers=4, check_timeout_seconds=5))
    funcs = [make(f"c{i}") for i in range(6)]
    results = audit._run_funcs(funcs)
    assert [r.name for r in results] == [f"c{i}" for i in range(6)]
    config.set_config(config.Config())


def test_run_funcs_serial_fallback(monkeypatch):
    config.set_config(config.Config(parallel_workers=1))
    funcs = [
        lambda: audit.CheckResult("a", "ok", "x"),
        lambda: audit.CheckResult("b", "ok", "y"),
    ]
    results = audit._run_funcs(funcs)
    assert [r.name for r in results] == ["a", "b"]
    config.set_config(config.Config())


def test_run_funcs_parallel_timeout(monkeypatch):
    config.set_config(config.Config(parallel_workers=4, check_timeout_seconds=0.1))

    def slow():
        time.sleep(1.0)
        return audit.CheckResult("slow", "ok", "x")

    results = audit._run_funcs([slow, slow])
    assert all(r.status == "skip" for r in results)
    assert all("timeout" in r.message for r in results)
    config.set_config(config.Config())


def test_run_funcs_parallel_exception(monkeypatch):
    config.set_config(config.Config(parallel_workers=4, check_timeout_seconds=5))

    def boom():
        raise RuntimeError("kaboom")

    results = audit._run_funcs([boom])
    assert results[0].status == "skip"
    assert "kaboom" in results[0].message
    config.set_config(config.Config())


def test_run_funcs_parallel_list_outcome(monkeypatch):
    config.set_config(config.Config(parallel_workers=4, check_timeout_seconds=5))

    def multi():
        return [audit.CheckResult("a", "ok", "x"), audit.CheckResult("b", "warn", "y")]

    results = audit._run_funcs([multi])
    assert len(results) == 2
    config.set_config(config.Config())


def test_cli_serial_flag(monkeypatch):
    seen = []

    def fake_run(funcs):
        seen.append(config.get_config().parallel_workers)
        return [audit.CheckResult("x", "ok", "")]

    monkeypatch.setattr(audit, "_run_funcs", fake_run)
    _capture(["audit", "--serial", "--check", "uptime"])
    assert seen and seen[0] == 1
    config.set_config(config.Config())


def test_cli_check_timeout_flag(monkeypatch):
    monkeypatch.setattr(audit, "_run_funcs", lambda funcs: [audit.CheckResult("x", "ok", "")])
    _capture(["audit", "--check-timeout", "2.5", "--check", "uptime"])
    assert config.get_config().check_timeout_seconds == 2.5
    config.set_config(config.Config())


# ---- new checks appear in CHECK_REGISTRY ----


def test_new_checks_registered():
    names = audit.list_check_names()
    assert "psi" in names
    assert "kernel-taint" in names
    assert "cert-expiry" in names
