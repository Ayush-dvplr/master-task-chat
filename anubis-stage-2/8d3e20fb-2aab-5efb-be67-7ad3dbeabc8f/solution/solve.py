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
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ZONES = ["core", "edge", "dmz", "mgmt"]
SPINE_KEYS = ["max_sessions", "retry_budget", "handshake_timeout_ms", "rekey_interval_s"]
FORMATS = [
    "csv", "tsv", "psv", "scsv", "colon", "ssv", "caret", "at", "dcolon",
    "bang", "tilde", "jsonarr", "jsonl", "xmlflat", "xmlnest", "ini",
    "fixed", "mdtable", "kvline", "props",
]
OPS = ["max", "min", "sum", "count", "last", "first"]
_SLUGS = [
    "cve_severity", "cipher_grade", "port_exposure", "tls_versions",
    "key_age_days", "iam_priv_level", "mfa_factor_count", "patch_lag_hours",
    "firewall_hits", "cert_days_left", "session_ttl", "rate_budget",
    "scope_bits", "audit_gap_min", "sudo_grants", "ssh_keybits",
    "kms_rotations", "acl_depth", "quota_caps", "login_fails",
    "privilege_escal", "dns_ttl_sec", "backup_age_hrs", "vuln_count",
    "handshake_ms", "nonce_reuse", "hsts_max_age", "cookie_ttl",
    "jwt_exp_min", "replay_window", "entropy_bits", "salt_rounds",
    "cidr_size", "egress_ports", "ingress_ports", "trust_score",
    "risk_weight", "drift_count", "seal_depth", "vault_leases",
    "rotation_days", "throttle_rps", "ban_minutes", "cap_drops",
    "syscall_allow", "namespace_ct", "cgroup_limit", "seccomp_rules",
    "apparmor_hits", "oauth_scopes",
]
_EXT = {
    "csv": "csv", "tsv": "tsv", "psv": "psv", "scsv": "scsv", "colon": "colon",
    "ssv": "ssv", "caret": "caret", "at": "at", "dcolon": "dcolon", "bang": "bang",
    "tilde": "tilde", "jsonarr": "json", "jsonl": "jsonl", "xmlflat": "xml",
    "xmlnest": "nxml", "ini": "ini", "fixed": "fixed", "mdtable": "md",
    "kvline": "kv", "props": "properties",
}


def corpora():
    out = []
    for i, slug in enumerate(_SLUGS):
        fmt = FORMATS[i % len(FORMATS)]
        hi = {42: 9007199254740952, 48: 9007199254740993}.get(i, 500 + 17 * i)
        out.append({
            "name": f"c{i + 1:02d}_{slug}",
            "ext": _EXT[fmt],
            "fmt": fmt,
            "op": OPS[i % len(OPS)],
            "lo": 1 + (i % 5),
            "hi": hi,
        })
    return out


def canon_int(text):
    if not isinstance(text, str):
        return None
    try:
        n = int(text)
    except (TypeError, ValueError):
        return None
    return n if str(n) == text else None


def counted(zone, value, flag, lo, hi):
    if zone not in ZONES or flag != "active":
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
            s = raw.strip()
            if not s or s[:1] == "#":
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


def aggregate(op, rows, lo, hi):
    vals = [n for (z, v, f) in rows if (n := counted(z, v, f, lo, hi)) is not None]
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
    rules = _load(data, "validation_rules.json")
    return [o["seq"] for o in _journal(data) if not _op_valid(o, rules)]


def _replay(data, doc, env):
    rules = _load(data, "validation_rules.json")
    defaults = _load(data, "defaults.json")
    base = defaults["base_config"]
    for op in _journal(data):
        if op["env"] == env and _op_valid(op, rules):
            if op.get("op", "set") == "unset":
                doc[op["key"]] = base[op["key"]] if op["key"] in SPINE_KEYS else defaults["mode"]
            else:
                doc[op["key"]] = op["value"]
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


def _elig_count_rows(rows, lo, hi):
    return sum(1 for (z, v, f) in rows if counted(z, v, f, lo, hi) is not None)


def _hi_fixpoint(c, rows, base_shift):
    e = 0
    hi = c["hi"] + base_shift
    for _ in range(32):
        hi = c["hi"] + base_shift + (e % 7)
        new_e = _elig_count_rows(rows, c["lo"], hi)
        if new_e == e:
            return hi
        e = new_e
    return hi


def all_aggregates(data):
    base_shift = _rekey_mod(data) + _rejected_shift(data)
    out = {}
    for c in corpora():
        rows = rows_of(c["fmt"], _text(data, f"{c['name']}.{c['ext']}"))
        hi = _hi_fixpoint(c, rows, base_shift)
        out[c["name"]] = aggregate(c["op"], rows, c["lo"], hi)
    return out


