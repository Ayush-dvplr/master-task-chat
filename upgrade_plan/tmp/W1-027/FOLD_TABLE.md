FOLD TABLE (W1-027, 3 Nov 2026): rules in the active rule files compared with drafts/P1/RULES_IN_FORCE.md

Key to file names (all under /home/user/master-task-chat/master_chat_tasks/ unless noted):
1. LEVER_RULES_v3.md = knowledge/LEVER_RULES_v3.md
2. 20261101_route1_notes.md = prompts/issued/_adhoc/20261101_route1_notes.md (its R0 overrides LEVER_RULES_v3.md where they differ)
3. QC_FIX_PLAYBOOK_v3.md = knowledge/QC_FIX_PLAYBOOK_v3.md
4. _COMMON_RULES_v5.md = prompts/templates/_COMMON_RULES_v5.md
5. pipeline_v4/PLAN.md = /home/user/master-task-chat/master_chat_work/_dev_research/pipeline_v4/PLAN.md
6. KNOWLEDGE.md = knowledge/KNOWLEDGE.md
7. state.json (standing rules part: targets, rules, rules_setup_v1, test_phase_gate)
8. README.md = master_chat_tasks/README.md
9. issue.py = tools/issue.py
RIF:N = line N of upgrade_plan/drafts/P1/RULES_IN_FORCE.md. PATTERNS = upgrade_plan/knowledge/PATTERNS.md.
Verdict is the first word of column 4. Rows where one source line holds several rules repeat the same file:line.

id | file:line | rule text, short | verdict | RULES_IN_FORCE line or rule id | proposed action

