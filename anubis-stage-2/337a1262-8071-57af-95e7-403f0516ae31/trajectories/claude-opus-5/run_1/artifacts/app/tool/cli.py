from __future__ import annotations

import argparse
import configparser
import itertools
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

# sentinel-ctl: policy bundle compiler.

JSON_INDENT = 2
MS_PER_SECOND = 1000
BPS_UNIT = 1000
TIMEOUT_FLOOR_MS = 1000
MIN_POOL_SHARE_MS = 100
DIVISOR_RANGE = range(6, 15)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, sort_keys=True, indent=JSON_INDENT) + "\n"
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


def _ini_parser(path):
    parser = configparser.RawConfigParser()
    parser.optionxform = str
    parser.read(path, encoding="utf-8")
    return parser


def read_conf(path):
    flat = {}
    parser = _ini_parser(path)
    for section in parser.sections():
        for key, value in parser.items(section):
            flat[key] = value
    return flat


def read_conf_sections(path):
    parser = _ini_parser(path)
    return {section: dict(parser.items(section)) for section in parser.sections()}


def read_kv_text(path):
    """Read a rules text file as key/value pairs split on the first '=' or ':'."""
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        hits = [stripped.find(sep) for sep in ("=", ":") if sep in stripped]
        if not hits:
            continue
        cut = min(hits)
        out[stripped[:cut].strip()] = stripped[cut + 1 :].strip()
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


def scale_half_up(value, mult_bps):
    """round_half_up(value * mult_bps / BPS_UNIT); ties round upward."""
    return (value * mult_bps * 2 + BPS_UNIT) // (2 * BPS_UNIT)


class Corpus:
    """Reference corpus reader that records the order in which files are consumed."""

    def __init__(self, data_dir):
        self.dir = Path(data_dir)
        self.order = []

    def _touch(self, name):
        if name not in self.order:
            self.order.append(name)
        return self.dir / name

    def note(self, name):
        self._touch(name)

    def toml(self, name):
        return read_toml(self._touch(name))

    def jsonc(self, name):
        return read_jsonc(self._touch(name))

    def json(self, name):
        return load_json(self._touch(name))

    def yaml_flat(self, name):
        return read_yaml_flat(self._touch(name))

    def conf_sections(self, name):
        return read_conf_sections(self._touch(name))

    def kv_text(self, name):
        return read_kv_text(self._touch(name))

    def xml(self, name, tag):
        return read_xml_records(self._touch(name), tag)

    def xlsx(self, name):
        return read_xlsx_rows(self._touch(name))

    def parquet(self, name):
        return read_parquet_rows(self._touch(name))


def effective_version(version_map, instant):
    best = None
    for entry in version_map["versions"]:
        if int(entry["effective_from"]) > instant:
            continue
        if best is None or int(entry["effective_from"]) > int(best["effective_from"]):
            best = entry
    return best["version"]


def _contains(window, instant):
    return int(window["start"]) <= instant < int(window["end"])


def _row_principal(row, aliases, instant):
    """The param_key a row overrides, or None when it overrides no principal."""
    alias = aliases.get(row["param_key"])
    if alias is None:
        return row["param_key"]
    if int(alias["start"]) <= instant < int(alias["end"]):
        return alias["principal"]
    return None


def _source_row(row, groups):
    """The row whose deltas apply: a reinstated row borrows the last active row's."""
    if row["status"] != "reinstated":
        return row
    earlier = [r for r in groups[row["override_id"]] if r["seq"] < row["seq"] and r["status"] == "active"]
    return earlier[-1] if earlier else None


def group_by_override_id(rows):
    groups = {}
    for row in rows:
        groups.setdefault(row["override_id"], []).append(row)
    for group in groups.values():
        group.sort(key=lambda r: r["seq"])
    return groups


def run_draw(rows, windows, instant, version, regions, allowances, aliases):
    """Selection plus the global ascending-seq draw against admit and allowance units."""
    groups = group_by_override_id(rows)

    selected = []
    for row in rows:
        if groups[row["override_id"]][-1]["seq"] != row["seq"]:
            continue
        if row["status"] not in ("active", "reinstated"):
            continue
        window = windows.get(row["window_id"])
        if window is None or not _contains(window, instant):
            continue
        if row.get("version") != version or window.get("version") != version:
            continue
        if _source_row(row, groups) is None:
            continue
        selected.append(row)

    admit_left = {wid: int(w["admit"]) for wid, w in windows.items()}
    region_left = dict(allowances)
    applied = []
    applied_ids = set()
    for row in sorted(selected, key=lambda r: r["seq"]):
        requires = row.get("requires")
        if requires is not None and requires not in applied_ids:
            continue
        region = regions.get(row["tenant"])
        if region_left.get(region, 0) < 1 or admit_left.get(row["window_id"], 0) < 1:
            continue
        region_left[region] -= 1
        admit_left[row["window_id"]] -= 1
        applied.append(row)
        applied_ids.add(row["override_id"])

    carried = []
    for row in rows:
        if row["status"] != "superseded" or "carry" not in row:
            continue
        window = windows.get(row["window_id"])
        if window is None or not _contains(window, instant):
            continue
        if row.get("version") != version or window.get("version") != version:
            continue
        carried.append(row)

    for row in applied + carried:
        row["_principal"] = _row_principal(row, aliases, instant)
    return applied, carried, groups