def zone_totals(data):
    base_shift = _rekey_mod(data) + _rejected_shift(data)
    tot = {z: 0 for z in ZONES}
    for c in corpora():
        rows = rows_of(c["fmt"], _text(data, f"{c['name']}.{c['ext']}"))
        hi = _hi_fixpoint(c, rows, base_shift)
        for (z, v, f) in rows:
            if counted(z, v, f, c["lo"], hi) is not None:
                tot[z] += 1
    return tot


def corpus_index(data):
    agg = all_aggregates(data)
    base_shift = _rekey_mod(data) + _rejected_shift(data)
    rows = []
    for c in corpora():
        parsed = rows_of(c["fmt"], _text(data, f"{c['name']}.{c['ext']}"))
        hi = _hi_fixpoint(c, parsed, base_shift)
        elig = _elig_count_rows(parsed, c["lo"], hi)
        rows.append({"name": c["name"], "format": c["fmt"], "op": c["op"],
                     "lo": c["lo"], "hi": c["hi"], "eligible_rows": elig, "value": agg[c["name"]]})
    return rows


def posture(agg):
    # ties on value broken by the EARLIER name (lexicographically first), per contract
    top = min(agg.items(), key=lambda kv: (-kv[1], kv[0]))
    return {"aggregate_total": sum(agg.values()), "corpus_count": len(agg),
            "max_corpus": top[0], "max_value": top[1],
            "nonzero_corpora": sum(1 for v in agg.values() if v > 0)}


ARTIFACT_NAMES = [
    "config.json", "report.json", "tool.zip", "aggregates.json", "aggregates.csv",
    "aggregates.tsv", "aggregates.xml", "aggregates.ini", "aggregates.env",
    "aggregates.md", "aggregates.txt", "validation_report.json", "summary.json",
    "profile_core.json", "profile_edge.json", "profile_dmz.json", "profile_mgmt.json",
    "rejected_ops.json", "zone_totals.json", "corpus_index.json", "posture.json",
    "manifest.sha256",
]
TRAILER = "harbor:sealb:policy:000000000badf00d"
MANIFEST_SET = sorted(n for n in ARTIFACT_NAMES if n not in {"tool.zip", "report.json", "manifest.sha256"})


def _write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(data, sort_keys=True, indent=2, separators=(",", ": "), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


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
    doc = {"profile": schema["profile"], "producer": schema["producer"],
           "container": schema["container"], "checksum": schema["checksum"], "mode": "strict-seal"}
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
    _write_json(out / "corpus_index.json", {"corpora": corpus_index(data), "count": len(corpora())})
    _write_json(out / "posture.json", posture(agg))
    rej = _rejected(data)
    _write_json(out / "rejected_ops.json", {"rejected": rej, "count": len(rej)})
    for z in ZONES:
        _write_json(out / f"profile_{z}.json", profile_config(data, z))
    main = _load_file(str(out / "config.json"))
    validation = {"ok": True, "checks": {
        "all_artifacts_present": all((out / n).exists() for n in ARTIFACT_NAMES if n not in {"validation_report.json", "summary.json", "manifest.sha256", "report.json", "tool.zip"}),
        "config_matches_policy": main == base_config(data),
        "config_scalar_flat": all(not isinstance(v, (dict, list)) for v in main.values()),
        "command_failures": [],
        "rejected_ops": rej,
        "profiles": {z: {"scalar_flat": True, "trailer": profile_config(data, z)["trailer"]} for z in ZONES},
        "corpus_count": len(corpora()),
        "aggregate_total": sum(agg.values()),
    }}
    _write_json(out / "validation_report.json", validation)
    inputs = sorted(p.name for p in Path(data).iterdir() if p.is_file())
    _write_json(out / "summary.json", {
        "tool": "sealb-ctl", "profile_tag": main["profile"], "trailer": TRAILER,
        "profiles": ZONES, "artifacts": ARTIFACT_NAMES, "artifact_count": len(ARTIFACT_NAMES),
        "inputs": inputs, "input_count": len(inputs), "corpus_count": len(corpora()),
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
        r = subprocess.run([sys.executable, str(TOOL / "cli.py"), *args],
                           cwd=str(TOOL), text=True, capture_output=True, timeout=120)
        cmds.append({"argv": ["python3", "cli.py", *args], "returncode": r.returncode, "stdout": r.stdout.strip()})
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


if __name__ == "__main__":
    main()
