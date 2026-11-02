"""Verifier for the {{FORMAT_TAG}} cli-config task.

Negative tests use polarity inversion: their assertions hold when a cheat is
present, so honest submissions fail those tests and avoid the negative weight.
"""

from __future__ import annotations

import hashlib
import base64
import json
import zlib
import os
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from rewardkit import criteria, criterion

CONFIG_PATH = Path("/app/out/config.json")
REPORT_PATH = Path("/app/out/report.json")
TOOL_ARCHIVE = Path("/app/out/tool.zip")
PROFILE_DEV_PATH = Path("/app/out/profile_dev.json")
PROFILE_PROD_PATH = Path("/app/out/profile_prod.json")
VALIDATION_REPORT_PATH = Path("/app/out/validation_report.json")
SUMMARY_PATH = Path("/app/out/summary.json")
ARTIFACT_PATHS = [CONFIG_PATH, REPORT_PATH, TOOL_ARCHIVE, PROFILE_DEV_PATH, PROFILE_PROD_PATH, VALIDATION_REPORT_PATH, SUMMARY_PATH]
ARTIFACT_NAMES = ["config.json", "report.json", "tool.zip", "profile_dev.json", "profile_prod.json", "validation_report.json", "summary.json"]
_TOOL_ROOT: Path | None = None
EVAL_SEED = {{EVAL_SEED}}
FORMAT_TAG = "{{FORMAT_TAG}}"
TRAILER = "{{CLI_TRAILER}}"
MAX_RECORDS_BASE = {{CLI_MAX_RECORDS_BASE}}
RETRY_LIMIT_BASE = {{CLI_RETRY_LIMIT_BASE}}
TIMEOUT_MS_BASE = {{CLI_TIMEOUT_MS_BASE}}
_UNTRUSTED_UID = 65532
_UNTRUSTED_GID = 65532
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]


_SHIPPED_DATA: dict[str, str] = {{SHIPPED_DATA}}
_DATA_CACHE: list[Path] = []
_INT_KEYS = ("max_records", "retry_limit", "timeout_ms")


def _data_dir() -> Path:
    """The agent's /app/data, rebuilt here: the verifier container never has it."""
    if not _DATA_CACHE:
        root = Path(tempfile.mkdtemp(prefix="shipped-data-"))
        for rel, blob in _SHIPPED_DATA.items():
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zlib.decompress(base64.b64decode(blob)))
        _DATA_CACHE.append(root)
    return _DATA_CACHE[0]


def _shipped(name: str) -> Any:
    return json.loads((_data_dir() / name).read_text(encoding="utf-8"))


