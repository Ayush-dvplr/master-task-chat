from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

# sentinel-ctl: policy bundle compiler.

ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)
ZIP_MODE = 0o100644


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, data):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def coerce(value):
    if re.fullmatch(r"-?[0-9]+", value):
        return int(value)
    if value in ("true", "false"):
        return value == "true"
    return value


def assert_flat(data):
    bad = [key for key, value in data.items() if isinstance(value, (dict, list))]
    if bad:
        raise SystemExit("configuration must be flat: " + ",".join(sorted(bad)))


def round_half_up(numerator, denominator):
    quotient = Decimal(numerator) / Decimal(denominator)
    return int(quotient.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def read_toml(path):
    import tomllib

    return tomllib.loads(Path(path).read_text(encoding="utf-8"))


def read_jsonc(path):
    text = Path(path).read_text(encoding="utf-8")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"(^|\s)//[^\n]*", "", text)
    return json.loads(text)


def read_yaml_flat(path):
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ": " not in stripped and not stripped.endswith(":"):
            continue
        key, _, value = stripped.partition(":")
        out[key.strip()] = value.strip().strip('"')
    return out


def read_conf(path):
    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")
    flat = {}
    for section in parser.sections():
        for key, value in parser.items(section):
            flat[key] = value
    return flat


def read_kv_txt(path):
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        out[key.strip()] = value.partition("#")[0].strip()
    return out


def read_xml_records(path, tag):
    root = ET.parse(path).getroot()
    return [dict(node.attrib) for node in root.iter(tag)]


def _col_to_idx(ref):
    letters = re.match(r"[A-Z]+", ref).group(0)
    idx = 0
    for char in letters:
        idx = idx * 26 + (ord(char) - ord("A") + 1)
    return idx - 1


def read_xlsx_rows(path):
    ns = "{" + "http" + "://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with zipfile.ZipFile(path) as zf:
        sroot = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))
        rows = []
        for row in sroot.iter(ns + "row"):
            cells = {}
            for cell in row.iter(ns + "c"):
                ref = cell.get("r", "A1")
                col = _col_to_idx(ref)
                vnode = cell.find(ns + "v")
                if cell.get("t") == "inlineStr":
                    tnode = cell.find(ns + "is/" + ns + "t")
                    cells[col] = tnode.text if tnode is not None else ""
                else:
                    cells[col] = vnode.text if vnode is not None else ""
            rows.append(cells)
    header = [rows[0][i] for i in sorted(rows[0])]
    records = []
    for cells in rows[1:]:
        records.append({name: cells.get(i, "") for i, name in enumerate(header)})
    return records


def read_parquet_rows(path):
    import pyarrow.parquet as pq

    return pq.read_table(path).to_pylist()


