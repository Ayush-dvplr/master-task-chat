# P2 Build a task from an accepted idea, template v5 (27 Oct 2026 18:45)

v5 changes (Ayush decisions 1, 4, 7, "proceed" 27 Oct; pipeline v4 PLAN `master_chat_work/_dev_research/pipeline_v4/PLAN.md`): _COMMON_RULES_v5 and QC_FIX_PLAYBOOK_v3; design uses a proven test lever (LEVER_RULES 1C P-1..P-3) with a Docker-only, capped kill test whose table splits WRONG / TIMEOUT / CRASH (Law-1 filter); Phase 8 stage-2 self-checks before QC (TRUTH recompute, TS-13 multi-file scan, CL-2 vacuity probe, TS-16 negatives silent on oracle and 2 honest variants, promise table, literal table, judge honesty negative + type/target table + one verb clause); next step is 3 fresh blind reads, then one full QC.

v3 changes (MASTER_UPGRADE_PLAN_v1 Part 1 + Part 2 pilot, 24 Oct): _COMMON_RULES_v3, QC_FIX_PLAYBOOK_v2, checks.json instead of the stale checklist; no count caps (24 Oct 12:50; kit floors 10 tests, 8 criteria); the reflex gate is replaced by precheck.sh CLEAN plus a private probe run the master queues (kill rule: final reward above 70, Ayush 26 Oct); the pre-mortem stays as a design aid; judge.toml is provisional until the probe.
v3 in-place 24 Oct 13:40 (Ayush 'yes', second read of 6 delivered tasks): >=3 independent levers from the habit bank, COST_TABLE (G10), RULE_COVERAGE (G11), generator bounds asserts (G12), one contract file (W10), rubric shape J1 <= 6 what-if figures, J3 mandatory, J4 concrete, J8, JUDGE_MAP, TRUTH sha by script.
v3 in-place 25 Oct (QC push 5574d77e, review ae47772, Ayush decisions 1-11): LEVER_RULES_v2; determinate evidence may settle a deliverable-property rule (EVIDENCE_MAP); IN-17 self-check; whole-document exact grading with stated exactness (G1/G5); no 'other scales', 'no count' or self-check paragraph; W11 no visible answers; G11 per AL-2 unit + established orderings; H7 retired; L11 pilot only; 3 blind reads before the probe.
v4 (26 Oct, board 720e1d7, delivery_study2 g1-g4): LEVER_RULES_v3; pick a design shape (B breadth or D degenerate instance) plus hardness sources S1-S11 instead of ">= 3 independent levers"; breadth target; BRANCH_FIRE check; Phase 0b design-stage blind read; probe-band judge (J2) with JUDGE_MAP columns; per-row ownership (G1a); stated invocation (G8a); toy worked examples (W6); judge estimate in the cost table instead of a fixed 90.
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
  1. `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/_COMMON_RULES_v5.md`;
  2. `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/LEVER_RULES_v3.md` (THE authority for the determinate test, design shapes, hardness sources, levers, writing, grading, judge probe band, holes list, STACKING_CHECK and the probe gate);
  3. `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/LEAK_LIBRARY.md` (how our levers leaked; never repeat a row);
  4. `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/QC_RULINGS.md` (what QC accepted and rejected) and `QC_FIX_PLAYBOOK_v3.md` (same folder; how a QC finding is fixed without softening a lever);
  5. `knowledge/KNOWLEDGE.md` in the same `master_chat_tasks/` folder, and the check inventory `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261024_process/qc_reverse/A/checks.json` (pass condition and what each check does NOT require).
- Never commit, push, pull or open a PR. Read-only git only. Edit only BUNDLE, WORK and OUT. Never edit the harness clone, the QC kit, `QC assigned/`, `my tasks/`, `QC_*/bundles/` or the Anubis repo.

