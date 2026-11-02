from __future__ import annotations

import argparse
import configparser
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

# sentinel-ctl: policy bundle compiler.
# NOTE: reported that compiled policy numbers drift from the authoritative model.


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data), encoding="utf-8")


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
    parser = configparser.SafeConfigParser()
    parser.read(path, encoding="utf-8")
    flat = {}
    for section in parser.sections():
        for key, value in parser.items(section):
            flat[key] = value
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


def resolve_policy(data_dir):
    data = Path(data_dir)
    manifest = read_toml(data / "boot_manifest.toml")["manifest"]
    instant = int(manifest["effective_instant"])

    ledger = read_jsonc(data / "bundle_ledger.jsonc")
    active_bundle = str(manifest["latest_bundle_id"])
    role_key = ledger[active_bundle]["role_key"]

    index = read_yaml_flat(data / "principal_role_index.yaml")
    param_key = index[role_key + ".param_key"]
    tenant = index[role_key + ".tenant"]
    role_level = int(index[role_key + ".role_level"])

    base_rows = {row["param_key"]: row for row in read_parquet_rows(data / "base_parameters.parquet")}
    base = base_rows[param_key]

    corpus = load_json(data / "request_corpus.json")
    version = corpus["entries"][0]["claimed_version"]

    windows = {w["id"]: w for w in read_xml_records(data / "effective_windows.xml", "window")}
    ledger_doc = load_json(data / "override_deltas.json")
    overrides = ledger_doc["overrides"]
    sums = {}
    for ov in overrides:
        entry = sums.setdefault(ov["tenant"], {"max_records_delta_sum": 0, "rows": 0, "timeout_ms_delta_sum_ms": 0})
        entry["rows"] += 1
        entry["max_records_delta_sum"] += int(ov["max_records_delta"])
        entry["timeout_ms_delta_sum_ms"] += int(ov["timeout_ms_delta"])
    ledger_controls = {}
    for name, control in ledger_doc["controls"].items():
        ledger_controls[name] = "ok" if sums.get(name) == control else "mismatch"
    selected = None
    for ov in overrides:
        if ov["param_key"] != param_key or ov["status"] != "active":
            continue
        window = windows.get(ov["window_id"])
        if window is None:
            continue
        start = int(window["start"])
        end = int(window["end"])
        if start <= instant <= end:
            selected = ov
            break

    multipliers = {row["tenant"]: row for row in read_xlsx_rows(data / "tenant_multiplier_table.xlsx")}
    mult = multipliers[tenant]
    mult_bps = int(mult["mult_bps"])
    cap = int(mult["max_records_cap"])

    tiers = {int(row["tier"]): row for row in read_parquet_rows(data / "threshold_tier_curve.parquet")}
    base_threshold = int(tiers[role_level - 1]["base_threshold"])

    rules = read_conf(data / "reconciliation_rules.conf")
    divisor = int(rules["iteration_divisor"])

    after_delta_mr = int(base["max_records_base"]) + int(selected["max_records_delta"])
    max_records = (min(cap, after_delta_mr) * mult_bps) // 1000
    retry_limit = int(base["retry_limit_base"]) + int(selected["retry_limit_delta"])
    timeout_ms = int(base["timeout_seconds_base"]) + int(selected["timeout_ms_delta"])

    risk_weight_eff = int(base["risk_weight_base"]) + int(selected["risk_delta"])
    contribution = (risk_weight_eff * mult_bps) // 1000
    risk_threshold = base_threshold + (contribution + base_threshold) // divisor

    defaults = load_json(data / "defaults.json")
    schema = load_json(data / "config_schema.json")
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
        "trailer": str(defaults["base_config"]["trailer"]),
        "param_key": param_key,
        "tenant": tenant,
        "effective_version": version,
    }
    trace = {
        "active_bundle": active_bundle,
        "applied_overrides": [selected["override_id"]],
        "ledger_controls": ledger_controls,
        "resolution_order": [],
        "rejected_branches": [],
    }
    curve = {"tier": role_level, "converged": risk_threshold, "iterations": [base_threshold, risk_threshold]}
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
    print(json.dumps(resolved))


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
    missing = [key for key in required if key not in data]
    if missing:
        raise SystemExit("missing: " + ",".join(missing))
    print("ok")


def cmd_report(args):
    data = load_json(args.config)
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

    p = sub.add_parser("export-report")
    p.add_argument("--config", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--digest", required=True)
    p.add_argument("--commands", required=True)
    p.set_defaults(func=cmd_report)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
