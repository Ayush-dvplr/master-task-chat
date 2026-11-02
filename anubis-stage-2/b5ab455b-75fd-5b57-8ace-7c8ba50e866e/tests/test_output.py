"""Deterministic channel for the task-ctl configuration task.

Every check returns a bool and never raises: missing, malformed or hostile agent output
makes a check return False. Checks that run the delivered tool unpack the delivered
archive into a directory the verifier owns, run it as an unprivileged user under a
timeout, and hand it inputs the checks write themselves, so the tool is exercised on
configurations other than the shipped one. Negative checks are named negative_<cheat>,
hold only when the cheat is present, and carry a negative weight.
"""

from __future__ import annotations

import ast
import functools
import hashlib
import io
import json
import os
import signal
import stat
import subprocess
import sys
import tempfile
import zipfile
import zlib
from contextlib import suppress
from pathlib import Path
from typing import Any

from rewardkit import criteria, criterion

ARTIFACT_NAMES = [
    "config.json",
    "report.json",
    "tool.zip",
    "profile_dev.json",
    "profile_prod.json",
    "validation_report.json",
    "summary.json",
]
MAX_ARTIFACT_BYTES = 1024 * 1024
TOOL_NAME = "task-ctl"
SEAL_HEAD = "harbor:cli-config"
NUMBER_FIELDS = ("max_records", "retry_limit", "timeout_ms")
IDENTITY_FIELDS = ("profile", "producer", "container", "checksum", "mode")
DOCUMENT_FIELDS = IDENTITY_FIELDS + NUMBER_FIELDS + ("trailer",)
REPORT_FIELDS = ("ok", "tool", "config_path", "config_sha256", "trailer", "commands", "repairs")
TRANSCRIPT_ORDER = ("init", "set", "set", "set", "seal", "validate", "export-report")
PATH_OPTIONS = ("--schema", "--defaults", "--out", "--config", "--overrides", "--samples", "--commands", "--repairs")
SHIPPED_PROFILE_NAMES = ["dev", "prod"]
SHIPPED_INPUT_NAMES = [
    "config_schema.json",
    "defaults.json",
    "env_overrides.json",
    "history_2026-07.jsonl",
    "sample_config_dev.json",
    "sample_config_prod.json",
    "sample_config_stage.json",
    "tool.zip",
    "validation_rules.json",
]
FORBIDDEN_KEYS = {"timestamp", "generated_at", "uuid", "random_seed"}
FORBIDDEN_KEY_DOCUMENTS = ("config.json", "report.json", "validation_report.json", "summary.json")
CREDENTIAL_KEYS = {"api_key", "apikey", "password", "secret", "token", "credential"}
SHIPPED_MARKERS = (b"TASK", b"Z\xc3\xbcrich-ops", b"edge-cache", b"9007199254740993")
SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]
INTERPRETER_OPTIONS = ("-E", "-s")

# The shipped inputs, byte for byte. The verifier container holds no copy of the agent's
# input directory, so the checks carry their own: repeated keys and the byte order mark
# included, because reading them correctly is part of what is graded.
SHIPPED_SCHEMA = (
    b'{\n'
    b'  "profile": "TASK",\n'
    b'  "producer": "",\n'
    b'  "container": "",\n'
    b'  "required_keys": ["profile", "producer", "container", "max_records", "retry_limit", "timeout_ms",'
    b' "checksum", "mode", "trailer"],\n'
    b'  "checksum": "crc32"\n'
    b'}\n'
)
SHIPPED_DEFAULTS = (
    b'{\n'
    b'  "checksum": "crc32",\n'
    b'  "mode": "strict-local",\n'
    b'  "producer": "Z\xc3\xbcrich-ops",\n'
    b'  "container": "edge-cache",\n'
    b'  "base_config": {\n'
    b'    "timeout_ms": 7148,\n'
    b'    "max_records": 9007199254740993,\n'
    b'    "retry_limit": 5,\n'
    b'    "timeout_ms": 7418\n'
    b'  }\n'
    b'}\n'
)
SHIPPED_OVERRIDES = (
    b'{\n'
    b'  "local": {\n'
    b'    "mode": "strict-local",\n'
    b'    "retry_limit_delta": 1\n'
    b'  },\n'
    b'  "dev": {\n'
    b'    "extends": "local",\n'
    b'    "retry_limit_delta": 1,\n'
    b'    "timeout_ms_delta": -125,\n'
    b'    "timeout_ms_delta": 125\n'
    b'  },\n'
    b'  "stage": {\n'
    b'    "mode": "relaxed-local",\n'
    b'    "timeout_ms_delta": 100,\n'
    b'    "max_records_delta": 40\n'
    b'  },\n'
    b'  "prod": {\n'
    b'    "extends": "stage",\n'
    b'    "retry_limit": 3,\n'
    b'    "retry_limit_delta": 0,\n'
    b'    "timeout_ms_delta": 150\n'
    b'  },\n'
    b'  "canary": {\n'
    b'    "extends": "prod",\n'
    b'    "mode": "canary-local",\n'
    b'    "retry_limit_delta": 2\n'
    b'  }\n'
    b'}\n'
)
SHIPPED_SAMPLES = {
    "dev": b'\xef\xbb\xbf{\n  "profile": "dev",\n  "max_records_delta": -10,\n  "checksum": "md5"\n}\n',
    "prod": b'{\n  "profile": "prod",\n  "max_records_delta": 25,\n  "checksum": "crc32"\n}\n',
    "stage": b'{\n  "profile": "stage",\n  "max_records_delta": 5\n}\n',
}

