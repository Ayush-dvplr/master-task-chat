"""Second, independent recomputation (ref_core, written from rating_contract.md) against solve.py.

Per-record diff with the first differing path, policy invariants, and override-removal probes
for plan_changes.log (the only correction mechanism in the data).
"""
import json
import pathlib
import subprocess
import sys
import tempfile
from decimal import Decimal

sys.dont_write_bytecode = True
W = pathlib.Path(__file__).resolve().parent
B = W.parent.parent / "metered-usage-rating-pipeline"
sys.path.insert(0, str(W))
from ref_core import REF_REGIONS, ref_compute  # noqa: E402
from gen_core import gen_month  # noqa: E402


def first_diff(a, b, path="$"):
    if type(a) is not type(b):
        return path
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                return f"{path}.{k}"
            d = first_diff(a[k], b[k], f"{path}.{k}")
            if d:
                return d
        return None
    if isinstance(a, list):
        if len(a) != len(b):
            return f"{path}[len]"
        for i, (x, y) in enumerate(zip(a, b)):
            d = first_diff(x, y, f"{path}[{i}]")
            if d:
                return d
        return None
    return None if a == b else path


def run_solve(files):
    d = pathlib.Path(tempfile.mkdtemp())
    (d / "in").mkdir()
    for k, v in files.items():
        (d / "in" / k).write_bytes(v)
    p = subprocess.run([sys.executable, "-B", str(B / "solution/solve.py"), "--input", str(d / "in"),
                        "--output", str(d / "o")], capture_output=True, text=True, check=False)
    assert p.returncode == 0, p.stderr
    out = {}
    for f in (d / "o").iterdir():
        if f.name.endswith(".jsonl"):
            out[f.name] = [json.loads(x) for x in f.read_text().splitlines() if x]
        elif f.name.endswith(".json"):
            out[f.name] = json.loads(f.read_text())
    return out


def start_plans(files):
    import csv
    rows = csv.DictReader(files["accounts.csv"].decode().splitlines())
    return {r["account_id"].strip().upper().replace("-", ""): r["plan"].strip() for r in rows}


def invariants(docs, files):
    rows = docs["normalized.jsonl"]
    dq = docs["data_quality.json"]
    start = start_plans(files)
    for r in REF_REGIONS:
        part = [x for x in rows if x["region"] == r]
        reg = docs[f"region_{r}.json"]
        base = sum(Decimal(x["charge"]) for x in part if start[x["account_id"]] == "committed")
        assert Decimal(reg["credit_base"]) == base
        assert Decimal(reg["credit_applied"]) == sum(Decimal(x["credit"]) for x in part)
        assert all(x["credit"] == "0.00" and x["true_up"] == "0.00"
                   for x in part if start[x["account_id"]] == "payg")
        pool, minimum = Decimal(reg["credit_pool"]), Decimal(reg["minimum"])
        counted = [x for x in part if start[x["account_id"]] == "committed"]
        if base <= pool:
            assert all(x["credit"] == x["charge"] for x in counted)
        else:
            held = [x for x in counted if Decimal(x["credit"]) >= Decimal("0.50")]
            assert all(x["credit"] == "0.00" for x in counted if x not in held)
            assert abs(sum(Decimal(x["credit"]) for x in held) - (pool if held else 0)) <= Decimal("0.01") * len(held)
        ups = sum(Decimal(x["true_up"]) for x in counted)
        assert Decimal(reg["true_up"]) == ups
        if base >= minimum:
            assert ups == 0
        else:
            assert abs(ups - (minimum - base)) <= Decimal("0.01") * len(counted)
        c = dq["collectors"][r]
        assert c["records"] == c["duplicates"] + c["quarantined"] + c["accepted"] and c["accepted"] == len(part)
        assert all(Decimal(x["net"]) == Decimal(x["charge"]) - Decimal(x["credit"]) + Decimal(x["true_up"])
                   for x in part)
    assert sum(dq["quarantine_reasons"].values()) == len(dq["quarantined_records"])
    pc = dq["plan_changes"]
    assert pc["lines"] == pc["applied"] + pc["unmatched"]


def compare(label, files):
    want = ref_compute(files)
    got = run_solve(files)
    bad = 0
    for name, doc in want.items():
        if name == "normalized.jsonl":
            gmap = {x["record_id"]: x for x in got.get(name, [])}
            for row in doc:
                d = first_diff(row, gmap.get(row["record_id"], {}))
                if d:
                    bad += 1
                    print(f"  {label} {name} {row['record_id']} differs at {d}")
                    break
        d = first_diff(doc, got.get(name))
        if d:
            bad += 1
            print(f"  {label} {name} differs at {d}")
    invariants(want, files)
    start = start_plans(files)
    moved_plan = sum(1 for x in want["normalized.jsonl"] if x["plan"] != start[x["account_id"]])
    grouped = sum(1 for r in files["accounts.csv"].decode().splitlines()[1:] if r.split(",")[3].strip())
    print(f"{label}: {len(want)} documents, {len(want['normalized.jsonl'])} lines, differing {bad}, "
          f"lines with plan in force != start plan {moved_plan}, accounts with parent {grouped}")
    assert bad == 0
    return want


def probe(label, files, edit):
    base = ref_compute(files)
    moved_files = dict(files)
    moved_files["plan_changes.log"] = edit(files["plan_changes.log"].decode()).encode()
    moved = run_solve(moved_files)
    n = sum(1 for a, b in zip(base["normalized.jsonl"], moved["normalized.jsonl"]) if a != b)
    docs = sorted(k for k in base if base[k] != moved.get(k))
    print(f"probe {label}: {n} lines moved, documents moved {len(docs)}")
    assert n > 0


def drop_all(text):
    return ""


def swap_same_ts(text):
    lines = text.splitlines()
    for i in range(len(lines) - 1):
        a, b = lines[i].split(), lines[i + 1].split()
        if a[0] == b[0] and a[2] == b[2]:
            lines[i], lines[i + 1] = lines[i + 1], lines[i]
    return "\n".join(lines) + "\n"


def main():
    data = B / "environment/data"
    shipped = {p.name: p.read_bytes() for p in data.iterdir() if p.name != "rating_contract.md"}
    compare("shipped", shipped)
    hidden = gen_month(4242, "2027-03", 1600, 1200, True, ref_compute)
    compare("hidden", hidden)
    for label, files in (("shipped", shipped), ("hidden", hidden)):
        probe(f"{label} plan_changes removed", files, drop_all)
        probe(f"{label} same-timestamp order swapped", files, swap_same_ts)
    print("CHECK_EXACT OK")


if __name__ == "__main__":
    main()
