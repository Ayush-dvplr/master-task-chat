# TEMPLATE_CHANGES (board 720e1d7, 26 Oct 2026)

How to apply: for each template, copy it to the new file name given, then replace each OLD line (by its line number in the CURRENT file) with the NEW text. "INSERT AFTER n" adds lines after old line n. Apply edits bottom-up inside each file so line numbers stay valid. Every edit points at the rule in `LEVER_RULES_v3_DRAFT.md` (here "v3") or a row in `CONFLICTS.md` (here "C<n>"). Lines that depend on an open decision are marked `[PENDING Ayush D<n>]` or `[PENDING QL Q<n>]` (numbers as in SUMMARY.md); apply those only after the answer, otherwise keep the old line.

Add one CHANGELOG line in `prompts/templates/CHANGELOG.md`:
`26 Oct (board 720e1d7): LEVER_RULES_v3 (shapes B/D, hardness sources S1-S11, probe-band judge, per-row ownership, stated invocation, blind judge estimate); P2_build_v4, P9_harden_from_results_v3, P13_blind_solve_v2, P1_chatgpt_ideas_v3, _COMMON_RULES_v4. Evidence: delivery_study2 g1-g4 + synthesis_720e1d7.`

---

## 1. `_COMMON_RULES_v3.md` -> `_COMMON_RULES_v4.md`

**Line 1**
- OLD: `# Common rules for every session started from a master-chat prompt (v3, 24 Oct 2026; in place 25 Oct: LEVER_RULES_v2, Never 6/8/11 for QC push 5574d77e IN-17 and determinate evidence, probe gate; v2 + plan v1 Part 1 corrections: precheck.sh, no count caps and genuine-minimum warns (24 Oct 12:50), IN-15 scope, author-note gate, judge lint, stop at PASS, fix side effects, generator diff)`
- NEW: `# Common rules for every session started from a master-chat prompt (v4, 26 Oct 2026: LEVER_RULES_v3, probe-band judge, toy worked examples, final-reward gate, blind judge estimate; v3 24-25 Oct: LEVER_RULES_v2, Never 6/8/11 for QC push 5574d77e IN-17 and determinate evidence, probe gate; v2 + plan v1 Part 1 corrections: precheck.sh, no count caps and genuine-minimum warns (24 Oct 12:50), IN-15 scope, author-note gate, judge lint, stop at PASS, fix side effects, generator diff)`

**Line 10**
- OLD: `- LEVER_RULES (determinate test 0b, levers L1-L11 and habit bank H1-H6, writing W1-W11, grading G1-G12, judge J1-J9, probe gate section 6): \`/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/LEVER_RULES_v2.md\` (v1 superseded 25 Oct). Read it by path; never copy it into a bundle or report.`
- NEW: `- LEVER_RULES (determinate test 0b, design shapes B and D, hardness sources S1-S11, levers L1-L11 and habit bank H1-H9, writing W1-W12, grading G1-G13, judge J1-J10 with the probe band, holes list section 8, probe gate section 6): \`/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/LEVER_RULES_v3.md\` (v2 superseded 26 Oct). Read it by path; never copy it into a bundle or report.`

**Line 27** (Never 8; W1 kept, C6; rerun promise allowed, C13)
- OLD: `8. Explain a trap in any agent-visible file (W1, hard rule; QC IN-17 01:47 fails the same act). No "not only X", no "note that", no "be careful", no trap lists, no rule counts in the instruction, no sentence that names the wrong reading, and no sentence announcing a property, edge case or branch the shipped input already establishes. State the rule; never state how it is usually misread. No self-check paragraph and no "at other scales" in the instruction (LEVER_RULES G5).`
- NEW: `8. Explain a trap in any agent-visible file (W1, hard rule; QC IN-17 01:47 fails the same act). No "not only X", no "note that", no "be careful", no trap lists, no rule counts in the instruction, no sentence that names the wrong reading, and no sentence announcing a property, edge case or branch the shipped input already establishes. State the rule; never state how it is usually misread. No self-check paragraph in the instruction. Allowed and required: the G5 rerun promise (the program runs again on fresh inputs of the same layout, and which axes change), stated without naming any branch as tricky (LEVER_RULES v3 G5). [PENDING QL Q4 for the "which axes change" clause]`

**Line 30** (W6 toy examples, C7)
- OLD: `11. Ship any answer for a graded document in \`environment/\` (LEVER_RULES W11): no answer key, golden or sample output, solved list, expected figure or claimed total, even one that agrees with the contract. Shipped controls reconcile under both readings (W7); the only exception is one unlabelled L11 witness per lever. Never ship an oracle that contradicts any sentence of the written contract (wafer 32.58 pts; dispatch QC v6 DS-20).`
- NEW: `11. Ship any answer for a graded document in \`environment/\` (LEVER_RULES W11): no answer key, golden or sample output, solved list, expected figure or claimed total, even one that agrees with the contract. Shipped controls reconcile under both readings (W7). Exceptions: one unlabelled L11 witness per lever, and at most one toy worked example per rule on invented values that appear in no shipped or hidden file (W6 v3). Never ship an oracle that contradicts any sentence of the written contract (wafer 32.58 pts; dispatch QC v6 DS-20).`

**Line 50** (J1, C8)
- OLD: `- J1 lint: no criterion restating a figure an output file holds; final-reply criteria are fine; what-if figures in no output file only per LEVER_RULES J1 (solve.py prints them, the verifier recomputes them, max 6, w <= 3 each, with a conduct criterion on that rerun).`
- NEW: `- J1 lint: no figure criterion at all (output-file figure, final-reply figure or what-if figure); Opus answers them right and they add nothing (LEVER_RULES v3 J1). A figure enters the judge only inside the honesty negative J3b ("states a figure that differs from the delivered file").`

**Line 51** (J3, J4)
- OLD: `- Every judge.toml has one honesty negative (J3, w -3 to -5) and, when the deliverable is code, exactly one concrete code-quality criterion (J4). No criterion restates a method a test grades (J8). precheck.sh flags a missing J3 or J4.`
- NEW: `- Every judge.toml has the honesty negatives J3a (claim without a run, -3) and J3b (figure differs from delivered file, -5), J3c when the response describes a check's size, and, when the deliverable is code, exactly one behavioural code-quality criterion (J4 v3: every handler acts on the error it catches; a missing or malformed declared input stops the run with a message naming the file). No criterion restates a method a test grades (J8). precheck.sh flags a missing J3a, J3b or J4.`

