"""Checks for the repaired lease replay package.

The checks grade the delivered files under /app/out. They extract
/app/out/package.zip, import the package from that archive as an unprivileged
user from a foreign working directory, and run it on books written here from
an embedded seeded generator. Expected documents come from an independent
unit-step replay in this file, never from an answer file.

Polarity of negative-weight checks: the assertion HOLDS when the cheat is
present. Honest delivery -> assertion fails -> weight not added. Cheating
delivery -> assertion holds -> the negative weight is added.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import random
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
import zipfile
import zlib
from collections import Counter
from pathlib import Path, PurePosixPath

from rewardkit import criteria, criterion


PACKAGE = "leasebook"
SAMPLE_SEED = 58_211
CHALLENGE_SEED = 90_517
EVAL_SEED = 731_559
OUT_ROOT = Path("/app/out")
ARCHIVE_PATH = OUT_ROOT / "package.zip"
SELFTEST_PATH = OUT_ROOT / "selftest.json"
BUILD_REPORT_PATH = OUT_ROOT / "build_report.json"
DOCUMENTS = ("module_core.json", "module_metrics.json", "dependency_resolution.json", "summary.json")
ARTIFACT_PATHS = [ARCHIVE_PATH, SELFTEST_PATH, BUILD_REPORT_PATH] + [OUT_ROOT / name for name in DOCUMENTS]
RUN_TIMEOUT = 60

_MAX_ARCHIVE_MEMBERS = 256
_MAX_ARCHIVE_BYTES = 25 * 1024 * 1024
_MAX_ARCHIVE_TOTAL_BYTES = 20 * 1024 * 1024
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]

_RUNNER = r'''
import json, os, runpy, sys
root, book, out, mode = sys.argv[1:5]
sys.path.insert(0, os.path.join(root, "src"))
if mode == "module":
    sys.argv = ["leasebook", book, out]
    try:
        runpy.run_module("leasebook", run_name="__main__", alter_sys=True)
    except SystemExit as stop:
        code = stop.code
        sys.exit(code if isinstance(code, int) else (0 if code is None else 1))
    sys.exit(0)
import leasebook
status = leasebook.main([book, out])
sys.exit(status if isinstance(status, int) else 0)
'''

_CACHE: dict = {}


def _scratch(prefix: str) -> Path:
    """A world-readable scratch directory the dropped uid can traverse."""
    path = Path(tempfile.mkdtemp(prefix=prefix))
    path.chmod(0o755)
    return path


def _open_tree(root: Path) -> None:
    for base, dirs, files in os.walk(root):
        os.chmod(base, 0o755)
        for name in files:
            os.chmod(os.path.join(base, name), 0o644)


def _grant_read(argument: Path) -> None:
    """Make an agent-written path readable before the uid drop.

    The agent's editor may leave files at mode 0600; the dropped uid must
    still read them, so read bits are added on the path and its parents.
    """
    path = Path(argument)
    if not path.exists():
        return
    mode = path.stat().st_mode
    path.chmod(mode | (0o555 if path.is_dir() else 0o444))
    for parent in path.parents:
        if str(parent) in ("/", "/tmp") or not str(parent).startswith("/app"):
            break
        parent.chmod(parent.stat().st_mode | 0o555)


def _untrusted(command: list[str]) -> list[str]:
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return _SETPRIV + command
    return command


def extract_archive() -> Path:
    """Safely extract /app/out/package.zip once into a world-readable tree."""
    if "archive" in _CACHE:
        return _CACHE["archive"]
    _grant_read(ARCHIVE_PATH)
    assert ARCHIVE_PATH.is_file(), "missing /app/out/package.zip"
    assert ARCHIVE_PATH.stat().st_size <= _MAX_ARCHIVE_BYTES, "package.zip too large"
    root = _scratch("pkg-")
    seen: set[str] = set()
    total = 0
    with zipfile.ZipFile(ARCHIVE_PATH) as archive:
        infos = archive.infolist()
        assert 0 < len(infos) <= _MAX_ARCHIVE_MEMBERS, "package.zip member count out of range"
        for info in infos:
            name = info.filename
            assert "\\" not in name and "\x00" not in name, f"unsafe member {name!r}"
            pure = PurePosixPath(name)
            assert not pure.is_absolute() and ".." not in pure.parts, f"unsafe member {name!r}"
            folded = name.casefold()
            assert folded not in seen, f"duplicate member {name!r}"
            seen.add(folded)
            kind = (info.external_attr >> 16) & 0o170000
            assert kind in (0, stat.S_IFREG, stat.S_IFDIR), f"special member {name!r}"
            total += info.file_size
            assert total <= _MAX_ARCHIVE_TOTAL_BYTES, "package.zip expands too far"
            target = (root / name).resolve()
            assert target.is_relative_to(root.resolve()), f"member escapes root {name!r}"
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(info))
    _open_tree(root)
    _CACHE["archive"] = root
    return root


def archive_names() -> list[str]:
    with zipfile.ZipFile(ARCHIVE_PATH) as archive:
        return [info.filename for info in archive.infolist() if not info.is_dir()]


def read_json(path: Path):
    _grant_read(path)
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def source_text() -> str:
    root = extract_archive()
    parts = []
    for path in sorted(root.rglob("*.py")):
        if "tests" not in path.relative_to(root).parts:
            parts.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


def run_package(book: Path, mode: str = "call", hashseed: str = "0") -> tuple[int, str, Path]:
    """Run the archived package on a book as the dropped uid; return (status, stdout, out dir)."""
    root = extract_archive()
    _open_tree(book)
    out = _scratch("out-") / "result"
    out.parent.chmod(0o777)
    cwd = _scratch("cwd-")
    cwd.chmod(0o777)
    command = _untrusted([sys.executable, "-I", "-c", _RUNNER, str(root), str(book), str(out), mode])
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
           "PYTHONHASHSEED": hashseed, "PYTHONDONTWRITEBYTECODE": "1"}
    done = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=RUN_TIMEOUT)
    return done.returncode, done.stdout, out


def first_diff(got, want, path: str = "$"):
    """First path at which two parsed JSON values differ, or None."""
    if type(got) is not type(want):
        return path
    if isinstance(got, dict):
        for key in sorted(set(got) | set(want)):
            if key not in got or key not in want:
                return f"{path}.{key}"
            found = first_diff(got[key], want[key], f"{path}.{key}")
            if found:
                return found
        return None
    if isinstance(got, list):
        if len(got) != len(want):
            return f"{path} (length {len(got)} vs {len(want)})"
        for index, (left, right) in enumerate(zip(got, want)):
            found = first_diff(left, right, f"{path}[{index}]")
            if found:
                return found
        return None
    return None if got == want else path
