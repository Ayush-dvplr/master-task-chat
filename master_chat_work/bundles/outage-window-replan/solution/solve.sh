#!/bin/bash
# Oracle: install the replan program, run it on the shipped inputs, then run the self-checks.
set -euo pipefail

mkdir -p /app/out
cp /solution/solve.py /app/out/derive_report.py
python3 /app/out/derive_report.py --data /app/data --out /app/out

work="$(mktemp -d)"
cat > "$work/selfcheck.py" <<'PYEOF'
import csv
import itertools
import json
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

PROGRAM = "/app/out/derive_report.py"
DATA = Path("/app/data")
OUT = Path("/app/out")
WORK = Path(sys.argv[1])
DOCS = ["policy_audit.json", "summary.json", "data_quality.json", "segment_commercial.json",
        "segment_public.json"] + [f"region_{r}.json" for r in ("North", "South", "West", "East")]
REGIONS = ("North", "South", "West", "East")
LOAD_FOR = {1: 300, 2: 500, 3: 800}


def run(data, out, cwd="/"):
    return subprocess.run([sys.executable, PROGRAM, "--data", str(data), "--out", str(out)],
                          cwd=cwd, capture_output=True, text=True, timeout=120)


def load(folder):
    return {name: json.loads((Path(folder) / name).read_text()) for name in DOCS}


def tiny(folder, last_day, factors, cap, reqs, plan):
    """A one-lane season (North, line) small enough to enumerate every season."""
    folder.mkdir(parents=True)
    with open(folder / "assets.jsonl", "w") as fh:
        for r in reqs:
            fh.write(json.dumps({"asset_id": r["asset_id"], "region": "North", "kind": "line", "crew_type": "line"}) + "\n")
    (folder / "requests.json").write_text(json.dumps({
        "season": {"first_day": 1, "last_day": last_day},
        "requests": [{k: r[k] for k in ("asset_id", "duration_days", "earliest_start", "latest_finish", "crews")} for r in reqs]}))
    (folder / "published_plan.json").write_text(json.dumps({"published_at": "2026-03-01T06:00:00Z", "plan": [
        {"asset_id": a, "status": "scheduled", "start": s} if s else {"asset_id": a, "status": "deferred"}
        for a, s in plan.items()]}))
    (folder / "network_constraints.json").write_text(json.dumps({"incompatible": [], "precedence": []}))
    (folder / "region_calendar.json").write_text(json.dumps({r: {"blackout_days": []} for r in REGIONS}))
    shutil.copy(DATA / "risk_policy.toml", folder / "risk_policy.toml")
    with open(folder / "customers.csv", "w") as fh:
        fh.write("customer_id,asset_id,class\n")
        n = 0
        for r in reqs:
            for _ in range(r["w"]):
                n += 1
                fh.write(f"Z{n:06d},{r['asset_id']},commercial\n")
    with open(folder / "load_forecast.tsv", "w") as fh:
        fh.write("region\tday\tperiod\tload_mw\n")
        for region in REGIONS:
            for day in range(1, last_day + 1):
                fh.write(f"{region}\t{day}\t1\t{LOAD_FOR[factors[day - 1]]}\n")
    with open(folder / "crew_roster.jsonl", "w") as fh:
        for day in range(1, last_day + 1):
            for k in range(cap):
                fh.write(json.dumps({"crew_id": f"Q{k}", "region": "North", "crew_type": "line", "day": day, "status": "on_duty"}) + "\n")
    (folder / "control_room.log").write_text("2026-03-02T00:00:00Z INFO HEARTBEAT seq=1\n")


def enumerate_best(last_day, factors, cap, reqs, plan):
    """Every season of the tiny lane scored by the objective order; returns the best key and start list."""
    late = last_day + 1
    options = [list(range(r["earliest_start"], r["latest_finish"] - r["duration_days"] + 2)) + [None] for r in reqs]
    best = None
    for starts in itertools.product(*options):
        use = [0] * (last_day + 2)
        for r, s in zip(reqs, starts):
            if s is not None:
                for d in range(s, s + r["duration_days"]):
                    use[d] += r["crews"]
        if max(use) > cap:
            continue
        risk = sum(r["w"] * (r["duration_days"] * 4 if s is None else sum(factors[d - 1] for d in range(s, s + r["duration_days"])))
                   for r, s in zip(reqs, starts))
        moved = sum((plan[r["asset_id"]] or None) != s for r, s in zip(reqs, starts))
        key = (risk, moved, [late if s is None else s for s in starts])
        if best is None or key < best[0]:
            best = (key, list(starts))
    return best


def witness(name, last_day, factors, cap, reqs, plan):
    folder = WORK / name
    tiny(folder / "data", last_day, factors, cap, reqs, plan)
    res = run(folder / "data", folder / "out")
    assert res.returncode == 0, res.stderr
    got = {r["asset_id"]: r["start"] for r in json.loads((folder / "out" / "policy_audit.json").read_text())["requests"]}
    key, starts = enumerate_best(last_day, factors, cap, reqs, plan)
    want = {r["asset_id"]: s for r, s in zip(reqs, starts)}
    assert got == want, (got, want)
    return key, want


