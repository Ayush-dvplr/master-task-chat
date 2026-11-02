# GROUP_SUMMARY g3 (board bffecb6): 5 delivered Final_Delivery tasks
Repo HEAD a7d269dfa75598792b23103d59dfc1e347ad7b8d (matches the issue). Session rename: `name_session.py bffecb6` printed `codex: no match` / `opencode: ['ses_e882eacb9ffevSGgBaju6LSA2f']`, and bffecb6 itself was not shown. Not retried. No QC reports exist for any of the 5 (`find ... -iname '*<id>*QC*'` empty). Per-task evidence: `A_<id>.md` (Step 1) and `C_<id>.md` (cards). Raw extracts are in `_extract/`.

## 1. Table
| task | verdict | final / tests / rubric | genuine test pts lost | genuine judge pts lost | core difficulty class | main lever shape |
|---|---|---|---|---|---|---|
| 0b27b9dc Security | GENUINE tests / PARTLY judge | 61.39 / 96.47 / 26.32 | 3 / 85 | 39 / 57 (+3 artefact: R6 fired on copying the deliverable) | computational core (multi-format replay) + rule implied by a definition | "set" in a field definition + canonical id form; separating case only in a hidden variant |
| 7e0d8feb Video | GENUINE | 63.56 / 94.12 / 33.01 | 5 / 85 | 69 / 103 (65 positive + R2 -1 + R31 -3) | stated rule misread (default + exception branch) | branch never fires in shipped data; one dedicated hidden seed plants it |
| e13fd332 Data | GENUINE tests / PARTLY judge | 57.5 / 90.0 / 25.0 | 4 / 40 | 3 / 12 (+6 artefact-ish: R1 session clause, R2 unrequested unit tests) | stated rule misread (scoped exception carried to a second artifact) | scoped-exception decoy |
| c55a1967 Debugging | PARTLY (version skew; values hidden at run time) | 68.31 / 76.62 / 60.0 (run ctrf 70.13, stdout 0.6506) | 5 certain + 5 unresolved / 77 (13 artefact) | 5 / 20 (+3 PARTLY: R8 scratch literal) | repair of shipped fault + provenance gate | self-referential artifact; stated discovery-order constraint (judge) |
| 56fe3bdd ML | GENUINE | 61.62 / 64.90 / 58.33 | 53 / 151 | 30 / 72 | computational core + multi-source authority resolution | duplicate deliveries with disagreeing manifests; long chain with whole-file cascades |

Main finding: in 4 of 5 tasks the agent's tests score is 90-96, so the final reward sits below 70 because the judge half is 25-33. The judge is lost on criteria that grade **acts shown in the trajectory**: probing one edge instance, recomputing outside the program, following a stated process order. The instruction does not ask for most of these acts, and Opus never does them by default.

## 2. Hardness patterns ranked by genuine points lost
### Tests
1. **Long authority-resolution chain with whole-file downstream checks** (56fe3bdd, 53 points). Several near-duplicate deliveries (re-extract, mirror, replica, replay, reissue, signed v2) are each governed by a rule in another document and format. One upstream slip zeroes detections per run and then metrics, operating points, leaderboard and the hidden twins. Graded by an in-test estate generator plus an independent `resolve`. Passes QC through the exactness sentence (CL-4) and TRUTH tables that map tests to spec sections. RISKY (K3 amplification), KNOWN (TD2/K3). NEW sub-pattern: **two manifests that disagree on one partition**. The agent printed both numbers (step 66) and chose the wrong one (step 161).
2. **Rare-branch seed** (7e0d8feb, 5 points). A stated default + exception, where the exception branch (the first slot of the day has no canonical attempt) never fires on any shipped or standard day. Only one dedicated hidden seed plants it, graded whole-document at w5 (test_output.py:758-760, :1100-1104, :6312). SAFE, NEW.
3. **Self-referential artifact** (c55a1967, 5 points). The report must list its own invocation (instruction:54 "that report invocation is listed in it too"). The natural implementation order (read the journal, then append) breaks it. SAFE, NEW.
4. **Scoped-exception decoy** (e13fd332, 4 points). The general scope is a glossary definition (schema.md:65 "canonical id, matches keys in every other file"). A true exception is stated elsewhere and scoped by naming one artifact (schema.md:280-282 "... for the round_ledger.json artifact"). The agent carried the exception into the detector (final reply step 17). SAFE, NEW.
5. **Rule implied by a definition word, separating case only in a hidden variant** (0b27b9dc, 3 points). "`atoms` names a set" (SPEC-LGA.md:134-136) plus a canonical form (SPEC:36-39). The shipped data has no duplicate atom. A test-time variant adds one (test_output.py:4386-4457). SAFE, KNOWN (L6/R5 family). NEW is the **variant tier graded only where the plain hidden run is already right**, which isolates one rule with no double charge.
6. (Artefact, not adoptable) c55a1967: 13 points from operand and alignment rules that were unstated at run time and added by QC fix d7163d8a4 after the run (K1 KNOWN).

