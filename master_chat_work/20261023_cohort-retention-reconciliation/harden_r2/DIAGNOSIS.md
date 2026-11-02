# P9 harden r2 diagnosis: cohort-retention-reconciliation (board 7cbd9f5)

Written 23 Oct 2026 IST. Phase 1 only; no BUNDLE edits. Harness HEAD 71a653b23fc2a6bc7ff3d4a8c286ec9a1b6a298e.
RESULT: `master_chat_work/20261023_cohort-retention-reconciliation/traj_a2/trajectory_job_cohort-retention-reconciliation_bb8ec0/`, claude-opus-5 Run 1: tests 100.0, rubric 100.0, combined 100.0 (`logs/pass-summary.json`).

## 0. Root cause: why 58.67 (v0) became 100/100/100 (a2)

### Cause 1, run error or wrong copy: NO
- The run used the current bundle. `logs/job-config.json` points at `.kiro-staged-tasks/cohort-retention-reconciliation`. That staged copy hashes to c4ac79773a32 (25 files): BUNDLE plus `.kiro-staged-from` (content `.../Tasks_INPUT/cohort-retention-reconciliation`) and `task.toml` allowed_hosts lines 25 and 32 with `host.docker.internal` added (the harness judge proxy injection). Nothing else differs.
- `Tasks_INPUT/cohort-retention-reconciliation` = 8667ff1e386d (24 files), the same as BUNDLE now and as `result_0b8ac36.json` tree_sha. `diff -rq Tasks_INPUT BUNDLE` exit 0.
- `.master-queue/task-archive/cohort-retention-reconciliation-20261023T003231` = b8312a0e4d2e (22 files, instruction.md mtime 19 Oct, no `audit_policy.md`, no `plan_history.csv`). It is the old pre-harden Tasks_INPUT copy that was archived when the new one was placed at 00:32:31. It was not the run copy. Agent step 5 runs `cat /app/data/audit_policy.md`, and that file exists only in r1 and later trees.
- `agent/instruction.txt` is byte-identical to BUNDLE `instruction.md`.
- No errors: Run 1 `result.json` exception_info None, verifier reward 1.0. ctrf summary: 25 tests, 20 passed, 5 failed (the 5 "failed" are `negative_*` penalties that did not fire). weighted_percentage 100.0. job.log/trial.log hold only "Skipping image OS validation ... docker inspect returned 1" (benign). finalize.log: normalize_ctrf skipped (already normalized), 0 errored.
- The judge read the response. `judge_response.txt` quotes it per criterion: R1 "Total revenue: 35700 cents.", R4 "14 reason entries across 11 rejected rows", R8 reasoning cites the final program run on /app/data after the last edit (steps 12, 17).

### Cause 2, harness or rescoring change: PARTLY (scoring did not change; the v0 number was a trap artefact)
- v0 had a judge. The master note says it did not, and that is wrong. `harden_r1/DIAGNOSIS.md`: v0 0.5868 = 0.5 x 0.4235 (tests 36/85) + 0.5 x 0.75 (judge 27/36). Both runs used the same 0.5/0.5 channel split. The harness moved from HEAD f3765e67 to 71a653b2, with no change to the reward formula for this bundle.
- v0 lost all 49 program-run test points to the permission trap: test-stdout had 18 lines `can't open file '/app/out/derive_report.py': [Errno 13] Permission denied`. The LEVERS.md local probe ran the agent's v0 program with the trap removed and it passed 12/12 program-run checks, which makes tests 85/85.
- Without the trap, v0 = 0.5 x 1.0 + 0.5 x 0.75 = **87.5**. The judge lost its 9 points to process criteria (R13 honesty negative, R17 dead branch), not to wrong figures.
- **The tests channel was never hard.** The v0 agent scored 100% on tests whenever its program could be read. The 58.67 measured the grader's file-permission bug, not task difficulty.

### Cause 3, our QC/fix rounds made it easier: NO for anything the agent sees; PARTLY on the rubric (R4 correctness fix)
- The harden r1 tree was not kept (`/tmp/opencode-logs/...stalecopy-20261022T233624` is gone). Evidence used instead:
  - QC v2 report `QC_2026-10-22/qc_report/cohort-retention-reconciliation/v2.md` line 11: the r1 copy (22:18, before P12) differs from the P12 tree in exactly 5 files: `solution/TRUTH.md`, `solution/solve.py`, `task.toml`, `tests/judge.toml`, `tests/test_output.py`.
  - BUNDLE mtimes agree. Everything the agent sees is dated harden r1 (21:03-21:18, before the 22:00 gates): `instruction.md`, `schema.md`, `audit_policy.md`, `events.csv`, `plan_history.csv`, `qualifying_rules.json`. Every P12 file is dated 23:04-23:07.