# Inputs of other shapes, written by the checks: a different format tag, a shuffled key
# list, a comma-separated key list, schema-side identity values that must be ignored, and a
# twelve-entry override graph whose deepest chain has seven entries.
SCHEMA_QX7 = {
    "profile": "QX7",
    "producer": "schema-side",
    "container": "schema-box",
    "checksum": "sha1",
    "required_keys": ["trailer", "timeout_ms", "mode", "profile", "checksum", "retry_limit", "max_records",
                      "producer", "container"],
}
DEFAULTS_QX7 = {
    "checksum": "crc32",
    "container": "rack-9",
    "mode": "batch-local",
    "producer": "\u00c5ngstr\u00f6m-lab",
    "base_config": {"max_records": 120, "retry_limit": 2, "timeout_ms": 950},
}
SCHEMA_OPS9 = {
    "profile": "ops9",
    "required_keys": "profile,trailer,producer,max_records,container,retry_limit,checksum,timeout_ms,mode",
}
DEFAULTS_OPS9 = {
    "checksum": "adler32",
    "container": "",
    "mode": "strict-local",
    "producer": "",
    "base_config": {"max_records": 64, "retry_limit": 3, "timeout_ms": 30000},
}
QUIRKY_SCHEMA = b'\xef\xbb\xbf{"required_keys": ["profile"], "profile": "R2D", "profile": "WRONG"}\n'
QUIRKY_DEFAULTS = (
    b'\xef\xbb\xbf{"mode": "first-mode", "producer": "\xc3\x98resund", "container": "c1", "checksum": "crc32",'
    b' "mode": "second-mode", "producer": "later", "container": "c2"}\n'
)
QUIRKY_OVERRIDES = (
    b'{"p": {"retry_limit_delta": 4, "mode": "m1", "retry_limit_delta": 40, "timeout_ms_delta": 7},'
    b' "q": {}, "p": {"mode": "second-entry", "timeout_ms_delta": 70}}\n'
)
QUIRKY_SAMPLES = {
    "p": b'\xef\xbb\xbf{"max_records_delta": 7, "max_records_delta": 70}\n',
}
GRAPH_OVERRIDES = {
    "base": {"mode": "pool-a", "retry_limit_delta": 1},
    "east": {"extends": "base", "timeout_ms_delta": 40},
    "east-1": {"extends": "east", "retry_limit_delta": -2, "mode": "pool-b"},
    "east-1a": {"extends": "east-1", "timeout_ms_delta": -15, "retry_limit": 99, "max_records_delta": 1000},
    "west": {"timeout_ms_delta": 5, "checksum": "md5"},
    "west-eu": {"extends": "west", "mode": "eu-local", "max_records": 1},
    "west-eu-c": {"extends": "west-eu", "retry_limit_delta": 2, "timeout_ms_delta": 10},
    "solo": {},
    "solo-x": {"extends": "solo", "timeout_ms": 1},
    "deep": {"extends": "east-1a", "mode": "pool-c"},
    "deeper": {"extends": "deep", "retry_limit_delta": 3},
    "deepest": {"extends": "deeper", "timeout_ms_delta": -100},
}
GRAPH_SAMPLES = {
    "base": {"max_records_delta": 10, "checksum": "md5"},
    "east-1": {"max_records_delta": -3},
    "east-1a": {"profile": "other", "max_records_delta": 2},
    "west": {"max_records_delta": 0},
    "west-eu": {"max_records_delta": 11, "checksum": "sha256"},
    "solo": {"checksum": "none"},
    "solo-x": {"max_records_delta": 5},
    "deeper": {"max_records_delta": -20},
    "deepest": {"max_records_delta": 1},
}
BROKEN_CHAINS = {
    "loop-a": {"extends": "loop-b"},
    "loop-b": {"extends": "loop-a"},
    "orphan": {"extends": "nowhere"},
    "fine": {},
}
CONFIG_QX7_FIELDS = {
    "profile": "QX7",
    "producer": "\u00c5ngstr\u00f6m-lab",
    "container": "rack-9",
    "checksum": "crc32",
    "mode": "batch-local",
    "max_records": 120,
    "retry_limit": 2,
    "timeout_ms": 950,
}
CONFIG_OPS9_FIELDS = {
    "profile": "ops9",
    "producer": "",
    "container": "",
    "checksum": "adler32",
    "mode": "strict-local",
    "max_records": 64,
    "retry_limit": 3,
    "timeout_ms": 30000,
}
INVALID_SETS = [
    ("MAX_RECORDS", "5"),
    ("max_records ", "5"),
    ("trailer", "5"),
    ("batch_size", "5"),
    ("max_records", "1e3"),
    ("max_records", "12.0"),
    ("retry_limit", " 7"),
    ("retry_limit", "+7"),
    ("retry_limit", "nan"),
    ("timeout_ms", "007"),
    ("timeout_ms", "1_000"),
    ("timeout_ms", ""),
    ("timeout_ms", "0x10"),
]


def out_dir(workspace: Path) -> Path:
    return workspace / "out"


def artifact(workspace: Path, name: str) -> Path:
    return out_dir(workspace) / name


