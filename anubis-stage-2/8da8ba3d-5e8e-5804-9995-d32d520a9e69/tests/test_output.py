"""Deterministic rewardkit criteria for the NONCE Ironvault Bastion cli-config task.

Each check is a top-level @criterion(description=...) function taking the
rewardkit ``workspace`` (the agent root, /app) and returning a bool. Positive
checks return True when the property holds. Negative checks use polarity
inversion: they return True only when the cheat is positively present, so an
honest submission returns False and avoids the negative weight. Every check is
guarded so bad, missing or hostile agent output yields False rather than an
exception, because an exception would abort the whole rewardkit run.

The verifier container has no /app/data mount (separate mode), so the two
contract files are embedded below as string constants and the expected derived
values are encoded as EXPECTED_* constants computed by the reference solution.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
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
    "policy_matrix.csv",
    "rate_limits.tsv",
    "rotation_schedule.yaml",
    "mfa_quorum.toml",
    "audit_sampling.ini",
    "threat_scores.jsonl",
    "cipher_priority.txt",
    "egress_allowlist.conf",
    "session_policy.xml",
    "trust_anchor_manifest.pem",
    "compliance_map.md",
    "attestation_ledger.log",
    "derived_metrics.env",
    "canary_thresholds.properties",
    "checksum_manifest.txt",
]

# Copies of environment/data/*.json; the verifier container has no /app/data mount.
SCHEMA_JSON_TEXT = """{
  "checksum": "sha256",
  "container": "vault-envelope",
  "mode": "strict-hardened",
  "producer": "Ironvault sealing service",
  "profile": "NONCE",
  "required_keys": "active_cipher_count,attestation_quorum,audit_sample_ratio_ppm,cert_expiring_soon,checksum,compliance_score,container,egress_rules_count,firewall_deny_count,hash_algo_score,mfa_quorum_threshold,mode,pbkdf_iterations,producer,profile,rate_limit_burst,rate_limit_rps,rbac_edge_count,secret_rotation_days,session_idle_timeout_seconds,session_ttl_seconds,threat_high_actors,token_entropy_bits,trailer,trust_anchor_score",
  "trailer": "harbor:cli-config:NONCE:001e28a70d5f8b91"
}
"""

RULES_JSON_TEXT = """{
  "numeric_bounds": {
    "attestation_quorum": [1, 128],
    "audit_sample_ratio_ppm": [1, 1000000],
    "pbkdf_iterations": [50000, 100000000],
    "rate_limit_rps": [1, 1000000],
    "session_ttl_seconds": [60, 86400],
    "token_entropy_bits": [64, 4096]
  },
  "profiles": ["dev", "prod"],
  "required_artifacts": [
    "config.json", "report.json", "tool.zip",
    "profile_dev.json", "profile_prod.json",
    "validation_report.json", "summary.json",
    "policy_matrix.csv", "rate_limits.tsv", "rotation_schedule.yaml",
    "mfa_quorum.toml", "audit_sampling.ini", "threat_scores.jsonl",
    "cipher_priority.txt", "egress_allowlist.conf", "session_policy.xml",
    "trust_anchor_manifest.pem", "compliance_map.md", "attestation_ledger.log",
    "derived_metrics.env", "canary_thresholds.properties", "checksum_manifest.txt"
  ]
}
"""

# Sample-hint values embedded so the hardcoding negative can fire independently
# of the agent container.
SAMPLE_HINT_STRINGS = {
    "NONCE-dev",
    "NONCE-prod",
    "reference sample for dev - values here are HINTS ONLY and must be derived, not copied.",
    "reference sample for prod - values here are HINTS ONLY and must be derived, not copied.",
}

EXPECTED_CONFIG = {
    "active_cipher_count": 154,
    "attestation_quorum": 44,
    "audit_sample_ratio_ppm": 23578,
    "cert_expiring_soon": 7,
    "checksum": "sha256",
    "compliance_score": 548,
    "container": "vault-envelope",
    "egress_rules_count": 129,
    "firewall_deny_count": 55,
    "hash_algo_score": 1078,
    "mfa_quorum_threshold": 148,
    "mode": "strict-hardened",
    "pbkdf_iterations": 3200000,
    "producer": "Ironvault sealing service",
    "profile": "NONCE",
    "rate_limit_burst": 4467,
    "rate_limit_rps": 1489,
    "rbac_edge_count": 86,
    "secret_rotation_days": 7,
    "session_idle_timeout_seconds": 161,
    "session_ttl_seconds": 1094,
    "threat_high_actors": 36,
    "token_entropy_bits": 768,
    "trailer": "harbor:cli-config:NONCE:001e28a70d5f8b91",
    "trust_anchor_score": 936,
}

EXPECTED_PROFILE_DEV = {
    "active_cipher_count": 154,
    "attestation_quorum": 44,
    "audit_sample_ratio_ppm": 23578,
    "cert_expiring_soon": 7,
    "checksum": "sha256",
    "compliance_score": 548,
    "container": "vault-envelope",
    "egress_rules_count": 129,
    "firewall_deny_count": 55,
    "hash_algo_score": 1078,
    "mfa_quorum_threshold": 147,
    "mode": "strict-hardened",
    "pbkdf_iterations": 1600000,
    "producer": "Ironvault sealing service",
    "profile": "NONCE-dev",
    "rate_limit_burst": 4167,
    "rate_limit_rps": 1389,
    "rbac_edge_count": 86,
    "secret_rotation_days": 7,
    "session_idle_timeout_seconds": 41,
    "session_ttl_seconds": 194,
    "threat_high_actors": 36,
    "token_entropy_bits": 768,
    "trailer": "harbor:cli-config:NONCE:001e28a70d5f8b91:dev",
    "trust_anchor_score": 936,
}

EXPECTED_PROFILE_PROD = {
    "active_cipher_count": 154,
    "attestation_quorum": 44,
    "audit_sample_ratio_ppm": 23578,
    "cert_expiring_soon": 7,
    "checksum": "sha256",
    "compliance_score": 548,
    "container": "vault-envelope",
    "egress_rules_count": 129,
    "firewall_deny_count": 55,
    "hash_algo_score": 1078,
    "mfa_quorum_threshold": 150,
    "mode": "strict-hardened",
    "pbkdf_iterations": 6400000,
    "producer": "Ironvault sealing service",
    "profile": "NONCE-prod",
    "rate_limit_burst": 5217,
    "rate_limit_rps": 1739,
    "rbac_edge_count": 86,
    "secret_rotation_days": 7,
    "session_idle_timeout_seconds": 401,
    "session_ttl_seconds": 2594,
    "threat_high_actors": 36,
    "token_entropy_bits": 768,
    "trailer": "harbor:cli-config:NONCE:001e28a70d5f8b91:prod",
    "trust_anchor_score": 936,
}

# --- hardening limits for archive expansion and subprocess capture ---
_ZIP_MAX_MEMBERS = 64
_ZIP_MAX_EXPANDED = 8 * 1024 * 1024
_ZIP_MAX_RATIO = 100
_SUBPROC_MAX_OUTPUT = 1 * 1024 * 1024
_SUBPROC_TIMEOUT = 90

# sha256 of the shipped broken /app/data/tool.zip's cli.py, embedded because the
# verifier runs in separate mode with no /app/data mount. Used by
# negative_delivered_cli_py_is_unrepaired to catch an unrepaired byte-copy.
_SHIPPED_CLI_SHA256 = "cebec28b59f1b77653c170190a89cb40e5c8e3fdb23490d6b8b05500d15bf540"


def out_dir(workspace: Path) -> Path:
    return Path(workspace) / "out"


def _grant_read(path: Path) -> None:
    """Make an agent-written path readable before the setpriv uid drop.

    Agents can leave files at mode 0600 (editor-style rename-into-place). The
    setpriv-dropped child then cannot open them. The verifier runs as root, so
    widening the mode is always allowed and changes no graded content.
    """
    try:
        if not path.exists():
            return
        path.chmod(path.stat().st_mode | (0o555 if path.is_dir() else 0o444))
        for parent in path.parents:
            if str(parent) in {"/", "/tmp"}:
                break
            try:
                parent.chmod(parent.stat().st_mode | 0o555)
            except OSError:
                pass
            if str(parent) == "/app":
                break
    except OSError:
        pass


def load_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


_TOOL_ROOT: Path | None = None


def tool_root(workspace: Path) -> Path:
    global _TOOL_ROOT
    if _TOOL_ROOT is not None:
        return _TOOL_ROOT
    archive = out_dir(workspace) / "tool.zip"
    root = Path(tempfile.mkdtemp(prefix="nonce-tool-"))
    root.chmod(0o755)
    with zipfile.ZipFile(archive) as zf:
        infos = zf.infolist()
        if len(infos) > _ZIP_MAX_MEMBERS:
            raise ValueError(f"tool.zip has too many members ({len(infos)})")
        total_expanded = 0
        for info in infos:
            rel = Path(info.filename)
            if rel.is_absolute() or ".." in rel.parts:
                raise ValueError(f"unsafe member {info.filename!r}")
            if info.is_dir():
                (root / rel).mkdir(parents=True, exist_ok=True)
                continue
            if info.file_size > _ZIP_MAX_EXPANDED:
                raise ValueError("member too large")
            if info.compress_size > 0:
                ratio = info.file_size / max(1, info.compress_size)
                if ratio > _ZIP_MAX_RATIO:
                    raise ValueError(f"suspicious compression ratio {ratio}")
            total_expanded += info.file_size
            if total_expanded > _ZIP_MAX_EXPANDED:
                raise ValueError("tool.zip expands to too many bytes")
            dest = root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(zf.read(info))
            dest.chmod(0o644)
    for path in [root, *root.rglob("*")]:
        if path.is_dir():
            path.chmod(0o755)
        else:
            path.chmod(0o644)
    try:
        shutil.chown(root, user="nobody", group="nogroup")
        for path in root.rglob("*"):
            shutil.chown(path, user="nobody", group="nogroup")
    except (LookupError, PermissionError, OSError):
        pass
    _TOOL_ROOT = root
    return root


def tool_source(workspace: Path) -> str:
    try:
        cli = tool_root(workspace) / "cli.py"
        if not cli.exists():
            return ""
        return cli.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _setpriv_prefix() -> list[str]:
    if os.geteuid() != 0:
        return []
    if not Path("/usr/bin/setpriv").is_file():
        return []
    try:
        import grp
        import pwd

        pwd.getpwnam("nobody")
        grp.getgrnam("nogroup")
    except (KeyError, ImportError):
        return []
    return ["/usr/bin/setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups", "--"]


def run_repaired_cli(workspace: Path, *args: str) -> subprocess.CompletedProcess[str]:
    root = tool_root(workspace)
    cli = root / "cli.py"
    if not cli.is_file():
        raise FileNotFoundError("repaired cli.py missing from tool.zip")
    argv = [*_setpriv_prefix(), sys.executable, "-I", str(cli), *args]
    proc = subprocess.Popen(
        argv,
        cwd="/tmp",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
        env={
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "PYTHONHASHSEED": "0",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
        },
    )
    try:
        stdout, stderr = proc.communicate(timeout=_SUBPROC_TIMEOUT)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        proc.wait()
        raise
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    stdout = (stdout or "")[:_SUBPROC_MAX_OUTPUT]
    stderr = (stderr or "")[:_SUBPROC_MAX_OUTPUT]
    return subprocess.CompletedProcess(argv, proc.returncode, stdout, stderr)


@criterion(description="every declared /app/out artifact exists as a non-empty readable regular file")
def all_artifacts_present_and_regular_files(workspace: Path) -> bool:
    try:
        out = out_dir(workspace)
        for name in ARTIFACT_NAMES:
            path = out / name
            if not path.is_file():
                return False
            st = path.stat()
            if not stat.S_ISREG(st.st_mode):
                return False
            if st.st_size <= 0:
                return False
            if not (st.st_mode & stat.S_IRUSR):
                return False
        return True
    except Exception:
        return False


@criterion(description="config.json contains every schema-required key with scalar-typed values")
def config_key_set_and_types(workspace: Path) -> bool:
    try:
        cfg = load_json(out_dir(workspace) / "config.json")
        if not isinstance(cfg, dict):
            return False
        if not set(EXPECTED_CONFIG).issubset(set(cfg)):
            return False
        for value in cfg.values():
            if isinstance(value, (dict, list)):
                return False
        for key, expected in EXPECTED_CONFIG.items():
            if not isinstance(cfg[key], type(expected)):
                return False
        return True
    except Exception:
        return False


@criterion(description="config.json equals the expected derivation over the input corpus")
def config_matches_expected_derived_values(workspace: Path) -> bool:
    try:
        cfg = load_json(out_dir(workspace) / "config.json")
        return all(cfg.get(key) == expected for key, expected in EXPECTED_CONFIG.items())
    except Exception:
        return False


@criterion(description="config.json is emitted with sort_keys, two-space indent and a trailing newline")
def config_is_sort_keys_two_space_indented(workspace: Path) -> bool:
    try:
        text = (out_dir(workspace) / "config.json").read_text(encoding="utf-8")
        if not text.endswith("\n"):
            return False
        parsed = json.loads(text)
        round_tripped = json.dumps(parsed, indent=2, sort_keys=True) + "\n"
        return text == round_tripped
    except Exception:
        return False


@criterion(description="profile_dev.json equals the expected dev profile after overrides and hardening")
def profile_dev_matches_expected(workspace: Path) -> bool:
    try:
        dev = load_json(out_dir(workspace) / "profile_dev.json")
        return all(dev.get(key) == expected for key, expected in EXPECTED_PROFILE_DEV.items())
    except Exception:
        return False


@criterion(description="profile_prod.json equals the expected prod profile after overrides and hardening")
def profile_prod_matches_expected(workspace: Path) -> bool:
    try:
        prod = load_json(out_dir(workspace) / "profile_prod.json")
        return all(prod.get(key) == expected for key, expected in EXPECTED_PROFILE_PROD.items())
    except Exception:
        return False


@criterion(description="dev and prod profiles carry the base trailer with the dev and prod suffixes")
def profiles_have_profile_specific_trailer_suffix(workspace: Path) -> bool:
    try:
        out = out_dir(workspace)
        dev = load_json(out / "profile_dev.json")
        prod = load_json(out / "profile_prod.json")
        base = load_json(out / "config.json")["trailer"]
        return (
            dev["trailer"].endswith(":dev")
            and prod["trailer"].endswith(":prod")
            and dev["trailer"] == f"{base}:dev"
            and prod["trailer"] == f"{base}:prod"
        )
    except Exception:
        return False


@criterion(description="pbkdf_iterations is base times a power of two and profiles halve and double it")
def pbkdf_iterations_obeys_power_of_two_multiplier_law(workspace: Path) -> bool:
    try:
        out = out_dir(workspace)
        cfg = load_json(out / "config.json")
        dev = load_json(out / "profile_dev.json")
        prod = load_json(out / "profile_prod.json")
        if cfg["pbkdf_iterations"] % 100000 != 0:
            return False
        ratio = cfg["pbkdf_iterations"] // 100000
        if not (ratio > 1 and (ratio & (ratio - 1)) == 0):
            return False
        return (
            dev["pbkdf_iterations"] * 2 == cfg["pbkdf_iterations"]
            and prod["pbkdf_iterations"] == cfg["pbkdf_iterations"] * 2
        )
    except Exception:
        return False


@criterion(description="rate_limit_burst equals rate_limit_rps times three across config and both profiles")
def rate_limit_burst_is_three_times_rps(workspace: Path) -> bool:
    try:
        out = out_dir(workspace)
        cfg = load_json(out / "config.json")
        dev = load_json(out / "profile_dev.json")
        prod = load_json(out / "profile_prod.json")
        return (
            cfg["rate_limit_burst"] == cfg["rate_limit_rps"] * 3
            and dev["rate_limit_burst"] == dev["rate_limit_rps"] * 3
            and prod["rate_limit_burst"] == prod["rate_limit_rps"] * 3
        )
    except Exception:
        return False


@criterion(description="report.json covers every pipeline subcommand kind with a runnable init round-trip")
def report_records_full_cli_transcript(workspace: Path) -> bool:
    try:
        report = load_json(out_dir(workspace) / "report.json")
        if report.get("ok") is not True:
            return False
        if report.get("tool") != "nonce-ctl":
            return False
        commands = report.get("commands")
        # Instruction minimum: 1 init + 1 derive + 1 validate + 2 emit-profile + >=3 emit-artifact + 1 export-report = 9
        if not isinstance(commands, list) or len(commands) < 9:
            return False
        for item in commands:
            if not set(item).issuperset({"argv", "returncode", "stdout"}):
                return False
            if not isinstance(item["argv"], list) or not item["argv"]:
                return False
            if not isinstance(item["returncode"], int):
                return False
        seen = "\n".join(" ".join(item["argv"]) for item in commands)
        for subcommand in ("init", "derive", "validate", "emit-profile", "emit-artifact", "export-report"):
            if subcommand not in seen:
                return False
        root = tool_root(workspace)
        schema = root / "config_schema.json"
        schema.write_text(SCHEMA_JSON_TEXT, encoding="utf-8")
        result_out = root / "config_init.json"
        result = run_repaired_cli(workspace, "init", "--schema", str(schema), "--out", str(result_out))
        if result.returncode != 0:
            return False
        initialized = json.loads(result_out.read_text(encoding="utf-8"))
        if not isinstance(initialized, dict):
            return False
        return all(not isinstance(v, (dict, list)) for v in initialized.values())
    except Exception:
        return False


@criterion(description="report.json config_sha256 equals sha256 of the delivered config.json bytes and trailer matches")
def report_digest_matches_config_bytes(workspace: Path) -> bool:
    try:
        out = out_dir(workspace)
        report = load_json(out / "report.json")
        digest = hashlib.sha256((out / "config.json").read_bytes()).hexdigest()
        return report.get("config_sha256") == digest and report.get("trailer") == EXPECTED_CONFIG["trailer"]
    except Exception:
        return False


@criterion(description="policy_matrix.csv is a binary RBAC matrix over sorted active roles and permissions")
def policy_matrix_dimensions_and_binary_cells(workspace: Path) -> bool:
    try:
        lines = (out_dir(workspace) / "policy_matrix.csv").read_text(encoding="utf-8").splitlines()
        if len(lines) < 2:
            return False
        header = lines[0].split(",")
        if header[0] != "role_id":
            return False
        perm_cols = header[1:]
        if not all(re.fullmatch(r"perm-\d{4}", col) for col in perm_cols):
            return False
        if perm_cols != sorted(perm_cols):
            return False
        row_ids = []
        for row in lines[1:]:
            cells = row.split(",")
            if len(cells) != len(header):
                return False
            if not re.fullmatch(r"role-\d{4}", cells[0]):
                return False
            row_ids.append(cells[0])
            for cell in cells[1:]:
                if cell not in {"0", "1"}:
                    return False
        return row_ids == sorted(row_ids)
    except Exception:
        return False


@criterion(description="rate_limits.tsv restricts to internal and admin zones, is sorted, and reports numeric fields")
def rate_limits_tsv_shape_and_sorted(workspace: Path) -> bool:
    try:
        lines = (out_dir(workspace) / "rate_limits.tsv").read_text(encoding="utf-8").splitlines()
        if lines[0] != "endpoint\tzone\teffective_rps\tconcurrency_delta":
            return False
        endpoints = []
        for row in lines[1:]:
            parts = row.split("\t")
            if len(parts) != 4:
                return False
            endpoint, zone, eff, delta = parts
            if zone not in {"internal", "admin"}:
                return False
            int(eff)
            int(delta)
            endpoints.append(endpoint)
        return endpoints == sorted(endpoints)
    except Exception:
        return False


@criterion(description="rotation_schedule.yaml lists required-only secret classes in ascending class_id order")
def rotation_schedule_only_required_classes_sorted(workspace: Path) -> bool:
    try:
        text = (out_dir(workspace) / "rotation_schedule.yaml").read_text(encoding="utf-8")
        if not text.startswith("# secret rotation schedule (required classes only)"):
            return False
        ids = re.findall(r"^\s*- class_id: (secret-class-\d{4})$", text, re.MULTILINE)
        if not ids or ids != sorted(ids):
            return False
        kinds = re.findall(r"^\s*kind: (\w+)$", text, re.MULTILINE)
        return len(kinds) == len(ids)
    except Exception:
        return False


@criterion(description="mfa_quorum.toml quorum_threshold equals the config value and the sum of factor weights")
def mfa_quorum_toml_matches_config(workspace: Path) -> bool:
    try:
        text = (out_dir(workspace) / "mfa_quorum.toml").read_text(encoding="utf-8")
        m = re.search(r"^quorum_threshold\s*=\s*(\d+)", text, re.MULTILINE)
        if m is None:
            return False
        if int(m.group(1)) != EXPECTED_CONFIG["mfa_quorum_threshold"]:
            return False
        weights = [int(x) for x in re.findall(r"^weight\s*=\s*(\d+)", text, re.MULTILINE)]
        if sum(weights) != EXPECTED_CONFIG["mfa_quorum_threshold"]:
            return False
        ids = re.findall(r'^id\s*=\s*"([^"]+)"', text, re.MULTILINE)
        return ids == sorted(ids)
    except Exception:
        return False


@criterion(description="audit_sampling.ini has an audit section listing only enabled channels in ascending order")
def audit_sampling_ini_channels_only_enabled(workspace: Path) -> bool:
    try:
        lines = [
            ln.strip()
            for ln in (out_dir(workspace) / "audit_sampling.ini").read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]
        if not lines[0].startswith(";"):
            return False
        if lines[1] != "[audit]":
            return False
        keys = []
        for ln in lines[2:]:
            if "=" not in ln:
                return False
            key, _, value = ln.partition("=")
            keys.append(key.strip())
            int(value.strip())
        return keys == sorted(keys) and len(keys) > 0
    except Exception:
        return False


@criterion(description="threat_scores.jsonl entries carry actor_id, tier and region with a valid tier and are sorted")
def threat_scores_jsonl_shape(workspace: Path) -> bool:
    try:
        lines = [ln for ln in (out_dir(workspace) / "threat_scores.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
        if len(lines) == 0:
            return False
        ids = []
        for ln in lines:
            entry = json.loads(ln)
            if set(entry) != {"actor_id", "tier", "region"}:
                return False
            if not re.fullmatch(r"actor-\d{4}", entry["actor_id"]):
                return False
            if int(entry["tier"]) not in {1, 2, 3, 4, 5}:
                return False
            ids.append(entry["actor_id"])
        return ids == sorted(ids)
    except Exception:
        return False


@criterion(description="cipher_priority.txt line count equals active_cipher_count from the main config")
def cipher_priority_count_matches_config(workspace: Path) -> bool:
    try:
        lines = [
            ln
            for ln in (out_dir(workspace) / "cipher_priority.txt").read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]
        if len(lines) != EXPECTED_CONFIG["active_cipher_count"]:
            return False
        return all(ln.startswith("TLS_ECDHE_PROFILE_") for ln in lines)
    except Exception:
        return False


@criterion(description="egress_allowlist.conf allow-line count equals egress_rules_count from the main config")
def egress_allowlist_count_matches_config(workspace: Path) -> bool:
    try:
        lines = [
            ln
            for ln in (out_dir(workspace) / "egress_allowlist.conf").read_text(encoding="utf-8").splitlines()
            if ln.strip().startswith("allow ")
        ]
        if len(lines) != EXPECTED_CONFIG["egress_rules_count"]:
            return False
        hosts = [ln.split(None, 1)[1] for ln in lines]
        return hosts == sorted(hosts)
    except Exception:
        return False


@criterion(description="trust_anchor_manifest.pem has matched blocks whose score comments sum to trust_anchor_score")
def trust_anchor_manifest_pem_blocks(workspace: Path) -> bool:
    try:
        text = (out_dir(workspace) / "trust_anchor_manifest.pem").read_text(encoding="utf-8")
        begins = text.count("-----BEGIN VAULT ANCHOR-----")
        ends = text.count("-----END VAULT ANCHOR-----")
        if not (begins == ends and begins > 0):
            return False
        scores = [int(x) for x in re.findall(r"^# score=(\d+)", text, re.MULTILINE)]
        return sum(scores) == EXPECTED_CONFIG["trust_anchor_score"]
    except Exception:
        return False


@criterion(description="compliance_map.md total_score equals compliance_score and equals the row-weight sum")
def compliance_map_total_matches_config(workspace: Path) -> bool:
    try:
        text = (out_dir(workspace) / "compliance_map.md").read_text(encoding="utf-8")
        if not text.startswith("# Compliance Map"):
            return False
        m = re.search(r"^total_score=(\d+)", text, re.MULTILINE)
        if m is None:
            return False
        if int(m.group(1)) != EXPECTED_CONFIG["compliance_score"]:
            return False
        rows = re.findall(r"^\| (framework-\d{4}) \| (\d+) \|", text, re.MULTILINE)
        if not rows:
            return False
        return sum(int(w) for _, w in rows) == EXPECTED_CONFIG["compliance_score"]
    except Exception:
        return False


@criterion(description="attestation_ledger.log active-signer entries are consistent with attestation_quorum")
def attestation_ledger_signer_count(workspace: Path) -> bool:
    try:
        lines = [
            ln
            for ln in (out_dir(workspace) / "attestation_ledger.log").read_text(encoding="utf-8").splitlines()
            if ln.strip().startswith("attest signer=")
        ]
        active_signers_min = (EXPECTED_CONFIG["attestation_quorum"] - 1) * 2
        active_signers_max = active_signers_min + 1
        if not (active_signers_min <= len(lines) <= active_signers_max):
            return False
        ids = [re.search(r"signer=(signer-\d{4})", ln).group(1) for ln in lines]
        return ids == sorted(ids)
    except Exception:
        return False


@criterion(description="session_policy.xml is well-formed and its scalar children mirror the derived config values")
def session_policy_xml_well_formed_and_matches_config(workspace: Path) -> bool:
    try:
        root = ET.parse(out_dir(workspace) / "session_policy.xml").getroot()
        if root.tag != "sessionPolicy":
            return False
        values = {child.tag: child.text for child in root}
        return (
            int(values["ttlSeconds"]) == EXPECTED_CONFIG["session_ttl_seconds"]
            and int(values["idleTimeoutSeconds"]) == EXPECTED_CONFIG["session_idle_timeout_seconds"]
            and int(values["mfaQuorum"]) == EXPECTED_CONFIG["mfa_quorum_threshold"]
            and int(values["tokenEntropyBits"]) == EXPECTED_CONFIG["token_entropy_bits"]
        )
    except Exception:
        return False


@criterion(description="derived_metrics.env carries every derived numeric scalar with an IRONVAULT prefix and integer value")
def derived_metrics_env_covers_all_scalars(workspace: Path) -> bool:
    try:
        lines = [
            ln
            for ln in (out_dir(workspace) / "derived_metrics.env").read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]
        keys = []
        for ln in lines:
            if not ln.startswith("IRONVAULT_"):
                return False
            key, _, value = ln.partition("=")
            keys.append(key.removeprefix("IRONVAULT_").lower())
            int(value)
        required_keys = {
            "pbkdf_iterations",
            "session_ttl_seconds",
            "session_idle_timeout_seconds",
            "rate_limit_rps",
            "rate_limit_burst",
            "mfa_quorum_threshold",
            "secret_rotation_days",
            "audit_sample_ratio_ppm",
            "token_entropy_bits",
            "trust_anchor_score",
            "egress_rules_count",
            "active_cipher_count",
            "compliance_score",
            "threat_high_actors",
            "attestation_quorum",
            "rbac_edge_count",
            "firewall_deny_count",
            "hash_algo_score",
            "cert_expiring_soon",
        }
        return all(required in keys for required in required_keys)
    except Exception:
        return False


@criterion(description="canary_thresholds.properties reports thresholds computed from the delivered config")
def canary_thresholds_derived_from_config(workspace: Path) -> bool:
    try:
        text = (out_dir(workspace) / "canary_thresholds.properties").read_text(encoding="utf-8")
        checks = [
            f"canary.min_signers={EXPECTED_CONFIG['attestation_quorum']}",
            f"canary.max_deny_rate={EXPECTED_CONFIG['firewall_deny_count']}",
            f"canary.latency_budget_ms={EXPECTED_CONFIG['session_idle_timeout_seconds']}",
            f"canary.error_pct={max(1, EXPECTED_CONFIG['audit_sample_ratio_ppm'] // 10000)}",
        ]
        return all(piece in text for piece in checks)
    except Exception:
        return False


@criterion(description="checksum_manifest.txt covers every emitted artifact except itself with correct sha256s")
def checksum_manifest_matches_disk_bytes(workspace: Path) -> bool:
    try:
        out = out_dir(workspace)
        text = (out / "checksum_manifest.txt").read_text(encoding="utf-8")
        lines = [ln for ln in text.splitlines() if ln.strip()]
        expected_names = {n for n in ARTIFACT_NAMES if n != "checksum_manifest.txt"}
        named = set()
        for line in lines:
            m = re.match(r"^([0-9a-f]{64})  (.+)$", line)
            if not m:
                return False
            digest, name = m.group(1), m.group(2)
            path = out / name
            if not path.is_file():
                return False
            if digest != hashlib.sha256(path.read_bytes()).hexdigest():
                return False
            named.add(name)
        return named == expected_names
    except Exception:
        return False


@criterion(description="validation_report.json reports ok and summary.json carries the full inventory")
def validation_report_and_summary_ok(workspace: Path) -> bool:
    try:
        out = out_dir(workspace)
        vr = load_json(out / "validation_report.json")
        if vr.get("ok") is not True:
            return False
        checks = vr["checks"]
        if checks.get("all_artifacts_present") is not True:
            return False
        if checks.get("config_scalar_flat") is not True:
            return False
        if checks.get("profiles_scalar_flat") is not True:
            return False
        if checks.get("command_failures") != []:
            return False
        if set(checks["required_artifacts"]) != set(ARTIFACT_NAMES):
            return False
        summary = load_json(out / "summary.json")
        if summary.get("artifact_count") != len(ARTIFACT_NAMES):
            return False
        if set(summary["artifacts"]) != set(ARTIFACT_NAMES):
            return False
        if summary.get("profiles") != ["dev", "prod"]:
            return False
        if summary.get("tool") != "nonce-ctl":
            return False
        if summary.get("format_tag") != "NONCE":
            return False
        if summary.get("trailer") != EXPECTED_CONFIG["trailer"]:
            return False
        inputs = summary.get("inputs")
        if not isinstance(inputs, list) or not inputs:
            return False
        return all(isinstance(name, str) and name for name in inputs)
    except Exception:
        return False


@criterion(description="unzipping tool.zip and running its validate subcommand against the delivered config succeeds")
def repaired_cli_runs_validate_against_delivered_config(workspace: Path) -> bool:
    try:
        root = tool_root(workspace)
        schema = root / "config_schema.json"
        schema.write_text(SCHEMA_JSON_TEXT, encoding="utf-8")
        rules = root / "validation_rules.json"
        rules.write_text(RULES_JSON_TEXT, encoding="utf-8")
        config_path = out_dir(workspace) / "config.json"
        _grant_read(config_path)
        result = run_repaired_cli(
            workspace,
            "validate",
            "--schema", str(schema),
            "--config", str(config_path),
            "--rules", str(rules),
        )
        return result.returncode == 0 and result.stdout.strip() == "ok"
    except Exception:
        return False


@criterion(description="the repaired CLI exits non-zero when invoked without a subcommand")
def repaired_cli_subcommand_is_required(workspace: Path) -> bool:
    try:
        result = run_repaired_cli(workspace)
        return result.returncode != 0
    except Exception:
        return False


@criterion(description="the repaired set subcommand preserves the key verbatim and coerces a negative integer value")
def set_preserves_key_and_coerces_negative(workspace: Path) -> bool:
    try:
        root = tool_root(workspace)
        probe = root / "set_probe_config.json"
        probe.write_text("{}", encoding="utf-8")
        probe.chmod(0o666)
        result = run_repaired_cli(
            workspace, "set", "--config", str(probe), "--key", "Rotation_Days", "--value", "-42"
        )
        if result.returncode != 0:
            return False
        value = json.loads(probe.read_text(encoding="utf-8")).get("Rotation_Days")
        return value == -42 and isinstance(value, int) and not isinstance(value, bool)
    except Exception:
        return False


@criterion(description="the repaired CLI source imports a network module that the instruction forbids")
def negative_network_imports_present(workspace: Path) -> bool:
    # Fires only when a banned network import is positively found in the source.
    try:
        src = tool_source(workspace)
        banned = ("import requests", "from requests", "import urllib", "from urllib", "import socket", "from socket")
        return any(token in src for token in banned)
    except Exception:
        return False


@criterion(description="a delivered artifact leaks a URL, bearer token, or credential-shaped key value pair")
def negative_forbidden_secret_or_url_material_in_outputs(workspace: Path) -> bool:
    # Fires only when banned material is positively found in a delivered artifact.
    try:
        out = out_dir(workspace)
        banned = ["http://", "https://", "secret=", "password=", "api_key=", "bearer "]
        for name in ARTIFACT_NAMES:
            path = out / name
            if path.suffix == ".zip" or not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            if any(token in text for token in banned):
                return True
        return False
    except Exception:
        return False


@criterion(description="the main config copies a scalar hint string from a sample_config file instead of deriving it")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    # Fires only when the main config itself carries a sample-hint-scoped value.
    try:
        cfg_path = out_dir(workspace) / "config.json"
        if not cfg_path.exists():
            return False
        cfg = load_json(cfg_path)
        return any(isinstance(v, str) and v in SAMPLE_HINT_STRINGS for v in cfg.values())
    except Exception:
        return False


@criterion(description="config.json carries a nested value or a nondeterministic dynamic field")
def negative_nested_or_dynamic_config(workspace: Path) -> bool:
    # Fires only when a nested value or a dynamic key is positively present.
    try:
        cfg_path = out_dir(workspace) / "config.json"
        if not cfg_path.exists():
            return False
        cfg = load_json(cfg_path)
        if any(isinstance(v, (dict, list)) for v in cfg.values()):
            return True
        dynamic = {"timestamp", "generated_at", "uuid", "random_seed", "now", "date", "run_id"}
        return any(key in cfg for key in dynamic)
    except Exception:
        return False


@criterion(description="the delivered /app/out/tool.zip packages a byte-identical copy of the unrepaired shipped cli.py")
def negative_delivered_cli_py_is_unrepaired(workspace: Path) -> bool:
    # Fires only when a byte-identical copy of the shipped broken cli.py is positively present inside /app/out/tool.zip; the "no tool.zip" case is already covered by all_artifacts_present_and_regular_files.
    try:
        archive = out_dir(workspace) / "tool.zip"
        if not archive.is_file() or archive.stat().st_size == 0:
            return False
        with zipfile.ZipFile(archive) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                if Path(info.filename).name == "cli.py":
                    return hashlib.sha256(zf.read(info)).hexdigest() == _SHIPPED_CLI_SHA256
        return False
    except Exception:
        return False


@criterion(description="the repaired CLI derive routine embeds a derived scalar constant literally")
def negative_hard_coded_derivation_constants(workspace: Path) -> bool:
    # Fires only when an expected scalar literal is positively found inside derive_values (where the arithmetic lives, not the thin cmd_derive wrapper).
    try:
        src = tool_source(workspace)
        derive_start = src.find("def derive_values")
        derive_end = src.find("\ndef ", derive_start + 1) if derive_start >= 0 else -1
        derive_body = src[derive_start:derive_end] if derive_start >= 0 else ""
        trap_numbers = [
            str(EXPECTED_CONFIG["pbkdf_iterations"]),
            str(EXPECTED_CONFIG["rate_limit_rps"]),
            str(EXPECTED_CONFIG["mfa_quorum_threshold"]),
            str(EXPECTED_CONFIG["audit_sample_ratio_ppm"]),
            str(EXPECTED_CONFIG["trust_anchor_score"]),
        ]
        return any(marker in derive_body for marker in trap_numbers)
    except Exception:
        return False


criteria.all_artifacts_present_and_regular_files(weight=1)
criteria.config_key_set_and_types(weight=3)
criteria.config_matches_expected_derived_values(weight=5)
criteria.config_is_sort_keys_two_space_indented(weight=3)
criteria.profile_dev_matches_expected(weight=5)
criteria.profile_prod_matches_expected(weight=5)
criteria.profiles_have_profile_specific_trailer_suffix(weight=3)
criteria.pbkdf_iterations_obeys_power_of_two_multiplier_law(weight=5)
criteria.rate_limit_burst_is_three_times_rps(weight=3)
criteria.report_records_full_cli_transcript(weight=5)
criteria.report_digest_matches_config_bytes(weight=3)
criteria.policy_matrix_dimensions_and_binary_cells(weight=3)
criteria.rate_limits_tsv_shape_and_sorted(weight=3)
criteria.rotation_schedule_only_required_classes_sorted(weight=3)
criteria.mfa_quorum_toml_matches_config(weight=5)
criteria.audit_sampling_ini_channels_only_enabled(weight=3)
criteria.threat_scores_jsonl_shape(weight=3)
criteria.cipher_priority_count_matches_config(weight=5)
criteria.egress_allowlist_count_matches_config(weight=5)
criteria.trust_anchor_manifest_pem_blocks(weight=5)
criteria.compliance_map_total_matches_config(weight=5)
criteria.attestation_ledger_signer_count(weight=3)
criteria.session_policy_xml_well_formed_and_matches_config(weight=5)
criteria.derived_metrics_env_covers_all_scalars(weight=3)
criteria.canary_thresholds_derived_from_config(weight=3)
criteria.checksum_manifest_matches_disk_bytes(weight=5)
criteria.validation_report_and_summary_ok(weight=5)
criteria.repaired_cli_runs_validate_against_delivered_config(weight=5)
criteria.repaired_cli_subcommand_is_required(weight=1)
criteria.set_preserves_key_and_coerces_negative(weight=1)
criteria.negative_network_imports_present(weight=-3)
criteria.negative_forbidden_secret_or_url_material_in_outputs(weight=-3)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_nested_or_dynamic_config(weight=-5)
criteria.negative_delivered_cli_py_is_unrepaired(weight=-5)
criteria.negative_hard_coded_derivation_constants(weight=-3)
