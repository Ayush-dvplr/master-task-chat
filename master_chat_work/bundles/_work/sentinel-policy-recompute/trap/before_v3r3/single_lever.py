"""Single-lever table: the oracle tool with exactly one wrong reading, scored by local_score.py.

Usage: single_lever.py <oracle_root>   (oracle_root/app/out holds the oracle artifacts; env SPR_TESTS picks the tests file)
"""
import io
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

WORK = Path(__file__).resolve().parent
oracle = Path(sys.argv[1]).resolve()

READINGS = {
    "first-only (L3 off: one override)": [
        ("            if override[\"param_key\"] == param_key:\n                applied.append(override)\n            continue",
         "            if override[\"param_key\"] == param_key and not applied:\n                applied.append(override)\n            continue"),
    ],
    "no allowance (L3 off)": [
        ("        elif remaining <= 0:\n", "        elif False:\n"),
    ],
    "allowance per principal only (L3 partial)": [
        ("        else:\n            remaining -= 1\n            if override[\"param_key\"] == param_key:",
         "        else:\n            if override[\"param_key\"] == param_key:\n                remaining -= 1\n            if override[\"param_key\"] == param_key:"),
    ],
    "raw timeout, rev ignored (L2 off)": [
        ("        return value * 1000 if int(row[\"rev\"]) == 1 else value", "        return value"),
    ],
    "make-it-match |v|<100 is seconds (L2 repair)": [
        ("        return value * 1000 if int(row[\"rev\"]) == 1 else value", "        return value * 1000 if abs(value) < 100 else value"),
    ],
    "risk rounded once on the sum (L7 off)": [
        ("    contribution = sum(half_up_bps(term, mult_bps) for term in risk_terms)",
         "    contribution = half_up_bps(sum(risk_terms), mult_bps)"),
    ],
    "controls trusted, never recomputed (L1 off)": [
        ("        ledger_controls[name] = \"ok\" if same else \"mismatch\"", "        ledger_controls[name] = \"ok\""),
    ],
    "window-version only, row version ignored (VG partial)": [
        ("        elif override[\"version\"] != version:\n            reason = \"row-version-\" + override[\"version\"]\n", ""),
    ],
    "inclusive window end": [
        ("int(window[\"start\"]) <= instant < int(window[\"end\"])", "int(window[\"start\"]) <= instant <= int(window[\"end\"])"),
    ],
}

src_zip = oracle / "app" / "out" / "tool.zip"
with zipfile.ZipFile(src_zip) as archive:
    members = {info.filename: (info, archive.read(info.filename)) for info in archive.infolist()}
base_cli = members["cli.py"][1].decode()

rows = []
for label, edits in READINGS.items():
    cli = base_cli
    for old, new in edits:
        assert cli.count(old) == 1, (label, old)
        cli = cli.replace(old, new)
    root = Path("/var/folders/13/lkwk3zl54tvf9xz694_t4rvm0000gn/T/opencode") / ("spr_lever_" + str(len(rows)))
    if root.exists():
        shutil.rmtree(root)
    shutil.copytree(oracle / "app" / "out", root / "app" / "out")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
        for name in sorted(members):
            info, data = members[name]
            archive.writestr(info, cli.encode() if name == "cli.py" else data)
    (root / "app" / "out" / "tool.zip").write_bytes(buffer.getvalue())
    out = subprocess.run([sys.executable, str(WORK / "local_score.py"), str(root)], capture_output=True, text=True)
    fails = [line.split()[0] for line in out.stdout.splitlines() if line.rstrip().endswith("fail") and not line.startswith("negative_")]
    score = [line for line in out.stdout.splitlines() if line.startswith("SCORE")]
    rows.append((label, score[-1] if score else "SCORE ? " + out.stderr[-300:], fails))
    shutil.rmtree(root)

for label, score, fails in rows:
    print(f"| {label} | {score} | {', '.join(fails)} |")
