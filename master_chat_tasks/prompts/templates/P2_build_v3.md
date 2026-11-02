# P2 Build a task from an accepted idea, template v3 (24 Oct 2026)

v3 changes (MASTER_UPGRADE_PLAN_v1 Part 1 + Part 2 pilot, 24 Oct): _COMMON_RULES_v3, QC_FIX_PLAYBOOK_v2, checks.json instead of the stale checklist; no count caps (24 Oct 12:50; kit floors 10 tests, 8 criteria); the reflex gate is replaced by precheck.sh CLEAN plus a private probe run the master queues (kill rule: final reward above 70, Ayush 26 Oct); the pre-mortem stays as a design aid; judge.toml is provisional until the probe.
v3 in-place 24 Oct 13:40 (Ayush 'yes', second read of 6 delivered tasks): >=3 independent levers from the habit bank, COST_TABLE (G10), RULE_COVERAGE (G11), generator bounds asserts (G12), one contract file (W10), rubric shape J1 <= 6 what-if figures, J3 mandatory, J4 concrete, J8, JUDGE_MAP, TRUTH sha by script.
v3 in-place 25 Oct (QC push 5574d77e, review ae47772, Ayush decisions 1-11): LEVER_RULES_v2; determinate evidence may settle a deliverable-property rule (EVIDENCE_MAP); IN-17 self-check; whole-document exact grading with stated exactness (G1/G5); no 'other scales', 'no count' or self-check paragraph; W11 no visible answers; G11 per AL-2 unit + established orderings; H7 retired; L11 pilot only; 3 blind reads before the probe.
v2 changes (SETUP_PLAN_v1 Part 1, IMPROVEMENT_PLAN_v1 A2/C1/C2/E3): designs from `knowledge/LEVER_RULES_v1.md` (never pasted); reflex pre-mortem before any file; QC_DEFENCE.md written before QC; STACKING_CHECK + reflex gate (<= 0.20) before P11; W1 hard rule; no rule counts in the instruction (v1 Phase 6 asked for one, which W1 forbids); board-id rename, compaction rules, result json; "Lessons for the master".

Master fills every `[[...]]`, checks the filled prompt against `knowledge/PROMPT_CHECKLIST.md`, saves it to `prompts/issued/[[SLUG]]/P2_build.md`, and Ayush pastes it into a NEW session opened in `/Users/mac/Desktop/Terminal Bench`.

=== PASTE BELOW ===

You are building one Harbor 0.24 input bundle (a terminal-agent benchmark task) from an accepted idea. It must pass the strict Input Bundle QC and make a careful frontier agent (claude-opus-5) lose most test points. Board id: `[[SHA]]`. This prompt is saved at `[[PROMPT_PATH]]`.

## Rules that survive compaction
- First thing: rename this session to `[[SHA]]`:
  python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/name_session.py" [[SHA]]
  If the list does not show it, note that in the report and carry on; never retry on another ID.
- Tools are always available. Never claim otherwise without a real call (bash `date`) and its quoted error.
- After every compaction: run `date`, re-read this prompt, then `WORK/TODO.md`, and continue from the first unticked item. Never re-run a finished Docker block; check its log for ALL_DONE first. Copy this section word for word into any compaction summary.
- Keep `WORK/TODO.md` and `WORK/LOG.md` current after every step. Read files in pieces of at most 50 KB.
- Read first, in full, in this order:
  1. `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/_COMMON_RULES_v3.md`;
  2. `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/LEVER_RULES_v2.md` (THE authority for the determinate test, levers, writing, grading, judge, STACKING_CHECK and the probe gate);
  3. `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/LEAK_LIBRARY.md` (how our levers leaked; never repeat a row);
  4. `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/QC_RULINGS.md` (what QC accepted and rejected) and `QC_FIX_PLAYBOOK_v2.md` (same folder; how a QC finding is fixed without softening a lever);
  5. `knowledge/KNOWLEDGE.md` in the same `master_chat_tasks/` folder, and the check inventory `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261024_process/qc_reverse/A/checks.json` (pass condition and what each check does NOT require).
- Never commit, push, pull or open a PR. Read-only git only. Edit only BUNDLE, WORK and OUT. Never edit the harness clone, the QC kit, `QC assigned/`, `my tasks/`, `QC_*/bundles/` or the Anubis repo.