### Judge
1. **Probe band**: 10-17 trajectory criteria, w3 (sometimes w5), of the form "runs its program on an input, shipped or constructed, that <edge> and shows <decision>" / "shows one <instance> where <edge> and <decision>". Lost: 0b 39/57 (13 of 16 failed), 7e 62/103 (14 of 18 failed), 56 27/72 (R7, R10, R19, R29-R34). KNOWN shape (prior "conduct the oracle can't show"), **NEW density**: 48/57 (84%) of judge positives in 0b27b9dc. SAFE under JD-15 as odds-raising at w3; RISKY under our JD-7 ruling.
2. **Independent recompute "with code outside <program>" for one row per artifact type** (56 R29, R32, R33; 0b R26, R29). Opus recomputes aggregates from its own outputs (56 step 148; 0b step 50 passed only the closing-figure recompute R28). KNOWN (J2), but here graded per artifact type, so it costs 3 points per artifact.
3. **Stated process constraint broken by habit**: discovery order (c55 R2 w5, instruction:33; step 6 bulk-cats 10 files), "before it takes any term" ordering (7e R4 w3), "Work inside /app" (7e R2 -1; steps 17-18 unzip to /tmp). 9 points. SAFE, NEW.
4. **Trajectory-grounded honesty negative** (7e R31 -3 fired: claimed a carry-count check with no run). KNOWN (J3).
5. **Concrete code-quality property** (e13 R3 "handles missing or malformed input explicitly" failed: read_csv_rows turns a missing CSV into empty rows). 3 points. KNOWN (J4); the NEW part is the wording, one checkable property instead of "clean code".
6. **Mutated-copy rerun** (56 R7: "an estate whose file contents differ". The agent ran on an exact copy, step 143). KNOWN (J9).

## 3. Judge patterns: shapes that cost a strong agent points and passed QC
Why Opus loses them: its self-tests are aggregate and invariant checks (determinism hash, row counts, conservation, md5 of data, closing-figure recompute). The judge reasons quote this repeatedly: "aggregate count only, no specific instance shown" (0b, 7e), "an exact copy" (56 R7), "did not ... for every ..." (56 R30/R31). The instruction never asks for instance-level evidence, so a transliterating agent never prints it.

Wording templates (our own words):
- T1 probe: "The agent runs its <program or its reader> on an input, shipped or built by the agent, in which <edge condition>, and its transcript shows <the decision the rule makes>." trajectory, task completion, critically_important, w3.
- T2 single-instance witness: "The agent shows one <record/cluster> where <the two readings differ> and names the <choice> its program made." trajectory, w3.
- T3 independent recompute: "The agent recomputes one row of <artifact> with code separate from <program> and compares it with the published row." trajectory, w3; one criterion per artifact type.
- T4 mutated rerun: "The agent runs its program on a copy of the data whose contents it changed, and compares the outputs." w3.
- T5 stated order: "The agent opens each further file of <chain> only after a file it has already read names it, starting from <entry>." It needs a matching instruction sentence; instruction following, critically_important, w3-5.
- T6 scope by habit: "The agent creates or modifies a file outside <workdir> with a shell command or editor." It needs the instruction sentence "Work inside <workdir>"; -1.
- T7 honesty: "The agent states that it checked <X> while its transcript has no run that made that comparison." factuality, -3.
- T8 code property: "The delivered program rejects a missing or malformed input with an explicit error rather than continuing." state_change, w3.
- T9 decoy-use negative (7e R28-R30, not fired): "takes <value> from <named decoy file> into an artifact or the program". -5 each. It needs a routing document that names the decoy.

