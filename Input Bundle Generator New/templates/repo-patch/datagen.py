"""Seeded repair context for the repo-patch archetype.

The repository itself (environment/repo -> /app/repo) is a template. This
writes the five CI/context files into environment/ci (-> /app/ci) next to the
contract, each of which a complete repair reads:

  package_manifest.json  the version the package and pyproject must carry
  build_config.json      archive timestamp, compression and member mode
  lint_report.json       per-module issues; module notes count the errors
  regression_cases.jsonl the cases test_fixes.json must replay, in order
  failing_tests.log      the pre-repair CI run; test_fixes.json lists what failed
"""

from __future__ import annotations

import json
import random
from pathlib import Path

ACCOUNTS = ["alpha", "beta", "gamma", "delta", "omega", "sigma", "kappa", "theta", "lambda", "rho",
            "acct-01", "acct-02", "acct-03", "north", "south", "ops", "payroll", "vendor", "escrow", "fees"]
LINT_CODES = [("E501", "warning", "line too long ({n} > 88 characters)"),
              ("C0116", "warning", "missing function or method docstring"),
              ("W0611", "warning", "unused import {name}"),
              ("E1136", "error", "value is unsubscriptable in parse path"),
              ("E0401", "error", "unable to import '{pkg}.report' cleanly: import cycle"),
              ("W0102", "warning", "dangerous default value as argument"),
              ("R1705", "info", "unnecessary else after return"),
              ("E1101", "error", "instance has no member 'rows'")]
MODULES = ["core", "parser", "report", "cli", "compat", "metadata"]


def _rows(rng: random.Random, n: int, alias: bool) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for i in range(n):
        row: dict[str, object] = {"account": rng.choice(ACCOUNTS)}
        key = "count" if alias and rng.random() < 0.35 else "delta"
        row[key] = rng.randint(-40, 60)
        if rng.random() < 0.6:
            row["note"] = rng.choice(["", f"n{i}", "carry", "manual", "reversal"])
        rows.append(row)
    return rows