## Inputs
- SLUG: `[[SLUG]]`
- ARCHETYPE: `[[ARCHETYPE]]` (its fixed output files: [[ARTIFACTS]])
- CATEGORY: `[[CATEGORY]]` (generator `--category` key)
- SEED: `[[SEED]]`
- IDEA (accepted, with the master's gate notes): `[[IDEA_PATH]]`
- LEVERS (at least 3 independent levers from LEVER_RULES section 1, at least 2 of L1-L3 or the 1b habit bank H1-H6 (H7 retired; L11 only when the master names it as a pilot), a set no live task already uses): [[LEVERS]]
- COUPLING (required, LEVER_RULES G1): one stated or determinate quantity computed from all records and carried into every row (an allocation, residual or metric), and the sentence that states it: [[COUPLING]]
- Master notes (changes to the idea, risks to watch): [[MASTER_NOTES]]
- TRUTH.md provenance rule: [[TRUTH_PROVENANCE_RULE]]
- BUNDLE: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/[[SLUG]]/`
- WORK: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/[[SLUG]]/`
- OUT (your report): `/Users/mac/Desktop/Terminal Bench/master_chat_work/[[DATE]]_[[SLUG]]/build/`

## Design rules
- Levers, writing, grading and judge follow LEVER_RULES_v2 sections 0b-4. Every rule of engagement is stated in a copied file (IN-15). A deliverable-property rule is either stated or settled by one determinate shipped fact listed in `WORK/EVIDENCE_MAP.md` (AL-1 05:21, LEVER_RULES 0b), never by silence (05:27). Every graded question has one reading (IN-16). No sentence announces what the input establishes (IN-17 01:47, W1). Difficulty comes from how rules are stated, where the evidence sits and how levers interact, never from silence (common rule Never 6) and never from explaining traps (common rule Never 8).
- The instruction states WHAT to build, completely and plainly, the output paths and whole-document exactness (G5); it states no rule of its own (W10). A pointer to the contract file is optional (01:45). No recipe.
- Each stated lever's wrong reading is an Opus habit from LEVER_RULES 1b (H1-H6). Decoys, look-alike files, encodings and duplicate ids are noise only, never a scoring lever.
- Do not make it hard by volume, arithmetic, puzzles, formatting, or hidden or ambiguous rules.

## Phases (tick each in WORK/TODO.md; log each command in WORK/LOG.md)

**Phase 0: reflex pre-mortem and design, then STOP.**
1. Check the GEN and QC fingerprints (common rule 1).
2. Reflex pre-mortem (`WORK/PREMORTEM.md`, before any other file): write, step by step, how claude-opus-5 would solve this task in its first 10 minutes: which files it reads and in what order, the program it writes once, the self-tests it runs (shipped data, its own tiny examples, invariants), and its reading of every rule. Then, per lever, the exact point where that program goes wrong, and why none of its self-tests would catch it. Any lever its first-write program would get right is redesigned before Phase 1.
3. Write `WORK/DESIGN.md`. It must cover:
   - the spine stages;
   - every input file (format, rows, dependencies, at least three chains of length 4 or more);
   - for every lever: the rule text and the file that governs it (W2), the reflex reading (from PREMORTEM), the constructed hidden cases, why the visible data cannot confirm it (W5, W6; for L11 the witness and UNIQUENESS plan), and how it interacts with the other levers;
   - the rejection paths;
   - the test plan (LEVER_RULES G1-G9: whole-document exact tests per hidden corpus with exactness stated in the instruction, or owned-row tests per trap family as the CL-4 fallback, visible then hidden `_hard`, amplification through the COUPLING quantity with every amplified slip tracing to a stated single-reading rule or an EVIDENCE_MAP fact, at least 2 mutation tests from the G6 stock recipes, the G8 hidden tier, planned weight shares) and the judge plan (J1-J9);
   - the expected loss per lever (which hidden input and check a careful solver loses).
4. Write `WORK/QC_DEFENCE.md` (IMPROVEMENT_PLAN C1): one entry per lever and per cascade: the rule ids it touches (IN-15, IN-16, IN-17, AL-1, AL-27, CL-4, TS-13, TS-19, TS-20, TS-26, AL-28, JD-7, JD-15), the quoted live rule, why the design passes (reuse a QC_RULINGS PASS where one exists), and the safe fallback if QC still flags it: the QC_FIX_PLAYBOOK row id and its DO fix written out for this lever (file, change), never a NEVER-column fix.
5. Write `WORK/DESIGN_SUMMARY.md`, at most 40 lines, for the master chat.
6. Stop and say "DESIGN READY: <path to DESIGN_SUMMARY.md>". Wait until Ayush replies "go". If he passes on changes from the master chat, apply them first.

**Phase 1: scaffold.**
- Run, from GEN, with the common-rule environment variables:
  `python3 generate_bundle.py --out "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles" --name [[SLUG]] --archetype [[ARCHETYPE]] --category [[CATEGORY]] --seed [[SEED]] --title "<title>" --description "<one paragraph, at most 100 words>" --author "Ayush Sah <ayush.sah@ethara.ai>"`
- Copy the untouched scaffold to `WORK/scaffold_orig/` for reference.
- Never use `--force`.

**Phase 2: data and spec.**
- Write a seeded stdlib `WORK/datagen.py` that produces `BUNDLE/environment/data/`. Keep the data flat, with at least [[MIN_INPUTS]] files in at least 5 formats and the planned chains.
- Every file must matter to a graded result.
- Volume must meet playground A5 (at least 20,000 lines in total, and at least 2,000 per csv, tsv, jsonl, txt or log file), but volume is not the difficulty.
- Write each rule in the spec or data-convention file that governs its data (W2, W3), every output key and every error string (DS-25). L1 controls are real and described in the file that defines them (W7). Overrides name the field exactly (W4). Separating cases ship only for L5 and, as one unlabelled witness, for L11 (W5). No worked example where the readings differ (W6). Every shipped control reconciles under both readings (W7).
- No answer for any graded document anywhere in `environment/` (W11): no answer keys, golden or sample outputs, solved lists, expected figures or claimed totals, even ones that agree with the contract.

**Phase 3: reference solution.**
- Write `solution/solve.py` and `solve.sh` from the written contract, not from the test code. Keep shared lines with `test_output.py` well under 20%, and solve.py at 30 or more substantive lines.
- It must be deterministic, offline, and run as uid 1000.
- Write `WORK/check_exact.py`, which recomputes the outputs a second, independent way from the visible documents only (never from solve.py), with a per-record diff and policy-invariant asserts (G9). For every footnote, erratum or correction mechanism, run an override-removal probe: drop it and show the oracle's output moves.

**Phase 4: tests (`tests/test_output.py`), per LEVER_RULES section 3.**
- Generate the hidden inputs verifier-side from an embedded seeded generator whose seed lives only in `tests/`; seeds change every named release literal. Run the agent's delivered program on them as a foreign uid from a foreign working directory, with `--prior` = its own shipped outputs where the task has periods (G8). No slug or author string inside SHA-pinned test text.
- G1/G2: whole-document exact tests per output document and hidden corpus, allowed because instruction.md states that only an exact match counts (CL-4 exemption FC:491, quoted in QC_DEFENCE); report the one-fact-wrong score anyway. Owned-row tests per trap family are the fallback if QC still fails CL-4. Message shows the first differing path. Amplification comes from the COUPLING quantity and from whole documents. No test returns early on another test's scalar.
- G3: hidden or mutated reruns >= 30% of positive weight, at least one per downstream document family; no shipped-data cap; isolated checks optional. G6: at least 2 mutation tests from the stock recipes. G7: first differing path in every assertion message. Literal-reading self-test per rule sentence (W9) before writing tests.
- Write the wrong implementation for each lever and confirm it loses that lever's points. A check that no wrong implementation fails is worthless.
- G10 cost table: `WORK/COST_TABLE.md`, one row per lever (wrong reading injected alone into a patched copy of solve.py, real tests, test points lost) plus one "all but this lever right" row with predicted overall, plus the one-fact-wrong score per lever (CL-4). Every lever alone >= 25% of test points; every "all but one" row overall < 70. Fix a failing lever before Phase 5. These are design numbers, not hardness evidence.
- G11 rule coverage: `WORK/RULE_COVERAGE.md`, header `| rule | file:line | mutant | tests failed |`, one row per AL-2 unit (each instruction.md promise plus each delegated rule it invokes, 05:33) and per ordering, precedence or tie-break the shipped input establishes (05:38), each mutant dropping that rule alone; every row fails at least 1 test, else add a hidden-tier fixture or drop the rule. precheck.sh fails a 0 row.
- G12: the embedded generator asserts every drawn value is inside the contract's stated bounds (TS-19); it plants every branch of each multi-branch rule on some seed (template master_chat_work/20261024_process/test_depth/kit/fam/cm_family.py), and the reference plus generator survive 300 seeds over the contract bounds with no crash or endless loop. No contract sentence lists the malformed values of a typed field (precheck LV-ENUM).
- Weights: 5 core, 3 sub-goal, 1 existence only (TS-20). At least 10 checks and at least 8 judge criteria, no upper cap (Ayush 24 Oct). Above 35 checks the kit prints WARN A3: record it, never merge lever checks to get under 35.
- G4 negatives: only cheating acts, grouped by act, <= 5 per act across tests and judge (AL-28). No negative grades a lever.
- No positive check may pass on an absence, and no two checks may read the same observable with the same logic (TS-26).
- EVIDENCE_MAP: `WORK/EVIDENCE_MAP.md` `| rule | test ids | shipped fact file:line | wrong readings it contradicts |` for every graded rule with no sentence; for each L11 lever also `WORK/UNIQUENESS.md` (every candidate reading fitted to every shipped and hidden witness, exactly one fits).
- Write `WORK/LEVERS.md`: one row per check, with its lever ids and weight, plus the weight total per lever.
- Re-embed the data, and write `reward.toml` (common rule 6).

**Phase 5: judge (`tests/judge.toml`), per LEVER_RULES section 4.**
- J1 no criterion restating an output-file figure (final-reply criteria are fine; what-if figure criteria for rerun figures in no output file only when solve.py prints them and the verifier recomputes them, max 6, w <= 3 each, with a conduct criterion on that rerun); J2 conduct criteria "independently recomputes <graded figure> outside its program for every <run/class/item> and compares", one w3 per output family, 6-20 in total, each performed by a solve.sh self-check stage that prints `check <id> ok` (JD-7 kept); J3 mandatory honesty negative w -3 to -5 ("claims a check passed with no run after its last edit that shows it"); J4 exactly one code-quality criterion with concrete conditions (no bare or pass-only except, no function over about 150 lines, no dead code) (JD-18); J5 no criterion endorses a reading the tests penalise; J6 one per-item enumeration criterion on the final answer; J7 deterministic artifact behaviour is a test, never a criterion; J8 no criterion restates a method a test grades; J9 one w3 criterion "runs its program on a copy of the data whose contents it altered (not only relocated) and checks that the dependent figures move", performed by the self-check stage; `[judge] mode = "batched"`. Never echo J2 or J9 wording in instruction.md.
- Write `WORK/JUDGE_MAP.md` (`| id | oracle shows it at | test it must not overlap |`); remove any criterion with no oracle-shows entry. Never add annotation keys (judge_qc J6).
- Each criterion is true for any correct solution and met by every competent approach (JD-7, JD-15), reads nothing a test reads (JD-8), uses positive grammar starting "The agent" or "The response", and counts instead of "some".
- Keep the five-key header exactly.

**Phase 6: instruction.md.**
- Rewrite it fully. The scaffold sentence has blank words in 4 archetypes.
- Plain English; a pointer to the contract file is optional (01:45). Name every output path once.
- State whole-document exactness up front (G5), e.g. "each output document is graded whole on fresh inputs, and only an exact match counts". Never add "at other scales", "there is no count to check yourself against" or a self-check paragraph. Where useful: one arbiter sentence naming which document wins when documents disagree (W8); the full output schema or the file that holds it.
- No trap explanations, no rule counts, no lists of pitfalls (W1). IN-17 self-check on every sentence: if it announces something the agent was meant to find AND the shipped input already establishes it, delete it.
- Include "You have N seconds to complete this task." with N equal to `[agent] timeout_sec`, and keep the online-lookup sentence.
- Never mention tests, a grader, a checker, a verifier, a judge, weights or "reward". Under 6000 characters.

**Phase 7: TRUTH.md.**
- Write the 8 sections in order: Defect, Load-bearing work, Verification, Root cause, Solution shape, Ordered plan, Pitfalls, Provenance.
- Mark at least 2 items `(focal)`, at least 1 `(drift)` and at least 1 `(trap)`, all of them real.
- Include the positive weight total, the named negatives and the current sha256 values. Write every sha256 and every figure from a script run after your last edit under `tests/` or `solution/` (DS-22: 5 of 90 fails); precheck.sh recomputes each `<name>: <sha256>` line and fails a mismatch.
- Apply the provenance rule above. If the validator and QC still disagree on it, write `OPEN CONFLICT Q18` in your report and do not invent a third option.

**Phase 8: self-check and gates (fix every FAIL, then re-run once).**
1. Run the 4 QC scripts from QC on BUNDLE, and `validate_bundle.py BUNDLE --archetype [[ARCHETYPE]]` (playground.py was removed from GEN in a72c20a4; check A5 volume with your own line count). Clear WARN C6.
2. Oracle through the real tests with the fastest local method that works: `uvx --from harbor-rewardkit==0.2.1 rewardkit` in scratch against a copy of the artifacts, or the QL Docker procedure (`knowledge/intake/ql_oracle_nop_procedure.md`) in the background. Oracle x3 = 1.0 on the tests channel (oracle x3 per Ayush; the kit asks x5), nop 0.0.
3. STACKING_CHECK (LEVER_RULES section 5): run `python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/stacking_check.py" "<BUNDLE>"`, correct its hints by reading the code, and write `OUT/STACKING_CHECK.md` (a) to (d).
4. `tools/precheck.sh BUNDLE` until its last line is `PRECHECK CLEAN` (common rule Always 10). No reflex gate: hardness is decided by 3 blind reads and the probe run the master queues next (LEVER_RULES section 6). Write in DESIGN.md, per lever, the hidden input and check where a careful solver is expected to lose points, so the probe's `loss.py` table can be compared with it.

**Phase 9: report.** Write `OUT/BUILD_REPORT.md` with: the tree and file counts; data formats, line counts and chains; the lever table (from LEVERS.md) with where each rule is written; weight shares; every script, validator and playground result; oracle and nop; the stacking verdict; the PRECHECK last line; the expected loss per lever; open conflicts; anything not run; and, last, `## Lessons for the master` (max 5 lines).

## Deliverables
- `OUT/BUILD_REPORT.md`, `OUT/STACKING_CHECK.md`, `WORK/PREMORTEM.md`, `WORK/DESIGN.md`, `WORK/LEVERS.md`, `WORK/QC_DEFENCE.md`, `WORK/COST_TABLE.md`, `WORK/RULE_COVERAGE.md`, `WORK/EVIDENCE_MAP.md` (and `WORK/UNIQUENESS.md` per L11 lever), `WORK/JUDGE_MAP.md`.
- `OUT/result_[[SHA]].json`: {"sha":"[[SHA]]","slug":"[[SLUG]]","step":"P2","status":"DONE|BLOCKED|PILOT_WEAK","levers":[],"tests":N,"criteria":N,"isolated_share":x,"whole_doc_share":x,"shipped_only_share":x,"precheck":"CLEAN|<n> findings","expected_loss":{"<lever>":"<check ids>"},"cost_table":{"<lever>":{"alone_pct":x,"all_but_one_overall":x}},"rules_uncovered":0,"stacking":"PASS|FAIL","oracle":[],"nop":x,"qc_fail":0,"tree_sha":"<sha256 over sorted paths+contents, first 12>","report":"<path>"}. The `sha` value is the board id. It must parse.

## Done when
- The bundle exists, all 4 QC scripts show 0 FAIL, the validator passes, and the A5 line count meets the volume rule.
- Oracle x3 1.0 and nop 0.0 on the tests channel; STACKING PASS; PRECHECK CLEAN.
- LEVERS.md covers every check; QC_DEFENCE.md covers every lever.
- Nothing was written inside GEN or QC (fingerprints re-checked).

Final reply (common rule, 10 lines max): DONE, BLOCKED or PILOT WEAK; levers and where each rule is written; check and criterion counts; weight shares; PRECHECK last line; stacking result; oracle; open conflicts; report path. Next step: master issues 3 P13 blind reads (a lever counts only if >= 2 of 3 programs miss it), then queues the private probe run (oracle 1.0, nop 0, current staged path), reads `loss.py`, applies the kill rule, then issues QC.
