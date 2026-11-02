from __future__ import annotations

import argparse
import configparser
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

# sentinel-ctl: policy bundle compiler.


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, sort_keys=True, indent=2) + "\n"
    Path(path).write_text(text, encoding="utf-8")


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


def read_ini(path):
    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")
    return {section: dict(parser.items(section)) for section in parser.sections()}


def read_conf(path):
    flat = {}
    for values in read_ini(path).values():
        flat.update(values)
    return flat


def read_settings(path):
    settings = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = re.match(r"([A-Za-z0-9_. ]+?)\s*[:=]\s*(.+)$", stripped)
        if match:
            settings[match.group(1).strip()] = match.group(2).strip()
    return settings


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
            sst = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            shared = ["".join(t.text or "" for t in si.iter(ns + "t")) for si in sst.iter(ns + "si")]
        sroot = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))
        rows = []
        for row in sroot.iter(ns + "row"):
            cells = {}
            for cell in row.iter(ns + "c"):
                col = _col_to_idx(cell.get("r", "A1"))
                vnode = cell.find(ns + "v")
                if cell.get("t") == "inlineStr":
                    tnode = cell.find(ns + "is/" + ns + "t")
                    cells[col] = tnode.text if tnode is not None else ""
                elif cell.get("t") == "s" and vnode is not None:
                    cells[col] = shared[int(vnode.text)]
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


def round_half_up(numerator, denominator):
    return (2 * numerator + denominator) // (2 * denominator)


class Corpus:
    """Reads reference files, recording the order in which they are consumed."""

    def __init__(self, data_dir):
        self.data = Path(data_dir)
        self.order = []

    def _mark(self, name):
        if name not in self.order:
            self.order.append(name)
        return self.data / name

    def json(self, name):
        return load_json(self._mark(name))

    def jsonc(self, name):
        return read_jsonc(self._mark(name))

    def toml(self, name):
        return read_toml(self._mark(name))

    def yaml_flat(self, name):
        return read_yaml_flat(self._mark(name))

    def ini(self, name):
        return read_ini(self._mark(name))

    def settings(self, name):
        return read_settings(self._mark(name))

    def xml(self, name, tag):
        return read_xml_records(self._mark(name), tag)

    def xlsx(self, name):
        return read_xlsx_rows(self._mark(name))

    def parquet(self, name):
        return read_parquet_rows(self._mark(name))

    def exists(self, name):
        return (self.data / name).exists()


REJECTED_FILES = (
    ("legacy_override_table.ini", "legacy override table of the superseded bundle"),
    ("superseded_windows.xml", "superseded effective-time windows"),
    ("principal_alias_table.jsonc", "retired-bundle aliases must not rename the resolved principal or tenant"),
    ("tenant_region_multipliers.xlsx", "superseded tenant multiplier table"),
    ("legacy_policy_memo.pdf", "retired bundle numbers retained for audit only"),
)


