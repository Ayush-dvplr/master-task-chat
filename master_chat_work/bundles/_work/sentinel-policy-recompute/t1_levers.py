"""t1 cost table: the oracle tool with one or more quiet-rule readings wrong, scored by local_score.py.

Usage: t1_levers.py <oracle_root>   (oracle_root/app/out holds the oracle artifacts)
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

FLOOR = "        timeout_ms = max(floor_ms, timeout_ms + added_ms[row[\"override_id\"]])\n"
R = {
    "q1-sum": [(FLOOR, "        timeout_ms = timeout_ms + added_ms[row[\"override_id\"]]\n")],
    "q1-final": [(FLOOR, "        timeout_ms = timeout_ms + added_ms[row[\"override_id\"]]\n    timeout_ms = max(floor_ms, timeout_ms)\n")],
    "q2-none": [("        if int(override[\"seq\"]) < last_seq[override[\"override_id\"]]:\n            reason = \"reissued-at-higher-seq\"\n        elif override[\"status\"]", "        if override[\"status\"]")],
    "q3-none": [("        names = [entry for entry in aliases if entry[\"alias\"] == row[\"param_key\"]]\n", "        names = []\n")],
    "q3-nospan": [("            if int(entry[\"start\"]) <= instant < int(entry[\"end\"]):\n", "            if True:\n")],
    "q4-none": [("        elif override.get(\"requires\") is not None and override[\"requires\"] not in drawn_ids:\n", "        elif False:\n")],
    "q4-anyorder": [("override[\"requires\"] not in drawn_ids:\n", "override[\"requires\"] not in {r[\"override_id\"] for r in overrides if r[\"status\"] == \"active\"}:\n")],
    "q5-none": [("            carried.append(row)\n", "            pass\n")],
    "q5-any": [("                and int(window[\"start\"]) <= instant < int(window[\"end\"])\n                and window[\"version\"] == version and row[\"version\"] == version\n", "")],
}
VARIANTS = {name: edits for name, edits in R.items()}
VARIANTS["first-write (q1-sum q2-none q3-none q4-none q5-none)"] = R["q1-sum"] + R["q2-none"] + R["q3-none"] + R["q4-none"] + R["q5-none"]

src_zip = oracle / "app" / "out" / "tool.zip"
with zipfile.ZipFile(src_zip) as archive:
    members = {info.filename: (info, archive.read(info.filename)) for info in archive.infolist()}
base_cli = members["cli.py"][1].decode()


def score(item):
    index, (label, edits) = item
    cli = base_cli
    for old, new in edits:
        assert cli.count(old) == 1, (label, old)
        cli = cli.replace(old, new)
    root = Path("/var/folders/13/lkwk3zl54tvf9xz694_t4rvm0000gn/T/opencode") / ("spr_t1_" + str(index))
    if root.exists():
        shutil.rmtree(root)
    shutil.copytree(oracle / "app" / "out", root / "app" / "out")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
        for name in sorted(members):
            info, data = members[name]
            archive.writestr(info, cli.encode() if name == "cli.py" else data)
    (root / "app" / "out" / "tool.zip").write_bytes(buffer.getvalue())
    out = subprocess.run([sys.executable, "-B", str(WORK / "local_score.py"), str(root)], capture_output=True, text=True)
    fails = [line.split()[0] for line in out.stdout.splitlines() if line.rstrip().endswith("fail") and not line.startswith("negative_")]
    found = [line for line in out.stdout.splitlines() if line.startswith("SCORE")]
    shutil.rmtree(root)
    return label, found[-1] if found else "SCORE ? " + out.stderr[-300:], fails


with ThreadPoolExecutor(1) as pool:
    for label, found, fails in pool.map(score, enumerate(VARIANTS.items())):
        print(f"| {label} | {found} | {', '.join(fails)} |", flush=True)
