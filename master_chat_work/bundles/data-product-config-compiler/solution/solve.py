#!/usr/bin/env python3
"""Repair the dpcc tool, run it on the shipped release, deliver it, then self-check.

The self-check stage recomputes every graded figure straight from the contract,
without importing the tool, and prints one `check R<n> ok` line per conduct item.
"""
import csv
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

APP = Path(os.environ.get("APP_ROOT", "/app"))
DATA = APP / "data"
TOOL = APP / "tool"
OUT = APP / "out"
SOURCES = ("cli.py", "loaders.py", "resolve.py", "quota.py", "emit.py", "README.md")
PASSED = object()
DOCS = ("config.json", "profile_dev.json", "profile_prod.json", "validation_report.json", "summary.json")

STRICT_CHECK = '''def json_type_ok(spec, value):
    """True when a JSON-layer value has exactly the JSON type of its key."""
    kind = spec["type"]
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "boolean":
        return isinstance(value, bool)
    if kind in ("enum", "string"):
        return isinstance(value, str)
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def check_override(spec, value):'''

LARGEST_REMAINDER = '''    units = {pid: quota * weight // total for pid, weight in weights.items()}
    left = quota - sum(units.values())
    ranked = sorted(weights, key=lambda pid: (-(quota * weights[pid] % total), pid))
    for pid in ranked[:left]:
        units[pid] += 1
    return units


def capped_split(quota, weights, caps):
    """split_quota, then hand the units above each quota_cap out again among the products under their cap."""
    held = {pid: 0 for pid in weights}
    pool, taking = quota, dict(weights)
    while pool > 0 and taking:
        for pid, units in split_quota(pool, taking).items():
            held[pid] += units
        pool = 0
        for pid in taking:
            cap = caps.get(pid)
            if cap is not None and held[pid] > cap:
                pool += held[pid] - cap
                held[pid] = cap
        taking = {pid: weight for pid, weight in taking.items() if caps.get(pid) is None or held[pid] < caps[pid]}
    return held'''

OWNER_TEAM = '''    latest = None
    for row in owner_rows:
        if row["owner"] == owner and row["active_from"] <= day:
            if latest is None or row["active_from"] > latest["active_from"]:
                latest = row
    if latest is None or (latest["active_to"] != "" and latest["active_to"] < day):
        return None
    return latest["team"]
'''

