# Proposals (not applied). Ranked by past findings each would have prevented, counted from FINDINGS.csv

Counts are upper bounds: a guard prevents a finding only if the session follows it. "Prevented" for reviewer-side items means the finding is not re-raised as new; QC can still report it as acknowledged.

| # | proposal | findings addressed | files |
|---|---|---|---|
| 1 | Give the QC reviewer the previous report, the kept list and the changed-lines list | 117 (REFLAG_KEPT 50 + MISSED_EARLIER 67) | `P11_full_qc_v3.md` (new), `QC_RULINGS.md` |
| 2 | After round 2, run a narrow recheck of changed lines; one full QC at the final round | 125 of 207 findings in round 3 or later (reviewer-side) | `P11_full_qc_v3.md`, `QC_FIX_PLAYBOOK_v3.md` |
| 3 | Fix-prompt guard rules | 45 FIX_CAUSED (at least 22 prompt-directed) | `P12_recheck_fix_v4.md` (new), `_COMMON_RULES_v5.md` |
| 4 | Stop the QC loop at the first 0-fail round; harden before QC, not after | 82 (33 fails) | `_COMMON_RULES_v5.md`, `QC_FIX_PLAYBOOK_v3.md` §5 |
| 5 | Split-vs-cap ruling, option C | 6 direct, 12 sentinel ping-pong rows | `QC_RULINGS.md`, `QC_FIX_PLAYBOOK_v3.md` rows TS-13/TS-23/NEW-CHECK |
| 6 | Build-time self-checks for the top 10 rules | 151 rows carry these ids (45 at v1) | `tools/precheck.sh`, `P2_build_v5.md` |
| 7 | Never regenerate tests without a byte diff | 8 (dispatch v3) | `_COMMON_RULES_v5.md` |

## 1. What the next QC round receives from the previous one (117)

REFLAG_KEPT (50, 15 fails) and MISSED_EARLIER (67, 23 fails) are the two largest reviewer-side groups.

Add to `master_chat_tasks/prompts/templates/P11_full_qc_v3.md` (new version of `P11_full_qc_v2.md`), in STEP 0:

> 4. Read the previous report `<REPORT_DIR>/v<N-1>.md`, the kept list `<OUT>/KEPT.md` and the changed-lines list `<OUT>/CHANGED_LINES.txt` (`diff -U0` of QC/copies/<prev_sha> vs this copy, made by master).
> - A finding on a line that is NOT in CHANGED_LINES and that v<N-1> passed must quote that pass and say why it is wrong now. Otherwise it goes under "Acknowledged, unchanged" with no severity.
> - A finding on an item in KEPT.md must answer the keep reason quoted there. If it does not, it is listed as "Kept, re-stated" and not counted in the verdict.
> - A suggested Fix must not contradict a QC_RULINGS row cited in KEPT.md (for example TS-23 "no cap", QC_RULINGS.md:137).

Add to `QC_RULINGS.md` (new section "Carry-over"):

> Kept items and unchanged lines are passed to the next reviewer (P11 v3 STEP 0.4). A re-flag without a new reason is recorded here as a variance row, not fixed.

## 2. Narrow recheck after round 2 (125 of 207 in round 3 or later)

Option analysis:
- **Narrow recheck only.** It would have dropped 125 reviewer-side findings in round 3 or later. It would also miss the real ones among the 22 MISSED fails in those rounds, for example sentinel v7 CL-2: a vacuous R10 that paid 5 judge points in A7.
- **Hybrid (recommended).** Rounds 3 to N-1 get a "changed-lines + touched rules" recheck. The kit rules are applied to every hunk in CHANGED_LINES, plus every check or criterion whose body, weight, id or description changed. The last round before a probe gets a full QC with the carry-over inputs from proposal 1.

Add to `P11_full_qc_v3.md`:

> MODE: `full` (round 1, round 2, final round) or `recheck` (other rounds). In recheck mode run scripts 1-4 in full. Run gates 01-05 only on CHANGED_LINES hunks and on every check or criterion they touch. Report other observations as "out-of-scope notes", not findings.

Add to `QC_FIX_PLAYBOOK_v3.md` §5: "Round 3+ QC is `recheck` unless the master marks it final."

## 3. Fix-prompt guard rules (45)

FIX_CAUSED is 67 in total; 45 of those carry a rule a touched-rule re-check covers. In sentinel, 8 of 9 prompt-directed causes copied QC's own Fix text: `P12_r1.md:28,:33,:36`, `20261027T0717_fix.md:16,:19`, `20261027T1217_fix.md:15,:20`.

Add to `master_chat_tasks/prompts/templates/P12_recheck_fix_v4.md` (new) under "Directions", and to `_COMMON_RULES_v5.md`:

