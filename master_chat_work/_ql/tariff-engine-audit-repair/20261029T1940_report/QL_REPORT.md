# QC Report: tariff-engine-audit-repair

- **Tasker:** Ayush sah
- **Task:** tariff-engine-audit-repair (`terminal-bench/tariff-engine-audit-repair`)
- **Bundle:** `/Users/apple/Desktop/Terminal Tasks/Anubis_Tasks_Samples/Pass@1_New/Sugam_Agrawal/Ayush sah/tariff-engine-audit-repair`
- **Reviewer:** Sisyphus
- **Date:** 2026-10-29
- **Scope:** the five root entries (`environment/`, `instruction.md`, `solution/`, `task.toml`, `tests/`). `trajectories/` and `output/` are out of scope by operator instruction.

**Verdict: ❌ FAIL (4 fails, 4 minors, 3 warns)**

This report lists issues only. Checks that passed are left out. During the write-up I re-checked every finding and dropped two earlier warns as false positives (see the end of the report).

---

## 1. Task summary

**The ask.** The agent repairs `tariff`, a stdlib-only Python billing package in `/app/repo` (src layout), so that it follows the written contract at `/app/ci/api_contract.md` (286 lines). It must also correct the visible unit tests that contradict the contract, without deleting, renaming or skipping any. The agent delivers seven files:

- `/app/out/patched-repo.zip`
- `/app/out/repair-report.json`
- `/app/out/module_core.json`, `/app/out/module_parser.json`, `/app/out/module_report.json`
- `/app/out/test_fixes.json`
- `/app/out/summary.json`

The final reply must list every changed function. The agent has 7200 s, with no network.

**What the contract covers:**
- read classification, with exception reasons in precedence order
- tiers by account position
- standing charges per calendar day, including `standing_changes`
- re-sharing of the allowance and carrying it to the next invoice
- the commitment credit, and no credit while arrears are open
- plans named by code
- revisions
- cumulative reads, estimated reads, and several meter or billing rows per key
- the CLI, including a missing-input error with exit 2
- a `--statements` mode that picks a voucher redemption (largest subset sum at or below the balance, ties broken by lexicographic order of ids) and must finish within 10 s
- the exact shapes of the zip and the JSON notes

**The shipped package and data.** The shipped package has about 20 seeded bugs, and two visible tests contradict the contract:
- `test_partial_period_standing_charge` expects 8.68; the contract value is 9.30.
- `test_commitment_credit_base` expects 0.99 / 47.75; the contract values are 0.00 / 48.74.

The shipped data in `/app/ci` holds:
- 10686 meter reads with mixed-type quantities
- 3393 account rows
- 2000 billing rows
- 210 voucher rows
- 2000 regression cases, plus their failing log
- a lint report with 380 issues
- the manifest and the build config

**Grading.**
- **Tests channel** (`tests/test_output.py`, 8954 lines): 158 checks, 670 positive and 8 negative points. The verifier rebuilds the shipped data from an embedded copy, extracts the zip, and runs the package as `nobody` (via `setpriv`). It runs it on the shipped data and on generated corpora: fresh, rescaled, relocated, rotated, recoded, renamed and API. It also plants quiet-rule groups (estimated reads, standing changes, extra meter and billing rows, carried allowance) and lever groups (revisions, arrears, cumulative reads), plus four kinds of statement corpora.
- **Judge channel** (`tests/judge.toml`): 16 criteria, 42 positive and 10 negative points.
- `reward.toml` gives each channel 0.5.

**Execution (Step 10).** All harbor runs went through the hq queue, and the run counts were set by the operator: oracle 2, nop 1, stub 1, plus owner-only.

| Run | Reward | Test points |
|---|---|---|
| oracle-1 | 1.000 | 670/670 |
| oracle-2 | 1.000 | 670/670 |
| owner-only | 1.000 | 670 |
| nop | 0.000 | 0 |
| stub | 0.0 | 0 (no test paid) |

No run had errors. The copies were deleted afterwards and the bundle was never edited. **Execution raised no issues.**

**Script results (Steps 1-4).** All four scripts exited 0. The only script finding still in scope is the tests_qc A3 warn (W1 below). structure_qc's five WARNs are all about `trajectories/`, which is out of scope.

---

## 2. Issue summary