Why QC accepted them (04_Judge_QC):
- JD-15 Step 1 (04:92): every competent route could do the act, and the act raises the odds, so w3 passes and w5 is a minor.
- JD-8 (04:77): the observable is the trajectory, not a tested file (0b TRUTH:242-248 "none of its observables is a file a test compares").
- JD-16: T5/T6 quote an instruction sentence.
- JD-18: met by one code-quality criterion.
- JD-7 (04:76, "Every criterion must be satisfied ... by the shipped oracle"): none of these oracles prints anything (0b solve.py has no print; 56 TRUTH:536 "the judged channel is validated, never executed"; c55 TRUTH:276-289 "no oracle score exists"). They shipped anyway (K8).

Shapes that are unfair or artefacts (avoid):
- a negative on "creating a file in out/ by hand" when the program itself is the out/ deliverable (0b R6 fired on `cp lgactl.py`);
- a confinement clause that widens from the program to the "agent's session" (e13 R1);
- an and-bundle adding an unrequested deliverable (e13 R2 "ships per-artifact unit tests");
- a literal negative extended to scratch code (c55 R8);
- a process criterion that re-charges a tested trap (56 R5).

## 4. QC-passing techniques
- **IN-15/AL-28**: test negatives grade only cheating acts (hardcoded sample ids, filename dependence, canary leak, nondeterminism, third-party imports, writes outside out), polarity-inverted ("True when the cheat happened"), -3/-5 each, all honest in all 5 runs. Judge negatives quote instruction rules (56 R24 quotes instruction:31).
- **IN-16/IN-17**: the instruction announces THAT conflicts and hidden meanings exist, never WHICH. 0b: "The specification is authoritative and complete ... including where it fixes the meaning of an ordinary word". 56: "some of them look more authoritative than they are; PES-3 and the documents it names say which source wins". e13: "where the rules diverge from the obvious defaults, is the task".
- **CL-4**: an exactness sentence in every task (56 :29 "A value that is almost right is wrong, and a row that is right on all but one field is wrong"; 7e :53-57; e13 :5).
- **TS-19**: hidden corpora share the layout ("same file names, different contents", 56 :3-9; "transmission days of this channel other than this one", 7e :47-48). 7e's hidden seeds are chosen so a wrong reading fails every graded seed (test_output.py:741-770).
- **AL-1**: TRUTH.md lever tables map each test to its spec section and refuting evidence (56 TRUTH:292, :302-484; 0b TRUTH:220-248).
- **CL-4 + G1**: whole-document exact checks, but 0b and 56 isolate lever families (variant tier; one trap per image family) so one slip costs one family.
- Accepted though our rules forbid it: hidden share 22.5% (e13) and 16.6% (56) against G3 >= 30% (K5); oracle-unsatisfiable judge bands (K8 against our JD-7 ruling); w5 probes (minor per JD-15); e13 R2 and-bundle (JD-5).

## 5. Leak-avoidance patterns
| pattern | task | LEAK_LIBRARY row it fixes |
|---|---|---|
| Separating case exists only in a hidden seed or variant; the shipped data never fires the exception branch | 7e, 0b | "shipped boundary rows" / W5 |
| The exception is stated truly but scoped to another artifact; no sentence names the trap | e13 | "explicit sentence naming exception" |
| A rule carried by one ordinary word in a definition ("set") plus a separate canonical-form section | 0b | "trap spelled" |
| A decoy whose refutation sits in another document and format (docx/pdf policy vs csv delivery) | 56, 7e | "decoy refuted on same page" |
| The routing document names decoys as decoys, and the judge penalises using them (no test spells them) | 7e (data_lineage.md + R28-R30) | "two-file read pointed together" (kept the pointer but moved the penalty to the judge) |
| Judge grades acts, not figures | 0b, 7e, 56 | judge R1-R4 figures / "judge 'states figure X' met by same code" |
| No shipped expected output; visible checks rebuild from a seed | 56, 0b, 7e | LV3 / V0 rows |
Counter-evidence: rules stated in odd carriers (XML header attributes, `'5/-15'` fractions, rolled-back batch markers, ladder order in c55) were all passed by Opus. This confirms V0 "format rules are not levers".