> G1. Never paste QC's "Fix:" line as the direction. Restate it as the property to reach, then list the side-effect rules for that edit from QC_FIX_PLAYBOOK row NEW-CHECK / JD-5.
>
> G2. Never move an assert into an existing check, and never move weight onto a conduct/route criterion. A freed judge weight goes to an outcome criterion, or the total drops.
>
> G3. Never delete a clause, sentence or grader without naming what then grades the remaining promise. Examples: sentinel R3 retarget left the stdlib rule ungraded (v5 AL-2); the R11 clause deletion left a vacuous criterion (v7 CL-2).
>
> G4. After the edits, the session runs every touched check or criterion against: TS-13, TS-14, TS-20, TS-23, TS-25, TS-26, CL-2, CL-4 (tests) or JD-2, JD-5, JD-6, JD-7, JD-9, JD-13, JD-15, AL-28 (judge). It writes one row per touched item in `RECHECK_FIX.md ## Touched-rule check`.
>
> G5. Vacuity probe: run the unedited input (shipped tool/data) through every positive judge criterion and test. Any that pass on it are a CL-2 fail before QC.
>
> G6. Last edit of the round: regenerate TRUTH.md digests, counts and line cites by script, and diff every criterion description against its body. This targets the 21 "docs left stale after code edits" rows (DS-22/AL-18/AL-19/TS-24/TS-14).

## 4. Stop at the first 0-fail round; harden before QC (82, 33 fails)

The 82 findings came after a task's first 0-fail round: dispatch 24, emberforge 19, cohort 15, district 13, vendor 11. The trigger was a harden after PASS (emberforge v6, district v4, cohort v3, vendor v5) or more fixes after MINOR (dispatch v5-v8).

The QL gate (tests < 100 and final < 70, QC_RULINGS.md:145) still forces hardening of easy tasks. The proposal is to change the order, not to drop hardening.

Add to `_COMMON_RULES_v5.md`:

> Order: build, then harden until 2 probes meet the gate, then QC. A bundle that passes QC with 0 fails is frozen. A later change goes through P11 `recheck` mode on CHANGED_LINES only (proposal 2), then one probe.

## 5. Split-vs-cap ruling (TS-13/TS-20/CL-4 vs A3/TS-23)

Evidence:
- 27 post-v1 findings sit on the split side and 22 on the cap side (3 RULE_CONFLICT, 3 FIX_CAUSED).
- Sentinel ping-pong: 12 TS-13/TS-20/CL-4 rows across v1-v7. They were kept v2-v6 because the split broke trap survival and G3 (`p12_r1/RECHECK_FIX.md:35-36`), then split in v6 (35 to 39 checks), then QC v7 said merge.

| option | rule | effect on past findings |
|---|---|---|
| A | Cap is a warn, record the count, never merge (current playbook :41) | Cap warns stay (22 raised, 0 need action). Split findings are fixed by splitting. Sentinel v7 TS-23 stands as a warn; QC v7's "merge" Fix is rejected by quoting the ruling. Avoids 0 findings but stops the ping-pong edits |
| B | Merge to ≤ 35 whenever QC asks | Reopens the split side. Sentinel's merged shipped check produced 12 rows over 7 rounds; merging the hidden pairs (QC v7 Fix) risks TS-13 again. Causes, not avoids |
| C (recommended) | At build, budget checks to ≤ 35: one check per core deliverable (split by artifact, never by assertion), and merge only w1 format/presence checks of one artifact | Would have avoided the 3 RULE_CONFLICT + 3 cap FIX_CAUSED and the 12 sentinel ping-pong rows: about 18 |

Add to `QC_RULINGS.md` (section TS-23):

> | sentinel | v7:44-45 | 39 checks after the per-artifact split | WARN; QC Fix "merge to 35" | count only | KEEP the split. Budget ≤ 35 at build by one-check-per-artifact; merge only w1 presence/format checks of the same artifact (option C). Never merge two artifacts or a lever check |

In `QC_FIX_PLAYBOOK_v3.md`, change row NEW-CHECK ":57 TS-23 count <= 35" to "TS-23 count recorded; over 35 is a warn handled by option C". It currently contradicts row TS-23 (:41).

## 6. Build-time self-checks for the top recurring rules (151)

The 151 rows carrying the top 10 ids are DS-22 21, AL-27 21, TS-13 17, JD-5 15, TS-23 14, TS-16 14, JD-15 13, TS-19 12, STEP11 12 and AL-2 12. 45 of them were already present at v1.

Add to `master_chat_tasks/tools/precheck.sh` and to `P2_build_v5.md` "Self-checks":

| id | check (precheck.sh line to add) |
|---|---|
| DS-22 / AL-18 | Recompute every sha256, line count, check count and weight total cited in TRUTH.md; fail on mismatch |
| AL-27 | `WORK/RULE_COVERAGE.md` has one mutant per stated rule/ordering; fail on any 0-loss row (playbook :36 already says this; make it a precheck fail) |
| TS-13 | Flag any check whose body opens two or more distinct `/app/out/*` paths or calls two `rebuild_*`/`run_*` helpers |
| JD-5 / JD-15 | Each criterion has one verb clause; `type` vs `evaluation_target` table (trajectory and conduct means agent behavior; a stated rule means instruction following plus its quoted sentence) |
| CL-2 | Vacuity probe from proposal 3 G5 |
| TS-16 | Run each negative on the oracle plus 2 honest variants; fail if any fires |
| TS-23 | Print the count and the option C budget |
| AL-2 / STEP11 / TS-19 | Promise table from instruction.md sentences, each mapped to a check or criterion id; fail on an empty row |

## 7. Never regenerate tests without a byte diff (dispatch v3: 8 FIX_CAUSED, 15 fails)

Add to `_COMMON_RULES_v5.md`:

> Before regenerating test_output.py from a generator, diff the generator output against the current file. Any hunk not named in the fix directions stops the session (`PAUSED: generator drift`).
