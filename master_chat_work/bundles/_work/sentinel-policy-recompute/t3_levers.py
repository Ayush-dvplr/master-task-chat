"""t3 cost table: the oracle tool with one or more rule readings wrong (incl. other ledger_repair programs), plus the blind
round-1 and round-2 programs, scored by local_score.py.

Usage: t3_levers.py <oracle_root> [label ...]   (oracle_root/app/out holds the oracle artifacts; labels pick variants)
Run with PYTHONPATH=<rewardkit stub> and a python that has pyarrow.
"""
import io
import os
import shutil
import subprocess
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

WORK = Path(__file__).resolve().parent
oracle = Path(sys.argv[1]).resolve()
pick = sys.argv[2:]

FLOOR = "        timeout_ms = max(floor_ms, timeout_ms + added_ms[row[\"override_id\"]])\n"
STANDING = "    standing = [entry for entry in reports if entry[\"kind\"] == \"curve\" and not any(seq > int(entry[\"seq\"]) for seq in resets)]\n"
UNIQUE = "        divisor = fits[0] if len(fits) == 1 else None\n"
R = {
    "q1-sum": [(FLOOR, "        timeout_ms = timeout_ms + added_ms[row[\"override_id\"]]\n")],
    "q2-none": [("        if int(override[\"seq\"]) < last_seq[override[\"override_id\"]]:\n            reason = \"reissued-at-higher-seq\"\n        elif override[\"status\"]", "        if override[\"status\"]")],
    "q3-none": [("        names = [entry for entry in aliases if entry[\"alias\"] == row[\"param_key\"]]\n", "        names = []\n")],
    "q4-none": [("        elif override.get(\"requires\") is not None and override[\"requires\"] not in drawn_ids:\n", "        elif False:\n")],
    "q5-none": [("            carried.append(row)\n", "            pass\n")],
    "u-none": [("    if standing:\n", "    if False:\n")],
    "u-firstfit": [(UNIQUE, "        divisor = fits[0] if fits else None\n")],
    "u-firstreport": [(UNIQUE, "        divisor = fits[0] if fits else None\n"),
                      ("                if all(report_fits(report, trial) for report in standing)]\n",
                       "                if report_fits(standing[0], trial)]\n")],
    "d1-none": [(STANDING, "    standing = [entry for entry in reports if entry[\"kind\"] == \"curve\"]\n")],
    "d1-first": [(STANDING, "    standing = [entry for entry in reports if entry[\"kind\"] == \"curve\" and not (resets and resets[0] > int(entry[\"seq\"]))]\n")],
    "d2-none": [("        elif override[\"status\"] != \"active\" and int(override[\"seq\"]) not in reinstated_from:\n",
                 "        elif override[\"status\"] != \"active\":\n")],
    "d2-own": [("        return reinstated_from.get(int(row[\"seq\"]), row)\n", "        return row\n")],
    "d2-first": [("            latest_active[row[\"override_id\"]] = row\n", "            latest_active.setdefault(row[\"override_id\"], row)\n")],
}
ZERO = "            return [] if need_m == 0 and need_t == 0 else None\n"
BODY = {
    "r-greedy": """        pick = rows[:count]
        if sum(r[2] for r in pick) == need_m and sum(r[3] for r in pick) == need_t:
            return sorted(r[1] for r in pick)
        return None
""",
    "r-naive": """        best = None
        for combo in __import__("itertools").combinations(rows, count):
            if sum(r[2] for r in combo) == need_m and sum(r[3] for r in combo) == need_t:
                key = (sum(r[0] for r in combo), sorted(r[1] for r in combo))
                if best is None or key < best:
                    best = key
        return best[1] if best else None
""",
    "r-dp": """        layer = {(0, 0, 0): (0, ())}
        for r in sorted(rows, key=lambda r: r[1]):
            nxt = dict(layer)
            for (c, m, t), (cost, seqs) in layer.items():
                if c < count:
                    key, val = (c + 1, m + r[2], t + r[3]), (cost + r[0], seqs + (r[1],))
                    if key not in nxt or val < nxt[key]:
                        nxt[key] = val
            layer = nxt
        hit = layer.get((count, need_m, need_t))
        return list(hit[1]) if hit else None
""",
    "r-dp2": """        layer = {(0, 0): (0, ())}
        for r in sorted(rows, key=lambda r: r[1]):
            nxt = dict(layer)
            for (c, m), (cost, seqs) in layer.items():
                if c < count:
                    key, val = (c + 1, m + r[2]), (cost + r[0], seqs + (r[1],))
                    if key not in nxt or val < nxt[key]:
                        nxt[key] = val
            layer = nxt
        hit = layer.get((count, need_m))
        ms = {r[1]: r[3] for r in rows}
        return list(hit[1]) if hit and sum(ms[s] for s in hit[1]) == need_t else None
""",
    "r-mitm": """        ordered = sorted(rows, key=lambda r: r[1])
        half = len(ordered) // 2

        def table(part):
            out = {}
            for j in range(count + 1):
                for combo in __import__("itertools").combinations(part, j):
                    key = (j, sum(r[2] for r in combo), sum(r[3] for r in combo))
                    val = (sum(r[0] for r in combo), tuple(r[1] for r in combo))
                    if key not in out or val < out[key]:
                        out[key] = val
            return out
        left, right = table(ordered[:half]), table(ordered[half:])
        best = None
        for (j, m, t), (cost, seqs) in left.items():
            other = right.get((count - j, need_m - m, need_t - t))
            if other is not None:
                val = (cost + other[0], seqs + other[1])
                if best is None or val < best:
                    best = val
        return list(best[1]) if best else None
""",
}
for name, body in BODY.items():
    R[name] = [(ZERO, ZERO + body)]