def read_regular_bytes(path: Path) -> bytes | None:
    """The bytes of a regular file within the published size bound; None for anything else."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return None
    chunks: list[bytes] = []
    size = 0
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return None
        while chunk := os.read(fd, 65536):
            size += len(chunk)
            if size > MAX_ARTIFACT_BYTES:
                return None
            chunks.append(chunk)
    except OSError:
        return None
    finally:
        os.close(fd)
    return b"".join(chunks)


def strict_json(raw: bytes | None) -> Any:
    """Parse output bytes as plain UTF-8 JSON; None when absent or unparseable."""
    if raw is None:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (ValueError, MemoryError, RecursionError):
        return None


def load_json(path: Path) -> Any:
    return strict_json(read_regular_bytes(path))


def lenient_json(raw: bytes) -> Any:
    """Read an input the way input_rules describe it: byte order mark dropped, first key wins."""

    def first_wins(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        kept: dict[str, Any] = {}
        for name, value in pairs:
            if name not in kept:
                kept[name] = value
        return kept

    return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=first_wins)


def canonical_bytes(document: Any) -> bytes:
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + b"\n"


def digest_hex(document: dict[str, Any]) -> str:
    stripped = {name: value for name, value in document.items() if name != "trailer"}
    return "%016x" % zlib.crc32(canonical_bytes(stripped))


def with_seal(document: dict[str, Any]) -> dict[str, Any]:
    stripped = {name: value for name, value in document.items() if name != "trailer"}
    stripped["trailer"] = SEAL_HEAD + ":" + str(stripped.get("profile")) + ":" + digest_hex(stripped)
    return stripped


def chain_names(overrides: dict[str, Any], name: str) -> list[str] | None:
    names: list[str] = []
    cursor: Any = name
    while cursor is not None:
        if not isinstance(cursor, str) or cursor in names or not isinstance(overrides.get(cursor), dict):
            return None
        names.insert(0, cursor)
        cursor = overrides[cursor].get("extends")
    return names


def expected_profile_docs(config: Any, overrides: Any, deltas: dict[str, int], name: str) -> list[dict[str, Any]] | None:
    """Reference resolution of profile_rules: one document per chain entry, root first."""
    if not isinstance(config, dict) or not isinstance(overrides, dict):
        return None
    names = chain_names(overrides, name)
    if names is None or not all(field in config for field in DOCUMENT_FIELDS):
        return None
    running = {field: config[field] for field in NUMBER_FIELDS + ("mode",)}
    parent_trailer = config["trailer"]
    docs: list[dict[str, Any]] = []
    for entry_name in names:
        entry = overrides[entry_name]
        running["max_records"] = running["max_records"] + deltas.get(entry_name, 0)
        running["retry_limit"] = running["retry_limit"] + entry.get("retry_limit_delta", 0)
        running["timeout_ms"] = running["timeout_ms"] + entry.get("timeout_ms_delta", 0)
        if "mode" in entry:
            running["mode"] = entry["mode"]
        doc = {
            "profile": str(config["profile"]) + "-" + entry_name,
            "producer": config["producer"],
            "container": config["container"],
            "checksum": config["checksum"],
        }
        doc.update(running)
        parent_trailer = str(parent_trailer) + ":" + entry_name + ":" + digest_hex(doc)
        doc["trailer"] = parent_trailer
        docs.append(doc)
    return docs


def shipped_policy() -> dict[str, Any]:
    schema = lenient_json(SHIPPED_SCHEMA)
    defaults = lenient_json(SHIPPED_DEFAULTS)
    doc = {"profile": schema["profile"]}
    for field in ("producer", "container", "checksum", "mode"):
        doc[field] = defaults[field]
    for field in NUMBER_FIELDS:
        doc[field] = defaults["base_config"][field]
    return with_seal(doc)


def shipped_deltas() -> dict[str, int]:
    return {name: lenient_json(raw).get("max_records_delta", 0) for name, raw in SHIPPED_SAMPLES.items()}


def same_values(got: Any, want: dict[str, Any], fields: tuple[str, ...]) -> bool:
    """Field-by-field equality that also refuses true or false standing in for an integer."""
    if not isinstance(got, dict):
        return False
    for field in fields:
        if field not in got or got[field] != want[field] or type(got[field]) is not type(want[field]):
            return False
    return True


def lock_artifacts(workspace: Path) -> None:
    """Remove group and other write access from the artifact directory and its files."""
    directory = out_dir(workspace)
    with suppress(OSError):
        status = os.lstat(directory)
        if not stat.S_ISDIR(status.st_mode):
            return
        os.chmod(directory, stat.S_IMODE(status.st_mode) & ~0o022)
        for entry in os.scandir(directory):
            if entry.is_file(follow_symlinks=False):
                os.chmod(entry.path, stat.S_IMODE(entry.stat(follow_symlinks=False).st_mode) & ~0o022)


@functools.lru_cache(maxsize=None)
def unpacked_root(workspace_text: str) -> str | None:
    """Extract the delivered archive once into a verifier-owned dir. None when unusable."""
    # The artifacts are locked before any delivered code runs, and the unpacked tree stays
    # owned by root and read-only to the unprivileged user that runs it.
    workspace = Path(workspace_text)
    lock_artifacts(workspace)
    raw = read_regular_bytes(artifact(workspace, "tool.zip"))
    if raw is None:
        return None
    try:
        root = Path(tempfile.mkdtemp(prefix="cli-config-tool-"))
        os.chmod(root, 0o755)
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            seen: set[str] = set()
            for info in zf.infolist():
                rel = Path(info.filename)
                if rel.is_absolute() or ".." in rel.parts or "\\" in info.filename:
                    return None
                if info.filename in seen:
                    return None
                seen.add(info.filename)
                if info.is_dir():
                    continue
                if info.file_size > MAX_ARTIFACT_BYTES:
                    return None
                dest = root / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                os.chmod(dest.parent, 0o755)
                dest.write_bytes(zf.read(info))
                os.chmod(dest, 0o644)
    except (OSError, ValueError, EOFError, zipfile.BadZipFile, zlib.error, RuntimeError, MemoryError):
        return None
    if not (root / "cli.py").is_file():
        return None
    return str(root)


def unpack_tool(workspace: Path) -> Path | None:
    text = unpacked_root(str(workspace))
    return None if text is None else Path(text)


def run_cli(root: Path, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str] | None:
    """Run the delivered CLI as an unprivileged subprocess in its own process group.

    -E and -s keep PYTHON* variables and user site-packages out; the script's own
    directory stays importable, as it is when README runs `python3 cli.py`.
    """
    command = [sys.executable, "-E", "-s", str(root / "cli.py"), *args]
    if os.name == "posix" and os.geteuid() == 0:
        command = [*SETPRIV, *command]
    popen_kwargs: dict[str, Any] = {
        "cwd": str(cwd) if cwd is not None else "/tmp",
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "env": {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "PYTHONHASHSEED": "0",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
        },
    }
    if os.name == "posix":
        popen_kwargs["start_new_session"] = True
    process = None
    pgid = None
    try:
        process = subprocess.Popen(command, **popen_kwargs)
        if os.name == "posix":
            pgid = process.pid
        stdout, stderr = process.communicate(timeout=20)
        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    except (OSError, ValueError, MemoryError, subprocess.SubprocessError):
        return None
    finally:
        if pgid is not None:
            with suppress(OSError):
                os.killpg(pgid, signal.SIGKILL)
        if process is not None:
            with suppress(OSError, subprocess.SubprocessError):
                process.wait(timeout=5)


def succeeded(result: subprocess.CompletedProcess[str] | None) -> bool:
    return result is not None and result.returncode == 0


def failed_cleanly(result: subprocess.CompletedProcess[str] | None) -> bool:
    """The published error shape: status 1, nothing on stdout, one line on stderr."""
    if result is None or result.returncode != 1 or result.stdout != "":
        return False
    return len([line for line in result.stderr.splitlines() if line.strip()]) == 1


def work_dir() -> Path:
    path = Path(tempfile.mkdtemp(prefix="cli-config-work-"))
    os.chmod(path, 0o777)
    return path


def put(directory: Path, name: str, data: bytes | dict[str, Any] | list[Any]) -> Path:
    """Write a check-owned input the unprivileged CLI can read but not change."""
    path = directory / name
    payload = data if isinstance(data, bytes) else json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
    path.write_bytes(payload)
    os.chmod(path, 0o644)
    return path


def init_and_set(root: Path, directory: Path, schema: dict[str, Any], defaults: dict[str, Any],
                 order: tuple[str, ...]) -> Path | None:
    """init, then one set per numeric key in the given order; the config path, or None."""
    schema_path = put(directory, "schema.json", schema)
    defaults_path = put(directory, "defaults.json", defaults)
    config = directory / "config.json"
    if not succeeded(run_cli(root, "init", "--schema", str(schema_path), "--defaults", str(defaults_path),
                             "--out", str(config))):
        return None
    for field in order:
        value = str(defaults["base_config"][field])
        if not succeeded(run_cli(root, "set", "--config", str(config), "--key", field, "--value", value)):
            return None
    return config


@functools.lru_cache(maxsize=None)
def graph_outputs(root_text: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Run the delivered profile subcommand for every entry of the twelve-entry graph."""
    root = Path(root_text)
    stage = work_dir()
    config = with_seal(CONFIG_QX7_FIELDS)
    config_path = put(stage, "config.json", canonical_bytes(config))
    overrides_path = put(stage, "overrides.json", GRAPH_OVERRIDES)
    samples = stage / "samples"
    samples.mkdir()
    os.chmod(samples, 0o755)
    for name, sample in sorted(GRAPH_SAMPLES.items()):
        put(samples, f"sample_config_{name}.json", sample)
    produced: dict[str, Any] = {}
    for name in sorted(GRAPH_OVERRIDES):
        target = stage / f"profile_{name}.json"
        result = run_cli(root, "profile", "--config", str(config_path), "--overrides", str(overrides_path),
                         "--samples", str(samples), "--name", name, "--out", str(target))
        produced[name] = strict_json(read_regular_bytes(target)) if succeeded(result) else None
    return config, produced


def argv_layout(argv: Any, absolute: bool = True) -> int | None:
    """Index of cli.py in an argv shaped as interpreter, options, cli.py, subcommand."""
    if not isinstance(argv, list) or len(argv) < 3 or not all(isinstance(part, str) for part in argv):
        return None
    if not os.path.basename(argv[0]).startswith("python"):
        return None
    for index in range(1, len(argv) - 1):
        if os.path.basename(argv[index]) == "cli.py":
            return index if argv[index].startswith("/") or not absolute else None
    return None


def option_values(tail: list[str]) -> dict[str, str] | None:
    """Map --option to its value for an argv tail after the subcommand."""
    values: dict[str, str] = {}
    index = 0
    while index < len(tail):
        token = tail[index]
        if not token.startswith("--"):
            return None
        if "=" in token:
            name, _, value = token.partition("=")
            index += 1
        elif index + 1 < len(tail):
            name, value = token, tail[index + 1]
            index += 2
        else:
            return None
        values[name] = value
    return values


def transcript_follows_schema(report: Any, config_doc: Any, config_path: str) -> bool:
    if not isinstance(report, dict) or sorted(report) != sorted(REPORT_FIELDS):
        return False
    if report.get("ok") is not True or report.get("tool") != TOOL_NAME or report.get("config_path") != config_path:
        return False
    commands = report.get("commands")
    if not isinstance(commands, list) or len(commands) != len(TRANSCRIPT_ORDER):
        return False
    if not isinstance(config_doc, dict):
        return False
    printed = {"init": "", "set": "", "seal": config_doc.get("trailer"), "validate": "ok", "export-report": ""}
    set_keys: list[str] = []
    for item, subcommand in zip(commands, TRANSCRIPT_ORDER):
        if not isinstance(item, dict) or sorted(item) != ["argv", "returncode", "stdout"]:
            return False
        returncode = item["returncode"]
        if not isinstance(returncode, int) or isinstance(returncode, bool) or returncode != 0:
            return False
        if item["stdout"] != printed[subcommand]:
            return False
        argv = item["argv"]
        index = argv_layout(argv)
        if index is None or argv[index + 1] != subcommand:
            return False
        options = option_values(argv[index + 2:])
        if options is None:
            return False
        if any(name in PATH_OPTIONS and not value.startswith("/") for name, value in options.items()):
            return False
        target = options.get("--out") if subcommand == "init" else options.get("--config")
        if target != config_path:
            return False
        if subcommand == "set":
            set_keys.append(options.get("--key", ""))
    return sorted(set_keys) == sorted(NUMBER_FIELDS)


