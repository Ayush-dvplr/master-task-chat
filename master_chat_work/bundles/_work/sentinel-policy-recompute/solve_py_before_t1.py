#!/usr/bin/env python3
from __future__ import annotations

import ast
import hashlib
import json
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from decimal import ROUND_HALF_UP, Decimal
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

READ_ERRORS = (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError,
               ET.ParseError, zipfile.BadZipFile, configparser.Error)


def declared_input(reader):
    # a declared input that is missing or does not parse stops the run with a message naming the file
    def wrapped(path, *args):
        if not Path(path).is_file():
            raise SystemExit("sentinel-ctl: declared input missing: " + str(path))
        try:
            return reader(path, *args)
        except READ_ERRORS as exc:
            raise SystemExit("sentinel-ctl: malformed input " + str(path) + ": " + repr(exc)) from exc
    return wrapped


@declared_input
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


@declared_input
def read_toml(path):
    import tomllib

    return tomllib.loads(Path(path).read_text(encoding="utf-8"))


@declared_input
def read_jsonc(path):
    text = Path(path).read_text(encoding="utf-8")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"(^|\s)//[^\n]*", "", text)
    return json.loads(text)


@declared_input
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


@declared_input
def read_conf(path):
    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")
    flat = {}
    for section in parser.sections():
        for key, value in parser.items(section):
            flat[key] = value
    return flat


@declared_input
def read_env_kv(path):
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        out[key.strip()] = value.strip()
    return out


@declared_input
def read_txt_kv(path):
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        out[key.strip()] = value.strip()
    return out


@declared_input
def read_colon_kv(path):
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if ":" in line and not line.startswith("#"):
            key, _, value = line.partition(":")
            out[key] = value
    return out


@declared_input
def read_xml_records(path, tag):
    root = ET.parse(path).getroot()
    return [dict(node.attrib) for node in root.iter(tag)]


def _col_to_idx(ref):
    letters = re.match(r"[A-Z]+", ref).group(0)
    idx = 0
    for char in letters:
        idx = idx * 26 + (ord(char) - ord("A") + 1)
    return idx - 1


@declared_input
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


@declared_input
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
    order = []
    try:
        return _resolve_policy(Path(data_dir), order)
    except (KeyError, ValueError, IndexError, TypeError, AttributeError) as exc:
        last = order[-1] if order else "boot_manifest.toml"
        raise SystemExit("sentinel-ctl: malformed input under " + str(data_dir)
                         + " near " + last + ": " + repr(exc)) from exc


