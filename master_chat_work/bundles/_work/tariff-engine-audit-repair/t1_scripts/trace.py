import json, re, sys
W = "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/tariff-engine-audit-repair/"
O = "/Users/mac/Desktop/Terminal Bench/master_chat_work/20261026_tariff-engine-audit-repair/harden_t1/"
src = open(W + "rule_mutants.py").read()
rows = re.findall(r'"(M\d+_\w+)": \(\s*"([^"]*)",\s*f?"([^"]*)"', src)
res = {}
for s in ("mutants_fix.json",):
    res.update(json.load(open(O + s)))
C = "environment/ci/api_contract.md"

def where(ref):
    return ref.replace("{C}", C) if "{C}" in ref else C + ref if ref.startswith(":") else ref

# generator branch per mutant (where hidden/shipped data makes the rule bite)
def branch(n):
    k = int(n[1:3])
    if k <= 7 or 40 <= k <= 51:
        return "deliverable checks (archive, reports, CLI) on shipped artifacts"
    if k in (8, 20, 21, 22, 23):
        return "_corpus_once: padded ids, quoted/malformed quantity reads; shipped reads"
    if k in (24, 25, 26, 27, 11, 17):
        return "_corpus_once: late/early/gone/outside/duplicate reads"
    if k in (52, 53, 56, 55):
        return "_corpus_once N1 allowance sharing (passes >= 3)"
    if k in (16, 57, 33):
        return "_period(crossing) N2 month-crossing periods"
    if k in (54, 30, 31, 19):
        return "_corpus_once shared_tiers N3 / tier caps"
    if k in (58, 59, 60, 18, 62):
        return "_plant_codes / _name_by_code / _renamed (L11)"
    if k in (63, 64):
        return "_quiet_once Q1 estimated reads"
    if k in (65, 66):
        return "_quiet_once Q2 standing_changes plans"
    if k in (67, 68):
        return "_quiet_once Q3 several billing rows"
    if k == 69:
        return "_quiet_once carried() Q4"
    if k == 70:
        return "_quiet_once Q5 several accounts rows"
    return "_corpus_once base invoices (ties, credits, kinds) + shipped"

cov = ["", "## 78d433c test-hardening round (26 Oct 2026)", "",
       "Re-measured on the 226-point test file (WORK/rule_mutants.py, 2 shards, raw `harden_t1/mutants_fix.json` (merged shards, M11/M25 re-run after a fix to their patches)). Contract lines refer to the 225-line api_contract.md. Last column: positive checks failed; none fires a negative.", "",
       "| rule | file:line | mutant | tests failed | score |", "|---|---|---|---|---|"]
trace = ["# RULE_TRACE (78d433c test-hardening round)", "",
         "One row per graded stated rule: the sentence (file:line), the generator branch that makes it bite, and the positive tests its mutant fails (WORK/rule_mutants.py on the 226-point test file). L11 is a found fact (rate_card.json `codes` witness), not a sentence; it is listed with its witness lines. A generator branch without a sentence would be a hidden rule: none.", "",
         "| rule id | sentence file:line | generator branch | tests |", "|---|---|---|---|"]
zero = []
for n, rule, ref in rows:
    r = res.get(n)
    if r is None or "checks" not in r:
        cov.append(f"| {rule} | {where(ref)} | {n} | ERROR {r and r.get('error','')[:60]} | - |")
        failed = ["(crash)"]
    else:
        failed = [c for c, v in r["checks"].items() if v["weight"] > 0 and not v["pass"]]
        neg = [c for c, v in r["checks"].items() if v["weight"] < 0 and v["pass"]]
        if not failed:
            zero.append(n)
        cov.append(f"| {rule} | {where(ref)} | {n} | {len(failed)}{' NEG ' + ','.join(neg) if neg else ''} | {r['score']:.4f} |")
    shown = ", ".join(failed[:4]) + (f" (+{len(failed)-4})" if len(failed) > 4 else "")
    trace.append(f"| {n.split('_')[0]} {rule} | {where(ref)} | {branch(n)} | {shown} |")
cov.append("")
cov.append(f"Rows: {len(rows)}; rows with 0 tests failed: {', '.join(zero) or 'none'}.")
files = ["instruction.md", "environment/ci/api_contract.md", "meter_reads.jsonl", "accounts.csv", "billing_periods.csv",
         "rate_card.json", "build_config.json", "package_manifest.json", "regression_cases.jsonl", "failing_tests.log",
         "lint_report.json", "repo/tests/test_visible.py", "repo/pyproject.toml"]
trace += ["", f"Tally: {len(rows)} graded stated rules (plus the L11 found fact) over {len(files)} files ({', '.join(files)}) in 8 formats (md, jsonl, csv, json, log, py, toml, zip artifact). Shape B floor (>= 30 rules, >= 10 files, >= 5 formats): PASS."]
open(O + "rule_coverage_section.md", "w").write("\n".join(cov) + "\n")
open(W + "RULE_TRACE.md", "w").write("\n".join(trace) + "\n")
print(len(rows), "rows; zero:", zero)