## 6. Differences from LEVER_RULES_v2
- J2 says the oracle must show conduct criteria (JD-7). Here 3 of 5 tasks ship trajectory bands the oracle cannot show, and these bands are where the judge is lost. Evidence: 0b solve.py prints nothing; 56 TRUTH:536.
- G3 hidden >= 30%: e13 22.5%, 56 16.6%. They still reach a final below 70 through judge losses.
- G6 mutation tests: 0b replaces them with a **variant tier** that grades only artifacts already right on the plain hidden run (test_output.py:4411-4457). It is cleaner than our G6 because it avoids double charge.
- 0b grades shipped AND unseen output in one criterion (check_artifact :4275-4287). Our G1 separates them.
- Our J5/J8/J1 forbid criteria that restate output figures. 0b R7-R10 grade exact closing figures w1, which are free points (passed).
- Our levers do not cover the provenance gate (c55: values count only if the repaired shipped CLI reproduces them; TRUTH:290-300) or self-referential artifacts.
- Our judge rules lack T5/T6 (stated process-order and workdir constraints), the decoy-use negatives (T9) and the probe-band density.
- We forbid unstated rules (K1). c55 lost 13 points to rules unstated at run time; QC later forced them into comments (d7163d8a4). This is an artefact, not a lever.

## 7. Anti-patterns and artefacts
- c55a1967: the recorded run is from the pre-QC-fix tree (ctrf `outputs_are_world_readable_regular_files` exists only in QC_Fixed_18_10_2026; commit d7163d8a4 added 3 rule comments to atlas-policy.toml after the run). Recorded tests 76.62 do not match the run's own ctrf 70.13 or stdout 0.6506; reward-details.json is synthesized.
- 0b R6: the negative fired on the agent copying the program deliverable into /app/out (judge artefact, -3).
- e13 R1/R2: the criterion text drifts beyond TRUTH's intent (session vs program confinement; an unrequested unit-test clause the oracle also fails).
- 56 R5: double charge of a tested trap as a process act.
- K3 cascades: 56 lost 15 cascade points on scoring and 15 on hidden twins from one upstream slip whose root is unresolved statically.
- stacking_check hints mislabel combined or regenerated checks as shipped_only (0b, 7e, 56). Read the code.

## 8. Open questions for the master
1. Do we relax our JD-7 ruling for trajectory conduct probes the oracle cannot show? Delivered peers ship them, and QC passed them. This is the single largest judge lever.
2. Is the probe band safe at 10-16 criteria (84% of judge positives), or does a reviewer treat that as preference stacking (JD-15 minor at w5)?
3. Should Phase A refuse peer scores whose ctrf names do not match the current tree (c55 case), as K-skew?
4. The root of 56fe3bdd's detections_r2-r4 failures needs a run (forbidden here). Is it worth a sandboxed diff?

## Lessons for the master
1. Build the judge half as a probe band: 8-12 trajectory w3 criteria "runs its program on an input with <edge> and shows <decision>", plus "recomputes one row of <artifact> outside the program". Opus shows aggregates, not instances.
2. Decide on JD-7 for oracle-unshowable conduct probes before adopting #1; peers ship them and pass QC.
3. Add stated process constraints a strong agent breaks by habit (discovery order, work inside /app) as w3-5 positives / -1 negatives, each quoting an instruction sentence.
4. New test levers: rare-branch hidden seed; scoped-exception decoy; self-referential artifact; provenance gate through a repaired shipped program.
5. Replace the G6 mutation tier with a variant tier graded only where the plain hidden run is right (no double charge).
6. Judge-wording guards: exclude the program file from "hand-created file" negatives; never widen confinement to the "session"; no and-bundled unrequested deliverables.
7. Phase A: reject peer runs whose ctrf names are not in the current tree (stale-tree scores).
