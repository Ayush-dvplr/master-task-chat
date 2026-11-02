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

Subcommands: init, set, validate, plan, compile, export-report. The compile
command reads the evidence corpora under the data directory and writes the
derived security-posture artifacts. Standard library only.
"""
from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

# One row of the corpus table in config_contract.md:
# | <name>.<ext> | <format> | <operator> | <lo> | <hi> |
_TABLE_ROW = re.compile(
    r"^\|\s*(c\d{2}_[a-z0-9_]+)\.([a-z]+)\s*\|\s*([a-z]+)\s*\|\s*([a-z]+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*$"
)


def rules_of(data):
    return json.loads((Path(data) / "validation_rules.json").read_text(encoding="utf-8"))


def zones_of(data):
    return list(rules_of(data)["zones"])


def corpora(data):
    bounds = rules_of(data)["corpus_bounds"]
    table = (Path(data) / "config_contract.md").read_text(encoding="utf-8")
    out = []
    for line in table.splitlines():
        m = _TABLE_ROW.match(line)
        if m is None:
            continue
        name, ext, fmt, op, lo_txt, hi_txt = m.groups()
        lo, hi = bounds[name]
        if (int(lo_txt), int(hi_txt)) != (lo, hi):
            raise SystemExit("contract table and corpus_bounds disagree for " + name)
        out.append({"name": name, "ext": ext, "fmt": fmt, "op": op, "lo": lo, "hi": hi})
    if sorted(c["name"] for c in out) != sorted(bounds):
        raise SystemExit("contract table does not list every corpus in corpus_bounds")
    return sorted(out, key=lambda c: c["name"])


def canon_int(text):
    if not isinstance(text, str):
        return None
    try:
        n = int(text)
    except (TypeError, ValueError):
        return None
    return n if str(n) == text else None


def counted(zone, value, flag, lo, hi, zones):
    if zone not in zones or flag != "active":
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
        s = raw.strip()
        if not s or s[:1] == "#":
            continue
        cells = raw.split(sep)
        if len(cells) != 3:
            continue
        if tuple(cells) == ("zone", "value", "flag"):
            continue
        acc.append(tuple(cells))
    return acc


def rows_of(fmt, text):
    simple = {"csv": ",", "tsv": "\t", "psv": "|", "scsv": ";", "colon": ":",
              "caret": "^", "at": "@", "bang": "!", "tilde": "~"}
    if fmt in simple:
        return _rows_delimited(text, simple[fmt])
    if fmt == "dcolon":
        acc = []
        for raw in text.splitlines():
            s = raw.strip()
            if not s or s[:1] == "#":
                continue
            cells = raw.split("::")
            if len(cells) == 3:
                acc.append((cells[0], cells[1], cells[2]))
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
            acc.append((r.findtext("zone", "").strip(), r.findtext("value", "").strip(), r.findtext("flag", "").strip()))
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
            s = raw.strip()
            if not s or s[:1] == "#" or "=" not in s:
                continue
            key, _, val = s.partition("=")
            if "." not in key:
                continue
            pfx, _, field = key.partition(".")
            if pfx not in groups:
                groups[pfx] = {}
                order.append(pfx)
            groups[pfx][field] = val
        return [(groups[p].get("zone", ""), groups[p].get("value", ""), groups[p].get("flag", "")) for p in order]
    return []


def aggregate(op, rows, lo, hi, zones):
    vals = [n for (z, v, f) in rows if (n := counted(z, v, f, lo, hi, zones)) is not None]
    if op == "count":
        return len(vals)
    if not vals:
        return 0
    return {"max": max, "min": min, "sum": sum,
            "last": lambda xs: xs[-1], "first": lambda xs: xs[0]}[op](vals)


def _load(data, name):
    return json.loads((Path(data) / name).read_text(encoding="utf-8"))


def _text(data, name):
    return (Path(data) / name).read_text(encoding="utf-8")


def _journal(data):
    rows = []
    for line in _text(data, "change_journal.jsonl").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return sorted(rows, key=lambda o: o["seq"])


def journal_fault(entry, rules):
    integer_bounds = rules["bounds"]
    key = entry.get("key")
    if entry.get("env") not in rules["journal_envs"]:
        return "env"
    if key != "mode" and key not in integer_bounds:
        return "key"
    action = entry.get("op")
    if action == "unset":
        return None
    if action != "set":
        return "op"
    value = entry.get("value")
    if key == "mode":
        return None if isinstance(value, str) and value in rules["allowed_modes"] else "mode"
    if isinstance(value, bool) or not isinstance(value, int):
        return "type"
    lo, hi = integer_bounds[key]
    return None if lo <= value <= hi else "range"


def _rejected(data):
    rules = rules_of(data)
    return [entry["seq"] for entry in _journal(data) if journal_fault(entry, rules) is not None]


def _replay(data, doc, env):
    rules = rules_of(data)
    defaults = _load(data, "defaults.json")
    for entry in _journal(data):
        if entry["env"] != env or journal_fault(entry, rules) is not None:
            continue
        key = entry["key"]
        if entry["op"] == "unset":
            doc[key] = defaults["mode"] if key == "mode" else defaults["base_config"][key]
        else:
            doc[key] = entry["value"]
    return doc


def _rekey_mod(data):
    return base_config(data)["rekey_interval_s"] % 97


def _rejected_shift(data):
    return len(_rejected(data)) % 31


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


def all_aggregates(data):
    shift = _rekey_mod(data) + _rejected_shift(data)
    zones = zones_of(data)
    out = {}
    for c in corpora(data):
        hi = c["hi"] + shift
        out[c["name"]] = aggregate(c["op"], rows_of(c["fmt"], _text(data, f"{c['name']}.{c['ext']}")), c["lo"], hi, zones)
    return out


def zone_totals(data):
    shift = _rekey_mod(data) + _rejected_shift(data)
    zones = zones_of(data)
    tot = {z: 0 for z in zones}
    for c in corpora(data):
        hi = c["hi"] + shift
        for (z, v, f) in rows_of(c["fmt"], _text(data, f"{c['name']}.{c['ext']}")):
            if counted(z, v, f, c["lo"], hi, zones) is not None:
                tot[z] += 1
    return tot


def corpus_index(data):
    agg = all_aggregates(data)
    shift = _rekey_mod(data) + _rejected_shift(data)
    zones = zones_of(data)
    rows = []
    for c in corpora(data):
        parsed = rows_of(c["fmt"], _text(data, f"{c['name']}.{c['ext']}"))
        elig = sum(1 for (z, v, f) in parsed if counted(z, v, f, c["lo"], c["hi"] + shift, zones) is not None)
        rows.append({"name": c["name"], "format": c["fmt"], "op": c["op"],
                     "lo": c["lo"], "hi": c["hi"], "eligible_rows": elig, "value": agg[c["name"]]})
    return rows


def posture(agg):
    top_name = min(agg, key=lambda name: (-agg[name], name))
    return {"aggregate_total": sum(agg.values()), "corpus_count": len(agg),
            "max_corpus": top_name, "max_value": agg[top_name],
            "nonzero_corpora": sum(1 for v in agg.values() if v > 0)}


ARTIFACT_NAMES = [
    "config.json", "report.json", "tool.zip", "aggregates.json", "aggregates.csv",
    "aggregates.tsv", "aggregates.xml", "aggregates.ini", "aggregates.env",
    "aggregates.md", "aggregates.txt", "validation_report.json", "summary.json",
    "profile_core.json", "profile_edge.json", "profile_dmz.json", "profile_mgmt.json",
    "rejected_ops.json", "zone_totals.json", "corpus_index.json", "posture.json",
    "manifest.sha256",
]
MANIFEST_SET = sorted(n for n in ARTIFACT_NAMES if n.endswith(".json") and n != "report.json")


def _write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, sort_keys=True, indent=2, separators=(",", ": "), ensure_ascii=False)
    Path(path).write_text(text + "\n", encoding="utf-8")


def coerce(value):
    number = canon_int(value)
    if number is not None:
        return number
    if value in ("true", "false"):
        return value == "true"
    return value


def assert_flat(doc):
    bad = [k for k, v in doc.items() if isinstance(v, (dict, list))]
    if bad:
        raise SystemExit("configuration must be flat: " + ",".join(sorted(bad)))


def cmd_init(a):
    schema = _load_file(a.schema)
    doc = {"profile": schema["profile"], "producer": schema["producer"],
           "container": schema["container"], "checksum": schema["checksum"]}
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


def cmd_report(a):
    doc = _load_file(a.config)
    assert_flat(doc)
    commands = json.loads(a.commands)
    report = {"ok": True, "tool": "sealb-ctl", "config_path": a.config,
              "config_sha256": a.digest, "trailer": doc.get("trailer"), "commands": commands}
    _write_json(a.out, report)
    print("reported")


def cmd_compile(a):
    data, out = a.data, Path(a.out)
    agg = all_aggregates(data)
    _write_json(out / "aggregates.json", agg)
    items = sorted(agg.items())
    (out / "aggregates.csv").write_text("corpus,value\n" + "".join(f"{k},{v}\n" for k, v in items), encoding="utf-8")
    (out / "aggregates.tsv").write_text("corpus\tvalue\n" + "".join(f"{k}\t{v}\n" for k, v in items), encoding="utf-8")
    root = ET.Element("aggregates")
    for k, v in items:
        ET.SubElement(root, "corpus", {"name": k, "value": str(v)})
    (out / "aggregates.xml").write_text(ET.tostring(root, encoding="unicode") + "\n", encoding="utf-8")
    (out / "aggregates.ini").write_text("[aggregates]\n" + "".join(f"{k} = {v}\n" for k, v in items), encoding="utf-8")
    (out / "aggregates.env").write_text("".join(f"{k.upper()}={v}\n" for k, v in items), encoding="utf-8")
    (out / "aggregates.md").write_text("| corpus | value |\n| --- | --- |\n" + "".join(f"| {k} | {v} |\n" for k, v in items), encoding="utf-8")
    (out / "aggregates.txt").write_text("".join(f"{k} {v}\n" for k, v in items), encoding="utf-8")
    _write_json(out / "zone_totals.json", zone_totals(data))
    _write_json(out / "corpus_index.json", {"corpora": corpus_index(data), "count": len(corpora(data))})
    _write_json(out / "posture.json", posture(agg))
    rej = _rejected(data)
    _write_json(out / "rejected_ops.json", {"rejected": rej, "count": len(rej)})
    profiles = list(rules_of(data)["profiles"])
    for z in profiles:
        _write_json(out / f"profile_{z}.json", profile_config(data, z))
    main = _load_file(str(out / "config.json"))
    validation = {"ok": True, "checks": {
        "all_artifacts_present": all((out / n).exists() for n in ARTIFACT_NAMES if n not in {"validation_report.json", "summary.json", "manifest.sha256", "report.json", "tool.zip"}),
        "config_matches_policy": main == base_config(data),
        "config_scalar_flat": all(not isinstance(v, (dict, list)) for v in main.values()),
        "command_failures": [],
        "rejected_ops": rej,
        "profiles": {z: {"scalar_flat": True, "trailer": profile_config(data, z)["trailer"]} for z in profiles},
        "corpus_count": len(corpora(data)),
        "aggregate_total": sum(agg.values()),
    }}
    _write_json(out / "validation_report.json", validation)
    inputs = sorted(p.name for p in Path(data).iterdir() if p.is_file())
    _write_json(out / "summary.json", {
        "tool": "sealb-ctl", "profile_tag": main["profile"], "trailer": main["trailer"],
        "profiles": profiles, "artifacts": ARTIFACT_NAMES, "artifact_count": len(ARTIFACT_NAMES),
        "inputs": inputs, "input_count": len(inputs), "corpus_count": len(corpora(data)),
        "aggregate_total": sum(agg.values())})
    lines = [f"{hashlib.sha256((out / n).read_bytes()).hexdigest()}  {n}" for n in MANIFEST_SET if (out / n).exists()]
    (out / "manifest.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("compiled")


def _load_file(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    p = argparse.ArgumentParser(prog="sealb-ctl")
    sub = p.add_subparsers(dest="command", required=True)
    q = sub.add_parser("init"); q.add_argument("--schema", required=True); q.add_argument("--out", required=True); q.set_defaults(func=cmd_init)
    q = sub.add_parser("set"); q.add_argument("--config", required=True); q.add_argument("--key", required=True); q.add_argument("--value", required=True); q.set_defaults(func=cmd_set)
    q = sub.add_parser("validate"); q.add_argument("--schema", required=True); q.add_argument("--config", required=True); q.set_defaults(func=cmd_validate)
    q = sub.add_parser("plan"); q.add_argument("--data", required=True); q.add_argument("--env", required=True); q.set_defaults(func=cmd_plan)
    q = sub.add_parser("compile"); q.add_argument("--data", required=True); q.add_argument("--out", required=True); q.set_defaults(func=cmd_compile)
    q = sub.add_parser("export-report"); q.add_argument("--config", required=True); q.add_argument("--out", required=True); q.add_argument("--digest", required=True); q.add_argument("--commands", required=True); q.set_defaults(func=cmd_report)
    a = p.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
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


def package():
    archive = OUT / "tool.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as zf:
        for path in sorted(p for p in TOOL.rglob("*") if p.is_file()):
            info = zipfile.ZipInfo(path.relative_to(TOOL).as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            zf.writestr(info, path.read_bytes())


def main():
    extract()
    (TOOL / "cli.py").write_text(REPAIRED_CLI, encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    schema = str(TOOL / "schema.json")
    config = str(OUT / "config.json")
    cmds = []

    def call(*args):
        argv = ["python3", "cli.py", *args]
        r = subprocess.run([sys.executable, str(TOOL / "cli.py"), *args],
                           cwd=str(TOOL), text=True, capture_output=True, timeout=120)
        cmds.append({"argv": argv, "returncode": r.returncode, "stdout": r.stdout.strip()})
        print("$ " + " ".join(argv))
        if r.stdout.strip():
            print(r.stdout.strip())
        print(f"[returncode {r.returncode}]")
        if r.returncode != 0:
            raise SystemExit("CLI failed: " + " ".join(args) + "\n" + r.stderr)
        return r

    call("init", "--schema", schema, "--out", config)
    planned = json.loads(call("plan", "--data", str(DATA), "--env", "base").stdout)
    for key in sorted(planned):
        call("set", "--config", config, "--key", key, "--value", str(planned[key]))
    call("validate", "--schema", schema, "--config", config)
    call("compile", "--data", str(DATA), "--out", str(OUT))
    digest = hashlib.sha256(Path(config).read_bytes()).hexdigest()
    call("export-report", "--config", config, "--out", str(OUT / "report.json"),
         "--digest", digest, "--commands", json.dumps(cmds, sort_keys=True))
    package()

    rekey = planned["rekey_interval_s"]
    rejected = json.loads((OUT / "rejected_ops.json").read_text(encoding="utf-8"))["count"]
    print(f"[oracle] effective hi = hi + (R mod 97) + (J mod 31); R = finished-spine rekey_interval_s = {rekey}, "
          f"J = rejected journal ops = {rejected}, shift = {rekey % 97} + {rejected % 31} = {rekey % 97 + rejected % 31}. "
          "A misclassified journal op changes J (and R if it touches rekey_interval_s), which moves the bound "
          "and changes the aggregate of any corpus with eligible rows between the old and new bound.")
    print("[oracle] a corpus value counts only when str(int(value)) == value on the field text, which rejects the "
          "Devanagari (U+0966..U+096F), Arabic-Indic (U+0660..U+0669), Gujarati (U+0AE6..U+0AEF) and "
          "full-width (U+FF10..U+FF19) digits that int() accepts silently.")


if __name__ == "__main__":
    main()