| ID | Severity | Check IDs | One line |
|---|---|---|---|
| F1 | ❌ Fail | CL-5, CL-10, CL-4, AL-4, IN-8, TS-19, Step 11 | Statement grading uses a hidden voucher scale and structure the contract never states, and it carries 55% of test weight |
| F2 | ❌ Fail | TS-20 | Statements outweigh the invoice engine, with two of four statement kinds being re-seeded copies of the first |
| F3 | ❌ Fail | CL-1, CL-9, AL-2, Step 11 | The agent's repaired `test_visible.py` is never run or checked; the verifier substitutes its own corrected copy |
| F4 | ❌ Fail | TS-24 | Agent subprocesses are not in their own process group and are not killed when a timeout fires |
| M1 | 🟡 Minor | AL-18 | The instruction says each invoice and statement list is "graded whole", but grading is split by field |
| M2 | 🟡 Minor | JD-5, JD-6 | Judge R7 bundles four properties, cannot be decided, and targets a non-artifact tree |
| M3 | 🟡 Minor | DS-22, AL-18 | TRUTH.md states two different balance ranges |
| M4 | 🟡 Minor | DS-22 | TRUTH.md overstates what every check does |
| W1 | ⚠️ Warn | TS-23 | 158 checks against a cap of 35 |
| W2 | ⚠️ Warn | TS-11 | The 10 s statement timeout is wall-clock under concurrent check threads |
| W3 | ⚠️ Warn | JD-15, JD-9 | Judge R1 asks the agent to recompute all 2000 invoices outside its program |

---
## 3. Fails

### F1. Statement grading uses a hidden scale and structure, and carries 55% of the test weight

**Check IDs:** CL-5, CL-10, CL-4, AL-4, IN-8, TS-19, Step 11 · **Type:** Bug/Error

**What the contract states.** The contract puts only a time limit on `--statements`:
- `environment/ci/api_contract.md:25-28` says `--statements` "writes the statement document ... and exits 0 within 10 seconds; output that comes later counts as no output".
- The Statements section (`api_contract.md:211-231`) defines the result: the largest subset sum at or below the balance, with ties going to the lexicographically first id list.
- Nowhere in the contract is there a bound on the voucher count, the balance, or the structure of the voucher amounts.

**What the agent can see.** The shipped `/app/ci/vouchers.csv` has at most 12 vouchers per account. No account's vouchers sum to more than 147496 cents (1474.96).

**What the tests grade:**
- `tests/test_output.py:7331` `LEDGER_LOW, LEDGER_HIGH = 30_000_000_000, 100_000_000_000`. The balances are 3e10 to 1e11 cents.
- `tests/test_output.py:7417` `face, odd = rng.randrange(50_000, 100_000), rng.randrange(9, 12)`.
- `tests/test_output.py:7424` `units = [rng.randrange(1_000, 60_000) for _ in range(rng.randrange(46, 56))]`.
- `tests/test_output.py:7463` `assert 55 <= len(vouchers) <= 66`.
- `tests/test_output.py:7611-7632` (`_scale_once`): 36 vouchers in `[target/20, target/8]` with unrelated amounts. `_assert_scale` forces a search cost above `SPLIT_LIMIT = 1<<24`.
- `tests/test_output.py:7220-7225` and `:7499-7503` run with `subprocess.run(..., timeout=STATEMENT_SECONDS)`, where STATEMENT_SECONDS = 10.

**Weight.** The registrations at `tests/test_output.py:8868-8952` cover 4 kinds (statement, ledger, batch, cycle) × 7 corpora × (feasible 3 + due 5 + redeemed 5) = 364 points. Adding `shipped_statements_exact` (5) gives **369 of 670 positive test points (55.1%)**.

**The author knew the scale was hidden:**
- `solution/TRUTH.md:155-156` says "a table over cents or over one sum, a split in two halves, a list of kept sums or a bounded search gives no output within 10 seconds."
- `solution/solve.py:561-562` says "Nothing in the contract bounds the balance or the voucher count, so neither is taken to be small." The oracle passes only because it exploits the generator's common-factor block structure.
- The only place the scale appears is the judge rubric. `tests/judge.toml:183` R14 says "constructs its own input in which one account has more than 30 vouchers and a balance above 100000000.00". The agent cannot see that file.

**Empirical evidence.** I generated `_ledger_texts` and `_scale_texts` corpora (fresh and rotated) in `/tmp/tariffqc`:
- The oracle's patched package answered `--statements` in 0.16 to 0.34 s.
- A generic exact reachable-sums solver was abandoned after more than 5M states (1.4 to 2.7 s) on accounts with 61, 57, 55, 58, 56 and 36 vouchers. For example, V608630 has 61 vouchers at T=53764839234, and V451602 has 36 vouchers at T=73491893300.
- Brute force (2^61) and meet-in-the-middle (2^30 per half) are both infeasible.

