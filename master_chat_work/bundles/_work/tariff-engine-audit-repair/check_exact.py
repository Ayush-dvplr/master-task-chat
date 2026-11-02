"""Independent exactness check of the oracle output (G9) plus wrong-variant probes.

usage: python3 check_exact.py APP_DIR   (APP_DIR holds ci/, repo/ and out/ after solve.py)
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import refengine  # noqa: E402

# name -> list of (relative file, old text, new text); applied to a repaired tree
VARIANTS = {
    "V_qty_coerce": [("src/tariff/parser.py", "    if type(value) is int and value >= 0:",
                      "    if type(value) is str and value.strip().isdigit():\n"
                      "        value = int(value.strip())\n"
                      "    if type(value) is int and value >= 0:")],
    "V_month_calendar": [("src/tariff/report.py",
                          'month_days = (period["end"] - period["start"]).days + 1',
                          'month_days = __import__("calendar").monthrange('
                          'period["start"].year, period["start"].month)[1]')],
    "V_month_30": [("src/tariff/report.py",
                    'month_days = (period["end"] - period["start"]).days + 1',
                    "month_days = 30")],
    "V_half_up": [("src/tariff/core.py", "rounding=ROUND_HALF_EVEN", 'rounding="ROUND_HALF_UP"')],
    "V_float_round": [("src/tariff/core.py",
                       "return Decimal(value).quantize(CENT, rounding=ROUND_HALF_EVEN)",
                       "return Decimal(repr(round(float(value), 2))).quantize(CENT)")],
    "V_credit_rounded": [("src/tariff/core.py",
                          '        total = money(subtotal * (1 - plan["credit_rate"]))',
                          '        total = subtotal - money(subtotal * plan["credit_rate"])')],
}


def make_variant(repo, name, dest):
    """Copy repo to dest and apply VARIANTS[name]; raise when a patch misses."""
    shutil.copytree(repo, dest, ignore=shutil.ignore_patterns("__pycache__"))
    for rel, old, new in VARIANTS.get(name, []):
        path = Path(dest) / rel
        text = path.read_text()
        if text.count(old) != 1:
            raise SystemExit(f"variant {name}: patch target missing in {rel}")
        path.write_text(text.replace(old, new))
    return Path(dest)


def run_cli(repo, data_dir):
    env = dict(os.environ, PYTHONPATH=str(Path(repo) / "src"), PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run([sys.executable, "-m", "tariff", str(data_dir)], env=env,
                          capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise SystemExit(f"cli failed: {proc.stderr[-500:]}")
    return json.loads(proc.stdout)


def case_texts(case, card_text):
    reads = "".join(json.dumps(r) + "\n" for r in case["reads"])
    acc = "account,meter,active_from,active_to\n" + "".join(
        f"{case['account']},{m['meter']},{m['active_from']},{m['active_to']}\n" for m in case["meters"])
    per = ("account,start,end,plan,commitment,allowance\n"
           f"{case['account']},{case['period']['start']},{case['period']['end']},"
           f"{case['plan']},{case['commitment']},{case['allowance']}\n")
    return {refengine.READS: reads, refengine.ACCOUNTS: acc, refengine.PERIODS: per,
            refengine.CARD: card_text}


def main(app):
    app = Path(app)
    ci, out = app / "ci", app / "out"
    want = refengine.evaluate_dir(ci)
    work = Path(tempfile.mkdtemp(prefix="check-exact-"))
    with zipfile.ZipFile(out / "patched-repo.zip") as zf:
        zf.extractall(work / "zip")
    got = run_cli(work / "zip", ci)
    print("shipped document whole-equal:", got == want)
    bad = [i["account"] for i, j in zip(got["invoices"], want["invoices"]) if i != j]
    print("  invoices differing:", len(bad), bad[:5])
    print("  exceptions equal:", got["exceptions"] == want["exceptions"])

    card_text = (ci / refengine.CARD).read_text()
    fixes = json.loads((out / "test_fixes.json").read_text())
    cases = [json.loads(l) for l in (ci / "regression_cases.jsonl").read_text().splitlines() if l]
    miss = 0
    for case, row in zip(cases, fixes["regression_cases"]):
        doc = refengine.evaluate(case_texts(case, card_text))
        total = doc["invoices"][0]["total"]
        ok = (row["name"] == case["name"] and row["expected"] == case["customer_claim"]
              and row["actual"] == total and row["passed"] == (total == case["customer_claim"]))
        miss += not ok
    print("regression rows exact:", miss == 0 and len(cases) == len(fixes["regression_cases"]),
          f"({len(cases)} cases, {miss} wrong)")

    print("variant probes on shipped data (equal = shipped data cannot separate):")
    for name in VARIANTS:
        try:
            repo = make_variant(work / "zip", name, work / name)
        except SystemExit as stale:
            print(f"  {name:18s} skipped: {stale}")
            continue
        doc = run_cli(repo, ci)
        diff = sum(a != b for a, b in zip(doc["invoices"], want["invoices"]))
        exc = doc["exceptions"] != want["exceptions"]
        print(f"  {name:18s} equal={doc == want} invoices_differ={diff} exceptions_differ={exc}")
    shutil.rmtree(work)


if __name__ == "__main__":
    main(sys.argv[1])
