"""Rewrite solution/TRUTH.md for the P12 fix of QC v1 (8e1b2d5). Content part runs once (guarded);
trial/date and sha part always.
usage: python3 -B truth_p12.py TRAP_JSON [TRIAL DATE]"""
import hashlib, json, re, sys
from pathlib import Path
B = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/tariff-engine-audit-repair")
p = B / "solution/TRUTH.md"
s = p.read_text()


def sub(old, new):
    global s
    assert s.count(old) == 1, old[:70]
    s = s.replace(old, new)


if "The judge channel carries 14 criteria" in s:
    cost = json.loads(Path(sys.argv[1]).read_text())

    def pts(name):
        return cost[name]["earned"]

    sub("""The contract defines Plan as the entry
    named by the account's `plan` and has no sentence about codes; the shipped card is the
    only thing that settles which entry a code names.""",
        """The contract defines Plan as the entry
    named by the row's `plan`, by its plan name or by one of its `codes`, and lists `codes`
    among the plan fields; the shipped card settles which entry each code names.""")
    sub("The test channel registers 110 positive checks worth 488 points and 2 negative checks,",
        "The test channel registers 114 positive checks worth 488 points and 2 negative checks,")
    sub("""- Archive and metadata (3), delivered visible tests pass (3), corrected test names (3),
  regression rows (3), module notes (1), summary (1), repair report and failing cases (1).
- Shipped files: exceptions (3), standing lines (5), energy lines with subtotal, credit
  and total (5).""",
        """- Archive layout (1), package metadata (1), the delivered package passing the shipped
  visible tests with only the two contract-wrong tests corrected (a copy held by the
  tests) (3), corrected test names (3), regression rows (3), module notes (1), summary
  (1), repair report shape (1), previously failing cases (1).
- Shipped files: exceptions (3), standing lines (5), energy lines (3), subtotals (1),
  credits and totals (1).""")
    start = s.index("Measured on real runs (test points of 488):")
    end = s.index("positive points.\n", start) + len("positive points.\n")
    para = (
        f"Measured on real runs (test points of 488): the oracle scores {pts('oracle')}; "
        f"allowance ignored {pts('N1_no_share')}; standing by the month of `start` "
        f"{pts('N2_start_month')}; tiers per meter {pts('N3_per_meter')}; an unknown plan "
        f"value falling to the first plan {pts('L11_first_plan')}; a key-only plan lookup "
        f"crashes on the shipped data (0); `estimated` ignored {pts('Q1_off')}; `standing_changes` "
        f"ignored {pts('Q2_off')}; last billing row only {pts('Q3_off')}; allowance not "
        f"carried {pts('Q4_off')}; last accounts row only {pts('Q5_off')}; revisions ignored "
        f"{pts('U1_off')}; the first fitting revision {pts('U1_first_fit')}; payments ignored "
        f"by the credit {pts('D1_off')}; counts billed as written {pts('D2_off')}; largest "
        f"voucher first {pts('S_greedy')}; a different id list among equal sums "
        f"{pts('S_tie_any')}; a missing payment row read as 0.00 {pts('S_no_paid')}; a bit "
        f"set over cents {pts('solver:bitset')}; the two visible assertions kept "
        f"{pts('V_keep_asserts')}. The judge channel carries 13 criteria, 33 positive points.\n")
    s = s[:start] + para + s[end:]
    sub("""scans the package for bare handlers and long functions, and prints
`check R1 ok` through `check R8 ok`, `check R12 ok`, `check R13 ok` and `check R14 ok`""",
        """scans the package for unused functions, parameters and constants, and prints
`check R1 ok` through `check R8 ok`, `check R11 ok`, `check R12 ok` and `check R13 ok`""")
    sub("""three runs on 2026-10-27 (test-hardening round
  d11904c), tests""", """three runs on 2026-10-27, tests""")
    sub("""  The test channel carries 110 positive checks worth 488 weight and 2 negative
  checks worth -8 weight. The judged channel carries 14 criteria worth 33
  positive points and 13 negative points.""",
        """  The test channel carries 114 positive checks worth 488 weight and 2 negative
  checks worth -8 weight. The judged channel carries 13 criteria worth 33
  positive points and 10 negative points.""")
if len(sys.argv) > 2:
    trial, date = sys.argv[2], sys.argv[3]
    s = re.sub(r"golden_score_trial_id: \S+", "golden_score_trial_id: " + trial, s)
    s = re.sub(r"three runs on \S+, tests", f"three runs on {date}, tests", s)
sh = hashlib.sha256((B / "solution/solve.sh").read_bytes()).hexdigest()
py = hashlib.sha256((B / "solution/solve.py").read_bytes()).hexdigest()
s = re.sub(r"fix_patch_sha256: [0-9a-f]{64}", "fix_patch_sha256: " + sh, s)
s = re.sub(r"solve_py_sha256: [0-9a-f]{64}", "solve_py_sha256: " + py, s)
p.write_text(s)
print("ok", py[:12])