- Check of each suspected change:
  - TRUTH/judge figures stated in the instruction: NO. instruction.md asks for 6 figures and states none. The agent computed them (step 12 output).
  - R4 "14 reason entries" exposure: NO exposure. 14 sits only in `solution/TRUTH.md` and `tests/judge.toml`, and the agent never sees either. P12 corrected R4 from 13 (wrong for the oracle) to 14. With 13, the agent's correct 14 would have failed R4 (-3/19, rubric 84.2, overall ~92). This fix made 100 reachable on the rubric, but it is a correctness fix and not a leak.
  - Serialization check requiring the full doc set: HARDER, not easier. `_written_study` now needs every document plus the reference cohorts before it awards the serialization and determinism points.
  - solve.py rewrite (tag_rows): not agent-visible. Output byte-identical, oracle x3 1.0.
  - R7 structure -> code quality: the agent met both wordings. The judge wrote "structure cleanly separates loading, cleaning, derivation, and output".
  - Rule text moved next to its use: NO. schema.md and audit_policy.md were not touched after harden r1. `task.toml` P12 change = `[task] description` metadata only.

### Cause 4, the levers were weak by design: YES
Every rule was one explicit sentence that the agent read once and coded correctly on the first write. Agent sequence:
- Read: step 4 `cat schema.md`, step 5 `cat audit_policy.md`, step 6 `cat` every data file.
- Plan (step 8): "rejection register computed independently on raw rows"; resolve merges "pick max by (eff, file_index); guard visited".
- Build and check: wrote the program once (step 9, recreated at step 11 with cosmetic changes only), ran it (12), self-tested on a synthetic extract (14-16) covering unsorted calendar, chained merges, plan-history tie, minimum_value>0, negative revenue, offset_zero_is_full true, a duplicated exclusion row and a final-period cohort. Determinism diff (17).
- It never edited the logic after the first write.

| Lever | Rule location (what gave it away) | Agent got it right at |
|---|---|---|
| CR-1 every reason (A) | audit_policy.md L20-25 "Each reason is tested on its own against the raw row, so a row carries every reason that holds for it, not only the one for the cleaning step that removed it" (the reflex trap is spelled out in the rule) | step 8 plan; step 11 `rejection_register` L210-239 (reason set) |
| CR-2 plan in force (B decoy) | audit_policy.md L9-16 plan_history latest on/before, later row on tie, opening plan fallback, resolved account. schema.md L107 "its account's plan" points at the policy. The decoy is contradicted in plain words. Shipped boundary a002/e009 shows the effect | step 11 `plan_in_force` L132, `weight_of` L142; step 19 explains a002 enterprise |
| CR-3 non-purchase subtracts (E) | schema.md L104-105 "A `purchase` adds its `value_cents`; every other revenue event type subtracts it" | step 11 L331 `if event_type != "purchase"` |
| CR-4 strict malformed (F) | schema.md L59-61 real YYYY-MM-DD date, value non-empty digit run | step 11 DATE_RE L15, DIGITS_RE L16, `is_malformed` L146 |
| CR-5 two duplicate notions (B) | schema.md L66-67 (among remaining, first kept) vs audit_policy.md L29-30 (earlier row anywhere in events.csv) | step 11 cleaning `seen` L177-183; register `seen_keys` over all raw rows L214-219 |
| V0-1 cleaning order (E) | schema.md numbered steps 1-6 | step 11 `clean_events` L152-193 |
| V0-2 pre-cohort out (A) | schema.md L92 "never before its own cohort" | step 11 `build_activity` L278 |
| V0-3 exclusion on resolved account (B) | schema.md L68-73 | step 11 L190 |
| V0-4 merge history (C) | schema.md L28-32 on/after, chain, latest effective_from wins | step 8 plan quote; step 11 `resolve_account` L115-130 |
| V0-5 minimum value (A) | schema.md L80-81 | step 11 `build_cohorts` L247 |
| V0-6 offset_zero flag (A) | schema.md L118 | step 11 L452 |
| V0-7 fraction format (E) | schema.md L12-15 | step 11 `rate()` L39 |
| V0-8 survival running min (B) | schema.md L98 "never rises" | step 11 L306 `floor = min(floor, count)` |

Common pattern:
- No rule had a plausible wrong reading. Each sentence named its own exception.
- The only "split across files" was a two-file read, and instruction.md tells the agent to read schema.md "together with the study records it points to".
- The decoy was refuted on the same page as its use.
- The shipped boundaries (a002/e009, e030/e031/e033) let a careful agent watch each rule fire. Hidden cases only repeat rules the agent had already coded.
- Every check graded a rule the agent read correctly, so the hidden-input design (70% weight) had nothing to separate.