**Line 53** (J2 probe band, C1)
- OLD: `- A conduct criterion stays only if the oracle trajectory can actually show it (JD-7); otherwise drop it.`
- NEW: `- Judge half = probe band (LEVER_RULES v3 J2): 8-16 probe criteria, w3, type process, evaluation_target trajectory, 55-70% of positive judge weight, each from templates P-a to P-h and each avoiding the J2b guards. Every probe act is performed by solve.sh's self-check stage, which prints \`check <id> ok\` and one witness line; a criterion with no oracle-shows row in \`WORK/JUDGE_MAP.md\` is removed (JD-7 04:76 kept). [If QL Q1 answers yes: acts the oracle cannot show may stay, but only at w1 and never more than 3.]`

**Line 59** (final gate, C16)
- OLD: `- Gate for real model runs (test phase, Ayush 23 Oct 09:33): tests < 100, rubric < 100, overall < 70, on 2 runs before PL. Since overall is the mean of tests and rubric, overall < 70 needs tests < 140 - rubric (rubric 90 needs tests < 50).`
- NEW: `- Gate for real model runs (Ayush 26 Oct, D2): final reward < 70 on 2 valid runs before PL; tests 100 is allowed when the judge half keeps the final below 70. Final = (tests + rubric) / 2, so final < 70 needs rubric < 140 - tests (tests 100 needs rubric < 40; tests 90 needs rubric < 50). [PENDING Ayush D2; until then keep the old line]`

**Line 62** (blind judge estimate, variance band C9)
- OLD: `- Hardness is proved by a real probe run on the harness, which the master queues, scored per check by \`tools/loss.py\`, after 3 blind reads (LEVER_RULES section 6: a lever counts only when at least 2 of 3 blind programs get it wrong). Reflex programs, per-lever solvers and differential fuzz of an old program on a changed bundle are not hardness evidence. Harden decisions: 1 run plus blind reads; final gate: 2 runs. Kill rule (Ayush 26 Oct): park when the probe's final reward (tests and judge combined) is above 70; tests alone never park a task; no round after a round marked LAST.`
- NEW: `- Hardness is proved by a real probe run on the harness, which the master queues, scored per check by \`tools/loss.py\`, after 3 blind reads (LEVER_RULES v3 section 6: a rule counts only when at least 2 of 3 blind programs get it wrong; each blind read also reports a judge estimate with lower and upper bounds; park at design when the lower-bound final is above 70 on 2 of 3). A design-stage blind read runs before the full build (P2 Phase 0b). Reflex programs, per-lever solvers and differential fuzz of an old program on a changed bundle are not hardness evidence. Harden decisions: 1 run plus blind reads; final gate: 2 runs. Kill rule (Ayush 26 Oct): park when the probe's final reward (tests and judge combined) is above 70; tests alone never park a task; single runs swing about 20 test points (G13), so a final between 65 and 75 gets a second probe and parks when the mean is above 70 [PENDING Ayush D3]; no round after a round marked LAST.`

---

## 2. `P2_build_v3.md` -> `P2_build_v4.md`

**INSERT AFTER 5**
- NEW: `v4 (26 Oct, board 720e1d7, delivery_study2 g1-g4): LEVER_RULES_v3; pick a design shape (B breadth or D degenerate instance) plus hardness sources S1-S11 instead of ">= 3 independent levers"; breadth target; BRANCH_FIRE check; Phase 0b design-stage blind read; probe-band judge (J2) with JUDGE_MAP columns; per-row ownership (G1a); stated invocation (G8a); toy worked examples (W6); judge estimate in the cost table instead of a fixed 90.`

**Line 23**
- OLD: `  2. \`/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/LEVER_RULES_v2.md\` (THE authority for the determinate test, levers, writing, grading, judge, STACKING_CHECK and the probe gate);`
- NEW: `  2. \`/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/LEVER_RULES_v3.md\` (THE authority for the determinate test, design shapes, hardness sources, levers, writing, grading, judge probe band, holes list, STACKING_CHECK and the probe gate);`

**Line 35** (C3, C12)
- OLD: `- LEVERS (at least 3 independent levers from LEVER_RULES section 1, at least 2 of L1-L3 or the 1b habit bank H1-H6 (H7 retired; L11 only when the master names it as a pilot), a set no live task already uses): [[LEVERS]]`
- NEW (3 lines):
  - `- SHAPE (LEVER_RULES v3 section 1: B breadth or D degenerate shipped instance): [[SHAPE]]`
  - `- HARDNESS SOURCES (section 1A: one primary S1 or S2, plus at least one of S3, S5, S6; S7-S11 optional; levers L1-L11 and habits H1-H9 as building blocks; a set no live task already uses): [[SOURCES]]`
  - `- BREADTH TARGET (Shape B: at least 30 graded stated rules over at least 10 files in at least 5 formats, at least 15 rules each >= 3% alone; Shape D: at most 3 sharp rules, each >= 25% alone, hard branch never fires on shipped data): [[BREADTH_TARGET]]`

**Line 46** (C11)
- OLD: `- Each stated lever's wrong reading is an Opus habit from LEVER_RULES 1b (H1-H6). Decoys, look-alike files, encodings and duplicate ids are noise only, never a scoring lever.`
- NEW: `- Each stated rule's wrong reading is an Opus habit from LEVER_RULES 1b (H1-H9: H8 first fit, H9 shipped-only self-test). Plain decoys, look-alike files, encodings and duplicate ids are noise only. A partial-authority decoy (a file demoted by its own header, with one named fact still live) is a hardness source (S5) and is graded on both sides.`

**Line 47** (C12)
- OLD: `- Do not make it hard by volume, arithmetic, puzzles, formatting, or hidden or ambiguous rules.`
- NEW: `- Do not make it hard by arithmetic, puzzles, formatting tricks, raw data volume, or hidden or ambiguous rules (LEVER_RULES v3 section 8: holes are not levers). Many plainly stated rules over many files and formats (Shape B) are allowed and preferred. Never state a size or runtime limit that hands over the exact method (cold-chain, registry/tasks.json:698).`

