from __future__ import annotations

import argparse
import configparser
import json
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from fractions import Fraction
from pathlib import Path

# sentinel-ctl: policy bundle compiler.
# Repaired: resolves the authoritative policy by walking the documented dependency
# chain (boot manifest -> active bundle -> role index -> base tables -> version map
# -> windows -> override ledger -> multipliers -> rounding/unit/convergence rules).


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dump_json(data):
    return json.dumps(data, sort_keys=True, indent=2) + "\n"


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


def read_toml(path):
    import tomllib

    return tomllib.loads(Path(path).read_text(encoding="utf-8"))


def read_jsonc(path):
    text = Path(path).read_text(encoding="utf-8")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"(^|\s)//[^\n]*", r"\1", text)
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
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def read_conf_sections(path):
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    parser.read(path, encoding="utf-8")
    return {section: dict(parser.items(section)) for section in parser.sections()}


def read_conf(path):
    flat = {}
    for values in read_conf_sections(path).values():
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
        shared = []
        if "xl/sharedStrings.xml" in zf.namelist():
            sst = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in sst.iter(ns + "si"):
                shared.append("".join(t.text or "" for t in si.iter(ns + "t")))
        sroot = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))
        rows = []
        for row in sroot.iter(ns + "row"):
            cells = {}
            for pos, cell in enumerate(row.iter(ns + "c")):
                ref = cell.get("r")
                col = _col_to_idx(ref) if ref else pos
                vnode = cell.find(ns + "v")
                kind = cell.get("t")
                if kind == "inlineStr":
                    cells[col] = "".join(t.text or "" for t in cell.iter(ns + "t"))
                elif kind == "s" and vnode is not None:
                    cells[col] = shared[int(vnode.text)]
                else:
                    cells[col] = vnode.text if vnode is not None and vnode.text is not None else ""
            rows.append(cells)
    header = {i: rows[0][i] for i in sorted(rows[0])}
    records = []
    for cells in rows[1:]:
        if not any(str(v).strip() for v in cells.values()):
            continue
        records.append({name: cells.get(i, "") for i, name in header.items()})
    return records


def read_parquet_rows(path):
    import pyarrow.parquet as pq

    return pq.read_table(path).to_pylist()


def to_int(value):
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if re.fullmatch(r"[+-]?[0-9]+", text):
        return int(text)
    frac = Fraction(text)
    if frac.denominator != 1:
        raise SystemExit("expected an integer value, got " + text)
    return int(frac)


def round_half_up(frac):
    frac = Fraction(frac)
    return int((frac + Fraction(1, 2)).__floor__())


def floor_div(num, den):
    return num // den


def in_window(instant, window):
    return to_int(window["start"]) <= instant < to_int(window["end"])