def resolve_policy(data_dir):
    data = Path(data_dir)
    order = []
    rejected = []

    def consume(name):
        if name not in order:
            order.append(name)
        return data / name

    def reject(ident, reason):
        rejected.append({"id": ident, "reason": reason})

    # 1. boot manifest fixes the effective instant and the candidate bundle ids.
    manifest = read_toml(consume("boot_manifest.toml"))["manifest"]
    instant = int(manifest["effective_instant"])

    # 2. supersession rules decide which manifest bundle field is authoritative.
    stale = read_kv_txt(consume("stale_version_rules.txt"))
    superseded_marker = stale["superseded_marker"].split(":")[-1]
    retired_bundle = stale["retired_bundle"]
    active_bundle = str(manifest[stale["prefer"]])
    ignored_bundle = str(manifest[stale["ignore"]])
    reject(
        ignored_bundle,
        "manifest {} names bundle {} but it is the retired/superseded bundle; "
        "stale_version_rules.txt prefers {}={}".format(
            stale["ignore"], ignored_bundle, stale["prefer"], active_bundle
        ),
    )

    migration = read_yaml_flat(consume("migration_notice.yml"))
    if migration["superseded_bundle"] != retired_bundle:
        raise SystemExit("supersession record disagrees with stale_version_rules")

    # 3. ledger maps the active bundle to its role key.
    ledger = read_jsonc(consume("bundle_ledger.jsonc"))
    for bundle_id, entry in sorted(ledger.items()):
        if bundle_id != active_bundle and entry["status"] != "active":
            reject(bundle_id, "ledger bundle {} has status {}".format(bundle_id, entry["status"]))
    bundle = ledger[active_bundle]
    if bundle["status"] != "active":
        raise SystemExit("active bundle is not active in the ledger")
    role_key = bundle["role_key"]

    # 4. role index, reached only through the ledger, yields the tenant/param/level.
    index = read_yaml_flat(consume(bundle["index_file"]))
    param_key = index[role_key + ".param_key"]
    tenant_raw = index[role_key + ".tenant"]
    role_level = int(index[role_key + ".role_level"])

    decoy_aliases = read_jsonc(data / "decoy_alias_table.jsonc")
    if tenant_raw in decoy_aliases or param_key in decoy_aliases:
        reject(
            "decoy_alias_table.jsonc",
            "decoy alias table from the retired bundle would rewrite {}->{} and {}->{}".format(
                tenant_raw,
                decoy_aliases.get(tenant_raw),
                param_key,
                decoy_aliases.get(param_key),
            ),
        )

    aliases = {row["from"]: row["to"] for row in load_json(consume("alias_table.json"))["aliases"]}
    tenant = aliases.get(tenant_raw, tenant_raw)

    catalog = {row["id"]: row for row in read_xml_records(consume("tenant_catalog.xml"), "tenant")}
    if catalog[tenant]["status"] != "active":
        raise SystemExit("resolved tenant is not active")
    region = catalog[tenant]["region"]

    # 5. numeric base table.
    base_rows = {row["param_key"]: row for row in read_parquet_rows(consume("base_parameters.parquet"))}
    base = base_rows[param_key]
    if int(base["role_level"]) != role_level:
        raise SystemExit("base table role level disagrees with the role index")

    legacy_overrides = read_conf(data / "legacy_override_table.ini")
    if legacy_overrides.get("bundle") == retired_bundle:
        reject(
            "legacy_override_table.ini",
            "decoy override table: rows belong to retired bundle {} and are marked {}".format(
                retired_bundle, legacy_overrides.get("status")
            ),
        )

    # 6. effective version comes from the documented instant, never from the client.
    versions = load_json(consume("policy_version_map.json"))["versions"]
    candidates = [row for row in versions if int(row["effective_from"]) <= instant]
    effective_version = max(candidates, key=lambda row: int(row["effective_from"]))["version"]

    corpus = load_json(consume("request_corpus.json"))["entries"]
    claims = [
        entry
        for entry in corpus
        if int(entry["at"]) == instant and entry["principal"] == role_key and entry["tenant"] == tenant
    ]
    client_version_ignored = False
    for entry in claims:
        if entry["claimed_version"] != effective_version:
            client_version_ignored = True
            reject(
                entry["claimed_version"],
                "client-claimed version {} on {} is higher-numbered than the version "
                "effective at instant {}; policy_version_map resolves {}".format(
                    entry["claimed_version"], entry["request_id"], instant, effective_version
                ),
            )

    # 7. windows are half-open: [start, end).
    precedence = read_conf(consume("override_precedence.conf"))
    windows = {row["id"]: row for row in read_xml_records(consume("effective_windows.xml"), "window")}

    superseded_windows = read_xml_records(data / "superseded_windows.xml", "window")
    if any(row.get("status") == superseded_marker for row in superseded_windows):
        reject(
            "superseded_windows.xml",
            "decoy windows file: all {} rows carry status {}".format(
                len(superseded_windows), superseded_marker
            ),
        )

    def contains(window, moment):
        return int(window["start"]) <= moment < int(window["end"])

    for window in sorted(windows.values(), key=lambda row: row["id"]):
        if int(window["end"]) == instant:
            reject(
                window["id"],
                "window ends at exactly the effective instant {}; half-open [start, end) "
                "excludes the end instant".format(instant),
            )

    ledger_doc = load_json(consume("override_deltas.json"))
    overrides = sorted(ledger_doc["overrides"], key=lambda row: int(row["seq"]))
    sums = {}
    for row in overrides:
        value = int(row["timeout_ms_delta"])
        entry = sums.setdefault(row["tenant"], {"max_records_delta_sum": 0, "rows": 0, "timeout_ms_delta_sum_ms": 0})
        entry["rows"] += 1
        entry["max_records_delta_sum"] += int(row["max_records_delta"])
        entry["timeout_ms_delta_sum_ms"] += value * 1000 if abs(value) < 100 else value
    ledger_controls = {
        name: ("ok" if sums.get(name) == ledger_doc["controls"][name] else "mismatch")
        for name in sorted(ledger_doc["controls"])
    }
    matches = []
    for override in overrides:
        if override["param_key"] != param_key:
            continue
        if override["status"] != "active":
            reject(
                override["override_id"],
                "override status {} is not active".format(override["status"]),
            )
            continue
        if override["version"] != effective_version:
            reject(
                override["override_id"],
                "override version {} does not match the effective version {}".format(
                    override["version"], effective_version
                ),
            )
            continue
        window = windows.get(override["window_id"])
        if window is None:
            reject(override["override_id"], "override window {} is not an effective window".format(override["window_id"]))
            continue
        if not contains(window, instant):
            reject(
                override["override_id"],
                "window {} [{}, {}) does not contain the effective instant {}".format(
                    window["id"], window["start"], window["end"], instant
                ),
            )
            continue
        matches.append(override)

    if not matches:
        raise SystemExit("no active in-window override for " + param_key)
    selected = matches[0]
    for extra in matches[1:]:
        reject(extra["override_id"], "lower precedence than " + selected["override_id"])

    # 8. tenant multipliers.
    multipliers = {
        row["tenant"]: row for row in read_xlsx_rows(consume("tenant_multiplier_table.xlsx"))
    }
    multiplier = multipliers[tenant]
    if multiplier["region"] != region:
        raise SystemExit("multiplier region disagrees with the tenant catalog")
    mult_bps = int(multiplier["mult_bps"])
    cap = int(multiplier["max_records_cap"])

    region_rows = {row["tenant"]: row for row in read_xlsx_rows(data / "tenant_region_multipliers.xlsx")}
    if tenant not in region_rows:
        reject(
            "tenant_region_multipliers.xlsx",
            "region multiplier table carries no row for {}; tenant_multiplier_table.xlsx is "
            "the authoritative multiplier source".format(tenant),
        )

    # 9. tier curve: the role level is the tier index, unshifted.
    tiers = {int(row["tier"]): row for row in read_parquet_rows(consume("threshold_tier_curve.parquet"))}
    tier = role_level
    base_threshold = int(tiers[tier]["base_threshold"])

    tier_overrides = load_json(data / "threshold_overrides.json")["overrides"]
    conflicting = [row for row in tier_overrides if int(row["tier"]) == tier]
    if len(conflicting) > 1:
        reject(
            "threshold_overrides.json",
            "decoy tier overrides: {} mutually inconsistent rows for tier {} with no "
            "documented selection key; convergence_spec.txt seeds from base_threshold".format(
                len(conflicting), tier
            ),
        )

    # 10. rounding, unit and clamp conventions.
    rules = read_conf(consume("reconciliation_rules.conf"))
    divisor = int(rules["iteration_divisor"])
    unit_factor = int(rules["timeout_unit_factor"])

    convergence = read_kv_txt(consume("convergence_spec.txt"))
    epsilon = int(convergence["convergence_epsilon"])
    max_iterations = int(convergence["max_iterations"])

    read_kv_txt(consume("clamp_rules.txt"))
    read_kv_txt(consume("risk_weight_rounding.txt"))
    # units_reference.txt is colon-separated, not key=value.
    units_text = Path(consume("units_reference.txt")).read_text(encoding="utf-8")
    if "ms = seconds * " + str(unit_factor) not in units_text:
        raise SystemExit("unexpected timeout unit conversion")

    for key, value in read_kv_txt(data / "numeric_constants.env").items():
        if key.startswith("DECOY_") or key.startswith("LEGACY_"):
            reject(
                "numeric_constants.env:" + key,
                "decoy constant {}={} is not a compiled policy value".format(key, value),
            )

    # 11. compile the numbers.
    after_delta_records = int(base["max_records_base"]) + int(selected["max_records_delta"])
    scaled_records = round_half_up(after_delta_records * mult_bps, 1000)
    max_records = min(cap, scaled_records)

    retry_limit = int(base["retry_limit_base"]) + int(selected["retry_limit_delta"])
    timeout_ms = int(base["timeout_seconds_base"]) * unit_factor + int(selected["timeout_ms_delta"])

    risk_weight_eff = int(base["risk_weight_base"]) + int(selected["risk_delta"])
    contribution = round_half_up(risk_weight_eff * mult_bps, 1000)

    iterations = [base_threshold]
    current = base_threshold
    converged = None
    for _ in range(max_iterations):
        nxt = base_threshold + (contribution + current) // divisor
        iterations.append(nxt)
        if abs(nxt - current) <= epsilon:
            converged = nxt
            break
        current = nxt
    if converged is None:
        raise SystemExit("threshold reconciliation did not converge")
    risk_threshold = converged

    schema = load_json(consume("config_schema.json"))
    defaults = load_json(consume("defaults.json"))
    for key, value in defaults["base_config"].items():
        if key.startswith("legacy_"):
            reject(
                "defaults.json:base_config." + key,
                "legacy default {}={} is superseded by the compiled value".format(key, value),
            )
    reject(
        "legacy_policy_memo.pdf",
        "retired bundle {} memo is retained for audit only and must not be compiled".format(
            retired_bundle
        ),
    )

    config = {
        "checksum": schema["checksum"],
        "container": schema["container"],
        "max_records": max_records,
        "mode": defaults["mode"],
        "producer": schema["producer"],
        "profile": schema["profile"],
        "retry_limit": retry_limit,
        "timeout_ms": timeout_ms,
        "trailer": str(defaults["base_config"]["trailer"]),
    }
    resolved = dict(config)
    resolved.update(
        {
            "param_key": param_key,
            "tenant": tenant,
            "effective_version": effective_version,
            "risk_threshold": risk_threshold,
        }
    )

    trace = {
        "active_bundle": active_bundle,
        "effective_version": effective_version,
        "param_key": param_key,
        "tenant": tenant,
        "client_version_ignored": client_version_ignored,
        "applied_overrides": [selected["override_id"]],
        "ledger_controls": ledger_controls,
        "resolution_order": order,
        "rejected_branches": rejected,
    }
    curve = {
        "tier": tier,
        "base_threshold": base_threshold,
        "contribution": contribution,
        "iterations": iterations,
        "converged": converged,
    }
    return resolved, trace, curve


