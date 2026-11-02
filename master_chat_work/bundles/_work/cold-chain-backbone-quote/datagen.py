"""Seeded stdlib generator for environment/ci of cold-chain-backbone-quote.

Writes the shipped quote book (sites.csv, layout.tsv, links.jsonl, access_rules.toml,
activation.ini), regression_cases.jsonl, failing_tests.log (a true record of the shipped
package), lint_report.json and package_manifest.json.  build_config.json and
api_contract.md are kept as written by hand.
"""
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUNDLE = HERE.parent.parent / "cold-chain-backbone-quote"
CI = BUNDLE / "environment" / "ci"
SHIPPED_SRC = BUNDLE / "environment" / "repo" / "src"
FIXED_SRC = HERE / "fixed_repo" / "src"
sys.path.insert(0, str(FIXED_SRC))
sys.dont_write_bytecode = True

import bookgen  # noqa: E402
from task import core, parser  # noqa: E402

SEED = 174241
N_PROJECTS = 96
N_CASES = 2400


def project_of(pid, P):
    sites = []
    for q in range(P["n"] + 1):
        role = "depot" if q == 0 else "cold_room" if q in P["terms"] else "relay"
        sites.append(("X%03d" % q, role, None if q == 0 else "c", P["act"][q]))
    links = [("E%03d%03d" % (a, b), "X%03d" % a, "X%03d" % b, c) for (a, b), c in sorted(P["edges"].items())]
    return parser.assemble(pid, sites, links, len(links))


def draw_book(rng):
    used = set()
    rows = []
    plan = {}
    pids = ["P%04d" % x for x in rng.sample(range(1000, 10000), N_PROJECTS)]
    corrupt_plan = [("DUP",), ("UNKNOWN",), ("NONET",), ("DUP",), ("UNKNOWN",), ("DUP", "NONET")]
    corrupt_at = dict(zip(rng.sample(range(N_PROJECTS), len(corrupt_plan) + 3), corrupt_plan + [("CLOSED_UNKNOWN",)] * 3))
    draws = 0
    for k, pid in enumerate(pids):
        corrupt = corrupt_at.get(k)
        while True:
            draws += 1
            if rng.random() < 0.2:
                P = bookgen.grouped(rng, rng.randint(2, 3), (4, 6), rng.randint(4, 7), (1.3, 1.7))
            else:
                n = rng.randint(18, 51)
                n_terms = rng.randint(4, 10)
                n_links = rng.randint(int(1.5 * n), int(1.9 * n))
                P = bookgen.gadget(rng, n, n_terms, n_links, rng.randint(3, 6), reach=rng.randint(3, 7))
            try:
                proj = project_of(pid, P)
            except parser.Rejected:
                continue
            if core.unique(proj):
                break
        plan[pid] = (P, corrupt, core.best_network(proj).quote)
        rows.append(bookgen.encode(rng, pid, P, used, corrupt))
    return rows, plan, draws


def draw_cases(rng):
    cases = []
    kinds = ["DUP", "UNKNOWN", "NONET"]
    for k in range(N_CASES):
        n = rng.randint(3, 8)
        P = bookgen.small(rng, n, rng.randint(1, min(4, n)), rng.randint(n, 14))
        ids = ["S%03d" % x for x in rng.sample(range(100, 1000), n + 1)]
        order = list(range(n + 1))
        rng.shuffle(order)
        sites = []
        for q in order:
            role = "depot" if q == 0 else "cold_room" if q in P["terms"] else "relay"
            sites.append({"site": ids[q], "role": role, "charge": P["act"][q], "position": q})
        links = []
        for (a, b), cost in sorted(P["edges"].items()):
            ends = [ids[a], ids[b]]
            rng.shuffle(ends)
            links.append({"link": "L%03d" % len(links), "a": ends[0], "b": ends[1], "cost": cost})
        if rng.random() < 0.06:
            kind = rng.choice(kinds)
            if kind == "DUP":
                q = rng.randint(1, n)
                sites.append({"site": ids[q], "role": "relay", "charge": rng.randint(2, 9), "position": q})
            elif kind == "UNKNOWN":
                links.append({"link": "L%03d" % len(links), "a": ids[rng.randint(0, n)], "b": "S0%02d" % rng.randint(10, 99), "cost": rng.randint(2, 20)})
            elif kind == "NONET":
                target = rng.choice(sorted(P["terms"]))
                links = [x for x in links if ids[target] not in (x["a"], x["b"])]
        rng.shuffle(links)
        cases.append({"case": "RC%04d" % (k + 1), "sites": sites, "links": links})
    return cases