# (file, wrong text, repaired text): each edit must match exactly once.
EDITS = [
    ("cli.py", "compile_release(args.data, when=args.date, out_dir=args.out)",
     "compile_release(args.data, args.date, args.out)"),
    ("cli.py", "    retired = loaders.load_deprecations(data_dir)\n",
     "    retired, retired_owners = loaders.load_deprecations(data_dir)\n"),
    ("cli.py", "resolve.classify(products, owner_rows, retired, day)",
     "resolve.classify(products, owner_rows, retired, retired_owners, day)"),
    ("loaders.py", '''        if raw.lower() in ("true", "false"):
            value = bool(raw)
        else:
            value = text_value(schema[key], raw)
''', "        value = text_value(schema[key], raw)\n        if value is PASSED:\n            continue\n"),
    ("loaders.py", "        return int(str(value).strip())\n", '''        text = str(value).strip()
        if not text or any(char not in "0123456789" for char in text):
            raise ValueError(value)
        return int(text)
'''),
    ("loaders.py", '''def text_value(spec, raw):
    """Read one text-layer value (yaml, ini, rules)."""
    return coerce(spec, _unquote(raw))
''', '''PASSED = object()


def text_value(spec, raw):
    """Read one text-layer value (yaml, ini, rules, env); PASSED when it does not read as the key's type."""
    try:
        return coerce(spec, _unquote(raw))
    except ValueError:
        return PASSED
'''),
    ("loaders.py", "        base[key] = text_value(schema[key], raw)\n", '''        value = text_value(schema[key], raw)
        if value is not PASSED:
            base[key] = value
'''),
    ("loaders.py", '''            current["lines"].append((key, text_value(schema[key], raw)))
''', '''            value = text_value(schema[key], raw)
            if value is not PASSED:
                current["lines"].append((key, value))
'''),
    ("loaders.py", "        rules.append((field, name, key, text_value(schema[key], raw)))\n", '''        value = text_value(schema[key], raw)
        if value is not PASSED:
            rules.append((field, name, key, value))
'''),
    ("loaders.py", '''    retired = {}
    for line in _content_lines(_read(data_dir, "deprecation.log")):''',
     '''    retired, owners = {}, {}
    for line in _content_lines(_read(data_dir, "deprecation.log")):'''),
    ("loaders.py", '''            pid = fields["product"]
            if pid not in retired or when < retired[pid]:
                retired[pid] = when
    return retired''', '''            pid = canon(fields["product"])
            if pid not in retired or when < retired[pid]:
                retired[pid] = when
        if "owner" in fields:
            when = parts[0][:10]
            name = fields["owner"]
            if name not in owners or when < owners[name]:
                owners[name] = when
    return retired, owners'''),
    ("resolve.py", "def classify(products, owner_rows, retired, day):",
     "def classify(products, owner_rows, retired, retired_owners, day):"),
    ("resolve.py", '''        owner_now = owner_team(product["owner"], by_owner.get(product["owner"], []), day)
''', '''        owner_now = owner_team(product["owner"], by_owner.get(product["owner"], []), day)
        if retired_owners.get(product["owner"], "9999-99-99") <= day:
            owner_now = None
'''),
    ("resolve.py", '''    for row in owner_rows:
        if row["owner"] != owner:
            continue
        if row["active_from"] <= day and (row["active_to"] == "" or row["active_to"] >= day):
            return row["team"]
    return None
''', OWNER_TEAM),
    ("resolve.py", "def check_override(spec, value):", STRICT_CHECK),
    ("resolve.py", '''    try:
        value = coerce(spec, value)
    except ValueError:
        return "type", None
''', '''    if not json_type_ok(spec, value):
        return "type", None
'''),
    ("resolve.py", "from loaders import coerce\n\n\n", ""),
    ("resolve.py", "    for record in product_records:",
     '    for record in sorted(product_records, key=lambda entry: entry["seq"]):'),
    ("resolve.py", "        elif value or isinstance(value, (bool, int)):", "        else:"),
    ("quota.py", "    return {pid: round(quota * weight / total) for pid, weight in weights.items()}",
     LARGEST_REMAINDER),
    ("cli.py", '''quota.split_quota(quotas["shared"], {pid: settings[pid]["weight"] for pid in active})''',
     '''quota.capped_split(quotas["shared"], {pid: settings[pid]["weight"] for pid in active},
                                {pid: settings[pid].get("quota_cap") for pid in active})'''),
    ("cli.py", '''quota.split_quota(quotas[env], {pid: env_settings[pid]["weight"] for pid in active})''',
     '''quota.capped_split(quotas[env], {pid: env_settings[pid]["weight"] for pid in active},
                                        {pid: env_settings[pid].get("quota_cap") for pid in active})'''),
    ("emit.py", "json.dumps(document, indent=2)", "json.dumps(document, indent=2, sort_keys=True)"),
]


def repair_tool():
    if TOOL.exists():
        shutil.rmtree(TOOL)
    TOOL.mkdir(parents=True)
    with zipfile.ZipFile(DATA / "tool.zip") as archive:
        for name in archive.namelist():
            assert "/" not in name and name in SOURCES, name
            (TOOL / name).write_bytes(archive.read(name))
    for name, wrong, right in EDITS:
        path = TOOL / name
        text = path.read_text()
        assert text.count(wrong) == 1, (name, wrong[:60])
        path.write_text(text.replace(wrong, right))


def run_tool(tool_dir, *args, cwd=None):
    command = [sys.executable, "-B", str(Path(tool_dir) / "cli.py"), *args]
    return subprocess.run(command, cwd=cwd or tempfile.gettempdir(), capture_output=True, text=True, timeout=600)