**Line 53** (pre-mortem; add H8/H9 and judge)
- OLD: `2. Reflex pre-mortem (\`WORK/PREMORTEM.md\`, before any other file): write, step by step, how claude-opus-5 would solve this task in its first 10 minutes: which files it reads and in what order, the program it writes once, the self-tests it runs (shipped data, its own tiny examples, invariants), and its reading of every rule. Then, per lever, the exact point where that program goes wrong, and why none of its self-tests would catch it. Any lever its first-write program would get right is redesigned before Phase 1.`
- NEW: `2. Reflex pre-mortem (\`WORK/PREMORTEM.md\`, before any other file): write, step by step, how claude-opus-5 would solve this task in its first 10 minutes: which files it reads and in what order, the program it writes once, the self-tests it runs (shipped data, its own tiny examples, invariants), and its reading of every rule. Then, per rule or source, the exact point where that program goes wrong, and why none of its self-tests would catch it (assume it returns the first fitting candidate, H8, and never builds an input that fires a stated branch, H9). Then, per planned judge criterion, whether its trajectory would show the act. Our parked builds were transliterated in about 3 minutes (registry/tasks.json:707-734): any design whose first-write program is exact on shipped data AND on a fresh hidden seed is redesigned before Phase 1.`

**Line 57** (BRANCH_FIRE, W5 v3)
- OLD: `   - for every lever: the rule text and the file that governs it (W2), the reflex reading (from PREMORTEM), the constructed hidden cases, why the visible data cannot confirm it (W5, W6; for L11 the witness and UNIQUENESS plan), and how it interacts with the other levers;`
- NEW: `   - for every graded rule (Shape B: the rule register with file:line per rule; Shape D: each sharp rule): the rule text and the file that governs it (W2), the reflex reading (from PREMORTEM), the constructed hidden cases, why the visible data cannot confirm it (W5, W6; for L11 the witness and UNIQUENESS plan), and how it interacts with the others; plus \`WORK/BRANCH_FIRE.md\` \`| rule | branch | fires on shipped (count) | fires on hidden (seeds) |\` (degenerate-shipped-instance check: in Shape D every hard branch has shipped count 0 and fires on every hidden corpus that grades it);`

**Line 59** (test plan)
- OLD: `   - the test plan (LEVER_RULES G1-G9: whole-document exact tests per hidden corpus with exactness stated in the instruction, or owned-row tests per trap family as the CL-4 fallback, visible then hidden \`_hard\`, amplification through the COUPLING quantity with every amplified slip tracing to a stated single-reading rule or an EVIDENCE_MAP fact, at least 2 mutation tests from the G6 stock recipes, the G8 hidden tier, planned weight shares) and the judge plan (J1-J9);`
- NEW: `   - the test plan (LEVER_RULES v3 G1-G13: whole-document exact tests per output family and hidden corpus with exactness and the rerun promise stated in the instruction, per-row ownership G1a so one slip costs its rows once, visible then hidden \`_hard\`, amplification through the COUPLING quantity with every amplified slip tracing to a stated single-reading rule or an EVIDENCE_MAP fact, at least 2 mutation tests counted only where the plain hidden run is exact (G6), the G8 hidden tier with its own RNG stream for rare fixtures, the stated invocation (G8a), planned weight shares per G3 for the chosen shape) and the judge plan (J1-J10: the probe band with each probe's template id P-a to P-h and the requirement it serves, J3a-c, J4, J6, J10);`

**INSERT AFTER 63** (Phase 0b design-stage blind read)
- NEW:
  - `**Phase 0b: design-stage blind read, then STOP.** (after "go")`
  - `1. Write a small prototype: \`WORK/proto/solve_proto.py\` (the core rules only), \`WORK/proto/gen_proto.py\` (3 hidden seeds), a draft instruction.md, the rule register and the governing rule files, and a small shipped sample, all under \`WORK/design_blind/\` in the final layout (\`instruction.md\`, \`environment/data/\`).`
  - `2. Check BRANCH_FIRE on the sample and the 3 seeds with the prototype.`
  - `3. Stop and say "DESIGN BLIND READY: <WORK/design_blind path>". The master issues one P13 blind read on that folder.`
  - `4. When the master returns the blind program path, run it on the sample and the 3 seeds and diff against the prototype outputs; write \`WORK/DESIGN_BLIND.md\` (rules the blind program got wrong, with seed and first differing record, minutes to first full write, and its judge estimate). If the blind program is exact on the sample AND on all 3 seeds, redesign (back to Phase 0 step 3). Otherwise continue to Phase 1.`

**Line 72** (formats)
- OLD: `- Write a seeded stdlib \`WORK/datagen.py\` that produces \`BUNDLE/environment/data/\`. Keep the data flat, with at least [[MIN_INPUTS]] files in at least 5 formats and the planned chains.`
- NEW: `- Write a seeded stdlib \`WORK/datagen.py\` that produces \`BUNDLE/environment/data/\`. Keep the data flat, with at least [[MIN_INPUTS]] files (Shape B: at least 10 governing files) in at least 5 formats and the planned chains. In Shape D the shipped instance must not fire any hard branch (BRANCH_FIRE shipped count 0). If the hidden generator re-renders rule documents per corpus, only the values change and the rule register lists them (W12).`

**Line 75** (W5/W6)
- OLD: `- Write each rule in the spec or data-convention file that governs its data (W2, W3), every output key and every error string (DS-25). L1 controls are real and described in the file that defines them (W7). Overrides name the field exactly (W4). Separating cases ship only for L5 and, as one unlabelled witness, for L11 (W5). No worked example where the readings differ (W6). Every shipped control reconciles under both readings (W7).`
- NEW: `- Write each rule in the spec or data-convention file that governs its data (W2, W3), every output key and every error string (DS-25). L1 controls are real and described in the file that defines them (W7). Overrides name the field exactly (W4). Separating cases ship only for L5 and, as one unlabelled witness, for L11 (W5). A rule may carry at most one worked example on invented toy values that appear in no shipped or hidden file and never says which case is tricky (W6 v3); no other worked example where the readings differ. Every shipped control reconciles under both readings (W7). A partial-authority decoy (S5) states its own demotion in its header and names the one fact that stays live.`

**Line 84** (G8a)
- OLD: `- Generate the hidden inputs verifier-side from an embedded seeded generator whose seed lives only in \`tests/\`; seeds change every named release literal. Run the agent's delivered program on them as a foreign uid from a foreign working directory, with \`--prior\` = its own shipped outputs where the task has periods (G8). No slug or author string inside SHA-pinned test text.`
- NEW: `- Generate the hidden inputs verifier-side from an embedded seeded generator whose seed lives only in \`tests/\`; seeds change every named release literal; rare-branch and tie fixtures use their own RNG stream (G8). Run the agent's delivered program on them as a foreign uid from a foreign working directory, with \`--prior\` = its own shipped outputs where the task has periods, using exactly the command instruction.md states (interpreter, flags, cwd, arguments; no unstated \`python -I\`) (G8a). No shared mutable cache across tests (G12). No slug or author string inside SHA-pinned test text.`

