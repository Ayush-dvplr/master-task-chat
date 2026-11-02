# GROUP_SUMMARY g2 (board aee9e0a)

Repo HEAD `a7d269dfa75598792b23103d59dfc1e347ad7b8d` (matches expected a7d269df). Session rename: `name_session.py aee9e0a` printed `codex: no match` / `opencode: ['ses_e882ed059ffe6dNgLOhxkb4MR7']`; the list did not literally show `aee9e0a` (noted, not retried).
Points below are raw weight units out of the task's positive total (tests: test_output weights; judge: criterion weights). T = tests/test_output.py of that task. Per-task evidence sits in `A_*.md` and `C_*.md`.

## 1. Table

| task | verdict | final/tests/rubric | genuine test pts lost | genuine judge pts lost | core class | main lever shape |
|---|---|---|---|---|---|---|
| b625f36e | PARTLY | 48.38/22.68/74.07 | 0 confirmed out of 72+3 lost (lost to a HIDDEN merge-loop rule plus a cascade; A_b625f36e) | 6/54 (R8, R9 off by one, INFERRED genuine); R2 5 ambiguous wording; R10 3 same hidden rule | unstated or implied rule + amplification | undefined termination branch in a chain walk (generator comment T:300-302 only), cascading over every check that reads the canonical site |
| 3def42a3 | GENUINE | 60.63/37.93/83.33 | 90/145 | 3/18 (R5 never reran on a relocated or altered copy) | other: about 31 stated rules composed at scale + format decoding (19 formats, 100 files) | partial-authority decoys (each decoy wins for one named slice), all-or-nothing per family on visible + hidden |
| daaca581 | GENUINE | 50.23/17.12/83.33 | 121/146 | 3/18 (R5 same) | same as 3def42a3 | same task; adds hidden-only tie-break fixtures. The gap to 3def42a3 is run variance (C_daaca581_DIFF) |
| 37a0c3d6 | PARTLY | 52.66/8.57/96.74 | 64/70 (zeroed by the stated `_full_core` spine T:3812-3817; the core miss is unlocated, INFERRED on a held-out corpus) | 3/92 (R11 wanted an exact intermediate onset value) | computational core + stated rules amplified by a stated cross-corpus spine | branch rules with toy worked examples whose branch fires only on held-out generated corpora + metamorphic reruns |
| 9125255a | GENUINE | 57.48/32.61/82.35 | 124/184 | 3/17 (R3 self-consistency negative fired) | other: about 80 stated per-file conventions composed at scale | L1 green control upstream of the graded filter (per-job controls matched, about 18 extra items still eligible) + per-suite row-set exactness |

Artefact checks (all 5): ctrf names match tests/ with no skew; `exception_info` null; no traceback, Permission denied or timeout. The hidden tier ran in every task, shown by passed hidden checks. 9125255a has a version skew (run 2026-10-24, fix 81f5a4278 on 2026-10-25) with no effect, because all 13 outputs parsed.

## 2. Hardness patterns ranked by genuine points lost