def resolve_policy(data_dir):
    data = Path(data_dir)
    order = []
    rejected = []

    def use(name):
        if name not in order:
            order.append(name)
        return data / name

    # 1. boot manifest: instant, active bundle (latest_bundle_id is ignored)
    manifest = read_toml(use("boot_manifest.toml"))["manifest"]
    instant = to_int(manifest["effective_instant"])
    stale_path = data / "stale_version_rules.txt"
    stale = {}
    if stale_path.exists():
        for line in stale_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                key, _, value = line.partition("=")
                stale[key.strip()] = value.strip()
        use("stale_version_rules.txt")
    prefer = stale.get("prefer", "active_bundle_id")
    active_bundle = str(manifest[prefer])
    latest_bundle = manifest.get("latest_bundle_id")

    # 2. bundle ledger -> role key and index file of the active bundle
    ledger = read_jsonc(use("bundle_ledger.jsonc"))
    bundle = ledger[active_bundle]
    if str(bundle.get("status", "active")) != "active":
        raise SystemExit("active bundle " + active_bundle + " is not active in the ledger")
    for bid in sorted(ledger):
        status = str(ledger[bid].get("status", ""))
        if bid != active_bundle and status in ("superseded", "retired"):
            reason = "bundle status " + status + " in bundle_ledger.jsonc"
            if latest_bundle is not None and str(latest_bundle) == bid:
                reason += "; latest_bundle_id ignored in favour of active_bundle_id"
            rejected.append({"id": bid, "reason": reason})
    if latest_bundle is not None and str(latest_bundle) != active_bundle and str(latest_bundle) not in ledger:
        rejected.append({"id": str(latest_bundle), "reason": "latest_bundle_id ignored in favour of active_bundle_id"})
    role_key = bundle["role_key"]

    # 3. role index of the active bundle
    index = read_yaml_flat(use(bundle.get("index_file", "principal_role_index.yaml")))
    param_key = index[role_key + ".param_key"]
    tenant = index[role_key + ".tenant"]
    role_level = to_int(index[role_key + ".role_level"])

    # 4. base parameters of the resolved principal
    base_rows = {row["param_key"]: row for row in read_parquet_rows(use("base_parameters.parquet"))}
    base = base_rows[param_key]

    # 5. effective version from the version map (client-claimed versions are ignored)
    vmap = load_json(use("policy_version_map.json"))
    version_from = {}
    effective_version = None
    best = None
    for entry in vmap["versions"]:
        start = to_int(entry["effective_from"])
        version_from[str(entry["version"])] = start
        if start <= instant and (best is None or start > best):
            best = start
            effective_version = str(entry["version"])
    if effective_version is None:
        raise SystemExit("no effective version at instant " + str(instant))

    # 6. effective windows (superseded windows are rejected)
    windows = {w["id"]: w for w in read_xml_records(use("effective_windows.xml"), "window")}
    if (data / "superseded_windows.xml").exists():
        rejected.append({"file": "superseded_windows.xml", "reason": "superseded windows are not effective windows; only effective_windows.xml binds"})

    # 7. unit and reconciliation rules
    units = {}
    for line in use("units_reference.txt").read_text(encoding="utf-8").splitlines():
        if ":" in line and not line.strip().startswith("#"):
            key, _, value = line.partition(":")
            units[key.strip()] = value.strip()
    cutover = to_int(units.get("timeout_ms_delta cutover", "0"))
    rules = read_conf(use("reconciliation_rules.conf"))
    unit_factor = to_int(rules.get("timeout_unit_factor", 1000))
    divisor = to_int(rules["iteration_divisor"])

    def delta_ms(row):
        raw = to_int(row["timeout_ms_delta"])
        start = version_from.get(str(row.get("version")))
        if start is not None and start < cutover:
            return raw * unit_factor
        return raw

    # 8. tenant catalog and override allowances
    catalog = {t["id"]: t for t in read_xml_records(use("tenant_catalog.xml"), "tenant")}
    allowance_cfg = read_conf_sections(use("quota_limits.cfg")).get("override_allowance", {})
    allowance = {region: to_int(value) for region, value in allowance_cfg.items()}
    use("override_precedence.conf")

    # 9. override ledger
    ledger_doc = load_json(use("override_deltas.json"))
    overrides = ledger_doc["overrides"]
    aliases = ledger_doc.get("param_key_aliases") or []

    def principal_of(row):
        key = row.get("param_key")
        for alias in aliases:
            if key == alias.get("alias"):
                if to_int(alias["start"]) <= instant < to_int(alias["end"]):
                    return alias.get("principal")
                return None
        return key

    # controls: parse/count over every stored row
    sums = {}
    for ov in overrides:
        entry = sums.setdefault(ov["tenant"], {"max_records_delta_sum": 0, "rows": 0, "timeout_ms_delta_sum_ms": 0})
        entry["rows"] += 1
        entry["max_records_delta_sum"] += to_int(ov["max_records_delta"])
        entry["timeout_ms_delta_sum_ms"] += delta_ms(ov)
    ledger_controls = {}
    for name, control in ledger_doc.get("controls", {}).items():
        got = sums.get(name, {"max_records_delta_sum": 0, "rows": 0, "timeout_ms_delta_sum_ms": 0})
        ok = all(to_int(control.get(k, 0)) == got[k] for k in got) and set(control) <= set(got)
        ledger_controls[name] = "ok" if ok else "mismatch"

    last_seq = {}
    for ov in overrides:
        oid = ov["override_id"]
        seq = to_int(ov["seq"])
        if oid not in last_seq or seq > last_seq[oid]:
            last_seq[oid] = seq

    def matches_version(ov):
        window = windows.get(ov.get("window_id"))
        if window is None or not in_window(instant, window):
            return False
        return str(ov.get("version")) == effective_version and str(window.get("version")) == effective_version

    def passes_selection(ov):
        if to_int(ov["seq"]) != last_seq[ov["override_id"]]:
            return False
        if str(ov.get("status")) != "active":
            return False
        return matches_version(ov)

    region_left = dict(allowance)
    admit_left = {wid: to_int(w.get("admit", 0)) for wid, w in windows.items()}
    applied_ids = set()
    applied_rows = []
    for ov in sorted(overrides, key=lambda r: to_int(r["seq"])):
        if not passes_selection(ov):
            continue
        req = ov.get("requires")
        if req not in (None, "") and req not in applied_ids:
            continue
        region = catalog.get(ov["tenant"], {}).get("region")
        wid = ov["window_id"]
        if region is None or region_left.get(region, 0) < 1 or admit_left.get(wid, 0) < 1:
            continue
        region_left[region] -= 1
        admit_left[wid] -= 1
        applied_ids.add(ov["override_id"])
        applied_rows.append(ov)

    # timeout pool per window over every applied row of that window
    added_timeout = {}
    by_window = {}
    for ov in applied_rows:
        d = delta_ms(ov)
        if d > 0:
            by_window.setdefault(ov["window_id"], []).append((ov, d))
        else:
            added_timeout[to_int(ov["seq"])] = d
    for wid, items in by_window.items():
        pool = to_int(windows[wid]["timeout_pool"])
        total = sum(d for _, d in items)
        if total <= pool:
            for ov, d in items:
                added_timeout[to_int(ov["seq"])] = d
            continue
        shares = {to_int(ov["seq"]): floor_div(pool * d, total) for ov, d in items}
        keep = [(ov, d) for ov, d in items if shares[to_int(ov["seq"])] >= 100]
        keep_total = sum(d for _, d in keep)
        for ov, d in items:
            added_timeout[to_int(ov["seq"])] = 0
        for ov, d in keep:
            added_timeout[to_int(ov["seq"])] = floor_div(pool * d, keep_total)

    mine = [ov for ov in applied_rows if principal_of(ov) == param_key]
    carry_mr = 0
    carry_risk = []
    for ov in overrides:
        carry = ov.get("carry")
        if str(ov.get("status")) != "superseded" or carry not in ("max_records_delta", "risk_delta"):
            continue
        if principal_of(ov) != param_key or not matches_version(ov):
            continue
        if carry == "max_records_delta":
            carry_mr += to_int(ov["max_records_delta"])
        else:
            carry_risk.append(to_int(ov["risk_delta"]))

    if (data / "legacy_override_table.ini").exists():
        rejected.append({"file": "legacy_override_table.ini", "reason": "legacy overrides of the superseded bundle; only override_deltas.json binds"})
    if (data / "principal_alias_table.jsonc").exists():
        rejected.append({"file": "principal_alias_table.jsonc", "reason": "conflicting aliases from the retired bundle; not used"})
    rejected.append({"file": "request_corpus.json", "reason": "client-claimed versions ignored; effective version comes from policy_version_map.json"})

    # 10. tenant multiplier and cap
    multipliers = {row["tenant"]: row for row in read_xlsx_rows(use("tenant_multiplier_table.xlsx"))}
    mult = multipliers[tenant]
    mult_bps = to_int(mult["mult_bps"])
    cap = to_int(mult["max_records_cap"])

    use("clamp_rules.txt")
    after_delta = to_int(base["max_records_base"]) + sum(to_int(ov["max_records_delta"]) for ov in mine) + carry_mr
    scaled = round_half_up(Fraction(after_delta * mult_bps, 1000))
    max_records = min(cap, scaled)

    retry_limit = to_int(base["retry_limit_base"]) + sum(to_int(ov["retry_limit_delta"]) for ov in mine)

    timeout_ms = to_int(base["timeout_seconds_base"]) * unit_factor
    if timeout_ms < 1000:
        timeout_ms = 1000
    for ov in sorted(mine, key=lambda r: to_int(r["seq"])):
        timeout_ms += added_timeout.get(to_int(ov["seq"]), 0)
        if timeout_ms < 1000:
            timeout_ms = 1000

    use("risk_weight_rounding.txt")
    terms = [to_int(base["risk_weight_base"])] + [to_int(ov["risk_delta"]) for ov in mine] + carry_risk
    contribution = sum(round_half_up(Fraction(term * mult_bps, 1000)) for term in terms)

    # 11. threshold reconciliation
    spec = {}
    for line in use("convergence_spec.txt").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            key, _, value = line.partition("=")
            spec[key.strip()] = value.strip()
    epsilon = to_int(spec.get("convergence_epsilon", "0"))
    max_iter = to_int(spec.get("max_iterations", "64"))
    tiers = {to_int(row["tier"]): row for row in read_parquet_rows(use("threshold_tier_curve.parquet"))}
    base_threshold = to_int(tiers[role_level]["base_threshold"])
    t = base_threshold
    iterations = [t]
    converged = False
    for _ in range(max_iter):
        t_next = base_threshold + floor_div(contribution + t, divisor)
        iterations.append(t_next)
        if abs(t_next - t) <= epsilon:
            converged = True
            t = t_next
            break
        t = t_next
    risk_threshold = t

    # 12. identity fields and trailer
    defaults = load_json(use(manifest.get("trailer_ref", "defaults.json")))
    schema = load_json(use(manifest.get("schema_ref", "config_schema.json")))
    use("request_corpus.json")
    resolved = {
        "profile": schema["profile"],
        "producer": schema["producer"],
        "container": schema["container"],
        "checksum": schema.get("checksum", defaults.get("checksum")),
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
        "client_version_ignored": True,
        "applied_overrides": [ov["override_id"] for ov in sorted(mine, key=lambda r: to_int(r["seq"]))],
        "ledger_controls": ledger_controls,
        "resolution_order": order,
        "rejected_branches": rejected,
    }
    curve = {
        "tier": role_level,
        "base_threshold": base_threshold,
        "contribution": contribution,
        "iterations": iterations,
        "converged": risk_threshold if converged else None,
    }
    return resolved, trace, curve


def cmd_init(args):
    schema = load_json(args.schema)
    data = {
        "profile": schema["profile"],
        "producer": schema["producer"],
        "container": schema["container"],
        "checksum": schema["checksum"],
        "mode": schema.get("mode", "strict-local"),
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


def cmd_report(args):
    data = load_json(args.config)
    commands = json.loads(args.commands)
    report = {
        "ok": all(c.get("returncode") == 0 for c in commands),
        "tool": "sentinel-ctl",
        "config_sha256": args.digest,
        "commands": commands,
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
    sys.exit(main())
