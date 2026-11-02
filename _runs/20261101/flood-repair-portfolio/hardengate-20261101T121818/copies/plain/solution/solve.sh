#!/bin/bash
# Oracle dispatcher for flood-repair-portfolio.
set -euo pipefail

mkdir -p /app/out
cp /solution/solve.py /app/out/derive_report.py
python3 /app/out/derive_report.py /app/data /app/out

# Self-check stage: recompute the reported figures outside the program and compare.
python3 - /app/data /app/out <<'PY'
import configparser, csv, itertools, json, shutil, subprocess, sys, tempfile, time
from pathlib import Path

data, out = Path(sys.argv[1]), Path(sys.argv[2])
doc = {p.name: json.loads(p.read_text()) for p in out.glob("*.json")}
order = json.loads((data / "manifest.json").read_text())["files"]


def rows(name, delim=","):
    with open(data / name, newline="") as handle:
        return [r for r in csv.DictReader(handle, delimiter=delim)]


props, segs, perms = rows("proposals.csv"), rows("segment_codes.tsv", "\t"), rows("permits.csv")
excl = json.loads((data / "exclusions.json").read_text())
sites = {s["site"]: s for s in map(json.loads, (data / "sites.jsonl").read_text().splitlines())}
region = {r["site"]: r["region"] for r in rows("region_codes.csv")}
mode = {r["crew"]: r["mode"] for r in rows("crews.tsv", "\t")}
ini = configparser.ConfigParser()
ini.optionxform = str
ini.read(data / "benefits.ini")
rate = {k: int(v) for k, v in ini["segment_rate"].items()}
uplift = {k: int(v) for k, v in ini["risk_uplift"].items()}
numbered = {"proposals.csv": props, "segment_codes.tsv": segs, "permits.csv": perms, "exclusions.json": excl}
rounds = sorted({r["round"] for r in props})


def fault(rid):
    mine = {r["proposal"] for r in props if r["round"] == rid}
    named = mine | {r["site"] for r in props if r["round"] == rid}
    for name in order:
        seen = set()
        for number, r in enumerate(numbered.get(name, []), 1):
            if r["round"] != rid:
                continue
            if name == "proposals.csv":
                bad = None
                if r["proposal"] in seen:
                    bad = "DUPLICATE_PROPOSAL"
                elif not (r["households"].isascii() and r["households"].isdigit()
                          and 1 <= int(r["households"]) <= 60) or r["site"] not in sites \
                        or r["crew"] not in mode or r["risk_override"] not in ("", "A", "B", "C", "D"):
                    bad = "INVALID_INPUT"
                seen.add(r["proposal"])
            elif name == "exclusions.json":
                bad = ("UNKNOWN_PROPOSAL" if r["first"] not in named or r["second"] not in named
                       else "INVALID_INPUT" if r["first"] == r["second"] else None)
            else:
                field, allowed = ("segment", rate) if name == "segment_codes.tsv" else \
                    ("status", ("held", "applied", "withdrawn"))
                bad = ("UNKNOWN_PROPOSAL" if r["proposal"] not in mine
                       else "INVALID_INPUT" if r[field] not in allowed else None)
            if bad:
                return {"round": rid, "code": bad, "file": name, "row": number}
    return None


segment = {(r["round"], r["proposal"]): r["segment"] for r in segs}
benefit, where = {}, {}
for number, r in enumerate(props, 1):
    cls = r["risk_override"] or sites.get(r["site"], {}).get("risk_class")
    key = (r["round"], r["proposal"])
    try:
        benefit[key] = int(r["households"]) * (rate[segment[key]] + uplift[cls]) + sites[r["site"]]["premium"]
    except (KeyError, ValueError):
        continue
    where.setdefault(r["round"], []).append((number, r["proposal"]))
want = []
for rid in rounds:
    f = fault(rid)
    if f is None:
        low = [n for n, p in where[rid] if benefit[(rid, p)] < 1]
        if low:
            f = {"round": rid, "code": "NONPOSITIVE_BENEFIT", "file": "proposals.csv", "row": low[0]}
    if f:
        want.append(f)
assert doc["data_quality.json"]["rejected"] == want
print("check R3 ok")

