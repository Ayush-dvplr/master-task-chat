# CONFLICTS (d9bd273)

| conflict | file:line | rule file:line | what Ayush must decide |
|---|---|---|---|
| C1. A tests/ file changed, so the pushed run (trial 6107faf5, final 49.77) no longer matches the bytes and a new paid run is needed. The QL regrade (54.31) is diagnostic only and cannot be pushed. | zip `tests/test_output.py:7931-7946, 7963-7992` | `_COMMON_RULES_v5.md:66-67` (never re-run the same bytes; regrade is diagnostic; Output_RFP tests/ = frozen tests/); `LEVER_RULES_v3.md:236` (any change after the run voids it); this prompt Phase 2 bullet 4 (each new paid run needs Ayush OK, outside the daily cap, Q5 a) | Confirm ONE new paid run on the post-harden frozen bytes, outside the daily cap. INFERRED: his 02:33 answer "Take his edits, QC, harden, run <40" (zip `REQUEST.md`) already covers it, so a yes/no is enough. |

Checked, no conflict:
- W1 / IN-17 / IN-15: there are no instruction.md, environment/ or contract edits (CHANGES.md). The `_check_missing_source` docstring (Q7932-7937) explains how the test works, but tests/ is hidden from the agent. The order it grades is stated in `environment/ci/api_contract.md:22-24`. The solve.py and TRUTH.md text is under solution/, which is hidden.
- Law-1 (`LEVER_RULES_v3.md:87-90`): no hunk adds difficulty that is lost by TIMEOUT or CRASH. On his regrade the stricter missing-source test still passes, and lost points are 91 WRONG / 0 TIMEOUT / 0 CRASH (TRIP_ql.md:6).
- PENDING overlap: PENDING = none, so no 3-way diff is needed.
- Older base: none. LAST_QC_COPY = TASKS_INPUT = 0de116d29fdb, and there are 0 "our newer bytes" rows.
- judge.toml and reward.toml are unchanged (diff_q_*.txt).

Advisory, not a stop row: the `_visible_test_removed` narrowing (Q7963-7992) lets `setUpModule(): raise unittest.SkipTest` and `InvoiceCase = unittest.skip(..)(InvoiceCase)` escape the w-3 penalty. I showed this in /tmp, see CHANGES.md. The fix goes into the P9 v4 harden, see ROUTE.md. It only adds watched nodes and does not take away his false-positive fix.
