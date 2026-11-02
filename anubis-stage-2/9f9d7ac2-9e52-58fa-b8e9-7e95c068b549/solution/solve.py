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

REPAIRED_CLI = r'''#!/usr/bin/env python3
"""sealb-ctl: offline security policy compiler (repaired reference).

Subcommands: init, set, validate, plan, compile, package, export-report, seal.
Every policy value, zone, corpus format, operator and bound is read from the
data directory at run time. Standard library only.
"""
from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

SPINE_KEYS = ["max_sessions", "retry_budget", "handshake_timeout_ms", "rekey_interval_s"]
ARTIFACT_NAMES = [
    "config.json", "report.json", "tool.zip", "aggregates.json", "aggregates.csv",
    "aggregates.tsv", "aggregates.xml", "aggregates.ini", "aggregates.env",
    "aggregates.md", "aggregates.txt", "validation_report.json", "summary.json",
    "profile_core.json", "profile_edge.json", "profile_dmz.json", "profile_mgmt.json",
    "rejected_ops.json", "zone_totals.json", "corpus_index.json", "posture.json",
    "manifest.sha256",
]
SEALED_BY_SEAL = {"validation_report.json", "manifest.sha256"}
MANIFEST_SET = sorted(n for n in ARTIFACT_NAMES if n.endswith(".json") and n != "report.json")
ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)
ZIP_ATTR = 0o100644 << 16


def _load_file(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _load(data, name):
    return _load_file(Path(data) / name)


def _text(data, name):
    return (Path(data) / name).read_text(encoding="utf-8")


def _write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, sort_keys=True, indent=2, separators=(",", ": "), ensure_ascii=False)
    Path(path).write_bytes((text + "\n").encode("utf-8"))


def _rules(data):
    return _load(data, "validation_rules.json")


def zones(data):
    return list(_rules(data)["zones"])


def corpora(data):
    """The fifty corpora: format and operator from the contract table, bounds from the rules file."""
    bounds = _rules(data)["corpus_bounds"]
    out = []
    for line in _text(data, "config_contract.md").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 5 or "." not in cells[0] or cells[0] == "corpus":
            continue
        fname, fmt, op, lo, hi = cells
        name = fname.rsplit(".", 1)[0]
        if name not in bounds:
            continue
        if [int(lo), int(hi)] != list(bounds[name]):
            raise SystemExit("contract table and validation_rules.json disagree on " + name)
        out.append({"name": name, "file": fname, "fmt": fmt, "op": op,
                    "lo": int(bounds[name][0]), "hi": int(bounds[name][1])})
    if sorted(c["name"] for c in out) != sorted(bounds):
        raise SystemExit("corpus table does not cover every corpus in validation_rules.json")
    return sorted(out, key=lambda c: c["name"])


def canon_int(text):
    if not isinstance(text, str):
        return None
    try:
        n = int(text)
    except (TypeError, ValueError):
        return None
    return n if str(n) == text else None


def counted(zone, value, flag, lo, hi, active_zones):
    if zone not in active_zones or flag != "active":
        return None
    n = canon_int(value)
    if n is None or n < lo or n > hi:
        return None
    return n


def _jfield(x):
    if isinstance(x, bool):
        return "true" if x else "false"
    if x is None:
        return ""
    if isinstance(x, int):
        return str(x)
    if isinstance(x, float):
        return repr(x)
    return str(x)


def _rows_delimited(text, sep):
    acc = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip()[:1] == "#":
            continue
        cells = raw.split(sep)
        if len(cells) != 3:
            continue
        a, b, c = cells
        if (a, b, c) == ("zone", "value", "flag"):
            continue
        acc.append((a, b, c))
    return acc


def rows_of(fmt, text):
    simple = {"csv": ",", "tsv": "\t", "psv": "|", "scsv": ";", "colon": ":",
              "caret": "^", "at": "@", "bang": "!", "tilde": "~"}
    if fmt in simple:
        return _rows_delimited(text, simple[fmt])
    if fmt == "dcolon":
        acc = []
        for raw in text.splitlines():
            if not raw.strip() or raw.lstrip()[:1] == "#":
                continue
            cells = raw.split("::")
            if len(cells) == 3:
                acc.append(tuple(cells))
        return acc
    if fmt == "ssv":
        acc = []
        for raw in text.splitlines():
            s = raw.strip()
            if not s or s[:1] == "#":
                continue
            cells = s.split()
            if len(cells) == 3 and cells[0] != "zone":
                acc.append((cells[0], cells[1], cells[2]))
        return acc
    if fmt in ("jsonarr", "jsonl"):
        acc = []
        if fmt == "jsonarr":
            try:
                blob = json.loads(text)
            except ValueError:
                blob = []
            seq = blob if isinstance(blob, list) else []
        else:
            seq = []
            for raw in text.splitlines():
                s = raw.strip()
                if not s or s.startswith("//"):
                    continue
                try:
                    seq.append(json.loads(s))
                except ValueError:
                    pass
        for obj in seq:
            if isinstance(obj, dict):
                acc.append((_jfield(obj.get("zone")), _jfield(obj.get("value")), _jfield(obj.get("flag"))))
        return acc
    if fmt == "xmlflat":
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            return []
        return [(r.get("zone", ""), r.get("value", ""), r.get("flag", "")) for r in root.findall("row")]
    if fmt == "xmlnest":
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            return []
        acc = []
        for r in root.findall("row"):
            acc.append((r.findtext("zone", ""), r.findtext("value", ""), r.findtext("flag", "")))
        return acc
    if fmt == "ini":
        cp = configparser.ConfigParser()
        try:
            cp.read_string(text)
        except configparser.Error:
            return []
        return [(cp[s].get("zone", ""), cp[s].get("value", ""), cp[s].get("flag", "")) for s in cp.sections()]
    if fmt == "fixed":
        acc = []
        for raw in text.splitlines():
            if not raw.strip() or raw.lstrip()[:1] == "#" or raw[:10].strip() == "zone":
                continue
            acc.append((raw[0:10].strip(), raw[10:30].strip(), raw[30:].strip()))
        return acc
    if fmt == "mdtable":
        acc = []
        for raw in text.splitlines():
            s = raw.strip()
            if not s.startswith("|"):
                continue
            cells = [c.strip() for c in s.strip("|").split("|")]
            if len(cells) == 3 and cells[0] != "zone" and not set(cells[0]) <= set("-: "):
                acc.append((cells[0], cells[1], cells[2]))
        return acc
    if fmt == "kvline":
        acc = []
        for raw in text.splitlines():
            s = raw.strip()
            if not s or s[:1] == "#":
                continue
            tok = dict(p.split("=", 1) for p in s.split() if "=" in p)
            if {"zone", "value", "flag"} <= set(tok):
                acc.append((tok["zone"], tok["value"], tok["flag"]))
        return acc
    if fmt == "props":
        groups, order = {}, []
        for raw in text.splitlines():
            if not raw.strip() or raw.lstrip()[:1] == "#" or "=" not in raw:
                continue
            key, _, val = raw.partition("=")
            if "." not in key:
                continue
            pfx, _, field = key.partition(".")
            if pfx not in groups:
                groups[pfx] = {}
                order.append(pfx)
            groups[pfx][field] = val
        return [(groups[p].get("zone", ""), groups[p].get("value", ""), groups[p].get("flag", "")) for p in order]
    raise SystemExit("unknown wire format: " + fmt)


def aggregate(op, values):
    if op == "count":
        return len(values)
    if not values:
        return 0
    return {"max": max, "min": min, "sum": sum,
            "last": lambda xs: xs[-1], "first": lambda xs: xs[0]}[op](values)


def _journal(data):
    rows = []
    for line in _text(data, "change_journal.jsonl").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return sorted(rows, key=lambda o: o["seq"])


def _op_valid(op, rules):
    if op["env"] not in rules["journal_envs"]:
        return False
    kind = op.get("op", "set")
    if kind == "unset":
        return op["key"] in SPINE_KEYS or op["key"] == "mode"
    if kind != "set":
        return False
    if op["key"] == "mode":
        return op["value"] in rules["allowed_modes"]
    if op["key"] in SPINE_KEYS:
        lo, hi = rules["bounds"][op["key"]]
        return type(op["value"]) is int and lo <= op["value"] <= hi
    return False


def _rejected(data):
    rules = _rules(data)
    return [o["seq"] for o in _journal(data) if not _op_valid(o, rules)]


def _replay(data, doc, env):
    rules = _rules(data)
    defaults = _load(data, "defaults.json")
    base = defaults["base_config"]
    for op in _journal(data):
        if op["env"] == env and _op_valid(op, rules):
            if op.get("op", "set") == "unset":
                doc[op["key"]] = base[op["key"]] if op["key"] in SPINE_KEYS else defaults["mode"]
            else:
                doc[op["key"]] = op["value"]
    return doc


def base_config(data):
    defaults = _load(data, "defaults.json")
    schema = _load(data, "config_schema.json")
    doc = {
        "checksum": defaults["checksum"],
        "container": schema["container"],
        "mode": defaults["mode"],
        "producer": schema["producer"],
        "profile": schema["profile"],
        **defaults["base_config"],
    }
    return _replay(data, doc, "base")


def profile_config(data, zone):
    doc = dict(base_config(data))
    ov = _load(data, "env_overrides.json")[zone]
    doc["retry_budget"] += int(ov["retry_budget_delta"])
    doc["handshake_timeout_ms"] += int(ov["handshake_timeout_ms_delta"])
    doc["rekey_interval_s"] += int(ov["rekey_interval_s_delta"])
    doc["mode"] = ov["mode"]
    doc["profile"] = f"{doc['profile']}-{zone}"
    doc["trailer"] = f"{doc['trailer']}:{zone}"
    return _replay(data, doc, zone)


def effective_shift(data):
    """hi + (R mod 97) + (J mod 31): R from the finished spine, J the rejected-op count."""
    return base_config(data)["rekey_interval_s"] % 97 + len(_rejected(data)) % 31


def evaluate(data):
    """One pass over every corpus: counted values per corpus and counted rows per zone."""
    shift = effective_shift(data)
    active = zones(data)
    per_corpus, per_zone = {}, {z: 0 for z in active}
    for c in corpora(data):
        hi = c["hi"] + shift
        vals = []
        for (z, v, f) in rows_of(c["fmt"], _text(data, c["file"])):
            n = counted(z, v, f, c["lo"], hi, active)
            if n is not None:
                vals.append(n)
                per_zone[z] += 1
        per_corpus[c["name"]] = vals
    return per_corpus, per_zone


def posture(agg):
    top = max(sorted(agg.items()), key=lambda kv: kv[1])  # first maximum in sorted order = earlier name
    return {"aggregate_total": sum(agg.values()), "corpus_count": len(agg),
            "max_corpus": top[0], "max_value": top[1],
            "nonzero_corpora": sum(1 for v in agg.values() if v != 0)}


def _is_flat(doc):
    return isinstance(doc, dict) and all(not isinstance(v, (dict, list)) for v in doc.values())


def coerce(value):
    if value.isdecimal():
        return int(value)
    if value in ("true", "false"):
        return value == "true"
    return value


def assert_flat(doc):
    bad = [k for k, v in doc.items() if isinstance(v, (dict, list))]
    if bad:
        raise SystemExit("configuration must be flat: " + ",".join(sorted(bad)))


def cmd_init(a):
    schema = _load_file(a.schema)
    doc = {k: schema[k] for k in ("profile", "producer", "container", "checksum")}
    _write_json(a.out, doc)
    print("initialized")


def cmd_set(a):
    doc = _load_file(a.config)
    doc[a.key] = coerce(a.value)
    assert_flat(doc)
    _write_json(a.config, doc)
    print("set " + a.key)


def cmd_validate(a):
    schema = _load_file(a.schema)
    doc = _load_file(a.config)
    assert_flat(doc)
    required = schema["required_keys"]
    if isinstance(required, str):
        required = required.split(",")
    missing = [k for k in required if k not in doc]
    if missing:
        raise SystemExit("missing: " + ",".join(missing))
    print("ok")


def cmd_plan(a):
    doc = base_config(a.data) if a.env == "base" else profile_config(a.data, a.env)
    print(json.dumps(doc, sort_keys=True))


def cmd_compile(a):
    data, out = a.data, Path(a.out)
    per_corpus, per_zone = evaluate(data)
    table = corpora(data)
    agg = {c["name"]: aggregate(c["op"], per_corpus[c["name"]]) for c in table}
    items = sorted(agg.items())
    _write_json(out / "aggregates.json", agg)
    (out / "aggregates.csv").write_text("name,value\n" + "".join(f"{k},{v}\n" for k, v in items), encoding="utf-8")
    (out / "aggregates.tsv").write_text("name\tvalue\n" + "".join(f"{k}\t{v}\n" for k, v in items), encoding="utf-8")
    (out / "aggregates.xml").write_text("<rows>" + "".join(f'<row name="{k}" value="{v}"/>' for k, v in items) + "</rows>\n", encoding="utf-8")
    (out / "aggregates.ini").write_text("[aggregates]\n" + "".join(f"{k} = {v}\n" for k, v in items), encoding="utf-8")
    (out / "aggregates.env").write_text("".join(f"{k.upper()}={v}\n" for k, v in items), encoding="utf-8")
    (out / "aggregates.md").write_text("| name | value |\n| --- | --- |\n" + "".join(f"| {k} | {v} |\n" for k, v in items), encoding="utf-8")
    (out / "aggregates.txt").write_text("name value\n" + "".join(f"{k} {v}\n" for k, v in items), encoding="utf-8")
    _write_json(out / "zone_totals.json", per_zone)
    index = [{"name": c["name"], "format": c["fmt"], "op": c["op"], "lo": c["lo"], "hi": c["hi"],
              "eligible_rows": len(per_corpus[c["name"]]), "value": agg[c["name"]]} for c in table]
    _write_json(out / "corpus_index.json", {"corpora": index, "count": len(index)})
    _write_json(out / "posture.json", posture(agg))
    rej = _rejected(data)
    _write_json(out / "rejected_ops.json", {"rejected": rej, "count": len(rej)})
    for z in zones(data):
        _write_json(out / f"profile_{z}.json", profile_config(data, z))
    main = _load_file(out / "config.json")
    inputs = sorted(p.name for p in Path(data).iterdir() if p.is_file())
    _write_json(out / "summary.json", {
        "tool": "sealb-ctl", "profile_tag": main["profile"], "trailer": main["trailer"],
        "profiles": list(_rules(data)["profiles"]), "artifacts": sorted(ARTIFACT_NAMES),
        "artifact_count": len(ARTIFACT_NAMES), "inputs": inputs, "input_count": len(inputs),
        "corpus_count": len(table), "aggregate_total": sum(agg.values())})
    print("compiled")


def cmd_package(a):
    src, dest = Path(a.src).resolve(), Path(a.out)
    members = sorted(p for p in src.rglob("*")
                     if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc")
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_STORED) as zf:
        for path in members:
            info = zipfile.ZipInfo(path.relative_to(src).as_posix(), date_time=ZIP_EPOCH)
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = ZIP_ATTR
            zf.writestr(info, path.read_bytes())
    print("packaged " + str(len(members)))


def cmd_report(a):
    doc = _load_file(a.config)
    assert_flat(doc)
    digest = hashlib.sha256(Path(a.config).read_bytes()).hexdigest()
    if a.digest != digest:
        raise SystemExit("digest does not match " + a.config)
    commands = json.loads(sys.stdin.read() if a.commands == "-" else a.commands)
    report = {"ok": all(c.get("returncode") == 0 for c in commands), "tool": "sealb-ctl",
              "config_path": a.config, "config_sha256": digest, "trailer": doc.get("trailer"),
              "commands": commands}
    _write_json(a.out, report)
    print("reported")


def cmd_seal(a):
    """Check the delivered artifacts against each other and the data, then write
    validation_report.json and the manifest that covers it."""
    data, out = a.data, Path(a.out)
    present = {n: (out / n).is_file() and (out / n).stat().st_size > 0
               for n in ARTIFACT_NAMES if n not in SEALED_BY_SEAL}
    extras = sorted(p.name for p in out.iterdir() if p.name not in ARTIFACT_NAMES)
    main = _load_file(out / "config.json")
    schema = _load_file(a.schema)
    required = schema["required_keys"]
    if isinstance(required, str):
        required = required.split(",")
    profiles = {}
    for z in zones(data):
        prof = _load_file(out / f"profile_{z}.json")
        profiles[z] = {"scalar_flat": _is_flat(prof),
                       "trailer": prof.get("trailer") == f"{main.get('trailer')}:{z}"}
    report = _load_file(out / "report.json")
    rejected = _load_file(out / "rejected_ops.json")
    index = _load_file(out / "corpus_index.json")
    post = _load_file(out / "posture.json")
    summ = _load_file(out / "summary.json")
    agg = _load_file(out / "aggregates.json")
    total = sum(agg.values())
    checks = {
        "all_artifacts_present": all(present.values()),
        "config_matches_policy": main == base_config(data),
        "config_scalar_flat": _is_flat(main) and sorted(main) == sorted(required),
        "command_failures": sum(1 for c in report["commands"] if c.get("returncode") != 0),
        "rejected_ops": rejected["count"],
        "profiles": profiles,
        "corpus_count": index["count"],
        "aggregate_total": total,
    }
    integers_agree = (
        rejected["count"] == len(rejected["rejected"]) == len(_rejected(data))
        and index["count"] == len(index["corpora"]) == len(agg) == post["corpus_count"]
        == summ["corpus_count"] == len(corpora(data))
        and total == post["aggregate_total"] == summ["aggregate_total"]
    )
    booleans = [checks["all_artifacts_present"], checks["config_matches_policy"], checks["config_scalar_flat"]]
    booleans += [flag for z in profiles for flag in profiles[z].values()]
    ok = all(booleans) and checks["command_failures"] == 0 and integers_agree and not extras
    _write_json(out / "validation_report.json", {"ok": ok, "checks": checks})
    lines = [f"{hashlib.sha256((out / n).read_bytes()).hexdigest()}  {n}" for n in MANIFEST_SET]
    (out / "manifest.sha256").write_text("".join(line + "\n" for line in lines), encoding="utf-8")
    if not ok:
        raise SystemExit("seal failed: " + json.dumps({"checks": checks, "extras": extras}, sort_keys=True))
    print("sealed")


def main():
    p = argparse.ArgumentParser(prog="sealb-ctl")
    sub = p.add_subparsers(dest="command", required=True)
    q = sub.add_parser("init"); q.add_argument("--schema", required=True); q.add_argument("--out", required=True); q.set_defaults(func=cmd_init)
    q = sub.add_parser("set"); q.add_argument("--config", required=True); q.add_argument("--key", required=True); q.add_argument("--value", required=True); q.set_defaults(func=cmd_set)
    q = sub.add_parser("validate"); q.add_argument("--schema", required=True); q.add_argument("--config", required=True); q.set_defaults(func=cmd_validate)
    q = sub.add_parser("plan"); q.add_argument("--data", required=True); q.add_argument("--env", required=True); q.set_defaults(func=cmd_plan)
    q = sub.add_parser("compile"); q.add_argument("--data", required=True); q.add_argument("--out", required=True); q.set_defaults(func=cmd_compile)
    q = sub.add_parser("package"); q.add_argument("--src", required=True); q.add_argument("--out", required=True); q.set_defaults(func=cmd_package)
    q = sub.add_parser("export-report"); q.add_argument("--config", required=True); q.add_argument("--out", required=True); q.add_argument("--digest", required=True); q.add_argument("--commands", required=True, help="JSON list, or - to read it from stdin"); q.set_defaults(func=cmd_report)
    q = sub.add_parser("seal"); q.add_argument("--data", required=True); q.add_argument("--out", required=True); q.add_argument("--schema", required=True); q.set_defaults(func=cmd_seal)
    a = p.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
'''

