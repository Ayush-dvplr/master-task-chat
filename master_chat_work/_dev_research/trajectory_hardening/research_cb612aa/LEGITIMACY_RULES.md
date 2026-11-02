# Legitimacy of each change kind (cb612aa)

QC kit = `H/Input_Bundle_QC/`. Rulings = `master_chat_tasks/knowledge/`. The test applied to every change: it must still pass QC **and** it must close a gap the instruction or environment already promises. If it only re-prices the one recorded run, it is overfitting.

## Rules that apply to every change kind
- Everything graded must be promised by the instruction or by a determinate fact shipped in the environment: AL-1 `05_Alignment_Integrity_QC.md:21` and IN-8 `01_Instruction_QC.md:38`. This rule separates a real gap from an overfit one. A trip point earns a test only if the rule that was broken is stated.
- Hidden behaviours are disallowed (AL-4 `05_…:35`). Trigger depth applies: the fixture must actually construct the case (AL-27 `05_…:38`).
- The oracle must score exactly 1.000 and nop exactly 0.000, measured on freshly executed runs of the shipped bytes. Copying numbers from earlier runs fails QC (`Final_checklist.md:390, :401, :404`). Weakening a test so the oracle passes is forbidden (`:409`).
- After any change to tests/ or solution/, recompute the TRUTH.md sha256 (DS-22, `QC_FIX_PLAYBOOK_v2.md:47`).
- Reset the reward.toml weights to 0.5/positive total, which the script recomputes (TS-S10 `03_Tests_QC.md:88`).

## 1. Re-weight existing checks or criteria: QC-SAFE when it raises a core check, QC-RISKY when it lowers one
- Rules: TS-20 `03_Tests_QC.md:51` (5 = core, 3 = sub-goal or key edge, 1 = minor; ordering must match the instruction; all-identical weights fail). JD-13 `04_Judge_QC.md:90`. TS-S10 `03_…:88`. Playbook `QC_FIX_PLAYBOOK_v2.md:42`: "Raise the core check… Forbidden: Lowering a lever check to fix the order".
- Real gap: sentinel `hidden_ledger_repair_*_hard` at w5 covers the cheapest-repair core rule (harden_t3 DIAGNOSIS.md:32-49). Raising it to w6 there was justified because it is the core deliverable.
- Overfit: raising the weight of exactly the checks the recorded run failed until the final lands at 69 is "making numbers without fixing" (`Final_checklist.md:409`). The weight is then set by the run, not by importance under TS-20.

## 2. Add tests at trip points: QC-SAFE if the rule is stated and the fixture builds it, QC-RISKY otherwise
- Rules: TS-13 one property per test (`03_…:44`). TS-19 learnable (`:50`). TS-25 no positive test grades an absence (`:52`). TS-26 no double payment (`:53`). TS-23 / A3: 10-35 checks, with a warning above 35 (`03_…:62`, `tests_qc.py:293-297`). TS-12 grade artifacts, not command history (`:42`). TS-27 no source-token grading (`:43`). The NEW-CHECK hygiene list (`QC_FIX_PLAYBOOK_v2.md:57`). The cost-table check G10 (`LEVER_RULES_v3.md:142`).
- Real gap: schema harden_w1 adds exact-optimum checks on larger hidden graphs (DESIGN.md:83, 8x5 = 40 points) for a rule the contract already states. The probe's plain Dijkstra without a lower bound (DESIGN.md:22) breaks a stated property at scale. This is AL-27 trigger depth: the old fixtures never constructed the case.
- Overfit: a test that asserts the specific number the recorded agent got wrong, on an input only that run produced, or a test grading an unstated tie-break the agent happened to miss. This fails AL-1 and AL-4. A further warning: schema already has 71 checks, which trips the A3 warning (HARDEN_REPORT.md:36). Adding more pushes past 35 again.

## 3. Add judge criteria: QC-SAFE for an odds-raising process act the oracle shows, QC-RISKY for a preference
- Rules: JD-6 decidable and self-contained (`04_Judge_QC.md:72`). JD-7 the oracle satisfies or avoids each criterion (`:76`). JD-8 no overlap with tests on the same observable (`:77`). JD-11 negatives cover the real cheat surface (`:88`). JD-14 no double payment (`:91`). JD-15 two-step conduct test: an odds-raising act at w1/3 passes, a w5 preference fails, a negative that penalises an approach fails (`:92`). JD-16 constraints quote the stated sentence (`:94-95`). Q1 trajectory criteria are allowed only if the oracle shows them (`QC_RULINGS.md:140`). Q2 probe wording passes JD-15 (`:141`). J2 probe band: 8-16 criteria at w3 (`LEVER_RULES_v3.md:151`). J2b guards (`:161-170`). AL-28 one act at most -5 across all layers (`05_…:39`; dispatch -6 FAIL `QC_RULINGS.md:95`).
- Real gap: an honesty negative for "claims all checks pass / byte-identical while it did not re-run after the last edit" (J3a/J3c, -3, `LEVER_RULES_v3.md:171-173`). 8 of 21 runs show this act and nothing charged it (TRIP_METHOD.md §4). The criterion is decidable from the trajectory, and the oracle avoids it.
- Overfit: a criterion that names the exact command or file the recorded agent skipped, phrased so that only that trajectory fails it. Examples: "runs `python3 cli.py --profile prod` before step 24", or a w5 "uses a DP". These are menu or preference criteria, which fail JD-15 and J2b. Also: re-charging the trap a test already grades (J2b, JD-8).

## 4. Remove or down-weight easy passes: QC-RISKY (usually blocked)
- Rules: TS-20 forbids lowering checks just to change the score (`QC_FIX_PLAYBOOK_v2.md:42`). TS-23 / A3 floor of 10 checks (`tests_qc.py:293-297`). CL-4 partial credit tracks partial correctness (`Final_checklist.md:491`). Removing a check on a stated behaviour breaks the coverage AL-1 promises.
- Real gap (allowed): merging two checks on one observable (TS-26 / JD-14) or splitting a menu check (TS-13). In both cases the format checks shrink because they were double-paid, not because they were easy. Examples: schema has 24 RIGHT_EASY rows; sensor's judge "states figure X" carried 12/15 judge points (scores.jsonl:60).
- Overfit: dropping cohort-retention's 5 format checks so that the same 100% run reads lower. The agent did nothing wrong, and CL-4 says one wrong fact should cost about one fact.

## 5. What QC itself does not police, and the pipeline does
LEVER_RULES_v3.md:207 (harden decisions rest on 1 real run plus blind reads), :211 (the fresh blind read is the only measure of a round, "never the old agent program"), :213 ("Not evidence: differential fuzz of an old program on a changed bundle"). QL `:207`: a judge-only rebuild never rescues a tests-100 task, because at least one positive test must be lost.

Summary: kinds 1-3 are QC-SAFE when the edit is anchored to a stated rule and the oracle passes. Kind 4 is QC-RISKY except as a TS-26 / TS-13 cleanup.