def replay_argument(value: str, root: Path, stage: Path) -> str | None:
    """Point an absolute path recorded in the transcript at the verifier's copies.

    Paths under the output directory move to the stage, paths under the input directory to
    the check-written copies of the shipped inputs, and paths under the tool directory to the
    unpacked delivered archive. An input that has no copy cannot be replayed.
    """
    if value.startswith("--") and "=" in value:
        name, _, inner = value.partition("=")
        mapped = replay_argument(inner, root, stage)
        return None if mapped is None else name + "=" + mapped
    if not value.startswith("/"):
        return value
    targets = (("/app/out/", stage / "out", False), ("/app/data/", stage / "data", True), ("/app/tool/", root, True))
    for prefix, base, must_exist in targets:
        if value.startswith(prefix):
            mapped = base / value[len(prefix):]
            if must_exist and not mapped.is_file():
                return None
            return str(mapped)
    return None


def json_keys_and_strings(value: Any) -> tuple[set[str], list[str]]:
    """Collect every lowercased key name and every string value in a JSON document."""
    keys: set[str] = set()
    strings: list[str] = []
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            for key, sub in item.items():
                if isinstance(key, str):
                    keys.add(key.lower())
                stack.append(sub)
        elif isinstance(item, list):
            stack.extend(item)
        elif isinstance(item, str):
            strings.append(item)
    return keys, strings


@criterion(description="all seven declared artifacts exist as non-empty regular files within the published size bound")
def artifacts_present(workspace: Path) -> bool:
    try:
        for name in ARTIFACT_NAMES:
            status = artifact(workspace, name).lstat()
            if not stat.S_ISREG(status.st_mode) or status.st_size == 0 or status.st_size > MAX_ARTIFACT_BYTES:
                return False
        return True
    except (OSError, ValueError):
        return False


@criterion(description="config.json carries the schema profile and the producer, container, checksum and mode of defaults.json")
def config_identity_matches_policy(workspace: Path) -> bool:
    try:
        return same_values(load_json(artifact(workspace, "config.json")), shipped_policy(), IDENTITY_FIELDS)
    except Exception:
        return False


@criterion(description="config.json carries the three base_config integers exactly, taking the first occurrence of a repeated key")
def config_integers_match_policy(workspace: Path) -> bool:
    try:
        return same_values(load_json(artifact(workspace, "config.json")), shipped_policy(), NUMBER_FIELDS)
    except Exception:
        return False


@criterion(description="the trailer in config.json is the CRC-32 config trailer of the document it sits in")
def config_trailer_is_its_seal(workspace: Path) -> bool:
    try:
        doc = load_json(artifact(workspace, "config.json"))
        return isinstance(doc, dict) and "trailer" in doc and doc["trailer"] == with_seal(doc)["trailer"]
    except Exception:
        return False


@criterion(description="config.json is stored in the canonical encoding with exactly the nine required keys")
def config_bytes_are_canonical(workspace: Path) -> bool:
    try:
        raw = read_regular_bytes(artifact(workspace, "config.json"))
        doc = strict_json(raw)
        return isinstance(doc, dict) and sorted(doc) == sorted(DOCUMENT_FIELDS) and raw == canonical_bytes(doc)
    except Exception:
        return False


def delivered_profile_matches_chain(workspace: Path, name: str) -> bool:
    config = load_json(artifact(workspace, "config.json"))
    profile = load_json(artifact(workspace, f"profile_{name}.json"))
    docs = expected_profile_docs(config, lenient_json(SHIPPED_OVERRIDES), shipped_deltas(), name)
    if docs is None or not isinstance(profile, dict) or sorted(profile) != sorted(DOCUMENT_FIELDS):
        return False
    return same_values(profile, docs[-1], IDENTITY_FIELDS + NUMBER_FIELDS)


@criterion(description="profile_dev.json holds the values its override chain resolves to from the delivered config.json")
def profile_dev_values_follow_its_chain(workspace: Path) -> bool:
    try:
        return delivered_profile_matches_chain(workspace, "dev")
    except Exception:
        return False


@criterion(description="profile_prod.json holds the values its override chain resolves to from the delivered config.json")
def profile_prod_values_follow_its_chain(workspace: Path) -> bool:
    try:
        return delivered_profile_matches_chain(workspace, "prod")
    except Exception:
        return False


@criterion(description="each delivered profile trailer extends the config.json trailer with one name and digest pair per chain entry")
def profile_trailers_chain_from_the_config(workspace: Path) -> bool:
    try:
        config = load_json(artifact(workspace, "config.json"))
        overrides = lenient_json(SHIPPED_OVERRIDES)
        for name in SHIPPED_PROFILE_NAMES:
            profile = load_json(artifact(workspace, f"profile_{name}.json"))
            docs = expected_profile_docs(config, overrides, shipped_deltas(), name)
            if docs is None or not isinstance(profile, dict):
                return False
            # Ancestors come from the reference resolution of the delivered config; the last
            # pair is the digest of the delivered profile body itself.
            parent = docs[-2]["trailer"] if len(docs) > 1 else config["trailer"]
            if profile.get("trailer") != parent + ":" + name + ":" + digest_hex(profile):
                return False
        return True
    except Exception:
        return False


@criterion(description="the delivered profile files are byte for byte what the delivered CLI writes from config.json and the shipped inputs")
def delivered_profiles_come_from_delivered_cli(workspace: Path) -> bool:
    try:
        root = unpack_tool(workspace)
        config_raw = read_regular_bytes(artifact(workspace, "config.json"))
        if root is None or config_raw is None:
            return False
        stage = work_dir()
        config_path = put(stage, "config.json", config_raw)
        overrides_path = put(stage, "env_overrides.json", SHIPPED_OVERRIDES)
        for name, raw in sorted(SHIPPED_SAMPLES.items()):
            put(stage, f"sample_config_{name}.json", raw)
        for name in SHIPPED_PROFILE_NAMES:
            delivered = read_regular_bytes(artifact(workspace, f"profile_{name}.json"))
            target = stage / f"rebuilt_{name}.json"
            result = run_cli(root, "profile", "--config", str(config_path), "--overrides", str(overrides_path),
                             "--samples", str(stage), "--name", name, "--out", str(target))
            if not succeeded(result) or delivered is None or read_regular_bytes(target) != delivered:
                return False
        return True
    except Exception:
        return False


@criterion(description="report.json holds exactly the published keys and the seven-entry command transcript the report schema describes")
def report_records_the_published_transcript(workspace: Path) -> bool:
    try:
        report = load_json(artifact(workspace, "report.json"))
        config = load_json(artifact(workspace, "config.json"))
        return transcript_follows_schema(report, config, str(artifact(workspace, "config.json")))
    except Exception:
        return False


@criterion(description="report.json carries the trailer of config.json and the SHA-256 of its bytes")
def report_digest_matches_delivered_config(workspace: Path) -> bool:
    try:
        report = load_json(artifact(workspace, "report.json"))
        raw = read_regular_bytes(artifact(workspace, "config.json"))
        config = strict_json(raw)
        if not isinstance(report, dict) or not isinstance(config, dict):
            return False
        return report.get("config_sha256") == hashlib.sha256(raw).hexdigest() and report.get("trailer") == config.get("trailer")
    except Exception:
        return False