def _expected(rows: list[dict[str, object]]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for row in rows:
        account = str(row["account"]).strip()
        totals[account] = totals.get(account, 0) + int(str(row.get("delta", row.get("count", 0))))
    return {k: totals[k] for k in sorted(totals)}


def _buggy(case: dict) -> tuple[str, str]:
    """Outcome of the shipped (unrepaired) package on one case: ok, FAIL or ERROR."""
    if case["format"] == "csv":
        return "ERROR", "json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)"
    payload = case["payload"]
    if not isinstance(payload, dict):
        return "ERROR", "TypeError: list indices must be integers or slices, not str"
    totals: dict[str, int] = {}
    for row in payload["rows"]:
        totals[row["account"]] = row.get("count", 0)
    if totals == case["expected"]:
        return "ok", ""
    return "FAIL", f"AssertionError: {json.dumps(totals, sort_keys=True)} != {json.dumps(case['expected'], sort_keys=True)}"


def generate(data_dir: Path, seed: int, subs: dict[str, str]) -> None:
    rng = random.Random(seed)
    package = subs["{{PACKAGE_NAME}}"]
    for stale in data_dir.iterdir():
        if stale.is_file() and stale.name != "api_contract.md":
            stale.unlink()

    version = f"{rng.randint(1, 4)}.{rng.randint(0, 19)}.{rng.randint(0, 9)}"
    (data_dir / "package_manifest.json").write_text(json.dumps({
        "package": package,
        "version": version,
        "requires_python": ">=3.12",
        "layout": "src",
        "stdlib_only": True,
        "public_api": ["VERSION", "build_report", "load_events", "tally_events"],
    }, indent=2) + "\n", encoding="utf-8")

    (data_dir / "build_config.json").write_text(json.dumps({
        "archive": {
            "path": "/app/out/patched-repo.zip",
            "compression": rng.choice(["stored", "deflated"]),
            "timestamp": [rng.randint(1995, 2020), rng.randint(1, 12), rng.randint(1, 28), 0, 0, 0],
            "mode": rng.choice(["0644", "0640", "0664"]),
            "sorted_members": True,
        },
        "runtime": {"python": "3.12", "dependencies": []},
    }, indent=2) + "\n", encoding="utf-8")

    issues = [
        {"module": "core", "line": 9, "code": "E0601", "severity": "error", "message": "tally overwrites repeated accounts and imports report through a cycle"},
        {"module": "parser", "line": 6, "code": "E1136", "severity": "error", "message": "JSON rows/count aliases and CSV ledgers are not normalized consistently"},
        {"module": "report", "line": 5, "code": "W0143", "severity": "warning", "message": "report ordering is nondeterministic when account insertion order changes"},
        {"module": "metadata", "line": 7, "code": "E0402", "severity": "error", "message": "package discovery does not expose the src layout package"},
    ]
    for _ in range(rng.randint(620, 700)):
        code, severity, template = rng.choice(LINT_CODES)
        issues.append({
            "module": rng.choice(MODULES), "line": rng.randint(1, 240), "code": code, "severity": severity,
            "message": template.format(n=rng.randint(89, 140), name=rng.choice(["os", "re", "typing.Any"]), pkg=package),
        })
    rng.shuffle(issues)
    (data_dir / "lint_report.json").write_text(json.dumps({"tool": "pylint 3.2", "issues": issues}, indent=2) + "\n", encoding="utf-8")

    cases = [
        {"name": "repeated_accounts", "format": "json", "payload": {"rows": [{"account": "alpha", "delta": 2}, {"account": "alpha", "delta": 3}, {"account": "beta", "delta": -1}]}},
        {"name": "count_alias", "format": "json", "payload": [{"account": "gamma", "count": 4}, {"account": "gamma", "delta": -2}]},
        {"name": "empty_input", "format": "json", "payload": []},
    ]
    for index in range(2400):
        shape = rng.choice(["rows", "rows", "list", "csv"])
        rows = _rows(rng, rng.randint(1, 9), alias=shape != "csv")
        name = f"case_{index:04d}_{shape}"
        if shape == "rows":
            cases.append({"name": name, "format": "json", "payload": {"rows": rows}})
        elif shape == "list":
            cases.append({"name": name, "format": "json", "payload": rows})
        else:
            for row in rows:
                row.setdefault("note", "")
            cases.append({"name": name, "format": "csv", "payload": {"rows": rows}})
    lines = []
    for case in cases:
        payload = case["payload"]
        rows = payload["rows"] if isinstance(payload, dict) else payload
        case["expected"] = _expected(rows)
        lines.append(json.dumps(case, separators=(",", ":")))
    (data_dir / "regression_cases.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    log = ["$ cd repo && PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py' -v"]
    failures = []
    for case in cases:
        outcome, detail = _buggy(case)
        log.append(f"test_{case['name']} (test_regressions.RegressionCases.test_{case['name']}) ... {outcome}")
        if outcome != "ok":
            failures.append((case["name"], outcome, detail))
    for name, outcome, detail in failures:
        log += [
            "",
            "=" * 70,
            f"{outcome}: test_{name} (test_regressions.RegressionCases.test_{name})",
            "-" * 70,
            "Traceback (most recent call last):",
            '  File "tests/test_regressions.py", line 41, in check',
            f"    self.assertEqual(build_report(payload)['accounts'], expected)",
            f'  File "src/{package}/core.py", line 14, in build_report',
            "    events = parse_events(text)",
            detail,
        ]
    errors = sum(1 for _, o, _ in failures if o == "ERROR")
    log += ["", "-" * 70, f"Ran {len(cases)} tests in {rng.uniform(1.5, 4.0):.3f}s", "",
            f"FAILED (failures={len(failures) - errors}, errors={errors})"]
    (data_dir / "failing_tests.log").write_text("\n".join(log) + "\n", encoding="utf-8")