def deliver():
    day = json.loads((DATA / "release_manifest.json").read_text())["compile_date"]
    OUT.mkdir(parents=True, exist_ok=True)
    done = run_tool(TOOL, "compile", "--data", str(DATA), "--date", day, "--out", str(OUT))
    assert done.returncode == 0, done.stderr
    done = run_tool(TOOL, "export-report", "--out", str(OUT))
    assert done.returncode == 0, done.stderr
    with zipfile.ZipFile(OUT / "tool.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for name in SOURCES:
            archive.write(TOOL / name, name)


# ---------------------------------------------------------------- self-check
class Release:
    """Contract recompute, written separately from the tool."""

    def __init__(self, folder: Path, day=None):
        self.folder = folder
        manifest = self.json("release_manifest.json")
        self.name = manifest["release"]
        self.day = day or manifest["compile_date"]
        self.keys = self.json("schema_registry.json")["keys"]
        self.quotas = self.json("cluster_quota.json")

    def json(self, name):
        return json.loads((self.folder / name).read_text())

    def lines(self, name):
        for raw in (self.folder / name).read_text().splitlines():
            raw = raw.strip()
            if raw and raw[0] != "#":
                yield raw

    def typed(self, key, raw):
        raw = raw.strip()
        if raw[:1] == '"' and raw[-1:] == '"' and len(raw) > 1:
            raw = raw[1:-1]
        kind = self.keys[key]["type"]
        if kind == "integer":
            return int(raw) if re.fullmatch(r"[0-9]+", raw) else PASSED
        if kind == "boolean":
            return raw.lower() == "true" if raw.lower() in ("true", "false") else PASSED
        if kind == "list":
            return [piece.strip() for piece in raw.split(",")] if raw else []
        return raw

    def verdict(self, key, value):
        spec = self.keys.get(key)
        if spec is None:
            return "unknown_key"
        if value is None:
            return None if spec.get("optional") else "type"
        kind = spec["type"]
        good = {"integer": type(value) is int, "boolean": type(value) is bool,
                "enum": type(value) is str, "string": type(value) is str,
                "list": type(value) is list and all(type(x) is str for x in value)}[kind]
        if not good:
            return "type"
        if kind == "integer" and not spec["min"] <= value <= spec["max"]:
            return "bounds"
        if kind == "enum" and value not in spec["values"]:
            return "bounds"
        return None

    def build(self):
        def ident(text):
            return text.upper().replace("-", "")

        catalog, section = {}, None
        for raw in self.lines("products.ini"):
            found = re.fullmatch(r"\[product (.+)\]", raw)
            if found:
                section = catalog.setdefault(ident(found.group(1).strip()), {"own": [], "labels": []})
                continue
            key, value = (part.strip() for part in raw.split("=", 1))
            if key in ("owner", "tier"):
                section[key] = value
            elif key == "labels":
                section["labels"] = [x.strip() for x in value.split(",")] if value else []
            else:
                section["own"].append((key, self.typed(key, value)))
        dead_products, dead_owners = set(), set()
        for raw in self.lines("deprecation.log"):
            stamp, kind, field = (raw.split() + ["", ""])[:3]
            if kind != "RETIRE" or stamp[:10] > self.day:
                continue
            what, _, value = field.partition("=")
            if what == "product":
                dead_products.add(ident(value))
            elif what == "owner":
                dead_owners.add(value)
        latest = {}
        with open(self.folder / "owners.csv", newline="") as handle:
            for row in csv.DictReader(handle):
                seen = latest.get(row["owner"])
                if row["active_from"] <= self.day and (seen is None or row["active_from"] > seen["active_from"]):
                    latest[row["owner"]] = row
        teams = {owner: row["team"] for owner, row in latest.items()
                 if (row["active_to"] == "" or row["active_to"] >= self.day) and owner not in dead_owners}
        self.catalog = catalog
        self.state, self.team = {}, {}
        for pid, info in catalog.items():
            if pid in dead_products:
                self.state[pid], self.team[pid] = "retired", None
            elif info["owner"] in teams:
                self.state[pid], self.team[pid] = "active", teams[info["owner"]]
            else:
                self.state[pid], self.team[pid] = "orphaned", None
        self.live = sorted(p for p in catalog if self.state[p] == "active")
        self.compiled = {p for p in catalog if self.state[p] != "retired"}
        self.rejects, self.team_pairs = [], {}
        team_doc = self.json("team_overrides.json")
        for tname in sorted(team_doc):
            for key in sorted(team_doc[tname]):
                why = self.verdict(key, team_doc[tname][key])
                if why:
                    self.rejects.append({"source": "team_overrides", "team": tname, "key": key, "reason": why})
                else:
                    self.team_pairs.setdefault(tname, []).append((key, team_doc[tname][key]))
        rows = [json.loads(x) for x in (self.folder / "product_overrides.jsonl").read_text().splitlines() if x.strip()]
        self.own_pairs = {}
        for row in sorted(rows, key=lambda r: r["seq"]):
            pid = ident(row["product"])
            why = "unknown_product" if pid not in self.compiled else self.verdict(row["key"], row["value"])
            if why:
                self.rejects.append({"source": "product_overrides", "seq": row["seq"], "product": pid,
                                     "key": row["key"], "reason": why})
            else:
                self.own_pairs.setdefault(pid, []).append((row["key"], row["value"]))
        self.selectors = []
        for raw in self.lines("selectors.rules"):
            head, _, tail = raw.partition(" set ")
            field, _, label = head.split(" ", 1)[1].partition(":")
            key, _, value = tail.partition(" ")
            self.selectors.append((field, label, key, self.typed(key, value)))
        self.base = {}
        for raw in self.lines("base_layer.yaml"):
            key, _, value = raw.partition(":")
            value = self.typed(key.strip(), value)
            if value is not PASSED:
                self.base[key.strip()] = value

    def env(self, which):
        parts, current = {}, None
        for raw in self.lines(f"env_{which}.toml"):
            if raw.startswith("["):
                current = parts.setdefault(raw.strip("[]").strip(), [])
            else:
                key, value = (piece.strip() for piece in raw.split("=", 1))
                current.append((key, self.typed(key, value)))
        return parts

    def settings(self, pid, env_parts=None):
        info = self.catalog[pid]
        steps = []
        if env_parts:
            steps += env_parts.get("defaults", []) + env_parts.get(f"tier.{info['tier']}", [])
        for field, label, key, value in self.selectors:
            if {"team": self.team[pid] == label, "tier": info["tier"] == label,
                    "label": label in info["labels"]}[field]:
                steps.append((key, value))
        steps += self.team_pairs.get(self.team[pid], []) if self.team[pid] else []
        steps += info["own"] + self.own_pairs.get(pid, [])
        result = dict(self.base)
        for key, value in steps:
            if value is PASSED:
                continue
            if value is None:
                result.pop(key, None)
            else:
                result[key] = value
        return result

    @staticmethod
    def split(total_units, weights):
        whole = sum(weights.values())
        fraction = {p: total_units * w % whole for p, w in weights.items()}
        given = {p: total_units * w // whole for p, w in weights.items()}
        spare = total_units - sum(given.values())
        for p in sorted(weights, key=lambda p: (-fraction[p], p))[:spare]:
            given[p] += 1
        return given

    @classmethod
    def capped(cls, total_units, weights, caps):
        held = dict.fromkeys(weights, 0)
        pool, under = total_units, sorted(weights)
        while pool and under:
            for p, units in cls.split(pool, {p: weights[p] for p in under}).items():
                held[p] += units
            excess = {p: held[p] - caps[p] for p in under if caps.get(p) is not None and held[p] > caps[p]}
            for p, units in excess.items():
                held[p] -= units
            pool = sum(excess.values())
            under = [p for p in under if caps.get(p) is None or held[p] < caps[p]]
        return held


def check(label, condition, detail=""):
    if not condition:
        raise SystemExit(f"check {label} FAILED {detail}")
    print(f"check {label} ok")


def read_docs(folder: Path):
    return {name: json.loads((folder / name).read_text()) for name in DOCS}


def self_check(folder: Path, docs: dict, prefix=""):
    rel = Release(folder, docs["config.json"]["compile_date"])
    rel.build()
    conf = docs["config.json"]["products"]
    check(prefix + "R1", set(conf) == set(rel.catalog) and all(
        conf[p]["status"] == rel.state[p] and conf[p]["team"] == rel.team[p] for p in rel.catalog))
    resolved = {p: rel.settings(p) for p in sorted(rel.compiled)}
    check(prefix + "R4", all(conf[p]["settings"] == resolved.get(p) for p in conf))
    shares = {"config.json": rel.capped(rel.quotas["shared"], {p: resolved[p]["weight"] for p in rel.live},
                                        {p: resolved[p].get("quota_cap") for p in rel.live})}
    deploy_ok = True
    for which in ("dev", "prod"):
        parts = rel.env(which)
        envset = {p: rel.settings(p, parts) for p in rel.live}
        shares[f"profile_{which}.json"] = rel.capped(rel.quotas[which], {p: envset[p]["weight"] for p in rel.live},
                                                     {p: envset[p].get("quota_cap") for p in rel.live})
        listed = docs[f"profile_{which}.json"]["products"]
        deploy_ok &= sorted(listed) == rel.live and all(
            listed[p][k] == envset[p][k] for p in rel.live for k in ("alerts_enabled", "pii_scan", "replicas"))
    quota_ok = all(conf[p]["quota"] == shares["config.json"].get(p, 0) for p in conf)
    for which in ("dev", "prod"):
        listed = docs[f"profile_{which}.json"]["products"]
        quota_ok &= all(listed[p]["quota"] == shares[f"profile_{which}.json"][p] for p in rel.live)
    check(prefix + "R2", quota_ok)
    check(prefix + "R3", docs["validation_report.json"]["rejected_overrides"] == rel.rejects)
    check(prefix + "R5", deploy_ok)
    summary = docs["summary.json"]
    counts = {s: sum(1 for p in rel.catalog if rel.state[p] == s) for s in ("active", "orphaned", "retired")}
    by_team = {}
    for p in rel.live:
        by_team[rel.team[p]] = by_team.get(rel.team[p], 0) + 1
    sources = [r["source"] for r in rel.rejects]
    check(prefix + "R6", summary["status_counts"] == counts and summary["active_by_team"] == by_team
          and summary["rejected_overrides"] == {s: sources.count(s) for s in ("team_overrides", "product_overrides")}
          and summary["quota_total"] == {"config": sum(shares["config.json"].values()),
                                         "dev": sum(shares["profile_dev.json"].values()),
                                         "prod": sum(shares["profile_prod.json"].values())})
    return shares


def check_later_row(scratch, unpacked, docs, day):
    """R13: a later-started owners.csv row that ended before the compile date orphans the owner's products."""
    eve = (datetime.date.fromisoformat(day) - datetime.timedelta(days=1)).isoformat()
    with open(DATA / "owners.csv", newline="") as handle:
        rows = list(csv.DictReader(handle))
    starts = {}
    for row in rows:
        starts[row["owner"]] = max(starts.get(row["owner"], ""), row["active_from"])
    conf = docs["config.json"]["products"]
    owner = next(e["owner"] for p, e in sorted(conf.items()) if e["status"] == "active" and starts[e["owner"]] < eve)
    folder = scratch / "later-row"
    shutil.copytree(DATA, folder)
    with open(folder / "owners.csv", "a", newline="") as handle:
        handle.write(f"{owner},{conf_team_other(conf, owner)},{eve},{eve}\n")
    out = scratch / "later-row-out"
    done = run_tool(unpacked, "compile", "--data", str(folder), "--date", day, "--out", str(out), cwd="/")
    assert done.returncode == 0, done.stderr
    moved = read_docs(out)
    self_check(folder, moved, prefix="later-row ")
    check("R13", all(e["status"] == "orphaned" and e["team"] is None
                     for e in moved["config.json"]["products"].values() if e["owner"] == owner))


def conf_team_other(conf, owner):
    mine = next(e["team"] for e in conf.values() if e["owner"] == owner and e["team"])
    return next(e["team"] for _, e in sorted(conf.items()) if e["team"] and e["team"] != mine)


def check_passed_text(scratch, unpacked, day):
    """R14: an env value written with digits outside 0-9 is passed over and changes nothing."""
    folder = scratch / "odd-digit"
    shutil.copytree(DATA, folder)
    text = (folder / "env_dev.toml").read_text()
    cut = text.index("[tier.")
    (folder / "env_dev.toml").write_text(text[:cut] + "replicas = \uff13\n" + text[cut:])
    out = scratch / "odd-digit-out"
    done = run_tool(unpacked, "compile", "--data", str(folder), "--date", day, "--out", str(out), cwd="/")
    assert done.returncode == 0, done.stderr
    check("R14", (out / "profile_dev.json").read_bytes() == (OUT / "profile_dev.json").read_bytes())


def check_second_round_cap(unpacked):
    """R15: by hand, quota 8 over weights 1/5/6 with caps DP3=1, DP2=4 ends 3/4/1 (DP2's cap binds in round two)."""
    weights, caps = {"DP1": 1, "DP2": 5, "DP3": 6}, {"DP3": 1, "DP2": 4}
    probe = ("import json, sys; sys.path.insert(0, sys.argv[1]); import quota; "
             f"print(json.dumps(quota.capped_split(8, {weights!r}, {caps!r}), sort_keys=True))")
    done = subprocess.run([sys.executable, "-B", "-c", probe, str(unpacked)], capture_output=True, text=True)
    hand = {"DP1": 3, "DP2": 4, "DP3": 1}
    check("R15", done.returncode == 0 and json.loads(done.stdout) == hand and Release.capped(8, weights, caps) == hand,
          done.stderr)


def main():
    repair_tool()
    deliver()
    docs = read_docs(OUT)
    report = json.loads((OUT / "report.json").read_text())
    assert report["ok"] and all(report["documents"][n] == hashlib.sha256((OUT / n).read_bytes()).hexdigest()
                                for n in DOCS)
    before = self_check(DATA, docs)
    with tempfile.TemporaryDirectory() as scratch:
        scratch = Path(scratch)
        unpacked = scratch / "unpacked"
        with zipfile.ZipFile(OUT / "tool.zip") as archive:
            archive.extractall(unpacked)
        day = docs["config.json"]["compile_date"]
        again = scratch / "again"
        done = run_tool(unpacked, "compile", "--data", str(DATA), "--date", day, "--out", str(again), cwd="/")
        check("R10", done.returncode == 0 and all((again / n).read_bytes() == (OUT / n).read_bytes() for n in DOCS),
              done.stderr)
        altered = scratch / "altered-data"
        shutil.copytree(DATA, altered)
        quotas = json.loads((altered / "cluster_quota.json").read_text())
        quotas = {k: v + 997 for k, v in quotas.items()}
        (altered / "cluster_quota.json").write_text(json.dumps(quotas, indent=2) + "\n")
        live = sorted(p for p, e in docs["config.json"]["products"].items() if e["status"] == "active")
        with open(altered / "product_overrides.jsonl", "a") as handle:
            handle.write(json.dumps({"seq": 10 ** 9, "product": live[0].lower(), "key": "weight", "value": 50,
                                     "ticket": "CHG-SELF"}) + "\n")
        moved = scratch / "moved"
        done = run_tool(unpacked, "compile", "--data", str(altered), "--date", day, "--out", str(moved), cwd="/")
        assert done.returncode == 0, done.stderr
        after = self_check(altered, read_docs(moved), prefix="altered ")
        check("R7", after["config.json"][live[0]] != before["config.json"][live[0]]
              and read_docs(moved)["config.json"]["products"][live[0]]["settings"]["weight"] == 50)
        check_later_row(scratch, unpacked, docs, day)
        check_passed_text(scratch, unpacked, day)
        check_second_round_cap(unpacked)
    for path in sorted(OUT.iterdir()):
        print("wrote", path)


if __name__ == "__main__":
    main()