def outcome_fixed(case):
    try:
        proj = parser.load_inline(case)
    except parser.Rejected as exc:
        return exc.code
    return core.best_network(proj).quote


SHIPPED_RUNNER = r'''
import json, sys, traceback
from task import core, parser
out = {}
for line in open(sys.argv[1], encoding="utf-8"):
    case = json.loads(line)
    try:
        proj = parser.load_inline(case)
    except parser.Rejected as exc:
        out[case["case"]] = ["value", exc.code]
        continue
    try:
        net = core.best_network(proj)
        out[case["case"]] = ["value", core.quote_of(proj, net.links)]
    except Exception as exc:
        out[case["case"]] = ["error", type(exc).__name__, str(exc)]
print(json.dumps(out))
'''


def shipped_outcomes(path):
    env = {"PATH": os.environ["PATH"], "PYTHONPATH": str(SHIPPED_SRC), "PYTHONDONTWRITEBYTECODE": "1"}
    res = subprocess.run([sys.executable, "-B", "-c", SHIPPED_RUNNER, str(path)], capture_output=True, text=True, env=env, check=True)
    return json.loads(res.stdout)


def visible_run():
    """Run the shipped visible tests from a copy placed at /app/repo-like path; return text."""
    tmp = Path(tempfile.mkdtemp())
    repo = tmp / "repo"
    shutil.copytree(BUNDLE / "environment" / "repo", repo)
    env = {"PATH": os.environ["PATH"], "PYTHONPATH": "src", "PYTHONDONTWRITEBYTECODE": "1", "LC_ALL": "C.UTF-8"}
    res = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"],
                         cwd=repo, capture_output=True, text=True, env=env)
    text = res.stderr.replace(str(repo.resolve()), "/app/repo").replace(str(repo), "/app/repo")
    text = text.replace(str(Path(sys.executable).parent.parent), "/usr/local")
    shutil.rmtree(tmp)
    lines = []
    for line in text.splitlines():
        if line.startswith("Ran "):
            line = "Ran %s tests in 0.041s" % line.split()[1]
        lines.append(line)
    return lines


def audit_log(rng, cases, shipped, fixed):
    status = []
    details = []
    failures = errors = 0
    names = []
    for case in cases:
        name = "test_" + case["case"].lower()
        got = shipped[case["case"]]
        names.append(name)
        ident = "%s (audit_regressions.RegressionAudit.%s)" % (name, name)
        if got[0] == "error":
            errors += 1
            status.append(ident + " ... ERROR")
            details += ["=" * 70, "ERROR: " + ident, "-" * 70, "Traceback (most recent call last):",
                        '  File "/srv/ci/audit/audit_regressions.py", line 58, in check',
                        "    result = quote_case(case)",
                        "%s: %s" % (got[1], got[2]), ""]
        elif got[1] != fixed[case["case"]]:
            failures += 1
            status.append(ident + " ... FAIL")
            details += ["=" * 70, "FAIL: " + ident, "-" * 70, "Traceback (most recent call last):",
                        '  File "/srv/ci/audit/audit_regressions.py", line 61, in check',
                        "    self.assertTrue(audit.agrees(case, result))",
                        "AssertionError: False is not true", ""]
        else:
            status.append(ident + " ... ok")
    noise = ["test_book_nightly (audit_book.BookAudit.test_book_nightly) ... skipped 'book audit runs nightly'",
             "test_book_weekly (audit_book.BookAudit.test_book_weekly) ... skipped 'book audit runs weekly'"]
    head = ["", "$ PYTHONPATH=repo/src python3 -m unittest discover -s /srv/ci/audit -p 'audit_*.py' -v"]
    tail = ["-" * 70, "Ran %d tests in 38.207s" % (len(cases) + len(noise)), "",
            "FAILED (failures=%d, errors=%d, skipped=%d)" % (failures, errors, len(noise))]
    return head + noise + status + details + tail