def _resolve_policy(data, order):
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

    version_from = {row["version"]: int(row["effective_from"]) for row in version_rows}
    units = read_colon_kv(data / "units_reference.txt")
    note("units_reference.txt")
    cutover = int(units["timeout_ms_delta cutover"].strip())

    def delta_ms(row):
        # the stored unit follows the effective_from of the row's version
        value = int(row["timeout_ms_delta"])
        return value * 1000 if version_from[row["version"]] < cutover else value

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

    regions = {row["id"]: row["region"] for row in read_xml_records(data / "tenant_catalog.xml", "tenant")}
    note("tenant_catalog.xml")
    allowance_rows = read_conf(data / "quota_limits.cfg")
    note("quota_limits.cfg")
    region_left = {}
    admit_left = {wid: int(w["admit"]) for wid, w in windows.items()}

    applied = []
    drawn = []  # applied rows of every principal; they share window timeout pools
    rejected_overrides = []
    for override in overrides:  # every tenant draws, in ascending seq
        window = windows.get(override["window_id"])
        region = regions[override["tenant"]]
        region_left.setdefault(region, int(allowance_rows[region]))
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
        elif region_left[region] <= 0:
            reason = "region-allowance-used-up"
        elif admit_left[override["window_id"]] <= 0:
            reason = "window-admits-used-up"
        else:
            region_left[region] -= 1
            admit_left[override["window_id"]] -= 1
            drawn.append(override)
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
    added_ms = {}
    for window_id in sorted({row["window_id"] for row in drawn}):
        rows = [row for row in drawn if row["window_id"] == window_id]
        for row in rows:
            if delta_ms(row) <= 0:
                added_ms[row["override_id"]] = delta_ms(row)
        sharing = {row["override_id"]: delta_ms(row) for row in rows if delta_ms(row) > 0}
        pool = int(windows[window_id]["timeout_pool"])
        total = sum(sharing.values())
        if total <= pool:
            added_ms.update(sharing)
            continue
        held = {oid: d for oid, d in sharing.items() if pool * d // total >= 100}
        held_total = sum(held.values())
        for oid, d in sharing.items():
            added_ms[oid] = pool * d // held_total if oid in held else 0  # whole pool shared again
    timeout_ms = int(base["timeout_seconds_base"]) * factor + sum(added_ms[row["override_id"]] for row in applied)

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
    try:
        commands = json.loads(args.commands)
    except ValueError as exc:
        raise SystemExit("sentinel-ctl: --commands is not a JSON list: " + repr(exc)) from exc
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


def run_cli(*args, keep_stderr=False):
    cmd = [sys.executable, str(TOOL / "cli.py"), *args]
    result = subprocess.run(cmd, cwd=TOOL, text=True, capture_output=True, timeout=60, check=False)
    entry = {"argv": ["python3", "cli.py", *args], "returncode": result.returncode, "stdout": result.stdout.strip()}
    print(json.dumps(entry, sort_keys=True))
    if result.stderr.strip():
        print("stderr: " + result.stderr.strip()[-2000:])
    return dict(entry, stderr=result.stderr.strip()) if keep_stderr else entry


def inspect_shipped_tool() -> None:
    source = (TOOL / "cli.py").read_text(encoding="utf-8").splitlines()
    print("\n".join(source[:30]))
    shipped_run = run_cli("resolve", "--data-dir", str(DATA), "--out", str(SHIPPED_SCRATCH), keep_stderr=True)
    failure = (shipped_run["stderr"].splitlines() or ["no stderr"])[-1]
    print("check R1 ok  shipped sentinel-ctl resolve ran before the first edit to /app/tool/cli.py: returncode "
          + str(shipped_run["returncode"]) + ", " + failure)
    # The shipped resolve stops at its configparser call, so a scratch copy with only that call
    # changed shows the values its computation produces, next to the repaired computation.
    scratch = Path(tempfile.mkdtemp(prefix="sentinel-shipped-"))
    shipped = (TOOL / "cli.py").read_text(encoding="utf-8")
    copies = {
        "shipped": shipped.replace("configparser.SafeConfigParser()", "configparser.ConfigParser()"),
        "repaired": CORRECT_CLI,
    }
    printed = {}
    for label, text in copies.items():
        script = scratch / (label + "_cli.py")
        script.write_text(text, encoding="utf-8")
        cmd = [sys.executable, str(script), "resolve", "--data-dir", str(DATA), "--out", str(scratch / label)]
        result = subprocess.run(cmd, text=True, capture_output=True, timeout=60, check=True)
        print(json.dumps({"argv": ["python3", script.name, *cmd[2:]], "stdout": result.stdout.strip()}))
        printed[label] = json.loads(result.stdout)
    wrong = []
    for key in sorted(printed["shipped"]):
        if printed["shipped"][key] != printed["repaired"].get(key):
            wrong.append(key + "=" + str(printed["shipped"][key]) + " where the reference files give "
                         + str(printed["repaired"].get(key)))
            print("[oracle] shipped computation prints wrong value " + wrong[-1])
    print("check R10 ok  defects named before the first edit to /app/tool/cli.py: configparser.SafeConfigParser"
          " was removed in Python 3.12; shipped computation prints " + (wrong[0] if wrong else "no differing value"))
    shutil.rmtree(scratch)


def self_check_ledger() -> None:
    # A corpus built here, unlike the shipped one: an earlier t-aurora row (same region r-north as
    # t-atlas) uses one unit of the r-north allowance of 3; a t-f003 row uses one admit of WIN-AUTH
    # (admit 2); a v100 row with rev 1 stores milliseconds; a pre-cutover t-atlas row with rev 2 stores
    # seconds in the control; a K042 row refused by the window draws no region unit, so the next K042
    # row in WIN-SC still gets one; the last K042 row is refused by the region allowance.
    corpus = Path(tempfile.mkdtemp(prefix="sentinel-selfcheck-"))
    for path in DATA.iterdir():
        if path.is_file():
            shutil.copyfile(path, corpus / path.name)
    ledger = json.loads((corpus / "override_deltas.json").read_text(encoding="utf-8"))
    own = [
        ("OV-SC-0", "K042", "t-atlas", "superseded", "WIN-OLD", "v040", 2, 3, 0, 0, 0),
        ("OV-SC-1", "K301", "t-aurora", "active", "WIN-SC", "v100", 2, 10, 0, 0, 0),
        ("OV-SC-2", "K003", "t-f003", "active", "WIN-AUTH", "v100", 2, 10, 0, 0, 0),
        ("OV-SC-3", "K042", "t-atlas", "active", "WIN-AUTH", "v100", 1, 60, -40, 1, 2),
        ("OV-SC-4", "K042", "t-atlas", "active", "WIN-AUTH", "v100", 2, 400, -30, 1, 5),
        ("OV-SC-5", "K042", "t-atlas", "active", "WIN-SC", "v100", 2, 2, -10, 0, 2),
        ("OV-SC-6", "K042", "t-atlas", "active", "WIN-SC", "v100", 2, 400, -20, 1, 9),
    ]
    rows = [{"max_records_delta": mr, "override_id": oid, "param_key": key, "retry_limit_delta": rr,
             "rev": rev, "risk_delta": risk, "status": status, "tenant": owner,
             "timeout_ms_delta": td, "version": ver, "window_id": wid}
            for (oid, key, owner, status, wid, ver, rev, td, mr, rr, risk) in own]
    kept = [row for row in ledger["overrides"] if not row["override_id"].startswith(("OV-K042-", "OV-K118-", "OV-K301-"))]
    ledger["overrides"] = rows + kept
    for seq, row in enumerate(ledger["overrides"], start=1):
        row["seq"] = seq
    froms = {row["version"]: int(row["effective_from"])
             for row in json.loads((corpus / "policy_version_map.json").read_text(encoding="utf-8"))["versions"]}
    controls = {}
    for row in ledger["overrides"]:
        entry = controls.setdefault(row["tenant"], {"max_records_delta_sum": 0, "rows": 0, "timeout_ms_delta_sum_ms": 0})
        entry["rows"] += 1
        entry["max_records_delta_sum"] += row["max_records_delta"]
        entry["timeout_ms_delta_sum_ms"] += row["timeout_ms_delta"] * (1000 if froms[row["version"]] < 1650000000 else 1)
    ledger["controls"] = {name: controls[name] for name in sorted(controls)}
    (corpus / "override_deltas.json").write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    quota = (corpus / "quota_limits.cfg").read_text(encoding="utf-8")
    (corpus / "quota_limits.cfg").write_text(re.sub(r"(?m)^r-north = \d+$", "r-north = 3", quota), encoding="utf-8")
    windows = (corpus / "effective_windows.xml").read_text(encoding="utf-8")
    windows = windows.replace('version="v100" admit="3" timeout_pool="1200" />',
                              'version="v100" admit="2" timeout_pool="1200" /><window id="WIN-SC" '
                              'start="1699999800" end="1700000200" version="v100" admit="5" timeout_pool="1500" />', 1)
    (corpus / "effective_windows.xml").write_text(windows, encoding="utf-8")

    out = corpus / "resolved"
    entry = run_cli("resolve", "--data-dir", str(corpus), "--out", str(out))
    if entry["returncode"] != 0:
        raise SystemExit(entry)
    resolved = json.loads(entry["stdout"])
    trace = json.loads((out / "dependency_trace.json").read_text(encoding="utf-8"))
    curve = json.loads((out / "threshold_curve.json").read_text(encoding="utf-8"))
    # by hand: SC-1 r-north 3->2, WIN-SC 5->4; SC-2 r-03, WIN-AUTH 2->1; SC-3 applied, r-north 1, WIN-AUTH 0;
    # SC-4 refused by WIN-AUTH and draws no r-north unit; SC-5 applied, r-north 0; SC-6 refused by r-north.
    # max_records min(285, half_up(250 * 1.075)) = 269; retry 2 + 1 + 0 = 3;
    # timeout 2000 + 60 + 2 = 2062 (60 is milliseconds on a v100 row); contribution 61 + 2 + 2 = 65.
    expected = {"applied_overrides": ["OV-SC-3", "OV-SC-5"], "max_records": 269, "retry_limit": 3,
                "timeout_ms": 2062, "contribution": 65, "t-atlas control": "ok"}
    got = {"applied_overrides": trace["applied_overrides"], "max_records": resolved["max_records"],
           "retry_limit": resolved["retry_limit"], "timeout_ms": resolved["timeout_ms"],
           "contribution": curve["contribution"], "t-atlas control": trace["ledger_controls"]["t-atlas"]}
    print("self-check expected " + json.dumps(expected, sort_keys=True))
    print("self-check got      " + json.dumps(got, sort_keys=True))
    if got != expected:
        raise SystemExit("self-check failed on the constructed corpus")
    print("ledger-check ok  unit cutover: timeout_ms 2062: v100 row with rev 1 read in milliseconds; v040 row with rev 2 read in seconds (t-atlas control ok)")
    print("ledger-check ok  region allowance: t-aurora row OV-SC-1 used an r-north unit first; OV-SC-6 refused when r-north ran out")
    print("ledger-check ok  window admit: t-f003 row OV-SC-2 used a WIN-AUTH admit; OV-SC-4 refused by the window drew no r-north unit, so OV-SC-5 applied")
    print("ledger-check ok  hand ledger: two K042 rows applied, max_records 269, retry_limit 3, timeout_ms 2062 as computed by hand")
    shutil.rmtree(corpus)


def self_check_pool() -> None:
    # A second constructed corpus: three applied WIN-AUTH rows (one of them another tenant's K003 row)
    # ask 60 + 450 + 300 = 810 ms of a 780 ms pool. First share: 57, 433, 288; the K003 row falls
    # below 100 and adds none. The whole pool is then shared again across the two rows that held:
    # floor(780 * 450 / 750) = 468 and floor(780 * 300 / 750) = 312. The fits test is not taken again.
    corpus = Path(tempfile.mkdtemp(prefix="sentinel-poolcheck-"))
    for path in DATA.iterdir():
        if path.is_file():
            shutil.copyfile(path, corpus / path.name)
    ledger = json.loads((corpus / "override_deltas.json").read_text(encoding="utf-8"))
    own = [
        ("OV-PC-1", "K003", "t-f003", 60, 0, 0, 0),
        ("OV-PC-2", "K042", "t-atlas", 450, -20, 1, 2),
        ("OV-PC-3", "K042", "t-atlas", 300, -30, 0, 3),
    ]
    rows = [{"max_records_delta": mr, "override_id": oid, "param_key": key, "retry_limit_delta": rr,
             "rev": 2, "risk_delta": risk, "status": "active", "tenant": owner,
             "timeout_ms_delta": td, "version": "v100", "window_id": "WIN-AUTH"}
            for (oid, key, owner, td, mr, rr, risk) in own]
    kept = [row for row in ledger["overrides"] if not row["override_id"].startswith(("OV-K042-", "OV-K118-", "OV-K301-"))]
    ledger["overrides"] = rows + kept
    for seq, row in enumerate(ledger["overrides"], start=1):
        row["seq"] = seq
    froms = {row["version"]: int(row["effective_from"])
             for row in json.loads((corpus / "policy_version_map.json").read_text(encoding="utf-8"))["versions"]}
    controls = {}
    for row in ledger["overrides"]:
        entry = controls.setdefault(row["tenant"], {"max_records_delta_sum": 0, "rows": 0, "timeout_ms_delta_sum_ms": 0})
        entry["rows"] += 1
        entry["max_records_delta_sum"] += row["max_records_delta"]
        entry["timeout_ms_delta_sum_ms"] += row["timeout_ms_delta"] * (1000 if froms[row["version"]] < 1650000000 else 1)
    ledger["controls"] = {name: controls[name] for name in sorted(controls)}
    (corpus / "override_deltas.json").write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    windows = (corpus / "effective_windows.xml").read_text(encoding="utf-8")
    windows = windows.replace('version="v100" admit="3" timeout_pool="1200" />',
                              'version="v100" admit="3" timeout_pool="780" />', 1)
    (corpus / "effective_windows.xml").write_text(windows, encoding="utf-8")

    out = corpus / "resolved"
    entry = run_cli("resolve", "--data-dir", str(corpus), "--out", str(out))
    if entry["returncode"] != 0:
        raise SystemExit(entry)
    resolved = json.loads(entry["stdout"])
    trace = json.loads((out / "dependency_trace.json").read_text(encoding="utf-8"))
    # timeout 2000 + 468 + 312 = 2780; max_records min(285, half_up(250 * 1.075)) = 269; retry 2 + 1 = 3.
    expected = {"applied_overrides": ["OV-PC-2", "OV-PC-3"], "max_records": 269, "retry_limit": 3, "timeout_ms": 2780}
    got = {"applied_overrides": trace["applied_overrides"], "max_records": resolved["max_records"],
           "retry_limit": resolved["retry_limit"], "timeout_ms": resolved["timeout_ms"]}
    print("pool-check expected " + json.dumps(expected, sort_keys=True))
    print("pool-check got      " + json.dumps(got, sort_keys=True))
    if got != expected:
        raise SystemExit("pool self-check failed on the constructed corpus")
    print("pool-check ok  timeout_ms 2780: K003 row fell below 100 and added none; the whole 780 ms pool was shared again as 468 + 312")
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
    self_check_pool()
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


# ---- self-check stage: runs after the deliverables exist; writes only to scratch copies ----

def out_digests():
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(OUT.iterdir()) if path.is_file()}


