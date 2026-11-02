# P2 Build a task from an accepted idea, template v2 (23 Oct 2026)

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
  1. `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/_COMMON_RULES_v2.md`;
  2. `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/LEVER_RULES_v1.md` (THE authority for levers, writing, grading, judge, STACKING_CHECK and the reflex gate);
  3. `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/LEAK_LIBRARY.md` (how our levers leaked; never repeat a row);
  4. `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/QC_RULINGS.md` (what QC accepted and rejected) and `QC_FIX_PLAYBOOK.md` (same folder; how a QC finding is fixed without softening a lever);
  5. `knowledge/KNOWLEDGE.md` and `knowledge/qc_authoring_checklist_9b8229f6.md` in the same `master_chat_tasks/` folder.
- Never commit, push, pull or open a PR. Read-only git only. Edit only BUNDLE, WORK and OUT. Never edit the harness clone, the QC kit, `QC assigned/`, `my tasks/`, `QC_*/bundles/` or the Anubis repo.

## Inputs
- SLUG: `[[SLUG]]`
- ARCHETYPE: `[[ARCHETYPE]]` (its fixed output files: [[ARTIFACTS]])
- CATEGORY: `[[CATEGORY]]` (generator `--category` key)
- SEED: `[[SEED]]`
- IDEA (accepted, with the master's gate notes): `[[IDEA_PATH]]`
- LEVERS (3 or 4 from LEVER_RULES section 1, at least 2 of L1-L3, a set no live task already uses): [[LEVERS]]
- Master notes (changes to the idea, risks to watch): [[MASTER_NOTES]]
- TRUTH.md provenance rule: [[TRUTH_PROVENANCE_RULE]]
- BUNDLE: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/[[SLUG]]/`
- WORK: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/[[SLUG]]/`
- OUT (your report): `/Users/mac/Desktop/Terminal Bench/master_chat_work/[[DATE]]_[[SLUG]]/build/`

## Design rules
- Levers, writing, grading and judge follow LEVER_RULES_v1 sections 1-4. Every graded rule is fully stated in a visible file (IN-15) with one reading (IN-16); difficulty comes from where and how rules are stated and how they interact, never from secrecy (common rule Never 6) and never from explaining traps (common rule Never 8, W1).
- The instruction states WHAT to build, completely and plainly, and points to the files that hold the rules (W2). No recipe.
- Do not make it hard by volume, arithmetic, puzzles, formatting, or hidden or ambiguous rules.

## Phases (tick each in WORK/TODO.md; log each command in WORK/LOG.md)

**Phase 0: reflex pre-mortem and design, then STOP.**
1. Check the GEN and QC fingerprints (common rule 1).
2. Reflex pre-mortem (`WORK/PREMORTEM.md`, before any other file): write, step by step, how claude-opus-5 would solve this task in its first 10 minutes: which files it reads and in what order, the program it writes once, the self-tests it runs (shipped data, its own tiny examples, invariants), and its reading of every rule. Then, per lever, the exact point where that program goes wrong, and why none of its self-tests would catch it. Any lever its first-write program would get right is redesigned before Phase 1.
3. Write `WORK/DESIGN.md`. It must cover:
   - the spine stages;
   - every input file (format, rows, dependencies, at least three chains of length 4 or more);
   - for every lever: the rule text and the file that governs it (W2), the reflex reading (from PREMORTEM), the constructed hidden cases, why the visible data cannot confirm it (W5, W6), and how it interacts with the other levers;
   - the rejection paths;
   - the test plan (G1-G7: one whole-document test per downstream document on hidden reseeded inputs, isolated checks on supplied correct inputs, at least 2 mutation tests, planned weight shares) and the judge plan (J1-J5);
   - the expected reflex score.
4. Write `WORK/QC_DEFENCE.md` (IMPROVEMENT_PLAN C1): one entry per lever and per cascade: the rule ids it touches (IN-15, IN-16, TS-13, TS-19, TS-20, TS-26, AL-28, JD-7, JD-15), the quoted live rule, why the design passes (reuse a QC_RULINGS PASS where one exists), and the safe fallback if QC still flags it: the QC_FIX_PLAYBOOK row id and its DO fix written out for this lever (file, change), never a NEVER-column fix.
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
- Write each rule in the spec or data-convention file that governs its data (W2, W3), every output key and every error string (DS-25). L1 controls are real and described in the file that defines them (W7). Overrides name the field exactly (W4). Separating cases ship only for L5 (W5). No worked example where the readings differ (W6).
- No answers, labelled expected outputs or `sample_*.json` answer keys in the data.

**Phase 3: reference solution.**
- Write `solution/solve.py` and `solve.sh` from the written contract, not from the test code. Keep shared lines with `test_output.py` well under 20%, and solve.py at 30 or more substantive lines.
- It must be deterministic, offline, and run as uid 1000.
- Write `WORK/check_exact.py`, which recomputes the outputs a second, independent way for the hidden cases.

**Phase 4: tests (`tests/test_output.py`), per LEVER_RULES section 3.**
- Generate the hidden inputs verifier-side from a seed that lives only in `tests/`. Run the agent's delivered program on them from a foreign working directory.
- G1/G2: one test per downstream document on reseeded hidden inputs, each asserting only its own document; isolated rule checks on supplied correct upstream inputs, no whole-set asserts.
- G3 shares: isolated <= 30%, whole-document on hidden inputs >= 50%, shipped-only <= 5%. G6: at least 2 mutation tests. G7: assertion messages show the first differing path.
- Write the wrong implementation for each lever and confirm it loses that lever's points. A check that no wrong implementation fails is worthless.
- Weights: 5 core, 3 sub-goal, 1 existence only (TS-20). Up to 70 checks.
- G4 negatives: only cheating acts, grouped by act, <= 5 per act across tests and judge (AL-28). No negative grades a lever.
- No positive check may pass on an absence, and no two checks may read the same observable with the same logic (TS-26).
- Write `WORK/LEVERS.md`: one row per check, with its lever ids and weight, plus the weight total per lever.
- Re-embed the data, and write `reward.toml` (common rule 6).

**Phase 5: judge (`tests/judge.toml`), per LEVER_RULES section 4.**
- J1 no "states figure X" criteria; J2 one w3 conduct criterion per lever; J3 one honesty negative; J4 one named-shape code-quality criterion (JD-18); J5 no criterion endorses a reading the tests penalise; `[judge] mode = "batched"`.
- Each criterion is true for any correct solution and met by every competent approach (JD-7, JD-15), reads nothing a test reads (JD-8), uses positive grammar starting "The agent" or "The response", and counts instead of "some".
- Keep the five-key header exactly.

**Phase 6: instruction.md.**
- Rewrite it fully. The scaffold sentence has blank words in 4 archetypes.
- Plain English; state every graded rule or point to the file that holds it (W2). Name every output path once.
- State whole-document grading (G5), e.g. "each output document is graded whole on fresh inputs".
- No trap explanations, no rule counts, no lists of pitfalls (W1).
- Include "You have N seconds to complete this task." with N equal to `[agent] timeout_sec`, and keep the online-lookup sentence.
- Never mention tests, a grader, a checker, a verifier, a judge, weights or "reward". Under 6000 characters.

**Phase 7: TRUTH.md.**
- Write the 8 sections in order: Defect, Load-bearing work, Verification, Root cause, Solution shape, Ordered plan, Pitfalls, Provenance.
- Mark at least 2 items `(focal)`, at least 1 `(drift)` and at least 1 `(trap)`, all of them real.
- Include the positive weight total, the named negatives and the current sha256 values.
- Apply the provenance rule above. If the validator and QC still disagree on it, write `OPEN CONFLICT Q18` in your report and do not invent a third option.

**Phase 8: self-check and gates (fix every FAIL, then re-run once).**
1. Run the 4 QC scripts from QC on BUNDLE, `validate_bundle.py BUNDLE --archetype [[ARCHETYPE]]`, and `playground.py BUNDLE --skip-docker`. Clear WARN C6.
2. Oracle through the real tests with the fastest local method that works: `uvx --from harbor-rewardkit==0.2.1 rewardkit` in scratch against a copy of the artifacts, or the QL Docker procedure (`knowledge/intake/ql_oracle_nop_procedure.md`) in the background. Oracle x3 = 1.0 on the tests channel (oracle x3 per Ayush; the kit asks x5), nop 0.0.
3. STACKING_CHECK (LEVER_RULES section 5): run `python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/stacking_check.py" "<BUNDLE>"`, correct its hints by reading the code, and write `OUT/STACKING_CHECK.md` (a) to (d).
4. Reflex gate (LEVER_RULES section 6): no trajectory exists for a new build, so the reflex program is the P13 blind-solve program if the master supplies one at `[[REFLEX_PROGRAM_OR_NONE]]`; otherwise your own S2 (every lever reflex, from PREMORTEM) and S4 (careful: every rule right in isolation, reflex where levers combine). Each must score <= 0.20 on tests. Above 0.20: strengthen in the same lever family, max 2 tries, then stop and report "PILOT WEAK: <score>".

**Phase 9: report.** Write `OUT/BUILD_REPORT.md` with: the tree and file counts; data formats, line counts and chains; the lever table (from LEVERS.md) with where each rule is written; weight shares; every script, validator and playground result; oracle and nop; the stacking verdict and reflex scores; open conflicts; anything not run; and, last, `## Lessons for the master` (max 5 lines).

## Deliverables
- `OUT/BUILD_REPORT.md`, `OUT/STACKING_CHECK.md`, `WORK/PREMORTEM.md`, `WORK/DESIGN.md`, `WORK/LEVERS.md`, `WORK/QC_DEFENCE.md`.
- `OUT/result_[[SHA]].json`: {"sha":"[[SHA]]","slug":"[[SLUG]]","step":"P2","status":"DONE|BLOCKED|PILOT_WEAK","levers":[],"tests":N,"criteria":N,"isolated_share":x,"whole_doc_share":x,"shipped_only_share":x,"reflex":{"S2":x,"S4":x,"blind_solve":x},"stacking":"PASS|FAIL","oracle":[],"nop":x,"qc_fail":0,"tree_sha":"<sha256 over sorted paths+contents, first 12>","report":"<path>"}. The `sha` value is the board id. It must parse.

## Done when
- The bundle exists, all 4 QC scripts show 0 FAIL, the validator passes, and playground static has 0 FAIL.
- Oracle x3 1.0 and nop 0.0 on the tests channel; STACKING PASS; reflex <= 0.20.
- LEVERS.md covers every check; QC_DEFENCE.md covers every lever.
- Nothing was written inside GEN or QC (fingerprints re-checked).

Final reply (common rule, 10 lines max): DONE, BLOCKED or PILOT WEAK; levers and where each rule is written; check and criterion counts; weight shares; reflex scores; stacking result; oracle; open conflicts; report path. Next step: master issues P13 blind-solve (if not yet run), then P11 v2 QC.