### Tests
| rank | pattern | SAFE/RISKY, KNOWN/NEW | mechanism | how graded | how it passes QC | tasks (genuine pts) |
|---|---|---|---|---|---|---|
| 1 | Rule count × source spread at scale | SAFE NEW (as a deliberate lever) | 30-80 small rules, each plainly stated, spread over 10-50 heterogeneous files. No single rule is hard; the agent cannot apply all of them exactly in one 30-80 min session. Late-band conventions inside one file (9125255a TRUTH drift: "A parser that handles only the first convention it sees fails on later bands") | exact rows per family or suite, visible + hidden | every rule has a sentence (TRUTH traceability tables), so IN-15/IN-16 pass and CL-4 passes on the exactness sentence | 9125255a 124, daaca581 121, 3def42a3 90 |
| 2 | Stated spine gate across hidden variants | RISKY KNOWN (DL R9/K4) | 8 core reports must be exact on the shipped corpus and on 8 held-out or metamorphic corpora at once, or 64/70 is zeroed | `_full_core` T:3812-3817 gates `_leaf` and `_held_out_exact` | instruction.md:3 states it ("a near miss anywhere earns nothing"); the QC report accepts it under CL-4 | 37a0c3d6 64 |
| 3 | Branch fires only on held-out corpora, stated with a toy worked example | SAFE NEW | the handbook gives each branch rule a toy example (skipped clock hour, emesis CYCLE, reversal of a reversal). The shipped corpus never triggers the branch, so a self-test on shipped data cannot see it | held-out generated corpora + metamorphic reruns | rule stated + example given (CL-5/FC:492); TRUTH: "graded on a held-out spring study" | 37a0c3d6 (inside the 64) |
| 4 | Partial-authority decoys | SAFE NEW | each decoy file is demoted by a manual section but stays authoritative for one named slice (late merges, reversal records, CAB-approved errata, lifted quarantines). "Trust it" and "ignore it" both fail | one dc-test per decoy file, exact on the rows it touches | each exception stated in the manual or policy (9125255a certification_policy.md:10 lists all eight partial exports with their valid part) | 3def42a3 dc03/04/05/09/13/14/15 (35), daaca581, 9125255a |
| 5 | Green control upstream of the graded filter | SAFE KNOWN (L1) | the published per-job controls are computed before eligibility. The agent reconciled every non-pref job and stopped, while about 18 items were wrongly eligible | per-suite row-set exactness (`_rows` T:6572-6585) | controls are honest, they just do not cover the filter | 9125255a |
| 6 | Hidden-only tie-break fixtures | SAFE NEW (W5 applied to tie-breaks) | stated tie-breaks (latest test then highest id, higher revision, higher erratum number, largest remainder lower id) planted only in the hidden tier by a separate RNG stream (daaca T `_tiebreak_fixtures`, `_ufe_tie_fixture`) | rows inside existing families | tie-breaks stated in the contract (C:68-69, C:120-123) | daaca581 (effect not separable from variance) |

### Judge
| rank | pattern | class | tasks (pts) |
|---|---|---|---|
| 1 | "reran the program on a relocated or deliberately altered copy and compared" | process step, SAFE NEW | 3def42a3 3, daaca581 3 (every transform run used /app/data, in 2 of 2 runs) |
| 2 | exact counterfactual or corpus figures in the final message (13 figures) | final-answer fact, RISKY KNOWN (SY losers) | b625f36e 6 genuine + 5 ambiguous + 3 hidden-rule |
| 3 | "agent establishes intermediate value V" (exact figure in the trajectory) | process fact, RISKY NEW | 37a0c3d6 3 (lost on the wording: printed the window, never the onset) |
| 4 | self-consistency negative ("keeps an interpretation after its own check shows a mismatch") | honesty/conduct negative, RISKY NEW | 9125255a 3 (fired on an honest disclosure; the retained reading was graded correct) |

## 3. Judge patterns (shapes that cost a strong agent, wording templates in our own words)
- **Relocated-copy rerun (process).** "The agent runs its finished program on a copy of the inputs placed at a different path, or on a deliberately altered copy, and compares the result with its main run." Opus did byte-identical reruns into new output dirs but never moved the input, in both 3def42a3 and daaca581 runs. Fair, because the instruction says the program is rerun elsewhere. Cheap to add.
- **Independent control comparison (process, passed by all).** "The agent compares an intermediate figure with a control held in a different file before trusting it." It costs nothing on its own, but it is the J2 lever: it pairs with an L1 control that is green yet incomplete.
- **Per-item enumeration in the final answer (passed).** "The final message names N defects or set-aside sources." Opus meets these (37a0c3d6 R25-R28, b625f36e 9 of 13 figures).
- **Exact counterfactual figure (risky).** "The final message reports how many X a habitual reading would have changed." This costs points through off-by-one errors in the agent's own counterfactual code, and it is unfair when the counterfactual's scope is worded loosely (b625f36e R2 "held out of scope").
- **Exact intermediate establishment (risky).** "The agent establishes that <entity> has value V." A judge reading it strictly fails the agent if the agent shows an equivalent fact but not V. Name the observable, not the number.
- **Self-consistency negative (avoid as written).** It collides with any instruction that asks the agent to report what it could not reconcile (9125255a item 56 vs R3). If it is used, the trigger must be the agent's mismatch being right AND its graded output following the refuted reading.

