#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

SOURCE_ARCHIVE = Path("/app/data/tool.zip")
DATA = Path("/app/data")
TOOL = Path("/app/tool").resolve()
OUT = Path("/app/out")
POLICY_KEYS = ["max_records", "retry_limit", "timeout_ms", "trailer"]
PROFILE_KEYS = ["profile", "mode", "max_records", "retry_limit", "timeout_ms", "trailer"]
RESOLVE_SCRATCH = Path("/tmp/sentinel-resolve")
SHIPPED_SCRATCH = Path("/tmp/sentinel-shipped-resolve")

CORRECT_CLI = r'''from __future__ import annotations

import argparse
import configparser
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

# sentinel-ctl: policy bundle compiler. Repaired reference.
# configuration must be flat: only scalar values are permitted anywhere.


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def half_up_bps(amount, bps):
    # round-half-up of amount * bps / 1000 for non-negative operands
    return (amount * bps + 500) // 1000


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
        value = value.strip()
        if value.startswith("#"):
            value = ""
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


def read_env_kv(path):
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        out[key.strip()] = value.strip()
    return out


def read_txt_kv(path):
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        out[key.strip()] = value.strip()
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
        shared = []
        if "xl/sharedStrings.xml" in zf.namelist():
            shared_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in shared_root.iter(ns + "si"):
                shared.append("".join(t.text or "" for t in si.iter(ns + "t")))
        sheet_root = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))
        rows = []
        for row in sheet_root.iter(ns + "row"):
            cells = {}
            for cell in row.iter(ns + "c"):
                ref = cell.get("r", "A1")
                col = _col_to_idx(ref)
                ctype = cell.get("t")
                vnode = cell.find(ns + "v")
                if ctype == "inlineStr":
                    tnode = cell.find(ns + "is/" + ns + "t")
                    value = tnode.text if tnode is not None else ""
                elif vnode is None:
                    value = ""
                elif ctype == "s":
                    value = shared[int(vnode.text)]
                else:
                    value = vnode.text
                cells[col] = value
            rows.append(cells)
    header = [rows[0][i] for i in sorted(rows[0])]
    records = []
    for cells in rows[1:]:
        record = {}
        for i, name in enumerate(header):
            record[name] = cells.get(i, "")
        records.append(record)
    return records


def read_parquet_rows(path):
    import pyarrow.parquet as pq

    table = pq.read_table(path)
    return table.to_pylist()


def effective_version(version_rows, instant):
    chosen = None
    for row in version_rows:
        if int(row["effective_from"]) <= instant:
            if chosen is None or int(row["effective_from"]) > int(chosen["effective_from"]):
                chosen = row
    return chosen["version"]


def resolve_policy(data_dir):
    data = Path(data_dir)
    order = []

    def note(name):
        order.append(name)

    manifest = read_toml(data / "boot_manifest.toml")["manifest"]
    note("boot_manifest.toml")
    active_bundle = str(manifest["active_bundle_id"])
    instant = int(manifest["effective_instant"])

    ledger = read_jsonc(data / "bundle_ledger.jsonc")
    note("bundle_ledger.jsonc")
    if active_bundle not in ledger or ledger[active_bundle]["status"] != "active":
        raise SystemExit("bundle " + active_bundle + " is not active in bundle_ledger.jsonc")

    migration = read_yaml_flat(data / "migration_notice.yml")
    note("migration_notice.yml")
    superseded_bundle = migration.get("superseded_bundle")

    role_key = ledger[active_bundle]["role_key"]
    index = read_yaml_flat(data / "principal_role_index.yaml")
    note("principal_role_index.yaml")
    param_key = index[role_key + ".param_key"]
    tenant = index[role_key + ".tenant"]
    role_level = int(index[role_key + ".role_level"])

    base_rows = {row["param_key"]: row for row in read_parquet_rows(data / "base_parameters.parquet")}
    note("base_parameters.parquet")
    base = base_rows[param_key]

    version_rows = load_json(data / "policy_version_map.json")["versions"]
    note("policy_version_map.json")
    version = effective_version(version_rows, instant)

    corpus = load_json(data / "request_corpus.json")
    note("request_corpus.json")
    client_claimed_version = corpus["entries"][0]["claimed_version"]

    windows = {w["id"]: w for w in read_xml_records(data / "effective_windows.xml", "window")}
    note("effective_windows.xml")

    ledger_doc = load_json(data / "override_deltas.json")
    note("override_deltas.json")
    overrides = sorted(ledger_doc["overrides"], key=lambda row: int(row["seq"]))

    def delta_ms(row):
        value = int(row["timeout_ms_delta"])
        return value * 1000 if int(row["rev"]) == 1 else value

    recomputed = {}
    for row in overrides:
        entry = recomputed.setdefault(row["tenant"], {"rows": 0, "max_records_delta_sum": 0, "timeout_ms_delta_sum_ms": 0})
        entry["rows"] += 1
        entry["max_records_delta_sum"] += int(row["max_records_delta"])
        entry["timeout_ms_delta_sum_ms"] += delta_ms(row)
    ledger_controls = {}
    for name, stored in sorted(ledger_doc["controls"].items()):
        got = recomputed.get(name, {"rows": 0, "max_records_delta_sum": 0, "timeout_ms_delta_sum_ms": 0})
        same = all(int(stored[key]) == got[key] for key in got)
        ledger_controls[name] = "ok" if same else "mismatch"

    allowance_rows = read_conf(data / "quota_limits.cfg")
    note("quota_limits.cfg")
    remaining = int(allowance_rows[tenant])

    applied = []
    rejected_overrides = []
    for override in overrides:
        if override["tenant"] != tenant:
            continue
        window = windows.get(override["window_id"])
        if override["status"] != "active":
            reason = "status-" + override["status"]
        elif window is None:
            reason = "unknown-window"
        elif not (int(window["start"]) <= instant < int(window["end"])):  # half-open [start, end)
            reason = "window-excludes-effective-instant"
        elif window["version"] != version:
            reason = "window-version-" + window["version"]
        elif override["version"] != version:
            reason = "row-version-" + override["version"]
        elif remaining <= 0:
            reason = "allowance-used-up"
        else:
            remaining -= 1
            if override["param_key"] == param_key:
                applied.append(override)
            continue
        if override["param_key"] == param_key:
            rejected_overrides.append({"override": override["override_id"], "reason": reason})

    multipliers = {row["tenant"]: row for row in read_xlsx_rows(data / "tenant_multiplier_table.xlsx")}
    note("tenant_multiplier_table.xlsx")
    mult = multipliers[tenant]
    mult_bps = int(mult["mult_bps"])
    cap = int(mult["max_records_cap"])

    tiers = {int(row["tier"]): row for row in read_parquet_rows(data / "threshold_tier_curve.parquet")}
    note("threshold_tier_curve.parquet")
    base_threshold = int(tiers[role_level]["base_threshold"])

    rules = read_conf(data / "reconciliation_rules.conf")
    note("reconciliation_rules.conf")
    factor = int(rules["timeout_unit_factor"])
    divisor = int(rules["iteration_divisor"])

    conv = read_txt_kv(data / "convergence_spec.txt")
    note("convergence_spec.txt")
    epsilon = int(conv["convergence_epsilon"])

    after_delta_mr = int(base["max_records_base"]) + sum(int(row["max_records_delta"]) for row in applied)
    scaled_mr = half_up_bps(after_delta_mr, mult_bps)
    max_records = min(cap, scaled_mr)
    retry_limit = int(base["retry_limit_base"]) + sum(int(row["retry_limit_delta"]) for row in applied)
    timeout_ms = int(base["timeout_seconds_base"]) * factor + sum(delta_ms(row) for row in applied)

    risk_terms = [int(base["risk_weight_base"])] + [int(row["risk_delta"]) for row in applied]
    contribution = sum(half_up_bps(term, mult_bps) for term in risk_terms)
    sequence = [base_threshold]
    while True:
        nxt = base_threshold + (contribution + sequence[-1]) // divisor
        sequence.append(nxt)
        if abs(nxt - sequence[-2]) <= epsilon:
            break
    risk_threshold = sequence[-1]

    defaults = load_json(data / "defaults.json")
    note("defaults.json")
    schema = load_json(data / "config_schema.json")
    note("config_schema.json")
    trailer = str(defaults["base_config"]["trailer"])

    resolved = {
        "profile": schema["profile"],
        "producer": schema["producer"],
        "container": schema["container"],
        "checksum": defaults["checksum"],
        "mode": defaults["mode"],
        "max_records": max_records,
        "retry_limit": retry_limit,
        "timeout_ms": timeout_ms,
        "risk_threshold": risk_threshold,
        "trailer": trailer,
        "param_key": param_key,
        "tenant": tenant,
        "effective_version": version,
    }
    trace = {
        "active_bundle": active_bundle,
        "effective_version": version,
        "param_key": param_key,
        "tenant": tenant,
        "resolution_order": order,
        "client_version_ignored": True,
        "applied_overrides": [row["override_id"] for row in applied],
        "ledger_controls": ledger_controls,
        "rejected_branches": [
            {"bundle": superseded_bundle, "reason": "superseded", "evidence": "migration_notice.yml"},
            {"file": "legacy_override_table.ini", "reason": "superseded-legacy-bundle"},
            {"file": "superseded_windows.xml", "reason": "window-outside-effective-instant"},
            {"version": client_claimed_version, "reason": "client-claimed"},
            *rejected_overrides,
        ],
    }
    curve = {
        "tier": role_level,
        "base_threshold": base_threshold,
        "contribution": contribution,
        "iterations": sequence,
        "converged": risk_threshold,
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
    required = schema["required_keys"].split(",")
    missing = [key for key in required if key not in data]
    if missing:
        raise SystemExit("missing: " + ",".join(missing))
    print("ok")


def cmd_report(args):
    data = load_json(args.config)
    assert_flat(data)
    commands = json.loads(args.commands)
    report = {
        "ok": True,
        "tool": "sentinel-ctl",
        "config_path": args.config,
        "config_sha256": args.digest,
        "commands": commands,
        "trailer": data.get("trailer"),
    }
    write_json(args.out, report)
    print("reported")


def main():
    parser = argparse.ArgumentParser(prog="sentinel-ctl")
    sub = parser.add_subparsers(dest="command", required=True)

    subcommand = sub.add_parser("init")
    subcommand.add_argument("--schema", required=True)
    subcommand.add_argument("--out", required=True)
    subcommand.set_defaults(func=cmd_init)

    subcommand = sub.add_parser("resolve")
    subcommand.add_argument("--data-dir", required=True)
    subcommand.add_argument("--out", required=True)
    subcommand.set_defaults(func=cmd_resolve)

    subcommand = sub.add_parser("set")
    subcommand.add_argument("--config", required=True)
    subcommand.add_argument("--key", required=True)
    subcommand.add_argument("--value", required=True)
    subcommand.set_defaults(func=cmd_set)

    subcommand = sub.add_parser("validate")
    subcommand.add_argument("--schema", required=True)
    subcommand.add_argument("--config", required=True)
    subcommand.set_defaults(func=cmd_validate)

    subcommand = sub.add_parser("export-report")
    subcommand.add_argument("--config", required=True)
    subcommand.add_argument("--out", required=True)
    subcommand.add_argument("--digest", required=True)
    subcommand.add_argument("--commands", required=True)
    subcommand.set_defaults(func=cmd_report)

    args = parser.parse_args()
    args.func(args)


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
                raise SystemExit("unsafe source member: " + repr(info.filename))
            dest = (TOOL / Path(*rel.parts)).resolve()
            if not dest.is_relative_to(TOOL):
                raise SystemExit("escaping source member: " + repr(info.filename))
            if info.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(zf.read(info))


def repair_cli() -> None:
    (TOOL / "cli.py").write_text(CORRECT_CLI, encoding="utf-8")


def dump_json(path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_data(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def run_cli(*args):
    cmd = [sys.executable, str(TOOL / "cli.py"), *args]
    result = subprocess.run(cmd, cwd=TOOL, text=True, capture_output=True, timeout=60, check=False)
    entry = {"argv": ["python3", "cli.py", *args], "returncode": result.returncode, "stdout": result.stdout.strip()}
    print(json.dumps(entry, sort_keys=True))
    if result.stderr.strip():
        print("stderr: " + result.stderr.strip()[-2000:])
    return entry


def inspect_shipped_tool() -> None:
    source = (TOOL / "cli.py").read_text(encoding="utf-8").splitlines()
    print("\n".join(source[:30]))
    run_cli("resolve", "--data-dir", str(DATA), "--out", str(SHIPPED_SCRATCH))


def self_check_ledger() -> None:
    # A ledger built here, unlike the shipped one: another t-atlas principal passes first, the
    # allowance of 3 runs out before the last K042 row, a rev 2 row sits under 100 ms, a rev 1 row
    # carries seconds, and the two applied risk deltas round differently one by one than summed.
    corpus = Path(tempfile.mkdtemp(prefix="sentinel-selfcheck-"))
    for path in DATA.iterdir():
        if path.is_file():
            shutil.copyfile(path, corpus / path.name)
    ledger = json.loads((corpus / "override_deltas.json").read_text(encoding="utf-8"))
    own = [
        ("OV-SC-1", "K118", 2, 30, 0, 0, 0),
        ("OV-SC-2", "K042", 2, 60, -40, 1, 2),
        ("OV-SC-3", "K042", 1, 2, -10, 0, 2),
        ("OV-SC-4", "K042", 2, 400, -30, 1, 5),
    ]
    rows = [{"max_records_delta": mr, "override_id": oid, "param_key": key, "retry_limit_delta": rr,
             "rev": rev, "risk_delta": risk, "seq": seq, "status": "active", "tenant": "t-atlas",
             "timeout_ms_delta": td, "version": "v100", "window_id": "WIN-AUTH"}
            for seq, (oid, key, rev, td, mr, rr, risk) in enumerate(own, start=1)]
    kept = [row for row in ledger["overrides"] if not (row["tenant"] == "t-atlas" and row["seq"] <= 6)]
    ledger["overrides"] = rows + kept
    atlas = [row for row in ledger["overrides"] if row["tenant"] == "t-atlas"]
    ledger["controls"]["t-atlas"] = {
        "max_records_delta_sum": sum(row["max_records_delta"] for row in atlas),
        "rows": len(atlas),
        "timeout_ms_delta_sum_ms": sum(row["timeout_ms_delta"] * (1000 if row["rev"] == 1 else 1) for row in atlas),
    }
    (corpus / "override_deltas.json").write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    quota = (corpus / "quota_limits.cfg").read_text(encoding="utf-8")
    (corpus / "quota_limits.cfg").write_text(re.sub(r"(?m)^t-atlas = \d+$", "t-atlas = 3", quota), encoding="utf-8")

    out = corpus / "resolved"
    entry = run_cli("resolve", "--data-dir", str(corpus), "--out", str(out))
    if entry["returncode"] != 0:
        raise SystemExit(entry)
    resolved = json.loads(entry["stdout"])
    trace = json.loads((out / "dependency_trace.json").read_text(encoding="utf-8"))
    curve = json.loads((out / "threshold_curve.json").read_text(encoding="utf-8"))
    # by hand: OV-SC-1 uses the first unit, OV-SC-2 and OV-SC-3 the next two, OV-SC-4 is cut.
    # max_records min(285, half_up(250 * 1.075)) = 269; retry 2 + 1 + 0 = 3;
    # timeout 2000 + 60 + 2 * 1000 = 4060; contribution 61 + 2 + 2 = 65 (66 if rounded once).
    expected = {"applied_overrides": ["OV-SC-2", "OV-SC-3"], "max_records": 269, "retry_limit": 3,
                "timeout_ms": 4060, "contribution": 65, "t-atlas control": "ok"}
    got = {"applied_overrides": trace["applied_overrides"], "max_records": resolved["max_records"],
           "retry_limit": resolved["retry_limit"], "timeout_ms": resolved["timeout_ms"],
           "contribution": curve["contribution"], "t-atlas control": trace["ledger_controls"]["t-atlas"]}
    print("self-check expected " + json.dumps(expected, sort_keys=True))
    print("self-check got      " + json.dumps(got, sort_keys=True))
    if got != expected:
        raise SystemExit("self-check failed on the constructed ledger")
    shutil.rmtree(corpus)


def package_tool() -> None:
    archive = OUT / "tool.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as zf:
        for path in sorted(p for p in TOOL.rglob("*") if p.is_file()):
            info = zipfile.ZipInfo(path.relative_to(TOOL).as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            zf.writestr(info, path.read_bytes())


def profile_values(name, resolved, format_tag):
    sample = load_data("sample_config_" + name + ".json")
    overrides = load_data("env_overrides.json")[name]
    return {
        "profile": format_tag + "-" + name,
        "mode": overrides["mode"],
        "max_records": int(resolved["max_records"]) + int(sample["max_records_delta"]),
        "retry_limit": int(resolved["retry_limit"]) + int(overrides["retry_limit_delta"]),
        "timeout_ms": int(resolved["timeout_ms"]) + int(overrides["timeout_ms_delta"]),
        "trailer": resolved["trailer"] + ":" + name,
    }


def scalar_flat(data):
    return all(not isinstance(value, (dict, list)) for value in data.values())


def main() -> None:
    extract()
    inspect_shipped_tool()
    repair_cli()
    self_check_ledger()
    OUT.mkdir(parents=True, exist_ok=True)
    config = OUT / "config.json"
    schema = TOOL / "schema.json"
    format_tag = load_data("config_schema.json")["profile"]
    rules = load_data("validation_rules.json")
    profiles = rules["profiles"]
    artifacts = rules["required_artifacts"]

    commands = []
    resolve_cmd = run_cli("resolve", "--data-dir", str(DATA), "--out", str(RESOLVE_SCRATCH))
    commands.append(resolve_cmd)
    resolved = json.loads(resolve_cmd["stdout"])
    trace = json.loads((RESOLVE_SCRATCH / "dependency_trace.json").read_text(encoding="utf-8"))
    curve = json.loads((RESOLVE_SCRATCH / "threshold_curve.json").read_text(encoding="utf-8"))

    commands.append(run_cli("init", "--schema", str(schema), "--out", str(config)))
    for key in POLICY_KEYS:
        commands.append(run_cli("set", "--config", str(config), "--key", key, "--value", str(resolved[key])))
    commands.append(run_cli("validate", "--schema", str(schema), "--config", str(config)))

    profile_paths = {name: OUT / ("profile_" + name + ".json") for name in profiles}
    for name, path in profile_paths.items():
        values = profile_values(name, resolved, format_tag)
        commands.append(run_cli("init", "--schema", str(schema), "--out", str(path)))
        for key in PROFILE_KEYS:
            commands.append(run_cli("set", "--config", str(path), "--key", key, "--value", str(values[key])))
        commands.append(run_cli("validate", "--schema", str(schema), "--config", str(path)))
    if any(item["returncode"] != 0 for item in commands):
        raise SystemExit(commands)

    digest = hashlib.sha256(config.read_bytes()).hexdigest()
    report_cmd = run_cli("export-report", "--config", str(config), "--out", str(OUT / "report.json"),
                         "--digest", digest, "--commands", json.dumps(commands, sort_keys=True))
    if report_cmd["returncode"] != 0:
        raise SystemExit(report_cmd)

    package_tool()

    inputs = sorted(path.name for path in DATA.iterdir() if path.is_file())
    dump_json(OUT / "summary.json", {
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
        "format_tag": format_tag,
        "input_count": len(inputs),
        "inputs": inputs,
        "profiles": profiles,
        "trailer": resolved["trailer"],
    })

    profile_docs = {name: json.loads(path.read_text(encoding="utf-8")) for name, path in profile_paths.items()}
    main_config = json.loads(config.read_text(encoding="utf-8"))
    checks = {
        # validation_report.json is the file being written, so it is the one artifact counted before it exists
        "all_artifacts_present": all((OUT / name).exists() or name == "validation_report.json" for name in artifacts),
        "command_failures": [item for item in commands if item.get("returncode") != 0],
        "config_matches_policy": all(main_config[key] == resolved[key] for key in main_config),
        "config_scalar_flat": scalar_flat(main_config),
        "profiles": {name: {"trailer": doc["trailer"]} for name, doc in profile_docs.items()},
        "required_artifacts": artifacts,
    }
    dump_json(OUT / "validation_report.json", {
        "ok": all([checks["all_artifacts_present"], checks["config_matches_policy"], checks["config_scalar_flat"], checks["command_failures"] == []]),
        "checks": checks,
        "policy_resolved": resolved,
        "threshold_curve": curve,
        "dependency_trace": trace,
    })
    for name in artifacts:
        print("wrote " + str(OUT / name))


if __name__ == "__main__":
    main()