def pool_amounts(applied, windows):
    """The millisecond amount each applied row adds under the window timeout pools."""
    amounts = {row["seq"]: row["_ms"] for row in applied}
    by_window = {}
    for row in applied:
        if row["_ms"] > 0:
            by_window.setdefault(row["window_id"], []).append(row)
    for wid, group in by_window.items():
        pool = int(windows[wid]["timeout_pool"])
        total = sum(r["_ms"] for r in group)
        if total <= pool:
            continue
        first = {r["seq"]: (pool * r["_ms"]) // total for r in group}
        kept = [r for r in group if first[r["seq"]] >= MIN_POOL_SHARE_MS]
        for row in group:
            amounts[row["seq"]] = 0
        if not kept:
            continue
        total_kept = sum(r["_ms"] for r in kept)
        for row in kept:
            amounts[row["seq"]] = (pool * row["_ms"]) // total_kept
    return amounts


def reconcile(base_threshold, contribution, divisor, epsilon, max_iterations):
    iterations = [base_threshold]
    value = base_threshold
    for _ in range(max_iterations):
        nxt = base_threshold + (contribution + value) // divisor
        iterations.append(nxt)
        if abs(nxt - value) <= epsilon:
            return iterations, nxt
        value = nxt
    return iterations, None


def find_repair(rows, control, ms_of):
    """Smallest-timeout set of spare rows whose removal reconciles the stored control."""
    groups = group_by_override_id(rows)
    protected = set()
    for group in groups.values():
        if group[-1]["status"] == "reinstated":
            earlier = [r for r in group[:-1] if r["status"] == "active"]
            if earlier:
                protected.add(earlier[-1]["seq"])
    spare = []
    for row in rows:
        if row["seq"] in protected:
            continue
        if (
            row["status"] == "withdrawn"
            or (row["status"] == "superseded" and "carry" not in row)
            or groups[row["override_id"]][-1]["seq"] != row["seq"]
        ):
            spare.append(row)
    drop_rows = len(rows) - int(control["rows"])
    drop_mr = sum(int(r["max_records_delta"]) for r in rows) - int(control["max_records_delta_sum"])
    drop_ms = sum(ms_of(r) for r in rows) - int(control["timeout_ms_delta_sum_ms"])
    if drop_rows < 0 or drop_rows > len(spare):
        return None
    best = None
    for combo in itertools.combinations(sorted(spare, key=lambda r: r["seq"]), drop_rows):
        if sum(int(r["max_records_delta"]) for r in combo) != drop_mr:
            continue
        if sum(ms_of(r) for r in combo) != drop_ms:
            continue
        key = (sum(abs(ms_of(r)) for r in combo), [r["seq"] for r in combo])
        if best is None or key < best:
            best = key
    return best[1] if best is not None else None


def resolve_policy(data_dir):
    corpus = Corpus(data_dir)
    rejected = []

    manifest = corpus.toml("boot_manifest.toml")["manifest"]
    instant = int(manifest["effective_instant"])

    stale = corpus.kv_text("stale_version_rules.txt")
    prefer_field = stale["prefer"]
    ignore_field = stale["ignore"]
    active_bundle = str(manifest[prefer_field])
    ignored_bundle = str(manifest[ignore_field])

    ledger = corpus.jsonc(manifest["ledger_ref"])
    if ignored_bundle != active_bundle:
        rejected.append(
            {
                "id": ignored_bundle,
                "reason": "bundle {0} is the {1} and bundle_ledger.jsonc marks it {2};"
                " stale_version_rules.txt prefers {3} {4}".format(
                    ignored_bundle,
                    ignore_field,
                    ledger[ignored_bundle]["status"],
                    prefer_field,
                    active_bundle,
                ),
            }
        )
    for bundle_id in sorted(ledger):
        if bundle_id in (active_bundle, ignored_bundle):
            continue
        if ledger[bundle_id]["status"] != "active":
            rejected.append(
                {
                    "id": bundle_id,
                    "reason": "bundle_ledger.jsonc marks bundle {0} {1}".format(
                        bundle_id, ledger[bundle_id]["status"]
                    ),
                }
            )

    role_key = ledger[active_bundle]["role_key"]
    index = corpus.yaml_flat(ledger[active_bundle]["index_file"])
    param_key = index[role_key + ".param_key"]
    tenant = index[role_key + ".tenant"]
    role_level = int(index[role_key + ".role_level"])

    legacy_role = ledger[ignored_bundle]["role_key"]
    if legacy_role != role_key:
        rejected.append(
            {
                "id": legacy_role,
                "reason": "role key {0} ({1}/{2}) belongs to bundle {3}, not the active bundle {4}".format(
                    legacy_role,
                    index[legacy_role + ".param_key"],
                    index[legacy_role + ".tenant"],
                    ignored_bundle,
                    active_bundle,
                ),
            }
        )
    corpus.note("principal_alias_table.jsonc")
    rejected.append(
        {
            "id": "principal_alias_table.jsonc",
            "reason": "retired-bundle principal aliases conflict with the active bundle and are not applied",
        }
    )
    corpus.note("legacy_override_table.ini")
    rejected.append(
        {
            "id": "legacy_override_table.ini",
            "reason": "legacy override table of retired bundle {0}; overrides come from override_deltas.json".format(
                ignored_bundle
            ),
        }
    )

    base_rows = {row["param_key"]: row for row in corpus.parquet("base_parameters.parquet")}

    version_map = corpus.json("policy_version_map.json")
    version = effective_version(version_map, instant)
    version_from = {entry["version"]: int(entry["effective_from"]) for entry in version_map["versions"]}

    ledger_doc = corpus.json(index["overrides_ref"])
    rows = ledger_doc["overrides"]
    aliases = {a["alias"]: a for a in ledger_doc.get("param_key_aliases") or []}

    windows = {w["id"]: w for w in corpus.xml("effective_windows.xml", "window")}
    corpus.note("superseded_windows.xml")
    rejected.append(
        {
            "id": "superseded_windows.xml",
            "reason": "its windows carry status:superseded; effective windows come from effective_windows.xml",
        }
    )
    for wid in sorted(windows):
        if _contains(windows[wid], instant) and windows[wid].get("version") != version:
            rejected.append(
                {
                    "id": wid,
                    "reason": "window {0} contains the effective instant but carries version {1},"
                    " not the effective version {2}".format(wid, windows[wid].get("version"), version),
                }
            )

    units = corpus.kv_text("units_reference.txt")
    cutover = int(units["timeout_ms_delta cutover"])

    def ms_of(row):
        raw = int(row["timeout_ms_delta"])
        return raw * MS_PER_SECOND if version_from[row["version"]] < cutover else raw

    stored = {}
    for row in rows:
        stored.setdefault(row["tenant"], []).append(row)
    ledger_controls = {}
    for name, control in ledger_doc["controls"].items():
        owned = stored.get(name, [])
        recomputed = {
            "rows": len(owned),
            "max_records_delta_sum": sum(int(r["max_records_delta"]) for r in owned),
            "timeout_ms_delta_sum_ms": sum(ms_of(r) for r in owned),
        }
        expected = {key: int(value) for key, value in control.items()}
        ledger_controls[name] = "ok" if recomputed == expected else "mismatch"

    corpus.note("override_precedence.conf")
    regions = {t["id"]: t["region"] for t in corpus.xml("tenant_catalog.xml", "tenant")}
    allowances = {
        key: int(value) for key, value in corpus.conf_sections("quota_limits.cfg")["override_allowance"].items()
    }

    applied, carried, groups = run_draw(rows, windows, instant, version, regions, allowances, aliases)
    for row in applied:
        row["_ms"] = ms_of(_source_row(row, groups))
    amounts = pool_amounts(applied, windows)

    corpus.note("clamp_rules.txt")
    multipliers = {row["tenant"]: row for row in corpus.xlsx("tenant_multiplier_table.xlsx")}
    corpus.note("risk_weight_rounding.txt")
    tiers = {int(row["tier"]): int(row["base_threshold"]) for row in corpus.parquet("threshold_tier_curve.parquet")}

    def compute(principal, tenant_id, level):
        row_base = base_rows[principal]
        mult = multipliers[tenant_id]
        mult_bps = int(mult["mult_bps"])
        cap = int(mult["max_records_cap"])
        mine = sorted((r for r in applied if r["_principal"] == principal), key=lambda r: r["seq"])
        carry = sorted((r for r in carried if r["_principal"] == principal), key=lambda r: r["seq"])
        sources = [_source_row(row, groups) for row in mine]

        after_delta = int(row_base["max_records_base"])
        after_delta += sum(int(src["max_records_delta"]) for src in sources)
        after_delta += sum(int(r["max_records_delta"]) for r in carry if r["carry"] == "max_records_delta")
        max_records = min(cap, scale_half_up(after_delta, mult_bps))

        retry_limit = int(row_base["retry_limit_base"]) + sum(int(src["retry_limit_delta"]) for src in sources)

        timeout_ms = int(row_base["timeout_seconds_base"]) * MS_PER_SECOND
        for row in mine:
            timeout_ms += amounts[row["seq"]]
            timeout_ms = max(timeout_ms, TIMEOUT_FLOOR_MS)

        terms = [int(row_base["risk_weight_base"])]
        terms.extend(int(src["risk_delta"]) for src in sources)
        terms.extend(int(r["risk_delta"]) for r in carry if r["carry"] == "risk_delta")
        contribution = sum(scale_half_up(term, mult_bps) for term in terms)

        return {
            "max_records": max_records,
            "retry_limit": retry_limit,
            "timeout_ms": timeout_ms,
            "contribution": contribution,
            "base_threshold": tiers[level],
            "applied": [row["override_id"] for row in mine],
        }

    spec = corpus.kv_text("convergence_spec.txt")
    epsilon = int(spec["convergence_epsilon"])
    max_iterations = int(spec["max_iterations"])
    fallback = int(corpus.conf_sections("reconciliation_rules.conf")["reconcile"]["iteration_divisor"])

    reports = ledger_doc.get("reports") or []
    resets = [int(r["seq"]) for r in reports if r.get("kind") == "reset"]
    standing = [
        r for r in reports if r.get("kind") == "curve" and (not resets or int(r["seq"]) > max(resets))
    ]
    for report in reports:
        if report.get("kind") == "curve" and report not in standing:
            rejected.append(
                {
                    "id": "curve report seq {0}".format(report["seq"]),
                    "reason": "withdrawn by the reset at seq {0} in override_deltas.json".format(max(resets)),
                }
            )
    if standing:
        targets = []
        for report in standing:
            role = report["role"]
            numbers = compute(
                index[role + ".param_key"], index[role + ".tenant"], int(index[role + ".role_level"])
            )
            targets.append((numbers["base_threshold"], numbers["contribution"], int(report["converged"])))
        divisors = [
            candidate
            for candidate in DIVISOR_RANGE
            if all(
                reconcile(bt, contrib, candidate, epsilon, max_iterations)[1] == want
                for bt, contrib, want in targets
            )
        ]
        divisor = divisors[0] if len(divisors) == 1 else None
    else:
        divisor = fallback

    numbers = compute(param_key, tenant, role_level)
    if divisor is None:
        iterations = [numbers["base_threshold"]]
        converged = None
    else:
        iterations, converged = reconcile(
            numbers["base_threshold"], numbers["contribution"], divisor, epsilon, max_iterations
        )

    schema = corpus.json(manifest["schema_ref"])
    defaults = corpus.json(manifest["trailer_ref"])
    resolved = {
        "profile": schema["profile"],
        "producer": schema["producer"],
        "container": schema["container"],
        "checksum": defaults["checksum"],
        "mode": defaults["mode"],
        "max_records": numbers["max_records"],
        "retry_limit": numbers["retry_limit"],
        "timeout_ms": numbers["timeout_ms"],
        "trailer": str(defaults["base_config"]["trailer"]),
        "param_key": param_key,
        "tenant": tenant,
        "effective_version": version,
        "risk_threshold": converged,
    }

    claimed = corpus.json("request_corpus.json")["entries"][0]["claimed_version"]
    rejected.append(
        {
            "id": "claimed_version " + str(claimed),
            "reason": "client-claimed version in request_corpus.json is not authoritative;"
            " the effective version comes from policy_version_map.json",
        }
    )
    trace = {
        "active_bundle": active_bundle,
        "effective_version": version,
        "param_key": param_key,
        "tenant": tenant,
        "client_version_ignored": True,
        "applied_overrides": numbers["applied"],
        "ledger_controls": ledger_controls,
        "resolution_order": list(corpus.order),
        "rejected_branches": rejected,
    }
    curve = {
        "tier": role_level,
        "base_threshold": numbers["base_threshold"],
        "contribution": numbers["contribution"],
        "iterations": iterations,
        "converged": converged,
    }
    repair = {
        name: find_repair(stored.get(name, []), ledger_doc["controls"][name], ms_of)
        for name, status in ledger_controls.items()
        if status == "mismatch"
    }
    return resolved, trace, curve, repair


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
    resolved, trace, curve, repair = resolve_policy(args.data_dir)
    out = Path(args.out)
    write_json(out / "policy_resolved.json", resolved)
    write_json(out / "dependency_trace.json", trace)
    write_json(out / "threshold_curve.json", curve)
    write_json(out / "ledger_repair.json", repair)
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
        "ok": True,
        "tool": "sentinel-ctl",
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