@criterion(description="replaying the first six recorded commands with the delivered CLI reproduces their exit codes and output and the delivered config.json bytes")
def report_transcript_replays_with_delivered_cli(workspace: Path) -> bool:
    try:
        report = load_json(artifact(workspace, "report.json"))
        delivered = read_regular_bytes(artifact(workspace, "config.json"))
        root = unpack_tool(workspace)
        if not isinstance(report, dict) or delivered is None or root is None:
            return False
        commands = report.get("commands")
        if not isinstance(commands, list) or len(commands) != len(TRANSCRIPT_ORDER):
            return False
        stage = work_dir()
        for sub in ("data", "out"):
            (stage / sub).mkdir()
        os.chmod(stage / "data", 0o755)
        os.chmod(stage / "out", 0o777)
        put(stage / "data", "config_schema.json", SHIPPED_SCHEMA)
        put(stage / "data", "defaults.json", SHIPPED_DEFAULTS)
        for item in commands[:-1]:
            if not isinstance(item, dict):
                return False
            argv = item.get("argv")
            index = argv_layout(argv, absolute=False)
            if index is None:
                return False
            mapped = [replay_argument(part, root, stage) for part in argv[index + 1:]]
            if any(part is None for part in mapped):
                return False
            result = run_cli(root, *[part for part in mapped if part is not None], cwd=stage)
            if result is None or result.returncode != item.get("returncode"):
                return False
            if result.stdout.strip() != item.get("stdout"):
                return False
        return read_regular_bytes(stage / "out" / "config.json") == delivered
    except Exception:
        return False


@criterion(description="every claim in validation_report.json matches the delivered artifacts and the shipped override chains")
def validation_report_tells_the_truth(workspace: Path) -> bool:
    try:
        report = load_json(artifact(workspace, "validation_report.json"))
        if not isinstance(report, dict) or not isinstance(report.get("checks"), dict):
            return False
        checks = report["checks"]
        config = load_json(artifact(workspace, "config.json"))
        run_report = load_json(artifact(workspace, "report.json"))
        if not isinstance(config, dict) or not isinstance(run_report, dict) or not isinstance(run_report.get("commands"), list):
            return False
        present = all(read_regular_bytes(artifact(workspace, name)) is not None for name in ARTIFACT_NAMES)
        flags = {
            "all_artifacts_present": present,
            "config_matches_policy": config == shipped_policy(),
            "config_scalar_flat": all(isinstance(v, (str, int)) and not isinstance(v, bool) for v in config.values()),
            "config_seal_verified": "trailer" in config and config["trailer"] == with_seal(config)["trailer"],
        }
        for key, truth in flags.items():
            if checks.get(key) is not truth:
                return False
        failures = [item for item in run_report["commands"] if not isinstance(item, dict) or item.get("returncode") != 0]
        if checks.get("command_failures") != failures or checks.get("required_artifacts") != ARTIFACT_NAMES:
            return False
        overrides = lenient_json(SHIPPED_OVERRIDES)
        wanted_profiles = {}
        for name in SHIPPED_PROFILE_NAMES:
            profile = load_json(artifact(workspace, f"profile_{name}.json"))
            if not isinstance(profile, dict):
                return False
            wanted_profiles[name] = {"trailer": profile.get("trailer"), "chain": chain_names(overrides, name)}
        if checks.get("profiles") != wanted_profiles:
            return False
        return report.get("ok") is (all(flags.values()) and not failures)
    except Exception:
        return False


@criterion(description="summary.json inventories the input files, the profiles, the artifacts and the trailer of config.json")
def summary_inventories_inputs_and_artifacts(workspace: Path) -> bool:
    try:
        summary = load_json(artifact(workspace, "summary.json"))
        config = load_json(artifact(workspace, "config.json"))
        if not isinstance(summary, dict) or not isinstance(config, dict):
            return False
        wanted = {
            "artifact_count": len(ARTIFACT_NAMES),
            "artifacts": ARTIFACT_NAMES,
            "profiles": SHIPPED_PROFILE_NAMES,
            "format_tag": "TASK",
            "trailer": config.get("trailer"),
            "inputs": SHIPPED_INPUT_NAMES,
            "input_count": len(SHIPPED_INPUT_NAMES),
        }
        return all(summary.get(key) == value and type(summary.get(key)) is type(value) for key, value in wanted.items())
    except Exception:
        return False


@criterion(description="the delivered archive is safe to unpack, keeps every member at the archive root and carries README.md, cli.py and schema.json")
def delivered_archive_is_flat_and_safe(workspace: Path) -> bool:
    try:
        if unpack_tool(workspace) is None:
            return False
        raw = read_regular_bytes(artifact(workspace, "tool.zip"))
        if raw is None:
            return False
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            names = {info.filename for info in zf.infolist()}
            flat = all("/" not in info.filename for info in zf.infolist())
            return flat and {"README.md", "cli.py", "schema.json"} <= names
    except Exception:
        return False


def usage_error(result: subprocess.CompletedProcess[str] | None) -> bool:
    return result is not None and result.returncode == 2 and result.stdout == "" and result.stderr.startswith("usage: task-ctl")


@criterion(description="the delivered CLI exits 2 with a task-ctl usage message on standard error, nothing on standard output and no file written, for no subcommand, a missing required option and an unknown option")
def delivered_cli_reports_usage_errors(workspace: Path) -> bool:
    try:
        root = unpack_tool(workspace)
        if root is None or not usage_error(run_cli(root)):
            return False
        stage = work_dir()
        schema_path = put(stage, "schema.json", SCHEMA_QX7)
        sealed = canonical_bytes(with_seal(CONFIG_QX7_FIELDS))
        config_path = put(stage, "config.json", sealed)
        target = stage / "written.json"
        attempts = [
            ("init", "--schema", str(schema_path), "--out", str(target)),
            ("validate", "--config", str(config_path)),
            ("profile", "--config", str(config_path), "--overrides", str(config_path), "--name", "x",
             "--out", str(target)),
            ("seal", "--config", str(config_path), "--bogus", "x"),
        ]
        for argv in attempts:
            if not usage_error(run_cli(root, *argv)) or os.path.lexists(target):
                return False
        return read_regular_bytes(config_path) == sealed
    except Exception:
        return False


@criterion(description="the delivered init takes profile from the schema and the other identity values from the defaults file, for a list and a comma-separated schema")
def delivered_cli_init_takes_identity_from_schema_and_defaults(workspace: Path) -> bool:
    try:
        root = unpack_tool(workspace)
        if root is None:
            return False
        for schema, defaults in ((SCHEMA_QX7, DEFAULTS_QX7), (SCHEMA_OPS9, DEFAULTS_OPS9)):
            stage = work_dir()
            target = stage / "seed.json"
            result = run_cli(root, "init", "--schema", str(put(stage, "schema.json", schema)), "--defaults",
                             str(put(stage, "defaults.json", defaults)), "--out", str(target))
            want = {"profile": schema["profile"]}
            want.update({field: defaults[field] for field in ("producer", "container", "checksum", "mode")})
            if not succeeded(result) or load_json(target) != want:
                return False
        return True
    except Exception:
        return False


@criterion(description="the delivered CLI reads inputs that start with a byte order mark and repeat keys, keeping the first occurrence, in init and in profile")
def delivered_cli_reads_inputs_by_the_input_rules(workspace: Path) -> bool:
    try:
        root = unpack_tool(workspace)
        if root is None:
            return False
        stage = work_dir()
        seed = stage / "seed.json"
        result = run_cli(root, "init", "--schema", str(put(stage, "schema.json", QUIRKY_SCHEMA)), "--defaults",
                         str(put(stage, "defaults.json", QUIRKY_DEFAULTS)), "--out", str(seed))
        want_seed = {"profile": "R2D", "producer": "\u00d8resund", "container": "c1", "checksum": "crc32",
                     "mode": "first-mode"}
        if not succeeded(result) or load_json(seed) != want_seed:
            return False
        config = with_seal(CONFIG_QX7_FIELDS)
        config_path = put(stage, "config.json", canonical_bytes(config))
        for name, raw in sorted(QUIRKY_SAMPLES.items()):
            put(stage, f"sample_config_{name}.json", raw)
        target = stage / "profile_p.json"
        result = run_cli(root, "profile", "--config", str(config_path), "--overrides",
                         str(put(stage, "overrides.json", QUIRKY_OVERRIDES)), "--samples", str(stage), "--name", "p",
                         "--out", str(target))
        docs = expected_profile_docs(config, lenient_json(QUIRKY_OVERRIDES),
                                     {name: lenient_json(raw)["max_records_delta"] for name, raw in QUIRKY_SAMPLES.items()}, "p")
        return succeeded(result) and docs is not None and same_values(load_json(target), docs[-1], IDENTITY_FIELDS + NUMBER_FIELDS)
    except Exception:
        return False