## 4. QC-passing techniques
- **IN-15 (rules of engagement):** every task states its run contract (program path, rerun on unseen corpora, exactness, timeouts) in the instruction. 37a0c3d6 instruction.md:3 lists exactly which axes the held-out copies change ("other studies, subjects, runs, memo tables, profile settings, site calendars, workbook date systems...") without saying which rule each axis exercises.
- **IN-16 (no two readings):** TRUTH traceability tables map every graded rule to a doc section (3def42a3 TRUTH.md:423-461; b625f36e TRUTH 401-478; 9125255a generator rule register `fb.R(id,family,sentence,doc)` renders each rule sentence into a doc). The one failure in this group (b625f36e loop rule) was absent from the traceability table, and no QC report caught it.
- **IN-17 (no pre-announcement):** they announce the defect classes, not the instances. Examples: "Some shipped values are wrong, stale or superseded on purpose" (9125255a instruction.md:3); "Working out which rules the published run broke ... is part of the job" (37a0c3d6 instruction.md:1); "Survey the directory rather than reading it as a list handed to you" (b625f36e instruction.md:14-15).
- **CL-4 (all-or-nothing):** an exactness sentence in the instruction, coupled to a reason ("Every settlement figure is coupled to the system-wide unaccounted-for energy reconciliation ... rows and figures only count when they are exact", 3def42a3). QC also accepted a cross-corpus spine as CL-4-compliant because it was stated (37a0c3d6 QC report).
- **TS-19 (bounds):** hidden corpora come from the same embedded generator, with "same file names and documented rules but different identifiers, values and data defects" (3def42a3 instruction). Branch-only-hidden is legal because each branch has a stated rule plus a toy example.
- **AL-1:** both tiers are regenerated from seeds inside the verifier (3def42a3 T:6047-6051 "/app/data never exists in this container"; b625f36e VISIBLE_SEED). The shipped data equals generator(SAMPLE_SEED) byte for byte (9125255a QC DS-3).
- **Accepted although our rules forbid or flag it:**
  - (a) Wrong-reading negatives. 37a0c3d6 has 8 at -3, made defensible by `_matches_flip` T:3842-3847 (fires only when output equals the flip AND the flip differs from truth). b625f36e has 9, and its merge_early probe was confounded and fired falsely. Our N4/G4 forbid these.
  - (b) The grader-read act paid twice (37a0c3d6 test -5 + judge R32 -5 = -10 > AL-28 ≤5). Not flagged.
  - (c) A hidden share under 30% (b625f36e 15.5%, 9125255a 13.6%; G3).
  - (d) 52 checks over the 35 cap (9125255a TS-23 WARN "defensible").
  - (e) A stated spine zeroing 91% of the weight (our R9 RISKY).
  - (f) An unstated 240 s per-run cap (37a0c3d6; harmless at 2.5 s).

## 5. Leak-avoidance patterns (with the LEAK_LIBRARY row each fixes)
- **Rule stated, instance withheld.** The shipped corpus contains no record where the branch fires; a toy example sits beside the rule (37a0c3d6 H:174-176, H:231-234). Fixes LL "shipped boundary rows let agent watch rule fire" / CR rows (W5, W6).
- **Partial-authority decoy.** The demotion and its one exception sit in the governing manual, far from the decoy file, which carries its own banner (3def42a3 TRUTH:180-198). Fixes LL "decoy refuted on same page" (W2, W8).
- **"N figures, none in any file you leave behind"** (b625f36e instruction.md:89-91). The final-message figures cannot be read off the agent's own outputs. Fixes LL judge R1-R4 / J1 (figure criteria met by the same code).
- **No shipped expected output, honest control upstream** (b625f36e TRUTH 633-644: baseline differs on 35/37 cells; 9125255a per-job controls). Fixes LL V0 rows "answer key visible" (W7, W11).
- **Opaque file names + catalog** (37a0c3d6 `ab_0re7.csv` style shards mapped by `ingest_catalog_be.json`; renamed again on held-out runs, T:3699). Fixes LL "two-file read pointed together" (no name pairs two files).
- **Rules buried in large padded docs** (9125255a policy 639 KB, conventions 623 KB; 3def42a3 contract 144 KB with normative prose only in lines 1-160). This raises read cost, not trap secrecy. Neutral (our LV5).