def cmd_init(args):
    schema = load_json(args.schema)
    data = {
        "profile": schema["profile"],
        "producer": schema["producer"],
        "container": schema["container"],
        "checksum": schema["checksum"],
        "mode": "strict-local",
    }
    write_json(args.out, data)
    print("initialized")


def cmd_resolve(args):
    resolved, trace, curve = resolve_policy(args.data_dir)
    out = Path(args.out)
    write_json(out / "policy_resolved.json", resolved)
    write_json(out / "dependency_trace.json", trace)
    write_json(out / "threshold_curve.json", curve)
    print(json.dumps(resolved, sort_keys=True))


def cmd_set(args):
    data = load_json(args.config)
    data[args.key] = coerce(args.value)
    assert_flat(data)
    write_json(args.config, data)
    print("set " + args.key)


def cmd_validate(args):
    schema = load_json(args.schema)
    data = load_json(args.config)
    assert_flat(data)
    required = schema["required_keys"]
    if isinstance(required, str):
        required = [key.strip() for key in required.split(",") if key.strip()]
    missing = [key for key in required if key not in data]
    if missing:
        raise SystemExit("missing: " + ",".join(missing))
    print("ok")


def cmd_profile(args):
    data = Path(args.data_dir)
    resolved = load_json(args.resolved)
    schema = load_json(data / "config_schema.json")
    env = load_json(data / "env_overrides.json")[args.name]
    sidecar = load_json(data / ("sample_config_" + args.name + ".json"))
    profile = {
        "checksum": resolved["checksum"],
        "container": resolved["container"],
        "producer": resolved["producer"],
        "mode": env["mode"],
        "profile": schema["profile"] + "-" + args.name,
        "max_records": int(resolved["max_records"]) + int(sidecar["max_records_delta"]),
        "retry_limit": int(resolved["retry_limit"]) + int(env["retry_limit_delta"]),
        "timeout_ms": int(resolved["timeout_ms"]) + int(env["timeout_ms_delta"]),
        "trailer": resolved["trailer"] + ":" + args.name,
    }
    assert_flat(profile)
    write_json(args.out, profile)
    print("profile " + args.name)


