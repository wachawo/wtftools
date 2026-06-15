#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the redesigned `wtf disk <path>` folder-usage breakdown."""

import io
import json
from contextlib import redirect_stdout

from wtftools import main, sections, sysinfo

# Synthetic du map rooted at "/".
MAP = {
    "/": 1000,
    "/home": 800,
    "/home/wachawo": 800,
    "/home/wachawo/myApps": 400,
    "/home/wachawo/vEnv": 300,
    "/usr": 150,
    "/var": 50,
}


def _capture(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main.main(argv)
    return rc, buf.getvalue()


# --- get_du_map ---


def test_get_du_map_parses(monkeypatch):
    out = "200\t/data/a\n500\t/data/b\n700\t/data\nbroken line\n"
    monkeypatch.setattr(sysinfo.shutil, "which", lambda name: "/usr/bin/du")
    monkeypatch.setattr(sysinfo.os.path, "isdir", lambda p: True)
    monkeypatch.setattr(sysinfo, "run", lambda cmd, timeout=120: (0, out, ""))
    sizes = sysinfo.get_du_map("/data", max_depth=2)
    assert sizes == {"/data/a": 200, "/data/b": 500, "/data": 700}


def test_get_du_map_empty_on_timeout(monkeypatch):
    monkeypatch.setattr(sysinfo.shutil, "which", lambda name: "/usr/bin/du")
    monkeypatch.setattr(sysinfo.os.path, "isdir", lambda p: True)
    monkeypatch.setattr(sysinfo, "run", lambda cmd, timeout=120: (124, "", "timeout"))
    assert sysinfo.get_du_map("/data") == {}


# --- collect_disk_usage ---


def test_collect_usage_flat(monkeypatch):
    monkeypatch.setattr(sections.sysinfo, "get_du_map", lambda root, max_depth=1: dict(MAP))
    data = sections.collect_disk_usage("/", tree=0)
    assert data["root"] == "/"
    assert data["total_bytes"] == 1000
    # Flat: only immediate children, sorted desc, all depth 0.
    assert [e["rel"] for e in data["entries"]] == ["home/", "usr/", "var/"]
    assert all(e["depth"] == 0 for e in data["entries"])
    home = data["entries"][0]
    assert home["path"] == "/home"
    assert home["percent"] == 80  # 800 / 1000


def test_collect_usage_tree_single_chain(monkeypatch):
    monkeypatch.setattr(sections.sysinfo, "get_du_map", lambda root, max_depth=1: dict(MAP))
    data = sections.collect_disk_usage("/", tree=1, depth=3)
    rels = [(e["depth"], e["rel"]) for e in data["entries"]]
    # Largest folder expanded as a single chain; siblings stay flat.
    assert rels == [
        (0, "home/"),
        (1, "home/wachawo/"),
        (2, "home/wachawo/myApps/"),
        (0, "usr/"),
        (0, "var/"),
    ]


def test_collect_usage_tree_top_n_per_level(monkeypatch):
    monkeypatch.setattr(sections.sysinfo, "get_du_map", lambda root, max_depth=1: dict(MAP))
    data = sections.collect_disk_usage("/", tree=2, depth=3)
    rels = [(e["depth"], e["rel"]) for e in data["entries"]]
    # depth 2 now shows the top-2 children of wachawo (myApps, vEnv).
    assert (2, "home/wachawo/myApps/") in rels
    assert (2, "home/wachawo/vEnv/") in rels


def test_collect_usage_top_cap(monkeypatch):
    monkeypatch.setattr(sections.sysinfo, "get_du_map", lambda root, max_depth=1: dict(MAP))
    data = sections.collect_disk_usage("/", tree=0, top=1)
    assert [e["rel"] for e in data["entries"]] == ["home/"]


def test_collect_usage_empty(monkeypatch):
    monkeypatch.setattr(sections.sysinfo, "get_du_map", lambda root, max_depth=1: {})
    data = sections.collect_disk_usage("/data")
    assert data["entries"] == []
    assert data["total_bytes"] == 0


# --- renderers ---


def test_render_usage_text(monkeypatch):
    monkeypatch.setattr(sections.sysinfo, "get_du_map", lambda root, max_depth=1: dict(MAP))
    text = sections.render_disk_usage_text(sections.collect_disk_usage("/", tree=1))
    assert "# DISK USAGE /" in text
    assert "home/" in text
    # depth-index is now the last column on each row.
    myapps = [ln for ln in text.splitlines() if "home/wachawo/myApps/" in ln][0]
    assert myapps.rstrip().endswith("2")
    assert "─" not in text  # no box-drawing


def test_render_usage_text_empty():
    text = sections.render_disk_usage_text({"root": "/data", "entries": []})
    assert "nothing to show" in text


def test_render_usage_plain(monkeypatch):
    monkeypatch.setattr(sections.sysinfo, "get_du_map", lambda root, max_depth=1: dict(MAP))
    plain = sections.render_disk_usage_plain(sections.collect_disk_usage("/", tree=0))
    first = plain.splitlines()[0]
    # bytes<TAB>percent<TAB>abspath<TAB>depth (index last)
    assert first == "800\t80\t/home\t0"


# --- cmd_disk dispatch ---


def test_cmd_disk_no_path_is_mount_overview(monkeypatch):
    called = {"mounts": False, "usage": False}
    monkeypatch.setattr(main.sections_mod, "collect_disk", lambda: called.__setitem__("mounts", True) or {"schema_version": 1, "mounts": []})
    monkeypatch.setattr(main.sections_mod, "collect_disk_usage", lambda *a, **k: called.__setitem__("usage", True) or {})
    rc, out = _capture(["disk"])
    assert rc == 0
    assert called["mounts"] is True
    assert called["usage"] is False


def test_cmd_disk_path_is_usage(monkeypatch):
    monkeypatch.setattr(main.os.path, "isdir", lambda p: True)
    monkeypatch.setattr(
        main.sections_mod,
        "collect_disk_usage",
        lambda root, tree=0, depth=3, top=0: {
            "schema_version": 1,
            "root": root,
            "total_bytes": 1000,
            "depth": depth,
            "tree": tree,
            "entries": [{"depth": 0, "path": "/home/x", "rel": "x/", "bytes": 500, "percent": 50}],
        },
    )
    rc, out = _capture(["disk", "/home"])
    assert rc == 0
    assert "DISK USAGE /home" in out
    assert "x/" in out


def test_cmd_disk_bad_path(monkeypatch):
    monkeypatch.setattr(main.os.path, "isdir", lambda p: False)
    rc, out = _capture(["disk", "/nope"])
    assert rc == 2
    assert "not a directory" in out


def test_cmd_disk_json_schema(monkeypatch):
    monkeypatch.setattr(main.os.path, "isdir", lambda p: True)
    monkeypatch.setattr(
        main.sections_mod,
        "collect_disk_usage",
        lambda root, tree=0, depth=3, top=0: {"schema_version": 1, "root": root, "total_bytes": 0, "depth": depth, "tree": tree, "entries": []},
    )
    rc, out = _capture(["disk", "/home", "--format", "json"])
    assert rc == 0
    payload = json.loads(out)
    assert payload["schema_version"] == 1
    assert payload["root"] == "/home"


def test_cmd_disk_tree_without_path_uses_fullest_mount(monkeypatch):
    monkeypatch.setattr(main.sections_mod, "pick_fullest_mount", lambda: "/var")
    monkeypatch.setattr(main.os.path, "isdir", lambda p: True)
    seen = {}
    monkeypatch.setattr(
        main.sections_mod,
        "collect_disk_usage",
        lambda root, tree=0, depth=3, top=0: seen.update(root=root, tree=tree)
        or {"schema_version": 1, "root": root, "total_bytes": 0, "depth": depth, "tree": tree, "entries": []},
    )
    rc, out = _capture(["disk", "--tree", "2"])
    assert rc == 0
    assert seen == {"root": "/var", "tree": 2}