**Impact (CL-4).** Take an agent whose invoices are all correct and whose redeem solver is correct but generic. It passes `shipped_statements_exact` (at most 12 vouchers) but times out on all 28 statement corpora. It loses 364 points, scoring 306/670 = 0.457 on the tests channel. TRUTH.md:263 confirms this figure: "halves alone 306 (the statement calls run past 10 s)", "a branch search 306".

The small-scale structure is visible in shipped account A1643. Its vouchers are multiples of 21.43 plus 5.34, 5.34 and 2.57. So a structure-exploiting solver is reachable (DS-21 passes). The scale and the voucher counts, which decide whether 55% of the score is paid, are not.

**Fix:** state the voucher-count and balance bounds and the amount structure in the Statements section of `api_contract.md`, or shrink the hidden statement corpora to the scale the shipped data shows and rebalance the weight.

---

### F2. Statements outweigh the invoice engine, and two of four statement kinds are re-seeded copies of the first

**Check ID:** TS-20 · **Type:** Bug/Error

**Evidence:**
- `tests/test_output.py:7548` `_SCALE_RNG = {"statement": (53, 29), "batch": (61, 37), "cycle": (67, 41)}`.
- `_scale_texts(kind, corpus)` at `tests/test_output.py:7640-7655` is one builder for all three kinds. Only the RNG constants differ.
- The same `_check_statement_feasible` and `_check_statement_field` functions are registered for each kind (`:8868-8952`).
- The batch and cycle kinds add 2 × 7 × 13 = 182 points for exactly the property the statement kind already measures: exact redeemed lists on 36-voucher sets.

**Weight split** (registrations `:8797-8952`):

| Area | Points |
|---|---|
| Statements | 369 |
| Invoice and exception field checks | 136 |
| Owned rule-group checks | 144 |
| Deliverables | 15 |
| CLI checks | 6 |

The instruction puts invoices first ("turns them into customer invoices", `instruction.md:1`; "Each invoice ... is graded whole", `instruction.md:13`). The contract gives statements one section of about 20 lines (`api_contract.md:211-231`). Yet statements carry more weight than invoicing, exceptions and every rule group combined, so the ordering is inverted.

**Fix:** drop or merge the batch and cycle statement kinds into the statement kind, and reweight so invoice correctness dominates the tests channel.

---
### F3. The agent's repaired `test_visible.py` is never run or checked; the verifier substitutes its own corrected copy

**Check IDs:** CL-1, CL-9, AL-2, Step 11 coverage · **Type:** Bug/Error

**What the contract requires** (`environment/ci/api_contract.md:235-237`):
- The visible tests the contract contradicts are corrected.
- No visible test function is deleted, renamed or skipped.
- "The repaired /app/repo/tests/test_visible.py passes against the repaired package".

**What the verifier does:**
- `tests/test_output.py:7790-7800` `_contract_visible_suite` builds the suite from the **shipped** `test_visible.py` (`_data_dir()/repo/tests/test_visible.py`) and applies the verifier's own `CONTRACT_TEST_EDITS`. These edits are defined at the top of the file: 8.68 → 9.30, credit 0.99 → 0.00, total 47.75 → 48.74.
- `tests/test_output.py:7803-7808` `_check_visible_tests_pass`, registered as `delivered_visible_tests_pass` (w3), runs that verifier-made suite against the delivered `src`. The agent's delivered `tests/test_visible.py` is never executed.
- `tests/test_output.py:7825+` `_check_corrected_tests`, registered as `corrected_tests_name_the_changed_tests` (w3), checks only three things:
  - the listed names are sorted;
  - `CORRECTED` ⊆ listed ⊆ changed (the AST dump differs);
  - `visible_tests_preserved is True`.

  It never checks that the agent's new assertions are correct.
- `solution/TRUTH.md:193-195` confirms that the visible tests run from "a copy held by the tests".

**Impact.** An agent that "corrects" the two contradicted tests to wrong values (for example 9.31, or by deleting the assertion body but keeping the function) still earns both checks (6 points). The contract requirement that the repaired file passes has no checker. The value `delivered_visible_tests_pass` claims to measure is supplied by the check setup (CL-9).

