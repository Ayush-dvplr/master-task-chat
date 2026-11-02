"""QL2 fixes F5/F6/F7/F17 and F4 figures in TRUTH_q2_body.md (one-shot; each old text must occur once)."""
from pathlib import Path

body = Path(__file__).resolve().parent.parent / "TRUTH_q2_body.md"
s = body.read_text()
EDITS = [
    # F6: allowance_ticks_mutation has no draws_from row.
    ("   `ledger_quality_match_hard`, `segment_rows_match_hard`, `tie_decisions_match_hard`,\n"
     "   totals and `allowance_ticks_mutation`.\n",
     "   `ledger_quality_match_hard`, `segment_rows_match_hard`, `tie_decisions_match_hard` and\n"
     "   totals.\n"),
    # F5: the receipt carries no record counts.
    ("6. (trap) The export receipt counts records and sums fields as written. It agrees with the\n"
     "   files whatever reading a program takes; no report figure comes from it.\n",
     "6. (trap) The export receipt names each file and sums named fields as written; it gives no\n"
     "   record counts. It agrees with the files whatever reading a program takes; no report figure\n"
     "   comes from it.\n"),
    # F4 counts.
    ("`tests/test_output.py` has 66 checks: 63 positive (237 points) and 3 negatives (-13).\n",
     "`tests/test_output.py` has 78 checks: 75 positive (261 points) and 3 negatives (-13).\n"),
    # F7 + F4 families.
    ("- Owned-row families (160): twenty families, each a shipped-data check (w3) and a `_hard`\n"
     "  check on a hidden seeded extract (w5). Each family owns its rows and compares them exactly,\n"
     "  reporting the first differing path. Season extract families: `selection`, `intervals`,\n"
     "  `tie_decisions`, `segment_rows`, `ledger_quality`, `region_totals_North`,\n"
     "  `region_totals_South`, `region_totals_West`, `region_totals_East`, `segment_totals`,\n"
     "  `summary`, `labels`, `quality_counts`. Settlement extract families: `credit_rows`,\n",
     "- Owned-row families (176): twenty-two families, each a light check (w3) and a `_hard` check\n"
     "  on a hidden seeded extract (w5). The light check runs on the shipped data, except\n"
     "  `tie_decisions_match`, which runs on a generated extract where two portfolios tie in one\n"
     "  event-region. Each family owns its rows and compares them exactly, reporting the first\n"
     "  differing path. Season extract families: `selection`, `intervals`,\n"
     "  `tie_decisions`, `segment_rows`, `ledger_quality`, `region_totals_North`,\n"
     "  `region_totals_South`, `region_totals_West`, `region_totals_East`, `segment_totals`,\n"
     "  `summary`, `labels`, `quality_counts`, `bid_cost_rows` (`bid_cost_cents` of every event\n"
     "  entry), `compliance_rows` (`compliance_counts` of every event entry). The shipped\n"
     "  `quality_counts_match` leaves out `unallocated_pool_count`, which `residual_match` grades\n"
     "  there. Settlement extract families: `credit_rows`,\n"),
    ("- Wide extracts (64): for each of the four wide extracts `wide_k_portfolios_feasible` (w3:\n",
     "- Wide extracts (72): for each of the four wide extracts `wide_k_portfolios_feasible` (w3:\n"),
    ("  (w5) and `wide_k_intervals_match` (w3), each compared whole.\n",
     "  (w5), `wide_k_intervals_match` (w3), `wide_k_bid_cost_rows_match` (w1) and\n"
     "  `wide_k_compliance_rows_match` (w1), each compared whole. The reference finds every optimum\n"
     "  by a table over sites (`_exact`), not by the branch search of `solve.py`; the wide optima\n"
     "  were computed once by `_exact`, checked equal to the oracle's, and are stored in the tests by\n"
     "  the digest of each event-region.\n"),
    ("and mutated checks carry 173 of 237 points.\n",
     "and mutated checks carry 191 of 261 points.\n"),
    # F17: the bound has five parts.
    ("   last, and stops a branch once a lower bound on components 1 and 2 (relief still reachable,\n"
     "   capped at the ceiling) is already worse than the best portfolio. The wide extracts take it\n",
     "   last, and stops a branch once the five-part key with components 1 and 2 bounded (relief still\n"
     "   reachable, capped at the ceiling, and segment relief still reachable) and components 3 to 5\n"
     "   taken as they stand is already worse than the best portfolio's key. The wide extracts take it\n"),
]
for old, new in EDITS:
    assert s.count(old) == 1, old[:60]
    s = s.replace(old, new)
body.write_text(s)
print("edited", len(EDITS))