def resolve_policy(data_dir):
    corpus = Corpus(data_dir)
    rejected = []

    manifest = corpus.toml("boot_manifest.toml")["manifest"]
    instant = int(manifest["effective_instant"])
    active_bundle = str(manifest["active_bundle_id"])
    latest_bundle = str(manifest["latest_bundle_id"])
    if latest_bundle != active_bundle:
        rejected.append({
            "id": "latest_bundle_id=" + latest_bundle,
            "reason": "boot manifest latest_bundle_id ignored; active_bundle_id " + active_bundle + " binds",
        })

    ledger = corpus.jsonc("bundle_ledger.jsonc")
    for bundle_id in sorted(ledger):
        if bundle_id != active_bundle:
            rejected.append({
                "id": bundle_id,
                "reason": "bundle not selected (status " + str(ledger[bundle_id]["status"]) + "); active_bundle_id is " + active_bundle,
            })
    bundle = ledger[active_bundle]
    if bundle["status"] != "active":
        raise SystemExit("active bundle is not active: " + active_bundle)
    role_key = bundle["role_key"]

    index = corpus.yaml_flat(bundle["index_file"])
    param_key = index[role_key + ".param_key"]
    tenant = index[role_key + ".tenant"]
    role_level = int(index[role_key + ".role_level"])

    base_rows = {row["param_key"]: row for row in corpus.parquet("base_parameters.parquet")}
    base = base_rows[param_key]

    version_rows = corpus.json("policy_version_map.json")["versions"]
    effective_from = {row["version"]: int(row["effective_from"]) for row in version_rows}
    effective_version = max(
        (row for row in version_rows if int(row["effective_from"]) <= instant),
        key=lambda row: int(row["effective_from"]),
    )["version"]

    claimed = corpus.json("request_corpus.json")["entries"][0]["claimed_version"]
    client_version_ignored = claimed != effective_version
    if client_version_ignored:
        rejected.append({
            "id": "claimed_version=" + str(claimed),
            "reason": "client-claimed version ignored; policy_version_map.json binds " + effective_version,
        })

    windows = {row["id"]: row for row in corpus.xml("effective_windows.xml", "window")}
    ledger_doc = corpus.json("override_deltas.json")
    overrides = sorted(ledger_doc["overrides"], key=lambda row: int(row["seq"]))

    reconcile = corpus.ini("reconciliation_rules.conf")["reconcile"]
    unit_factor = int(reconcile["timeout_unit_factor"])
    divisor = int(reconcile["iteration_divisor"])
    cutover = int(corpus.settings("units_reference.txt")["timeout_ms_delta cutover"])

    def delta_ms(row):
        stored = int(row["timeout_ms_delta"])
        if effective_from[row["version"]] < cutover:
            return stored * unit_factor
        return stored

    sums = {}
    for row in overrides:
        entry = sums.setdefault(row["tenant"], {"max_records_delta_sum": 0, "rows": 0, "timeout_ms_delta_sum_ms": 0})
        entry["rows"] += 1
        entry["max_records_delta_sum"] += int(row["max_records_delta"])
        entry["timeout_ms_delta_sum_ms"] += delta_ms(row)
    ledger_controls = {}
    for name, control in ledger_doc["controls"].items():
        stored = {key: int(value) for key, value in control.items()}
        ledger_controls[name] = "ok" if sums.get(name) == stored else "mismatch"

    tenants = {row["id"]: row for row in corpus.xml("tenant_catalog.xml", "tenant")}
    allowance = {key: int(value) for key, value in corpus.ini("quota_limits.cfg")["override_allowance"].items()}

    def note(row, reason):
        if row["param_key"] == param_key:
            rejected.append({"id": row["override_id"], "reason": reason})

    passed = []
    for row in overrides:
        if row["status"] != "active":
            note(row, "override status " + str(row["status"]))
            continue
        window = windows.get(row["window_id"])
        if window is None:
            note(row, "window " + row["window_id"] + " absent from effective_windows.xml")
            continue
        if not int(window["start"]) <= instant < int(window["end"]):
            note(row, "window " + row["window_id"] + " does not contain effective_instant in [start, end)")
            continue
        if row["version"] != effective_version or window["version"] != effective_version:
            note(row, "row version " + row["version"] + " / window version " + window["version"] + " is not the effective version " + effective_version)
            continue
        passed.append(row)

    region_used = {}
    window_used = {}
    applied = []
    for row in passed:
        region = tenants[row["tenant"]]["region"]
        window = windows[row["window_id"]]
        region_left = region_used.get(region, 0) < allowance[region]
        window_left = window_used.get(row["window_id"], 0) < int(window["admit"])
        if region_left and window_left:
            region_used[region] = region_used.get(region, 0) + 1
            window_used[row["window_id"]] = window_used.get(row["window_id"], 0) + 1
            applied.append(row)
        elif region_left:
            note(row, "admit count of window " + row["window_id"] + " exhausted at this seq")
        else:
            note(row, "override_allowance of region " + region + " exhausted at this seq")
    mine = [row for row in applied if row["param_key"] == param_key]

    multipliers = {row["tenant"]: row for row in corpus.xlsx("tenant_multiplier_table.xlsx")}
    mult = multipliers[tenant]
    mult_bps = int(mult["mult_bps"])
    cap = int(mult["max_records_cap"])

    tiers = {int(row["tier"]): int(row["base_threshold"]) for row in corpus.parquet("threshold_tier_curve.parquet")}
    base_threshold = tiers[role_level]

    convergence = corpus.settings("convergence_spec.txt")
    epsilon = int(convergence["convergence_epsilon"])
    max_iterations = int(convergence["max_iterations"])

    after_delta = int(base["max_records_base"]) + sum(int(row["max_records_delta"]) for row in mine)
    max_records = min(cap, round_half_up(after_delta * mult_bps, 1000))
    retry_limit = int(base["retry_limit_base"]) + sum(int(row["retry_limit_delta"]) for row in mine)
    timeout_ms = int(base["timeout_seconds_base"]) * unit_factor + sum(delta_ms(row) for row in mine)

    terms = [int(base["risk_weight_base"])] + [int(row["risk_delta"]) for row in mine]
    contribution = sum(round_half_up(term * mult_bps, 1000) for term in terms)

    iterations = [base_threshold]
    current = base_threshold
    for _ in range(max_iterations):
        nxt = base_threshold + (contribution + current) // divisor
        iterations.append(nxt)
        step = abs(nxt - current)
        current = nxt
        if step <= epsilon:
            break
    risk_threshold = current

    defaults = corpus.json(manifest["trailer_ref"])
    schema = corpus.json(manifest["schema_ref"])
    for key in sorted(defaults["base_config"]):
        if key.startswith("legacy_"):
            rejected.append({
                "id": manifest["trailer_ref"] + ":base_config." + key,
                "reason": "legacy default superseded by the resolved policy value",
            })
    for name, reason in REJECTED_FILES:
        if corpus.exists(name):
            rejected.append({"id": name, "reason": reason})

    resolved = {
        "profile": schema["profile"],
        "producer": schema["producer"],
        "container": schema["container"],
        "checksum": defaults["checksum"],
        "mode": defaults["mode"],
        "max_records": max_records,
        "retry_limit": retry_limit,
        "timeout_ms": timeout_ms,
        "trailer": str(defaults["base_config"]["trailer"]),
        "param_key": param_key,
        "tenant": tenant,
        "effective_version": effective_version,
        "risk_threshold": risk_threshold,
    }
    trace = {
        "active_bundle": active_bundle,
        "effective_version": effective_version,
        "param_key": param_key,
        "tenant": tenant,
        "client_version_ignored": client_version_ignored,
        "applied_overrides": [row["override_id"] for row in mine],
        "ledger_controls": ledger_controls,
        "resolution_order": list(corpus.order),
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


def config_keys(schema):
    required = schema["required_keys"]
    if isinstance(required, str):
        required = [key.strip() for key in required.split(",") if key.strip()]
    return list(required)


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


def cmd_profile(args):
    resolved, _, _ = resolve_policy(args.data_dir)
    data = Path(args.data_dir)
    schema = load_json(data / "config_schema.json")
    env = load_json(data / "env_overrides.json")[args.env]
    sidecar = load_json(data / ("sample_config_" + args.env + ".json"))
    profile = {
        "checksum": resolved["checksum"],
        "container": resolved["container"],
        "producer": resolved["producer"],
        "mode": env["mode"],
        "profile": schema["profile"] + "-" + args.env,
        "max_records": resolved["max_records"] + int(sidecar["max_records_delta"]),
        "retry_limit": resolved["retry_limit"] + int(env["retry_limit_delta"]),
        "timeout_ms": resolved["timeout_ms"] + int(env["timeout_ms_delta"]),
        "trailer": resolved["trailer"] + ":" + args.env,
    }
    assert_flat(profile)
    write_json(args.out, profile)
    print(json.dumps(profile, sort_keys=True))


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
    missing = [key for key in config_keys(schema) if key not in data]
    if missing:
        raise SystemExit("missing: " + ",".join(missing))
    print("ok")


def cmd_report(args):
    data = load_json(args.config)
    commands = json.loads(args.commands)
    report = {
        "ok": True,
        "tool": "sentinel-ctl",
        "commands": commands,
        "config_sha256": args.digest,
        "trailer": data.get("trailer"),
    }
    write_json(args.out, report)
    print("reported")


def main():
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

    p = sub.add_parser("profile")
    p.add_argument("--data-dir", required=True)
    p.add_argument("--env", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_profile)

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
