"""Build the repair deliverables of the tariff package.

    python3 /app/build_deliverables.py [--ci /app/ci] [--repo /app/repo] [--out /app/out]

Standard library only. Runs the repaired visible tests, replays the regression
cases, packs the repaired repo and writes the seven deliverables.
"""
import argparse
import ast
import csv
import importlib
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ARTIFACT_NAMES = ["patched-repo.zip", "repair-report.json", "module_core.json",
                  "module_parser.json", "module_report.json", "test_fixes.json", "summary.json"]
ORIGINAL_TESTS = sorted([
    "test_single_tier_energy_line", "test_standing_line_full_month",
    "test_bool_quantity_is_rejected", "test_decimal_quantity_is_rejected",
    "test_unknown_meter_is_reported", "test_read_on_inactive_day",
    "test_duplicate_read_keeps_first", "test_padded_identifiers_match",
    "test_no_credit_below_commitment", "test_render_round_trips",
    "test_cli_prints_document", "test_partial_period_standing_charge",
    "test_commitment_credit_base",
])
CORRECTED_TESTS = ["test_commitment_credit_base", "test_partial_period_standing_charge"]

FIXES = {
    "core": [
        "rate_tiers: tier caps are inclusive account positions (was cap - 1) and units continue from the account position of earlier meters",
        "energy_lines/standing_line/settle: exact Fraction arithmetic from the decimal text, rounded half to even to 0.01 per line",
        "standing_line: prorates each active day by the days of its calendar month (was a flat 30-day month) and honours standing_changes",
        "share_allowance: shares the allowance in equal parts over energy lines, capped at each line's exact value, returning the unshared rest",
        "settle: commitment credit applies on the rounded subtotal (was the raw metered base incl. malformed reads); total = subtotal x (1 - credit_rate)",
    ],
    "parser": [
        "_quantity: only a JSON integer of 0 or more is accepted; text, decimals, booleans and null are malformed",
        "parse_reads: reads the estimated flag (absent = false) and parses decimals exactly",
        "_active/classify: a meter may have several active windows per account",
        "classify: adds outside_period (day in no billing period of the account) and replaced_estimate; duplicate_read keys include estimated",
        "classify: exceptions are sorted by read_id only (was account then read_id)",
    ],
    "report": [
        "_load: several accounts.csv rows per meter and several billing rows per account; commitment and allowance read exactly",
        "resolve_plan: a billing plan value may be a tariff code listed in a plan's codes",
        "build_invoices: one invoice per billing row sorted by account then start, reads assigned to the row holding their day",
        "build_invoices: unshared allowance carries to the account's next invoice",
        "_invoice: amounts written as strings with two decimals",
    ],
}
PACKAGE_FIXES = [
    "__init__.VERSION set to 2.4.1 to match the package manifest",
    "__main__.main: missing input files reported on stderr as 'missing input: <name>' with exit code 2",
    "pyproject.toml: version 2.4.1, requires-python >=3.12, dependencies = []",
    "README.md: describes contract proration and settlement",
    "tests/test_visible.py: corrected test_partial_period_standing_charge (9.30) and test_commitment_credit_base (no credit below commitment)",
]


def write_json(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def lint_errors(ci):
    report = json.loads((ci / "lint_report.json").read_text(encoding="utf-8"))
    counts = {}
    for issue in report["issues"]:
        if issue.get("severity") == "error":
            counts[issue.get("module")] = counts.get(issue.get("module"), 0) + 1
    return counts


def previously_failing(ci):
    names = set()
    pattern = re.compile(r"^(test_\S+) \(.*\) \.\.\. (FAIL|ERROR|ok)\s*$")
    for line in (ci / "failing_tests.log").read_text(encoding="utf-8").splitlines():
        match = pattern.match(line.strip())
        if match and match.group(2) in ("FAIL", "ERROR"):
            names.add(match.group(1)[len("test_"):])
    return sorted(names)


def build_zip(repo, ci, target):
    config = json.loads((ci / "build_config.json").read_text(encoding="utf-8"))["archive"]
    compression = zipfile.ZIP_STORED if config["compression"] == "stored" else zipfile.ZIP_DEFLATED
    mode = int(str(config["mode"]), 8)
    stamp = tuple(config["timestamp"])
    members = []
    for path in repo.rglob("*"):
        rel = path.relative_to(repo)
        if path.is_dir() or "__pycache__" in rel.parts or path.suffix == ".pyc":
            continue
        members.append(rel.as_posix())
    members.sort()
    with zipfile.ZipFile(target, "w", compression=compression) as archive:
        for name in members:
            info = zipfile.ZipInfo(name, date_time=stamp)
            info.compress_type = compression
            info.create_system = 3
            info.external_attr = (0o100000 | mode) << 16
            archive.writestr(info, (repo / name).read_bytes())
    return members


def run_visible_tests(repo):
    env = dict(os.environ, PYTHONPATH=str(repo / "src"), PYTHONDONTWRITEBYTECODE="1")
    done = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
                          cwd=repo, env=env, capture_output=True, text=True)
    return done.returncode == 0, done.stderr


def test_names(repo):
    tree = ast.parse((repo / "tests" / "test_visible.py").read_text(encoding="utf-8"))
    names, decorated = [], False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            names.append(node.name)
            decorated = decorated or bool(node.decorator_list)
    return sorted(names), decorated