REPAIRED_README = """# sealb-ctl

Offline security policy compiler, standard library only.

Usage:

    python3 cli.py init --schema schema.json --out config.json
    python3 cli.py set --config config.json --key max_sessions --value 100
    python3 cli.py validate --schema schema.json --config config.json
    python3 cli.py plan --data /app/data --env base
    python3 cli.py compile --data /app/data --out /app/out
    python3 cli.py package --src /app/tool --out /app/out/tool.zip
    python3 cli.py export-report --config config.json --out report.json --digest <sha256> --commands <json|->
    python3 cli.py seal --data /app/data --out /app/out --schema schema.json

`init` writes the schema identity keys. `set` stores one flat scalar.
`validate` rejects nested values first, then missing required keys.
`plan` prints the resolved policy for `base` or one zone. `compile` reads
config.json from the output directory and writes every derived artifact
except the report, the archive, the validation report and the manifest.
`package` rebuilds the tool archive deterministically. `export-report`
records the command transcript. `seal` cross-checks the delivered artifacts,
then writes validation_report.json and manifest.sha256.

`test_cli.py` holds unit tests for each component on a small synthetic
fixture: `python3 -B -m unittest -q test_cli` from this directory.
"""

TOOL_TESTS = r'''"""Unit tests for sealb-ctl on a small synthetic fixture (standard library only).

Run from the tool directory: python3 -B -m unittest -q test_cli
"""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cli  # noqa: E402

ZONES = ["core", "edge", "dmz", "mgmt"]
KEYS = ["profile", "producer", "container", "checksum", "mode",
        "max_sessions", "retry_budget", "handshake_timeout_ms", "rekey_interval_s", "trailer"]
JOURNAL = [
    {"seq": 3, "env": "base", "key": "max_sessions", "op": "unset"},
    {"seq": 1, "env": "base", "key": "max_sessions", "op": "set", "value": 40},
    {"seq": 2, "env": "base", "key": "rekey_interval_s", "op": "set", "value": 300},
    {"seq": 4, "env": "base", "key": "retry_budget", "op": "set", "value": "5"},
    {"seq": 5, "env": "base", "key": "retry_budget", "op": "set", "value": 99},
    {"seq": 6, "env": "lab", "key": "retry_budget", "op": "set", "value": 2},
    {"seq": 7, "env": "core", "key": "retry_budget", "op": "set", "value": 7},
    {"seq": 8, "env": "base", "key": "MODE", "op": "set", "value": "audit-seal"},
]
CSV_ROWS = ("zone,value,flag\ncore,12,active\ncore, 12,active\nedge,60,active\nedge,64,active\n"
            "core,012,active\ncore,5,ACTIVE\nlab,5,active\n# note\n\n")
PROPS_ROWS = ("r0001.zone=core\nr0001.value=7\nr0001.flag=active\n"
              "r0002.zone=edge\nr0002.value=8\nr0002.flag=active \n")


def make_fixture(root):
    root.mkdir(parents=True, exist_ok=True)
    files = {
        "validation_rules.json": {
            "profiles": ZONES, "zones": ZONES, "forbidden_keys": ["timestamp"],
            "allowed_modes": ["strict-seal", "audit-seal"], "journal_envs": ["base"] + ZONES,
            "bounds": {"max_sessions": [1, 100], "retry_budget": [0, 10],
                       "handshake_timeout_ms": [1, 1000], "rekey_interval_s": [1, 1000]},
            "corpus_bounds": {"k01_alpha": [1, 50], "k02_beta": [1, 50]}},
        "defaults.json": {
            "checksum": "crc32", "mode": "strict-seal", "producer": "p", "container": "c",
            "base_config": {"max_sessions": 10, "retry_budget": 1, "handshake_timeout_ms": 100,
                            "rekey_interval_s": 200, "trailer": "t:0"}},
        "config_schema.json": {"profile": "SYN", "producer": "p", "container": "c",
                               "required_keys": KEYS, "scalar_only": True, "checksum": "crc32"},
        "env_overrides.json": {z: {"mode": "audit-seal" if z == "core" else "strict-seal",
                                   "retry_budget_delta": 1 if z == "core" else 0,
                                   "handshake_timeout_ms_delta": 0, "rekey_interval_s_delta": 0}
                               for z in ZONES},
    }
    for name, obj in files.items():
        (root / name).write_text(json.dumps(obj), encoding="utf-8")
    (root / "change_journal.jsonl").write_text("".join(json.dumps(o) + "\n" for o in JOURNAL), encoding="utf-8")
    (root / "config_contract.md").write_text(
        "| corpus | format | operator | lo | hi |\n| --- | --- | --- | --- | --- |\n"
        "| k01_alpha.csv | csv | sum | 1 | 50 |\n| k02_beta.properties | props | count | 1 | 50 |\n",
        encoding="utf-8")
    (root / "k01_alpha.csv").write_text(CSV_ROWS, encoding="utf-8")
    (root / "k02_beta.properties").write_text(PROPS_ROWS, encoding="utf-8")
    return root


def run_cli(*args):
    return subprocess.run([sys.executable, "-B", str(HERE / "cli.py"), *args],
                          text=True, capture_output=True, timeout=120)


class Parsing(unittest.TestCase):
    def test_canonical_integers(self):
        for good in ("12", "0", "-5", "9007199254740993"):
            self.assertEqual(cli.canon_int(good), int(good))
        for bad in ("012", "+5", " 12", "12 ", "1_000", "0x1f", "12.0", "1e3", "80kb", "-0", "-00",
                    "\u0661\u0662", "\uff11\uff12", "\u0967", "\u0ae7", ""):
            self.assertIsNone(cli.canon_int(bad), bad)

    def test_row_eligibility(self):
        self.assertEqual(cli.counted("core", "12", "active", 1, 50, ZONES), 12)
        self.assertEqual(cli.counted("core", "50", "active", 1, 50, ZONES), 50)
        self.assertIsNone(cli.counted("core", "51", "active", 1, 50, ZONES))
        self.assertIsNone(cli.counted("core", "12", "ACTIVE", 1, 50, ZONES))
        self.assertIsNone(cli.counted("core", "12", "active ", 1, 50, ZONES))
        self.assertIsNone(cli.counted("lab", "12", "active", 1, 50, ZONES))
        self.assertIsNone(cli.counted("c\u043ere", "12", "active", 1, 50, ZONES))

    def test_wire_formats_keep_field_bytes(self):
        rows = cli.rows_of("csv", CSV_ROWS)
        self.assertEqual(len(rows), 7)
        self.assertIn(("core", " 12", "active"), rows)
        self.assertNotIn(("zone", "value", "flag"), rows)
        self.assertEqual(cli.rows_of("props", PROPS_ROWS), [("core", "7", "active"), ("edge", "8", "active ")])
        self.assertEqual(cli.rows_of("dcolon", "core::5::active\nedge:: 6::active\n"),
                         [("core", "5", "active"), ("edge", " 6", "active")])

    def test_operators_and_tie_break(self):
        self.assertEqual(cli.aggregate("sum", [1, 2]), 3)
        self.assertEqual(cli.aggregate("count", []), 0)
        self.assertEqual(cli.aggregate("max", []), 0)
        self.assertEqual(cli.aggregate("first", [4, 9]), 4)
        self.assertEqual(cli.aggregate("last", [4, 9]), 9)
        self.assertEqual(cli.posture({"b": 5, "a": 5})["max_corpus"], "a")


class Fixture(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.data = make_fixture(self.tmp / "data")
        self.schema = str(self.data / "config_schema.json")

    def tearDown(self):
        self._tmp.cleanup()

    def test_journal_replays_in_seq_order_with_unset(self):
        self.assertEqual(cli._rejected(self.data), [4, 5, 6, 8])
        spine = cli.base_config(self.data)
        self.assertEqual((spine["max_sessions"], spine["rekey_interval_s"], spine["retry_budget"]), (10, 300, 1))
        self.assertEqual(sorted(spine), sorted(KEYS))

    def test_zone_profile(self):
        prof = cli.profile_config(self.data, "core")
        self.assertEqual((prof["retry_budget"], prof["mode"], prof["profile"], prof["trailer"]),
                         (7, "audit-seal", "SYN-core", "t:0:core"))

    def test_effective_bound_and_reduction(self):
        self.assertEqual(cli.effective_shift(self.data), 300 % 97 + 4 % 31)
        per_corpus, per_zone = cli.evaluate(self.data)
        self.assertEqual(per_corpus, {"k01_alpha": [12, 60], "k02_beta": [7]})
        self.assertEqual(per_zone, {"core": 2, "edge": 1, "dmz": 0, "mgmt": 0})

    def test_config_commands(self):
        cfg = self.tmp / "config.json"
        self.assertEqual(run_cli("init", "--schema", self.schema, "--out", str(cfg)).returncode, 0)
        first = cfg.read_bytes()
        run_cli("init", "--schema", self.schema, "--out", str(cfg))
        self.assertEqual(cfg.read_bytes(), first)
        self.assertEqual(sorted(json.loads(first)), ["checksum", "container", "producer", "profile"])
        self.assertEqual(run_cli("set", "--config", str(cfg), "--key", "max_sessions", "--value", "40").returncode, 0)
        self.assertEqual(json.loads(cfg.read_text(encoding="utf-8"))["max_sessions"], 40)
        missing = run_cli("validate", "--schema", self.schema, "--config", str(cfg))
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("missing", missing.stderr)
        nested = self.tmp / "nested.json"
        nested.write_text(json.dumps({"profile": "X", "nested": {"deep": 1}}), encoding="utf-8")
        bad = run_cli("validate", "--schema", self.schema, "--config", str(nested))
        self.assertNotEqual(bad.returncode, 0)
        self.assertIn("flat", bad.stderr)

    def test_json_bytes(self):
        path = self.tmp / "x.json"
        cli._write_json(path, {"b": "\u00e9", "a": 1})
        self.assertEqual(path.read_bytes(), '{\n  "a": 1,\n  "b": "\u00e9"\n}\n'.encode("utf-8"))

    def test_package_is_deterministic(self):
        src = self.tmp / "src"
        src.mkdir()
        (src / "b.py").write_text("b\n", encoding="utf-8")
        (src / "a.md").write_text("a\n", encoding="utf-8")
        for name in ("one.zip", "two.zip"):
            self.assertEqual(run_cli("package", "--src", str(src), "--out", str(self.tmp / name)).returncode, 0)
        self.assertEqual((self.tmp / "one.zip").read_bytes(), (self.tmp / "two.zip").read_bytes())
        with zipfile.ZipFile(self.tmp / "one.zip") as zf:
            infos = zf.infolist()
        self.assertEqual([i.filename for i in infos], ["a.md", "b.py"])
        for i in infos:
            self.assertEqual((i.compress_type, i.date_time, i.external_attr),
                             (zipfile.ZIP_STORED, (1980, 1, 1, 0, 0, 0), 0o100644 << 16))

    def test_compile_then_seal(self):
        out = self.tmp / "out"
        out.mkdir()
        cli._write_json(out / "config.json", cli.base_config(self.data))
        self.assertEqual(run_cli("compile", "--data", str(self.data), "--out", str(out)).returncode, 0)
        self.assertEqual(json.loads((out / "aggregates.json").read_text(encoding="utf-8")),
                         {"k01_alpha": 72, "k02_beta": 1})
        self.assertEqual((out / "aggregates.csv").read_text(encoding="utf-8"),
                         "name,value\nk01_alpha,72\nk02_beta,1\n")
        src = self.tmp / "tool"
        src.mkdir()
        (src / "cli.py").write_text("pass\n", encoding="utf-8")
        self.assertEqual(run_cli("package", "--src", str(src), "--out", str(out / "tool.zip")).returncode, 0)
        digest = hashlib.sha256((out / "config.json").read_bytes()).hexdigest()
        cmds = json.dumps([{"argv": ["python3", "cli.py", "compile"], "returncode": 0, "stdout": "compiled"}])
        self.assertEqual(run_cli("export-report", "--config", str(out / "config.json"), "--out",
                                 str(out / "report.json"), "--digest", digest, "--commands", cmds).returncode, 0)
        seal = ("seal", "--data", str(self.data), "--out", str(out), "--schema", self.schema)
        self.assertEqual(run_cli(*seal).returncode, 0)
        self.assertIs(json.loads((out / "validation_report.json").read_text(encoding="utf-8"))["ok"], True)
        posture = json.loads((out / "posture.json").read_text(encoding="utf-8"))
        posture["aggregate_total"] += 1
        cli._write_json(out / "posture.json", posture)
        self.assertNotEqual(run_cli(*seal).returncode, 0)
        self.assertIs(json.loads((out / "validation_report.json").read_text(encoding="utf-8"))["ok"], False)


if __name__ == "__main__":
    unittest.main()
'''


