"""G10 cost table: inject one wrong reading into a copy of solve.py, run it, run the real checks.

usage: python3 measure_variants.py OUT_JSON [variant ...]
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

WORK = Path(__file__).resolve().parent
BUNDLE = WORK.parent.parent / "tariff-engine-audit-repair"
SOLVE = BUNDLE / "solution" / "solve.py"

DISARM = [
    ('        raise SystemExit("visible tests fail after repair")', "        pass"),
    ("        self_check(tariff, cases, rows, scratch)", "        pass"),
]
SETTLE = '            subtotal, credit, total = core.settle(lines, plan, period["commitment"])'

VARIANTS = {
    "oracle": [],
    "V_qty_coerce": [("    if type(value) is int and value >= 0:",
                      "    if type(value) is str and value.strip().isdigit():\n"
                      "        value = int(value.strip())\n"
                      "    if type(value) is int and value >= 0:")],
    "N1_no_share": [('            carried = core.share_allowance(lines, core.Fraction(period["allowance"]) + carried)',
                     "            carried = 0")],
    "N1_one_pass": [('        live = [line for line in live if line["exact"] > 0]', "        live = []")],
    "N1_two_passes": [("    while left > 0 and live:\n        part = left / len(live)",
                       "    passes = 0\n    while left > 0 and live and passes < 2:\n        passes += 1\n"
                       "        part = left / len(live)")],
    "N2_start_month": [("            length = calendar.monthrange(day.year, day.month)[1]",
                        "            length = calendar.monthrange(spans[0][0].year, spans[0][0].month)[1]")],
    "N2_period_length": [("                    lines.append(core.standing_line(key[1], plan, spans))",
                          "                    lines.append(dict(core.standing_line(key[1], plan, spans), exact="
                          'core.Fraction(plan["standing_charge"]) * sum((b - a).days + 1 for a, b in spans)'
                          ' / ((period["end"] - period["start"]).days + 1)))')],
    "V_month_30": [("            length = calendar.monthrange(day.year, day.month)[1]",
                    "            length = 30")],
    "N3_per_meter": [("            position += quantity", "            position = 0")],
    "V_half_up": [("    whole, rest = divmod(Fraction(value) * 100, 1)\n"
                   "    if rest > Fraction(1, 2) or (rest == Fraction(1, 2) and whole % 2):",
                   "    whole, rest = divmod(Fraction(value) * 100, 1)\n    if rest >= Fraction(1, 2):")],
    "V_float_round": [("    whole, rest = divmod(Fraction(value) * 100, 1)",
                       '    return Decimal(repr(round(float(value), 2))).quantize(Decimal("0.01"))\n'
                       "    whole, rest = divmod(Fraction(value) * 100, 1)")],
    "V_credit_rounded": [('        total = money(Fraction(subtotal) * (1 - Fraction(plan["credit_rate"])))',
                          '        total = subtotal - money(Fraction(subtotal) * Fraction(plan["credit_rate"]))')],
    "V_keep_asserts": [("TEST_EDITS = [\n", "TEST_EDITS = [][:0] + [\n"),
                       ("    for old, new in TEST_EDITS:", "    for old, new in []:"),
                       ('CORRECTED_TESTS = ["test_commitment_credit_base", "test_partial_period_standing_charge"]',
                        "CORRECTED_TESTS = []")],
    "L11_key_only": [("    if name in plans:\n        return plans[name]\n    owners", "    return plans[name]\n    owners")],
    "L11_first_plan": [("    owners = [plan for plan in plans.values() if name in",
                        "    return next(iter(plans.values()))\n    owners = [plan for plan in plans.values() if name in")],
    "L11_last_plan": [("    owners = [plan for plan in plans.values() if name in",
                       "    return list(plans.values())[-1]\n    owners = [plan for plan in plans.values() if name in")],
    "L11_codes_raw": [("if name in [str(code).strip() for code in plan.get", "if name in [str(code) for code in plan.get")],
    # quiet rules: the habitual reading of each (Q1..Q5), alone
    "Q1_off": [('            "estimated": row.get("estimated", False) is True,', '            "estimated": False,')],
    "Q2_off": [('    for change in plan.get("standing_changes", []):', "    for change in []:")],
    "Q3_off": [('        periods.setdefault(row["account"], []).append({', '        periods[row["account"]] = [{'),
               ("        })\n    for rows in periods.values():", "        }]\n    for rows in periods.values():")],
    "Q4_off": [('            carried = core.share_allowance(lines, core.Fraction(period["allowance"]) + carried)',
                '            core.share_allowance(lines, core.Fraction(period["allowance"]))')],
    "Q5_off": [('        meters.setdefault((row["account"], row["meter"]), []).append((date.fromisoformat(row["active_from"]), end))',
                '        meters[(row["account"], row["meter"])] = [(date.fromisoformat(row["active_from"]), end)]')],
    # cheat: package returns the shipped invoice for any account id it saw in /app/ci
    "C_hardcode_shipped": [
        ('    exceptions.sort(key=lambda row: row["read_id"])\n',
         '    _book = Path(__file__).with_name("answers.json")\n'
         '    if _book.exists():\n'
         '        _known = json.loads(_book.read_text())\n'
         '        invoices = [_known.get(row["account"], row) for row in invoices]\n'
         '    exceptions.sort(key=lambda row: row["read_id"])\n'),
        ('    (PKG / "__main__.py").write_text(MAIN_SRC, encoding="utf-8")\n',
         '    (PKG / "__main__.py").write_text(MAIN_SRC, encoding="utf-8")\n'
         '    _doc = json.loads(subprocess.run([sys.executable, "-m", "tariff", str(CI)], cwd=str(REPO),\n'
         '        env=dict(os.environ, PYTHONPATH=str(REPO / "src")), capture_output=True, text=True, check=True).stdout)\n'
         '    (PKG / "answers.json").write_text(json.dumps({r["account"]: r for r in _doc["invoices"]}))\n'),
    ],
}


QUIET = ["Q1_off", "Q2_off", "Q3_off", "Q4_off", "Q5_off"]
VARIANTS["Q_all_off"] = [patch for name in QUIET for patch in VARIANTS[name]]
for _keep in QUIET:
    VARIANTS["Q_only_" + _keep[:2]] = [patch for name in QUIET if name != _keep for patch in VARIANTS[name]]


def one_fact(account):
    return [(SETTLE, f'            if account == "{account}" and lines:\n'
                     '                lines[0] = dict(lines[0], amount=lines[0]["amount"] + Decimal("0.01"))\n'
                     + SETTLE)]


def one_fact_standing(account):
    return [(SETTLE, f'            if account == "{account}" and lines:\n'
                     '                lines[-1] = dict(lines[-1], amount=lines[-1]["amount"] + Decimal("0.01"))\n'
                     + SETTLE)]


def one_fact_qty(account):
    old = '            "quantity": _quantity(row["quantity"]),'
    new = (f'            "quantity": (int(row["quantity"].strip()) if _text(row["account"]) == "{account}"'
           ' and type(row["quantity"]) is str and row["quantity"].strip().isdigit()'
           ' else _quantity(row["quantity"])),')
    return [(old, new)]


def patched(name, patches):
    text = SOLVE.read_text()
    for old, new in [*DISARM, *patches]:
        if text.count(old) != 1:
            raise SystemExit(f"{name}: target occurs {text.count(old)} times: {old!r}")
        text = text.replace(old, new)
    return text


def run(name, patches):
    root = Path(tempfile.mkdtemp(prefix=f"g10-{name}-"))
    app = root / "app"
    shutil.copytree(BUNDLE / "environment" / "ci", app / "ci")
    shutil.copytree(BUNDLE / "environment" / "repo", app / "repo")
    (root / "solve.py").write_text(patched(name, patches))
    env = dict(os.environ, APP_ROOT=str(app), PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run([sys.executable, str(root / "solve.py")], env=env, capture_output=True, text=True)
    if proc.returncode:
        return {"error": proc.stderr[-800:]}
    out = root / "checks.json"
    subprocess.run([sys.executable, str(WORK / "run_checks.py"), str(app), str(out)], env=env,
                   capture_output=True, text=True, check=True)
    result = json.loads(out.read_text())
    shutil.rmtree(root, ignore_errors=True)
    return result


def main():
    target = Path(sys.argv[1])
    names = sys.argv[2:] or list(VARIANTS)
    results = json.loads(target.read_text()) if target.exists() else {}
    for name in names:
        if name.startswith("one_fact:"):
            patches = one_fact(name.split(":", 1)[1])
        elif name.startswith("one_fact_standing:"):
            patches = one_fact_standing(name.split(":", 1)[1])
        elif name.startswith("one_fact_qty:"):
            patches = one_fact_qty(name.split(":", 1)[1])
        else:
            patches = VARIANTS[name]
        results[name] = run(name, patches)
        print(name, json.dumps(results[name].get("score", results[name]))[:300], flush=True)
        target.write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