## Inputs
- SLUG: `[[SLUG]]`
- ARCHETYPE: `[[ARCHETYPE]]` (its fixed output files: [[ARTIFACTS]])
- CATEGORY: `[[CATEGORY]]` (generator `--category` key)
- SEED: `[[SEED]]`
- IDEA (accepted, with the master's gate notes): `[[IDEA_PATH]]`
- SHAPE (LEVER_RULES v3 section 1: B breadth or D degenerate shipped instance): [[SHAPE]]
- HARDNESS SOURCES (section 1A: one primary S1 or S2, plus at least one of S3, S5, S6; S7-S11 optional; levers L1-L11 and habits H1-H9 as building blocks; a set no live task already uses): [[SOURCES]]
- BREADTH TARGET (Shape B: at least 30 graded stated rules over at least 10 files in at least 5 formats, at least 15 rules each >= 3% alone; Shape D: at most 3 sharp rules, each >= 25% alone, hard branch never fires on shipped data): [[BREADTH_TARGET]]
- COUPLING (required, LEVER_RULES G1): one stated or determinate quantity computed from all records and carried into every row (an allocation, residual or metric), and the sentence that states it: [[COUPLING]]
- Master notes (changes to the idea, risks to watch): [[MASTER_NOTES]]
- TRUTH.md provenance rule: [[TRUTH_PROVENANCE_RULE]]
- BUNDLE: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/[[SLUG]]/`
- WORK: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/[[SLUG]]/`
- OUT (your report): `/Users/mac/Desktop/Terminal Bench/master_chat_work/[[DATE]]_[[SLUG]]/build/`

## Design rules
- Levers, writing, grading and judge follow LEVER_RULES_v3 sections 0b-4. Every rule of engagement is stated in a copied file (IN-15). A deliverable-property rule is either stated or settled by one determinate shipped fact listed in `WORK/EVIDENCE_MAP.md` (AL-1 05:21, LEVER_RULES 0b), never by silence (05:27). Every graded question has one reading (IN-16). No sentence announces what the input establishes (IN-17 01:47, W1). Difficulty comes from how rules are stated, where the evidence sits and how levers interact, never from silence (common rule Never 6) and never from explaining traps (common rule Never 8).
- The instruction states WHAT to build, completely and plainly, the output paths and whole-document exactness (G5); it states no rule of its own (W10). A pointer to the contract file is optional (01:45). No recipe.
- Each stated rule's wrong reading is an Opus habit from LEVER_RULES 1b (H1-H9: H8 first fit, H9 shipped-only self-test). Plain decoys, look-alike files, encodings and duplicate ids are noise only. A partial-authority decoy (a file demoted by its own header, with one named fact still live) is a hardness source (S5) and is graded on both sides.
- Do not make it hard by arithmetic, puzzles, formatting tricks, raw data volume, or hidden or ambiguous rules (LEVER_RULES v3 section 8: holes are not levers). Many plainly stated rules over many files and formats (Shape B) are allowed and preferred. Never state a size or runtime limit that hands over the exact method (cold-chain, registry/tasks.json:698).

## Phases (tick each in WORK/TODO.md; log each command in WORK/LOG.md)

**Phase 0: reflex pre-mortem and design, then STOP.**
1. Check the GEN and QC fingerprints (common rule 1).
2. Reflex pre-mortem (`WORK/PREMORTEM.md`, before any other file): write, step by step, how claude-opus-5 would solve this task in its first 10 minutes: which files it reads and in what order, the program it writes once, the self-tests it runs (shipped data, its own tiny examples, invariants), and its reading of every rule. Then, per rule or source, the exact point where that program goes wrong, and why none of its self-tests would catch it (assume it returns the first fitting candidate, H8, and never builds an input that fires a stated branch, H9). Then, per planned judge criterion, whether its trajectory would show the act. Our parked builds were transliterated in about 3 minutes (registry/tasks.json:707-734): any design whose first-write program is exact on shipped data AND on a fresh hidden seed is redesigned before Phase 1.
3. Write `WORK/DESIGN.md`. It must cover:
   - the spine stages;
   - every input file (format, rows, dependencies, at least three chains of length 4 or more);
   - for every graded rule (Shape B: the rule register with file:line per rule; Shape D: each sharp rule): the rule text and the file that governs it (W2), the reflex reading (from PREMORTEM), the constructed hidden cases, why the visible data cannot confirm it (W5, W6; for L11 the witness and UNIQUENESS plan), and how it interacts with the others; plus `WORK/BRANCH_FIRE.md` `| rule | branch | fires on shipped (count) | fires on hidden (seeds) |` (degenerate-shipped-instance check: in Shape D every hard branch has shipped count 0 and fires on every hidden corpus that grades it);
   - the rejection paths;
   - the test plan (LEVER_RULES v3 G1-G13: whole-document exact tests per output family and hidden corpus with exactness and the rerun promise stated in the instruction, per-row ownership G1a so one slip costs its rows once, visible then hidden `_hard`, amplification through the COUPLING quantity with every amplified slip tracing to a stated single-reading rule or an EVIDENCE_MAP fact, at least 2 mutation tests counted only where the plain hidden run is exact (G6), the G8 hidden tier with its own RNG stream for rare fixtures, the stated invocation (G8a), planned weight shares per G3 for the chosen shape) and the judge plan (J1-J10: the probe band with each probe's template id P-a to P-h and the requirement it serves, J3a-c, J4, J6, J10);
   - the expected loss per lever (which hidden input and check a careful solver loses).
   - the kill test (v5, LEVER_RULES v3.4 Law-1 filter): every plausible solver for the core (the strongest generic solvers, a plain first-write program) run on prototype hidden instances in Docker only (`docker run --rm --memory 4g --cpus 2`, wall cap `perl -e 'alarm N; exec @ARGV'`; common rule Always 16), recorded in `WORK/KILL_TEST.md` as `| solver | instance | seconds | WRONG / TIMEOUT / CRASH / EXACT | lever points kept |`. The lever passes only if every strong solver loses by WRONG (a valid but wrong document); a TIMEOUT or CRASH loss counts only under LEVER_RULES v3.5 (no shipped input slow, limit stated, cost 10-30% confined to lever checks; add column `shipped inputs fast`). [v3.6: Ayush 27 Oct 22:30, new gate tests < 85, rubric < 85, final < 50] See LEVER_RULES_v3 1C v3.6 bullet: a test lever now costs 25-40% of positive test points, and a plain first-write program and the all-but-one program aim at tests <= 75. Blind bar: each of the 3 fresh blind reads scores tests <= 80, its losses WRONG output or v3.5 hidden-scale loss. Judge: probe band with predicted probe mid 15-20. Overnight auto runs: the master may send "go" at DESIGN READY when the kill table passes (every generic solver and every blind program loses >= 15% of lever points, shipped inputs fast, reference <= 1/4 of the stated limit); otherwise Needs Ayush.
4. Write `WORK/QC_DEFENCE.md` (IMPROVEMENT_PLAN C1): one entry per lever and per cascade: the rule ids it touches (IN-15, IN-16, IN-17, AL-1, AL-27, CL-4, TS-13, TS-19, TS-20, TS-26, AL-28, JD-7, JD-15), the quoted live rule, why the design passes (reuse a QC_RULINGS PASS where one exists), and the safe fallback if QC still flags it: the QC_FIX_PLAYBOOK row id and its DO fix written out for this lever (file, change), never a NEVER-column fix.
5. Write `WORK/DESIGN_SUMMARY.md`, at most 40 lines, for the master chat.
6. Stop and say "DESIGN READY: <path to DESIGN_SUMMARY.md>". Wait until Ayush replies "go". If he passes on changes from the master chat, apply them first.

**Phase 0b: design-stage blind read, then STOP.** (after "go")
1. Write a small prototype: `WORK/proto/solve_proto.py` (the core rules only), `WORK/proto/gen_proto.py` (3 hidden seeds), a draft instruction.md, the rule register and the governing rule files, and a small shipped sample, all under `WORK/design_blind/` in the final layout (`instruction.md`, `environment/data/`).
2. Check BRANCH_FIRE on the sample and the 3 seeds with the prototype.
3. Stop and say "DESIGN BLIND READY: <WORK/design_blind path>". The master issues one P13 blind read on that folder.
4. When the master returns the blind program path, run it on the sample and the 3 seeds and diff against the prototype outputs; write `WORK/DESIGN_BLIND.md` (rules the blind program got wrong, with seed and first differing record, minutes to first full write, and its judge estimate). If the blind program is exact on the sample AND on all 3 seeds, redesign (back to Phase 0 step 3). Otherwise continue to Phase 1.

**Phase 1: scaffold.**
- Run, from GEN, with the common-rule environment variables:
  `python3 generate_bundle.py --out "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles" --name [[SLUG]] --archetype [[ARCHETYPE]] --category [[CATEGORY]] --seed [[SEED]] --title "<title>" --description "<one paragraph, at most 100 words>" --author "Ayush Sah <ayush.sah@ethara.ai>"`
- Copy the untouched scaffold to `WORK/scaffold_orig/` for reference.
- Never use `--force`.

**Phase 2: data and spec.**
- Write a seeded stdlib `WORK/datagen.py` that produces `BUNDLE/environment/data/`. Keep the data flat, with at least [[MIN_INPUTS]] files (Shape B: at least 10 governing files) in at least 5 formats and the planned chains. In Shape D the shipped instance must not fire any hard branch (BRANCH_FIRE shipped count 0). If the hidden generator re-renders rule documents per corpus, only the values change and the rule register lists them (W12).
- Every file must matter to a graded result.
- Volume must meet playground A5 (at least 20,000 lines in total, and at least 2,000 per csv, tsv, jsonl, txt or log file), but volume is not the difficulty.
- Write each rule in the spec or data-convention file that governs its data (W2, W3), every output key and every error string (DS-25). L1 controls are real and described in the file that defines them (W7). Overrides name the field exactly (W4). Separating cases ship only for L5 and, as one unlabelled witness, for L11 (W5). A rule may carry at most one worked example on invented toy values that appear in no shipped or hidden file and never says which case is tricky (W6 v3); no other worked example where the readings differ. Every shipped control reconciles under both readings (W7). A partial-authority decoy (S5) states its own demotion in its header and names the one fact that stays live.
- No answer for any graded document anywhere in `environment/` (W11): no answer keys, golden or sample outputs, solved lists, expected figures or claimed totals, even ones that agree with the contract.

**Phase 3: reference solution.**
- Write `solution/solve.py` and `solve.sh` from the written contract, not from the test code. Keep shared lines with `test_output.py` well under 20%, and solve.py at 30 or more substantive lines.
- It must be deterministic, offline, and run as uid 1000.
- Write `WORK/check_exact.py`, which recomputes the outputs a second, independent way from the visible documents only (never from solve.py), with a per-record diff and policy-invariant asserts (G9). For every footnote, erratum or correction mechanism, run an override-removal probe: drop it and show the oracle's output moves.

**Phase 4: tests (`tests/test_output.py`), per LEVER_RULES section 3.**
- Generate the hidden inputs verifier-side from an embedded seeded generator whose seed lives only in `tests/`; seeds change every named release literal; rare-branch and tie fixtures use their own RNG stream (G8). Run the agent's delivered program on them as a foreign uid from a foreign working directory, with `--prior` = its own shipped outputs where the task has periods, using exactly the command instruction.md states (interpreter, flags, cwd, arguments; no unstated `python -I`) (G8a). No shared mutable cache across tests (G12). No slug or author string inside SHA-pinned test text.
- G1/G1a/G2: whole-document exact tests per output family and hidden corpus, allowed because instruction.md states that only an exact match counts (CL-4 exemption FC:491, quoted in QC_DEFENCE); report the one-fact-wrong score anyway. Every output row or byte is owned by exactly one test (`OWNED` map, shared columns masked outside their owner); a test that compared nothing never passes. At most one stated cross-corpus gate per task, with its sentence in instruction.md; the related QC checks (CL-4, TS-19, AL-28) must pass and every key, field and value form any test reads must be named somewhere in the shipped contract (minimal explanation is fine); never grade a key the agent cannot read (G1, QL 26 Oct). Message shows the first differing path. Amplification comes from the COUPLING quantity and from whole documents. No test returns early on another test's scalar.
- G3 by shape: Shape D at least 70% of positive weight on generated hidden corpora; Shape B no floor; every shape at least one hidden rerun per output family; shares measured through the call graph, not test names. G6: at least 2 mutation tests from the stock recipes, each counted only on corpora where the plain hidden run of the same family is exact. G7: first differing path in every assertion message. Literal-reading self-test per rule sentence (W9) before writing tests.
- Write the wrong implementation for each lever and confirm it loses that lever's points. A check that no wrong implementation fails is worthless.
- G10 cost table: `WORK/COST_TABLE.md`, one row per rule (Shape B) or lever (Shape D): wrong reading injected alone into a patched copy of solve.py, real tests, test points lost; plus one "all but this one right" row with predicted final = (tests + design judge estimate) / 2, using the judge mid estimate from JUDGE_MAP (probes at 25%), never a fixed 90; plus the one-fact-wrong score per rule (CL-4). Gate Shape B: at least 15 rules each >= 3% and the 15 smallest rows sum to >= 40%. Gate Shape D: every lever alone >= 25%. Both: every "all but one" row final < 70. Fix a failing row before Phase 5. These are design numbers, not hardness evidence.
- G11 rule coverage: `WORK/RULE_COVERAGE.md`, header `| rule | file:line | mutant | tests failed |`, one row per AL-2 unit (each instruction.md promise plus each delegated rule it invokes, 05:33) and per ordering, precedence or tie-break the shipped input establishes (05:38), each mutant dropping that rule alone; every row fails at least 1 test, else add a hidden-tier fixture or drop the rule. precheck.sh fails a 0 row.
- G12: the embedded generator asserts every drawn value is inside the contract's stated bounds (TS-19); it plants every branch of each multi-branch rule on some seed (template master_chat_work/20261024_process/test_depth/kit/fam/cm_family.py), and the reference plus generator survive 300 seeds over the contract bounds with no crash or endless loop. No contract sentence lists the malformed values of a typed field (precheck LV-ENUM).
- Weights: 5 core, 3 sub-goal, 1 existence only (TS-20). At least 10 checks and at least 8 judge criteria, no upper cap (Ayush 24 Oct). Above 35 checks the kit prints WARN A3: record it, never merge lever checks to get under 35.
- G4 negatives: only cheating acts, grouped by act, <= 5 per act across tests and judge (AL-28). No negative grades a lever, no wrong-reading detector, no negative that depends on the program's exit code alone.
- No positive check may pass on an absence, and no two checks may read the same observable with the same logic (TS-26).
- EVIDENCE_MAP: `WORK/EVIDENCE_MAP.md` `| rule | test ids | shipped fact file:line | wrong readings it contradicts |` for every graded rule with no sentence; for each L11 lever also `WORK/UNIQUENESS.md` (every candidate reading fitted to every shipped and hidden witness, exactly one fits).
- Write `WORK/LEVERS.md`: one row per check, with its lever ids and weight, plus the weight total per lever.
- Re-embed the data, and write `reward.toml` (common rule 6).

**Phase 5: judge (`tests/judge.toml`), per LEVER_RULES section 4.**
- J1 no figure criterion of any kind. J2 probe band: 8-16 criteria, each w3, importance "important", type "process", evaluation_target "trajectory", 55-70% of positive judge weight, each filled from one template P-a to P-h (edge-input run, one-instance witness, recompute outside the program per artifact type, altered-copy rerun, relocated rerun, broken tool run before the first edit, uniqueness witness, missing or malformed input run), each naming the requirement it serves (04:92), each performed by a solve.sh self-check stage that prints `check <id> ok` and one witness line (JD-7 kept; QL 26 Oct: a trajectory criterion is allowed only when the oracle shows it); obey every J2b guard. J3a claim-without-run -3, J3b figure differs from delivered file -5 (final_answer), J3c overstated check size -3 when relevant. J4 exactly one behavioural code-quality criterion (every exception handler acts on the error it catches; a missing or malformed declared input stops the run with a message naming the file), met by solve.py line by line (JD-18). J5 no criterion endorses a reading the tests penalise. J6 one per-item enumeration criterion on the final answer. J7 deterministic artifact behaviour is a test. J8 no rule-restating method steps. J10 one instruction-following criterion per stated process rule (order w3, work directory -1), at most 2, quoting the sentence. `[judge] mode = "batched"`. Never echo probe wording in instruction.md.
- Write `WORK/JUDGE_MAP.md` (`| id | template | requirement it serves (sentence file:line) | oracle shows it at (solve.sh line / printed check) | test it must not overlap | expected Opus PASS? |`), then the band totals: probe count, probe share of positive weight, and the judge lower, mid and upper estimate for an Opus-like agent (LEVER_RULES v3 section 6). Remove any criterion with no oracle-shows entry. Never add annotation keys (judge_qc J6).
- Each criterion is true for any correct solution and met by every competent approach (JD-7, JD-15), reads nothing a test reads (JD-8), uses positive grammar starting "The agent" or "The response", and counts instead of "some".
- Keep the five-key header exactly.

**Phase 6: instruction.md.**
- Rewrite it fully. The scaffold sentence has blank words in 4 archetypes.
- Plain English; a pointer to the contract file is optional (01:45). Name every output path once.
- State whole-document exactness up front (G5), e.g. "each output document is graded whole on fresh inputs, and only an exact match counts", and the rerun promise: the program is run again on fresh inputs in the same layout; mention only what is necessary and give no list of the axes that change (QL 26 Oct: naming them is allowed by QC but off by default). State the exact command the program is run with (G8a) and the rules of engagement (work directory, process order, files that may change) (W10). Never add "at other scales", "there is no count to check yourself against" or a self-check paragraph. Where useful: one arbiter sentence naming which document wins when documents disagree (W8); the full output schema or the file that holds it.
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
3b. Stage-2 self-checks before QC (v5; write each table to `WORK/SELF_CHECKS.md`; any FAIL row is fixed before step 4):
   - DS-22 / AL-18: recompute every digest, count, weight total and line cite in TRUTH.md by script.
   - TS-13: list every check that opens 2 or more `/app/out/*` files or calls 2 or more rebuild or run helpers; split or justify each.
   - CL-2 vacuity probe: run the unedited shipped tool and data through every positive test check by script (any pass = FAIL); read every positive judge criterion and fail any that an agent who changed nothing would earn.
   - TS-16: every negative stays silent on the oracle and on 2 honest variants (named in the table).
   - Promise table: every instruction.md sentence -> the check or criterion id that grades it; an empty row = FAIL (AL-2, STEP11, TS-19).
   - Literal table: every literal the oracle emits is STATED (file:line) or DERIVABLE (how); UNREACHABLE or INVENTED = FAIL (DS-21, DS-25, CL-10).
   - Judge: the J3a honesty negative is present (claims a check passed, or outputs byte-identical, with no run after the last edit; -3; disjoint from every other negative, AL-28); a type/target table per criterion (JD-15); one verb clause per criterion (JD-5).
4. `tools/precheck.sh BUNDLE` until its last line is `PRECHECK CLEAN` (common rule Always 10). No reflex gate: hardness is decided by 3 blind reads (tests and judge estimate) and the probe run the master queues next (LEVER_RULES v3 section 6). Write in DESIGN.md, per rule, the hidden input and check where a careful solver is expected to lose points, and per probe criterion whether Opus is expected to show it, so the probe's `loss.py` table can be compared with it.

**Phase 9: report.** Write `OUT/BUILD_REPORT.md` with: the tree and file counts; data formats, line counts and chains; the lever table (from LEVERS.md) with where each rule is written; weight shares; every script, validator and playground result; oracle and nop; the stacking verdict; the PRECHECK last line; the expected loss per lever; open conflicts; anything not run; and, last, `## Lessons for the master` (max 5 lines).

## Deliverables
- `OUT/BUILD_REPORT.md`, `OUT/STACKING_CHECK.md`, `WORK/PREMORTEM.md`, `WORK/DESIGN.md`, `WORK/DESIGN_BLIND.md`, `WORK/BRANCH_FIRE.md`, `WORK/LEVERS.md`, `WORK/QC_DEFENCE.md`, `WORK/COST_TABLE.md`, `WORK/RULE_COVERAGE.md`, `WORK/RULE_TRACE.md` (one row per generator branch: the sentence and file:line that states it), `WORK/EVIDENCE_MAP.md` (and `WORK/UNIQUENESS.md` per L11 lever or S3 candidate space), `WORK/JUDGE_MAP.md`.
- `OUT/result_[[SHA]].json`: {"sha":"[[SHA]]","slug":"[[SLUG]]","step":"P2","status":"DONE|BLOCKED|PILOT_WEAK","shape":"B|D","sources":[],"rules_graded":N,"files":N,"formats":N,"levers":[],"tests":N,"criteria":N,"probes":N,"probe_share":x,"judge_estimate":{"lower":x,"mid":x,"upper":x},"design_blind":"<rules missed>/<rules>","isolated_share":x,"whole_doc_share":x,"shipped_only_share":x,"precheck":"CLEAN|<n> findings","expected_loss":{"<lever>":"<check ids>"},"cost_table":{"<lever>":{"alone_pct":x,"all_but_one_overall":x}},"rules_uncovered":0,"stacking":"PASS|FAIL","oracle":[],"nop":x,"qc_fail":0,"tree_sha":"<sha256 over sorted paths+contents, first 12>","report":"<path>"}. The `sha` value is the board id. It must parse.

## Done when
- The bundle exists, all 4 QC scripts show 0 FAIL, the validator passes, and the A5 line count meets the volume rule.
- Oracle x3 1.0 and nop 0.0 on the tests channel; STACKING PASS; PRECHECK CLEAN.
- LEVERS.md covers every check; QC_DEFENCE.md covers every lever.
- Nothing was written inside GEN or QC (fingerprints re-checked).

Final reply (common rule, 10 lines max): DONE, BLOCKED or PILOT WEAK; levers and where each rule is written; check and criterion counts; weight shares; PRECHECK last line; stacking result; oracle; open conflicts; report path. Next step (v5 order): master issues 3 fresh P13 blind reads (the round counts only if they lose >= 10% of positive test points by WRONG output; each reports a judge estimate; redesign, never park, if the lower-bound final is above 70 on 2 of 3), then one full QC (P11 v3 MODE full) with a fix-all pass, QC recheck rounds, freeze, then 1 harness run on the frozen bytes.