**Line 85** (G1a)
- OLD: `- G1/G2: whole-document exact tests per output document and hidden corpus, allowed because instruction.md states that only an exact match counts (CL-4 exemption FC:491, quoted in QC_DEFENCE); report the one-fact-wrong score anyway. Owned-row tests per trap family are the fallback if QC still fails CL-4. Message shows the first differing path. Amplification comes from the COUPLING quantity and from whole documents. No test returns early on another test's scalar.`
- NEW: `- G1/G1a/G2: whole-document exact tests per output family and hidden corpus, allowed because instruction.md states that only an exact match counts (CL-4 exemption FC:491, quoted in QC_DEFENCE); report the one-fact-wrong score anyway. Every output row or byte is owned by exactly one test (\`OWNED\` map, shared columns masked outside their owner); a test that compared nothing never passes. No cross-corpus gate unless QL Q3 says yes and instruction.md states it word for word (G1). Message shows the first differing path. Amplification comes from the COUPLING quantity and from whole documents. No test returns early on another test's scalar.`

**Line 86** (G3, G6)
- OLD: `- G3: hidden or mutated reruns >= 30% of positive weight, at least one per downstream document family; no shipped-data cap; isolated checks optional. G6: at least 2 mutation tests from the stock recipes. G7: first differing path in every assertion message. Literal-reading self-test per rule sentence (W9) before writing tests.`
- NEW: `- G3 by shape: Shape D at least 70% of positive weight on generated hidden corpora; Shape B no floor; every shape at least one hidden rerun per output family; shares measured through the call graph, not test names. G6: at least 2 mutation tests from the stock recipes, each counted only on corpora where the plain hidden run of the same family is exact. G7: first differing path in every assertion message. Literal-reading self-test per rule sentence (W9) before writing tests.`

**Line 88** (G10)
- OLD: `- G10 cost table: \`WORK/COST_TABLE.md\`, one row per lever (wrong reading injected alone into a patched copy of solve.py, real tests, test points lost) plus one "all but this lever right" row with predicted overall, plus the one-fact-wrong score per lever (CL-4). Every lever alone >= 25% of test points; every "all but one" row overall < 70. Fix a failing lever before Phase 5. These are design numbers, not hardness evidence.`
- NEW: `- G10 cost table: \`WORK/COST_TABLE.md\`, one row per rule (Shape B) or lever (Shape D): wrong reading injected alone into a patched copy of solve.py, real tests, test points lost; plus one "all but this one right" row with predicted final = (tests + design judge estimate) / 2, using the judge mid estimate from JUDGE_MAP (probes at 25%), never a fixed 90; plus the one-fact-wrong score per rule (CL-4). Gate Shape B: at least 15 rules each >= 3% and the 15 smallest rows sum to >= 40%. Gate Shape D: every lever alone >= 25%. Both: every "all but one" row final < 70. Fix a failing row before Phase 5. These are design numbers, not hardness evidence.`

**Line 92** (G4)
- OLD: `- G4 negatives: only cheating acts, grouped by act, <= 5 per act across tests and judge (AL-28). No negative grades a lever.`
- NEW: `- G4 negatives: only cheating acts, grouped by act, <= 5 per act across tests and judge (AL-28). No negative grades a lever, no wrong-reading detector, no negative that depends on the program's exit code alone.`

**Line 99** (judge, J1-J10)
- OLD: `- J1 no criterion restating an output-file figure (final-reply criteria are fine; what-if figure criteria for rerun figures in no output file only when solve.py prints them and the verifier recomputes them, max 6, w <= 3 each, with a conduct criterion on that rerun); J2 conduct criteria "independently recomputes <graded figure> outside its program for every <run/class/item> and compares", one w3 per output family, 6-20 in total, each performed by a solve.sh self-check stage that prints \`check <id> ok\` (JD-7 kept); J3 mandatory honesty negative w -3 to -5 ("claims a check passed with no run after its last edit that shows it"); J4 exactly one code-quality criterion with concrete conditions (no bare or pass-only except, no function over about 150 lines, no dead code) (JD-18); J5 no criterion endorses a reading the tests penalise; J6 one per-item enumeration criterion on the final answer; J7 deterministic artifact behaviour is a test, never a criterion; J8 no criterion restates a method a test grades; J9 one w3 criterion "runs its program on a copy of the data whose contents it altered (not only relocated) and checks that the dependent figures move", performed by the self-check stage; \`[judge] mode = "batched"\`. Never echo J2 or J9 wording in instruction.md.`
- NEW: `- J1 no figure criterion of any kind. J2 probe band: 8-16 criteria, each w3, importance "important", type "process", evaluation_target "trajectory", 55-70% of positive judge weight, each filled from one template P-a to P-h (edge-input run, one-instance witness, recompute outside the program per artifact type, altered-copy rerun, relocated rerun, broken tool run before the first edit, uniqueness witness, missing or malformed input run), each naming the requirement it serves (04:92), each performed by a solve.sh self-check stage that prints \`check <id> ok\` and one witness line (JD-7 kept); obey every J2b guard. J3a claim-without-run -3, J3b figure differs from delivered file -5 (final_answer), J3c overstated check size -3 when relevant. J4 exactly one behavioural code-quality criterion (every exception handler acts on the error it catches; a missing or malformed declared input stops the run with a message naming the file), met by solve.py line by line (JD-18). J5 no criterion endorses a reading the tests penalise. J6 one per-item enumeration criterion on the final answer. J7 deterministic artifact behaviour is a test. J8 no rule-restating method steps. J10 one instruction-following criterion per stated process rule (order w3, work directory -1), at most 2, quoting the sentence. \`[judge] mode = "batched"\`. Never echo probe wording in instruction.md.`

**Line 100** (JUDGE_MAP)
- OLD: `- Write \`WORK/JUDGE_MAP.md\` (\`| id | oracle shows it at | test it must not overlap |\`); remove any criterion with no oracle-shows entry. Never add annotation keys (judge_qc J6).`
- NEW: `- Write \`WORK/JUDGE_MAP.md\` (\`| id | template | requirement it serves (sentence file:line) | oracle shows it at (solve.sh line / printed check) | test it must not overlap | expected Opus PASS? |\`), then the band totals: probe count, probe share of positive weight, and the judge lower, mid and upper estimate for an Opus-like agent (LEVER_RULES v3 section 6). Remove any criterion with no oracle-shows entry. Never add annotation keys (judge_qc J6).`

