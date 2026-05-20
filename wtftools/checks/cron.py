#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Crontab checking — vendored from checkcrontab, trimmed for wtftools."""

import logging
import os
import platform
import re
import stat
import subprocess
import tempfile
import traceback
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

RANGE_PARTS_COUNT = 2
CRONTAB_PERMISSIONS = 0o644
CRONTAB_OWNER_UID = int(os.getenv("CRONTAB_OWNER_UID", "0"))
USER_CRONTAB_MIN_FIELDS = 6
SYSTEM_CRONTAB_MIN_FIELDS = 7
SYSTEM_CRONTAB_MAX_FIELDS = 7
SPECIAL_KEYWORD_MIN_FIELDS = 2
SYSTEM_SPECIAL_MIN_FIELDS = 3

MINUTE_PATTERN = r"^(\*|([0-5]?[0-9])(-([0-5]?[0-9]))?(/([0-9]+))?(,([0-5]?[0-9])(-([0-5]?[0-9]))?(/([0-9]+))?)*|\*/([0-9]+))$"
HOUR_PATTERN = r"^(\*|([0-9]|1[0-9]|2[0-3])(-([0-9]|1[0-9]|2[0-3]))?(/([0-9]|1[0-9]|2[0-3]))?(,([0-9]|1[0-9]|2[0-3])(-([0-9]|1[0-9]|2[0-3]))?(/([0-9]|1[0-9]|2[0-3]))?)*|\*/([0-9]|1[0-9]|2[0-3]))$"
DAY_PATTERN = r"^(\*|([1-9]|[12][0-9]|3[01])(-([1-9]|[12][0-9]|3[01]))?(/([1-9]|[12][0-9]|3[01]))?(,([1-9]|[12][0-9]|3[01])(-([1-9]|[12][0-9]|3[01]))?(/([1-9]|[12][0-9]|3[01]))?)*|\*/([1-9]|[12][0-9]|3[01]))$"
MONTH_PATTERN = r"^(\*|([1-9]|1[0-2])(-([1-9]|1[0-2]))?(/([1-9]|1[0-2]))?(,([1-9]|1[0-2])(-([1-9]|1[0-2]))?(/([1-9]|1[0-2]))?)*|\*/([1-9]|1[0-2]))$"
WEEKDAY_PATTERN = r"^(\*|([0-7])(-([0-7]))?(/([0-7]))?(,([0-7])(-([0-7]))?)*|\*/([0-7]))$"
INVALID_NAME_ALLOWED_RE = r"^[A-Za-z0-9_-]+$"

VALID_KEYWORDS = ["@reboot", "@yearly", "@annually", "@monthly", "@weekly", "@daily", "@midnight", "@hourly"]

