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

LOOP = "    for override in overrides:  # every tenant draws, in ascending seq\n"
REGION = "        region = regions[override[\"tenant\"]]\n        region_left.setdefault(region, int(allowance_rows[region]))\n"
UNIT = "        return value * 1000 if version_from[row[\"version\"]] < cutover else value"
REGION_REFUSE = "            reason = \"region-allowance-used-up\"\n"
ADMIT_REFUSE = "            reason = \"window-admits-used-up\"\n"
READINGS = {
    "N1 off: no region allowance": [
        ("        elif region_left[region] <= 0:\n", "        elif False:\n"),
    ],
    "N1 one-fact-wrong: allowance counted per tenant (region value)": [
        (REGION, "        region = override[\"tenant\"]\n        region_left.setdefault(region, int(allowance_rows[regions[region]]))\n"),
    ],
    "N1 one-fact-wrong: one counter for every row (resolved region value)": [
        (REGION, "        region = \"*\"\n        region_left.setdefault(region, int(allowance_rows[regions[tenant]]))\n"),
    ],
    "N2 off: timeout_ms_delta read raw": [
        (UNIT, "        return value"),
    ],
    "N2 one-fact-wrong: unit taken from rev": [
        (UNIT, "        return value * 1000 if int(row[\"rev\"]) == 1 else value"),
    ],
    "N3 off: no window admits": [
        ("        elif admit_left[override[\"window_id\"]] <= 0:\n", "        elif False:\n"),
    ],
    "N3 one-fact-wrong: admits drawn by the resolved tenant only": [
        ("            admit_left[override[\"window_id\"]] -= 1\n            drawn.append",
         "            admit_left[override[\"window_id\"]] -= 1 if override[\"tenant\"] == tenant else 0\n            drawn.append"),
    ],
    "draw_order: region refusal still draws an admit": [
        (REGION_REFUSE, REGION_REFUSE + "            admit_left[override[\"window_id\"]] -= 1\n"),
    ],
    "draw_order: window refusal still draws a region unit": [
        (ADMIT_REFUSE, ADMIT_REFUSE + "            region_left[region] -= 1\n"),
    ],
    "probe-1 reading: own-tenant rows only, region value, no admits": [
        (LOOP, "    for override in [row for row in overrides if row[\"tenant\"] == tenant]:\n"),
        ("        elif admit_left[override[\"window_id\"]] <= 0:\n", "        elif False:\n"),
    ],
    "L7 risk rounded once on the sum": [
        ("    contribution = sum(half_up_bps(term, mult_bps) for term in risk_terms)",
         "    contribution = half_up_bps(sum(risk_terms), mult_bps)"),
    ],
    "L1 controls trusted": [
        ("        ledger_controls[name] = \"ok\" if same else \"mismatch\"", "        ledger_controls[name] = \"ok\""),
    ],
    "row version ignored": [
        ("        elif override[\"version\"] != version:\n            reason = \"row-version-\" + override[\"version\"]\n", ""),
    ],
    "inclusive window end": [
        ("int(window[\"start\"]) <= instant < int(window[\"end\"])", "int(window[\"start\"]) <= instant <= int(window[\"end\"])"),
    ],
    'N4 off: timeout pool ignored': [('        if total <= pool:\n', '        if True:\n')],
    'N4 one-fact-wrong: fits test taken again on the second share': [('            added_ms[oid] = pool * d // held_total if oid in held else 0  # whole pool shared again', '            added_ms[oid] = (d if held_total <= pool else pool * d // held_total) if oid in held else 0')],
    'N4 one-fact-wrong: first share kept, pool not shared again': [('            added_ms[oid] = pool * d // held_total if oid in held else 0  # whole pool shared again', '            added_ms[oid] = pool * d // total if oid in held else 0')],
    'N4 one-fact-wrong: only the dropped milliseconds shared again': [('            added_ms[oid] = pool * d // held_total if oid in held else 0  # whole pool shared again', '            added_ms[oid] = pool * d // total + sum(pool * x // total for o, x in sharing.items() if o not in held) * d // held_total if oid in held else 0')],
    'N4 one-fact-wrong: no row dropped below 100': [('if pool * d // total >= 100}', '}')],
    "N4 one-fact-wrong: pool shared by the resolved key's rows only": [('for row in rows if delta_ms(row) > 0}', 'for row in rows if delta_ms(row) > 0 and row["param_key"] == param_key}')],
    "first passing override only": [
        ("                applied.append(override)\n", "                applied.append(override) if not applied else None\n"),
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