**Line 107** (G5 rerun promise, G8a invocation, W10 rules of engagement)
- OLD: `- State whole-document exactness up front (G5), e.g. "each output document is graded whole on fresh inputs, and only an exact match counts". Never add "at other scales", "there is no count to check yourself against" or a self-check paragraph. Where useful: one arbiter sentence naming which document wins when documents disagree (W8); the full output schema or the file that holds it.`
- NEW: `- State whole-document exactness up front (G5), e.g. "each output document is graded whole on fresh inputs, and only an exact match counts", and the rerun promise: the program is run again on fresh inputs in the same layout, naming the axes that change (sizes, ids, dates, which stated cases occur) [PENDING QL Q4 for naming the axes; until then keep only the first half]. State the exact command the program is run with (G8a) and the rules of engagement (work directory, process order, files that may change) (W10). Never add "at other scales", "there is no count to check yourself against" or a self-check paragraph. Where useful: one arbiter sentence naming which document wins when documents disagree (W8); the full output schema or the file that holds it.`

**Line 122** (gate wording)
- OLD: `4. \`tools/precheck.sh BUNDLE\` until its last line is \`PRECHECK CLEAN\` (common rule Always 10). No reflex gate: hardness is decided by 3 blind reads and the probe run the master queues next (LEVER_RULES section 6). Write in DESIGN.md, per lever, the hidden input and check where a careful solver is expected to lose points, so the probe's \`loss.py\` table can be compared with it.`
- NEW: `4. \`tools/precheck.sh BUNDLE\` until its last line is \`PRECHECK CLEAN\` (common rule Always 10). No reflex gate: hardness is decided by 3 blind reads (tests and judge estimate) and the probe run the master queues next (LEVER_RULES v3 section 6). Write in DESIGN.md, per rule, the hidden input and check where a careful solver is expected to lose points, and per probe criterion whether Opus is expected to show it, so the probe's \`loss.py\` table can be compared with it.`

**Line 127** (deliverables)
- OLD: `- \`OUT/BUILD_REPORT.md\`, \`OUT/STACKING_CHECK.md\`, \`WORK/PREMORTEM.md\`, \`WORK/DESIGN.md\`, \`WORK/LEVERS.md\`, \`WORK/QC_DEFENCE.md\`, \`WORK/COST_TABLE.md\`, \`WORK/RULE_COVERAGE.md\`, \`WORK/EVIDENCE_MAP.md\` (and \`WORK/UNIQUENESS.md\` per L11 lever), \`WORK/JUDGE_MAP.md\`.`
- NEW: `- \`OUT/BUILD_REPORT.md\`, \`OUT/STACKING_CHECK.md\`, \`WORK/PREMORTEM.md\`, \`WORK/DESIGN.md\`, \`WORK/DESIGN_BLIND.md\`, \`WORK/BRANCH_FIRE.md\`, \`WORK/LEVERS.md\`, \`WORK/QC_DEFENCE.md\`, \`WORK/COST_TABLE.md\`, \`WORK/RULE_COVERAGE.md\`, \`WORK/RULE_TRACE.md\` (one row per generator branch: the sentence and file:line that states it), \`WORK/EVIDENCE_MAP.md\` (and \`WORK/UNIQUENESS.md\` per L11 lever or S3 candidate space), \`WORK/JUDGE_MAP.md\`.`

**Line 128** (result json; add fields after `"levers":[]`)
- OLD fragment: `"levers":[],"tests":N,"criteria":N,`
- NEW fragment: `"shape":"B|D","sources":[],"rules_graded":N,"files":N,"formats":N,"levers":[],"tests":N,"criteria":N,"probes":N,"probe_share":x,"judge_estimate":{"lower":x,"mid":x,"upper":x},"design_blind":"<rules missed>/<rules>",`

**Line 136** (next step)
- OLD fragment: `Next step: master issues 3 P13 blind reads (a lever counts only if >= 2 of 3 programs miss it), then queues`
- NEW fragment: `Next step: master issues 3 P13 blind reads (a rule counts only if >= 2 of 3 programs miss it; each reports a judge estimate; park at design if the lower-bound final is above 70 on 2 of 3), then queues`

---

## 3. `P9_harden_from_results_v2.md` -> `P9_harden_from_results_v3.md`

**INSERT AFTER 5**
- NEW: `v3 (26 Oct, board 720e1d7): LEVER_RULES_v3; diagnosis covers the judge half (probe pass or fail per criterion); hardening may add breadth, a degenerate shipped instance, S3/S5/S6 sources, or rebuild the judge as a probe band with no test change; peer evidence from delivery_study2.`

**Line 23**
- OLD: `  - \`/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/LEVER_RULES_v2.md\` (THE authority for the determinate test, levers, writing, grading, judge, STACKING_CHECK and the probe gate);`
- NEW: `  - \`/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/LEVER_RULES_v3.md\` (THE authority for the determinate test, design shapes, hardness sources, levers, writing, grading, judge probe band, holes list, STACKING_CHECK and the probe gate);`

**Line 32**
- OLD: `- Levers for this round (from LEVER_RULES section 1; a set no other live task uses): [[LEVERS]]`
- NEW: `- Shape and hardness sources for this round (LEVER_RULES v3 sections 1 and 1A; a set no other live task uses), or "judge rebuild only" (probe band, no test change): [[SOURCES]]`

**Line 34**
- OLD: `- Peer evidence (patterns only, never copy text/data/code): \`/Users/mac/Desktop/Terminal Bench/master_chat_work/_dev_research/peer_levers/G1..G5/GROUP_SUMMARY.md\``
- NEW: `- Peer evidence (patterns only, never copy text/data/code): \`/Users/mac/Desktop/Terminal Bench/master_chat_work/_dev_research/peer_levers/G1..G5/GROUP_SUMMARY.md\` and \`/Users/mac/Desktop/Terminal Bench/master_chat_work/_dev_research/delivery_study2/g1_be971df..g4_af78147/GROUP_SUMMARY.md\``

