# CHANGES: QL zip vs ours (d9bd273)

Base check: TASKS_INPUT, Output_RFP (excl. trajectories/), LAST_QC_COPY (QC/copies/f054899) and BUNDLE all have tree sha `0de116d29fdb` (INVENTORY.md). The zip bundle excl. trajectories/ is `dfd8e457d203`. All three diffs (`diff_q_*.txt`, `diff_U0_*.txt`) list the same 3 files. Because LAST_QC_COPY equals TASKS_INPUT, no file can be "our newer bytes". All 3 files are QL edits.

Line numbers: `F` = frozen (TASKS_INPUT), `Q` = his copy (`/tmp/ql-tariff-engine-audit-repair-20261029T0359/x/tariff-engine-audit-repair/`).

| file | hunk lines | layer | what it means, one line | origin |
|---|---|---|---|---|
| solution/TRUTH.md | F128-136 -> Q128-138 | solution | Lever S1 oracle note rewritten to describe the new 3-form reachability table plus a smallest-id greedy walk, in place of the gcd-unit + small-subset method. TRUTH is hidden from the agent, so this is not W1/IN-17. | QL edit |
| solution/TRUTH.md | F321 -> Q323 | meta | `solve_py_sha256` updated to `b3a65364...fa93b`. This matches `shasum -a 256 solution/solve.py` on his bytes. | QL edit |
| solution/solve.py | +Q431-553 | solution | New `SUM_LIMIT/CENT_LIMIT/PEEL_LIMIT`, `_sum_width`, `_peel`, `_BySums`, `_ByCents`, `_ByUnits`, `_table` (reachable totals per id position). | QL edit |
| solution/solve.py | F434-471 -> Q554-574 | solution | `_redeem` rewritten: it filters vouchers `<= target`, builds `_table`, takes `best()`, then walks ids ascending and takes each voucher the later ids can still finish. Old: it chose a gcd unit by cost, used a bitset on the large part and enumerated up to 20 small vouchers. | QL edit |
| tests/test_output.py | F7932-7938 -> Q7931-7946 (`_check_missing_source`) | tests | Stricter test. Before: one deleted pair (meter_reads, billing_periods). Now: pairs (0,2),(0,1),(1,2),(2,3) of `INPUT_FILES` (Q42), and each pair must name the earlier file. It grades the stated order in `environment/ci/api_contract.md:22-24`. Criterion `missing_source_is_named` w3 (Q8362-8364, Q8668). | QL edit |
| tests/test_output.py | Q7949 | tests | A blank line was added. | QL edit (cosmetic) |
| tests/test_output.py | F7954-7962 -> Q7963-7992 (`_visible_test_removed`) | tests | The penalty check is narrowed. Before, any `skip*` name anywhere in the delivered `test_visible.py` fired it. Now it only watches the shipped test functions' bodies and decorators, the decorators of their enclosing classes, and module-level `raise`. Penalty `negative_visible_test_removed` w-3 (Q8594-8596, Q8714). | QL edit |

## What the edits do (checked in /tmp, plain python, no Docker)
- solve.py `_redeem`: I ran old and new against brute force on 3000 random cases (0-9 vouchers, mixed units). Result: `old_wrong 0 new_wrong 0` (`/tmp/.../difftest.py`, LOG 04:1x). On a synthetic case with 60 or 200 vouchers of about 1e8 cents and no shared factor, the new code raises `ValueError` and the old one takes 2.8 s, or times out after 30 s. That input is outside the hidden-corpus shape in TRUTH.md:139-141 (balance 50,000.00-90,000.00, 45-70 vouchers sharing a factor, so `cap <= 9e6 < CENT_LIMIT`). INFERRED: the oracle is fine on the hidden corpora. Oracle = 1.0 on his bytes is UNVERIFIED (Docker is not allowed here).
- tests `_visible_test_removed`: I ran old and new on four variants of the shipped `environment/repo/tests/test_visible.py` (LOG 04:2x):
  - `setUpModule raise SkipTest`: old fires, new does NOT.
  - `module assign unittest.skip(...)(InvoiceCase)`: old fires, new does NOT.
  - agent's own `@skipIf` on a new test: old fires (a false positive), new does not.
  - unchanged file: neither fires.
  So the edit fixes a false positive but opens two ways to skip every shipped test with no -3. `delivered_visible_tests_pass` (Q7819-7824) runs a rebuilt suite (`_contract_visible_suite`), not the delivered file, so it does not catch these either.
- On the QL regrade, neither test edit changed any test result: test_output is 397/488 both before and after (reward-details.json in Output_RFP vs zip).
