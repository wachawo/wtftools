#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for wtftools.config — INI-driven configuration."""

from wtftools import config


def test_defaults():
    cfg = config.Config()
    assert cfg.disk_warn_pct == 85
    assert cfg.disk_fail_pct == 95
    assert cfg.ignored_checks == set()


def test_load_missing_paths_returns_defaults():
    cfg = config.load_config(["/nonexistent/x.ini", "/nonexistent/y.ini"])
    assert cfg.disk_warn_pct == 85


def test_load_thresholds(tmp_path):
    f = tmp_path / "cfg.ini"
    f.write_text("[thresholds]\n" "disk_warn = 70\n" "disk_fail = 80\n" "swap_warn = 10\n" "load_warn = 0.5\n" "load_fail = 1.5\n" "tcp_retrans_warn = 2\n")
    cfg = config.load_config([str(f)])
    assert cfg.disk_warn_pct == 70
    assert cfg.disk_fail_pct == 80
    assert cfg.swap_warn_pct == 10
    assert cfg.load_warn_ratio == 0.5
    assert cfg.load_fail_ratio == 1.5
    assert cfg.tcp_retrans_warn_pct == 2.0


def test_load_ignore_lists(tmp_path):
    f = tmp_path / "cfg.ini"
    f.write_text("[ignore]\n" "checks = swap, updates\n" "result_names = disk /mnt/Backup, disk /mnt/Video\n")
    cfg = config.load_config([str(f)])
    assert cfg.ignored_checks == {"swap", "updates"}
    assert cfg.ignored_result_names == {"disk /mnt/Backup", "disk /mnt/Video"}


def test_load_ignore_multiline(tmp_path):
    f = tmp_path / "cfg.ini"
    f.write_text("[ignore]\n" "checks =\n" "    swap\n" "    updates\n" "    pids\n")
    cfg = config.load_config([str(f)])
    assert cfg.ignored_checks == {"swap", "updates", "pids"}


def test_load_invalid_value_keeps_default(tmp_path, caplog):
    f = tmp_path / "cfg.ini"
    f.write_text("[thresholds]\ndisk_warn = not-a-number\n")
    cfg = config.load_config([str(f)])
    assert cfg.disk_warn_pct == 85


def test_load_corrupt_file(tmp_path):
    f = tmp_path / "cfg.ini"
    f.write_text("not [valid ini\n=garbage")
    # Should not crash, just return defaults.
    cfg = config.load_config([str(f)])
    assert isinstance(cfg, config.Config)


def test_layered_paths_later_overrides(tmp_path):
    a = tmp_path / "a.ini"
    b = tmp_path / "b.ini"
    a.write_text("[thresholds]\ndisk_warn = 50\n")
    b.write_text("[thresholds]\ndisk_warn = 99\n")
    cfg = config.load_config([str(a), str(b)])
    assert cfg.disk_warn_pct == 99  # configparser: last file wins


def test_get_set_config():
    new_cfg = config.Config(disk_warn_pct=42)
    config.set_config(new_cfg)
    assert config.get_config().disk_warn_pct == 42
    # Restore default for other tests
    config.set_config(config.Config())


def test_example_config_non_empty():
    text = config.example_config()
    assert "[thresholds]" in text
    assert "[ignore]" in text
    assert "disk_warn" in text


def test_coerce_handles_bool(tmp_path):
    # No bool field today, but ensure the path is exercised when one is added.
    cfg = config.Config()
    # Direct exercise of _coerce with a bool sentinel.
    import configparser as cp

    p = cp.ConfigParser()
    p.read_string("[s]\nf = true\n")
    cfg.__dict__["_test_bool"] = False
    config._coerce(p, "s", "f", False, "_test_bool", cfg)
    assert cfg.__dict__["_test_bool"] is True


def test_default_paths_constant():
    assert any("config.ini" in p for p in config.DEFAULT_CONFIG_PATHS)