## 6. Differences vs LEVER_RULES_v2 (evidence)
- **They rely on breadth; we rely on a few sharp levers.** 3 of 5 tasks get their genuine loss from 30-80 plainly stated rules plus 6-19 formats, with no single trap (C_3def42a3 §3, C_9125255a §3). LR v2 §0 frames legal difficulty as composition/amplification, but it has no "rule count × source count" lever and no target for it.
- **Partial-authority decoys** (default demotion + one named surviving slice) do not appear in LR. They come closest to W8 plus L6, but the decoy itself is graded on both sides.
- **Branch-only-hidden with a toy worked example.** LR W5 says separating cases are hidden-only, and W6 says no worked example where readings differ. 37a0c3d6 gives a worked example on toy values for every branch and still loses the hidden tier. A toy example that covers the rule does not leak a shipped instance. LR should allow W6-compatible toy examples.
- **Metamorphic reruns** (37a0c3d6 m_corrections T:3615, m_profile T:3668; 3def42a3 r3 relocated with altered mtimes) go beyond our G8 reseed and relocate: they append chains, change case, reorder config and drop scope.
- **Per-row ownership grading** (3def42a3 `_focus`/`_disjoint`/OWNED T:6077-6263: every output byte graded exactly once, the shared UFE columns masked except in t12). This answers our K3 cascade risk better than G2. LR has no such mechanism.
- **Flip-equal negatives** (37a0c3d6 `_matches_flip`) make wrong-reading negatives defensible. LR G4 bans them outright.
- **Hidden-only tie-break fixtures on their own RNG stream** (daaca581) keep the visible tier byte-stable. LR does not mention them.
- **We forbid what they did and lost to:** b625f36e's loop rule is exactly LR "never: silence" (a branch that never fires on shipped data, with no sentence). It produced a false negative firing and a cascade, which confirms our rule.

## 7. Anti-patterns and artefacts
- **b625f36e:** a HIDDEN RULE (merge-loop termination, generator comment T:298-314 only, reference T:1208-1219) caused a cascade over about 15 canonical-site checks. It also falsely fired negative `merge_applied_before_merge_instant` (probe T:3435-3461). The test comment T:3050-3053 claims "a solver that broke exactly one rule loses exactly the weight of that rule", and the cascade makes that false. Judge R2's scope wording is ambiguous (agent 1532 vs reference 1160).
- **9125255a:** judge R3 contradicts instruction item 56. Version skew exists but has no effect.
- **37a0c3d6:** a stated spine with an unlocated miss. The grade gives no diagnostic signal: 6/70 whatever the size of the error.
- **Single-run variance:** the same task on byte-identical data scored 37.93 vs 17.12 on tests (3def42a3 vs daaca581). Visible outputs differ in read_resolution, control_report and summary totals (A_daaca581). One run cannot rank versions.
- **stacking_check.py hints are wrong for seeded-tier designs.** It reported 37a0c3d6 hidden at 8.6% (true 57.1%) and 3def42a3 hidden at 3.4% (true 100% gated). Its TS-26 duplicate flags were false positives in 3def42a3.
- **No QC reports** exist for b625f36e, 3def42a3 or daaca581, so the loop rule never had a reviewer.

## 8. Open questions for the master
1. Should we adopt "rule count × source spread" as a named lever with a target (for example ≥25 stated rules over ≥8 formats)? It costs build effort but is QC-safe.
2. Is a toy worked example per branch, with the branch firing only on hidden corpora, acceptable under our W5/W6 reading? 37a0c3d6 suggests it is both safe and strong.
3. Do we accept flip-equal wrong-reading negatives (fire only when the output equals the named wrong reading and that differs from truth), or keep the G4 ban?
4. Should the judge always include a relocated/altered-copy rerun process criterion (it cost 3 in 2 of 2 runs)?
5. Given about 20-point single-run variance, do we need ≥2 runs before a park/kill decision on tests?
6. Should stacking_check.py learn seeded-tier and `_hard`-gated designs so its hidden-share hints stop misleading?

## Lessons for the master
1. Add a breadth lever: 30+ plainly stated rules over many formats beat Opus in all 3 GENUINE tasks with no hidden rule; budget build effort for it.
2. Allow toy worked examples per branch rule, and plant the branch only in hidden or metamorphic corpora (37a0c3d6: 64/70 lost, QC clean).
3. Adopt per-row ownership grading (each output row graded by exactly one test, shared columns masked) to stop cascades without spines.
4. Add partial-authority decoys (demoted file keeps one stated slice) as a lever; grade both sides.
5. Judge: add a "reran on a relocated or altered copy" process criterion. Drop the "establishes value V" and self-consistency-negative shapes.
6. Keep the ban on unstated branches: b625f36e shows they cascade and fire negatives falsely. Require every generator branch to appear in a rule-trace table.
7. Treat single runs as ±20 points on tests; fix stacking_check hidden-share detection for seeded tiers.
