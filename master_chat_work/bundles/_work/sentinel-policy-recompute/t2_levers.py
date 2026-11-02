"""t2 cost table: the oracle tool with one or more rule readings wrong, plus the blind round-1 program, scored by local_score.py.

Usage: t2_levers.py <oracle_root> [label ...]   (oracle_root/app/out holds the oracle artifacts; labels pick variants)
Run with PYTHONPATH=<rewardkit stub> and a python that has pyarrow.
"""
import io
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
VARIANTS = {name: edits for name, edits in R.items()}
FIRST_WRITE = ("d2-none", "q1-sum", "q2-none", "q3-none", "q4-none", "q5-none", "u-none")
VARIANTS["first-write (" + " ".join(FIRST_WRITE) + ")"] = [edit for name in FIRST_WRITE for edit in R[name]]
VARIANTS["blind-r1"] = "blind"
if pick:
    VARIANTS = {name: edits for name, edits in VARIANTS.items() if name in pick or name.split(" ")[0] in pick}

src_zip = oracle / "app" / "out" / "tool.zip"
with zipfile.ZipFile(src_zip) as archive:
    members = {info.filename: (info, archive.read(info.filename)) for info in archive.infolist()}
base_cli = members["cli.py"][1].decode()


def score(item):
    index, (label, edits) = item
    if edits == "blind":
        payload = {name: (WORK / "blind_r1" / "app" / "tool" / name).read_bytes() for name in members}
    else:
        cli = base_cli
        for old, new in edits:
            assert cli.count(old) == 1, (label, old)
            cli = cli.replace(old, new)
        payload = {name: (cli.encode() if name == "cli.py" else data) for name, (info, data) in members.items()}
    root = Path("/var/folders/13/lkwk3zl54tvf9xz694_t4rvm0000gn/T/opencode") / ("spr_t2_" + str(index))
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


with ThreadPoolExecutor(4) as pool:
    for label, found, fails, crashes in pool.map(score, enumerate(VARIANTS.items())):
        print(f"| {label} | {found} | {', '.join(fails)} | crashes {len(crashes)} {crashes[:1]} |", flush=True)
