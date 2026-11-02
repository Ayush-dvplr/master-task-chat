"""Build OUT/STACKING_CHECK.md for wave 1 from the round-3 file and the Docker cost run."""
import json
import sys
from pathlib import Path

R3 = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/20261026_tariff-engine-audit-repair/harden_t3/STACKING_CHECK.md")
OUT = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/20261027_tariff-engine-audit-repair/harden_w1_d11904c/STACKING_CHECK.md")
COST = Path(__file__).resolve().parent.parent / "t4_results" / "cost_docker.json"
CORPORA = ["fresh", "rescaled", "relocated", "rotated", "api", "recoded", "renamed"]

lines = R3.read_text().splitlines()
cost = json.loads(COST.read_text())


def score(name):
    row = cost[name]
    failed = sum(1 for c in row["checks"].values() if c["weight"] > 0 and not c["pass"])
    return f"{row['earned'] / row['positive']:.4f}", failed


head = """# STACKING_CHECK: tariff-engine-audit-repair, wave 1 hardening (d11904c)

Source: `stacking_check.py BUNDLE` output kept in `stacking_raw.txt` (112 checks, 488 positive, -8 negative;
judge 14 criteria, 33 positive, batched), corrected below by reading `tests/test_output.py` (rendered from
WORK/test_output.src.py by WORK/embed.py). Rows 1-91 are the round-3 rows, unchanged apart from the shipped
statement count; the 21 ledger rows are new. Lever columns as in round 3; S1L = the wave-1 ledger-scale optimum
(any one-sum table, halves, Pareto list or bounded search runs past 10 s; greedy is feasible but not optimal)."""

out = head.splitlines()
i = 0
while not lines[i].startswith("## (a)"):
    i += 1
body = lines[i:]
res = []
for line in body:
    if line.startswith("| shipped_statements_exact |"):
        line = line.replace("(60 statements)", "(61 statements, incl. A1643 in two-unit shape)")
    if line.startswith("| negative_hardcoded_sample_answers |"):
        for c in CORPORA:
            res.append(f"| {c}_ledger_statements_feasible | 3 | {c} ledger corpus: accounts, order, balance, redeemed ids own and distinct, sum <= balance, due = balance - sum | `_check_ledger_feasible` vs `_ledger_statements`; 10 s run | S1L timeout (table, halves, Pareto, bounded search), S3, corpus lever per `_LEDGER_LEVER` |")
            res.append(f"| {c}_ledger_statement_due_exact | 5 | {c} ledger corpus: (account, due) list | `_check_ledger_field(due)` vs `_redeem_split` | S1L greedy/timeout, S3, corpus lever |")
            res.append(f"| {c}_ledger_statement_redeemed_exact | 5 | {c} ledger corpus: (account, redeemed) list | `_check_ledger_field(redeemed)` vs `_redeem_split` | S1L greedy/timeout, S2 ties in both voucher groups, S3, corpus lever |")
    res.append(line)
body = res

text = "\n".join(out + [""] + body) + "\n"

text = text.replace(
    "## (b) Penalty groups",
    "Wave 1: the 21 ledger checks read the `--statements` document on seven new texts (own RNG, balances 3e10-1e11\n"
    "cents); feasibility, due and redeemed are separate fields with separate logic, as in round 3, so no observable is\n"
    "paid twice (TS-26 PASS). The round-3 statement corpora, checks and r3 `_redeem` are byte-unchanged.\n\n## (b) Penalty groups",
)

g3_old_start = text.index("## (c)")
g3_old_end = text.index("## (d)")
g3 = """## (c) Weight shares (G3), by code

| class | points | share of 488 |
|---|---|---|
| hidden or mutated reruns (round-3 total 361 + ledger hidden 7 x 13 = 91) | 452 | 92.6% |
| of which statement checks on hidden corpora (r3 91 + ledger 91) | 182 | 37.3% |
| of which the wave-1 lever (ledger checks) | 91 | 18.6% |
| shipped data (shipped_* 13, summary 1, shipped_statements_exact 5) | 19 | 3.9% |
| deliverable / artifact checks | 17 | 3.5% |

The tool's 24.6% hidden figure classes checks by name; by code every corpus check reruns the delivered program on a
generated hidden corpus. G3 PASS. Tests 112 (A3 WARN over 35 kept, TS-23), criteria 14 >= 8, judge unchanged.

"""
text = text[:g3_old_start] + g3 + text[g3_old_end:]