LEVER_RULES_v3.md
F1 | LEVER_RULES_v3.md:5 | templates point to this file by path; they never paste it | SAME | RIF:14 (R33, prompts read live files) | keep as how to text
F2 | LEVER_RULES_v3.md:32 | silence, preformatted values, a never fired branch, coinciding readings and prohibitions never settle a rule; each needs a stated sentence | MISSING, looks still in force (QC kit 05:27); touches R28 | RIF:15 (R28 open) | keep as how to text
F3 | LEVER_RULES_v3.md:33 | a degenerate shipped instance always needs the rule sentence for every branch it hides; it may hide the case, never the rule | MISSING, looks still in force; touches R28 | RIF:15 (R28 open) | ASK AYUSH (decide together with Q116)
F4 | LEVER_RULES_v3.md:35 | rules of engagement (scope, files that may change, tools, order, negatives) are always stated | MISSING, looks still in force (IN-15) | none | add to RULES_IN_FORCE: "Rules of engagement (scope, files that may change, tools, order, negatives) are always stated in a file the agent reads."
F5 | LEVER_RULES_v3.md:36 | every rule settled by shipped evidence gets a WORK/EVIDENCE_MAP.md row | MISSING, looks still in force | none | keep as how to text
F6 | LEVER_RULES_v3.md:37 | every stated rule gets a RULE_TRACE row; a generator branch with no sentence is a hidden rule: delete the branch or write the sentence | MISSING, looks still in force | none | keep as how to text
F7 | LEVER_RULES_v3.md:40 | pick ONE primary shape (B breadth or D degenerate instance) plus a secondary source from 1A | CONTRADICTS: RIF names the primary lever by PATTERNS.md DESIGN families, not by Shape B or D | RIF:10 (R25) | ASK AYUSH (propose: replace with RIF:10, keep shapes as background)
F8 | LEVER_RULES_v3.md:42 | Shape D: at most 3 sharp rules, each costs at least 25 percent alone, at least 70 percent of positive weight on hidden corpora | CONTRADICTS: RIF asks 40 percent for the primary lever and sets no 25 percent per lever or 70 percent hidden floor | RIF:10 (R25) | ASK AYUSH
F9 | LEVER_RULES_v3.md:44 | a lever set must not repeat another live task's full set | SAME | RIF:1 (GOAL: new, not a copy) | keep as how to text
F10 | LEVER_RULES_v3.md:58 | L11 evidence induction is a pilot, not required in builds | MISSING; paused by LEVER_RULES_v3.md:86 | none | ASK AYUSH
F11 | LEVER_RULES_v3.md:60 | never use silence (open scope, two antecedents, unmapped codes, unstated output conventions); some silences allowed only when one shipped fact determines the answer and EVIDENCE_MAP names it | MISSING, looks still in force (IN-16) | RIF:15 (R28 open, related) | keep as how to text
F12 | LEVER_RULES_v3.md:86 | stated rule levers (L1 to L11, S1, S3, S5, S6, H1 to H9, T1 to T4) are PAUSED; no new hardening round relies on them until the lever audit | CONTRADICTS: RIF allows a misread rule lever with one clear deciding sentence (CR7), and PATTERNS D3 is a misread rule family | RIF:10 (CR7, R25) | ASK AYUSH (propose: lift the pause per CR7)
F13 | LEVER_RULES_v3.md:87 | v3.4 Law-1: a test lever counts only on WRONG output; timeout or crash never counts | SUPERSEDED: LEVER_RULES_v3.md:91 says v3.8 overrides v3.4 Law-1 | LEVER_RULES_v3.md:91 | delete as superseded
F14 | LEVER_RULES_v3.md:88 | v3.5: timeout or crash counts under 3 conditions, condition 3 cost 10 to 30 percent inside lever checks | SUPERSEDED (condition 3): LEVER_RULES_v3.md:91 and 20261101_route1_notes.md:8 "no 30% cap"; conditions 1 and 2 live on in route1 R0 1(c) | LEVER_RULES_v3.md:91 | delete as superseded (condition 3 only)
F15 | LEVER_RULES_v3.md:89 | v3.6 bars: lever cost 25 to 40 percent, first write tests at most 75, blind at most 80, gate final under 50 | SUPERSEDED: the line itself says "SUPERSEDED by the v3.7 bullet below" | LEVER_RULES_v3.md:90 | delete as superseded
F16 | LEVER_RULES_v3.md:90 | v3.7 design bars: first write tests at most 60, each blind tests at most 65 (none above 70), judge mid at most 20, DESIGN READY (a) to (e) incl predicted final at most 35 | MISSING; partly replaced by LEVER_RULES_v3.md:91 and 20261101_route1_notes.md:39 (R5 replaces (c) and (e)) | none | ASK AYUSH (which design bars stay)
F17 | LEVER_RULES_v3.md:90 | overnight auto runs: the master may send "go" at DESIGN READY, otherwise Needs Ayush | MISSING; unclear if still in force | none | ASK AYUSH
F18 | LEVER_RULES_v3.md:91 | primary lever kinds only (a) carrier variation, (b) unfired documented branch, (c) measured scale | CONTRADICTS: RIF takes the primary lever from any PATTERNS.md DESIGN family (includes D3 misread rule and D5 buried detail) | RIF:10 (R25) | ASK AYUSH (propose: replace kind list by PATTERNS families)
F19 | LEVER_RULES_v3.md:91 | primary lever carries at least 40 percent of positive test weight | SAME | RIF:10 (R25) | keep as how to text
F20 | LEVER_RULES_v3.md:91 | misread rule held out branches are extras, never counted toward the bar | CONTRADICTS: RIF allows a misread rule lever as primary with one clear deciding sentence | RIF:10 (CR7) | delete as superseded by RIF:10 (CR7, decided)
F21 | LEVER_RULES_v3.md:91 | (c) measured scale may be the primary lever; TIMEOUT or CRASH counts with no cap | CONTRADICTS: RIF says a timeout lever is only an extra unless Ayush says so | RIF:10 | ASK AYUSH
F22 | LEVER_RULES_v3.md:91 | careful program keeping at least 60 percent of primary lever points = NO CORE; paid exact program with 0 differences over 2,000 variants = park | MISSING; "park" clashes with "nothing is parked except on Ayush's word" (20261101_route1_notes.md:17) | none | ASK AYUSH
F23 | LEVER_RULES_v3.md:91 | every lever names oracle branch, program branch and a saved input that differs | MISSING, looks still in force | none | add to RULES_IN_FORCE: "Every lever names in DESIGN.md the oracle branch, the careful program branch and a saved input where they differ."
F24 | LEVER_RULES_v3.md:91 | never copy doc contradicting hidden data, underspecified graded fields, unbounded unstated forms, source shape tests | MISSING, looks still in force | none | add to RULES_IN_FORCE: "Never copy holes: hidden data against a doc line, an underspecified graded field, unbounded unstated forms, source shape tests."
F25 | LEVER_RULES_v3.md:93 | rejected sources: wrong reading negatives, exact optimum with a stated method, odd carriers and format rules, mutation tiers alone | CONTRADICTS: "odd carriers and format rules" are rejected here but carrier variation is PATTERNS D2, a DESIGN family RIF allows | RIF:10 (R25) | ASK AYUSH (keep the other rejected sources as how to text)
F26 | LEVER_RULES_v3.md:95 | combine S1 or S2 as primary with S3, S5 or S6; S7 only with a CL-4 sentence | CONTRADICTS: primary comes from PATTERNS families | RIF:10 (R25) | ASK AYUSH
F27 | LEVER_RULES_v3.md:115 | unbounded induction (forms or meanings unstated): never | MISSING, looks still in force | none | add to RULES_IN_FORCE (fold into F24 wording)
F28 | LEVER_RULES_v3.md:116 | instructed effort caps ("stop at 1500 s"): never | MISSING, looks still in force | none | add to RULES_IN_FORCE: "No effort cap in any instruction."
F29 | LEVER_RULES_v3.md:117 | judge only band (tests near 100, judge negatives): never | MISSING, looks still in force | RIF:9 (tests under 85 makes it moot) | keep as how to text
F30 | LEVER_RULES_v3.md:120 | promotion PROMISING to PROVEN needs 2 of our tasks on frozen bytes at tests at most 60 and rubric at most 20 | MISSING | none | keep as how to text
F31 | LEVER_RULES_v3.md:136 | H1: never list the malformed values of a typed field; precheck fails LV-ENUM | MISSING (hides a fair trap, normal) | none | keep as how to text
F32 | LEVER_RULES_v3.md:146 | W1 never explain the trap: no "not only X", no "note that", no trap lists, no rule counts | SAME (adds "no rule counts") | RIF:10 (R30) | keep as how to text; ASK AYUSH whether "no rule counts" joins RIF:10
F33 | LEVER_RULES_v3.md:147 | W2 each rule sits in the file that governs its data | MISSING | none | keep as how to text
F34 | LEVER_RULES_v3.md:149 | W4 an override names the field exactly | MISSING | none | keep as how to text
F35 | LEVER_RULES_v3.md:150 | W5 separating cases only in hidden inputs (L5 excepted); BRANCH_FIRE table, hard branch fires 0 times on shipped data | MISSING | none | keep as how to text
F36 | LEVER_RULES_v3.md:151 | W6 a worked example only on invented toy values, at most one per rule, never a graded figure | MISSING; check against RIF:11 "ask for a worked example in the instruction when one is graded" | RIF:11 (Q106) | ASK AYUSH
F37 | LEVER_RULES_v3.md:152 | W7 a shipped control is real and honest and reconciles under both readings | MISSING | none | keep as how to text
F38 | LEVER_RULES_v3.md:153 | W8 when several documents carry rules, one instruction sentence names which wins | MISSING | none | keep as how to text
F39 | LEVER_RULES_v3.md:154 | W9 literal reading self test; rewrite if the oracle loses points | MISSING | none | keep as how to text
F40 | LEVER_RULES_v3.md:155 | W10 one rule register; instruction.md states no rule of the computation | MISSING; may clash with RIF:11 "every criterion traces to an instruction sentence" | RIF:11 (Q106) | ASK AYUSH
F41 | LEVER_RULES_v3.md:156 | W11 no answer for any graded document visible to the agent | MISSING, looks still in force | none | add to RULES_IN_FORCE: "Nothing in environment/ shows the answer for a graded document."
F42 | LEVER_RULES_v3.md:157 | W12 re-rendered rule documents stay word for word except values | MISSING | none | keep as how to text
F43 | LEVER_RULES_v3.md:160 | one act costs at most minus 5 across both layers (AL-28) | MISSING (kit rule) | none | keep as how to text
F44 | LEVER_RULES_v3.md:161 | G1 tests compare each output document whole and exact on each hidden corpus | MISSING, looks still in force (also route1 R0 3) | none | add to RULES_IN_FORCE: "Every task states the exact bar sentence; tests compare whole documents per hidden run."
F45 | LEVER_RULES_v3.md:161 | at most one stated cross corpus gate per task, with its sentence in instruction.md | MISSING | none | keep as how to text
F46 | LEVER_RULES_v3.md:161 | never grade a key the agent cannot read; every key and value form a test reads is named in the shipped contract | MISSING, looks still in force (QL ruling) | none | add to RULES_IN_FORCE: "Never grade a key, field or value form the shipped contract does not name."
F47 | LEVER_RULES_v3.md:162 | G1a per row ownership; a test that compared nothing never passes | MISSING | none | keep as how to text
F48 | LEVER_RULES_v3.md:163 | G2 each test asserts only its own observable; no early return on another document | MISSING | none | keep as how to text
F49 | LEVER_RULES_v3.md:164 | G3 Shape D at least 70 percent hidden weight; every shape at least one hidden rerun per output family | CONTRADICTS (70 percent floor tied to Shape D; RIF sets 40 percent primary share only) | RIF:10 (R25) | ASK AYUSH (keep the one hidden rerun per family part as how to text)
F50 | LEVER_RULES_v3.md:165 | G4 negatives grade only cheating acts, at most 5 per group, no negative grades a lever, none on exit code alone | MISSING | none | keep as how to text
F51 | LEVER_RULES_v3.md:166 | G5 instruction states exactness and the rerun promise; no axis list; no "at other scales"; no self check paragraph | MISSING | none | keep as how to text
F52 | LEVER_RULES_v3.md:167 | G6 at least 2 mutation tests; a variant counts only where the plain hidden run is exact | MISSING | none | keep as how to text
F53 | LEVER_RULES_v3.md:168 | G7 assertion messages recorded in ctrf | MISSING | none | keep as how to text
F54 | LEVER_RULES_v3.md:169 | G8 hidden inputs from an embedded seeded generator; no slug or author string in SHA pinned test text | MISSING | none | keep as how to text
F55 | LEVER_RULES_v3.md:170 | G8a instruction.md states the exact command the tests run; no unstated python -I or cwd | MISSING, looks still in force | none | add to RULES_IN_FORCE: "The instruction states the exact command the tests use to run the program."
F56 | LEVER_RULES_v3.md:171 | G9 expected values independent of the oracle; never hard code shipped expected values from the oracle alone | MISSING, looks still in force | none | keep as how to text
F57 | LEVER_RULES_v3.md:172 | G10 cost table: Shape D every lever at least 25 percent; every all but one row predicted final under 70 | CONTRADICTS: 70 predates the final under 40 gate; 25 percent per lever predates R25 | RIF:9, RIF:10 | ASK AYUSH
F58 | LEVER_RULES_v3.md:172 | differential fuzz of an earlier program on a changed bundle is not evidence | MISSING | none | keep as how to text
F59 | LEVER_RULES_v3.md:173 | G11 RULE_COVERAGE: every mutant row fails at least 1 test; tie breaks need a planted tie | MISSING | none | keep as how to text
F60 | LEVER_RULES_v3.md:174 | G12 generator values inside stated bounds; 300 seeds with no crash; no shared mutable cache | MISSING | none | keep as how to text
F61 | LEVER_RULES_v3.md:175 | G13 treat any single test score as plus or minus 20 and any final as plus or minus 10 | MISSING | none | keep as how to text
F62 | LEVER_RULES_v3.md:176 | counts: no cap on tests or criteria; the QC WARN above 35 is recorded, not fixed | CONTRADICTS: RIF sets counts QC minimum, soft 70, hard 100 | RIF:8 (Ayush's rule) | delete as superseded by RIF:8
F63 | LEVER_RULES_v3.md:176 | TS-20 core weights never 1 | MISSING | none | keep as how to text
F64 | LEVER_RULES_v3.md:180 | J1 no figure criterion; a figure enters the judge only inside J3b | MISSING | none | keep as how to text
F65 | LEVER_RULES_v3.md:181 | J2 probe band: 8 to 16 probes, w3, 55 to 70 percent of positive judge weight; the oracle shows every probe act | MISSING | none | keep as how to text
F66 | LEVER_RULES_v3.md:181 | never echo probe wording in instruction.md | CONTRADICTS: RIF says every criterion traces to an instruction sentence | RIF:11 (Q106) | ASK AYUSH
F67 | LEVER_RULES_v3.md:191 | J2b probe guards (one act per criterion, no self consistency negative, no menu of acts, and others) | MISSING | none | keep as how to text
F68 | LEVER_RULES_v3.md:201 | J3a honesty negative minus 3 present in every judge | SAME | RIF:11 (R29) | keep as how to text
F69 | LEVER_RULES_v3.md:202 | J3b figure that differs from the delivered file, minus 5 | MISSING | none | keep as how to text
F70 | LEVER_RULES_v3.md:203 | J3c size of a check stated larger than the trajectory shows, minus 3 | MISSING | none | keep as how to text
F71 | LEVER_RULES_v3.md:204 | J4 exactly one behavioural code quality criterion; the oracle meets it line by line | MISSING; wording differs from QC_FIX_PLAYBOOK_v3.md:50 | none | ASK AYUSH (pick one wording)
F72 | LEVER_RULES_v3.md:205 | J5 no criterion endorses a reading the tests penalise | MISSING | none | keep as how to text
F73 | LEVER_RULES_v3.md:206 | J6 one per item enumeration criterion on the final answer | MISSING | none | keep as how to text
F74 | LEVER_RULES_v3.md:207 | J7 a deterministic artifact behaviour is a test, never a criterion | MISSING | none | keep as how to text
F75 | LEVER_RULES_v3.md:208 | J8 no criterion restates a method a test grades | MISSING | none | keep as how to text
F76 | LEVER_RULES_v3.md:210 | J10 stated process rules get one instruction following criterion each, at most 2 | MISSING | none | keep as how to text
F77 | LEVER_RULES_v3.md:212 | a criterion with no oracle shows entry in JUDGE_MAP is removed; never add keys to criterion.annotations | MISSING | none | keep as how to text
F78 | LEVER_RULES_v3.md:215 | STACKING_CHECK gate on every build, harden and fix round before P11 | MISSING | none | keep as how to text
F79 | LEVER_RULES_v3.md:229 | design stage blind read before the full build; redesign if it matches the oracle | MISSING; route 1 needs no fresh blinds before QC (20261101_route1_notes.md:47) | none | ASK AYUSH
F80 | LEVER_RULES_v3.md:230 | 3 fresh blind reads before every probe; a rule counts only when 2 of 3 programs get it wrong | MISSING; same clash with 20261101_route1_notes.md:47 | none | ASK AYUSH
F81 | LEVER_RULES_v3.md:236 | harden or redesign before a probe when the lower bound final is above 70 on 2 of 3 blinds | CONTRADICTS: 70 predates the final under 40 gate | RIF:9 | ASK AYUSH
F82 | LEVER_RULES_v3.md:237 | gate: tests under 85, rubric under 85, final under 40 on 1 valid run of frozen QC passed bytes | SAME | RIF:9 (R26) | keep as how to text
F83 | LEVER_RULES_v3.md:237 | old gates tests under 100 and final under 70; then final under 50 | SUPERSEDED: the line marks both "REPLACED" | LEVER_RULES_v3.md:237 (v3.7 text) | delete as superseded
F84 | LEVER_RULES_v3.md:237 | re-hardened tasks: judge target probe band with predicted mid 15 to 20 | MISSING; differs from LEVER_RULES_v3.md:90 (mid at most 20) | none | ASK AYUSH
F85 | LEVER_RULES_v3.md:237 | push needs 1 valid run on the frozen bytes; any change after that run voids it | SAME | RIF:9 | keep as how to text
F86 | LEVER_RULES_v3.md:237 | a judge only rebuild never rescues a tests 100 task; at least one positive test must be lost | SAME (implied by tests under 85) | RIF:9 | keep as how to text
F87 | LEVER_RULES_v3.md:238 | before diagnosing a run, diff its staged copy and ctrf ids against the bundle; a stale tree score is not a baseline | MISSING, looks still in force | none | add to RULES_IN_FORCE: "Before diagnosing a run, diff its staged copy against the bundle; a score from another tree is no baseline."
F88 | LEVER_RULES_v3.md:239 | NO AUTO PARK; a task is parked only on Ayush's word | MISSING, looks still in force | none | add to RULES_IN_FORCE: "No task is parked except on Ayush's word."
F89 | LEVER_RULES_v3.md:239 | the hardening round is issued with Ayush's override past the 3 round limit | CONTRADICTS: RIF has no round caps | RIF:8 (R15) | delete as superseded by RIF:8
F90 | LEVER_RULES_v3.md:240 | old kill rule: park above final 70; variance band; a round marked LAST is the last | SUPERSEDED: line starts "(Superseded by v3.2 for parking)" | LEVER_RULES_v3.md:239 | delete as superseded
F91 | LEVER_RULES_v3.md:241 | the fresh blind read is the only measure of a round; a round counts when blinds lose at least 10 percent; design blind tries the strongest generic solver | MISSING; clashes with 20261101_route1_notes.md:47 | none | ASK AYUSH
F92 | LEVER_RULES_v3.md:241 | one QC before the first probe; every finding, minors included, fixed in one pass | CONTRADICTS: RIF accepts a minor that does not repeat | RIF:7 (R18) | ASK AYUSH
F93 | LEVER_RULES_v3.md:242 | order: design, build, 3 blinds, full QC, rechecks, freeze, 1 harness run | MISSING; differs from the route 1 order at 20261101_route1_notes.md:17 | none | ASK AYUSH (which order is current)
F94 | LEVER_RULES_v3.md:242 | no hardening after a QC pass | SAME | RIF:7 (R16) | keep as how to text
F95 | LEVER_RULES_v3.md:242 | if the run misses the gate, never re-run the same bytes | SAME | RIF:9 (R27) | keep as how to text
F96 | LEVER_RULES_v3.md:242 | regrade is diagnostic only; push evidence only for a judge only edit on a valid run with Ayush's OK, repackaged with repackage_one.py | MISSING, looks still in force | none | add to RULES_IN_FORCE: "A regrade is diagnostic only, except a judge only edit on a valid run with Ayush's written OK, repackaged by repackage_one.py."
F97 | LEVER_RULES_v3.md:243 | "QC deferred" is never a pass for IN-16 | MISSING | none | keep as how to text
F98 | LEVER_RULES_v3.md:244 | not evidence: differential fuzz, one run per lever claim, oracle injection numbers, unsupported blind PASS | MISSING | none | keep as how to text
F99 | LEVER_RULES_v3.md:245 | a run with a grader error is never a baseline; only valid true lines in scores.jsonl count | MISSING, looks still in force | none | add to RULES_IN_FORCE: "Only valid runs (no grader error) count as baselines."
F100 | LEVER_RULES_v3.md:258 | holes are not levers: never build the listed peer holes | MISSING, looks still in force | none | add to RULES_IN_FORCE (fold into F24 wording)

20261101_route1_notes.md
F101 | 20261101_route1_notes.md:1 | route 1 notes override LEVER_RULES_v3 where they differ; R0 overrides R4 and R5 | MISSING (authority order); RIF now changes R0 content | RIF:10 | ASK AYUSH (state that RIF wins over R0)
F102 | 20261101_route1_notes.md:5 | primary lever, at least one per task, at least 40 percent of positive test weight | SAME | RIF:10 (R25) | keep as how to text
F103 | 20261101_route1_notes.md:5 | the CAREFUL EXACT PROGRAM (written from shipped files only) must lose the primary lever; a lever aware row is never a blocker | MISSING, looks still in force | none | add to RULES_IN_FORCE: "The primary lever is lost by the careful exact program written from the shipped files only."
F104 | 20261101_route1_notes.md:5 | allowed primary kinds (a), (b), (c) only | CONTRADICTS: RIF takes the primary lever from PATTERNS.md DESIGN families | RIF:10 (R25) | ASK AYUSH (propose: replace kinds by PATTERNS families)
F105 | 20261101_route1_notes.md:8 | (c) measured scale primary; TIMEOUT or CRASH counts with no 30 percent cap | CONTRADICTS: RIF says timeout lever only as an extra unless Ayush says so | RIF:10 | ASK AYUSH
F106 | 20261101_route1_notes.md:8 | runtime lever: one stated runtime sentence, no method word, reference at most 1/4 of the limit, careful program at least 4x, shipped inputs fast, each lever corpus in its own call | MISSING | RIF:10 (size bound may be stated) | keep as how to text
F107 | 20261101_route1_notes.md:9 | misread rule held out branches are EXTRAS, never counted toward the 40 percent | CONTRADICTS: RIF allows a misread rule lever with one clear deciding sentence | RIF:10 (CR7) | delete as superseded by RIF:10 (CR7, decided)
F108 | 20261101_route1_notes.md:10 | every task carries the exact bar sentence; tests compare whole documents per hidden run | MISSING, looks still in force | none | add to RULES_IN_FORCE (same wording as F44)
F109 | 20261101_route1_notes.md:11 | every lever names oracle branch, program branch and a saved input that differs; no named difference, no lever | MISSING, looks still in force | none | add to RULES_IN_FORCE (same wording as F23)
F110 | 20261101_route1_notes.md:12 | careful program keeping at least 60 percent = NO CORE; 0 differences over 2,000 variants = park | MISSING; "park" clashes with :17 | none | ASK AYUSH
F111 | 20261101_route1_notes.md:13 | never copy doc contradicting hidden data, underspecified graded fields, unbounded forms, source shape tests | MISSING, looks still in force | none | add to RULES_IN_FORCE (same wording as F24)
F112 | 20261101_route1_notes.md:14 | the instruction keeps "Leave enough of that time to finish and write your final reply."; no effort cap | MISSING, looks still in force | none | add to RULES_IN_FORCE: "Every instruction keeps the finish time sentence; no effort cap."
F113 | 20261101_route1_notes.md:17 | route: build, full QC, 1 paid run, harden from what it got wrong, QC again, 1 paid run | MISSING; differs from LEVER_RULES_v3.md:242 order | none | ASK AYUSH (which order is current)
F114 | 20261101_route1_notes.md:17 | a winning blind or paid program guides the harden, never a reason to park; nothing parked except on Ayush's word | MISSING, looks still in force | none | add to RULES_IN_FORCE (same wording as F88)
F115 | 20261101_route1_notes.md:20 | every hidden check and lever stays in tests; docs never announce it: no "note that", no trap list, no method word, no stated size bound | CONTRADICTS: RIF allows a size bound for a runtime lever | RIF:10 (R30) | delete "no stated size bound" as superseded by RIF:10; keep the rest as how to text
F116 | 20261101_route1_notes.md:21 | every graded fact has a determinate source in shipped docs or data; listed in EVIDENCE_MAP | MISSING, looks still in force (IN-16) | RIF:15 (R28, related) | keep as how to text
F117 | 20261101_route1_notes.md:22 | QC_DEFENCE rows for every new or changed check | MISSING | none | keep as how to text
F118 | 20261101_route1_notes.md:30 | the new hidden check sits where the trajectory shows the agent did not look | MISSING | none | keep as how to text
F119 | 20261101_route1_notes.md:33 | allowed lever form: L2 held out instances firing a documented branch | MISSING; R0 overrides R4 where they differ | RIF:10 (maps to PATTERNS D1) | ASK AYUSH
F120 | 20261101_route1_notes.md:34 | allowed lever form: LC1 bounded induction | MISSING; not an R0 kind | RIF:10 | ASK AYUSH (is it a PATTERNS family)
F121 | 20261101_route1_notes.md:35 | hidden scale TIMEOUT only where Ayush granted an exception for the task | SUPERSEDED: the line marks "[SUPERSEDED 2 Nov by R0 1(c)]"; note RIF:10 now says nearly the old text ("unless Ayush says so") | 20261101_route1_notes.md:35 bracket, RIF:10 | ASK AYUSH (RIF brings the old rule back)
F122 | 20261101_route1_notes.md:36 | rubric: probe band on skipped checks; J3a honesty negative kept; restating criteria removed | SAME (J3a part) | RIF:11 (R29) | keep as how to text
F123 | 20261101_route1_notes.md:37 | not allowed: an unstated rule, a method word, a stated size bound, a trap announcement, an effort cap, a judge only band | CONTRADICTS on "stated size bound" | RIF:10 (R30) | delete "a stated size bound" as superseded by RIF:10; keep the rest
F124 | 20261101_route1_notes.md:40 | DESIGN READY (a): paid run program on new tests gives predicted final at most 35 | MISSING | none | ASK AYUSH
F125 | 20261101_route1_notes.md:41 | DESIGN READY (b): lever share at least 40 percent | SAME | RIF:10 (R25) | keep as how to text
F126 | 20261101_route1_notes.md:42 | DESIGN READY (c): EVIDENCE_MAP and QC_DEFENCE complete | MISSING | none | keep as how to text
F127 | 20261101_route1_notes.md:43 | DESIGN READY (d): a careful enumerator keeping the lever is recorded, not a blocker | SUPERSEDED for the primary lever: the line's own bracket "[2 Nov: for the PRIMARY lever R0 5 makes the careful program a blocker]" | 20261101_route1_notes.md:12 | delete the primary lever part as superseded
F128 | 20261101_route1_notes.md:44 | DESIGN READY (e): reference at most 1/4 of any stated limit, verifier at most 90 percent, oracle and owner 1.0, nop 0 | MISSING | none | keep as how to text
F129 | 20261101_route1_notes.md:47 | stop at DESIGN READY and wait for "go" | MISSING | none | ASK AYUSH (with F17)
F130 | 20261101_route1_notes.md:47 | no fresh blinds required before QC on route 1 | MISSING; clashes with LEVER_RULES_v3.md:230 and :241 | none | ASK AYUSH

QC_FIX_PLAYBOOK_v3.md
F131 | QC_FIX_PLAYBOOK_v3.md:3 | quoted Ayush line: "we have to bypass the QC so that we can maintain the levers, traps etc ... a regular fix can make it soft and easy" | ASK AYUSH, agreed line check | none | ASK AYUSH, agreed line check (not rewritten)
F132 | QC_FIX_PLAYBOOK_v3.md:10 | "bypass" means satisfy exactly what the rule demands; it never means hiding a defect from QC | ASK AYUSH, agreed line check (pairs with F131) | none | ASK AYUSH, agreed line check (not rewritten)
F133 | QC_FIX_PLAYBOOK_v3.md:21 | at least 10 checks and 8 criteria (kit floor) | SAME | RIF:8 (QC minimum) | keep as how to text
F134 | QC_FIX_PLAYBOOK_v3.md:21 | no upper cap; WARN above 35 recorded with the count | CONTRADICTS: RIF sets soft 70 and hard 100 | RIF:8 | delete as superseded by RIF:8
F135 | QC_FIX_PLAYBOOK_v3.md:23 | fix directions that keep the trap, in order (1) to (5) | MISSING | none | keep as how to text
F136 | QC_FIX_PLAYBOOK_v3.md:24 | soft directions are never used unless Ayush says so for one finding (delete a rule, move it beside its use, separating example, explain a reading, count rules, loosen a criterion, drop a lever check, shrink hidden data) | MISSING, looks still in force | none | add to RULES_IN_FORCE: "No fix softens a lever (the playbook's soft directions) unless Ayush says so for that finding."
F137 | QC_FIX_PLAYBOOK_v3.md:29 | IN-15 row: state the rule once as a bare property in its governing file; never beside the step, never a separating example, never naming the trap | MISSING | none | keep as how to text
F138 | QC_FIX_PLAYBOOK_v3.md:30 | IN-16 row: never settle by a worked figure or in the instruction; never pick the reflex program's reading because it is easier | MISSING | none | keep as how to text
F139 | QC_FIX_PLAYBOOK_v3.md:31 | IN-17 row: never move the sentence into a contract file; never delete a rule of engagement or an IN-16 settler | MISSING | none | keep as how to text
F140 | QC_FIX_PLAYBOOK_v3.md:32 | AL-1 row: never a solved list or answer key as evidence | MISSING | none | keep as how to text
F141 | QC_FIX_PLAYBOOK_v3.md:33 | AL-2 row: remove an ungraded request not part of a lever; never a figure criterion or presence only test | MISSING | none | keep as how to text
F142 | QC_FIX_PLAYBOOK_v3.md:34 | AL-2b row: keep a what-if figure criterion per LEVER_RULES J1, max 6, w at most 3 | MISSING; clashes with LEVER_RULES_v3.md:180 J1 (no figure criterion, what-if or not) | none | ASK AYUSH
F143 | QC_FIX_PLAYBOOK_v3.md:35 | AL-18 row: recompute digests and counts last; never edit figures by hand | MISSING | RIF:6 (R13, related) | keep as how to text
F144 | QC_FIX_PLAYBOOK_v3.md:36 | AL-27 row: never delete the rule or put the triggering row in shipped data | MISSING | none | keep as how to text
F145 | QC_FIX_PLAYBOOK_v3.md:37 | AL-28 row: never touch positive cascades; never delete the anti hardcoding negative | MISSING | none | keep as how to text
F146 | QC_FIX_PLAYBOOK_v3.md:38 | S6 row: keep deliberate CRLF data noise as a warn; never CRLF in a .sh file | MISSING | none | keep as how to text
F147 | QC_FIX_PLAYBOOK_v3.md:39 | TS-26 row: never delete the whole document hidden test; never move weight from a lever check to a format check | MISSING | none | keep as how to text
F148 | QC_FIX_PLAYBOOK_v3.md:40 | TS-13 row: split into two checks; never fold a second rule into another check | SAME | RIF:6 (R9) | keep as how to text
F149 | QC_FIX_PLAYBOOK_v3.md:41 | TS-23 row: KEEP as a warn, there is no cap; never merge or drop checks to get under 35 | CONTRADICTS: RIF sets soft 70 and hard 100 | RIF:8 | delete as superseded by RIF:8 (keep "merge only true duplicates" as how to text)
F150 | QC_FIX_PLAYBOOK_v3.md:42 | TS-20 row: never lower a lever check to fix the order | MISSING | none | keep as how to text
F151 | QC_FIX_PLAYBOOK_v3.md:43 | TS-16 row: never widen a negative | MISSING | none | keep as how to text
F152 | QC_FIX_PLAYBOOK_v3.md:44 | TS-19 row: never widen stated bounds or describe the hidden distribution | MISSING | none | keep as how to text
F153 | QC_FIX_PLAYBOOK_v3.md:45 | TS-25 row: never delete the check and its weight | MISSING | none | keep as how to text
F154 | QC_FIX_PLAYBOOK_v3.md:46 | JD-7 row: never loosen the criterion; fix the oracle | MISSING | none | keep as how to text
F155 | QC_FIX_PLAYBOOK_v3.md:47 | DS-22 row: TRUTH.md sha256 values by script as the last edit | SAME | RIF:6 (R13) | keep as how to text
F156 | QC_FIX_PLAYBOOK_v3.md:48 | DS-20 row: fix the oracle; never change the contract to match it | MISSING | none | keep as how to text
F157 | QC_FIX_PLAYBOOK_v3.md:49 | JD-15 row: never announce in instruction.md what the judge looks for | MISSING; check against RIF:11 (criteria trace to instruction sentences) | RIF:11 (Q106) | ASK AYUSH
F158 | QC_FIX_PLAYBOOK_v3.md:50 | JD-18 row: exactly one code quality criterion worded as one judgement ("a Python reviewer would accept as maintainable") | MISSING; wording differs from LEVER_RULES_v3.md:204 J4 (behavioural wording) | none | ASK AYUSH (pick one wording)
F159 | QC_FIX_PLAYBOOK_v3.md:51 | DS-4 row: always fix by removing the signal from the data | MISSING | none | keep as how to text
F160 | QC_FIX_PLAYBOOK_v3.md:52 | DS-6 row: never regenerate data in a way that drops separating rows | MISSING | none | keep as how to text
F161 | QC_FIX_PLAYBOOK_v3.md:53 | SUGGEST row: KEEP only with verifiable evidence; never KEEP "because it would reveal lever L" | MISSING | none | keep as how to text
F162 | QC_FIX_PLAYBOOK_v3.md:54 | JD-5 row: split, then re-check JD-2, JD-7, JD-9, JD-15, IN-8 | SAME | RIF:6 (R11) | keep as how to text
F163 | QC_FIX_PLAYBOOK_v3.md:55 | CL-4 row: REBUT with FC:491 first; never weaken a lever to pass CL-4 | MISSING | none | keep as how to text
F164 | QC_FIX_PLAYBOOK_v3.md:56 | JD-8 row: delete the criterion the tests settle; renumber ids; never keep both | MISSING | none | keep as how to text
F165 | QC_FIX_PLAYBOOK_v3.md:57 | NEW-CHECK row: hygiene checks on each new check; regenerate only after the byte diff | SAME | RIF:6 (R11, R14) | keep as how to text
F166 | QC_FIX_PLAYBOOK_v3.md:58 | NOISE row: a finding on unchanged lines that passed is kept with diff evidence; never edit unchanged lines | SAME | RIF:6 (R17) | keep as how to text
F167 | QC_FIX_PLAYBOOK_v3.md:64 | G1 never paste QC's "Fix:" text as the direction | SAME | RIF:6 (R8) | keep as how to text
F168 | QC_FIX_PLAYBOOK_v3.md:65 | G2 never move an assert into an existing check or weight onto a conduct or route criterion | SAME | RIF:6 (R9) | keep as how to text
F169 | QC_FIX_PLAYBOOK_v3.md:66 | G3 never delete a clause, sentence or grader without naming what grades the rest | SAME | RIF:6 (R10) | keep as how to text
F170 | QC_FIX_PLAYBOOK_v3.md:67 | G4 re-check every touched check and criterion, one row each in RECHECK_FIX.md | SAME | RIF:6 (R11) | keep as how to text
F171 | QC_FIX_PLAYBOOK_v3.md:68 | G5 run the vacuity probe again after fixes | SAME | RIF:6 (R12) | keep as how to text
F172 | QC_FIX_PLAYBOOK_v3.md:69 | G6 docs and TRUTH.md regenerated last, by script | SAME | RIF:6 (R13) | keep as how to text
F173 | QC_FIX_PLAYBOOK_v3.md:70 | G7 never regenerate tests without a byte diff; an unnamed hunk stops the session | SAME | RIF:6 (R14) | keep as how to text
F174 | QC_FIX_PLAYBOOK_v3.md:71 | count cap option A: above 35 checks is a recorded warn | CONTRADICTS: RIF sets soft 70 and hard 100 | RIF:8 | delete as superseded by RIF:8
F175 | QC_FIX_PLAYBOOK_v3.md:75 | direction lines: every FIX names file and change; a lever marked easier carries a compensation; a REBUT quotes its kit line | MISSING | none | keep as how to text
F176 | QC_FIX_PLAYBOOK_v3.md:84 | trap survival PASS: every lever keeps at least 90 percent of its before share and no separating case is removed | MISSING | none | keep as how to text
F177 | QC_FIX_PLAYBOOK_v3.md:85 | trap survival FAIL: compensate, at most 2 tries, then stop PAUSED | CONTRADICTS: RIF says no caps, Ayush decides each time | RIF:8 (R15) | ASK AYUSH
F178 | QC_FIX_PLAYBOOK_v3.md:93 | compensation in the same lever family only | MISSING | none | keep as how to text
F179 | QC_FIX_PLAYBOOK_v3.md:99 | a fix that softened a lever gets a NEVER entry and a lessons.jsonl line | SAME | RIF:4 (R4) | keep as how to text

_COMMON_RULES_v5.md
F180 | _COMMON_RULES_v5.md:3 | if a rule here conflicts with the prompt, stop and report; do not choose | SAME | RIF:2 (R1, flags anything contradictory) | keep as how to text
F181 | _COMMON_RULES_v5.md:7 | never use a frozen QC copy unless the prompt names it | SAME | RIF:14 (R33) | keep as how to text
F182 | _COMMON_RULES_v5.md:8 | precheck.sh is read only; run it, never edit it | MISSING | none | keep as how to text
F183 | _COMMON_RULES_v5.md:10 | read LEVER_RULES by path; never copy it into a bundle or report | SAME | RIF:14 (R33) | keep as how to text
F184 | _COMMON_RULES_v5.md:12 | playbook DO fixes only, never NEVER fixes; section 1b binds every fix | SAME | RIF:6 | keep as how to text
F185 | _COMMON_RULES_v5.md:20 | Never 1: edit GEN, QC, beta-task-generator, QC assigned/, Anubis_Tasks_Samples or master_chat_tasks | SAME (list is wider than RIF's "my tasks/") | RIF:14 (R35), RIF:4 (R3) | keep as how to text
F186 | _COMMON_RULES_v5.md:21 | Never 2: read only git; allowed repos only Terminal_2.0_Harbor_Harness, Anubis_Tasks_Samples, beta-task-generator, Finalized_Tasks_RFP | CONTRADICTS: the R34 decision adds master-task-chat to the repos it may read; read only part SAME | RIF:14 (R34) | add to RULES_IN_FORCE: "Repos it may read: Terminal_2.0_Harbor_Harness, Anubis_Tasks_Samples, beta-task-generator, Finalized_Tasks_RFP, master-task-chat."
F187 | _COMMON_RULES_v5.md:22 | Never 3: no notes, plans or logs inside a bundle folder | MISSING | none | keep as how to text
F188 | _COMMON_RULES_v5.md:23 | Never 4: no generate_bundle.py --force, no playground.py --model, nothing that uploads files or keys | MISSING, looks still in force | none | add to RULES_IN_FORCE: "Never run generate_bundle.py --force, playground.py --model, or anything that uploads files or keys."
F189 | _COMMON_RULES_v5.md:24 | Never 5: claim a number you did not measure; unconfirmed is UNVERIFIED | MISSING, looks still in force | RIF:2 (R1 verifies, related) | add to RULES_IN_FORCE: "Never claim an unmeasured number; unconfirmed means UNVERIFIED."
F190 | _COMMON_RULES_v5.md:25 | Never 6: rules of engagement always stated; silence never settles a graded question; "QC deferred" never passes IN-16 | MISSING, looks still in force (kit); touches R28 | RIF:15 (R28 open) | keep as how to text
F191 | _COMMON_RULES_v5.md:26 | Never 7: delete anything outside your own scratch and log folders | MISSING | none | keep as how to text
F192 | _COMMON_RULES_v5.md:27 | Never 8: explain a trap in any agent visible file; no "note that", no "be careful", no trap lists, no rule counts, no self check paragraph | SAME | RIF:10 (R30) | keep as how to text
F193 | _COMMON_RULES_v5.md:28 | Never 9: no author notes (TRAP, lever, decoy, hidden test ...) in agent visible files | MISSING | none | keep as how to text
F194 | _COMMON_RULES_v5.md:29 | Never 10: harden, add levers or rework after a QC PASS | SAME | RIF:7 (R16) | keep as how to text
F195 | _COMMON_RULES_v5.md:30 | Never 11: ship any answer for a graded document; never ship an oracle that contradicts the contract | MISSING, looks still in force | none | add to RULES_IN_FORCE (same wording as F41)
F196 | _COMMON_RULES_v5.md:33 | Always 1: re-hash GEN and QC against fingerprints; on a difference stop and report UPSTREAM CHANGED | MISSING (RULE_REVIEW R2 improvement 9 covers the card line) | none | keep as how to text
F197 | _COMMON_RULES_v5.md:34 | Always 2: run generator tools with PYTHONDONTWRITEBYTECODE and IBG_MEMORY_PATH | MISSING | none | keep as how to text
F198 | _COMMON_RULES_v5.md:35 | Always 3: long commands under nohup; never end your turn while your own job runs | MISSING | none | keep as how to text
F199 | _COMMON_RULES_v5.md:36 | Always 4: read QC rules from live files, match ID and wording | SAME | RIF:14 (R33) | keep as how to text
F200 | _COMMON_RULES_v5.md:37 | Always 5: keep TODO.md, PLAN.md, LOG.md current | MISSING | none | keep as how to text
F201 | _COMMON_RULES_v5.md:38 | Always 6: after a data edit regenerate embedding, reward.toml and TRUTH sha256 by script as the last edit | SAME | RIF:6 (R13) | keep as how to text
F202 | _COMMON_RULES_v5.md:39 | Always 7: bundle text rules (no em or en dashes, no TODO markers, LF, under 100 MB, ENV HOME, litellm pin) | MISSING | none | keep as how to text
F203 | _COMMON_RULES_v5.md:40 | Always 8: author string Ayush Sah <ayush.sah@ethara.ai> | MISSING | none | keep as how to text
F204 | _COMMON_RULES_v5.md:42 | Always 10: PRECHECK CLEAN before reporting DONE | MISSING, looks still in force | none | keep as how to text
F205 | _COMMON_RULES_v5.md:43 | Always 11: byte diff of generator output before regenerating | SAME | RIF:6 (R14) | keep as how to text
F206 | _COMMON_RULES_v5.md:44 | Always 12: hygiene checks on every new or split test | SAME | RIF:6 (R11) | keep as how to text
F207 | _COMMON_RULES_v5.md:44 | Always 12: "There is no count cap." | CONTRADICTS: RIF sets soft 70 and hard 100 | RIF:8 | delete as superseded by RIF:8
F208 | _COMMON_RULES_v5.md:45 | Always 13: unchanged lines that passed last round are reviewer variance, KEEP with diff | SAME | RIF:6 (R17) | keep as how to text
F209 | _COMMON_RULES_v5.md:46 | Always 14: look up each FIX in FIX_SIDE_EFFECTS and re-check | SAME | RIF:6 (R11) | keep as how to text
F210 | _COMMON_RULES_v5.md:47 | Always 15: never import tests/ or solution/ without PYTHONDONTWRITEBYTECODE | MISSING | none | keep as how to text
F211 | _COMMON_RULES_v5.md:48 | Always 16: solver, kill test and blind runs in Docker only, dockfree.py START=yes, memory 4g, cpus 2, wall cap; never on the host | SAME (fixed 4g and 2 cpus where RIF makes limits settings; dockfree.py is primary here, fallback in RIF) | RIF:12 (R19, R20) | keep as how to text; read limits from the settings file
F212 | _COMMON_RULES_v5.md:49 | Always 17: Law-1 WRONG only, timeout counts only with cost 10 to 30 percent | SUPERSEDED: the line's own v3.8 bracket says R0 overrides it (no cap) | _COMMON_RULES_v5.md:49 bracket, LEVER_RULES_v3.md:91 | delete as superseded
F213 | _COMMON_RULES_v5.md:49 | Always 17: v3.7 design bars (first write at most 60, blinds at most 65, mid at most 20, DESIGN READY (a) to (e)), overnight go | MISSING | none | ASK AYUSH (same as F16, F17)
F214 | _COMMON_RULES_v5.md:50 | Always 18: never repeat an identical tool call 3 times in a row | MISSING | none | keep as how to text
F215 | _COMMON_RULES_v5.md:53 | J1 lint: no figure criterion at all | MISSING | none | keep as how to text
F216 | _COMMON_RULES_v5.md:54 | every judge.toml has J3a (minus 3) | SAME | RIF:11 (R29) | keep as how to text
F217 | _COMMON_RULES_v5.md:54 | every judge.toml has J3b, J3c when needed, and exactly one behavioural J4 for code | MISSING | none | keep as how to text
F218 | _COMMON_RULES_v5.md:55 | never add keys to criterion.annotations | MISSING | none | keep as how to text
F219 | _COMMON_RULES_v5.md:56 | judge half is a probe band; a criterion with no oracle shows row is removed | MISSING | none | keep as how to text
F220 | _COMMON_RULES_v5.md:57 | the grader read negative is anchored to /tests/ at the root or /logs/verifier | MISSING | none | keep as how to text
F221 | _COMMON_RULES_v5.md:58 | a time or memory limit is at least 3x the oracle's measured time, or there is no limit | MISSING; differs from 20261101_route1_notes.md:8 (reference at most 1/4 of the limit, so at least 4x) | RIF:10 (runtime lever) | ASK AYUSH (3x or 4x)
F222 | _COMMON_RULES_v5.md:61 | label every score "tests-only" unless a real judged run happened | MISSING | none | keep as how to text
F223 | _COMMON_RULES_v5.md:62 | gate tests under 85, rubric under 85, final under 40 on 1 valid run of frozen QC passed bytes | SAME | RIF:9 (R26) | keep as how to text
F224 | _COMMON_RULES_v5.md:63 | kit floors at least 10 tests and 8 criteria | SAME | RIF:8 (QC minimum) | keep as how to text
F225 | _COMMON_RULES_v5.md:63 | no upper cap on tests or criteria; above 35 record the WARN, never merge to get under 35 | CONTRADICTS: RIF sets soft 70 and hard 100 | RIF:8 | delete as superseded by RIF:8
F226 | _COMMON_RULES_v5.md:64 | QC target: zero fails, every minor or warn left genuine and as few as possible; fix a real minor when it keeps every lever | CONTRADICTS in part: RIF passes QC at no fail in 2 runs in a row and accepts a minor that does not repeat | RIF:7 (R18) | ASK AYUSH (propose: replace with RIF:7)
F227 | _COMMON_RULES_v5.md:65 | 3 blind reads; a rule counts when 2 of 3 get it wrong; harden or redesign when the lower bound final is above 70 | MISSING; the 70 threshold predates the final under 40 gate; route 1 needs no blinds before QC | RIF:9 | ASK AYUSH
F228 | _COMMON_RULES_v5.md:65 | no auto park; only Ayush parks a task | MISSING, looks still in force | none | add to RULES_IN_FORCE (same wording as F88)
F229 | _COMMON_RULES_v5.md:65 | old kill rule (park above 70; tests 100 on 2 runs park; no round after LAST) kept for arithmetic | SUPERSEDED: the same line says no auto park, kill rule kept for arithmetic only | _COMMON_RULES_v5.md:65 | delete as superseded
F230 | _COMMON_RULES_v5.md:66 | order: design, build, 3 blinds, full QC, recheck, freeze, 1 harness run | MISSING; differs from 20261101_route1_notes.md:17 | none | ASK AYUSH (which order is current)
F231 | _COMMON_RULES_v5.md:66 | a missed gate is never re-run on the same bytes | SAME | RIF:9 (R27) | keep as how to text
F232 | _COMMON_RULES_v5.md:66 | regrade diagnostic only, with the v3.7 judge only exception | MISSING, looks still in force | none | add to RULES_IN_FORCE (same wording as F96)
F233 | _COMMON_RULES_v5.md:67 | packaging integrity: package from exactly the frozen bytes of the gate run; never package a regrade outside the exception | MISSING, looks still in force | none | add to RULES_IN_FORCE: "A pushed bundle is packaged from exactly the frozen bytes of the gate run, with that run's scores."
F234 | _COMMON_RULES_v5.md:68 | a run with a grader error is never a baseline | MISSING, looks still in force | none | add to RULES_IN_FORCE (same wording as F99)
F235 | _COMMON_RULES_v5.md:71 | every report ends with "Lessons for the master", at most 5 lines | SAME | RIF:4 (R4) | keep as how to text
F236 | _COMMON_RULES_v5.md:74 | final reply at most 12 lines | MISSING | none | keep as how to text

pipeline_v4/PLAN.md
F237 | pipeline_v4/PLAN.md:8 | decision 1: no harden after a QC pass; later changes only through stage 7, recheck QC and 1 new run | SAME | RIF:7 (R16) | keep as how to text
F238 | pipeline_v4/PLAN.md:8 | decision 1: order design, build, blind, QC, freeze, 1 run | MISSING; differs from 20261101_route1_notes.md:17 | none | ASK AYUSH
F239 | pipeline_v4/PLAN.md:9 | decision 2: QC round 2 and later is recheck mode with carry over | MISSING | none | keep as how to text
F240 | pipeline_v4/PLAN.md:10 | decision 3: check cap option A only, over 35 is a recorded warn | CONTRADICTS: RIF sets soft 70 and hard 100 | RIF:8 | delete as superseded by RIF:8
F241 | pipeline_v4/PLAN.md:11 | decision 4: Law-1, WRONG output only; amended timeout counts at 10 to 30 percent | SUPERSEDED: LEVER_RULES_v3.md:91 overrides v3.4 Law-1 and v3.5 condition 3 | LEVER_RULES_v3.md:91 | delete as superseded
F242 | pipeline_v4/PLAN.md:12 | decision 5: regrade diagnostic only, judge only exception | MISSING, looks still in force | none | add to RULES_IN_FORCE (same wording as F96)
F243 | pipeline_v4/PLAN.md:13 | decision 6: a missed gate gets no re-run on the same bytes | SAME | RIF:9 (R27) | keep as how to text
F244 | pipeline_v4/PLAN.md:14 | decision 7: honesty negative minus 3 in every judge, disjoint from other negatives | SAME | RIF:11 (R29) | keep as how to text
F245 | pipeline_v4/PLAN.md:15 | decision 8: the master edits tests or judge so the score drops, "in a form QC accepts" | ASK AYUSH, agreed line check | none | ASK AYUSH, agreed line check (not rewritten)
F246 | pipeline_v4/PLAN.md:16 | decision 9: auto mode QC runs 2 oracle and 1 nop in Step 10 | MISSING; differs from state.json:30 (oracle 3 runs) | none | keep as how to text
F247 | pipeline_v4/PLAN.md:19 | stage 1: kill test in Docker only with memory and wall cap | SAME | RIF:12 (R19) | keep as how to text
F248 | pipeline_v4/PLAN.md:19 | stage 1: a lever passes only if every strong solver loses by WRONG | SUPERSEDED: LEVER_RULES_v3.md:91 (v3.8) | LEVER_RULES_v3.md:91 | delete as superseded
F249 | pipeline_v4/PLAN.md:23 | stage 2: CL-2 vacuity probe by script, any pass is a fail | SAME | RIF:6 (R12) | keep as how to text
F250 | pipeline_v4/PLAN.md:24 | stage 2: every negative silent on the oracle and on 2 honest variants | MISSING | none | keep as how to text
F251 | pipeline_v4/PLAN.md:25 | stage 2: promise table, an empty row fails | MISSING | none | keep as how to text
F252 | pipeline_v4/PLAN.md:26 | stage 2: literal table, an unreachable or invented literal fails | MISSING | none | keep as how to text
F253 | pipeline_v4/PLAN.md:28 | stage 3: 3 blinds must lose at least 10 percent, else back to design; v3.7 bars | MISSING; route 1 needs no blinds before QC (20261101_route1_notes.md:47) | none | ASK AYUSH
F254 | pipeline_v4/PLAN.md:30 | G1 never paste QC's "Fix:" text | SAME | RIF:6 (R8) | keep as how to text
F255 | pipeline_v4/PLAN.md:31 | G2 never move an assert or weight onto a conduct or route criterion | SAME | RIF:6 (R9) | keep as how to text
F256 | pipeline_v4/PLAN.md:32 | G3 never delete a clause or grader without naming what grades the rest | SAME | RIF:6 (R10) | keep as how to text
F257 | pipeline_v4/PLAN.md:33 | G4 re-check every touched check | SAME | RIF:6 (R11) | keep as how to text
F258 | pipeline_v4/PLAN.md:34 | G5 vacuity probe again | SAME | RIF:6 (R12) | keep as how to text
F259 | pipeline_v4/PLAN.md:35 | G6 docs and TRUTH regenerated last by script | SAME | RIF:6 (R13) | keep as how to text
F260 | pipeline_v4/PLAN.md:36 | G7 byte diff before regenerating tests | SAME | RIF:6 (R14) | keep as how to text
F261 | pipeline_v4/PLAN.md:37 | stage 5: a finding on an unchanged line must answer the earlier pass reason | SAME | RIF:6 (R17) | keep as how to text
F262 | pipeline_v4/PLAN.md:37 | stage 5: 0 fails then freeze | CONTRADICTS: RIF needs no fail in 2 QC runs in a row | RIF:7 (R18) | delete as superseded by RIF:7
F263 | pipeline_v4/PLAN.md:38 | stage 6: Step 10 complete on the frozen bytes before push | MISSING, looks still in force | none | add to RULES_IN_FORCE: "Before push, QC Step 10 (oracle, nop, stub, owner only) is complete on the frozen bytes."
F264 | pipeline_v4/PLAN.md:38 | stage 6: gate tests under 85, rubric under 85, final under 40 | SAME | RIF:9 (R26) | keep as how to text
F265 | pipeline_v4/PLAN.md:38 | stage 6: package from exactly those bytes; Output_RFP tests/ equals frozen tests/ | MISSING, looks still in force | none | add to RULES_IN_FORCE (same wording as F233)
F266 | pipeline_v4/PLAN.md:39 | stage 7: never fit a check to one run's quirk; remove or down weight only to undo double payment | MISSING | none | keep as how to text
F267 | pipeline_v4/PLAN.md:49 | QC safe form table: each edit done in the "QC-safe form", "flagged if done directly" | ASK AYUSH, agreed line check | none | ASK AYUSH, agreed line check (not rewritten)
F268 | pipeline_v4/PLAN.md:59 | regrade never push evidence except the judge only exception | MISSING, looks still in force | none | add to RULES_IN_FORCE (same wording as F96)
F269 | pipeline_v4/PLAN.md:63 | auto mode: real model harbor runs stay denied; only oracle and nop allowed | MISSING | none | keep as how to text
F270 | pipeline_v4/PLAN.md:65 | guard: 3 Docker runs per auto QC session, one after another; at most 2 Docker heavy jobs at once | CONTRADICTS: RIF makes worker and harness limits settings | RIF:12 (R21, R22) | delete as superseded by RIF:12 (move the numbers to the settings file)
F271 | pipeline_v4/PLAN.md:66 | an auto mode QC sign off records Step 10 as reduced; the rest is owed before push | MISSING, looks still in force | none | add to RULES_IN_FORCE (same wording as F263)
F272 | pipeline_v4/PLAN.md:76 | master spawns at most 2 Docker heavy workers at once | CONTRADICTS: RIF makes these limits settings | RIF:12 (R21) | delete as superseded by RIF:12
F273 | pipeline_v4/PLAN.md:99 | never package a regrade except under the v3.7 exception | MISSING, looks still in force | none | add to RULES_IN_FORCE (same wording as F96)

KNOWLEDGE.md
F274 | KNOWLEDGE.md:6 | our flow: probe before QC, kill rule tests at least 95 drop or swap, stop at first PASS, 2 runs under gate | CONTRADICTS: RIF gate is 1 run of frozen QC passed bytes; no drop without Ayush | RIF:9, RIF:8 | delete as superseded by RIF:9 and pipeline v4
F275 | KNOWLEDGE.md:7 | each lever alone costs at least 25 percent; all but one right stays overall under 70 | CONTRADICTS: RIF primary lever 40 percent and final under 40 | RIF:9, RIF:10 | delete as superseded by RIF:9 and RIF:10
F276 | KNOWLEDGE.md:9 | weights in plus or minus 1, 3, 5; sum of negatives at most sum of positives | MISSING (kit rule) | none | keep as how to text
F277 | KNOWLEDGE.md:14 | run the generator from a copy or with IBG_MEMORY_PATH and PYTHONDONTWRITEBYTECODE | MISSING | none | keep as how to text
F278 | KNOWLEDGE.md:30 | QC ids get renumbered: match on ID plus wording | SAME | RIF:14 (R33) | keep as how to text
F279 | KNOWLEDGE.md:39 | tests at least 10, judge at least 8 | SAME | RIF:8 (QC minimum) | keep as how to text
F280 | KNOWLEDGE.md:39 | NO upper cap; above 35 WARN recorded | CONTRADICTS: RIF sets soft 70 and hard 100 | RIF:8 | delete as superseded by RIF:8
F281 | KNOWLEDGE.md:39 | QC target: zero fails, only genuine minors or warns, as few as possible | CONTRADICTS in part: RIF uses the Q95 definition | RIF:7 (R18) | ASK AYUSH (propose: replace with RIF:7)
F282 | KNOWLEDGE.md:46 | ours: final reward under 70 on 2 valid runs | CONTRADICTS: RIF gate tests under 85, rubric under 85, final under 40 on 1 run | RIF:9 | delete as superseded by RIF:9
F283 | KNOWLEDGE.md:68 | anti cheat: keep nothing graded reachable; use explicit specific prohibitions | MISSING | none | keep as how to text
F284 | KNOWLEDGE.md:72 | only real runs count; a reviewer rating is not a hardness measure | MISSING, looks still in force | none | add to RULES_IN_FORCE: "Only real runs measure hardness; a reviewer rating never gates."
F285 | KNOWLEDGE.md:94 | harness queue ask line "gate: tests<100, rubric<100, overall<70" | CONTRADICTS: RIF gate tests under 85, rubric under 85, final under 40 | RIF:9 | delete as superseded by RIF:9 (example should read the settings value)
F286 | KNOWLEDGE.md:96 | an issued run prompt holds only the paste text; each bundle path once per ask | MISSING | none | keep as how to text
F287 | KNOWLEDGE.md:97 | the harness chat never edits bundles and never retries a startup network error | MISSING | none | keep as how to text
F288 | KNOWLEDGE.md:99 | check job config path and tree sha at every intake | MISSING, looks still in force | none | keep as how to text
F289 | KNOWLEDGE.md:102 | older samples outside Pass@1_New are QC failed: do not mine them | MISSING; source may now be anubis-stage-2 (RULE_REVIEW R34 note) | none | ASK AYUSH
F290 | KNOWLEDGE.md:104 | Q57 scope: ONLY Pass@1_New/Dinshi_Jain/Aditya Patel/ | MISSING; looks stale | none | ASK AYUSH
F291 | KNOWLEDGE.md:107 | after a missed gate no re-run on the same bytes | SAME | RIF:9 (R27) | keep as how to text
F292 | KNOWLEDGE.md:108 | TIMEOUT or CRASH counts only on hidden scale with a stated limit and cost 10 to 30 percent | CONTRADICTS: LEVER_RULES_v3.md:91 removed the cap; RIF says timeout lever only as an extra unless Ayush says so | RIF:10 | ASK AYUSH
F293 | KNOWLEDGE.md:109 | WRONG_UNGRADED rows only by reading, never by keyword | MISSING | none | keep as how to text
F294 | KNOWLEDGE.md:110 | QC safe form table, "flagged if done directly" | ASK AYUSH, agreed line check | none | ASK AYUSH, agreed line check (not rewritten)
F295 | KNOWLEDGE.md:118 | next step by the gate tests under 85, rubric under 85, final under 40 | SAME | RIF:9 (R26) | keep as how to text
F296 | KNOWLEDGE.md:119 | regrade diagnostic only, judge only exception | MISSING, looks still in force | none | add to RULES_IN_FORCE (same wording as F96)
F297 | KNOWLEDGE.md:120 | at every freeze record the tree sha; intake.py refuses a gate_run row when the sha differs | MISSING, looks still in force | RIF:9 (frozen bytes) | add to RULES_IN_FORCE: "Every freeze records the tree sha; a gate run counts only on that sha."

state.json (standing rules part)
F298 | state.json:27 | per_run_gate | SUPERSEDED: value reads "SUPERSEDED by test_phase_gate (rule 37)" | state.json:126 | delete as superseded
F299 | state.json:28 | design aim careful solver tests 0.10 to 0.20 | MISSING; looks stale against design for tests at most 60 | none | ASK AYUSH
F300 | state.json:29 | caps tests at most 35, judge at most 35; PL acceptance zero findings incl warns | CONTRADICTS: RIF counts soft 70 hard 100; QC pass by Q95 | RIF:8, RIF:7 | delete as superseded by RIF:8 and RIF:7
F301 | state.json:30 | oracle 3 runs 1.0, nop 1 run 0.0, stub if possible | MISSING; differs from pipeline_v4/PLAN.md:16 (2 oracle in auto) | none | keep as how to text
F302 | state.json:31 | test_phase_gate tests under 100, rubric under 100, overall under 70 | CONTRADICTS: RIF gate 85, 85, 40 (same key at state.json:126 has the live value) | RIF:9 | delete as superseded by RIF:9
F303 | state.json:32 | acceptance zero QC findings (fail, minor, warn) | CONTRADICTS: RIF passes QC by Q95 (minor accepted if it does not repeat) | RIF:7 (R18) | delete as superseded by RIF:7
F304 | state.json:33 | kill rule v4: every strong solver loses by WRONG (Law 1); 3 blinds lose at least 10 percent; no probe before QC | SUPERSEDED: LEVER_RULES_v3.md:91 overrides Law-1 | LEVER_RULES_v3.md:91 | delete as superseded
F305 | state.json:34 | push needs 1 valid run on frozen QC passed bytes; any change voids it; no re-run on the same bytes | SAME | RIF:9 (R26, R27) | keep as how to text
F306 | state.json:52 | STRICT: allowed repos only 4 listed; read only git; never pull, commit, push; give Ayush the commands | CONTRADICTS: list lacks master-task-chat (R34 decision); read only part SAME | RIF:14 (R34) | add to RULES_IN_FORCE (same repo list as F186)
F307 | state.json:53 | all discussion work in the temp folder; reorganise later; ask before delete | MISSING; looks stale (20 Oct temp folder) | none | ASK AYUSH
F308 | state.json:54 | do not hardcode generator or QC rules into prompts | SAME | RIF:14 (R33) | keep as how to text
F309 | state.json:55 | QC must give zero findings incl warns | SUPERSEDED: line starts "SUPERSEDED 24 Oct" | state.json:55 | delete as superseded
F310 | state.json:56 | do not run tasks myself; write prompts | SAME | RIF:2 (R1) | keep as how to text
F311 | state.json:57 | keep only important instructions; mark guesses UNVERIFIED | SAME in part (R5); "mark guesses UNVERIFIED" MISSING | RIF:4 (R5) | add to RULES_IN_FORCE: "Mark guesses UNVERIFIED."
F312 | state.json:58 | update records as soon as something is decided | MISSING | RIF:4 (R3 to R5, related) | keep as how to text
F313 | state.json:59 | never use a frozen QC copy | SAME | RIF:14 (R33) | keep as how to text
F314 | state.json:60 | 1 trajectory run per task while building; 8 runs only on final approval | MISSING; RIF makes paid runs per day a setting | RIF:13 (R24) | ASK AYUSH
F315 | state.json:61 | context budget: the master stays light; big reads go to other sessions | SAME | RIF:2 (R1) | keep as how to text
F316 | state.json:62 | hardness lives mainly in the instruction or task, not only in tests and rubric; traps genuine | MISSING; touches R28 and PATTERNS | RIF:15 (R28) | ASK AYUSH
F317 | state.json:63 | criteria a typical agent run can genuinely fail | MISSING | none | keep as how to text
F318 | state.json:64 | ORACLE/NOP: use intake/ql_oracle_nop_procedure.md (oracle up to 3x) | MISSING; may be stale | none | ASK AYUSH
F319 | state.json:65 | re-confirm every QC FAIL in a separate session; fix only REAL | SAME | RIF:7 (false positive review) | keep as how to text
F320 | state.json:66 | stub run with QL copy steps; drop if not possible | MISSING | none | keep as how to text
F321 | state.json:68 | follow our QC, weighted partial credit (CL-4), not binary pass or fail | MISSING | none | keep as how to text
F322 | state.json:69 | ChatGPT gives premise; target careful model tests 0.10 to 0.20 | MISSING; looks stale | none | ASK AYUSH
F323 | state.json:70 | a reviewer rating never is the hardness gate; only real runs count | MISSING, looks still in force | none | add to RULES_IN_FORCE (same wording as F284)
F324 | state.json:71 | the clone's Input_Bundle_QC is the live QC; QC assigned/ is not | SAME | RIF:14 (R33) | keep as how to text
F325 | state.json:72 | TRIAL FREEZE: do not bump templates or rules on 1 or 2 results during the trial | MISSING; looks expired (trial 21 to 24 Oct) but not marked | none | ASK AYUSH
F326 | state.json:73 | TRIAL USE: apply pending lessons only through issued prompts | MISSING; looks expired, not marked | none | ASK AYUSH
F327 | state.json:74 | REPLY FILES: master creates an empty .md path first; never store raw replies in master_chat_tasks | MISSING | RIF:4 (R5, related) | keep as how to text
F328 | state.json:75 | RESULT COPY: copy, never move, read only on the source | MISSING | none | keep as how to text
F329 | state.json:76 | INTAKE: verify every input on disk before answering or recording | SAME | RIF:2 (R1) | keep as how to text
F330 | state.json:77 | CHMOD: chown root and chmod 755 /logs/verifier; pins | MISSING | none | keep as how to text
F331 | state.json:78 | HARNESS PULL: always give Ayush the ff only fetch and merge command, never plain git pull | SAME | RIF:14 (R34, Ayush runs every pull) | keep as how to text
F332 | state.json:79 | SESSIONS: max 6 live sessions; Docker heavy max 2 | CONTRADICTS: RIF makes worker limits settings | RIF:12 (R21) | delete as superseded by RIF:12 (value into settings)
F333 | state.json:80 | ORACLE COUNT: master templates default oracle x3; report states "Oracle x3 per Ayush; the kit asks x5"; "Do not push this to other chats/PL" | ASK AYUSH, unclear what may not be passed on; possible agreed line check | none | ASK AYUSH (not rewritten)
F334 | state.json:81 | QC CHAIN (17:02) | SUPERSEDED: line starts "SUPERSEDED by QC CHAIN v2" | state.json:86 | delete as superseded
F335 | state.json:82 | SESSION COUNT: 6 session cap counts only working sessions | CONTRADICTS: RIF makes worker limits settings | RIF:12 (R21) | delete as superseded by RIF:12
F336 | state.json:83 | SESSION COUNT update: 5 slots for working sessions | CONTRADICTS: RIF makes worker limits settings | RIF:12 (R21) | delete as superseded by RIF:12
F337 | state.json:84 | BOARD: every issued session gets a 7 char sha; master verifies on disk | SAME | RIF:5 (R6), RIF:2 (R1) | keep as how to text
F338 | state.json:85 | MINOR RULE | SUPERSEDED: line starts "SUPERSEDED 24 Oct by dec 101" | state.json:85 | delete as superseded
F339 | state.json:86 | QC CHAIN v2: max 3 rounds; max 2 fix rounds after the first QC, enforced by tools/issue.py | CONTRADICTS: RIF has no round caps; issue.py caps become warnings | RIF:8 (R15) | delete as superseded by RIF:8
F340 | state.json:86 | every bundle has QC_DEFENCE.md and XREF.md; xref_check.py 0 findings before gates | MISSING | none | keep as how to text
F341 | state.json:87 | never harbor delete; images pruned only in idle cleanup | SAME | RIF:12 (R23) | keep as how to text
F342 | state.json:87 | bundle lock; timestamps with seconds and random hex; never rename a slug | MISSING | none | keep as how to text
F343 | state.json:88 | STATUS: registry/tasks.json via status.py is the source for task stats | MISSING | none | keep as how to text
F344 | state.json:89 | TEST-PHASE GATE: tests under 100, rubric under 100, overall under 70 | CONTRADICTS: RIF gate 85, 85, 40; not marked superseded in the file | RIF:9 | delete as superseded by RIF:9
F345 | state.json:90 | DROP RULE (permanent): dropped after 3 rebuild or harden rounds | CONTRADICTS: RIF has no round caps | RIF:8 (R15) | delete as superseded by RIF:8
F346 | state.json:91 | DEV RESEARCH folder and research roles | MISSING | none | keep as how to text
F347 | state.json:92 | PROBE FIRST: one private probe run before QC | SUPERSEDED: state.json:33 says "no probe before QC (pipeline v4 27 Oct)" | state.json:33 | delete as superseded
F348 | state.json:93 | STOP AT PASS: no harden after a QC PASS | SAME | RIF:7 (R16) | keep as how to text
F349 | state.json:93 | drop rule enforced by issue.py refusal; override only by Ayush's verbatim line | CONTRADICTS: issue.py round caps become warnings, never refusals | RIF:8 (R15) | delete as superseded by RIF:8
F350 | state.json:94 | NOISE CHECK: unchanged and passed lines are noise, KEEP with diff evidence | SAME | RIF:6 (R17) | keep as how to text
F351 | state.json:94 | never prune QC copies | MISSING | none | keep as how to text
F352 | state.json:95 | no KEEP or FIX ruling without the kit line and the side effect row | MISSING | none | keep as how to text
F353 | state.json:96 | only Anubis_Tasks_Samples/Pass@1_New/ holds current passing peers | MISSING; may be stale (anubis-stage-2) | none | ASK AYUSH
F354 | state.json:105 | BASELINE RULE: grader error run never a baseline; Phase A check at every intake | MISSING, looks still in force | none | add to RULES_IN_FORCE (same wording as F99)
F355 | state.json:106 | HOLDS: before any trajectory, a P13 blind must score tests under 100 | MISSING; looks stale | none | ASK AYUSH
F356 | state.json:108 | READY FOR TRAJECTORY: QC 0 FAIL, oracle x3, STACKING pass, reflex program at most 0.20 | CONTRADICTS: QC pass is Q95 (RIF:7); the reflex score is retired (QC_FIX_PLAYBOOK_v3.md:84) | RIF:7 | ASK AYUSH
F357 | state.json:110 | TODAY 23 Oct ONLY: Docker max 2 waived; blind solve skipped | SUPERSEDED: the line limits itself to 23 Oct | state.json:111 | delete as superseded
F358 | state.json:111 | FROM 24 Oct: Docker max 2; blind solve session for tasks with no trajectory | CONTRADICTS: RIF makes Docker and worker limits settings | RIF:12 (R21) | delete as superseded by RIF:12 (blind part ASK AYUSH)
F359 | state.json:113 | every session report ends with "Lessons for the master"; master copies them | SAME | RIF:4 (R4) | keep as how to text
F360 | state.json:114 | CHECKPOINT: a log checkpoint line before every compaction | MISSING, looks still in force | RIF:3 (R2, related) | add to RULES_IN_FORCE: "Before compaction write a checkpoint line (phase, running sessions, next step)."
F361 | state.json:115 | every prompt passes PROMPT_CHECKLIST.md before its link is given | MISSING | none | keep as how to text
F362 | state.json:117 | COHORT one sweep: every stated rule gets a test or is removed | MISSING; task specific | none | keep as how to text
F363 | state.json:126 | test_phase_gate tests under 85, rubric under 85, final under 40 | SAME | RIF:9 (R26) | keep as how to text

README.md
F364 | README.md:3 | the master chat is an advisor | CONTRADICTS: RIF says the master is the brain (plans, tunes prompts, verifies, flags, reports) | RIF:2 (R1) | delete as superseded by RIF:2
F365 | README.md:3 | only the master chat writes here, only through the tools | SAME | RIF:4 (R3) | keep as how to text
F366 | README.md:5 | 7 step read order after any compaction | CONTRADICTS: RIF reads the state card first and loads only live work | RIF:3 (R2) | delete as superseded by RIF:3
F367 | README.md:7 | answer any task question from status.py, never from memory | MISSING | none | keep as how to text
F368 | README.md:8 | list open questions older than 12 h to Ayush (U7) | MISSING, looks still in force (RULE_REVIEW R2 improvement 12, accepted) | none | add to RULES_IN_FORCE: "Questions to Ayush older than 12 hours are listed first."
F369 | README.md:10 | route 1 R0 overrides older lever text everywhere | CONTRADICTS: RIF changes R0 (PATTERNS families, CR7, timeout as extra) | RIF:10 | ASK AYUSH (state that RIF wins)
F370 | README.md:12 | pipeline_v4/PLAN.md wins where it differs | MISSING; authority order now unclear | none | ASK AYUSH
F371 | README.md:14 | re-check live state before acting; run TZ=Asia/Kolkata date before writing a time | MISSING | none | keep as how to text
F372 | README.md:19 | issue.py refuses past caps (2 fix rounds, 2 QC rounds, drop at 3, 8 session time box) unless override | CONTRADICTS: decided, round caps become warnings, never refusals | RIF:8 (R15) | delete as superseded by RIF:8
F373 | README.md:21 | every build and fix session runs precheck.sh until PRECHECK CLEAN | MISSING | none | keep as how to text
F374 | README.md:28 | after any write, view the result before saying it is done | MISSING | RIF:2 (R1 verifies, related) | keep as how to text
F375 | README.md:31 | "WRONG-only wording below is superseded" | SUPERSEDED: the line's own [2 Nov v3.8] bracket | README.md:31 bracket | delete as superseded
F376 | README.md:31 | gate met (tests<100, rubric<100, overall<70) = push | CONTRADICTS: RIF gate 85, 85, 40 | RIF:9 | delete as superseded by RIF:9
F377 | README.md:31 | count cap option A (over 35 = warn) | CONTRADICTS: RIF soft 70, hard 100 | RIF:8 | delete as superseded by RIF:8
F378 | README.md:31 | harness: one Docker task at a time, max 2 Docker heavy jobs on the Mac | CONTRADICTS: RIF makes these limits settings | RIF:12 (R21) | delete as superseded by RIF:12
F379 | README.md:31 | no harden after QC PASS | SAME | RIF:7 (R16) | keep as how to text
F380 | README.md:31 | honesty negative minus 3 in every judge | SAME | RIF:11 (R29) | keep as how to text
F381 | README.md:31 | no re-run on the same bytes after a missed gate | SAME | RIF:9 (R27) | keep as how to text
F382 | README.md:34 | U3 every lesson gets template_change or no change with reason | MISSING | RIF:4 (R4, related) | keep as how to text
F383 | README.md:35 | U4 no KEEP or FIX ruling without the kit line and side effect row | MISSING | none | keep as how to text
F384 | README.md:36 | U9 every plan states the harness runs it needs | MISSING | RIF:13 (cost, related) | keep as how to text
F385 | README.md:37 | U12 stop at the first QC PASS | SAME | RIF:7 (R16) | keep as how to text
F386 | README.md:38 | U13 unchanged and passed lines are noise, KEEP with diff | SAME | RIF:6 (R17) | keep as how to text
F387 | README.md:39 | U14 keep every QC report copy; never prune | MISSING | none | keep as how to text
F388 | README.md:40 | verify every input on disk first, then record, then answer | SAME | RIF:2 (R1) | keep as how to text
F389 | README.md:62 | store only rules, decisions, state, failures, lessons, scores, levers, ideas; never chat summaries | SAME | RIF:4 (R5) | keep as how to text
F390 | README.md:62 | mark guesses UNVERIFIED; IST times from date; no secrets | MISSING | none | add to RULES_IN_FORCE (fold with F311: "Mark guesses UNVERIFIED; no secrets.")
F391 | README.md:67 | if 3 tasks leak or fail the same way, change the template, not the weights | MISSING (close to R4 "a lesson that repeats becomes a tool check") | RIF:4 (R4) | keep as how to text
F392 | README.md:70 | allowed repos 4 listed, read only git; Ayush runs every pull, commit and push | CONTRADICTS: list lacks master-task-chat (R34 decision); read only part SAME | RIF:14 (R34) | add to RULES_IN_FORCE (same repo list as F186)
F393 | README.md:71 | never edit the generator, QC kit, QC assigned/ or my tasks/ without "proceed" | SAME | RIF:14 (R35) | keep as how to text
F394 | README.md:72 | when two authorities conflict, report it to Ayush; never pick one | SAME | RIF:2 (R1 flags contradictions), RIF:1 | keep as how to text
F395 | README.md:73 | handoff = board sha, step, clickable file link only | SAME | RIF:5 (R6) | keep as how to text
F396 | README.md:74 | long jobs run in the background with logs | MISSING | none | keep as how to text
F397 | README.md:77 | master process failures to lessons.jsonl; Ayush's corrections verbatim to feedback.jsonl, same turn | SAME | RIF:4 (R4) | keep as how to text

issue.py
F398 | issue.py:16 | refuses a fix session after 2 fix rounds since the last QC | CONTRADICTS: decided, round caps become warnings, never refusals | RIF:8 (R15) | delete as superseded by RIF:8 (turn into a warning)
F399 | issue.py:17 | refuses a QC session after 2 QC rounds | CONTRADICTS: same decision | RIF:8 (R15) | delete as superseded by RIF:8 (turn into a warning)
F400 | issue.py:17 | refuses a QC session when the task already passed QC (stop at first PASS) | SAME (rule), but enforced as a refusal | RIF:7 (R16) | ASK AYUSH (stays a refusal, or a warning like the round caps)
F401 | issue.py:18 | refuses a harden session after a QC PASS | SAME (rule), enforced as a refusal | RIF:7 (R16) | ASK AYUSH (same question as F400)
F402 | issue.py:19 | drop rule: refuses after 3 harden or rebuild rounds | CONTRADICTS: no round caps; refusals become warnings | RIF:8 (R15) | delete as superseded by RIF:8 (turn into a warning)
F403 | issue.py:20 | refuses any session for a dropped, killed or parked task | MISSING; consistent with "parked only on Ayush's word" | none | keep as how to text
F404 | issue.py:21 | time box: refuses after 8 sessions for a task since its last stage change | CONTRADICTS: no caps on session count | RIF:8 (R15) | delete as superseded by RIF:8 (turn into a warning)
F405 | issue.py:31 | lint hard refusal: a leftover template placeholder | MISSING | none | keep as how to text
F406 | issue.py:32 | lint hard refusal: two different oracle counts outside kit lines | MISSING | none | keep as how to text
F407 | issue.py:35 | lint warning: a gate target that differs from the live gate (LIVE_GATE at :60 = tests 85, rubric 85, final 40) with no decisions row | SAME (values); hardcoded at issue.py:60 while RIF:9 makes the gate a setting | RIF:9 | keep as how to text; read the gate from the settings file
F408 | issue.py:38 | lint warning: a predicted final bar with no "Reachable:" line | MISSING | none | keep as how to text
F409 | issue.py:217 | any cap refusal stands unless --override with Ayush's exact words | CONTRADICTS: decided, round caps are warnings, never refusals | RIF:8 (R15) | delete as superseded by RIF:8 (print a warning and log it)
F410 | issue.py:28 | the handoff printed is the only thing Ayush gets: board sha, step, one clickable link | SAME | RIF:5 (R6) | keep as how to text

SUMMARY

Counts per verdict per file (SAME, CONTRADICTS, MISSING, SUPERSEDED, ASK AYUSH; rows):
1. LEVER_RULES_v3.md: SAME 10, CONTRADICTS 15, MISSING 58, SUPERSEDED 5, ASK AYUSH 0; 100 rows
2. 20261101_route1_notes.md: SAME 3, CONTRADICTS 4, MISSING 15, SUPERSEDED 1, ASK AYUSH 0; 30 rows
3. QC_FIX_PLAYBOOK_v3.md: SAME 14, CONTRADICTS 4, MISSING 26, SUPERSEDED 0, ASK AYUSH 2; 49 rows
4. _COMMON_RULES_v5.md: SAME 19, CONTRADICTS 3, MISSING 29, SUPERSEDED 2, ASK AYUSH 0; 57 rows
5. pipeline_v4/PLAN.md: SAME 14, CONTRADICTS 4, MISSING 12, SUPERSEDED 2, ASK AYUSH 2; 37 rows
6. KNOWLEDGE.md: SAME 4, CONTRADICTS 6, MISSING 10, SUPERSEDED 0, ASK AYUSH 1; 24 rows
7. state.json: SAME 15, CONTRADICTS 13, MISSING 17, SUPERSEDED 7, ASK AYUSH 1; 66 rows
8. README.md: SAME 12, CONTRADICTS 8, MISSING 12, SUPERSEDED 1, ASK AYUSH 0; 34 rows
9. issue.py: SAME 4, CONTRADICTS 5, MISSING 3, SUPERSEDED 0, ASK AYUSH 0; 13 rows
10. All files: SAME 95, CONTRADICTS 62, MISSING 182, SUPERSEDED 18, ASK AYUSH 6; 410 rows
11. Proposed actions over all rows: keep as how to text 232, ASK AYUSH 72, delete as superseded 60, add to RULES_IN_FORCE 46 (many add rows repeat the same wording across files).
12. ASK AYUSH verdict rows with the note "agreed line check": F131, F132 (QC_FIX_PLAYBOOK_v3.md:3 and :10), F245 (pipeline_v4/PLAN.md:15), F267 (pipeline_v4/PLAN.md:49), F294 (KNOWLEDGE.md:110). F333 (state.json:80) is unclear and listed as a possible one. None was rewritten.
13. Long running sessions: no active rule found that stops a long running session; issue.py:21 caps the number of sessions per task (F404), not their run time.

Top 10 contradictions (one line each):
1. Primary lever kinds: LEVER_RULES_v3.md:91 and 20261101_route1_notes.md:5 allow only kinds (a), (b), (c); RIF:10 takes the primary lever from any PATTERNS.md DESIGN family (F18, F104, also README.md:10 F369).
2. Misread rule levers: LEVER_RULES_v3.md:91 and 20261101_route1_notes.md:9 make them extras never counted; RIF:10 (CR7) allows one as primary with a clear deciding sentence (F20, F107).
3. Stated rule levers paused: LEVER_RULES_v3.md:86 pauses L1 to L11, S1, S3, S5, S6, H1 to H9; RIF:10 and PATTERNS D3 use a misread rule family (F12).
4. Timeout lever: LEVER_RULES_v3.md:91 and 20261101_route1_notes.md:8 let measured scale be primary with no cap; RIF:10 says timeout only as an extra unless Ayush says so (F21, F105, F292).
5. issue.py round caps: issue.py:16, :17, :19, :21, :217 refuse past 2 fix rounds, 2 QC rounds, 3 harden rounds and 8 sessions; decided: warnings, never refusals (F398 to F404, F409; README.md:19 F372; state.json:86, :90, :93).
6. Count caps: LEVER_RULES_v3.md:176, _COMMON_RULES_v5.md:44 and :63, QC_FIX_PLAYBOOK_v3.md:21, :41, :71, pipeline_v4/PLAN.md:10, KNOWLEDGE.md:39, state.json:29, README.md:31 say no upper cap (warn above 35, or tests at most 35); RIF:8 sets soft 70, hard 100.
7. Old gates still written: README.md:31, KNOWLEDGE.md:46 and :94, state.json:31 and :89 give tests under 100, rubric under 100, overall under 70 (or final under 70 on 2 runs); RIF:9 is 85, 85, 40 on 1 run.
8. QC pass definition: state.json:32 (zero findings incl warns), pipeline_v4/PLAN.md:37 (0 fails once, then freeze), LEVER_RULES_v3.md:241 (fix every minor) differ from RIF:7 (no fail in 2 runs in a row, a non repeating minor accepted) (F303, F262, F92).
9. Probe wording: LEVER_RULES_v3.md:181 says never echo probe wording in instruction.md; RIF:11 (Q106) says every criterion traces to an instruction sentence (F66).
10. Size bound: 20261101_route1_notes.md:20 and :37 forbid any stated size bound; RIF:10 (R30) allows one for a runtime lever (F115, F123).

Other contradictions worth Ayush's eye: README.md:3 "advisor" against RIF:2 brain (F364); README.md:5 seven step read order against RIF:3 state card (F366); repos list without master-task-chat in _COMMON_RULES_v5.md:21, state.json:52, README.md:70 (F186, F306, F392); fixed Docker and session numbers in state.json:79, :82, :83, :111, pipeline_v4/PLAN.md:65, :76, README.md:31 against RIF:12 settings; LEVER_RULES_v3.md:93 rejects odd carriers while PATTERNS D2 is a carrier family (F25).
Conflicts inside the active files with no RIF line (all ASK AYUSH): code quality criterion wording LEVER_RULES_v3.md:204 against QC_FIX_PLAYBOOK_v3.md:50 (F71, F158); what-if figure criterion QC_FIX_PLAYBOOK_v3.md:34 against LEVER_RULES_v3.md:180 J1 (F142); limit at least 3x oracle time _COMMON_RULES_v5.md:58 against reference at most 1/4 of the limit 20261101_route1_notes.md:8 (F221); "park" in LEVER_RULES_v3.md:91 against "nothing parked except on Ayush's word" 20261101_route1_notes.md:17 (F22, F110); blinds before QC in LEVER_RULES_v3.md:230 against none on route 1 at 20261101_route1_notes.md:47 (F80, F130); oracle 3 runs state.json:30 against 2 oracle in auto pipeline_v4/PLAN.md:16 (F246, F301); RIF:10 restores the timeout permission text that 20261101_route1_notes.md:35 marks superseded (F121).
