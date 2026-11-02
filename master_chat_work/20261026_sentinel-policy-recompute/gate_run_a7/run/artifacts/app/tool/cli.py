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

SELECTABLE_STATUS = ("active", "reinstated")


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


def read_kv_text(path):
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith(";"):
            continue
        key, sep, value = stripped.partition("=")
        if not sep:
            continue
        out[key.strip()] = value.strip()
    return out


def _parser(path):
    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")
    return parser


def read_conf(path):
    parser = _parser(path)
    flat = {}
    for section in parser.sections():
        for key, value in parser.items(section):
            flat[key] = value
    return flat


def read_conf_section(path, section):
    parser = _parser(path)
    if not parser.has_section(section):
        return {}
    return dict(parser.items(section))


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


def round_half_up_bps(value, bps):
    """round_half_up(value * bps / 1000) in exact integer arithmetic."""
    return (value * bps + 500) // 1000


def _run_curve(base_threshold, contribution, divisor, epsilon, max_iterations):
    iterations = [base_threshold]
    current = base_threshold
    for _ in range(max_iterations):
        nxt = base_threshold + (contribution + current) // divisor
        iterations.append(nxt)
        if abs(nxt - current) <= epsilon:
            return iterations, nxt
        current = nxt
    return iterations, None


def _best_repair(spares, need_rows, need_mr, need_ms):
    """Smallest total absolute timeout, ties to the first ascending seq list."""
    if need_rows < 0 or need_rows > len(spares):
        return None
    rows = sorted(spares, key=lambda r: r["seq"])
    best = None
    for combo in itertools.combinations(rows, need_rows):
        if sum(r["mr"] for r in combo) != need_mr:
            continue
        if sum(r["ms"] for r in combo) != need_ms:
            continue
        seqs = [r["seq"] for r in combo]
        key = (sum(abs(r["ms"]) for r in combo), seqs)
        if best is None or key < best[0]:
            best = (key, seqs)
    return best[1] if best else None


class Corpus:
    """The reference material, recording every file in the order it is consumed."""

    def __init__(self, data_dir):
        self.dir = Path(data_dir)
        self.order = []

    def path(self, name):
        if name not in self.order:
            self.order.append(name)
        return self.dir / name

    def text(self, name):
        return Path(self.path(name)).read_text(encoding="utf-8")

    def has(self, name):
        return (self.dir / name).exists()


