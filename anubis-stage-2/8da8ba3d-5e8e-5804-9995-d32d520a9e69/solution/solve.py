#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath

SOURCE_ARCHIVE = Path("/app/data/tool.zip")
DATA = Path("/app/data")
TOOL = Path("/app/tool").resolve()
OUT = Path("/app/out")

FIXED_CLI = r'''#!/usr/bin/env python3
"""nonce-ctl - Ironvault Bastion policy CLI (repaired reference build)."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from pathlib import Path

REPORT_STDOUT = "reported"
THROTTLED_ZONES = {"internal", "admin"}
HIGH_THREAT_TIER = 4
CERT_EXPIRY_WINDOW_DAYS = 30
PPM_PER_PERCENT = 10000
PEM_END = "-----END VAULT ANCHOR-----"

# Order of the IRONVAULT_<KEY> lines written by `emit-artifact --kind derived_metrics`.
DERIVED_METRIC_KEYS = [
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
]


def read_text(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise SystemExit(f"cannot read {path}: {exc.strerror or exc}") from None


def load_json(path):
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON in {path}: {exc}") from None


def write_json(path, data):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def coerce(value):
    if isinstance(value, (int, bool)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text.lstrip("-").isdecimal():
            return int(text)
        if text in {"true", "false"}:
            return text == "true"
    return value


def assert_flat(data):
    nested = sorted(k for k, v in data.items() if isinstance(v, (dict, list)))
    if nested:
        raise SystemExit("configuration must be flat: " + ",".join(nested))


def load_config(path):
    data = load_json(path)
    if not isinstance(data, dict):
        raise SystemExit(f"{path} must hold a JSON object")
    assert_flat(data)
    return data


def content_lines(path):
    """Yield (line_number, stripped_line) for every non-blank, non-comment line."""
    for number, raw in enumerate(read_text(path).splitlines(), start=1):
        line = raw.strip()
        if line and not line.startswith("#"):
            yield number, line


def read_jsonl(path):
    rows = []
    for number, line in content_lines(path):
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"invalid JSON on line {number} of {path}: {exc}") from None
    return rows


def read_delimited(path, delimiter):
    reader = csv.DictReader(io.StringIO(read_text(path)), delimiter=delimiter)
    return [dict(row) for row in reader]


def read_csv(path):
    return read_delimited(path, ",")


def read_tsv(path):
    return read_delimited(path, "\t")


def read_properties(path):
    result = {}
    for _, line in content_lines(path):
        key, separator, value = line.partition("=")
        if separator:
            result[key.strip()] = value.strip()
    return result


def read_yaml_list(path, list_key):
    """Read the `<list_key>:` block of `  - id: ...` items with indented scalar fields."""
    items = []
    current = None
    in_list = False
    for line in read_text(path).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == f"{list_key}:":
            in_list = True
            continue
        if not in_list:
            continue
        item_match = re.match(r"^  - id: (.+)$", line)
        field_match = re.match(r"^    ([A-Za-z_][A-Za-z0-9_]*): (.+)$", line)
        if item_match:
            if current is not None:
                items.append(current)
            current = {"id": item_match.group(1).strip()}
        elif field_match and current is not None:
            current[field_match.group(1)] = field_match.group(2).strip()
    if current is not None:
        items.append(current)
    return items


def read_conf_actions(path):
    actions = []
    for _, line in content_lines(path):
        parts = line.split(None, 1)
        if len(parts) == 2:
            actions.append((parts[0], parts[1].strip()))
    return actions


def read_lines(path):
    return [line for _, line in content_lines(path)]


def active_threat_actors(data_dir):
    actors = read_jsonl(data_dir / "threat_actors.jsonl")
    return sorted(
        (a for a in actors if a.get("status") == "active" and not a.get("quarantined")),
        key=lambda a: a["id"],
    )


def usable_mfa_factors(data_dir):
    return [
        f
        for f in read_csv(data_dir / "mfa_factors.csv")
        if f["enabled"] == "true" and f["deprecated"] == "false"
    ]


def strong_mfa_factors(data_dir):
    return sorted(
        (f for f in usable_mfa_factors(data_dir) if f["factor_class"] == "strong"),
        key=lambda f: f["factor_id"],
    )


def hardening_offsets(data_dir, profile_id):
    """Return (session_ttl_offset, idle_timeout_offset) for one hardening profile row."""
    for row in read_yaml_list(data_dir / "hardening_profiles.yaml", "profiles"):
        if row["id"] == profile_id:
            return int(row["session_ttl_offset"]), int(row["idle_timeout_offset"])
    return 0, 0


def throttled_endpoints(data_dir):
    return sorted(
        (
            r
            for r in read_csv(data_dir / "rate_limits.csv")
            if r["zone"] in THROTTLED_ZONES and r["deprecated"] == "false"
        ),
        key=lambda r: r["endpoint"],
    )


def required_secret_classes(data_dir):
    classes = read_yaml_list(data_dir / "secret_classes.yaml", "classes")
    return sorted(
        (c for c in classes if c["required"] == "true"), key=lambda c: c["id"]
    )


def enabled_audit_channels(data_dir):
    """Return sorted (channel, delta) pairs for channels with sampling enabled."""
    settings = read_properties(data_dir / "audit_sampling.properties")
    channels = set()
    for key in settings:
        match = re.match(r"^sampling\.(.+)\.(enabled|delta)$", key)
        if match:
            channels.add(match.group(1))
    return [
        (channel, settings.get(f"sampling.{channel}.delta", "0"))
        for channel in sorted(channels)
        if settings.get(f"sampling.{channel}.enabled") == "true"
    ]


def active_ciphers(data_dir):
    deprecated = {
        entry["cipher"]
        for entry in read_jsonl(data_dir / "cipher_deprecations.jsonl")
        if entry.get("deprecated_at")
    }
    return [c for c in read_lines(data_dir / "cipher_suites.txt") if c not in deprecated]


def allowed_egress_hosts(data_dir):
    allowed = {
        host
        for action, host in read_conf_actions(data_dir / "egress_hosts.conf")
        if action == "allow"
    }
    return sorted(allowed - set(read_lines(data_dir / "egress_denylist.txt")))


def active_trust_anchors(data_dir):
    return sorted(
        (
            r
            for r in read_csv(data_dir / "trust_anchor_scores.csv")
            if r["status"] == "active" and r["rotation_ok"] == "true"
        ),
        key=lambda r: r["anchor_id"],
    )


def mapped_framework_weights(data_dir):
    """Return sorted (framework, weight) pairs for every framework with a mapped control."""
    weights = {
        f["id"]: int(f["weight"])
        for f in read_yaml_list(data_dir / "compliance_frameworks.yaml", "frameworks")
    }
    mapped = {
        m["framework"]
        for m in read_csv(data_dir / "compliance_mappings.csv")
        if m["status"] == "mapped"
    }
    return [(name, weights.get(name, 0)) for name in sorted(mapped)]


def active_signers(data_dir):
    return sorted(
        (s for s in read_csv(data_dir / "attestation_signers.csv") if s["status"] == "active"),
        key=lambda s: s["signer_id"],
    )


def active_rbac(data_dir):
    """Return (sorted active role ids, sorted active permission ids, binding pairs)."""
    roles = sorted(
        r["role_id"] for r in read_csv(data_dir / "rbac_roles.csv") if r["active"] == "true"
    )
    permissions = sorted(
        p["perm_id"]
        for p in read_tsv(data_dir / "rbac_permissions.tsv")
        if p["active"] == "true"
    )
    bindings = [
        (b["role"], b["permission"]) for b in read_jsonl(data_dir / "rbac_bindings.jsonl")
    ]
    return roles, permissions, bindings


def derive_values(data_dir):
    data_dir = Path(data_dir)
    defaults = load_json(data_dir / "defaults.json")
    schema = load_json(data_dir / "config_schema.json")

    actors = active_threat_actors(data_dir)
    max_tier = max((int(a["tier"]) for a in actors), default=1)
    pbkdf_iterations = int(defaults["base_pbkdf_iters"]) * (2 ** max_tier)
    threat_high = sum(1 for a in actors if int(a["tier"]) >= HIGH_THREAT_TIER)

    step_reduction = sum(
        int(f["step_reduction_seconds"]) for f in usable_mfa_factors(data_dir)
    )
    base_ttl_offset, _ = hardening_offsets(data_dir, "base")
    session_ttl = int(defaults["base_session_ttl"]) - step_reduction + base_ttl_offset

    base_idle = [
        int(r["idle_seconds"])
        for r in read_csv(data_dir / "session_lifetimes.csv")
        if r["tier"] == "base" and r["active"] == "true"
    ]
    session_idle = min(base_idle) if base_idle else int(defaults["base_idle_timeout"])

    rate_limit_rps = int(defaults["base_rate_rps"]) + sum(
        int(r["concurrency_delta"]) for r in throttled_endpoints(data_dir)
    )
    rate_limit_burst = rate_limit_rps * int(defaults["base_rate_burst_factor"])

    mfa_quorum = sum(int(f["weight"]) for f in strong_mfa_factors(data_dir))

    rotation_minimums = [
        int(c["rotation_days_min"]) for c in required_secret_classes(data_dir)
    ]
    secret_rotation_days = (
        min(rotation_minimums)
        if rotation_minimums
        else int(defaults["base_rotation_days"])
    )

    audit_ppm = int(defaults["base_audit_ratio_ppm"]) + sum(
        int(delta) for _, delta in enabled_audit_channels(data_dir)
    )

    required_bits = [
        int(t["entropy_bits"])
        for t in read_tsv(data_dir / "token_entropy.tsv")
        if t["policy"] == "required"
    ]
    token_entropy = max(required_bits) if required_bits else int(defaults["base_token_bits"])

    roles, permissions, bindings = active_rbac(data_dir)
    role_set, permission_set = set(roles), set(permissions)
    rbac_edges = sum(
        1 for role, permission in bindings if role in role_set and permission in permission_set
    )

    firewall_deny = sum(
        1 for r in read_tsv(data_dir / "firewall_rules.tsv") if r["action"] == "deny"
    )
    hash_score = sum(
        int(r["weight"])
        for r in read_csv(data_dir / "hash_algorithms.csv")
        if r["deprecated"] == "false"
    )
    cert_expiring = sum(
        1
        for r in read_csv(data_dir / "cert_expiry.csv")
        if r["status"] == "active" and 0 <= int(r["expiry_days"]) <= CERT_EXPIRY_WINDOW_DAYS
    )

    return {
        "active_cipher_count": len(active_ciphers(data_dir)),
        "attestation_quorum": len(active_signers(data_dir)) // 2 + 1,
        "audit_sample_ratio_ppm": audit_ppm,
        "cert_expiring_soon": cert_expiring,
        "checksum": defaults["checksum"],
        "compliance_score": sum(w for _, w in mapped_framework_weights(data_dir)),
        "container": schema["container"],
        "egress_rules_count": len(allowed_egress_hosts(data_dir)),
        "firewall_deny_count": firewall_deny,
        "hash_algo_score": hash_score,
        "mfa_quorum_threshold": mfa_quorum,
        "mode": defaults["mode"],
        "pbkdf_iterations": pbkdf_iterations,
        "producer": schema["producer"],
        "profile": schema["profile"],
        "rate_limit_burst": rate_limit_burst,
        "rate_limit_rps": rate_limit_rps,
        "rbac_edge_count": rbac_edges,
        "secret_rotation_days": secret_rotation_days,
        "session_idle_timeout_seconds": session_idle,
        "session_ttl_seconds": session_ttl,
        "threat_high_actors": threat_high,
        "token_entropy_bits": token_entropy,
        "trailer": schema["trailer"],
        "trust_anchor_score": sum(int(r["score"]) for r in active_trust_anchors(data_dir)),
    }


def cmd_init(args):
    schema = load_json(args.schema)
    data = {
        key: schema[key]
        for key in ("profile", "producer", "container", "checksum", "mode", "trailer")
    }
    write_json(args.out, data)
    print("initialized")


def cmd_derive(args):
    write_json(args.out, derive_values(args.data))
    print("derived")


def cmd_set(args):
    data = load_config(args.config)
    data[args.key] = coerce(args.value)
    write_json(args.config, data)
    print("set " + args.key)


def cmd_validate(args):
    schema = load_json(args.schema)
    data = load_config(args.config)
    missing = [k for k in schema["required_keys"].split(",") if k not in data]
    if missing:
        raise SystemExit("missing: " + ",".join(missing))
    bounds = load_json(args.rules).get("numeric_bounds", {})
    for key, (low, high) in bounds.items():
        if key in data:
            value = data[key]
            if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
                raise SystemExit(f"out-of-bounds: {key}={value}")
    print("ok")


def cmd_emit_profile(args):
    data_dir = Path(args.data)
    schema = load_json(args.schema)
    base = load_config(args.config)
    all_overrides = load_json(args.overrides)
    overrides = all_overrides.get(args.name) if isinstance(all_overrides, dict) else None
    if not isinstance(overrides, dict):
        raise SystemExit(f"no overrides for profile {args.name!r} in {args.overrides}")
    ttl_offset, idle_offset = hardening_offsets(data_dir, args.name)
    defaults = load_json(data_dir / "defaults.json")

    profile = dict(base)
    profile["session_ttl_seconds"] = (
        base["session_ttl_seconds"] + int(overrides["session_ttl_delta"]) + ttl_offset
    )
    profile["session_idle_timeout_seconds"] = base["session_idle_timeout_seconds"] + idle_offset
    profile["pbkdf_iterations"] = (
        base["pbkdf_iterations"] * int(overrides["pbkdf_scale_num"])
    ) // int(overrides["pbkdf_scale_den"])
    profile["mfa_quorum_threshold"] = (
        base["mfa_quorum_threshold"] + int(overrides["mfa_quorum_delta"])
    )
    profile["rate_limit_rps"] = base["rate_limit_rps"] + int(overrides["rate_limit_delta"])
    profile["rate_limit_burst"] = profile["rate_limit_rps"] * int(
        defaults["base_rate_burst_factor"]
    )
    profile["profile"] = f"{schema['profile']}-{args.name}"
    profile["trailer"] = f"{schema['trailer']}:{overrides['trailer_suffix']}"
    write_json(args.out, profile)
    print("profile " + args.name)


def config_argument(args):
    if not args.config:
        raise SystemExit(f"emit-artifact --kind {args.kind} needs --config")
    return load_config(args.config)


def render_policy_matrix(args):
    roles, permissions, bindings = active_rbac(Path(args.data))
    granted = set(bindings)
    lines = ["role_id," + ",".join(permissions)]
    for role in roles:
        cells = ["1" if (role, permission) in granted else "0" for permission in permissions]
        lines.append(",".join([role] + cells))
    return lines


def render_rate_limits(args):
    lines = ["endpoint\tzone\teffective_rps\tconcurrency_delta"]
    for row in throttled_endpoints(Path(args.data)):
        effective_rps = int(row["base_rps"]) + int(row["concurrency_delta"])
        lines.append(
            f"{row['endpoint']}\t{row['zone']}\t{effective_rps}\t{row['concurrency_delta']}"
        )
    return lines


def render_rotation_schedule(args):
    lines = ["# secret rotation schedule (required classes only)", "schedule:"]
    for secret_class in required_secret_classes(Path(args.data)):
        lines.append(f"  - class_id: {secret_class['id']}")
        lines.append(f"    kind: {secret_class['kind']}")
        lines.append(f"    rotation_days_min: {secret_class['rotation_days_min']}")
        lines.append(f"    rotation_days_max: {secret_class['rotation_days_max']}")
    return lines


def render_mfa_quorum(args):
    factors = strong_mfa_factors(Path(args.data))
    quorum = sum(int(factor["weight"]) for factor in factors)
    lines = ["# mfa quorum", f"quorum_threshold = {quorum}"]
    for factor in factors:
        lines.append("[[factor]]")
        lines.append(f"id = \"{factor['factor_id']}\"")
        lines.append(f"weight = {factor['weight']}")
    return lines


def render_audit_sampling(args):
    lines = ["; audit sampling (enabled channels only)", "[audit]"]
    for channel, delta in enabled_audit_channels(Path(args.data)):
        lines.append(f"{channel} = {delta}")
    return lines


def render_threat_scores(args):
    return [
        json.dumps(
            {"actor_id": actor["id"], "tier": actor["tier"], "region": actor["region"]},
            sort_keys=True,
        )
        for actor in active_threat_actors(Path(args.data))
    ]


def render_cipher_priority(args):
    return active_ciphers(Path(args.data))


def render_egress_allowlist(args):
    lines = ["# egress allowlist (post-denylist)"]
    lines.extend(f"allow {host}" for host in allowed_egress_hosts(Path(args.data)))
    return lines


def render_session_policy(args):
    config = config_argument(args)
    return [
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
        "<sessionPolicy>",
        f"  <ttlSeconds>{config['session_ttl_seconds']}</ttlSeconds>",
        f"  <idleTimeoutSeconds>{config['session_idle_timeout_seconds']}</idleTimeoutSeconds>",
        f"  <mfaQuorum>{config['mfa_quorum_threshold']}</mfaQuorum>",
        f"  <tokenEntropyBits>{config['token_entropy_bits']}</tokenEntropyBits>",
        "</sessionPolicy>",
    ]


def render_trust_anchor_manifest(args):
    data_dir = Path(args.data)
    pem_text = read_text(data_dir / "trust_anchors.pem")
    lines = ["# trust anchor manifest (active, rotation-ok anchors only)"]
    for anchor in active_trust_anchors(data_dir):
        start = pem_text.find(f"# anchor {anchor['anchor_id']}")
        if start < 0:
            continue
        block = pem_text[start:].split(PEM_END, 1)[0]
        lines.append(block + PEM_END)
        lines.append(f"# score={anchor['score']}")
    return lines


def render_compliance_map(args):
    rows = mapped_framework_weights(Path(args.data))
    lines = ["# Compliance Map", "", "| framework | weight |", "|---|---|"]
    lines.extend(f"| {name} | {weight} |" for name, weight in rows)
    lines.append("")
    lines.append(f"total_score={sum(weight for _, weight in rows)}")
    return lines


def render_attestation_ledger(args):
    return [
        f"attest signer={s['signer_id']} strength={s['strength']} rotated_days={s['rotated_days']}"
        for s in active_signers(Path(args.data))
    ]


def render_derived_metrics(args):
    config = config_argument(args)
    return [f"IRONVAULT_{key.upper()}={config[key]}" for key in DERIVED_METRIC_KEYS]


def render_canary_thresholds(args):
    config = config_argument(args)
    return [
        "# canary thresholds derived from active security policy",
        f"canary.error_pct={max(1, config['audit_sample_ratio_ppm'] // PPM_PER_PERCENT)}",
        f"canary.latency_budget_ms={config['session_idle_timeout_seconds']}",
        f"canary.min_signers={config['attestation_quorum']}",
        f"canary.max_deny_rate={config['firewall_deny_count']}",
    ]


def render_checksum_manifest(args):
    if not args.out_dir:
        raise SystemExit("emit-artifact --kind checksum_manifest needs --out-dir")
    out_dir = Path(args.out_dir)
    if not out_dir.is_dir():
        raise SystemExit(f"--out-dir {out_dir} is not a directory")
    manifest = Path(args.out).resolve()
    lines = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.resolve() != manifest:
            lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}")
    return lines


ARTIFACT_RENDERERS = {
    "policy_matrix": render_policy_matrix,
    "rate_limits": render_rate_limits,
    "rotation_schedule": render_rotation_schedule,
    "mfa_quorum": render_mfa_quorum,
    "audit_sampling": render_audit_sampling,
    "threat_scores": render_threat_scores,
    "cipher_priority": render_cipher_priority,
    "egress_allowlist": render_egress_allowlist,
    "session_policy": render_session_policy,
    "trust_anchor_manifest": render_trust_anchor_manifest,
    "compliance_map": render_compliance_map,
    "attestation_ledger": render_attestation_ledger,
    "derived_metrics": render_derived_metrics,
    "canary_thresholds": render_canary_thresholds,
    "checksum_manifest": render_checksum_manifest,
}


def cmd_emit_artifact(args):
    lines = ARTIFACT_RENDERERS[args.kind](args)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("emit " + args.kind)


def cmd_export_report(args):
    data = load_config(args.config)
    try:
        commands = json.loads(args.commands)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"--commands is not valid JSON: {exc}") from None
    if not isinstance(commands, list):
        raise SystemExit("--commands must be a JSON list")
    # This process exits 0 right after the report is written, so its own entry
    # carries the exact argv it was started with and that return code.
    commands.append(
        {"argv": list(sys.orig_argv), "returncode": 0, "stdout": REPORT_STDOUT}
    )
    report = {
        "ok": True,
        "tool": "nonce-ctl",
        "config_path": args.config,
        "config_sha256": args.digest,
        "commands": commands,
        "trailer": data.get("trailer"),
    }
    write_json(args.out, report)
    print(REPORT_STDOUT)


def build_parser():
    parser = argparse.ArgumentParser(prog="nonce-ctl")
    subcommands = parser.add_subparsers(dest="command", required=True)

    init = subcommands.add_parser("init")
    init.add_argument("--schema", required=True)
    init.add_argument("--out", required=True)
    init.set_defaults(func=cmd_init)

    derive = subcommands.add_parser("derive")
    derive.add_argument("--data", required=True)
    derive.add_argument("--out", required=True)
    derive.set_defaults(func=cmd_derive)

    set_value = subcommands.add_parser("set")
    set_value.add_argument("--config", required=True)
    set_value.add_argument("--key", required=True)
    set_value.add_argument("--value", required=True)
    set_value.set_defaults(func=cmd_set)

    validate = subcommands.add_parser("validate")
    validate.add_argument("--schema", required=True)
    validate.add_argument("--config", required=True)
    validate.add_argument("--rules", required=True)
    validate.set_defaults(func=cmd_validate)

    emit_profile = subcommands.add_parser("emit-profile")
    emit_profile.add_argument("--schema", required=True)
    emit_profile.add_argument("--config", required=True)
    emit_profile.add_argument("--overrides", required=True)
    emit_profile.add_argument("--data", required=True)
    emit_profile.add_argument("--name", required=True)
    emit_profile.add_argument("--out", required=True)
    emit_profile.set_defaults(func=cmd_emit_profile)

    emit_artifact = subcommands.add_parser("emit-artifact")
    emit_artifact.add_argument("--kind", required=True, choices=sorted(ARTIFACT_RENDERERS))
    emit_artifact.add_argument("--data", required=True)
    emit_artifact.add_argument("--out", required=True)
    emit_artifact.add_argument("--config", required=False)
    emit_artifact.add_argument("--out-dir", required=False, dest="out_dir")
    emit_artifact.set_defaults(func=cmd_emit_artifact)

    export_report = subcommands.add_parser("export-report")
    export_report.add_argument("--config", required=True)
    export_report.add_argument("--out", required=True)
    export_report.add_argument("--digest", required=True)
    export_report.add_argument("--commands", required=True)
    export_report.set_defaults(func=cmd_export_report)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except (KeyError, TypeError, ValueError) as exc:
        raise SystemExit(
            f"nonce-ctl {args.command}: malformed input ({type(exc).__name__}: {exc})"
        ) from None


if __name__ == "__main__":
    main()
'''