checks = []

# Self-built lane where taking the heaviest request first is not optimal; enumeration of every season agrees.
reqs = [dict(asset_id="A90001", duration_days=2, earliest_start=1, latest_finish=2, crews=1, w=3),
        dict(asset_id="A90002", duration_days=2, earliest_start=1, latest_finish=6, crews=1, w=5)]
key, want = witness("greedy_witness", 6, [1, 1, 3, 3, 1, 1], 1, reqs, {"A90001": 1, "A90002": 1})
checks.append(("optimal_small_lane", f"enumerated best {key[:2]} starts {want}; heaviest-first would defer A90001"))

# Self-built tie: equal total risk either way round; the lower asset_id takes the earlier day.
reqs = [dict(asset_id="A90011", duration_days=1, earliest_start=3, latest_finish=4, crews=1, w=2),
        dict(asset_id="A90012", duration_days=1, earliest_start=3, latest_finish=4, crews=1, w=4)]
key, want = witness("tie_witness", 6, [1] * 6, 1, reqs, {"A90011": None, "A90012": None})
checks.append(("tie_order", f"tie broken as {want} with objective {key[:2]}"))

# One request's risk-days recomputed by hand from the shipped files.
audit = json.loads((OUT / "policy_audit.json").read_text())["requests"]
row = next(r for r in audit if r["status"] == "scheduled")
policy = tomllib.loads((DATA / "risk_policy.toml").read_text())
cw = policy["class_weight"]
with open(DATA / "customers.csv") as fh:
    weight = sum(cw[c["class"]] for c in csv.DictReader(fh) if c["asset_id"] == row["asset_id"])
peak = {}
with open(DATA / "load_forecast.tsv") as fh:
    for rec in csv.DictReader(fh, delimiter="\t"):
        if rec["region"] == row["region"]:
            peak[int(rec["day"])] = max(peak.get(int(rec["day"]), 0), int(rec["load_mw"]))
bands = sorted((b["min_mw"], b["factor"]) for b in policy["load_band"]["bands"])
hand = weight * sum([f for m, f in bands if m <= peak[d]][-1] for d in range(row["start"], row["end"] + 1))
assert hand == row["risk_days"], (hand, row)
checks.append(("one_request_by_hand", f"{row['asset_id']} weight {weight} days {row['start']}-{row['end']} risk_days {hand}"))

# Totals recomputed outside the program from the per-request rows.
docs = load(OUT)
summ = docs["summary.json"]
assert summ["risk_days"] == sum(r["risk_days"] for r in audit)
assert summ["moved"] == sum(r["moved"] for r in audit)
assert summ["risk_days"] == sum(docs[f"region_{r}.json"]["risk_days"] for r in REGIONS)
assert summ["risk_days"] == docs["segment_commercial.json"]["risk_days"] + docs["segment_public.json"]["risk_days"]
checks.append(("totals_recomputed", f"risk_days {summ['risk_days']} = rows = regions = segments; moved {summ['moved']}"))

# Altered copy: the same records in reversed row order give the same documents.
alt = WORK / "altered"
shutil.copytree(DATA, alt)
for name in ("customers.csv", "crew_roster.jsonl", "load_forecast.tsv"):
    lines = (alt / name).read_text().splitlines()
    head, body = (lines[:1], lines[1:]) if name.endswith(("csv", "tsv")) else ([], lines)
    (alt / name).write_text("\n".join(head + body[::-1]) + "\n")
res = run(alt, WORK / "altered_out")
assert res.returncode == 0 and load(WORK / "altered_out") == docs, res.stderr
checks.append(("altered_copy", "reversed row order in 3 files: 9 of 9 documents identical"))

# Relocated copy run from another working directory.
reloc = WORK / "elsewhere" / "deep" / "inputs"
shutil.copytree(DATA, reloc)
res = run(reloc, WORK / "reloc_out", cwd=str(WORK))
assert res.returncode == 0 and load(WORK / "reloc_out") == docs, res.stderr
checks.append(("relocated_copy", f"run from {WORK} on {reloc}: 9 of 9 documents identical"))

# Missing and malformed declared inputs stop the run with a message naming the file.
miss = WORK / "missing"
shutil.copytree(DATA, miss)
(miss / "customers.csv").unlink()
res = run(miss, WORK / "missing_out")
assert res.returncode != 0 and "customers.csv" in res.stderr, res
checks.append(("missing_input", f"exit {res.returncode}: {res.stderr.strip()}"))
bad = WORK / "malformed"
shutil.copytree(DATA, bad)
(bad / "requests.json").write_text((bad / "requests.json").read_text()[:200])
res = run(bad, WORK / "malformed_out")
assert res.returncode != 0 and "requests.json" in res.stderr, res
checks.append(("malformed_input", f"exit {res.returncode}: {res.stderr.strip()[:120]}"))

for cid, line in checks:
    print(f"check {cid} ok")
    print(f"  {line}")
PYEOF
python3 "$work/selfcheck.py" "$work"
rm -rf "$work"
