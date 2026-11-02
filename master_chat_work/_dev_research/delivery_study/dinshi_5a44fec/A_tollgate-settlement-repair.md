# A tollgate-settlement-repair — Step 1

**Verdict: GENUINE** (one of the two failed checks is contested: expected form contradicts a literal runbook sentence).

Recorded 72.89 / 91.55 / 54.24. QC re-grade of stored artifacts against fixed tests: test_output **66/72 = 91.67%** (QC report `Aniket_Datta_tollgate-settlement-repair_QC_Report.md:149`).

## Artefact screen
- result.json exception_info null; no negative fired (report.json: negatives passed=false = not fired).
- Agent run 20:24:04-20:36:15 UTC (12 min) within 5400 s; finished with `finish` at step 49.
- Delivered code run under `_sandboxed` setpriv uid 65534 (tests/test_output.py:361) with `_tree` chown of the extracted package (:351). Holdout drivers `delivered_package_prices_holdout`, `reports_holdout`, `reconciles_holdout`, `resolves_fleet_accounts`, `resolves_order` all PASSED → program executed under the drop; no permission artefact.

## Failed checks (2, both weight 3)
| check | expected (test) | agent (artifacts/app/out) | kind |
|---|---|---|---|
| `build_report_chain_and_phase` (tests/test_output.py:522-533) | `root_cause_chain == ["_bootstrap.py","core.py"]` | `["_bootstrap.py","tariff.py","metrics.py"]` (build_report.json; written in agent step 33) | wrong VALUE (judgement field) |
| `dependency_block_orders` (:549-561) | `load_order == ["registry","audit","tariff","metrics","core"]`, bind order bare names, `MANIFEST_ORDER` bare (:81) | same orders with `.py` suffix (`"registry.py", ...`) | wrong FORM; orders themselves correct |

Rule locations:
- chain: runbook.md:179-180 "`root_cause_chain`, the modules whose defects had to be repaired in order before the next one could be seen, listed in that order". Oracle constant `ROOT_CAUSE_CHAIN = ["_bootstrap.py", "core.py"]` (solution/solve.py:44); rationale only in solution/TRUTH.md:139-146 (not agent-visible). Agent never deliberated on the chain (no "chain" occurrence in its thoughts outside the write step 33 and self-check step 47).
- suffix: runbook.md:182-185 "Every module named in a delivered block carries the source file name as it appears in the archive, with its `.py` suffix, and every module list in a block is sorted and carries no repeats." The sentence sits in the build_report paragraph 8.5 but says "in a delivered block"; the oracle emits bare names for the dependency block (solve.py:97-98, 443-445). The agent applied the sentence globally (self-check step 47 asserts `.py` on build_report lists only, but its dependency block also carries `.py`). QC CL-5 (QC report :105) cites runbook 182-186 as satisfying the `.py` requirement and did not notice the dependency block contradicts it. Note the same sentence's "sorted" clause cannot apply to load_order, which shows its intended scope is the build report — scope carried by placement, not stated.

## Points
- Lost 6/71 recorded (6/72 re-graded). Genuine value loss 3 (chain). Contested 3 (dependency form: agent obeyed the literal global sentence). Genuine points lost counted as **3**, contested 3 flagged.