def cmd_pack(args):
    src = Path(args.src)
    names = sorted(path.name for path in src.iterdir() if path.is_file())
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as zf:
        for name in names:
            info = zipfile.ZipInfo(name, date_time=ZIP_EPOCH)
            info.external_attr = ZIP_MODE << 16
            info.compress_type = zipfile.ZIP_STORED
            zf.writestr(info, (src / name).read_bytes())
    print("packed " + ",".join(names))


def cmd_report(args):
    data = load_json(args.config)
    commands = json.loads(args.commands)
    report = {
        "ok": all(entry["returncode"] == 0 for entry in commands),
        "tool": "sentinel-ctl",
        "commands": commands,
        "config_sha256": args.digest,
        "trailer": data["trailer"],
    }
    write_json(args.out, report)
    print("reported")


def cmd_summarize(args):
    data = Path(args.data_dir)
    resolved = load_json(args.resolved)
    rules = load_json(data / "validation_rules.json")
    schema = load_json(data / "config_schema.json")
    inputs = sorted(path.name for path in data.iterdir() if path.is_file())
    summary = {
        "artifact_count": len(rules["required_artifacts"]),
        "artifacts": list(rules["required_artifacts"]),
        "profiles": list(rules["profiles"]),
        "format_tag": schema["profile"],
        "trailer": resolved["trailer"],
        "input_count": len(inputs),
        "inputs": inputs,
    }
    write_json(args.out, summary)
    print("summarized " + str(len(inputs)))