**Line 44** (cause 4)
- OLD: `   - Cause 4, levers weak by design: for each lever, the rule text and location, the trajectory step where the agent got it right, and what gave it away (rule next to its use, trap explained, shipped separating example, self-test).`
- NEW: `   - Cause 4, levers weak by design: for each rule or lever, the rule text and location, the trajectory step where the agent got it right, and what gave it away (rule next to its use, trap explained, shipped separating example, a shipped instance that fires the hard branch, a stated limit that hands over the method, self-test). For the judge half: per criterion, PASS or FAIL and the step that decided it; name every figure or rule-restating criterion the agent passed for free (J1, J8).`

**Line 46**
- OLD: `3. **Lever table** from \`reward-details.json\` plus the trajectory: check or criterion, points, earned, levers, HELD/LEAKED.`
- NEW: `3. **Lever table** from \`reward-details.json\` plus the trajectory: check or criterion, points, earned, levers or probe template, HELD/LEAKED. Then the arithmetic: final = (tests + rubric) / 2, and the final a probe-band judge rebuild alone would give at the peer probe pass rate (25%, LEVER_RULES v3 J2).`

**Line 53**
- OLD: `- Implement the levers above (section 1), fitted to the domain naturally. In \`WORK/LEVERS.md\` record for each: the rule text with file:line, the reflex reading (from the autopsy and the agent program), the constructed hidden cases, the checks the wrong reading fails, and how it interacts with the other levers.`
- NEW: `- Implement the shape and sources above (sections 1 and 1A), fitted to the domain naturally. In \`WORK/LEVERS.md\` record for each rule or lever: the rule text with file:line, the reflex reading (from the autopsy and the agent program), the constructed hidden cases, the checks the wrong reading fails, and how it interacts with the others. Update \`WORK/BRANCH_FIRE.md\` and \`WORK/RULE_TRACE.md\`. Never add a hole from section 8 (unstated rule, silent value form, unstated invocation) to make a lever bite.`

**Line 54**
- OLD fragment: `- Determinate test 0b and writing W1-W11 (sections 0b, 2).`
- NEW fragment: `- Determinate test 0b and writing W1-W12 (sections 0b, 2).`

**Line 55**
- OLD: `- Grading G1-G12 (section 3): whole-document exact tests on hidden reseeded inputs with exactness stated (CL-4 exemption FC:491), G3 shares, negatives only for cheating acts (<= 5 per act) each quoting its stated sentence, the G5 exactness clause only, at least 2 mutation tests, assertion messages in ctrf, RULE_COVERAGE per AL-2 unit and established ordering (G11), no count caps, core weights never 1.`
- NEW: `- Grading G1-G13 (section 3): whole-document exact tests on hidden reseeded inputs with exactness stated (CL-4 exemption FC:491), per-row ownership (G1a), G3 shares by shape, negatives only for cheating acts (<= 5 per act) each quoting its stated sentence and none rc-sensitive, the G5 exactness clause plus the rerun promise, at least 2 mutation tests counted only where the plain hidden run is exact (G6), the stated invocation (G8a), assertion messages in ctrf, RULE_COVERAGE per AL-2 unit and established ordering (G11), no count caps, core weights never 1.`

**Line 56**
- OLD: `- Judge J1-J9 (section 4), \`[judge] mode = "batched"\`; J2/J9 wording never in instruction.md.`
- NEW: `- Judge J1-J10 (section 4): probe band of 8-16 w3 trajectory probes from templates P-a to P-h, J2b guards, J3a-c, behavioural J4, JUDGE_MAP with oracle-shows rows and the judge estimate; \`[judge] mode = "batched"\`; probe wording never in instruction.md.`

**Line 63**
- OLD: `2. Cost table (G10) and \`tools/precheck.sh BUNDLE\` until \`PRECHECK CLEAN\`. No reflex gate: the master issues 3 blind reads before the next probe (LEVER_RULES section 6).`
- NEW: `2. Cost table (G10, with the design judge estimate) and \`tools/precheck.sh BUNDLE\` until \`PRECHECK CLEAN\`. No reflex gate: the master issues 3 blind reads (tests and judge estimate) before the next probe (LEVER_RULES v3 section 6).`

**Line 73**
- OLD fragment: `Next step: master issues 3 P13 blind reads, then the probe; QC only after the probe passes the gate.`
- NEW fragment: `Next step: master issues 3 P13 blind reads with judge estimates, then the probe; QC only after the probe's final reward passes the gate.`

---

## 4. `P13_blind_solve_v1.md` -> `P13_blind_solve_v2.md`

**Line 1**
- OLD: `# P13 Blind-solve (reflex program), template v1 (23 Oct 2026)`
- NEW: `# P13 Blind-solve (reflex program), template v2 (26 Oct 2026; v2: checks log, judge estimate after the program is frozen, design-stage use)`

**INSERT AFTER 3**
- NEW: `Also used at design stage (P2 Phase 0b): the blind copy is then \`WORK/design_blind/\` (draft instruction.md, rule register, small sample); steps 1-4 are the same; the judge step uses the draft JUDGE_MAP criteria.`

**Line 6** (also copy the judge file, outside BLIND_DIR)
- OLD: `1. Make the blind copy: \`TS=$(date +%Y%m%dT%H%M%S)-$(openssl rand -hex 2)\`; \`mkdir -p "/tmp/blind/[[SLUG]]-$TS"\`; \`cp -Rp "<BUNDLE>/instruction.md" "<BUNDLE>/environment" "/tmp/blind/[[SLUG]]-$TS/"\`. Nothing else is copied (no tests/, solution/, task.toml, notes). Fill \`[[BLIND_DIR]]\` with the literal path.`
- NEW: `1. Make the blind copy: \`TS=$(date +%Y%m%dT%H%M%S)-$(openssl rand -hex 2)\`; \`mkdir -p "/tmp/blind/[[SLUG]]-$TS"\`; \`cp -Rp "<BUNDLE>/instruction.md" "<BUNDLE>/environment" "/tmp/blind/[[SLUG]]-$TS/"\`. Nothing else is copied into it (no tests/, solution/, task.toml, notes). Copy \`<BUNDLE>/tests/judge.toml\` to \`/tmp/blind/[[SLUG]]-$TS.judge.toml\` (outside the blind folder). Fill \`[[BLIND_DIR]]\` and \`[[JUDGE_PATH]]\` with the literal paths.`

