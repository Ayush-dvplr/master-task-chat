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
    ("m2", "convention 6 allowance (consumed by K042 rows only)", [
        ("        else:\n            remaining -= 1\n            if override[\"param_key\"] == param_key:",
         "        else:\n            if override[\"param_key\"] == param_key:\n                remaining -= 1\n            if override[\"param_key\"] == param_key:"),
    ]),
    ("m2b", "convention 6 allowance (never enforced)", [
        ("        elif remaining <= 0:\n", "        elif False:\n"),
    ]),
    ("m3", "convention 3 units (rev 1 seconds not x1000)", [
        ("        return value * 1000 if int(row[\"rev\"]) == 1 else value", "        return value"),
    ]),
    ("m3b", "convention 3 units (|v|<100 read as seconds)", [
        ("        return value * 1000 if int(row[\"rev\"]) == 1 else value", "        return value * 1000 if abs(value) < 100 else value"),
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
        ("            if override[\"param_key\"] == param_key:\n                applied.append(override)\n            continue",
         "            if override[\"param_key\"] == param_key and not applied:\n                applied.append(override)\n            continue"),
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