DANGEROUS_PATTERNS = [
    (r"\brm\s+-rf\s+/", "dangerous command: 'rm -rf /'"),
    (r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;", "dangerous fork bomb"),
    (r"\bmkfs\.\w+\s+/dev/", "dangerous: filesystem creation"),
    (r"\bdd\s+if=.*\s+of=/dev/(sd|nvme|hd)", "dangerous: dd to raw disk"),
]


def check_filename(file_path: str) -> str:
    name = os.path.basename(file_path or "")
    if not name:
        return f"{file_path} empty name filename"
    if name.startswith("."):
        return f"{name} wrong filename: starts with '.'"
    if name.endswith("~"):
        return f"{name} wrong filename: ends with '~'"
    if "." in name:
        return f"{name} wrong filename contains '.'"
    if "#" in name:
        return f"{name} wrong filename contains '#'"
    if "," in name:
        return f"{name} wrong filename contains ','"
    if not re.match(INVALID_NAME_ALLOWED_RE, name):
        return f"invalid filename '{name}': contains characters outside [A-Za-z0-9_-]"
    return ""


def check_daemon() -> List[str]:
    errors: List[str] = []
    try:
        result = subprocess.run(["systemctl", "is-active", "cron"], capture_output=True, text=True, timeout=5, check=False)
        if result.returncode != 0 or result.stdout.strip() != "active":
            result2 = subprocess.run(["systemctl", "is-active", "crond"], capture_output=True, text=True, timeout=5, check=False)
            if result2.returncode != 0 or result2.stdout.strip() != "active":
                errors.append("cron daemon is not active")
    except FileNotFoundError:
        errors.append("systemctl not found")
    except Exception as exc:
        errors.append(f"cron daemon check failed: {type(exc).__name__}")
    return errors


def check_kind(path: str, follow_symlink: bool = True) -> str:
    st = os.stat(path) if follow_symlink else os.lstat(path)
    m = st.st_mode
    if stat.S_ISREG(m):
        return "regular_file"
    if stat.S_ISDIR(m):
        return "directory"
    if stat.S_ISLNK(m):
        return "symlink"
    if stat.S_ISCHR(m):
        return "char_device"
    if stat.S_ISBLK(m):
        return "block_device"
    if stat.S_ISSOCK(m):
        return "socket"
    if stat.S_ISFIFO(m):
        return "fifo"
    return "unknown"


def check_owner_and_permissions(file_path: str, owner_uid: int = CRONTAB_OWNER_UID) -> List[str]:
    errors: List[str] = []
    if not os.path.lexists(file_path):
        return [f"{file_path}: file does not exist"]
    try:
        if os.path.islink(file_path):
            link_stat = os.lstat(file_path)
            if link_stat.st_uid != owner_uid:
                errors.append(f"wrong symlink owner: sudo chown -h root:root {file_path}")
            target_path = os.path.realpath(file_path)
            if not os.path.exists(target_path):
                errors.append(f"broken symlink ({target_path} does not exist)")
                return errors
        else:
            target_path = file_path
        kind = check_kind(target_path)
        if kind != "regular_file":
            errors.append(f"{target_path}({kind}): not a regular_file.")
        stat_info = os.stat(target_path)
        mode = stat_info.st_mode & 0o777
        if mode != CRONTAB_PERMISSIONS:
            errors.append(f"wrong permissions ({oct(mode)}): sudo chmod 644 {target_path}")
        if stat_info.st_uid != owner_uid:
            errors.append(f"wrong owner: sudo chown root:root {target_path}")
    except Exception as exc:
        errors.append(f"{exc}")
    return errors


def get_line_content(file_path: str, line_number: int) -> str:
    try:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
            if 1 <= line_number <= len(lines):
                return lines[line_number - 1].rstrip("\n")
    except Exception as exc:
        logger.debug(f"{type(exc).__name__}: {exc}")
    return ""


def clean_line_for_output(line: str) -> str:
    return re.sub(r" +", " ", line.replace("\t", " "))


def check_dangerous_commands(command: str) -> List[str]:
    for pattern, message in DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return [message]
    return []


def validate_single_time_value(value: str, field_name: str, min_val: int, max_val: int) -> List[str]:
    errors: List[str] = []
    if value.startswith("*/"):
        step_part = value[2:]
        if step_part.isdigit():
            step_val = int(step_part)
            if step_val <= 0:
                errors.append(f"step value must be positive in {field_name}: '{value}'")
            if step_val > max_val:
                errors.append(f"step value {step_val} exceeds maximum {max_val} for {field_name}: '{value}'")
        else:
            errors.append(f"invalid step value in {field_name}: '{value}'")
        return errors
    if "-" in value:
        range_parts = value.split("-")
        if len(range_parts) == RANGE_PARTS_COUNT:
            start_str, end_str = range_parts
            if start_str.isdigit() and end_str.isdigit():
                start_val = int(start_str)
                end_val = int(end_str)
                if start_val > end_val:
                    errors.append(f"invalid range {start_val}-{end_val} in {field_name}: start > end")
                if start_val < min_val or start_val > max_val:
                    errors.append(f"range start {start_val} out of bounds ({min_val}-{max_val}) for {field_name}")
                if end_val < min_val or end_val > max_val:
                    errors.append(f"range end {end_val} out of bounds ({min_val}-{max_val}) for {field_name}")
        return errors
    if value.isdigit():
        num_val = int(value)
        if num_val < min_val or num_val > max_val:
            errors.append(f"value {num_val} out of bounds ({min_val}-{max_val}) for {field_name}")
    return errors


def validate_time_field_logic(value: str, field_name: str, min_val: int, max_val: int) -> List[str]:
    errors: List[str] = []
    if value == "*":
        return errors
    if "," in value:
        seen = set()
        for part in value.split(","):
            part = part.strip()
            if not part:
                errors.append(f"empty value in {field_name} list: '{value}'")
                continue
            if part in seen:
                errors.append(f"duplicate value '{part}' in {field_name} list: '{value}'")
            seen.add(part)
            errors.extend(validate_single_time_value(part, field_name, min_val, max_val))
    else:
        errors.extend(validate_single_time_value(value, field_name, min_val, max_val))
    return errors


def check_time_field(value: str, field_name: str, pattern: str, min_val: int, max_val: int) -> List[str]:
    logic_errors = validate_time_field_logic(value, field_name, min_val, max_val)
    if logic_errors:
        return logic_errors
    if not re.match(pattern, value):
        return [f"invalid {field_name} format: '{value}'"]
    return []


def check_user_exists(username: str) -> bool:
    if username in ("root",):
        return True
    try:
        result = subprocess.run(["id", username], capture_output=True, text=True, timeout=5, check=False)
        return result.returncode == 0
    except Exception:
        return True


def check_user(username: str) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []
    if not username or username.startswith("#") or '"' in username or "@" in username or " " in username \
            or not re.match(r"^[a-zA-Z][a-zA-Z0-9_-]{0,31}$", username):
        errors.append(f"invalid user format: '{username}'")
    elif platform.system().lower() != "windows" and not check_user_exists(username):
        warnings.append(f"user does not exist: '{username}'")
    return errors, warnings


def check_command(command: str) -> List[str]:
    if not command:
        return ["missing command"]
    return check_dangerous_commands(command)


def check_special(keyword: str, parts: List[str], is_system_crontab: bool) -> List[str]:
    errors: List[str] = []
    if keyword not in VALID_KEYWORDS:
        return [f"invalid special keyword '{keyword}'"]
    if is_system_crontab:
        if len(parts) < SYSTEM_SPECIAL_MIN_FIELDS:
            return [f"minimum {SYSTEM_SPECIAL_MIN_FIELDS} fields required for system crontab"]
        user_errors, _ = check_user(parts[1])
        errors.extend(user_errors)
        errors.extend(check_command(" ".join(parts[2:])))
    elif len(parts) > 1:
        errors.extend(check_command(" ".join(parts[1:])))
    else:
        errors.append("minimum 2 fields required for user crontab")
    return errors


def check_line(line: str, line_number: int, file_name: str, file_path: Optional[str] = None,
               is_system_crontab: bool = False) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []

    if "=" in line and not any(ch.isdigit() or ch in "*@" for ch in line.split("=")[0]):
        return errors, warnings

    line_content = get_line_content(file_path, line_number) if file_path else line
    line_content = clean_line_for_output(line_content)

    def wrap(items: List[str]) -> List[str]:
        return [f"{file_name} (Line {line_number}): {line_content} # {e}" for e in items]

    if line.startswith("@"):
        parts = line.split()
        if len(parts) < SPECIAL_KEYWORD_MIN_FIELDS:
            return wrap([f"insufficient fields for special keyword (minimum {SPECIAL_KEYWORD_MIN_FIELDS})"]), []
        errors.extend(check_special(parts[0], parts, is_system_crontab))
        return wrap(errors), wrap(warnings)

    parts = line.split()
    min_fields = SYSTEM_CRONTAB_MIN_FIELDS if is_system_crontab else USER_CRONTAB_MIN_FIELDS
    if len(parts) < min_fields:
        return wrap([f"insufficient fields (minimum {min_fields}, found {len(parts)})"]), []

    minute, hour, day, month, weekday = parts[:5]

    if is_system_crontab:
        user = parts[5]
        command = " ".join(parts[6:])
        user_errors, user_warnings = check_user(user)
        errors.extend(user_errors)
        warnings.extend(user_warnings)
    else:
        command = " ".join(parts[5:])

    errors.extend(check_command(command))
    errors.extend(check_time_field(minute, "minutes", MINUTE_PATTERN, 0, 59))
    errors.extend(check_time_field(hour, "hours", HOUR_PATTERN, 0, 23))
    errors.extend(check_time_field(day, "day of month", DAY_PATTERN, 1, 31))
    errors.extend(check_time_field(month, "month", MONTH_PATTERN, 1, 12))
    errors.extend(check_time_field(weekday, "day of week", WEEKDAY_PATTERN, 0, 7))

    return wrap(errors), wrap(warnings)


def get_crontab(username: str) -> Optional[str]:
    try:
        result = subprocess.run(["crontab", "-l", "-u", username], capture_output=True, text=True, timeout=10, check=False)
        if result.returncode == 0:
            return result.stdout
        return None
    except Exception as exc:
        logger.debug(f"{type(exc).__name__}: {exc}")
        return None


def check_file(file_path: str, is_system_crontab: bool = False) -> Tuple[int, List[str], List[str]]:
    """Check a single crontab file. Returns (rows_checked, errors, warnings)."""
    errors: List[str] = []
    warnings: List[str] = []
    rows_checked = 0
    try:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception as exc:
        logger.warning(f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}")
        return 0, [f"{file_path}: cannot read ({exc})"], []

    i = 0
    while i < len(lines):
        line = lines[i].rstrip("\n")
        line_number = i + 1
        if line.endswith("\\"):
            full_line = line[:-1]
            i += 1
            while i < len(lines) and lines[i].startswith((" ", "\t")):
                cont = lines[i].rstrip("\n")
                if cont.endswith("\\"):
                    full_line += "\n" + cont[:-1]
                    i += 1
                else:
                    full_line += "\n" + cont
                    i += 1
                    break
            line = full_line
        else:
            i += 1
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        rows_checked += 1
        line_errors, line_warnings = check_line(line, line_number, os.path.basename(file_path), file_path, is_system_crontab)
        errors.extend(line_errors)
        warnings.extend(line_warnings)
    return rows_checked, errors, warnings


def find_user_crontab(username: str) -> Optional[str]:
    candidates = [
        f"/var/spool/cron/crontabs/{username}",
        f"/var/spool/cron/{username}",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    content = get_crontab(username)
    if content:
        with tempfile.NamedTemporaryFile(mode="w", suffix=f".{username}", delete=False) as tmp:
            tmp.write(content)
            return tmp.name
    return None


def discover_default_targets() -> List[Tuple[str, bool]]:
    """Find typical crontab locations on the system."""
    targets: List[Tuple[str, bool]] = []
    if os.path.exists("/etc/crontab"):
        targets.append(("/etc/crontab", True))
    cron_d = "/etc/cron.d"
    if os.path.isdir(cron_d):
        for name in sorted(os.listdir(cron_d)):
            path = os.path.join(cron_d, name)
            if os.path.isfile(path) and not check_filename(name):
                targets.append((path, True))
    user_spool = "/var/spool/cron/crontabs"
    if os.path.isdir(user_spool):
        try:
            for name in sorted(os.listdir(user_spool)):
                path = os.path.join(user_spool, name)
                if os.path.isfile(path):
                    targets.append((path, False))
        except PermissionError:
            pass
    return targets