**PRIMARY CAUSE: 4.** Contributing:
- Cause 2: the 58.67 was a permission-trap artefact. Without the trap v0 scores 87.5 (tests 100%), so the task was never hard on tests.
- Cause 3 (minor, rubric only): the P12 R4 correction made 19/19 reachable. That fix is correct and must stay.

## 1. Per-check and per-criterion result, mapped to levers (P1.1)

Tests channel: 60/60 positive points, 0 negatives fired.

| Check | Pts | Earned | Levers | Verdict |
|---|---|---|---|---|
| artifact_set | 1 | 1 | shipped-only | LEAKED |
| hidden_cohorts | 5 | 5 | CR-4, V0-4, V0-5 | LEAKED |
| hidden_retention | 5 | 5 | CR-4, V0-2 | LEAKED |
| hidden_survival | 3 | 3 | V0-8 | LEAKED |
| hidden_revenue | 5 | 5 | CR-2, CR-3 | LEAKED |
| hidden_segments | 5 | 5 | CR-2, CR-3 | LEAKED |
| hidden_data_quality_counts | 3 | 3 | CR-4, CR-5 | LEAKED |
| hidden_rejection_register | 5 | 5 | CR-1, CR-5 | LEAKED |
| hidden_reconciliation | 3 | 3 | CR-3, V0-6 | LEAKED |
| hidden_study_audit | 1 | 1 | (audit doc) | LEAKED |
| hidden_per_cohort_documents | 3 | 3 | CR-2, CR-3 | LEAKED |
| hidden_serialization_is_canonical | 1 | 1 | V0-7 | LEAKED |
| deterministic_rerun | 3 | 3 | (process) | LEAKED |
| register_lists_every_reason | 3 | 3 | CR-1 | LEAKED |
| plan_in_force_on_the_event_date | 3 | 3 | CR-2 | LEAKED |
| other_revenue_types_subtract | 3 | 3 | CR-3 | LEAKED |
| malformed_rows_are_dropped_first | 3 | 3 | CR-4 | LEAKED |
| merge_history_by_event_date | 3 | 3 | V0-4 | LEAKED |
| pre_cohort_activity_stays_out_of_the_matrix | 1 | 1 | V0-2 | LEAKED |
| rates_are_exact_signed_fractions | 1 | 1 | V0-7 | LEAKED |
| 5 x negative_* (-5, -5, -3, -5, -5) | -23 | 0 fired | cheat detectors | n/a |

Judge channel: 19/19.

| Criterion | W | Met | Lever | Verdict |
|---|---|---|---|---|
| R1 total revenue 35700 | 3 | yes | CR-3 | LEAKED |
| R2 weighted total 138900 | 5 | yes | CR-2, CR-3 | LEAKED |
| R3 mid weighted 54000 | 3 | yes | CR-2 | LEAKED |
| R4 register 14 reason entries | 3 | yes | CR-1, CR-5 | LEAKED |
| R5 2026-P1 share 460/463 | 3 | yes | CR-2, V0-7 | LEAKED |
| R6 clean count 23 | 1 | yes | CR-4, CR-5, V0-1 | LEAKED |
| R7 code quality | 1 | yes | (quality) | n/a |
| R8 honesty negative | -5 | not fired | (honesty) | n/a |

Lever totals (test points shared by a multi-lever check are counted under each lever):

| Lever | Test pts available | Earned | Judge pts | Earned | Verdict |
|---|---|---|---|---|---|
| CR-1 | 8 | 8 | 3 | 3 | LEAKED |
| CR-2 | 16 | 16 | 14 | 14 | LEAKED |
| CR-3 | 21 | 21 | 8 | 8 | LEAKED |
| CR-4 | 16 | 16 | 1 | 1 | LEAKED |
| CR-5 | 8 | 8 | 4 | 4 | LEAKED |
| V0-1 | (in all hidden docs) | all | 1 | 1 | LEAKED |
| V0-2 | 6 | 6 | 0 | 0 | LEAKED |
| V0-3 | (in all hidden docs) | all | 0 | 0 | LEAKED |
| V0-4 | 8 | 8 | 0 | 0 | LEAKED |
| V0-5 | 5 | 5 | 0 | 0 | LEAKED |
| V0-6 | 3 | 3 | 0 | 0 | LEAKED |
| V0-7 | 2 | 2 | 3 | 3 | LEAKED |
| V0-8 | 3 | 3 | 0 | 0 | LEAKED |

