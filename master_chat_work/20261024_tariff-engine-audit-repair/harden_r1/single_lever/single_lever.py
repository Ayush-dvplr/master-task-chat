"""Single-lever table: oracle program with exactly one habit slip, scored by the new tests.

python3 single_lever.py ORACLE_APP_ROOT WORK_DIR OUT_JSON
"""
import json, os, shutil, subprocess, sys, zipfile
from pathlib import Path

oracle, work, out_json = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
C, R, P = "src/tariff/core.py", "src/tariff/report.py", "src/tariff/parser.py"
SLIPS = {
    "N1_no_share": [(C, "    live = [line for line in lines if line[\"kind\"] == \"energy\"]\n",
                     "    live = []\n")],
    "N1_one_pass": [(C, "        live = [line for line in live if line[\"exact\"] > 0]\n", "        live = []\n")],
    "N1_two_passes": [(C, "    left = Fraction(allowance)\n", "    left = Fraction(allowance)\n    passes = 0\n"),
                      (C, "        live = [line for line in live if line[\"exact\"] > 0]\n",
                       "        passes += 1\n        live = [line for line in live if line[\"exact\"] > 0] if passes < 2 else []\n")],
    "N2_start_month": [(C, "    exact = Fraction(0)\n    day = first\n",
                        "    exact = Fraction(plan[\"standing_charge\"]) * ((last - first).days + 1) / calendar.monthrange(first.year, first.month)[1]\n    day = last + timedelta(days=1)\n")],
    "N2_period_length": [(R, "                lines.append(core.standing_line(key[1], plan, *span))\n",
                          "                line = core.standing_line(key[1], plan, *span)\n"
                          "                line[\"exact\"] = Fraction(plan[\"standing_charge\"]) * line[\"units\"] / ((period[\"end\"] - period[\"start\"]).days + 1)\n"
                          "                lines.append(line)\n"),
                         (R, "import ", "from fractions import Fraction\nimport ")],
    "N3_per_meter": [(R, "            position += quantity\n", "            position = 0\n")],
    "TR4_qty_coerce": [(P, "    if type(value) is int and value >= 0:\n        return value\n",
                        "    if isinstance(value, str) and value.strip().isdigit():\n        return int(value)\n"
                        "    if isinstance(value, float) and value.is_integer() and value >= 0:\n        return int(value)\n"
                        "    if type(value) is int and value >= 0:\n        return value\n")],
    "TR2_half_up": [(C, "(rest == Fraction(1, 2) and whole % 2)", "rest == Fraction(1, 2)")],
    "TR2_credit_rounded": [(C, "        total = money(Fraction(subtotal) * (1 - Fraction(plan[\"credit_rate\"])))\n",
                            "        total = subtotal - money(Fraction(subtotal) * Fraction(plan[\"credit_rate\"]))\n")],
}
results = {}
for name, edits in SLIPS.items():
    app = Path(f"/tmp/d62-slip-{name}")
    shutil.rmtree(app, ignore_errors=True)
    for sub in ("ci", "repo", "out"):
        shutil.copytree(oracle / sub, app / sub)
    with zipfile.ZipFile(oracle / "out/patched-repo.zip") as z:
        files = {i.filename: z.read(i) for i in z.infolist()}
    for path, old, new in edits:
        text = files[path].decode()
        assert text.count(old) >= 1, (name, old)
        files[path] = text.replace(old, new, 1).encode()
    with zipfile.ZipFile(app / "out/patched-repo.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for fname, data in files.items():
            z.writestr(fname, data)
    res = app / "checks.json"
    subprocess.run([sys.executable, str(work / "run_checks.py"), str(app), str(res)],
                   env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, capture_output=True, check=True)
    data = json.loads(res.read_text())
    lost = sorted(k for k, v in data["checks"].items() if v["weight"] > 0 and not v["pass"])
    results[name] = {"score": round(data["score"], 4), "earned": data["earned"],
                     "lost_points": data["positive"] - data["earned"], "lost": lost}
    print(f"{name:20s} score {data['score']:.4f} lost {data['positive'] - data['earned']:3d} {lost}", flush=True)
out_json.write_text(json.dumps(results, indent=1))
