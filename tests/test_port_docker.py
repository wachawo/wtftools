#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for `wtf port <N>` and `wtf docker [NAME]`."""

import io
import json
import os
from contextlib import redirect_stdout

from wtftools import main, sysinfo


def _capture(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main.main(argv)
    return rc, buf.getvalue()


# --- sysinfo helpers ---


def test_get_proc_info_self():
    info = sysinfo.get_proc_info(os.getpid())
    assert info["pid"] == os.getpid()
    # The test runner's own exe and cwd are always readable.
    assert info["exe"] and os.path.exists(info["exe"])
    assert info["cwd"] == os.getcwd()
    assert info["user"]


def test_port_map_lsof_parsing(monkeypatch):
    fake = (
        "COMMAND   PID     USER   FD   TYPE DEVICE SIZE/OFF NODE NAME\n"
        "asterisk 4242 asterisk   13u  IPv4  12345      0t0  UDP *:5060\n"
        "asterisk 4242 asterisk   14u  IPv4  12346      0t0  TCP *:5060 (LISTEN)\n"
        "other     999 root        9u  IPv4  10000      0t0  TCP *:80\n"
    )
    monkeypatch.setattr(sysinfo.shutil, "which", lambda name: "/usr/bin/lsof")
    monkeypatch.setattr(sysinfo, "run", lambda cmd, timeout=5: (0, fake, ""))
    entries = sysinfo._port_map_lsof(5060)
    assert len(entries) == 2
    assert {e["proto"] for e in entries} == {"udp", "tcp"}
    listen = [e for e in entries if e["proto"] == "tcp"][0]
    assert listen["pid"] == 4242
    assert listen["user"] == "asterisk"
    assert listen["addr"] == "*:5060"
    assert listen["state"] == "LISTEN"


def test_get_port_processes_enriches_and_falls_back(monkeypatch):
    monkeypatch.setattr(sysinfo, "_port_map_lsof", lambda port: None)
    monkeypatch.setattr(sysinfo, "_port_map_psutil", lambda port: [{"pid": 1, "command": "init", "user": "root", "proto": "tcp", "addr": "*:5060", "state": "LISTEN"}])
    monkeypatch.setattr(sysinfo, "get_proc_info", lambda pid: {"pid": pid, "exe": "/sbin/init", "cwd": "/", "cmdline": "/sbin/init", "user": "root"})
    entries = sysinfo.get_port_processes(5060)
    assert entries[0]["exe"] == "/sbin/init"
    assert entries[0]["cwd"] == "/"


# --- wtf port ---


def test_cmd_port_text(monkeypatch):
    monkeypatch.setattr(
        main.sysinfo,
        "get_port_processes",
        lambda port: [
            {
                "pid": 4242,
                "command": "asterisk",
                "user": "asterisk",
                "proto": "tcp",
                "addr": "*:5060",
                "state": "LISTEN",
                "exe": "/usr/sbin/asterisk",
                "cwd": "/var/lib/asterisk",
                "cmdline": "asterisk -g",
            }
        ],
    )
    rc, out = _capture(["port", "5060"])
    assert rc == 0
    assert "PORT 5060" in out
    assert "4242" in out
    assert "/usr/sbin/asterisk" in out
    assert "/var/lib/asterisk" in out


def test_cmd_port_alias_and_plain(monkeypatch):
    monkeypatch.setattr(
        main.sysinfo,
        "get_port_processes",
        lambda port: [
            {
                "pid": 4242,
                "command": "asterisk",
                "user": "asterisk",
                "proto": "tcp",
                "addr": "*:5060",
                "state": "LISTEN",
                "exe": "/usr/sbin/asterisk",
                "cwd": "/var/lib/asterisk",
                "cmdline": "asterisk -g",
            }
        ],
    )
    rc, out = _capture(["ports", "5060", "--format", "plain"])
    assert rc == 0
    assert out.strip() == "tcp\t*:5060\tLISTEN\t4242\tasterisk\tasterisk\t/usr/sbin/asterisk\t/var/lib/asterisk"


def test_cmd_port_json_and_empty(monkeypatch):
    monkeypatch.setattr(main.sysinfo, "get_port_processes", lambda port: [])
    rc, out = _capture(["port", "5060", "--format", "json"])
    assert rc == 1
    payload = json.loads(out)
    assert payload["schema_version"] == 1
    assert payload["port"] == 5060
    assert payload["processes"] == []


def test_ports_without_arg_still_lists(monkeypatch):
    # No positional → the normal listing path runs, not the drilldown.
    monkeypatch.setattr(main.sysinfo, "get_listening_ports", lambda: [])
    called = {"detail": False}
    monkeypatch.setattr(main, "_cmd_port_detail", lambda args: called.__setitem__("detail", True) or 0)
    rc, out = _capture(["ports", "--format", "json"])
    assert rc == 0
    assert called["detail"] is False


# --- wtf docker ---


def test_cmd_docker_no_docker(monkeypatch):
    monkeypatch.setattr(main.shutil, "which", lambda name: None)
    rc, out = _capture(["docker"])
    assert rc == 2
    assert "docker not available" in out


def test_cmd_docker_name(monkeypatch):
    monkeypatch.setattr(main.shutil, "which", lambda name: "/usr/bin/docker")
    monkeypatch.setattr(
        main.sysinfo,
        "get_docker_container_origin",
        lambda name: {
            "name": "web",
            "image": "nginx",
            "status": "running",
            "compose_project": "proj",
            "compose_service": "web",
            "working_dir": "/srv/proj",
            "config_files": "/srv/proj/docker-compose.yml",
        },
    )
    rc, out = _capture(["docker", "web"])
    assert rc == 0
    assert "proj / web" in out
    assert "/srv/proj" in out
    assert "docker-compose.yml" in out


def test_cmd_docker_name_not_found(monkeypatch):
    monkeypatch.setattr(main.shutil, "which", lambda name: "/usr/bin/docker")
    monkeypatch.setattr(main.sysinfo, "get_docker_container_origin", lambda name: None)
    rc, out = _capture(["docker", "ghost"])
    assert rc == 1
    assert "not found" in out


def test_cmd_docker_list_plain(monkeypatch):
    monkeypatch.setattr(main.shutil, "which", lambda name: "/usr/bin/docker")
    monkeypatch.setattr(
        main.sysinfo,
        "get_docker_containers",
        lambda: [
            {
                "name": "web",
                "image": "nginx",
                "status": "running",
                "compose_project": "proj",
                "compose_service": "web",
                "working_dir": "/srv/proj",
                "config_files": "/srv/proj/docker-compose.yml",
            }
        ],
    )
    rc, out = _capture(["docker", "--format", "plain"])
    assert rc == 0
    assert out.strip() == "web\trunning\tnginx\tproj\tweb\t/srv/proj\t/srv/proj/docker-compose.yml"


def test_cmd_docker_non_compose(monkeypatch):
    monkeypatch.setattr(main.shutil, "which", lambda name: "/usr/bin/docker")
    monkeypatch.setattr(
        main.sysinfo,
        "get_docker_container_origin",
        lambda name: {"name": "solo", "image": "alpine", "status": "running", "compose_project": None, "compose_service": None, "working_dir": None, "config_files": None},
    )
    rc, out = _capture(["docker", "solo"])
    assert rc == 0
    assert "not a compose container" in out


def test_get_docker_container_origin_parses(monkeypatch):
    inspect = json.dumps(
        [
            {
                "Name": "/web",
                "Config": {
                    "Image": "nginx",
                    "Labels": {
                        "com.docker.compose.project": "proj",
                        "com.docker.compose.service": "web",
                        "com.docker.compose.project.working_dir": "/srv/proj",
                        "com.docker.compose.project.config_files": "/srv/proj/docker-compose.yml",
                    },
                },
                "State": {"Status": "running"},
            }
        ]
    )
    monkeypatch.setattr(sysinfo.shutil, "which", lambda name: "/usr/bin/docker")
    monkeypatch.setattr(sysinfo, "run", lambda cmd, timeout=5: (0, inspect, ""))
    info = sysinfo.get_docker_container_origin("web")
    assert info["name"] == "web"
    assert info["working_dir"] == "/srv/proj"
    assert info["compose_project"] == "proj"


def test_cmd_port_text_empty(monkeypatch):
    monkeypatch.setattr(main.sysinfo, "get_port_processes", lambda port: [])
    rc, out = _capture(["port", "5060"])
    assert rc == 1
    assert "nothing is using this port" in out


def test_cmd_docker_list_text(monkeypatch):
    monkeypatch.setattr(main.shutil, "which", lambda name: "/usr/bin/docker")
    monkeypatch.setattr(
        main.sysinfo,
        "get_docker_containers",
        lambda: [
            {"name": "web", "image": "nginx", "status": "running", "compose_project": "p", "compose_service": "web", "working_dir": "/srv/p", "config_files": "/srv/p/dc.yml"},
            {"name": "solo", "image": "alpine", "status": "running", "compose_project": None, "compose_service": None, "working_dir": None, "config_files": None},
        ],
    )
    rc, out = _capture(["docker"])
    assert rc == 0
    assert "DOCKER" in out
    assert "/srv/p" in out
    assert "not compose" in out


def test_cmd_docker_list_empty(monkeypatch):
    monkeypatch.setattr(main.shutil, "which", lambda name: "/usr/bin/docker")
    monkeypatch.setattr(main.sysinfo, "get_docker_containers", lambda: [])
    rc, out = _capture(["docker"])
    assert rc == 0
    assert "no running containers" in out


def test_cmd_docker_list_unreachable(monkeypatch):
    monkeypatch.setattr(main.shutil, "which", lambda name: "/usr/bin/docker")
    monkeypatch.setattr(main.sysinfo, "get_docker_containers", lambda: None)
    rc, out = _capture(["docker"])
    assert rc == 1
    assert "cannot list containers" in out


def test_port_map_lsof_error_returns_none(monkeypatch):
    monkeypatch.setattr(sysinfo.shutil, "which", lambda name: "/usr/bin/lsof")
    monkeypatch.setattr(sysinfo, "run", lambda cmd, timeout=5: (2, "", "boom"))
    assert sysinfo._port_map_lsof(5060) is None


def test_port_map_lsof_absent(monkeypatch):
    monkeypatch.setattr(sysinfo.shutil, "which", lambda name: None)
    assert sysinfo._port_map_lsof(5060) is None


def test_port_map_ss_parsing(monkeypatch):
    line = 'tcp   LISTEN 0 128 0.0.0.0:5060 0.0.0.0:* users:(("asterisk",pid=4242,fd=14))\n'
    monkeypatch.setattr(sysinfo.shutil, "which", lambda name: "/usr/bin/ss")
    monkeypatch.setattr(sysinfo, "run", lambda cmd, timeout=5: (0, line, ""))
    entries = sysinfo._port_map_ss(5060)
    assert entries[0]["pid"] == 4242
    assert entries[0]["command"] == "asterisk"
    assert entries[0]["addr"] == "0.0.0.0:5060"


def test_get_port_processes_no_pid(monkeypatch):
    monkeypatch.setattr(sysinfo, "_port_map_lsof", lambda port: [{"pid": None, "command": "?", "proto": "tcp", "addr": "*:5060", "state": "LISTEN"}])
    entries = sysinfo.get_port_processes(5060)
    assert entries[0]["exe"] is None
    assert entries[0]["cwd"] is None


def test_get_docker_containers_lists(monkeypatch):
    monkeypatch.setattr(sysinfo.shutil, "which", lambda name: "/usr/bin/docker")
    monkeypatch.setattr(sysinfo, "run", lambda cmd, timeout=5: (0, "web\n", ""))
    monkeypatch.setattr(sysinfo, "get_docker_container_origin", lambda name: {"name": name, "working_dir": "/srv/p"})
    result = sysinfo.get_docker_containers()
    assert result == [{"name": "web", "working_dir": "/srv/p"}]