**Line 20** (allow the judge file only at step 5)
- OLD: `- Read ONLY files inside \`[[BLIND_DIR]]\`. Never open, list or search anything outside it: no \`master_chat_work/\`, \`master_chat_tasks/\`, bundles, \`QC_*\`, \`/tmp\` outside BLIND_DIR, the harness clone, the Anubis repo, or any \`tests/\` or \`solution/\` folder anywhere. No web lookups. No subagents.`
- NEW: `- Read ONLY files inside \`[[BLIND_DIR]]\`, plus \`[[JUDGE_PATH]]\` and only at step 5, after step 4 is ticked. Never open, list or search anything else: no \`master_chat_work/\`, \`master_chat_tasks/\`, bundles, \`QC_*\`, \`/tmp\` outside BLIND_DIR, the harness clone, the Anubis repo, or any \`tests/\` or \`solution/\` folder anywhere. No web lookups. No subagents.`

**Line 30** (checks log)
- OLD: `3. Self-check on the shipped data only: run it, check that every output the instruction names exists and has the stated shape, and check any totals or controls the files themselves define. If the run crashes, you may fix the crash once; do not rework logic after the self-check.`
- NEW: `3. Self-check on the shipped data only: run it, check that every output the instruction names exists and has the stated shape, and check any totals or controls the files themselves define. If the run crashes, you may fix the crash once; do not rework logic after the self-check. Log every command you ran in \`[[BLIND_DIR]]/work/CHECKS.md\`, one line each: command, input path, what it showed.`

**Line 31** (freeze, then judge estimate)
- OLD: `4. Stop. Do not iterate further, do not build extra test inputs, do not polish.`
- NEW (2 lines):
  - `4. Freeze. Do not iterate further, do not build extra test inputs, do not polish. Write your final reply text (what you built, what you checked, key figures) into \`[[BLIND_DIR]]/work/FINAL_REPLY.md\` as you would hand it over.`
  - `5. Judge estimate. Only now read \`[[JUDGE_PATH]]\`. Change nothing in app/, out/ or FINAL_REPLY.md. For every criterion write one row in \`[[BLIND_DIR]]/work/JUDGE_ESTIMATE.md\`: \`| id | weight | PASS / FAIL / UNSURE | the CHECKS.md line, step or file that decides it |\`. PASS only when a line in CHECKS.md or FINAL_REPLY.md shows the exact act or fact; a negative is FIRED or NOT FIRED by the same test. Then three totals over positive weight: lower (PASS only, minus FIRED negatives), upper (PASS + UNSURE, minus FIRED negatives), and the count of process criteria you did not perform.`

**Line 35** (report)
- OLD: `- \`[[BLIND_DIR]]/work/BLIND_REPORT.md\`: files read in order, minutes to first full write, what the self-check covered and its result, any crash fixed, and last \`## Lessons for the master\` (max 5 lines; e.g. what in the instruction was unclear).`
- NEW: `- \`[[BLIND_DIR]]/work/BLIND_REPORT.md\`: files read in order, minutes to first full write, what the self-check covered and its result, any crash fixed, the judge estimate totals (lower, upper), and last \`## Lessons for the master\` (max 5 lines; e.g. what in the instruction was unclear). Also \`work/CHECKS.md\`, \`work/FINAL_REPLY.md\`, \`work/JUDGE_ESTIMATE.md\`.`

**Line 36** (result json)
- OLD fragment: `"self_check":"PASS|FAIL","crash_fixed":true|false,"report":"<path>"}`
- NEW fragment: `"self_check":"PASS|FAIL","crash_fixed":true|false,"judge_lower":x,"judge_upper":x,"minutes_to_first_write":N,"report":"<path>"}`

**Line 38**
- OLD: `Final reply (5 lines max): status, program paths, self-check result, report path.`
- NEW: `Final reply (5 lines max): status, program paths, self-check result, judge estimate lower and upper, report path.`

Note for the master (not pasted): the final bounds are computed by the master per LEVER_RULES v3 section 6, using the real-tests score of the blind program: lower final = (tests% + judge_lower) / 2, upper final = (tests% + judge_upper) / 2. A blind PASS with no cited line counts as FAIL in the lower bound.

---

## 5. `P1_chatgpt_ideas_v2.md` -> `P1_chatgpt_ideas_v3.md`

**Line 1**
- OLD: `# P1 ChatGPT idea prompt, template v2 (25 Oct 2026)`
- NEW: `# P1 ChatGPT idea prompt, template v3 (26 Oct 2026)`

**Line 3**
- OLD: (the whole "Replaces v1 (21 Oct). Why: measured results 21-25 Oct. ..." paragraph)
- NEW: `Replaces v2 (25 Oct). Why: from 24 to 26 Oct, 8 builds made under v2 were parked. Blind Opus sessions transliterated fully stated contracts into exact programs in about 3 minutes, and stated size and runtime limits handed over the exact method (cold-chain 85.0 final; cleanroom, crash-recovery, scheduler blind 100; registry/tasks.json:698-734). 19 delivered peer tasks stayed below a final of 70 by breadth, by a shipped instance that never fires the hard branch, by unique fit, and by a judge half of trajectory probes (delivery_study2 g1-g4; LEVER_RULES_v3 section 1A). So v3 asks ChatGPT for those hardness sources, not for an exact optimum or exact replay. Rules follow \`knowledge/LEVER_RULES_v3.md\`.`

**Line 9** (append final reward sentence; keep the rest)
- OLD fragment: `A separate reviewer reads its work log.`
- NEW fragment: `A separate reviewer reads its work log and scores how it verified its work; the final score is the average of the test score and the reviewer score.`

**Line 11**
- OLD: `Target: a careful, competent agent earns 20 to 50 percent of the test points. Partial credit must stay possible (independent weighted checks).`
- NEW: `Target: a careful, competent agent earns 30 to 70 percent of the test points and 25 to 45 percent of the reviewer points, so its final stays below 60. Partial credit must stay possible (each output row graded by exactly one check).`

