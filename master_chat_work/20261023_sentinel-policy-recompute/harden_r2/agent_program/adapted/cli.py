from __future__ import annotations

import argparse
import configparser
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

# sentinel-ctl: policy bundle compiler.
# The authoritative policy is reconstructed from the reference material; the
# rule binding each value is stated in the reference file holding that data.

JSON_INDENT = 2
ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)
ZIP_MODE = 0o100644


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dump_json(data):
    return json.dumps(data, indent=JSON_INDENT, sort_keys=True) + "\n"


def write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(dump_json(data), encoding="utf-8")


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


def required_keys(schema):
    keys = schema["required_keys"]
    if isinstance(keys, str):
        return [part.strip() for part in keys.split(",") if part.strip()]
    return list(keys)


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


def read_text(path):
    return Path(path).read_text(encoding="utf-8")


def read_kv_text(path):
    out = {}
    for line in read_text(path).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith(";"):
            continue
        key, sep, value = stripped.partition("=")
        if not sep:
            continue
        out[key.strip()] = value.strip()
    return out


def read_ini_sections(path):
    parser = configparser.ConfigParser()
    parser.optionxform = str
    parser.read(path, encoding="utf-8")
    return {section: dict(parser.items(section)) for section in parser.sections()}


def read_conf(path):
    flat = {}
    for values in read_ini_sections(path).values():
        flat.update(values)
    return flat


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