## 2. What made each LEAKED lever derivable (P1.2)
See the table in section 0, cause 4. In short:
- CR-1: the rule text states the trap ("not only the one for the cleaning step that removed it"). The shipped rows e030/e031/e033 carry 2 reasons each.
- CR-2: the decoy pointer ("its account's plan") is resolved two paragraphs later in plain words. Shipped a002/e009 shows it.
- CR-3: one sentence, no alternative reading.
- CR-4: one sentence, and the regex follows directly from it.
- CR-5: the two notions sit in different files, but each one is fully explicit. The agent's plan (step 8) shows it built the register "independently on raw rows".
- V0-1..V0-8: numbered steps and single sentences. All were already coded correctly in v0 (probe 12/12), so they had leaked before r1.
- The agent's own self-test (steps 14-16) exercised every hidden-case family the grader uses: chained merges, plan tie, min value, negative revenue, offset_zero flag, unsorted calendar, final-period cohort.

## 3. Baselines (P1.3)
`WORK/baselines.json` records no S-k solver scores, only the v0 tree sha ae77ceb8..., harness_head f3765e67 and v0 reward 0.5868. The a2 agent matched the full reading (oracle-equivalent): 20/20 positive checks at 1.0, every shipped figure equal to TRUTH. Phase 3 must add solver scores (S2, S4, S-a2) to baselines.json.

## 4. Diff harden r1 -> P12 r1 -> current BUNDLE (P1.4)
- Current BUNDLE = P12 r1 tree = run copy minus harness staging (8667ff1e386d).
- Harden r1 -> P12 changed only `solution/TRUTH.md`, `solution/solve.py`, `task.toml` (description), `tests/judge.toml` (R4 13->14, R7 wording), and `tests/test_output.py` (`_written_study` full-doc requirement).
- None of these files is agent-visible, and none put a figure or a rule in front of the agent.
- **Suspected cause REFUTED** for the tests channel. For the rubric it is a needed correction: R4=13 was wrong, and leaving it would only have made the rubric unreachable for a correct solver, not hard.

## 5. Where the agent went wrong or skipped verification (P1.5): candidate judge criteria
- It made no mistakes. It verified more than the grader requires: synthetic extract, determinism diff, AST parse, and a grep for network modules. No step skipped verification.
- So a2 offers no real mistake to grade. The process criteria have to come from mistakes the new levers are built to cause, and every such criterion must also be true of the oracle (JD-7), met by every competent route (JD-15), and must not read what a test reads (JD-8).
- Implication for Phase 2: a correct-reading program states every shipped figure correctly. The judge "states figure X" criteria (R1-R6) can only drop below 100 if the new levers change a SHIPPED figure. That means at least one decoy default contradicted on a rare shipped boundary, with the figure asked for plainly in the instruction (batch notes line 28).
- Candidate judge criteria for Phase 2 (one figure each, needing the full new chain, absent from every file):
  - a shipped figure that depends on the new C-family stage defect being repaired;
  - a shipped figure that depends on the new composition boundary;
  - a reconciliation residual that is non-zero only under the decoy reading.
- Keep R7 code quality (JD-18) and R8 honesty negative. `mode = "batched"` is already set.

## 6. Direction for Phase 2 (proposal; awaiting "go")
- Families: A + B + C. C = registry LV-002, audit-and-repair of a broken multi-stage pipeline against a documented contract. This differs from r1 (A+B+E+F) and adds the required C/D. D (LV-003 size ladder) is rejected because it is volume difficulty, which the master notes forbid.
- C mechanism:
  - Ship a prior analyst's staged program under `/app/legacy/` with 5-6 independent silent defects. Each defect gives correct output on the shipped extract and wrong output only on hidden-only or rare-boundary inputs. Examples: dedup keyed on the resolved account, the calendar ordered by period_id text, the plan read from accounts.csv when plan_history is empty for the account, the survival floor reset at a gap, fraction reduction via float.
  - Some defects carry a plausible code comment that contradicts the written contract (decoy default in code).
  - Document per-stage contracts. Never document the bug list.
  - The grader keeps grading whole downstream documents on reseeded hidden inputs, plus per-stage intermediate documents, so a defect upstream poisons the chain (family B).
- A-family composition modelled on the one `held` registry lever (LV-EF-L7, real run lost 10/11 to an if/elif early return): hidden-only rule pairs whose natural code structure drops one effect. Each rule stays stated, but in different files, with neither sentence naming the other.
- Weights: rule-isolating checks <=30%, shipped-only <=5%, whole downstream documents on hidden inputs keep partial credit. Caps 70/70 respected. TS-20 respected.
- Honest risk: LV-002 is a registry `candidate` with no real-run evidence. An agent that ignores `/app/legacy/` and writes from the contracts (as a2 did) avoids the code decoys. The new levers therefore have to bite through the contracts too: rare shipped boundary plus hidden composition, not only through the legacy code.

DIAGNOSIS READY