def resolve_policy(data_dir):
    cx = Corpus(data_dir)

    # boot manifest -> stale version rules -> ledger -> principal index -> overrides
    manifest = read_toml(cx.path("boot_manifest.toml"))["manifest"]
    instant = int(manifest["effective_instant"])
    stale = read_kv_text(cx.path("stale_version_rules.txt"))
    active_bundle = str(manifest[stale["prefer"]])
    ignored_bundle = str(manifest[stale["ignore"]])

    ledger = read_jsonc(cx.path(manifest["ledger_ref"]))
    bundle = ledger[active_bundle]
    role_key = bundle["role_key"]
    index = read_yaml_flat(cx.path(bundle["index_file"]))

    def role_params(key):
        return (
            index[key + ".param_key"],
            index[key + ".tenant"],
            int(index[key + ".role_level"]),
        )

    param_key, tenant, role_level = role_params(role_key)

    vmap = load_json(cx.path("policy_version_map.json"))
    version_rows = vmap["versions"]
    version = max(
        (v for v in version_rows if int(v["effective_from"]) <= instant),
        key=lambda v: int(v["effective_from"]),
    )["version"]
    effective_from = {v["version"]: int(v["effective_from"]) for v in version_rows}

    corpus_doc = load_json(cx.path("request_corpus.json"))
    client_version_ignored = any(
        entry["claimed_version"] != version for entry in corpus_doc["entries"]
    )

    units_text = cx.text("units_reference.txt")
    cutover = int(re.search(r"cutover:\s*(-?\d+)", units_text).group(1))
    ms_factor = int(re.search(r"ms\s*=\s*seconds\s*\*\s*(\d+)", units_text).group(1))
    timeout_floor = int(re.search(r"raised to (\d+)", units_text).group(1))

    base_rows = {
        row["param_key"]: row
        for row in read_parquet_rows(cx.path("base_parameters.parquet"))
    }

    odoc = load_json(cx.path(index["overrides_ref"]))
    stored = sorted(odoc["overrides"], key=lambda r: int(r["seq"]))
    alias_map = {a["alias"]: a for a in odoc.get("param_key_aliases", [])}
    reports = odoc.get("reports", [])
    controls = odoc.get("controls", {})

    windows = {
        w["id"]: w for w in read_xml_records(cx.path("effective_windows.xml"), "window")
    }
    read_conf(cx.path("override_precedence.conf"))
    catalog = {
        t["id"]: t for t in read_xml_records(cx.path("tenant_catalog.xml"), "tenant")
    }
    allowance = {
        key: int(value)
        for key, value in read_conf_section(
            cx.path("quota_limits.cfg"), "override_allowance"
        ).items()
    }

    def principal_of(row):
        entry = alias_map.get(row["param_key"])
        if entry is None:
            return row["param_key"]
        if int(entry["start"]) <= instant < int(entry["end"]):
            return entry["principal"]
        return None

    def delta_ms(row):
        value = int(row["timeout_ms_delta"])
        return value * ms_factor if effective_from[row["version"]] < cutover else value

    latest_seq = {}
    for row in stored:
        latest_seq[row["override_id"]] = int(row["seq"])

    def source_row(row):
        """A reinstated row adds the deltas of the last active row below its seq."""
        if row["status"] != "reinstated":
            return row
        prior = [
            r
            for r in stored
            if r["override_id"] == row["override_id"]
            and r["status"] == "active"
            and int(r["seq"]) < int(row["seq"])
        ]
        return prior[-1] if prior else None

    # selection per override_precedence.conf
    refused = []
    passing = []
    for row in stored:
        window = windows.get(row["window_id"])
        if int(row["seq"]) != latest_seq[row["override_id"]]:
            reason = "reissued: the same override_id is stored at a higher seq"
        elif row["status"] not in SELECTABLE_STATUS:
            reason = "status " + row["status"] + " passes no selection"
        elif window is None:
            reason = "window " + row["window_id"] + " is not in effective_windows.xml"
        elif not int(window["start"]) <= instant < int(window["end"]):
            reason = (
                "window " + row["window_id"]
                + " does not contain effective_instant in its half-open span"
            )
        elif row["version"] != version:
            reason = (
                "row version " + row["version"]
                + " is not the effective version " + version
            )
        elif window["version"] != version:
            reason = (
                "window " + row["window_id"] + " carries version " + window["version"]
                + ", not the effective version " + version
            )
        elif source_row(row) is None:
            reason = "reinstated with no earlier active row of its override_id"
        else:
            reason = None
        if reason is None:
            passing.append(row)
        else:
            refused.append((row, reason))

    # draw: ascending seq, one region allowance unit and one window admit unit each
    admit_left = {wid: int(w.get("admit", 0)) for wid, w in windows.items()}
    allow_left = dict(allowance)
    applied = []
    applied_ids = set()
    for row in passing:
        region = catalog[row["tenant"]]["region"]
        if "requires" in row and row["requires"] not in applied_ids:
            refused.append(
                (
                    row,
                    "requires " + str(row["requires"])
                    + ", which was not applied at a lower seq",
                )
            )
            continue
        if allow_left.get(region, 0) <= 0:
            refused.append(
                (row, "region " + region + " has no override_allowance unit left")
            )
            continue
        if admit_left.get(row["window_id"], 0) <= 0:
            refused.append((row, "window " + row["window_id"] + " has no admit unit left"))
            continue
        allow_left[region] -= 1
        admit_left[row["window_id"]] -= 1
        applied.append(row)
        applied_ids.add(row["override_id"])

    # the applied rows of a window share that window's timeout_pool
    added_ms = {}
    for wid in sorted({row["window_id"] for row in applied}):
        pool = int(windows[wid].get("timeout_pool", 0))
        positive = []
        for row in applied:
            if row["window_id"] != wid:
                continue
            value = delta_ms(source_row(row))
            if value > 0:
                positive.append((int(row["seq"]), value))
            else:
                added_ms[int(row["seq"])] = value
        total = sum(value for _, value in positive)
        if total <= pool:
            for seq, value in positive:
                added_ms[seq] = value
            continue
        shares = {seq: pool * value // total for seq, value in positive}
        keep = [(seq, value) for seq, value in positive if shares[seq] >= 100]
        kept = sum(value for _, value in keep)
        for seq, _ in positive:
            added_ms[seq] = 0
        for seq, value in keep:
            added_ms[seq] = pool * value // kept

    # a superseded row with a carry field contributes that one delta
    carried = []
    for row in stored:
        window = windows.get(row["window_id"])
        if row["status"] != "superseded" or "carry" not in row or window is None:
            continue
        if not int(window["start"]) <= instant < int(window["end"]):
            continue
        if row["version"] == version and window["version"] == version:
            carried.append(row)

    multipliers = {
        row["tenant"]: row
        for row in read_xlsx_rows(cx.path("tenant_multiplier_table.xlsx"))
    }
    cx.text("clamp_rules.txt")
    cx.text("risk_weight_rounding.txt")
    tier_curve = {
        int(row["tier"]): int(row["base_threshold"])
        for row in read_parquet_rows(cx.path("threshold_tier_curve.parquet"))
    }

    conv_text = cx.text("convergence_spec.txt")
    epsilon = int(re.search(r"convergence_epsilon\s*=\s*(-?\d+)", conv_text).group(1))
    max_iterations = int(re.search(r"max_iterations\s*=\s*(\d+)", conv_text).group(1))

    rec_text = cx.text("reconciliation_rules.conf")
    rec = read_conf(cx.path("reconciliation_rules.conf"))
    bounds = re.search(r"whole number from (\d+) to (\d+)", rec_text)
    divisor_range = range(int(bounds.group(1)), int(bounds.group(2)) + 1)

    def compile_params(key, tenant_id, level):
        base = base_rows[key]
        mult = multipliers[tenant_id]
        mult_bps = int(mult["mult_bps"])
        cap = int(mult["max_records_cap"])
        mine = [row for row in applied if principal_of(row) == key]
        # a reinstated row adds the deltas of the active row it reinstates
        deltas = [source_row(row) for row in mine]

        def carry_of(field):
            return [
                row
                for row in carried
                if principal_of(row) == key and row["carry"] == field
            ]

        after_delta = int(base["max_records_base"])
        after_delta += sum(int(r["max_records_delta"]) for r in deltas)
        after_delta += sum(
            int(r["max_records_delta"]) for r in carry_of("max_records_delta")
        )
        max_records = min(cap, round_half_up_bps(after_delta, mult_bps))

        retry_limit = int(base["retry_limit_base"])
        retry_limit += sum(int(r["retry_limit_delta"]) for r in deltas)

        timeout_ms = int(base["timeout_seconds_base"]) * ms_factor
        for row in mine:
            timeout_ms += added_ms[int(row["seq"])]
            timeout_ms = max(timeout_ms, timeout_floor)

        terms = [int(base["risk_weight_base"])]
        terms += [int(r["risk_delta"]) for r in deltas]
        terms += [int(r["risk_delta"]) for r in carry_of("risk_delta")]
        contribution = sum(round_half_up_bps(term, mult_bps) for term in terms)

        return {
            "max_records": max_records,
            "retry_limit": retry_limit,
            "timeout_ms": timeout_ms,
            "contribution": contribution,
            "base_threshold": tier_curve[level],
            "applied": mine,
        }

    # the iteration divisor is the one under which every standing curve report converges
    last_reset = max(
        (int(r["seq"]) for r in reports if r.get("kind") == "reset"), default=None
    )
    standing = [
        r
        for r in reports
        if r.get("kind") == "curve" and (last_reset is None or int(r["seq"]) > last_reset)
    ]
    if standing:
        candidates = []
        for candidate in divisor_range:
            for report in standing:
                rkey, rtenant, rlevel = role_params(report["role"])
                rparams = compile_params(rkey, rtenant, rlevel)
                _, got = _run_curve(
                    rparams["base_threshold"],
                    rparams["contribution"],
                    candidate,
                    epsilon,
                    max_iterations,
                )
                if got != int(report["converged"]):
                    break
            else:
                candidates.append(candidate)
        divisor = candidates[0] if len(candidates) == 1 else None
    else:
        divisor = int(rec["iteration_divisor"])

    params = compile_params(param_key, tenant, role_level)
    if divisor is None:
        iterations, converged = [params["base_threshold"]], None
    else:
        iterations, converged = _run_curve(
            params["base_threshold"],
            params["contribution"],
            divisor,
            epsilon,
            max_iterations,
        )

    schema = load_json(cx.path("config_schema.json"))
    defaults = load_json(cx.path("defaults.json"))
    resolved = {
        "profile": schema["profile"],
        "producer": schema["producer"],
        "container": schema["container"],
        "checksum": defaults["checksum"],
        "mode": defaults["mode"],
        "max_records": params["max_records"],
        "retry_limit": params["retry_limit"],
        "timeout_ms": params["timeout_ms"],
        "trailer": str(defaults["base_config"]["trailer"]),
        "param_key": param_key,
        "tenant": tenant,
        "effective_version": version,
        "risk_threshold": converged,
    }

    # controls are a parse check over every stored row, timeouts in milliseconds
    recomputed = {}
    for row in stored:
        entry = recomputed.setdefault(
            row["tenant"],
            {"max_records_delta_sum": 0, "rows": 0, "timeout_ms_delta_sum_ms": 0},
        )
        entry["rows"] += 1
        entry["max_records_delta_sum"] += int(row["max_records_delta"])
        entry["timeout_ms_delta_sum_ms"] += delta_ms(row)
    ledger_controls = {
        name: ("ok" if recomputed.get(name) == dict(control) else "mismatch")
        for name, control in controls.items()
    }

    protected = set()
    for row in stored:
        if int(row["seq"]) == latest_seq[row["override_id"]] and row["status"] == "reinstated":
            src = source_row(row)
            if src is not None:
                protected.add(int(src["seq"]))

    def is_spare(row):
        if int(row["seq"]) in protected:
            return False
        if row["status"] == "withdrawn":
            return True
        if row["status"] == "superseded" and "carry" not in row:
            return True
        return int(row["seq"]) != latest_seq[row["override_id"]]

    ledger_repair = {}
    for name, state in ledger_controls.items():
        if state != "mismatch":
            continue
        got = recomputed.get(
            name, {"max_records_delta_sum": 0, "rows": 0, "timeout_ms_delta_sum_ms": 0}
        )
        control = controls[name]
        spares = [
            {"seq": int(r["seq"]), "mr": int(r["max_records_delta"]), "ms": delta_ms(r)}
            for r in stored
            if r["tenant"] == name and is_spare(r)
        ]
        ledger_repair[name] = _best_repair(
            spares,
            got["rows"] - int(control["rows"]),
            got["max_records_delta_sum"] - int(control["max_records_delta_sum"]),
            got["timeout_ms_delta_sum_ms"] - int(control["timeout_ms_delta_sum_ms"]),
        )

    rejected = []

    def reject(name, reason):
        rejected.append({"name": name, "reason": reason})

    reject(
        ignored_bundle,
        "bundle status " + str(ledger.get(ignored_bundle, {}).get("status"))
        + "; it is the " + stale["ignore"] + " and stale_version_rules.txt prefers "
        + stale["prefer"] + " " + active_bundle,
    )
    for bid in sorted(ledger):
        if bid not in (active_bundle, ignored_bundle) and ledger[bid].get("status") != "active":
            reject(bid, "ledger bundle status " + str(ledger[bid].get("status")))
    legacy_role = ledger.get(ignored_bundle, {}).get("role_key")
    if legacy_role:
        reject(legacy_role, "role_key of the superseded bundle " + ignored_bundle)
        if legacy_role + ".param_key" in index:
            reject(
                index[legacy_role + ".param_key"],
                "param_key of the superseded role " + legacy_role,
            )
    for name, why in (
        ("legacy_override_table.ini", "legacy override table of the superseded bundle"),
        ("superseded_windows.xml", "superseded effective-time windows"),
        ("principal_alias_table.jsonc", "conflicting aliases from the retired bundle"),
        ("legacy_policy_memo.pdf", "retired bundle memo, retained for audit only"),
        (
            "threshold_overrides.json",
            "tier deltas bound by no rule; the curve comes from threshold_tier_curve.parquet",
        ),
        (
            "tenant_region_multipliers.xlsx",
            "region multipliers; the tenant multiplier comes from tenant_multiplier_table.xlsx",
        ),
        ("effective_instant_examples.xml", "half-open window examples, context only"),
    ):
        if cx.has(name):
            reject(name, why)
    reject(
        "request_corpus.json",
        "client-claimed versions are not authoritative; the effective version "
        + version + " comes from policy_version_map.json",
    )
    for wid in sorted(windows):
        window = windows[wid]
        if int(window["start"]) <= instant < int(window["end"]):
            if window["version"] != version:
                reject(wid, "window carries version " + window["version"] + ", not " + version)
        elif int(window["end"]) == instant:
            reject(wid, "window span is half-open and ends at effective_instant")
    for row, reason in sorted(refused, key=lambda item: int(item[0]["seq"])):
        if principal_of(row) == param_key:
            reject(row["override_id"], reason)

    trace = {
        "active_bundle": active_bundle,
        "effective_version": version,
        "param_key": param_key,
        "tenant": tenant,
        "client_version_ignored": client_version_ignored,
        "applied_overrides": [row["override_id"] for row in params["applied"]],
        "ledger_controls": ledger_controls,
        "resolution_order": list(cx.order),
        "rejected_branches": rejected,
    }
    curve = {
        "tier": role_level,
        "base_threshold": params["base_threshold"],
        "contribution": params["contribution"],
        "iterations": iterations,
        "converged": converged,
    }
    return resolved, trace, curve, ledger_repair


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
    report = {
        "ok": True,
        "tool": "sentinel-ctl",
        "commands": json.loads(args.commands),
        "config_sha256": args.digest,
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
    if getattr(args, "func", None) is None:
        parser.error("a subcommand is required")
    args.func(args)


if __name__ == "__main__":
    main()