def extract() -> None:
    if TOOL.exists():
        shutil.rmtree(TOOL)
    TOOL.mkdir(parents=True)
    with zipfile.ZipFile(SOURCE_ARCHIVE) as zf:
        for info in zf.infolist():
            rel = PurePosixPath(info.filename)
            mode = (info.external_attr >> 16) & 0xFFFF
            if rel.is_absolute() or ".." in rel.parts or stat.S_ISLNK(mode):
                raise SystemExit(f"unsafe source member: {info.filename!r}")
            dest = (TOOL / Path(*rel.parts)).resolve()
            if not dest.is_relative_to(TOOL):
                raise SystemExit(f"escaping source member: {info.filename!r}")
            if info.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(zf.read(info))


def repair_cli() -> None:
    (TOOL / "cli.py").write_text(FIXED_CLI, encoding="utf-8", newline="\n")


def run_cli(*args: str) -> dict:
    cmd = [sys.executable, str(TOOL / "cli.py"), *args]
    result = subprocess.run(
        cmd, cwd=TOOL, text=True, capture_output=True, timeout=60, check=False
    )
    return {
        "argv": cmd,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
    }


def require_success(entry: dict) -> dict:
    if entry["returncode"] != 0:
        subcommand = entry["argv"][2]
        raise SystemExit(
            f"{subcommand} exited {entry['returncode']}: {entry['stdout']!r}"
        )
    return entry