def scratch_corpus(root, label):
    corpus = root / label
    corpus.mkdir()
    for path in DATA.iterdir():
        if path.is_file():
            shutil.copyfile(path, corpus / path.name)
    return corpus


def resolve_on(corpus, keep_stderr=False):
    out = corpus.parent / (corpus.name + "-out")
    entry = run_cli("resolve", "--data-dir", str(corpus), "--out", str(out), keep_stderr=keep_stderr)
    if keep_stderr:
        return entry, None, None, None
    if entry["returncode"] != 0:
        raise SystemExit("resolve failed on " + str(corpus))
    trace = json.loads((out / "dependency_trace.json").read_text(encoding="utf-8"))
    curve = json.loads((out / "threshold_curve.json").read_text(encoding="utf-8"))
    return entry, json.loads(entry["stdout"]), trace, curve


def edit_text(path, old, new):
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit("self-check edit not unique in " + path.name + ": " + old)
    path.write_text(text.replace(old, new), encoding="utf-8")


def set_tenant_mult(xlsx, tenant, mult_bps):
    with zipfile.ZipFile(xlsx) as zf:
        members = [(info, zf.read(info)) for info in zf.infolist()]
    pattern = re.compile(r'(<row r="(\d+)"><c r="A\2" t="inlineStr"><is><t>' + re.escape(tenant)
                         + r'</t></is></c><c r="B\2" t="inlineStr"><is><t>)(\d+)(</t>)')
    with zipfile.ZipFile(xlsx, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for info, body in members:
            if info.filename == "xl/worksheets/sheet1.xml":
                text, count = pattern.subn(lambda m: m.group(1) + str(mult_bps) + m.group(4), body.decode("utf-8"))
                if count != 1:
                    raise SystemExit("tenant row " + tenant + " not found in the multiplier sheet")
                body = text.encode("utf-8")
            zf.writestr(info, body)


def half_up(value):
    return int(Decimal(value).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def recompute_outside():
    # A second implementation, written apart from sentinel-ctl: it reads the reference files with its own
    # parsers and rounds with decimal ROUND_HALF_UP, following each rule as the reference file states it.
    import configparser
    import tomllib
    import xml.etree.ElementTree as ET
    import pyarrow.parquet as pq

    def text(name):
        return (DATA / name).read_text(encoding="utf-8")

    def flat_yaml(name):
        pairs = (line.split(":", 1) for line in text(name).splitlines() if ":" in line and not line.lstrip().startswith("#"))
        return {key.strip(): value.split("#")[0].strip().strip('"') for key, value in pairs}

    manifest = tomllib.loads(text("boot_manifest.toml"))["manifest"]
    instant = int(manifest["effective_instant"])
    ledger = json.loads(re.sub(r"(^|\s)//[^\n]*", "", re.sub(r"/\*.*?\*/", "", text("bundle_ledger.jsonc"), flags=re.S)))
    role_key = ledger[manifest["active_bundle_id"]]["role_key"]
    index = flat_yaml("principal_role_index.yaml")
    param_key, tenant, role_level = index[role_key + ".param_key"], index[role_key + ".tenant"], int(index[role_key + ".role_level"])
    base = next(row for row in pq.read_table(DATA / "base_parameters.parquet").to_pylist() if row["param_key"] == param_key)
    versions = json.loads(text("policy_version_map.json"))["versions"]
    version = max((row for row in versions if int(row["effective_from"]) <= instant), key=lambda row: int(row["effective_from"]))["version"]
    version_from = {row["version"]: int(row["effective_from"]) for row in versions}
    windows = {node.get("id"): node.attrib for node in ET.parse(DATA / "effective_windows.xml").getroot().iter("window")}
    region_of = {node.get("id"): node.get("region") for node in ET.parse(DATA / "tenant_catalog.xml").getroot().iter("tenant")}
    quota = configparser.ConfigParser()
    quota.read_string(text("quota_limits.cfg"))
    allowance = {region: int(value) for region, value in quota["override_allowance"].items()}
    cutover = int(next(line.split(":", 1)[1] for line in text("units_reference.txt").splitlines()
                       if line.startswith("timeout_ms_delta cutover:")))
    rules = configparser.ConfigParser()
    rules.read_string(text("reconciliation_rules.conf"))
    factor = int(rules["reconcile"]["timeout_unit_factor"])
    divisor = int(rules["reconcile"]["iteration_divisor"])
    epsilon = int(next(line.split("=", 1)[1] for line in text("convergence_spec.txt").splitlines()
                       if line.startswith("convergence_epsilon")))

    def ms(row):
        return int(row["timeout_ms_delta"]) * (1000 if version_from[row["version"]] < cutover else 1)

    left_region, left_admit, drawn = dict(allowance), {wid: int(w["admit"]) for wid, w in windows.items()}, []
    for row in sorted(json.loads(text("override_deltas.json"))["overrides"], key=lambda row: int(row["seq"])):
        window = windows.get(row["window_id"])
        region = region_of[row["tenant"]]
        if (row["status"] == "active" and window is not None and int(window["start"]) <= instant < int(window["end"])
                and window["version"] == version and row["version"] == version
                and left_region[region] > 0 and left_admit[row["window_id"]] > 0):
            left_region[region] -= 1
            left_admit[row["window_id"]] -= 1
            drawn.append(row)
    applied = [row for row in drawn if row["param_key"] == param_key]
    added = {}
    for wid in {row["window_id"] for row in drawn}:
        asking = {row["override_id"]: ms(row) for row in drawn if row["window_id"] == wid and ms(row) > 0}
        added.update({row["override_id"]: ms(row) for row in drawn if row["window_id"] == wid and ms(row) <= 0})
        pool, total = int(windows[wid]["timeout_pool"]), sum(asking.values())
        if total <= pool:
            added.update(asking)
            continue
        kept = {oid: d for oid, d in asking.items() if pool * d // total >= 100}
        added.update({oid: (pool * d // sum(kept.values()) if oid in kept else 0) for oid, d in asking.items()})
    timeout_ms = int(base["timeout_seconds_base"]) * factor + sum(added[row["override_id"]] for row in applied)

    with zipfile.ZipFile(DATA / "tenant_multiplier_table.xlsx") as zf:
        sheet = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
    cells = dict(re.findall(r'<c r="([A-Z]+\d+)" t="inlineStr"><is><t>([^<]*)</t>', sheet))
    row_no = next(ref[1:] for ref, value in cells.items() if ref.startswith("A") and value == tenant)
    mult, cap = int(cells["B" + row_no]), int(cells["C" + row_no])
    contribution = sum(half_up(Decimal(term) * mult / 1000)
                       for term in [int(base["risk_weight_base"])] + [int(row["risk_delta"]) for row in applied])
    tier_base = next(int(row["base_threshold"]) for row in pq.read_table(DATA / "threshold_tier_curve.parquet").to_pylist()
                     if int(row["tier"]) == role_level)
    threshold = tier_base
    while True:
        following = tier_base + (contribution + threshold) // divisor
        if abs(following - threshold) <= epsilon:
            threshold = following
            break
        threshold = following
    max_records = min(cap, half_up(Decimal(int(base["max_records_base"]) + sum(int(row["max_records_delta"]) for row in applied)) * mult / 1000))
    prod_max_records = max_records + int(json.loads(text("sample_config_prod.json"))["max_records_delta"])
    return {"timeout_ms": timeout_ms, "threshold": threshold, "contribution": contribution,
            "prod_max_records": prod_max_records, "applied": sorted(row["override_id"] for row in applied)}


def self_check_probes() -> None:
    before = out_digests()
    root = Path(tempfile.mkdtemp(prefix="sentinel-probes-"))
    _, shipped, shipped_trace, shipped_curve = resolve_on(scratch_corpus(root, "as-shipped"))

    corpus = scratch_corpus(root, "window-end")
    edit_text(corpus / "effective_windows.xml", '<window id="WIN-AUTH" start="1699999000" end="1700001000"',
              '<window id="WIN-AUTH" start="1699999000" end="1700000000"')
    _, _, trace, _ = resolve_on(corpus)
    reasons = {row.get("override"): row.get("reason") for row in trace["rejected_branches"] if "override" in row}
    if "OV-K042-auth" in trace["applied_overrides"] or reasons.get("OV-K042-auth") != "window-excludes-effective-instant":
        raise SystemExit("window end boundary: OV-K042-auth was not excluded")
    print("check R2 ok  WIN-AUTH end set to the effective instant 1700000000: applied " + json.dumps(trace["applied_overrides"])
          + " (shipped " + json.dumps(shipped_trace["applied_overrides"]) + "), OV-K042-auth " + reasons["OV-K042-auth"])

    corpus = scratch_corpus(root, "half-term")
    deltas = json.loads((corpus / "override_deltas.json").read_text(encoding="utf-8"))
    row = next(row for row in deltas["overrides"] if row["override_id"] == "OV-K042-auth")
    old_delta, row["risk_delta"] = row["risk_delta"], 60
    (corpus / "override_deltas.json").write_text(json.dumps(deltas, indent=2) + "\n", encoding="utf-8")
    _, _, _, curve = resolve_on(corpus)
    expected = shipped_curve["contribution"] - half_up(Decimal(old_delta) * 1075 / 1000) + 65
    if curve["contribution"] != expected:
        raise SystemExit("half rounding: contribution " + str(curve["contribution"]) + ", expected " + str(expected))
    print("check R3 ok  OV-K042-auth risk_delta 60: term 60 * 1075 / 1000 = 64.5 rounds half up to 65; contribution "
          + str(curve["contribution"]) + " (shipped " + str(shipped_curve["contribution"]) + ")")

    corpus = scratch_corpus(root, "multiplier")
    set_tenant_mult(corpus / "tenant_multiplier_table.xlsx", shipped["tenant"], 900)
    _, resolved, _, _ = resolve_on(corpus)
    if resolved["max_records"] == shipped["max_records"]:
        raise SystemExit("tenant multiplier change left max_records unchanged")
    print("check R4 ok  " + shipped["tenant"] + " mult_bps 1075 -> 900: max_records " + str(shipped["max_records"])
          + " -> " + str(resolved["max_records"]))

    corpus = scratch_corpus(root, "role-level")
    edit_text(corpus / "principal_role_index.yaml", "operator.role_level: 4", "operator.role_level: 3")
    _, resolved, _, curve = resolve_on(corpus)
    if curve["base_threshold"] == shipped_curve["base_threshold"] and resolved["risk_threshold"] == shipped["risk_threshold"]:
        raise SystemExit("role_level change left the threshold unchanged")
    print("check R5 ok  operator.role_level 4 -> 3: base_threshold " + str(shipped_curve["base_threshold"]) + " -> "
          + str(curve["base_threshold"]) + ", risk_threshold " + str(shipped["risk_threshold"]) + " -> " + str(resolved["risk_threshold"]))

    corpus = scratch_corpus(root, "missing-input")
    (corpus / "tenant_multiplier_table.xlsx").unlink()
    entry, _, _, _ = resolve_on(corpus, keep_stderr=True)
    if entry["returncode"] == 0 or "tenant_multiplier_table.xlsx" not in entry["stderr"]:
        raise SystemExit("missing declared input was not reported by name")
    print("check R6 ok  tenant_multiplier_table.xlsx removed: returncode " + str(entry["returncode"]) + ", " + entry["stderr"].splitlines()[-1])

    outside = recompute_outside()
    config = json.loads((OUT / "config.json").read_text(encoding="utf-8"))
    report = json.loads((OUT / "validation_report.json").read_text(encoding="utf-8"))
    prod = json.loads((OUT / "profile_prod.json").read_text(encoding="utf-8"))
    pairs = [("R7", "timeout_ms of config.json", outside["timeout_ms"], config["timeout_ms"]),
             ("R8", "converged risk threshold in validation_report.json", outside["threshold"], report["threshold_curve"]["converged"]),
             ("R9", "max_records of profile_prod.json", outside["prod_max_records"], prod["max_records"])]
    for cid, what, mine, delivered in pairs:
        if mine != delivered:
            raise SystemExit(what + ": recomputed " + str(mine) + ", delivered " + str(delivered))
        print("check " + cid + " ok  " + what + ": recomputed outside sentinel-ctl " + str(mine) + ", delivered " + str(delivered)
              + " (applied " + ",".join(outside["applied"]) + ", contribution " + str(outside["contribution"]) + ")")

    corpus = scratch_corpus(root, "malformed-input")
    (corpus / "policy_version_map.json").write_text("{not json\n", encoding="utf-8")
    entry, _, _, _ = resolve_on(corpus, keep_stderr=True)
    tree = ast.parse((TOOL / "cli.py").read_text(encoding="utf-8"))
    handlers = [node for node in ast.walk(tree) if isinstance(node, ast.ExceptHandler)]
    if entry["returncode"] == 0 or "policy_version_map.json" not in entry["stderr"] \
            or not all(any(isinstance(stmt, ast.Raise) for stmt in node.body) for node in handlers):
        raise SystemExit("malformed declared input was not reported by name, or a handler swallows its error")
    print("check R11 ok  " + str(len(handlers)) + " exception handlers in /app/tool/cli.py, each raises; malformed policy_version_map.json: returncode "
          + str(entry["returncode"]) + ", " + entry["stderr"].splitlines()[-1][:160])

    shutil.rmtree(root)
    if out_digests() != before:
        raise SystemExit("self-check changed a file under /app/out")
    print("self-check left /app/out unchanged (" + str(len(before)) + " files) and removed its scratch corpora")


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-check"]:
        self_check_probes()
    else:
        main()