def cmd_verify(args):
    data = Path(args.data_dir)
    rules = load_json(data / "validation_rules.json")
    resolved = load_json(args.resolved)
    curve = load_json(args.curve)
    trace = load_json(args.trace)
    config = load_json(args.config)
    commands = json.loads(Path(args.commands).read_text(encoding="utf-8"))

    out_dir = Path(args.out_dir)
    own = Path(args.out).name
    required = list(rules["required_artifacts"])
    present = [name for name in required if (out_dir / name).exists() or name == own]

    config_keys = {key for key in resolved if key not in ("param_key", "tenant", "effective_version", "risk_threshold")}
    expected = {key: resolved[key] for key in config_keys}

    profiles = {}
    for name in rules["profiles"]:
        profile = load_json(out_dir / ("profile_" + name + ".json"))
        profiles[name] = {"trailer": profile["trailer"]}

    checks = {
        "all_artifacts_present": sorted(present) == sorted(required),
        "config_matches_policy": config == expected,
        "config_scalar_flat": all(
            isinstance(value, (str, int, float, bool)) and not isinstance(value, (dict, list))
            for value in config.values()
        ),
        "command_failures": [entry["argv"] for entry in commands if entry["returncode"] != 0],
        "required_artifacts": required,
        "profiles": profiles,
    }
    report = {
        "ok": (
            checks["all_artifacts_present"]
            and checks["config_matches_policy"]
            and checks["config_scalar_flat"]
            and not checks["command_failures"]
        ),
        "checks": checks,
        "policy_resolved": resolved,
        "threshold_curve": curve,
        "dependency_trace": trace,
    }
    write_json(args.out, report)
    print("verified ok=" + str(report["ok"]).lower())


def build_parser():
    parser = argparse.ArgumentParser(prog="sentinel-ctl")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init")
    p.add_argument("--schema", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("resolve")
    p.add_argument("--data-dir", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_resolve)

    p = sub.add_parser("set")
    p.add_argument("--config", required=True)
    p.add_argument("--key", required=True)
    p.add_argument("--value", required=True)
    p.set_defaults(func=cmd_set)

    p = sub.add_parser("validate")
    p.add_argument("--schema", required=True)
    p.add_argument("--config", required=True)
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("profile")
    p.add_argument("--data-dir", required=True)
    p.add_argument("--resolved", required=True)
    p.add_argument("--name", required=True, choices=["dev", "prod"])
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_profile)

    p = sub.add_parser("pack")
    p.add_argument("--src", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_pack)

    p = sub.add_parser("export-report")
    p.add_argument("--config", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--digest", required=True)
    p.add_argument("--commands", required=True)
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("summarize")
    p.add_argument("--data-dir", required=True)
    p.add_argument("--resolved", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_summarize)

    p = sub.add_parser("verify")
    p.add_argument("--data-dir", required=True)
    p.add_argument("--resolved", required=True)
    p.add_argument("--curve", required=True)
    p.add_argument("--trace", required=True)
    p.add_argument("--config", required=True)
    p.add_argument("--commands", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_verify)

    return parser


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