def matches_observed_run(recorded: dict, observed: dict) -> bool:
    # argv[0] is the interpreter path the OS started; a platform launcher may
    # rewrite it, so the comparison covers the script, its arguments, the
    # return code and the trimmed stdout.
    return (
        recorded.get("argv", [])[1:] == observed["argv"][1:]
        and recorded.get("returncode") == observed["returncode"]
        and recorded.get("stdout") == observed["stdout"]
    )


def package_tool() -> None:
    archive = OUT / "tool.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as zf:
        for path in sorted(p for p in TOOL.rglob("*") if p.is_file()):
            info = zipfile.ZipInfo(
                path.relative_to(TOOL).as_posix(), date_time=(1980, 1, 1, 0, 0, 0)
            )
            info.external_attr = 0o100644 << 16
            zf.writestr(info, path.read_bytes())


def dump_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    extract()
    repair_cli()

    config = OUT / "config.json"
    schema = DATA / "config_schema.json"
    rules = DATA / "validation_rules.json"
    overrides = DATA / "env_overrides.json"
    report = OUT / "report.json"

    commands: list[dict] = []
    commands.append(
        run_cli("init", "--schema", str(schema), "--out", str(config))
    )
    commands.append(
        run_cli("derive", "--data", str(DATA), "--out", str(config))
    )
    commands.append(
        run_cli("validate", "--schema", str(schema), "--config", str(config), "--rules", str(rules))
    )
    for name in ("dev", "prod"):
        commands.append(
            run_cli(
                "emit-profile",
                "--schema", str(schema),
                "--config", str(config),
                "--overrides", str(overrides),
                "--data", str(DATA),
                "--name", name,
                "--out", str(OUT / f"profile_{name}.json"),
            )
        )
    emit_specs = [
        ("policy_matrix", OUT / "policy_matrix.csv"),
        ("rate_limits", OUT / "rate_limits.tsv"),
        ("rotation_schedule", OUT / "rotation_schedule.yaml"),
        ("mfa_quorum", OUT / "mfa_quorum.toml"),
        ("audit_sampling", OUT / "audit_sampling.ini"),
        ("threat_scores", OUT / "threat_scores.jsonl"),
        ("cipher_priority", OUT / "cipher_priority.txt"),
        ("egress_allowlist", OUT / "egress_allowlist.conf"),
        ("trust_anchor_manifest", OUT / "trust_anchor_manifest.pem"),
        ("compliance_map", OUT / "compliance_map.md"),
        ("attestation_ledger", OUT / "attestation_ledger.log"),
    ]
    for kind, path in emit_specs:
        commands.append(
            run_cli("emit-artifact", "--kind", kind, "--data", str(DATA), "--out", str(path))
        )
    config_specs = [
        ("session_policy", OUT / "session_policy.xml"),
        ("derived_metrics", OUT / "derived_metrics.env"),
        ("canary_thresholds", OUT / "canary_thresholds.properties"),
    ]
    for kind, path in config_specs:
        commands.append(
            run_cli(
                "emit-artifact",
                "--kind", kind,
                "--data", str(DATA),
                "--config", str(config),
                "--out", str(path),
            )
        )
    manifest_args = (
        "emit-artifact",
        "--kind", "checksum_manifest",
        "--data", str(DATA),
        "--out", str(OUT / "checksum_manifest.txt"),
        "--out-dir", str(OUT),
    )
    commands.append(run_cli(*manifest_args))

    for entry in commands:
        require_success(entry)

    digest = hashlib.sha256(config.read_bytes()).hexdigest()
    report_run = require_success(
        run_cli(
            "export-report",
            "--config", str(config),
            "--out", str(report),
            "--digest", digest,
            "--commands", json.dumps(commands, sort_keys=True),
        )
    )
    # export-report writes its own entry while it runs; confirm that entry
    # matches the argv, return code and stdout observed from outside.
    recorded = json.loads(report.read_text())["commands"][-1]
    if not matches_observed_run(recorded, report_run):
        raise SystemExit("report.json export-report entry differs from the observed run")
    commands.append(report_run)

    package_tool()

    cfg = json.loads(config.read_text())
    validation_rules = json.loads(rules.read_text())
    artifacts = validation_rules["required_artifacts"]
    dev = json.loads((OUT / "profile_dev.json").read_text())
    prod = json.loads((OUT / "profile_prod.json").read_text())
    self_written = {"validation_report.json", "summary.json"}
    checks = {
        "all_artifacts_present": all(
            (OUT / n).exists() or n in self_written for n in artifacts
        ),
        "config_scalar_flat": all(
            not isinstance(v, (dict, list)) for v in cfg.values()
        ),
        "config_key_count": len(cfg),
        "config_bounded_keys_present": all(
            k in cfg for k in validation_rules.get("numeric_bounds", {})
        ),
        "config_all_required_keys_present": all(
            k in cfg for k in json.loads(schema.read_text())["required_keys"].split(",")
        ),
        "profiles_scalar_flat": all(
            not isinstance(v, (dict, list)) for v in dev.values()
        )
        and all(not isinstance(v, (dict, list)) for v in prod.values()),
        "profile_dev_trailer": dev["trailer"],
        "profile_prod_trailer": prod["trailer"],
        "command_failures": [c for c in commands if c["returncode"] != 0],
        "required_artifacts": artifacts,
    }
    dump_json(
        OUT / "validation_report.json",
        {
            "ok": checks["all_artifacts_present"]
            and checks["config_scalar_flat"]
            and checks["profiles_scalar_flat"]
            and checks["config_bounded_keys_present"]
            and checks["config_all_required_keys_present"]
            and not checks["command_failures"],
            "checks": checks,
        },
    )

    inputs = sorted(p.name for p in DATA.iterdir() if p.is_file())
    dump_json(
        OUT / "summary.json",
        {
            "artifact_count": len(artifacts),
            "artifacts": artifacts,
            "input_count": len(inputs),
            "inputs": inputs,
            "profiles": ["dev", "prod"],
            "tool": "nonce-ctl",
            "trailer": cfg["trailer"],
            "format_tag": "NONCE",
        },
    )

    # The manifest must hash the final report.json, tool.zip, validation_report.json
    # and summary.json, so it is regenerated once they exist. This last run cannot
    # appear in report.json, because report.json is one of the files it hashes.
    require_success(run_cli(*manifest_args))


if __name__ == "__main__":
    main()