@criterion(description="the delivered set stores the exact integer for each numeric key, beyond float precision, and a later set replaces the earlier value")
def delivered_cli_set_stores_exact_integers(workspace: Path) -> bool:
    try:
        root = unpack_tool(workspace)
        if root is None:
            return False
        stage = work_dir()
        config = stage / "config.json"
        if not succeeded(run_cli(root, "init", "--schema", str(put(stage, "schema.json", SCHEMA_QX7)), "--defaults",
                                 str(put(stage, "defaults.json", DEFAULTS_QX7)), "--out", str(config))):
            return False
        steps = [("max_records", "9007199254740995"), ("retry_limit", "0"), ("timeout_ms", "-250"),
                 ("max_records", "18446744073709551617")]
        for field, value in steps:
            if not succeeded(run_cli(root, "set", "--config", str(config), "--key", field, "--value", value)):
                return False
        want = {"max_records": 18446744073709551617, "retry_limit": 0, "timeout_ms": -250}
        return same_values(load_json(config), want, NUMBER_FIELDS)
    except Exception:
        return False


@criterion(description="the delivered set refuses a key other than the three numeric keys and any value that is not a plain base-10 integer, with the published error shape and the file unchanged, while still storing a valid value in that file")
def delivered_cli_set_refuses_invalid_input(workspace: Path) -> bool:
    try:
        root = unpack_tool(workspace)
        if root is None:
            return False
        stage = work_dir()
        start = canonical_bytes({field: CONFIG_QX7_FIELDS[field] for field in IDENTITY_FIELDS + NUMBER_FIELDS})
        config = stage / "config.json"
        for field, value in INVALID_SETS:
            config.write_bytes(start)
            os.chmod(config, 0o666)
            result = run_cli(root, "set", "--config", str(config), "--key", field, "--value", value)
            if not failed_cleanly(result) or read_regular_bytes(config) != start:
                return False
        # Control: the same file still takes a valid value, so refusing everything earns nothing.
        config.write_bytes(start)
        os.chmod(config, 0o666)
        if not succeeded(run_cli(root, "set", "--config", str(config), "--key", "timeout_ms", "--value", "0")):
            return False
        return same_values(load_json(config), {"timeout_ms": 0}, ("timeout_ms",))
    except Exception:
        return False


@criterion(description="every document the delivered CLI writes is in the canonical encoding, and setting keys in a different order yields identical bytes")
def delivered_cli_writes_canonical_bytes(workspace: Path) -> bool:
    try:
        root = unpack_tool(workspace)
        if root is None:
            return False
        builds = []
        for order in (NUMBER_FIELDS, tuple(reversed(NUMBER_FIELDS))):
            stage = work_dir()
            config = init_and_set(root, stage, SCHEMA_QX7, DEFAULTS_QX7, order)
            if config is None or not succeeded(run_cli(root, "seal", "--config", str(config))):
                return False
            builds.append(read_regular_bytes(config))
        outputs = list(builds)
        seed_stage = work_dir()
        seed = seed_stage / "seed.json"
        if not succeeded(run_cli(root, "init", "--schema", str(put(seed_stage, "schema.json", SCHEMA_QX7)),
                                 "--defaults", str(put(seed_stage, "defaults.json", DEFAULTS_QX7)), "--out", str(seed))):
            return False
        outputs.append(read_regular_bytes(seed))
        profile_stage = work_dir()
        config_path = put(profile_stage, "config.json", canonical_bytes(with_seal(CONFIG_QX7_FIELDS)))
        target = profile_stage / "profile.json"
        put(profile_stage, "sample_config_solo.json", {"max_records_delta": 3})
        if not succeeded(run_cli(root, "profile", "--config", str(config_path), "--overrides",
                                 str(put(profile_stage, "overrides.json", {"solo": {}})), "--samples",
                                 str(profile_stage), "--name", "solo", "--out", str(target))):
            return False
        outputs.append(read_regular_bytes(target))
        if builds[0] != builds[1]:
            return False
        return all(raw is not None and raw == canonical_bytes(strict_json(raw)) for raw in outputs)
    except Exception:
        return False


@criterion(description="the delivered seal stores and prints the CRC-32 config trailer, ignoring a stale trailer and the input's own byte layout")
def delivered_cli_seal_writes_the_crc32_trailer(workspace: Path) -> bool:
    try:
        root = unpack_tool(workspace)
        if root is None:
            return False
        body = dict(CONFIG_QX7_FIELDS)
        body["max_records"] = 9007199254740995
        stale = dict(body)
        stale["trailer"] = SEAL_HEAD + ":QX7:0000000000000000"
        layouts = [
            canonical_bytes(body),
            canonical_bytes(stale),
            (json.dumps(body, indent=2, ensure_ascii=True) + "\n").encode("utf-8"),
        ]
        want = with_seal(body)
        for raw in layouts:
            stage = work_dir()
            config = stage / "config.json"
            config.write_bytes(raw)
            os.chmod(config, 0o666)
            result = run_cli(root, "seal", "--config", str(config))
            if not succeeded(result) or result.stdout.strip() != want["trailer"]:
                return False
            if not same_values(load_json(config), want, DOCUMENT_FIELDS):
                return False
        return True
    except Exception:
        return False


@criterion(description="the delivered validate prints ok and exits 0 for conforming configurations checked against a list schema and a comma-separated schema, and refuses a mismatched profile")
def delivered_cli_validate_accepts_conforming_configs(workspace: Path) -> bool:
    try:
        root = unpack_tool(workspace)
        if root is None:
            return False
        for schema, fields in ((SCHEMA_QX7, CONFIG_QX7_FIELDS), (SCHEMA_OPS9, CONFIG_OPS9_FIELDS)):
            stage = work_dir()
            result = run_cli(root, "validate", "--schema", str(put(stage, "schema.json", schema)), "--config",
                             str(put(stage, "config.json", canonical_bytes(with_seal(fields)))))
            if not succeeded(result) or result.stdout.strip() != "ok":
                return False
        # Control: a comma-separated schema with a mismatched profile is refused, so accepting
        # everything earns nothing.
        stage = work_dir()
        mismatched = canonical_bytes(with_seal(dict(CONFIG_OPS9_FIELDS, profile="ops8")))
        result = run_cli(root, "validate", "--schema", str(put(stage, "schema.json", SCHEMA_OPS9)), "--config",
                         str(put(stage, "config.json", mismatched)))
        return result is not None and result.returncode == 1 and result.stdout.strip() == ""
    except Exception:
        return False