def lint(rng):
    files = {"core": "core.py", "parser": "parser.py", "report": "report.py", "__main__": "__main__.py"}
    lengths = {m: len((SHIPPED_SRC / "task" / f).read_text().splitlines()) for m, f in files.items()}
    catalog = [
        ("C0116", "convention", "missing function or method docstring"),
        ("C0103", "convention", "variable name does not conform to snake_case naming style"),
        ("R0914", "refactor", "too many local variables"),
        ("R0912", "refactor", "too many branches"),
        ("W0612", "warning", "unused variable"),
        ("C0301", "convention", "line too long"),
        ("R1702", "refactor", "too many nested blocks"),
        ("W0640", "warning", "cell variable defined in loop"),
        ("C0200", "convention", "consider using enumerate instead of iterating with range and len"),
        ("R1714", "refactor", "consider merging these comparisons with 'in'"),
    ]
    issues = []
    for _ in range(640):
        module = rng.choice(sorted(files))
        code, severity, message = rng.choice(catalog)
        issues.append({"module": module, "line": rng.randint(1, lengths[module]), "code": code,
                       "severity": severity, "message": message})
    issues.sort(key=lambda x: (x["module"], x["line"], x["code"]))
    return {"tool": "pylint 3.2", "issues": issues}


def main():
    rng = random.Random(SEED)
    rows, plan, draws = draw_book(rng)
    files = bookgen.render(rows, rng)
    for name, text in files.items():
        (CI / name).write_text(text, encoding="utf-8")
    book = parser.load_book(CI)
    expected_rejected = {pid for pid, (_P, c, _q) in plan.items() if c and c != ("CLOSED_UNKNOWN",)}
    assert set(book["rejected"]) == expected_rejected, (book["rejected"], expected_rejected)
    for pid, proj in book["projects"].items():
        quote = core.best_network(proj).quote
        assert core.unique(proj) and quote == plan[pid][2], (pid, quote, plan[pid][2])

    cases = draw_cases(rng)
    case_path = CI / "regression_cases.jsonl"
    case_path.write_text("".join(json.dumps(c, sort_keys=False) + "\n" for c in cases), encoding="utf-8")
    fixed = {c["case"]: outcome_fixed(c) for c in cases}
    shipped = shipped_outcomes(case_path)
    log = ["$ cd repo && PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py' -v"]
    log += visible_run()
    log += audit_log(rng, cases, shipped, fixed)
    (CI / "failing_tests.log").write_text("\n".join(log) + "\n", encoding="utf-8")

    (CI / "lint_report.json").write_text(json.dumps(lint(rng), indent=2) + "\n", encoding="utf-8")
    manifest = {
        "package": "task", "version": "2.18.5", "requires_python": ">=3.12", "layout": "src",
        "stdlib_only": True,
        "public_api": ["VERSION", "task.core.best_network", "task.core.site_lines",
                       "task.parser.load_book", "task.parser.load_inline", "task.report.build"],
    }
    (CI / "package_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    rej_cases = sum(1 for v in fixed.values() if isinstance(v, str))
    print("draws", draws, "accepted", len(book["projects"]), "rejected", book["rejected"])
    print("cases", len(cases), "rejected cases", rej_cases)
    print("shipped case mismatches", sum(1 for c in cases if shipped[c["case"]][0] == "error" or shipped[c["case"]][1] != fixed[c["case"]]))
    for name in sorted(os.listdir(CI)):
        print(name, sum(1 for _ in open(CI / name, encoding="utf-8")))


if __name__ == "__main__":
    main()