**Fix:** extract `tests/test_visible.py` from the delivered archive and run it against the delivered package. Also assert that the agent's versions of `test_partial_period_standing_charge` and `test_commitment_credit_base` expect the contract values (9.30, and 0.00 / 48.74).

---

### F4. Agent subprocesses are not in their own process group and are not killed on timeout

**Check ID:** TS-24 · **Type:** Bug/Error

**Evidence:**
- `tests/test_output.py:5637-5639` (`_run`): `subprocess.run(_untrusted_command(command), ..., timeout=120)`.
- `tests/test_output.py:7220-7225` (`_statement_run`) and `:7499-7503` (`_ledger_run`): `subprocess.run(command, ..., timeout=STATEMENT_SECONDS)`.
- A search of `tests/test_output.py` for `start_new_session`, `killpg`, `Popen` and `process_group` finds nothing.

On timeout, `subprocess.run` kills only the direct child. A forked grandchild that the agent's package spawns keeps running while the remaining checks execute. Those checks include the 10 s wall-clock statement checks, so a leftover child competing for the 2 CPUs (`task.toml` `cpus = 2`) can push them past the limit.

**Mitigations already in place.** These mean the reward itself cannot be forged:
- Agent code runs as `nobody` through `setpriv --reuid=nobody --regid=nogroup --clear-groups`.
- `tests/test.sh` sets `chown root:root /logs/verifier; chmod 755 /logs/verifier; chmod -R go-rwx /tests`, removes stale reward files, and ends with `exec rewardkit ...`.

The Gate 03 isolation list still requires "Every agent subprocess has exited before its check returns (killing the process group)", and any missed bullet is a fail.

**Fix:** start agent commands with `subprocess.Popen(..., start_new_session=True)`, and call `os.killpg(proc.pid, signal.SIGKILL)` on timeout and after normal exit, before the check returns.

---

## 4. Minors

### M1. The instruction's grading claim is untrue: grading is per field, not whole

**Check ID:** AL-18 · **Type:** Bug/Error

**Evidence:**
- `instruction.md:13` says "Each invoice, each exception list and each statement list is graded whole on fresh inputs, and only an exact match counts."
- Invoices are graded in separate pieces, each paid on its own: `_check_lines` (energy or standing lines), `_check_heads` (account, period, plan, subtotal) and `_check_settlement` (credit, total), all at `tests/test_output.py:7671-7745`.
- Statement lists have a lenient `_check_statement_feasible` (w3: redeemed ids owned, distinct and within the balance) alongside the exact `due` and `redeemed` checks.
- So a partly wrong invoice or statement list still earns points.

**Fix:** reword the sentence to say that each graded field must match the contract exactly, and drop the claim of whole-document grading.

### M2. Judge R7 bundles four properties, cannot be decided, and targets a non-artifact tree

**Check IDs:** JD-5, JD-6 · **Type:** Suggestion/Improvement

**Evidence:**
- `tests/judge.toml:92` says "The agent delivers a /app/repo/src/tariff package free of dead code: every function, parameter and module-level constant is used by the package and every branch can run."
- It combines four observables: functions, parameters, constants and branches.
- "every branch can run" is not decidable from a trajectory or a file read.
- `evaluation_target = "state_change"` points at `/app/repo`, while the declared deliverable is `/app/out/patched-repo.zip` (`task.toml` artifacts).

**Fix:** narrow R7 to one observable on the archive contents, for example "no function defined in src/tariff inside /app/out/patched-repo.zip is left uncalled by the package".

### M3. TRUTH.md states two different balance ranges for the ledger statement sets

**Check IDs:** DS-22, AL-18 · **Type:** Bug/Error

**Evidence:**
- `solution/TRUTH.md:143-146` says "balance is 400 to 800 million (in cents 4e10 to 8e10)".
- `solution/TRUTH.md:242` and `:250` say "between 3e10 and 1e11 cents".
- The code agrees with the second range: `tests/test_output.py:7331` `LEDGER_LOW, LEDGER_HIGH = 30_000_000_000, 100_000_000_000`.

**Fix:** use one range throughout TRUTH.md: 3e10 to 1e11 cents.

### M4. TRUTH.md overstates what every check does

**Check ID:** DS-22 · **Type:** Bug/Error

**Evidence:**
- `solution/TRUTH.md:190-191` says "Every check extracts /app/out/patched-repo.zip and runs the package inside it as nobody with setpriv."
- Several checks only read JSON artifacts and execute nothing: `summary_lists_inputs_and_artifacts`, `module_notes_follow_contract`, `repair_report_has_stated_shape` and `previously_failing_matches_log`.