def extract():
    if TOOL.exists():
        shutil.rmtree(TOOL)
    TOOL.mkdir(parents=True)
    with zipfile.ZipFile(SOURCE_ARCHIVE) as zf:
        for info in zf.infolist():
            rel = PurePosixPath(info.filename)
            mode = (info.external_attr >> 16) & 0xFFFF
            if rel.is_absolute() or ".." in rel.parts or stat.S_ISLNK(mode):
                raise SystemExit("unsafe member: " + info.filename)
            dest = (TOOL / Path(*rel.parts)).resolve()
            if not dest.is_relative_to(TOOL):
                raise SystemExit("escaping member: " + info.filename)
            if info.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(zf.read(info))


def main():
    extract()
    (TOOL / "cli.py").write_text(REPAIRED_CLI, encoding="utf-8")
    (TOOL / "README.md").write_text(REPAIRED_README, encoding="utf-8")
    (TOOL / "test_cli.py").write_text(TOOL_TESTS, encoding="utf-8")
    unit = subprocess.run([sys.executable, "-B", "-m", "unittest", "-q", "test_cli"],
                          cwd=str(TOOL), text=True, capture_output=True, timeout=600)
    if unit.returncode != 0:
        raise SystemExit("unit tests failed:\n" + unit.stdout + unit.stderr)
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    schema = str(TOOL / "schema.json")
    config = str(OUT / "config.json")
    cmds = []

    def call(*args, stdin=None):
        r = subprocess.run([sys.executable, str(TOOL / "cli.py"), *args], input=stdin,
                           cwd=str(TOOL), text=True, capture_output=True, timeout=300)
        cmds.append({"argv": ["python3", "cli.py", *args], "returncode": r.returncode, "stdout": r.stdout.strip()})
        if r.returncode != 0:
            raise SystemExit("CLI failed: " + " ".join(args) + "\n" + r.stderr)
        return r

    def export_report():
        digest = hashlib.sha256(Path(config).read_bytes()).hexdigest()
        call("export-report", "--config", config, "--out", str(OUT / "report.json"),
             "--digest", digest, "--commands", "-", stdin=json.dumps(cmds, sort_keys=True))

    call("init", "--schema", schema, "--out", config)
    planned = json.loads(call("plan", "--data", str(DATA), "--env", "base").stdout)
    for key in sorted(planned):
        call("set", "--config", config, "--key", key, "--value", str(planned[key]))
    call("validate", "--schema", schema, "--config", config)
    call("compile", "--data", str(DATA), "--out", str(OUT))
    call("package", "--src", str(TOOL), "--out", str(OUT / "tool.zip"))
    export_report()
    call("seal", "--data", str(DATA), "--out", str(OUT), "--schema", schema)
    export_report()


if __name__ == "__main__":
    main()