R["r-none"] = [('    write_json(out / "ledger_repair.json", repair)\n', "")]
R["r-tie-last"] = [("        return min(found) if found else None\n", "        return max(found) if found else None\n")]
R["r-unit"] = [("        rows = sorted((abs(delta_ms(row)), int(row[\"seq\"])", "        rows = sorted((abs(int(row[\"timeout_ms_delta\"])), int(row[\"seq\"])")]
R["r-q2"] = [("\n                or int(row[\"seq\"]) < last_seq[row[\"override_id\"]])\n", ")\n")]
R["r-q5"] = [("or (row[\"status\"] == \"superseded\" and row.get(\"carry\") is None)", "or row[\"status\"] == \"superseded\"")]
R["r-d2"] = [("        if int(row[\"seq\"]) in kept:\n            return False\n", "")]
VARIANTS = {name: edits for name, edits in R.items()}
FIRST_WRITE = ("d2-none", "q1-sum", "q2-none", "q3-none", "q4-none", "q5-none", "u-none")
VARIANTS["first-write (" + " ".join(FIRST_WRITE) + ")"] = [edit for name in FIRST_WRITE for edit in R[name]]
VARIANTS["first-write-r (t2 first write + r-greedy)"] = [edit for name in FIRST_WRITE + ("r-greedy",) for edit in R[name]]
VARIANTS["blind-r1"] = "blind_r1"
VARIANTS["blind-r2"] = "blind_r2"
if pick:
    VARIANTS = {name: edits for name, edits in VARIANTS.items() if name in pick or name.split(" ")[0] in pick}

src_zip = oracle / "app" / "out" / "tool.zip"
with zipfile.ZipFile(src_zip) as archive:
    members = {info.filename: (info, archive.read(info.filename)) for info in archive.infolist()}
base_cli = members["cli.py"][1].decode()


def score(item):
    index, (label, edits) = item
    if isinstance(edits, str):
        payload = {name: (WORK / edits / "app" / "tool" / name).read_bytes() for name in members}
    else:
        cli = base_cli
        for old, new in edits:
            assert cli.count(old) == 1, (label, old)
            cli = cli.replace(old, new)
        payload = {name: (cli.encode() if name == "cli.py" else data) for name, (info, data) in members.items()}
    root = Path(os.environ.get("SPR_TMP", "/var/folders/13/lkwk3zl54tvf9xz694_t4rvm0000gn/T/opencode")) / ("spr_t3_" + str(index))
    if root.exists():
        shutil.rmtree(root)
    shutil.copytree(oracle / "app" / "out", root / "app" / "out")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
        for name in sorted(members):
            archive.writestr(members[name][0], payload[name])
    (root / "app" / "out" / "tool.zip").write_bytes(buffer.getvalue())
    out = subprocess.run([sys.executable, "-B", str(WORK / "local_score.py"), str(root)], capture_output=True, text=True)
    fails = [line.split()[0] for line in out.stdout.splitlines() if line.rstrip().endswith("fail") and not line.startswith("negative_")]
    crashes = [line[:160] for line in out.stdout.splitlines() if "resolve exited" in line]
    found = [line for line in out.stdout.splitlines() if line.startswith("SCORE")]
    shutil.rmtree(root)
    return label, found[-1] if found else "SCORE ? " + out.stderr[-300:], fails, crashes


with ThreadPoolExecutor(int(os.environ.get("SPR_THREADS", "4"))) as pool:
    for label, found, fails, crashes in pool.map(score, enumerate(VARIANTS.items())):
        print(f"| {label} | {found} | {', '.join(fails)} | crashes {len(crashes)} {crashes[:1]} |", flush=True)