**Fix:** limit the sentence to the checks that execute the package.

---
## 5. Warns

### W1. Check count far above the cap

**Check ID:** TS-23 (tests_qc A3) · **Type:** Suggestion/Improvement

**Evidence:** tests_qc reports "158 checks; cap is 35 (warn)". `tests/test_output.py:8797-8952` registers 158 checks, which is 670 positive and 8 negative points. Most of the excess comes from the same field checks repeated over 7 corpora and 4 statement kinds (see F2).

**Suggestion:** collapse the per-corpus repeats into fewer checks, each covering a property across all corpora.

### W2. The 10 s statement timeout is wall-clock under concurrent check threads

**Check ID:** TS-11 · **Type:** Suggestion/Improvement

**Evidence:**
- `tests/test_output.py:7220-7225` and `:7499-7503` apply `timeout=STATEMENT_SECONDS` (10 s, wall clock).
- `tests/test_output.py:5592` notes "rewardkit runs checks on several threads".
- `task.toml` sets `cpus = 2`.

The oracle took 0.16 to 0.34 s, so it has a wide margin. A correct solver that runs in, say, 6 to 9 s alone could pass or fail depending on how many other agent subprocesses are running at that moment.

**Suggestion:** run the statement checks one at a time, or measure CPU time of the child instead of wall time.

### W3. Judge R1 asks for close to a second implementation

**Check IDs:** JD-15, JD-9 (borderline) · **Type:** Suggestion/Improvement

**Evidence:** `tests/judge.toml:14` R1 (+3, trajectory) says "The agent independently recomputes the line amounts, subtotal, credit and total of every invoice for the files in /app/ci outside its program and compares them with the program's output."

That means all 2000 shipped invoices, recomputed outside the package. A competent agent who verifies by targeted spot checks, which R4, R5, R11, R12 and R13 already reward, loses these 3 points. At weight 3 it can be justified because it raises the odds of a correct end state, so this is a warn.

**Suggestion:** ask for a recomputation of a stated sample, for example "at least 20 invoices", instead of every invoice.

---

## 6. False positives removed

I re-checked each earlier observation and dropped the ones that do not hold up.

| Earlier observation | Why it was dropped |
|---|---|
| Oracle helpers (`TEST_EDITS`, `previously_failing()`, `lint_errors()`) identical to the verifier's (DS-24) | They are small deterministic parsers of the contract edits, the log and the lint report, and only one correct form exists. The rating, rule and redeem logic is independently written (Decimal/Fraction modules vs. the verifier's Fraction ledger). tests_qc O1 measured 7% overlap. Not a real independence problem. |
| Seed formulas in TRUTH.md (DS-27) | `solution/TRUTH.md:220, 225, 233-234, 246` document how the grading corpora are generated, which is a description of the task, not a story of how it was authored. |
| `instruction.md:1` "It reads a month of meter reads" vs. contract periods of 1 to 62 days | This describes the shipped sample, which is monthly. The contract governs the general case, and `instruction.md:3` says the contract wins. No contradiction. |
| structure_qc WARNs S3, S5, X1 | All five concern `trajectories/`, which is out of scope by operator instruction. |
| Oracle prints judge criterion labels (`check R1 ok` ... `check R16 ok`) | `solution/` is unreachable by the agent, and the oracle never opens `/tests` or `/logs`. No leak. |
| `{{` template-residue hits in `tests/test_output.py:6000, 6693, 6696, 6983, 6985` | These are f-string brace escapes, not template placeholders. |
| `solve.sh` idempotency | `solution/solve.py:749` skips a test edit that is already applied, and the module writes are whole-file replacements. Re-running is safe. |

---

## 7. Fix priority

1. **F1 + F2 together.** Either state the statement bounds and structure in the contract or shrink the hidden statement corpora, then remove the duplicated batch and cycle kinds and rebalance so invoice correctness dominates. Today a correct but generic agent tops out at 0.457 of the tests channel.
2. **F3.** Grade the agent's delivered `tests/test_visible.py` from the archive and assert the corrected expected values.
3. **F4.** Add process-group launch and kill to `_run`, `_statement_run` and `_ledger_run`.
4. **M1 to M4.** Prose corrections in `instruction.md:13`, `judge.toml:92` and `TRUTH.md:143-146, 190-191`.
5. **W1 to W3.** Optional tightening.