def _journal() -> list[dict[str, Any]]:
    ops = [json.loads(line) for line in (_data_dir() / "change_journal.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    return sorted(ops, key=lambda op: op["seq"])


def _valid(op: dict[str, Any], rules: dict[str, Any]) -> bool:
    if op["env"] not in rules["journal_envs"]:
        return False
    if op["key"] == "mode":
        return op["value"] in rules["allowed_modes"]
    if op["key"] in _INT_KEYS:
        low, high = rules["bounds"][op["key"]]
        return type(op["value"]) is int and low <= op["value"] <= high
    return False


def _apply(config: dict[str, Any], env: str) -> dict[str, Any]:
    rules = _shipped("validation_rules.json")
    for op in _journal():
        if op["env"] == env and _valid(op, rules):
            config[op["key"]] = op["value"]
    return config


def rejected_ops() -> list[int]:
    rules = _shipped("validation_rules.json")
    return [op["seq"] for op in _journal() if not _valid(op, rules)]


def expected_config() -> dict[str, Any]:
    defaults = _shipped("defaults.json")
    schema = _shipped("config_schema.json")
    config = {
        "checksum": defaults["checksum"],
        "container": schema["container"],
        "mode": defaults["mode"],
        "producer": schema["producer"],
        "profile": schema["profile"],
        **defaults["base_config"],
    }
    return _apply(config, "base")


def expected_profile(name: str) -> dict[str, Any]:
    config = dict(expected_config())
    sample = _shipped(f"sample_config_{name}.json")
    override = _shipped("env_overrides.json")[name]
    config["max_records"] += int(sample["max_records_delta"])
    config["checksum"] = sample["checksum"]
    config["retry_limit"] += int(override["retry_limit_delta"])
    config["timeout_ms"] += int(override["timeout_ms_delta"])
    config["mode"] = override["mode"]
    config["profile"] = f"{config['profile']}-{name}"
    config["trailer"] = f"{config['trailer']}:{name}"
    return _apply(config, name)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def root_only_tests_present() -> bool:
    try:
        status = Path("/tests").stat()
    except FileNotFoundError:
        return False
    return status.st_uid == 0 and (status.st_mode & 0o077) == 0


def untrusted_kwargs() -> dict[str, Any]:
    if os.name != "posix":
        if root_only_tests_present():
            raise RuntimeError("POSIX uid isolation is required")
        return {}
    if os.geteuid() != 0 and root_only_tests_present():
        raise RuntimeError("verifier must run as root to isolate /tests")
    return {}


def _grant_read(argument: str) -> None:
    """Make an agent-written path readable before the uid drop.

    Agent editors write through a temp file in the same directory and rename it,
    so a program the agent wrote can land at mode 0600 (owner-only). The checks
    run that program as an unprivileged user, which then cannot open it, and a
    correct submission would score zero for a reason that has nothing to do with
    the task. The verifier runs as root, so widening the mode is always allowed
    here and it changes no graded content.
    """
    if not argument.startswith("/app"):
        return
    path = Path(argument)
    if not path.exists():
        return
    try:
        path.chmod(path.stat().st_mode | (0o555 if path.is_dir() else 0o444))
        for parent in path.parents:
            parent.chmod(parent.stat().st_mode | 0o555)
            if str(parent) == "/app":
                break
    except OSError:
        pass


def untrusted_command(command: list[str]) -> list[str]:
    if os.name == "posix" and os.geteuid() == 0:
        for argument in command:
            _grant_read(argument)
        return [*_SETPRIV, *command]
    return command


def tool_root() -> Path:
    global _TOOL_ROOT
    if _TOOL_ROOT is not None:
        return _TOOL_ROOT
    root = Path(tempfile.mkdtemp(prefix="cli-config-tool-"))
    root.chmod(0o755)
    with zipfile.ZipFile(TOOL_ARCHIVE) as zf:
        names: set[str] = set()
        for info in zf.infolist():
            rel = Path(info.filename)
            assert not rel.is_absolute() and ".." not in rel.parts and "\\" not in info.filename
            assert info.filename not in names
            names.add(info.filename)
            dest = root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(zf.read(info))
            dest.chmod(0o644)
    _TOOL_ROOT = root
    return root


def tool_path() -> Path:
    return tool_root() / "cli.py"


def schema_path() -> Path:
    return tool_root() / "schema.json"


def run_repaired_cli(*args: str) -> subprocess.CompletedProcess[str]:
    path = tool_path()
    assert path.is_file(), "repaired CLI source is missing from tool.zip"
    kwargs: dict[str, Any] = {
        "cwd": "/tmp",
        "text": True,
        "capture_output": True,
        "timeout": 20,
        "env": {"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONHASHSEED": "0", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
    }
    return subprocess.run(untrusted_command([sys.executable, "-I", str(path), *args]), **kwargs)


def source_text() -> str:
    path = tool_path()
    if not path.exists():
        return ""
    chunks = [path.read_text(encoding="utf-8", errors="replace")]
    schema = schema_path()
    if schema.exists():
        chunks.append(schema.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)


def _check_artifacts_exist():
    """POSITIVE: all declared artifacts exist and are non-empty."""
    for path in ARTIFACT_PATHS:
        assert path.is_file(), f"missing {path}"
        assert path.stat().st_size > 0, f"empty {path}"
    assert CONFIG_PATH.stat().st_size > 100
    assert REPORT_PATH.stat().st_size > 200


def _check_config_is_flat_json_object():
    """POSITIVE: config.json is one flat object with scalar values only."""
    data = load_json(CONFIG_PATH)
    assert isinstance(data, dict)
    assert set(data) == set(expected_config())
    assert all(not isinstance(value, (dict, list)) for value in data.values())
    assert all(isinstance(key, str) and key == key.strip() and key.lower() == key for key in data)


def _check_config_matches_hidden_seed_policy():
    """POSITIVE: flat config values match independently derived hidden policy."""
    assert load_json(CONFIG_PATH) == expected_config()


def _check_report_records_real_cli_commands():
    """POSITIVE: report contains successful local CLI command transcript."""
    report = load_json(REPORT_PATH)
    commands = report["commands"]
    assert report["ok"] is True
    assert report["tool"] == "{{PACKAGE_NAME}}-ctl"
    assert isinstance(commands, list) and len(commands) >= 6
    seen = "\n".join(" ".join(item.get("argv", [])) for item in commands)
    for subcommand in ("init", "set", "validate", "export-report"):
        assert subcommand in seen
    assert all(item.get("returncode") == 0 for item in commands)


def _check_report_is_deterministic_and_truthful():
    """POSITIVE: report digest and trailer describe the delivered config exactly."""
    report = load_json(REPORT_PATH)
    digest = hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest()
    assert report["config_sha256"] == digest
    assert report["trailer"] == TRAILER
    assert "generated_at" not in report and "timestamp" not in report


def _check_outputs_are_world_readable_regular_files():
    """POSITIVE: artifacts are regular files readable by the verifier."""
    for path in ARTIFACT_PATHS:
        status = path.stat()
        assert stat.S_ISREG(status.st_mode)
        assert status.st_mode & stat.S_IRUSR
        assert status.st_size < 1024 * 1024


def _check_no_external_network_endpoints_or_secrets():
    """POSITIVE: outputs contain no endpoint URLs, credentials, or secret material."""
    text = "".join(path.read_text(errors="ignore") for path in ARTIFACT_PATHS).lower()
    banned = ["http://", "https://", "token", "secret", "password", "api_key", "apikey", "credential"]
    assert not any(token in text for token in banned)


def _check_cli_source_was_repaired_not_bypassed():
    """POSITIVE: repaired CLI retains subcommands and deterministic flat validation."""
    text = source_text()
    for token in ("add_subparsers", "cmd_init", "cmd_set", "cmd_validate", "cmd_report", "sort_keys=True"):
        assert token in text
    assert "configuration must be flat" in text
    assert "args.config)  # BUG" not in text


def _check_config_round_trips_through_cli_validator():
    """POSITIVE: repaired CLI validates the delivered config when run unprivileged."""
    result = run_repaired_cli("validate", "--schema", str(schema_path()), "--config", str(CONFIG_PATH))
    assert result.returncode == 0, result.stderr or result.stdout
    assert result.stdout.strip() == "ok"


def _check_canonical_trailer_present():
    """POSITIVE: config carries the canonical seeded trailer once."""
    text = CONFIG_PATH.read_text(encoding="utf-8")
    assert load_json(CONFIG_PATH)["trailer"] == TRAILER
    assert text.count(TRAILER) == 1


def _check_profile_dev_matches_embedded_reference():
    """POSITIVE: dev profile artifact is normalized from sidecars and hidden policy."""
    data = load_json(PROFILE_DEV_PATH)
    assert data == expected_profile("dev")
    assert all(not isinstance(value, (dict, list)) for value in data.values())


def _check_profile_prod_matches_embedded_reference():
    """POSITIVE: prod profile artifact is normalized from sidecars and hidden policy."""
    data = load_json(PROFILE_PROD_PATH)
    assert data == expected_profile("prod")
    assert all(not isinstance(value, (dict, list)) for value in data.values())


def _check_validation_report_covers_all_artifacts_and_profiles():
    """POSITIVE: validation_report.json records deterministic coverage of profiles and artifacts."""
    report = load_json(VALIDATION_REPORT_PATH)
    checks = report["checks"]
    assert report["ok"] is True
    assert checks["all_artifacts_present"] is True
    assert checks["config_matches_policy"] is True
    assert checks["config_scalar_flat"] is True
    assert checks["command_failures"] == []
    assert checks["required_artifacts"] == ARTIFACT_NAMES
    assert set(checks["profiles"]) == {"dev", "prod"}
    assert checks["profiles"]["dev"]["trailer"] == f"{TRAILER}:dev"
    assert checks["profiles"]["prod"]["trailer"] == f"{TRAILER}:prod"
    assert checks["rejected_ops"] == rejected_ops()


def _check_summary_lists_inputs_profiles_and_artifacts():
    """POSITIVE: summary.json has exact artifact order and flat input inventory."""
    summary = load_json(SUMMARY_PATH)
    assert summary["artifact_count"] == 7
    assert summary["artifacts"] == ARTIFACT_NAMES
    assert summary["profiles"] == ["dev", "prod"]
    assert summary["format_tag"] == FORMAT_TAG
    assert summary["trailer"] == TRAILER
    assert summary["input_count"] >= 6
    assert summary["inputs"] == sorted(p.name for p in _data_dir().iterdir() if p.is_file())
    assert summary["input_count"] == len(summary["inputs"])


def _check_negative_weight_hardcoded_sample_answers():
    """NEGATIVE: fires when repaired source embeds hidden numeric policy constants."""
    text = source_text()
    markers = [str(EVAL_SEED), str(MAX_RECORDS_BASE), str(TIMEOUT_MS_BASE)]
    assert any(marker in text for marker in markers), "honest baseline: hidden policy is not embedded in CLI source"


def _check_negative_weight_nested_or_dynamic_config():
    """NEGATIVE: fires when config uses nested containers or nondeterministic fields."""
    data = load_json(CONFIG_PATH)
    dynamic = {"timestamp", "generated_at", "uuid", "random_seed"}
    assert any(isinstance(value, (dict, list)) for value in data.values()) or any(key in data for key in dynamic), "honest baseline: flat deterministic config"


def _check_negative_weight_fake_cli_transcript():
    """NEGATIVE: fires when report claims CLI use but no repaired CLI can validate."""
    report = load_json(REPORT_PATH) if REPORT_PATH.exists() else {}
    commands = report.get("commands")
    result = run_repaired_cli("validate", "--schema", str(schema_path()), "--config", str(CONFIG_PATH)) if TOOL_ARCHIVE.exists() else None
    assert commands and (result is None or result.returncode != 0), "honest baseline: transcript is backed by a working CLI"


def _check_negative_weight_network_or_secret_material():
    """NEGATIVE: fires on task-specific forbidden network or credential indicators."""
    text = (source_text() + CONFIG_PATH.read_text(errors="ignore") + REPORT_PATH.read_text(errors="ignore")).lower()
    assert any(token in text for token in ("requests", "urllib", "socket", "https://", "api_key", "password")), "honest baseline: offline local configuration"


if __name__ == "__main__":
    failures = 0
    for name in sorted(globals()):
        if name.startswith("test_"):
            try:
                globals()[name]()
            except Exception as exc:
                failures += 1
                print(f"FAIL {name}: {exc}")
            else:
                print(f"PASS {name}")
    raise SystemExit(1 if failures else 0)


def _holds(check) -> bool:
    try:
        check()
    except Exception:
        return False
    return True


@criterion(description="All declared artifacts exist and are non-empty.")
def artifacts_exist(workspace: Path) -> bool:
    return _holds(_check_artifacts_exist)


@criterion(description="Config.json is one flat object with scalar values only.")
def config_is_flat_json_object(workspace: Path) -> bool:
    return _holds(_check_config_is_flat_json_object)


@criterion(description="Flat config values match independently derived hidden policy.")
def config_matches_hidden_seed_policy(workspace: Path) -> bool:
    return _holds(_check_config_matches_hidden_seed_policy)


@criterion(description="Report contains successful local CLI command transcript.")
def report_records_real_cli_commands(workspace: Path) -> bool:
    return _holds(_check_report_records_real_cli_commands)


@criterion(description="Report digest and trailer describe the delivered config exactly.")
def report_is_deterministic_and_truthful(workspace: Path) -> bool:
    return _holds(_check_report_is_deterministic_and_truthful)


@criterion(description="Artifacts are regular files readable by the verifier.")
def outputs_are_world_readable_regular_files(workspace: Path) -> bool:
    return _holds(_check_outputs_are_world_readable_regular_files)


@criterion(description="Outputs contain no endpoint URLs, credentials, or secret material.")
def no_external_network_endpoints_or_secrets(workspace: Path) -> bool:
    return _holds(_check_no_external_network_endpoints_or_secrets)


@criterion(description="Repaired CLI retains subcommands and deterministic flat validation.")
def cli_source_was_repaired_not_bypassed(workspace: Path) -> bool:
    return _holds(_check_cli_source_was_repaired_not_bypassed)


@criterion(description="Repaired CLI validates the delivered config when run unprivileged.")
def config_round_trips_through_cli_validator(workspace: Path) -> bool:
    return _holds(_check_config_round_trips_through_cli_validator)


@criterion(description="Config carries the canonical seeded trailer once.")
def canonical_trailer_present(workspace: Path) -> bool:
    return _holds(_check_canonical_trailer_present)


@criterion(description="Dev profile artifact is normalized from sidecars and hidden policy.")
def profile_dev_matches_embedded_reference(workspace: Path) -> bool:
    return _holds(_check_profile_dev_matches_embedded_reference)


@criterion(description="Prod profile artifact is normalized from sidecars and hidden policy.")
def profile_prod_matches_embedded_reference(workspace: Path) -> bool:
    return _holds(_check_profile_prod_matches_embedded_reference)


@criterion(description="Validation_report.json records deterministic coverage of profiles and artifacts.")
def validation_report_covers_all_artifacts_and_profiles(workspace: Path) -> bool:
    return _holds(_check_validation_report_covers_all_artifacts_and_profiles)


@criterion(description="Summary.json has exact artifact order and flat input inventory.")
def summary_lists_inputs_profiles_and_artifacts(workspace: Path) -> bool:
    return _holds(_check_summary_lists_inputs_profiles_and_artifacts)


@criterion(description="Fires when repaired source embeds hidden numeric policy constants.")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    return _holds(_check_negative_weight_hardcoded_sample_answers)


@criterion(description="Fires when config uses nested containers or nondeterministic fields.")
def negative_nested_or_dynamic_config(workspace: Path) -> bool:
    return _holds(_check_negative_weight_nested_or_dynamic_config)


@criterion(description="Fires when report claims CLI use but no repaired CLI can validate.")
def negative_fake_cli_transcript(workspace: Path) -> bool:
    return _holds(_check_negative_weight_fake_cli_transcript)


@criterion(description="Fires on task-specific forbidden network or credential indicators.")
def negative_network_or_secret_material(workspace: Path) -> bool:
    return _holds(_check_negative_weight_network_or_secret_material)


criteria.artifacts_exist(weight=1)
criteria.config_is_flat_json_object(weight=3)
criteria.config_matches_hidden_seed_policy(weight=5)
criteria.report_records_real_cli_commands(weight=5)
criteria.report_is_deterministic_and_truthful(weight=3)
criteria.outputs_are_world_readable_regular_files(weight=1)
criteria.no_external_network_endpoints_or_secrets(weight=3)
criteria.cli_source_was_repaired_not_bypassed(weight=5)
criteria.config_round_trips_through_cli_validator(weight=5)
criteria.canonical_trailer_present(weight=3)
criteria.profile_dev_matches_embedded_reference(weight=3)
criteria.profile_prod_matches_embedded_reference(weight=3)
criteria.validation_report_covers_all_artifacts_and_profiles(weight=5)
criteria.summary_lists_inputs_profiles_and_artifacts(weight=3)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_nested_or_dynamic_config(weight=-5)
criteria.negative_fake_cli_transcript(weight=-3)
criteria.negative_network_or_secret_material(weight=-3)