def scale_half_up(value, bps, unit):
    """round_half_up(value * bps / unit): a half value rounds upward."""
    return (value * bps + unit // 2) // unit


def resolve_policy(data_dir):
    data = Path(data_dir)
    order = []
    rejected = []

    def consume(name):
        if name not in order:
            order.append(name)
        return data / name

    def reject(name, reason):
        rejected.append({"name": name, "reason": reason})

    # 1. boot manifest: entry point of the dependency chain.
    manifest = read_toml(consume("boot_manifest.toml"))["manifest"]
    instant = int(manifest["effective_instant"])

    # 2. stale/superseded handling states which manifest field binds.
    stale = read_kv_text(consume("stale_version_rules.txt"))
    prefer_field = stale["prefer"]
    ignore_field = stale["ignore"]
    active_bundle = str(manifest[prefer_field])
    ignored_bundle = str(manifest[ignore_field])
    migration = read_yaml_flat(consume("migration_notice.yml"))

    # 3. bundle ledger: the active bundle names the index file and the role key.
    ledger = read_jsonc(consume("bundle_ledger.jsonc"))
    entry = ledger[active_bundle]
    if entry.get("status") != "active":
        raise SystemExit("bundle " + active_bundle + " is not active in the ledger")
    for bundle_id in sorted(ledger):
        if bundle_id == active_bundle:
            continue
        status = ledger[bundle_id].get("status", "unknown")
        if bundle_id == ignored_bundle:
            reject(
                bundle_id,
                "ledger status " + status + "; " + ignore_field + " is ignored and " + prefer_field
                + " " + active_bundle + " binds per stale_version_rules.txt (migration_notice.yml: "
                + str(migration.get("reason", "")) + ")",
            )
            reject(ledger[bundle_id]["role_key"], "role key of superseded bundle " + bundle_id)
        else:
            reject(bundle_id, "ledger status " + status + "; not the " + prefer_field)
    reject(
        "legacy_override_table.ini",
        "override table of superseded bundle " + ignored_bundle
        + "; overrides bind from override_deltas.json",
    )
    reject(
        "principal_alias_table.jsonc",
        "retired-bundle aliases; the principal is resolved through the ledger index file",
    )
    reject("legacy_policy_memo.pdf", "audit-only memo of superseded bundle " + ignored_bundle)

    role_key = entry["role_key"]
    index = read_yaml_flat(consume(entry["index_file"]))
    param_key = index[role_key + ".param_key"]
    tenant = index[role_key + ".tenant"]
    role_level = int(index[role_key + ".role_level"])

    # 4. base numeric table of the resolved principal.
    base_rows = {row["param_key"]: row for row in read_parquet_rows(consume("base_parameters.parquet"))}
    base = base_rows[param_key]

    # 5. effective version: greatest effective_from not after the instant.
    version_map = load_json(consume("policy_version_map.json"))
    candidates = [v for v in version_map["versions"] if int(v["effective_from"]) <= instant]
    newest = max(int(v["effective_from"]) for v in candidates)
    effective_version = [v["version"] for v in candidates if int(v["effective_from"]) == newest][-1]

    # 6. the client-claimed version never binds.
    corpus = load_json(consume("request_corpus.json"))
    claimed = None
    for request in corpus["entries"]:
        if int(request["at"]) == instant and request["tenant"] == tenant and request["principal"] == role_key:
            claimed = request["claimed_version"]
            break
    if claimed is None:
        claimed = corpus["entries"][0]["claimed_version"]
    if claimed != effective_version:
        reject(
            claimed,
            "client-claimed version in request_corpus.json; the effective version "
            + effective_version + " from policy_version_map.json binds",
        )

    # 7. effective-time windows; the superseded set never binds.
    windows = {w["id"]: w for w in read_xml_records(consume("effective_windows.xml"), "window")}
    reject("superseded_windows.xml", "superseded effective-time windows; effective_windows.xml binds")

    # 8. override selection, tenant allowance and deltas.
    precedence = read_ini_sections(consume("override_precedence.conf"))["precedence"]
    if "active" not in precedence["select"]:
        raise SystemExit("unsupported override selection rule: " + precedence["select"])
    regions = {t["id"]: t["region"] for t in read_xml_records(consume("tenant_catalog.xml"), "tenant")}
    allowance = int(read_ini_sections(consume("quota_limits.cfg"))["override_allowance"][regions[tenant]])
    ledger_doc = load_json(consume("override_deltas.json"))

    rules = read_ini_sections(consume("reconciliation_rules.conf"))["reconcile"]
    unit_factor = int(rules["timeout_unit_factor"])
    stated = re.search(r"ms\s*=\s*seconds\s*\*\s*(\d+)", read_text(consume("units_reference.txt")))
    if int(stated.group(1)) != unit_factor:
        raise SystemExit("timeout unit factor disagrees with units_reference.txt")
    constants = read_kv_text(consume("numeric_constants.env"))
    if int(constants["MS_PER_SECOND"]) != unit_factor:
        raise SystemExit("MS_PER_SECOND disagrees with the timeout unit factor")
    for name in sorted(constants):
        if name.startswith("LEGACY_"):
            reject("numeric_constants.env:" + name, "legacy constant; the base tables bind")

    def row_timeout_ms(row):
        # a rev 1 row stores timeout_ms_delta in whole seconds
        delta = int(row["timeout_ms_delta"])
        return delta * unit_factor if int(row["rev"]) == 1 else delta

    sums = {}
    for row in ledger_doc["overrides"]:
        totals = sums.setdefault(
            row["tenant"], {"max_records_delta_sum": 0, "rows": 0, "timeout_ms_delta_sum_ms": 0}
        )
        totals["rows"] += 1
        totals["max_records_delta_sum"] += int(row["max_records_delta"])
        totals["timeout_ms_delta_sum_ms"] += row_timeout_ms(row)
    ledger_controls = {
        name: "ok" if sums.get(name) == control else "mismatch"
        for name, control in ledger_doc["controls"].items()
    }

    def selection_failure(row):
        if row["status"] != "active":
            return "override status " + row["status"]
        if row["version"] != effective_version:
            return "override version " + row["version"] + " is not the effective version " + effective_version
        window = windows.get(row["window_id"])
        if window is None:
            return "window " + row["window_id"] + " is not in effective_windows.xml"
        if window["version"] != effective_version:
            return (
                "window " + row["window_id"] + " carries version " + window["version"]
                + ", not the effective version " + effective_version
            )
        if not int(window["start"]) <= instant < int(window["end"]):
            return (
                "window " + row["window_id"] + " [" + window["start"] + "," + window["end"]
                + ") does not contain the effective instant"
            )
        return None

    applied = []
    used = 0
    tenant_rows = sorted(
        (row for row in ledger_doc["overrides"] if row["tenant"] == tenant), key=lambda r: int(r["seq"])
    )
    for row in tenant_rows:
        failure = selection_failure(row)
        if failure is not None:
            reject(row["override_id"], failure)
            continue
        if used >= allowance:
            reject(row["override_id"], "tenant override allowance " + str(allowance) + " already used up")
            continue
        used += 1
        if row["param_key"] == param_key:
            applied.append(row)
        else:
            reject(
                row["override_id"],
                "selected row of principal " + row["param_key"] + ", not the resolved principal " + param_key,
            )

    # 9. tenant multiplier and cap.
    multipliers = {row["tenant"]: row for row in read_xlsx_rows(consume("tenant_multiplier_table.xlsx"))}
    mult = multipliers[tenant]
    mult_bps = int(mult["mult_bps"])
    cap = int(mult["max_records_cap"])
    glossary = read_kv_text(consume("glossary.txt"))
    bps_unit = int(re.search(r"(\d+) bps = 1.0x", glossary["bps"]).group(1))
    if int(constants["MULT_BPS_DEFAULT"]) != bps_unit:
        raise SystemExit("MULT_BPS_DEFAULT disagrees with the basis-point unit")

    # 10. max_records: the clamp order is stated in clamp_rules.txt.
    if "min(cap, scaled)" not in read_text(consume("clamp_rules.txt")):
        raise SystemExit("unsupported max_records clamp order in clamp_rules.txt")
    after_delta = int(base["max_records_base"]) + sum(int(row["max_records_delta"]) for row in applied)
    max_records = min(cap, scale_half_up(after_delta, mult_bps, bps_unit))

    retry_limit = int(base["retry_limit_base"]) + sum(int(row["retry_limit_delta"]) for row in applied)
    timeout_ms = int(base["timeout_seconds_base"]) * unit_factor + sum(row_timeout_ms(row) for row in applied)

    # 11. risk contribution: per-term rounding per risk_weight_rounding.txt.
    if "sum of round_half_up(term" not in read_text(consume("risk_weight_rounding.txt")):
        raise SystemExit("unsupported risk weight rounding rule in risk_weight_rounding.txt")
    terms = [int(base["risk_weight_base"])] + [int(row["risk_delta"]) for row in applied]
    contribution = sum(scale_half_up(term, mult_bps, bps_unit) for term in terms)

    # 12. threshold reconciliation over the tier curve.
    tiers = {int(row["tier"]): row for row in read_parquet_rows(consume("threshold_tier_curve.parquet"))}
    base_threshold = int(tiers[role_level]["base_threshold"])
    spec = read_kv_text(consume("convergence_spec.txt"))
    epsilon = int(spec["convergence_epsilon"])
    max_iterations = int(spec["max_iterations"])
    divisor = int(rules["iteration_divisor"])
    current = base_threshold
    iterations = [current]
    converged = False
    for _ in range(max_iterations):
        following = base_threshold + (contribution + current) // divisor
        iterations.append(following)
        step = abs(following - current)
        current = following
        if step <= epsilon:
            converged = True
            break
    if not converged:
        raise SystemExit("threshold reconciliation did not converge")
    risk_threshold = current

    # 13. identity fields from the manifest's schema and trailer references.
    schema = load_json(consume(manifest["schema_ref"]))
    defaults = load_json(consume(manifest["trailer_ref"]))
    for name in sorted(defaults["base_config"]):
        if name.startswith("legacy_"):
            reject(
                manifest["trailer_ref"] + ":base_config." + name,
                "legacy default; the resolved policy binds",
            )

    config_values = {
        "profile": schema["profile"],
        "producer": schema["producer"],
        "container": schema["container"],
        "checksum": schema["checksum"],
        "mode": defaults["mode"],
        "max_records": max_records,
        "retry_limit": retry_limit,
        "timeout_ms": timeout_ms,
        "trailer": str(defaults["base_config"]["trailer"]),
    }
    needed = required_keys(schema)
    if set(needed) != set(config_values):
        raise SystemExit("resolved policy does not cover the schema required keys")

    resolved = {key: config_values[key] for key in needed}
    resolved["param_key"] = param_key
    resolved["tenant"] = tenant
    resolved["effective_version"] = effective_version
    resolved["risk_threshold"] = risk_threshold

    trace = {
        "active_bundle": active_bundle,
        "effective_version": effective_version,
        "param_key": param_key,
        "tenant": tenant,
        "client_version_ignored": claimed != effective_version,
        "applied_overrides": [row["override_id"] for row in applied],
        "ledger_controls": ledger_controls,
        "resolution_order": order,
        "rejected_branches": rejected,
    }
    curve = {
        "tier": role_level,
        "base_threshold": base_threshold,
        "contribution": contribution,
        "iterations": iterations,
        "converged": risk_threshold,
    }
    return resolved, trace, curve


def policy_config(resolved, schema):
    return {key: resolved[key] for key in required_keys(schema)}


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
    missing = [key for key in required_keys(schema) if key not in data]
    if missing:
        raise SystemExit("missing: " + ",".join(missing))
    print("ok")


def cmd_profile(args):
    data = Path(args.data_dir)
    config = load_json(args.config)
    schema = load_json(data / "config_schema.json")
    env = load_json(data / "env_overrides.json")[args.name]
    sidecar = load_json(data / ("sample_config_" + args.name + ".json"))
    profile = {
        "checksum": config["checksum"],
        "container": config["container"],
        "producer": config["producer"],
        "mode": env["mode"],
        "profile": schema["profile"] + "-" + args.name,
        "max_records": int(config["max_records"]) + int(sidecar["max_records_delta"]),
        "retry_limit": int(config["retry_limit"]) + int(env["retry_limit_delta"]),
        "timeout_ms": int(config["timeout_ms"]) + int(env["timeout_ms_delta"]),
        "trailer": str(config["trailer"]) + ":" + args.name,
    }
    assert_flat(profile)
    write_json(args.out, profile)
    print("profile " + args.name)


def cmd_report(args):
    data = load_json(args.config)
    commands = json.loads(args.commands)
    report = {
        "ok": all(int(command["returncode"]) == 0 for command in commands),
        "tool": "sentinel-ctl",
        "commands": commands,
        "config_sha256": args.digest,
        "trailer": data.get("trailer"),
    }
    write_json(args.out, report)
    print("reported")


def cmd_summary(args):
    data = Path(args.data_dir)
    rules = load_json(data / "validation_rules.json")
    schema = load_json(data / "config_schema.json")
    defaults = load_json(data / "defaults.json")
    inputs = sorted(entry.name for entry in data.iterdir() if entry.is_file())
    summary = {
        "artifact_count": len(rules["required_artifacts"]),
        "artifacts": list(rules["required_artifacts"]),
        "profiles": list(rules["profiles"]),
        "format_tag": schema["profile"],
        "trailer": str(defaults["base_config"]["trailer"]),
        "input_count": len(inputs),
        "inputs": inputs,
    }
    write_json(args.out, summary)
    print("summarized")


def cmd_validation(args):
    data = Path(args.data_dir)
    rules = load_json(data / "validation_rules.json")
    schema = load_json(data / "config_schema.json")
    resolved = load_json(Path(args.resolved) / "policy_resolved.json")
    trace = load_json(Path(args.resolved) / "dependency_trace.json")
    curve = load_json(Path(args.resolved) / "threshold_curve.json")
    config = load_json(args.config)
    commands = json.loads(args.commands)
    out = Path(args.out).resolve()
    artifacts = Path(args.artifacts_dir)

    # the report itself is the artifact being written by this run
    present = all(
        (artifacts / name).exists() or (artifacts / name).resolve() == out
        for name in rules["required_artifacts"]
    )
    profiles = {}
    for name in rules["profiles"]:
        profile = load_json(artifacts / ("profile_" + name + ".json"))
        profiles[name] = {"trailer": profile["trailer"]}
    checks = {
        "all_artifacts_present": present,
        "config_matches_policy": config == policy_config(resolved, schema),
        "config_scalar_flat": all(not isinstance(value, (dict, list)) for value in config.values()),
        "command_failures": [c["argv"] for c in commands if int(c["returncode"]) != 0],
        "required_artifacts": list(rules["required_artifacts"]),
        "profiles": profiles,
    }
    report = {
        "ok": (
            checks["all_artifacts_present"]
            and checks["config_matches_policy"]
            and checks["config_scalar_flat"]
            and not checks["command_failures"]
            and all(state == "ok" for state in trace["ledger_controls"].values())
        ),
        "checks": checks,
        "policy_resolved": resolved,
        "threshold_curve": curve,
        "dependency_trace": trace,
    }
    write_json(args.out, report)
    print("validated")


def cmd_package(args):
    source = Path(args.source)
    members = sorted(
        path for path in source.rglob("*") if path.is_file() and "__pycache__" not in path.parts
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as zf:
        for path in members:
            info = zipfile.ZipInfo(str(path.relative_to(source)), date_time=ZIP_EPOCH)
            info.external_attr = ZIP_MODE << 16
            info.create_system = 3
            zf.writestr(info, path.read_bytes())
    print("packaged " + str(len(members)))


def main():
    parser = argparse.ArgumentParser(prog="sentinel-ctl")
    sub = parser.add_subparsers(dest="command")

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
    p.add_argument("--config", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_profile)

    p = sub.add_parser("export-report")
    p.add_argument("--config", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--digest", required=True)
    p.add_argument("--commands", required=True)
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("export-summary")
    p.add_argument("--data-dir", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_summary)

    p = sub.add_parser("export-validation")
    p.add_argument("--data-dir", required=True)
    p.add_argument("--resolved", required=True)
    p.add_argument("--config", required=True)
    p.add_argument("--artifacts-dir", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--commands", required=True)
    p.set_defaults(func=cmd_validation)

    p = sub.add_parser("package")
    p.add_argument("--source", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_package)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