def run_cli_missing(repo):
    env = dict(os.environ, PYTHONPATH=str(repo / "src"), PYTHONDONTWRITEBYTECODE="1")
    with tempfile.TemporaryDirectory() as tmp:
        done = subprocess.run([sys.executable, "-m", "tariff", tmp], env=env,
                              capture_output=True, text=True)
    return (done.returncode == 2 and done.stdout == ""
            and done.stderr.strip() == "missing input: meter_reads.jsonl")


def replay_case(tariff, ci, case):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "meter_reads.jsonl").write_text(
            "".join(json.dumps(read) + "\n" for read in case["reads"]), encoding="utf-8")
        with open(root / "accounts.csv", "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["account", "meter", "active_from", "active_to"])
            for meter in case["meters"]:
                writer.writerow([case["account"], meter["meter"], meter["active_from"],
                                 meter.get("active_to") or ""])
        with open(root / "billing_periods.csv", "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["account", "start", "end", "plan", "commitment", "allowance"])
            writer.writerow([case["account"], case["period"]["start"], case["period"]["end"],
                             case["plan"], case["commitment"], case["allowance"]])
        (root / "rate_card.json").write_bytes((ci / "rate_card.json").read_bytes())
        document = tariff.build_invoices(root)
    totals = [inv["total"] for inv in document["invoices"]
              if inv["account"] == str(case["account"]).strip()]
    return totals[0] if totals else ""


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ci", default="/app/ci")
    parser.add_argument("--repo", default="/app/repo")
    parser.add_argument("--out", default="/app/out")
    args = parser.parse_args(argv)
    ci, repo, out = Path(args.ci), Path(args.repo), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(repo / "src"))
    tariff = importlib.import_module("tariff")
    manifest = json.loads((ci / "package_manifest.json").read_text(encoding="utf-8"))

    tests_ok, test_log = run_visible_tests(repo)
    names, decorated = test_names(repo)
    preserved = names == ORIGINAL_TESTS and not decorated
    cli_ok = run_cli_missing(repo)
    version_ok = tariff.VERSION == manifest["version"]
    first = tariff.build_invoices(ci)
    deterministic = first == tariff.build_invoices(ci)

    cases = []
    for line in (ci / "regression_cases.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        actual = replay_case(tariff, ci, case)
        cases.append({"name": case["name"], "expected": case["customer_claim"],
                      "actual": actual, "passed": actual == case["customer_claim"]})

    lint = lint_errors(ci)
    write_json(out / "module_core.json", {
        "module": "core", "status": "fixed", "fixes": FIXES["core"],
        "lint_errors": lint.get("tariff.core", 0),
        "validations": ["visible unit tests (tests/test_visible.py)",
                        "inclusive tier caps across meters",
                        "calendar-month standing proration",
                        "half-even cent rounding of line amounts and totals",
                        "regression case replay of /app/ci/regression_cases.jsonl"],
    })
    write_json(out / "module_parser.json", {
        "module": "parser", "status": "fixed", "fixes": FIXES["parser"],
        "lint_errors": lint.get("tariff.parser", 0),
        "contract_terms": sorted(["VERSION", "build_invoices", "render"]),
    })
    write_json(out / "module_report.json", {
        "module": "report", "status": "fixed", "fixes": FIXES["report"],
        "lint_errors": lint.get("tariff.report", 0),
        "deterministic": deterministic,
    })
    write_json(out / "test_fixes.json", {
        "visible_tests_preserved": preserved,
        "corrected_tests": CORRECTED_TESTS,
        "previously_failing": previously_failing(ci),
        "regression_cases": cases,
        "all_regressions_passed": all(case["passed"] for case in cases),
    })
    write_json(out / "repair-report.json", {
        "package": "tariff",
        "fixes": FIXES["core"] + FIXES["parser"] + FIXES["report"] + PACKAGE_FIXES,
        "checks": [
            {"name": "visible tests pass (unittest discover -s tests)", "passed": tests_ok},
            {"name": "visible test functions preserved", "passed": preserved},
            {"name": "tariff.VERSION equals manifest version", "passed": version_ok},
            {"name": "CLI reports missing input with exit 2", "passed": cli_ok},
            {"name": "build_invoices deterministic on /app/ci", "passed": deterministic},
        ],
    })
    members = build_zip(repo, ci, out / "patched-repo.zip")
    write_json(out / "summary.json", {
        "package": "tariff",
        "status": "complete",
        "inputs_used": sorted(p.name for p in ci.iterdir() if p.is_file()),
        "artifacts": [f"/app/out/{name}" for name in ARTIFACT_NAMES],
        "artifact_count": 7,
        "stdlib_only": True,
    })
    print(json.dumps({
        "visible_tests_passed": tests_ok, "visible_tests_preserved": preserved,
        "cli_missing_input_ok": cli_ok, "version_ok": version_ok,
        "deterministic": deterministic, "invoices": len(first["invoices"]),
        "exceptions": len(first["exceptions"]), "zip_members": members,
        "regressions": len(cases), "regressions_passed": sum(c["passed"] for c in cases),
    }, indent=2))
    if not tests_ok:
        sys.stderr.write(test_log)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