rejected = {f["round"] for f in want}
summary = {r["round"]: r for r in doc["summary.json"]["rounds"]}
for rid in rounds:
    if rid not in rejected:
        assert summary[rid]["total_benefit"] == sum(benefit[(rid, p)] for p in summary[rid]["selected"])
for row in doc["policy_audit.json"]["rows"]:
    if row["kind"] == "VALUE" and row["status"] == "planned":
        assert row["benefit"] == benefit[(row["round"], row["proposal"])]
print("check R1 ok")

held = {}
for r in perms:
    if r["status"] != "withdrawn":
        held.setdefault((r["round"], r["permit"]), set()).add(r["proposal"])
site = {(r["round"], r["proposal"]): r["site"] for r in props}
crew = {(r["round"], r["proposal"]): r["crew"] for r in props}


def joins(rid, a, b):
    found = []
    if crew[(rid, a)] == crew[(rid, b)] and mode[crew[(rid, a)]] == "exclusive":
        found.append("crew")
    if any(k[0] == rid and {a, b} <= group for k, group in held.items()):
        found.append("permit")
    na, nb = {a, site[(rid, a)]}, {b, site[(rid, b)]}
    if any(e["round"] == rid and ((e["first"] in na and e["second"] in nb) or (e["first"] in nb and e["second"] in na))
           for e in excl):
        found.append("exclusion")
    return found


for row in doc["policy_audit.json"]["rows"]:
    if row["kind"] == "PAIR" and row["status"] == "planned":
        assert row["sources"] == joins(row["round"], row["first"], row["second"])
print("check R2 ok")

for kind, label, of in (("region", "R4", lambda rid, p: region[site[(rid, p)]]),
                        ("segment", "R5", lambda rid, p: segment[(rid, p)])):
    for path in sorted(out.glob(kind + "_*.json")):
        name = doc[path.name][kind]
        for entry in doc[path.name]["rounds"]:
            mine = [p for p in summary[entry["round"]]["selected"] if of(entry["round"], p) == name]
            assert entry["selected"] == mine
            assert entry["benefit"] == sum(benefit[(entry["round"], p)] for p in mine)
    print("check %s ok" % label)

for rid in rounds:
    ids = sorted(p for n, p in where.get(rid, []))
    if rid in rejected or len(ids) > 16:
        continue
    bad = {(a, b) for a, b in itertools.combinations(ids, 2) if joins(rid, a, b)}
    best = None
    for k in range(len(ids) + 1):
        for pick in itertools.combinations(ids, k):
            if any(pair in bad for pair in itertools.combinations(pick, 2)):
                continue
            key = (-sum(benefit[(rid, p)] for p in pick), list(pick))
            best = key if best is None or key < best else best
    assert summary[rid]["selected"] == best[1] and summary[rid]["total_benefit"] == -best[0]
print("check R6 ok")

first, raised = next((r, site[(r["round"], p)]) for r in doc["summary.json"]["rounds"] for p in r["selected"]
                     if sites[site[(r["round"], p)]]["premium"] <= 400)
with tempfile.TemporaryDirectory() as td:
    copy, moved = Path(td) / "data", Path(td) / "out"
    shutil.copytree(data, copy)
    text = (copy / "sites.jsonl").read_text().splitlines()
    for i, line in enumerate(text):
        entry = json.loads(line)
        if entry["site"] == raised:
            entry["premium"] += 400
            text[i] = json.dumps(entry)
    (copy / "sites.jsonl").write_text("\n".join(text) + "\n")
    subprocess.run([sys.executable, "-I", "-S", str(out / "derive_report.py"), str(copy), str(moved)], check=True)
    again = {r["round"]: r for r in json.loads((moved / "summary.json").read_text())["rounds"]}
    assert again[first["round"]]["total_benefit"] > first["total_benefit"]
print("check R7 ok")
with tempfile.TemporaryDirectory() as td:
    started = time.monotonic()
    subprocess.run([sys.executable, "-I", "-S", str(out / "derive_report.py"), str(data), td], check=True)
    seconds = time.monotonic() - started
assert seconds < 20
print("check R8 ok (%.2f s for the shipped book)" % seconds)
print("rejected rounds: " + ", ".join(f["round"] for f in want))
PY