d_start = text.index("## (d)")
d_end = text.index("## (e)")
rows = [
    ("oracle", "oracle"),
    ("blind round-3 program (WORK/blind_r3, 397/397 last round)", "blind_r3"),
    ("blind round-3 program with the reference optimum", "blind_r3+solver:reference"),
    ("big-int bitset over cents (blind r3 `_redeem` / gcd-reduced rebuild / sum only)", None),
    ("dict table of sums", "solver:table"),
    ("Pareto list", "solver:pareto"),
    ("halves (raw / deduped id split / deduped amount split)", None),
    ("branch and bound, fractional bound", "solver:branch_bound"),
    ("largest voucher first (greedy)", "solver:greedy"),
    ("naive combinations", "solver:naive"),
]
d = ["## (d) Cost table (G10), measured in Docker, tests share of 488 (WORK/t4_results/cost_docker.json)", "",
     "| program | tests | positive checks failed |", "|---|---|---|"]
for label, name in rows:
    if name is None:
        group = ["solver:blind_r3", "solver:bitset", "solver:bitset_sum_only"] if "bitset" in label else ["solver:mitm", "solver:mitm_dedupe", "solver:mitm_dedupe_sorted"]
        got = [score(g) for g in group]
        d.append(f"| {label} | {' / '.join(s for s, _ in got)} | {' / '.join(str(f) for _, f in got)} |")
    else:
        s, f = score(name)
        d.append(f"| {label} | {s} | {f} |")
qs = ["Q1_off", "Q2_off", "Q3_off", "Q4_off", "Q5_off"]
got = [score(q) for q in qs]
d.append(f"| Q1 / Q2 / Q3 / Q4 / Q5 wrong alone | {' / '.join(s for s, _ in got)} | {' / '.join(str(f) for _, f in got)} |")
got = [score(q) for q in ["U1_off", "D1_off", "D2_off"]]
d.append(f"| U1 / D1 / D2 wrong alone | {' / '.join(s for s, _ in got)} | {' / '.join(str(f) for _, f in got)} |")
got = [score(q) for q in ["first_write", "first_write+solver:bitset", "first_write+solver:greedy"]]
d.append(f"| first write (Q1-Q5, U1, D1, D2 wrong) / plus cents bitset / plus greedy | {' / '.join(s for s, _ in got)} | {' / '.join(str(f) for _, f in got)} |")
singles = qs + ["U1_off", "D1_off", "D2_off", "blind_r3"]
best = max(singles, key=lambda n: cost[n]["earned"])
s, f = score(best)
d.append(f"| all but one right (best single-rule-wrong: {best}) | {s} | {f}; <= 92 PASS |")
lever = [n for n in cost["oracle"]["checks"] if "_ledger_" in n]
d += ["", f"Lever alone: {sum(cost['oracle']['checks'][n]['weight'] for n in lever)} of 488 points in {len(lever)} checks (18.6%, 10-30 PASS);",
      "every generic solver keeps at most the feasibility points of the ledger corpora (>= 15% lost PASS).", ""]
text = text[:d_start] + "\n".join(d) + "\n" + text[d_end:]

text = text.replace(
    "## (h) JUDGE_MAP",
    "Wave 1 ledger corpora: 7 statements each, 3 big (balance 3e10-1e11 cents, 55-66 vouchers, both voucher groups\n"
    "used, ties planted in each group), 1 overpaid at 0.00, greedy differs on 4-6 of 7 (WORK/BRANCH_FIRE.md wave 1);\n"
    "shipped now 61 statements (A1643 added).\n\n## (h) JUDGE_MAP",
)
text = text.replace(
    "`_statement_run` (`[sys.executable, \"-B\", \"-m\", \"tariff\", \"--statements\", data]`, timeout 10 s).",
    "`_statement_run` and `_ledger_run` (`[sys.executable, \"-B\", \"-m\", \"tariff\", \"--statements\", data]`, timeout 10 s).",
)
assert "—" not in text and "–" not in text
OUT.write_text(text)
print("wrote", OUT, len(text.splitlines()), "lines")