def nonconforming_variants() -> list[bytes]:
    """Configurations that break exactly one validate rule each, against SCHEMA_QX7."""
    good = with_seal(CONFIG_QX7_FIELDS)
    variants: list[bytes] = []

    def resealed(change: dict[str, Any], drop: str | None = None) -> bytes:
        doc = {name: value for name, value in CONFIG_QX7_FIELDS.items() if name != drop}
        doc.update(change)
        return canonical_bytes(with_seal(doc))

    upper = {name: value for name, value in CONFIG_QX7_FIELDS.items() if name != "mode"}
    upper["MODE"] = CONFIG_QX7_FIELDS["mode"]
    variants.append(canonical_bytes(with_seal(upper)))
    variants.append(resealed({"notes": "x"}))
    variants.append(resealed({}, drop="container"))
    variants.append(resealed({"retry_limit": True}))
    variants.append(resealed({"timeout_ms": "950"}))
    variants.append(resealed({"max_records": 120.0}))
    variants.append(resealed({"container": ["rack-9"]}))
    variants.append(resealed({"profile": "QX8"}))
    flipped = dict(good)
    flipped["trailer"] = good["trailer"][:-1] + ("0" if good["trailer"][-1] != "0" else "1")
    variants.append(canonical_bytes(flipped))
    short = dict(good)
    short["trailer"] = SEAL_HEAD + ":QX7:" + "%08x" % zlib.crc32(canonical_bytes(CONFIG_QX7_FIELDS))
    variants.append(canonical_bytes(short))
    variants.append((json.dumps(good, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"))
    variants.append((json.dumps(good, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))
    variants.append(canonical_bytes(good)[:-1])
    return variants


@criterion(description="the delivered validate exits 1 with nothing on standard output for each configuration that breaks one published validate rule, while accepting a conforming one")
def delivered_cli_validate_rejects_nonconforming_configs(workspace: Path) -> bool:
    try:
        root = unpack_tool(workspace)
        if root is None:
            return False
        stage = work_dir()
        schema_path = put(stage, "schema.json", SCHEMA_QX7)
        # Control: a conforming configuration no other check uses is accepted, so refusing
        # everything earns nothing.
        control = canonical_bytes(with_seal(dict(CONFIG_QX7_FIELDS, max_records=9007199254740995)))
        result = run_cli(root, "validate", "--schema", str(schema_path), "--config",
                         str(put(stage, "control.json", control)))
        if not succeeded(result) or result.stdout.strip() != "ok":
            return False
        for number, raw in enumerate(nonconforming_variants()):
            result = run_cli(root, "validate", "--schema", str(schema_path), "--config",
                             str(put(stage, f"variant_{number}.json", raw)))
            if result is None or result.returncode != 1 or result.stdout.strip() != "":
                return False
        return True
    except Exception:
        return False


@criterion(description="the delivered profile resolves every entry of a twelve-entry override graph to the values its extends chain accumulates")
def delivered_cli_profile_resolves_inheritance_chains(workspace: Path) -> bool:
    try:
        root = unpack_tool(workspace)
        graph = graph_outputs(str(root)) if root is not None else None
        if graph is None:
            return False
        config, produced = graph
        deltas = {name: sample.get("max_records_delta", 0) for name, sample in GRAPH_SAMPLES.items()}
        for name in sorted(GRAPH_OVERRIDES):
            docs = expected_profile_docs(config, GRAPH_OVERRIDES, deltas, name)
            got = produced.get(name)
            if docs is None or not isinstance(got, dict) or sorted(got) != sorted(DOCUMENT_FIELDS):
                return False
            if not same_values(got, docs[-1], IDENTITY_FIELDS + NUMBER_FIELDS):
                return False
        return True
    except Exception:
        return False


@criterion(description="each profile trailer the delivered CLI writes is its parent trailer followed by its entry name and the digest of its own document")
def delivered_cli_profile_chains_trailers(workspace: Path) -> bool:
    try:
        root = unpack_tool(workspace)
        graph = graph_outputs(str(root)) if root is not None else None
        if graph is None:
            return False
        config, produced = graph
        for name in sorted(GRAPH_OVERRIDES):
            got = produced.get(name)
            parent_name = GRAPH_OVERRIDES[name].get("extends")
            parent = config if parent_name is None else produced.get(parent_name)
            if not isinstance(got, dict) or not isinstance(parent, dict) or "trailer" not in parent:
                return False
            if got.get("trailer") != str(parent["trailer"]) + ":" + name + ":" + digest_hex(got):
                return False
        return True
    except Exception:
        return False


@criterion(description="the delivered profile reports an unknown name, an extends naming a missing entry and an extends cycle with the published error shape and writes no file, while resolving the intact entry beside them")
def delivered_cli_profile_refuses_broken_chains(workspace: Path) -> bool:
    try:
        root = unpack_tool(workspace)
        if root is None:
            return False
        stage = work_dir()
        config_path = put(stage, "config.json", canonical_bytes(with_seal(CONFIG_QX7_FIELDS)))
        overrides_path = put(stage, "overrides.json", BROKEN_CHAINS)
        for name in ("ghost", "loop-a", "orphan"):
            target = stage / f"profile_{name}.json"
            result = run_cli(root, "profile", "--config", str(config_path), "--overrides", str(overrides_path),
                             "--samples", str(stage), "--name", name, "--out", str(target))
            if not failed_cleanly(result) or os.path.lexists(target):
                return False
        # Control: the intact entry in the same file resolves, so refusing everything earns nothing.
        target = stage / "profile_fine.json"
        result = run_cli(root, "profile", "--config", str(config_path), "--overrides", str(overrides_path),
                         "--samples", str(stage), "--name", "fine", "--out", str(target))
        written = load_json(target) if succeeded(result) else None
        return isinstance(written, dict) and written.get("profile") == "QX7-fine"
    except Exception:
        return False


def run_export_report(root: Path, failed_entry: bool) -> tuple[Any, list[str], Path, bytes, list[Any], list[str]] | None:
    """Drive the delivered export-report on a non-canonical config given by a relative path."""
    stage = work_dir()
    doc = with_seal(CONFIG_QX7_FIELDS)
    raw = (json.dumps(doc, indent=2) + "\n").encode("utf-8")
    put(stage, "config.json", raw)
    recorded: list[Any] = [
        {"argv": ["python3", "/opt/x/cli.py", "init"], "returncode": 0, "stdout": ""},
        {"argv": ["python3", "/opt/x/cli.py", "seal"], "returncode": 0, "stdout": doc["trailer"]},
        {"argv": ["python3", "/opt/x/cli.py", "validate"], "returncode": 1 if failed_entry else 0, "stdout": ""},
    ]
    repairs = ["cmd_a: first cause", "cmd_b: second cause"]
    commands_path = put(stage, "commands.json", recorded)
    repairs_path = put(stage, "repairs.json", repairs)
    target = stage / "report.json"
    tail = ["export-report", "--config", "config.json", "--commands", str(commands_path), "--repairs",
            str(repairs_path), "--out", str(target)]
    result = run_cli(root, *tail, cwd=stage)
    if not succeeded(result) or result.stdout != "":
        return None
    return load_json(target), tail, stage, raw, recorded, repairs


@criterion(description="the delivered export-report writes the report schema with the absolute config path, the digest of the file bytes, the given entries and repairs, and its own entry last, starting with the interpreter and the absolute cli.py")
def delivered_cli_export_report_writes_the_report_schema(workspace: Path) -> bool:
    try:
        root = unpack_tool(workspace)
        outcome = run_export_report(root, failed_entry=False) if root is not None else None
        if outcome is None:
            return False
        report, tail, stage, raw, recorded, repairs = outcome
        if not isinstance(report, dict) or sorted(report) != sorted(REPORT_FIELDS):
            return False
        if report["ok"] is not True or report["tool"] != TOOL_NAME or report["repairs"] != repairs:
            return False
        if report["config_path"] != str(stage / "config.json") or report["config_sha256"] != hashlib.sha256(raw).hexdigest():
            return False
        if report["trailer"] != with_seal(CONFIG_QX7_FIELDS)["trailer"]:
            return False
        commands = report["commands"]
        if not isinstance(commands, list) or len(commands) != len(recorded) + 1 or commands[:-1] != recorded:
            return False
        own = commands[-1]
        if not isinstance(own, dict) or sorted(own) != ["argv", "returncode", "stdout"]:
            return False
        if own["returncode"] != 0 or isinstance(own["returncode"], bool) or own["stdout"] != "":
            return False
        # The exact vector, interpreter options included, is graded separately by
        # delivered_cli_export_report_records_interpreter_argv.
        return argv_layout(own["argv"]) is not None
    except Exception:
        return False


@criterion(description="the delivered export-report writes ok false when a recorded command exited non-zero")
def delivered_cli_export_report_marks_failed_runs(workspace: Path) -> bool:
    try:
        root = unpack_tool(workspace)
        outcome = run_export_report(root, failed_entry=True) if root is not None else None
        return outcome is not None and isinstance(outcome[0], dict) and outcome[0].get("ok") is False
    except Exception:
        return False


def run_export_without(root: Path, omit: tuple[str, ...]) -> tuple[subprocess.CompletedProcess[str] | None, Path, list[str]]:
    """Drive the delivered export-report on a sealed config, leaving out the named options."""
    stage = work_dir()
    config = put(stage, "config.json", canonical_bytes(with_seal(CONFIG_QX7_FIELDS)))
    target = stage / "report.json"
    tail = ["export-report", "--config", str(config)]
    if "--commands" not in omit:
        tail += ["--commands", str(put(stage, "commands.json", []))]
    if "--repairs" not in omit:
        tail += ["--repairs", str(put(stage, "repairs.json", ["cmd_a: first cause"]))]
    tail += ["--out", str(target)]
    return run_cli(root, *tail), target, tail


@criterion(description="the delivered export-report treats a missing --commands or --repairs as a usage error and writes no report, while the full call succeeds")
def delivered_cli_export_report_requires_commands_and_repairs(workspace: Path) -> bool:
    try:
        root = unpack_tool(workspace)
        if root is None:
            return False
        for omit in (("--commands",), ("--repairs",), ("--commands", "--repairs")):
            result, target, _ = run_export_without(root, omit)
            if not usage_error(result) or os.path.lexists(target):
                return False
        # Control: with both inputs the same call succeeds, so refusing everything earns nothing.
        result, target, _ = run_export_without(root, ())
        return succeeded(result) and target.is_file()
    except Exception:
        return False


@criterion(description="the delivered export-report records as its own argv the full vector the interpreter received, interpreter options included")
def delivered_cli_export_report_records_interpreter_argv(workspace: Path) -> bool:
    try:
        root = unpack_tool(workspace)
        if root is None:
            return False
        result, target, tail = run_export_without(root, ())
        if not succeeded(result):
            return False
        report = load_json(target)
        own = report["commands"][-1]["argv"] if isinstance(report, dict) and report.get("commands") else None
        # cli_command_contract.export-report: argv is the vector "as the interpreter received it",
        # so the -E -s the check launched it with sit between the interpreter and cli.py.
        return argv_layout(own) is not None and own[1:] == [*INTERPRETER_OPTIONS, str(root / "cli.py"), *tail]
    except Exception:
        return False


@criterion(description="config.json carries a nested object or list as a value")
def negative_nested_config_value(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    try:
        data = load_json(artifact(workspace, "config.json"))
        return isinstance(data, dict) and any(isinstance(value, (dict, list)) for value in data.values())
    except Exception:
        return False


@criterion(description="config.json, report.json, validation_report.json or summary.json carries a key the published forbidden_keys list names")
def negative_forbidden_key_in_documents(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    try:
        for name in FORBIDDEN_KEY_DOCUMENTS:
            keys, _ = json_keys_and_strings(load_json(artifact(workspace, name)))
            if keys & FORBIDDEN_KEYS:
                return True
        return False
    except Exception:
        return False


@criterion(description="the delivered CLI writes a shipped-only value such as TASK or the shipped producer into documents built from other inputs")
def negative_shipped_values_hardcoded_in_cli(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    try:
        root = unpack_tool(workspace)
        if root is None:
            return False
        written: list[bytes] = []
        stage = work_dir()
        config = init_and_set(root, stage, SCHEMA_QX7, DEFAULTS_QX7, NUMBER_FIELDS)
        if config is not None:
            written.append(read_regular_bytes(config) or b"")
        graph = graph_outputs(str(root))
        if graph is not None:
            written.extend(canonical_bytes(doc) for _, doc in sorted(graph[1].items()) if doc is not None)
        return any(marker in raw for raw in written for marker in SHIPPED_MARKERS)
    except Exception:
        return False


@criterion(description="the delivered tool imports a module outside the standard library and its own files")
def negative_non_stdlib_import_in_tool(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    try:
        root = unpack_tool(workspace)
        if root is None:
            return False
        local = {path.stem for path in root.glob("*.py")} | {path.name for path in root.iterdir() if path.is_dir()}
        allowed = set(sys.stdlib_module_names) | local
        for source in sorted(root.rglob("*.py")):
            try:
                tree = ast.parse(source.read_text(encoding="utf-8"))
            except (OSError, ValueError, SyntaxError, MemoryError, RecursionError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    if any(alias.name.split(".")[0] not in allowed for alias in node.names):
                        return True
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    head = (node.module or "").split(".")[0]
                    if head and head not in allowed:
                        return True
        return False
    except Exception:
        return False


@criterion(description="config.json or report.json breaks the published document_rules with a string holding :// or a credential-named key")
def negative_url_or_credential_in_documents(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    try:
        for name in ("config.json", "report.json"):
            keys, strings = json_keys_and_strings(load_json(artifact(workspace, name)))
            if keys & CREDENTIAL_KEYS:
                return True
            if any("://" in text for text in strings):
                return True
        return False
    except Exception:
        return False


criteria.artifacts_present(weight=1)
criteria.config_identity_matches_policy(weight=3)
criteria.config_integers_match_policy(weight=3)
criteria.config_trailer_is_its_seal(weight=1)
criteria.config_bytes_are_canonical(weight=1)
criteria.profile_dev_values_follow_its_chain(weight=3)
criteria.profile_prod_values_follow_its_chain(weight=3)
criteria.profile_trailers_chain_from_the_config(weight=3)
criteria.delivered_profiles_come_from_delivered_cli(weight=5)
criteria.report_records_the_published_transcript(weight=3)
criteria.report_digest_matches_delivered_config(weight=1)
criteria.report_transcript_replays_with_delivered_cli(weight=5)
criteria.validation_report_tells_the_truth(weight=3)
criteria.summary_inventories_inputs_and_artifacts(weight=3)
criteria.delivered_archive_is_flat_and_safe(weight=1)
criteria.delivered_cli_reports_usage_errors(weight=1)
criteria.delivered_cli_init_takes_identity_from_schema_and_defaults(weight=3)
criteria.delivered_cli_reads_inputs_by_the_input_rules(weight=3)
criteria.delivered_cli_set_stores_exact_integers(weight=3)
criteria.delivered_cli_set_refuses_invalid_input(weight=3)
criteria.delivered_cli_writes_canonical_bytes(weight=5)
criteria.delivered_cli_seal_writes_the_crc32_trailer(weight=5)
criteria.delivered_cli_validate_accepts_conforming_configs(weight=3)
criteria.delivered_cli_validate_rejects_nonconforming_configs(weight=5)
criteria.delivered_cli_profile_resolves_inheritance_chains(weight=5)
criteria.delivered_cli_profile_chains_trailers(weight=3)
criteria.delivered_cli_profile_refuses_broken_chains(weight=1)
criteria.delivered_cli_export_report_writes_the_report_schema(weight=3)
criteria.delivered_cli_export_report_marks_failed_runs(weight=1)
criteria.delivered_cli_export_report_requires_commands_and_repairs(weight=5)
criteria.delivered_cli_export_report_records_interpreter_argv(weight=5)
criteria.negative_nested_config_value(weight=-5)
criteria.negative_forbidden_key_in_documents(weight=-3)
criteria.negative_shipped_values_hardcoded_in_cli(weight=-5)
criteria.negative_non_stdlib_import_in_tool(weight=-3)
criteria.negative_url_or_credential_in_documents(weight=-3)
