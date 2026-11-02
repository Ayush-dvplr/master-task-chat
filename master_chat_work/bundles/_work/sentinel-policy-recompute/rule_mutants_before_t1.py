"""Rule coverage mutants: the oracle tool with one contract rule broken, scored by local_score.py.

Usage: rule_mutants.py <oracle_root>   (oracle_root/app/out holds the oracle artifacts; env SPR_TESTS picks the tests file)
m1-m7 recreate the QC v3 Gate 05 mutants (v3.md:244-254) as cli.py edits; the rest cover the remaining contract rules.
"""
import io
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

WORK = Path(__file__).resolve().parent
oracle = Path(sys.argv[1]).resolve()

MUTANTS = [
    ("m1", "per-term rounding", [
        ("    contribution = sum(half_up_bps(term, mult_bps) for term in risk_terms)",
         "    contribution = half_up_bps(sum(risk_terms), mult_bps)"),
    ]),
    ("m2", "N1 region allowance (counted per tenant)", [
        ("        region = regions[override[\"tenant\"]]\n        region_left.setdefault(region, int(allowance_rows[region]))\n",
         "        region = override[\"tenant\"]\n        region_left.setdefault(region, int(allowance_rows[regions[region]]))\n"),
    ]),
    ("m2b", "N1 region allowance (never enforced)", [
        ("        elif region_left[region] <= 0:\n", "        elif False:\n"),
    ]),
    ("m2c", "N1 region allowance (one counter for every row)", [
        ("        region = regions[override[\"tenant\"]]\n        region_left.setdefault(region, int(allowance_rows[region]))\n",
         "        region = \"*\"\n        region_left.setdefault(region, int(allowance_rows[regions[tenant]]))\n"),
    ]),
    ("m3", "N2 unit cutover (timeout_ms_delta read raw)", [
        ("        return value * 1000 if version_from[row[\"version\"]] < cutover else value", "        return value"),
    ]),
    ("m3b", "N2 unit cutover (unit taken from rev)", [
        ("        return value * 1000 if version_from[row[\"version\"]] < cutover else value",
         "        return value * 1000 if int(row[\"rev\"]) == 1 else value"),
    ]),
    ("m4", "half-open window (end inclusive)", [
        ("int(window[\"start\"]) <= instant < int(window[\"end\"])", "int(window[\"start\"]) <= instant <= int(window[\"end\"])"),
    ]),
    ("m5", "row version (row version check dropped)", [
        ("        elif override[\"version\"] != version:\n            reason = \"row-version-\" + override[\"version\"]\n", ""),
    ]),
    ("m6", "clamp order (clamp before multiply)", [
        ("    scaled_mr = half_up_bps(after_delta_mr, mult_bps)\n    max_records = min(cap, scaled_mr)",
         "    scaled_mr = half_up_bps(min(cap, after_delta_mr), mult_bps)\n    max_records = scaled_mr"),
    ]),
    ("m7", "status (status check dropped)", [
        ("        if override[\"status\"] != \"active\":", "        if False:"),
    ]),
    ("m8", "first-only override (one override per key)", [
        ("                applied.append(override)\n", "                applied.append(override) if not applied else None\n"),
    ]),
    ("m9", "effective version (latest version, instant ignored)", [
        ("        if int(row[\"effective_from\"]) <= instant:\n", "        if True:\n"),
    ]),
    ("m10", "tier = role_level (tier read one below role_level)", [
        ("    base_threshold = int(tiers[role_level][\"base_threshold\"])",
         "    base_threshold = int(tiers.get(role_level - 1, tiers[role_level])[\"base_threshold\"])"),
    ]),
    ("m11", "B9 vs B7 (latest bundle B9 read as active)", [
        ("    active_bundle = str(manifest[\"active_bundle_id\"])", "    active_bundle = str(manifest[\"latest_bundle_id\"])"),
        ("    if active_bundle not in ledger or ledger[active_bundle][\"status\"] != \"active\":",
         "    if active_bundle not in ledger:"),
    ]),
    ("m12", "client claimed version (v205 used as effective version)", [
        ("    client_claimed_version = corpus[\"entries\"][0][\"claimed_version\"]\n",
         "    client_claimed_version = corpus[\"entries\"][0][\"claimed_version\"]\n    version = client_claimed_version\n"),
    ]),
    ("m13", "controls (stored controls trusted)", [
        ("        ledger_controls[name] = \"ok\" if same else \"mismatch\"", "        ledger_controls[name] = \"ok\""),
    ]),
    ("m14", "window version (window version check dropped)", [
        ("        elif window[\"version\"] != version:\n            reason = \"window-version-\" + window[\"version\"]\n", ""),
    ]),
    ("m15", "N3 window admit (never enforced)", [
        ("        elif admit_left[override[\"window_id\"]] <= 0:\n", "        elif False:\n"),
    ]),
    ("m16", "N3 window admit (drawn by the resolved tenant only)", [
        ("            admit_left[override[\"window_id\"]] -= 1\n            drawn.append",
         "            admit_left[override[\"window_id\"]] -= 1 if override[\"tenant\"] == tenant else 0\n            drawn.append"),
    ]),
    ("m17", "draw_order (region refusal still draws an admit)", [
        ("            reason = \"region-allowance-used-up\"\n",
         "            reason = \"region-allowance-used-up\"\n            admit_left[override[\"window_id\"]] -= 1\n"),
    ]),
    ("m18", "draw_order (window refusal still draws a region unit)", [
        ("            reason = \"window-admits-used-up\"\n",
         "            reason = \"window-admits-used-up\"\n            region_left[region] -= 1\n"),
    ]),
    ('m19', 'N4 timeout pool ignored', [('        if total <= pool:\n', '        if True:\n')]),
    ('m20', 'N4 fits test taken again on the second share', [('            added_ms[oid] = pool * d // held_total if oid in held else 0  # whole pool shared again', '            added_ms[oid] = (d if held_total <= pool else pool * d // held_total) if oid in held else 0')]),
    ('m21', 'N4 first share kept, pool not shared again', [('            added_ms[oid] = pool * d // held_total if oid in held else 0  # whole pool shared again', '            added_ms[oid] = pool * d // total if oid in held else 0')]),
    ('m22', 'N4 only the dropped milliseconds shared again', [('            added_ms[oid] = pool * d // held_total if oid in held else 0  # whole pool shared again', '            added_ms[oid] = pool * d // total + sum(pool * x // total for o, x in sharing.items() if o not in held) * d // held_total if oid in held else 0')]),
    ('m23', 'N4 no row dropped below 100', [('if pool * d // total >= 100}', '}')]),
    ('m24', "N4 pool shared by the resolved key's rows only", [('for row in rows if delta_ms(row) > 0}', 'for row in rows if delta_ms(row) > 0 and row["param_key"] == param_key}')]),
]

src_zip = oracle / "app" / "out" / "tool.zip"
with zipfile.ZipFile(src_zip) as archive:
    members = {info.filename: (info, archive.read(info.filename)) for info in archive.infolist()}
base_cli = members["cli.py"][1].decode()

rows = []
for mid, rule, edits in MUTANTS:
    if len(sys.argv) > 2 and mid not in sys.argv[2:]:
        continue
    cli = base_cli
    for old, new in edits:
        assert cli.count(old) == 1, (mid, old)
        cli = cli.replace(old, new)
    root = Path("/var/folders/13/lkwk3zl54tvf9xz694_t4rvm0000gn/T/opencode") / ("spr_mut_" + mid)
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
    fails = [line.split()[0] + "(" + line.split("w=")[1].split()[0] + ")" for line in out.stdout.splitlines()
             if line.rstrip().endswith("fail") and not line.startswith("negative_")]
    score = [line for line in out.stdout.splitlines() if line.startswith("SCORE")]
    rows.append((mid, rule, score[-1] if score else "SCORE ? " + out.stderr[-300:], fails))
    shutil.rmtree(root)

for mid, rule, score, fails in rows:
    print(f"| {mid} | {rule} | {score} | {', '.join(fails)} |")