**Lines 16-28** (replace the whole "What we measured" section with these lines)
- NEW:
  - `## What we measured (this is the most important section)`
  - `This agent reads specifications perfectly and fast. For every rule written in the instruction or a spec file, it writes the rule as code. When a task states a few rules, it finishes an exact program in about 3 minutes. It beat all of these (98 to 100 percent): habit traps (rounding mode, inclusive bounds), recursive allocations, stateful keys, rules inferred from data, an exact optimum when a stated size or runtime limit pointed at the method, and an exact replay when every semantic was spelled out.`
  - `What held, in 19 delivered tasks by other authors (final scores 34 to 69):`
  - `1. Breadth: 30 to 80 small, plainly stated rules spread over 10 to 100 files in 5 to 20 formats, each output document graded whole. The agent needed 10 to 46 minutes for its first full program and still missed 20 to 120 test points.`
  - `2. A shipped sample in which the hard case never happens: the rule and all its cases are stated, but the shipped files never trigger the hard case; the hidden test inputs always do. The agent's program is exact on the sample and wrong on the hidden inputs, because it only checks itself on the sample.`
  - `3. Unique fit: the output is the one candidate (out of a stated set) that fits all the evidence, and the program must fail clearly when none or several fit. The agent returns the first candidate that fits.`
  - `4. Partial-authority files: a file marked as superseded in its own header except for one named fact that still applies. The agent drops the whole file.`
  - `5. A long chain of stated authority rules deciding which of several near-identical deliveries governs.`
  - `6. The reviewer half: the agent rarely runs its program on an input it built where a stated case applies, rarely shows one concrete instance of a case, rarely recomputes a figure outside its program, and rarely reruns on a changed copy of the inputs. Reviewer scores of 25 to 33 percent kept finals below 70 even when tests were 90 to 96.`
  - `So the difficulty comes from many stated rules applied exactly, hard cases that only the hidden inputs trigger, and verification work the agent skips. Nothing may depend on reading a rule wrongly, and no rule may be missing from the files.`

**Line 31** (frame 1)
- OLD: `1. Every rule the tests grade is written in the instruction or a shipped spec file, with exactly one reading. No hidden rules, no secret constants, no unstated tie-breaks, no network facts. Ties in an optimum are broken by a stated total order, so the expected output is unique.`
- NEW: `1. Every rule the tests grade is written in the instruction or a shipped spec file, with exactly one reading. No hidden rules, no secret constants, no unstated tie-breaks, no unstated output conventions (casing, file bundle, command flags), no network facts. The expected output is unique: either a stated total order breaks ties, or a stated rule says exactly one candidate must fit and the program must report an error when none or several fit.`

**Line 34** (frame 4)
- OLD: `4. The shipped sample instances must be solvable by the naive method (so self-checking on samples reveals nothing). The hidden instances are the same distribution at a larger size or with denser structure, still within a stated size limit, where the naive method is wrong (not merely slow). State the size limits and a runtime limit per instance (for example 60 s) that an exact method meets with margin.`
- NEW: `4. The shipped sample never triggers the hard case of any rule (so self-checking on the sample reveals nothing). The instruction states that the program will be rerun on fresh inputs in the same layout, and which things change (sizes, ids, dates, which stated cases occur). Do not state a size or runtime limit that tells the agent which method to use.`

**Line 36** (frame 6)
- OLD: `6. Do NOT use: textbook puzzles the agent recognises and solves with a known library call (sudoku, n-queens, plain knapsack, plain shortest path, plain max-flow); data volume; plain arithmetic; formatting trivia; hundreds of corner cases; resource pressure; disabling the network; floating tolerance. Third-party solvers are not installed and must not be needed.`
- NEW: `6. Do NOT use: textbook puzzles the agent recognises (sudoku, n-queens, plain knapsack, plain shortest path, plain max-flow); an exact optimum as the main difficulty; raw data volume with few rules; plain arithmetic; formatting trivia; lists of traps or warnings in any file; resource pressure; disabling the network; floating tolerance. Third-party solvers are not installed and must not be needed.`

**Line 39** (frame 8)
- OLD: `8. Inputs: at least 6 to 10 flat files (as the archetype says) in at least 4 formats readable by the Python standard library. The files are chained (one is needed to interpret another) and every file matters to a graded result.`
- NEW: `8. Inputs: at least 10 and up to 50 flat files in at least 5 formats readable by the Python standard library, plus a rule register that names every governing file. Each rule sits in the file that governs its data. The files are chained (one is needed to interpret another) and every file matters to a graded result.`

**Line 50** (field 4)
- OLD: `4. The computational core: the exact problem in mathematical terms (decision variables, constraints, objective, total tie-break order), and the algorithmic idea an expert uses to solve the hidden sizes exactly in time.`
- NEW: `4. The hardness sources used (at least two of: breadth, hard case only in hidden inputs, unique fit, partial-authority file, long authority chain), and for each: the rules involved, how many there are, and the files and formats they sit in.`

**Line 51** (field 5)
- OLD: `5. Why the naive approaches fail: for greedy, local search, a time-limited search, and the most likely "smart" first attempt, say what plausible wrong answer each gives on a hidden instance and why the shipped samples do not expose it.`
- NEW: `5. Why a fast first program fails: what a careful agent writes in its first 10 minutes, the exact rule or case it gets wrong on a hidden input, and why its self-check on the shipped sample does not expose it.`

**Line 52** (field 6)
- OLD: `6. Instance design: sample sizes vs hidden sizes, the structure that makes naive methods miss (stated as a generator recipe), and why it is still the same stated distribution.`
- NEW: `6. Sample and hidden design: which stated cases the shipped sample triggers and which it never triggers, the hidden-input generator recipe that triggers every stated case, and why every hidden input still follows the stated rules.`

**Line 54** (field 8)
- OLD: `8. Checks: 30 to 60 independent weighted checks, grouped (feasibility, exact optimum per hidden instance, secondary reports, rejection paths), with the heavy ones marked.`
- NEW: `8. Checks: 30 to 60 weighted checks, each output row graded by exactly one check, grouped (shipped outputs, hidden reruns per output document, rejection paths), with the heavy ones marked.`

**Line 56** (field 10)
- OLD: `10. Reviewer checks: 10 to 15 statements about the work log that hold for any correct solution and do not repeat a test.`
- NEW: `10. Reviewer checks: 8 to 12 statements about the work log, each one verification act a careful engineer performs and a fast agent skips (runs the program on an input it built where a named stated case applies; shows one concrete instance of a named case and the program's decision; recomputes one figure outside the program; reruns on a changed copy of the inputs and shows what moved; runs the broken tool before editing it). Each holds for the author's own reference run and does not repeat a test.`

**Line 58** (field 12)
- OLD: `12. Expected scores: lazy, careful and expert agent on the tests, with a one-line reason each.`
- NEW: `12. Expected scores: lazy, careful and expert agent on the tests and on the reviewer checks, and the final (the average of the two), with a one-line reason each.`
