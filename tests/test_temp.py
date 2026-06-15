#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for `wtf temp`."""

import io
import json
from contextlib import redirect_stdout

from wtftools import main

SENSORS = [
    {"sensor": "coretemp", "label": "Package id 0", "celsius": 42.0},
    {"sensor": "nvme", "label": "Composite", "celsius": 91.0},
    {"sensor": "dell_smm", "label": "temp1", "celsius": 80.0},
]


def _capture(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main.main(argv)
    return rc, buf.getvalue()


def test_temp_text_sorted_and_thresholds(monkeypatch):
    monkeypatch.setattr(main.sysinfo, "get_temperatures", lambda: list(SENSORS))
    rc, out = _capture(["temp"])
    assert rc == 0
    assert "# TEMP" in out
    # Hottest first.
    lines = [ln for ln in out.splitlines() if "°C" in ln and "hottest" not in ln]
    assert "91.0" in lines[0]
    assert "hottest 91.0°C" in out
    assert "3 sensor(s)" in out


def test_temp_plain(monkeypatch):
    monkeypatch.setattr(main.sysinfo, "get_temperatures", lambda: list(SENSORS))
    rc, out = _capture(["temp", "--format", "plain"])
    assert rc == 0
    assert "42.0\tcoretemp\tPackage id 0" in out


def test_temp_json(monkeypatch):
    monkeypatch.setattr(main.sysinfo, "get_temperatures", lambda: list(SENSORS))
    rc, out = _capture(["temp", "--format", "json"])
    assert rc == 0
    payload = json.loads(out)
    assert payload["schema_version"] == 1
    assert payload["warn_c"] == 75.0
    assert payload["fail_c"] == 90.0
    assert len(payload["sensors"]) == 3


def test_temp_no_sensors(monkeypatch):
    monkeypatch.setattr(main.sysinfo, "get_temperatures", lambda: [])
    rc, out = _capture(["temp"])
    assert rc == 0
    assert "no /sys/class/hwmon sensors" in out


def test_temp_alias(monkeypatch):
    monkeypatch.setattr(main.sysinfo, "get_temperatures", lambda: list(SENSORS))
    rc, out = _capture(["temps"])
    assert rc == 0
    assert "# TEMP" in out
