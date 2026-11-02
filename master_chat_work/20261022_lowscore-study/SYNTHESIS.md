# Low-score study: SYNTHESIS (Phase A static study + Phase B Docker replay of 07, 08, 09)

Built from `tasks/01..10_*.md` (each verified by the master against its `verifier/ctrf.json`), `notes/ours.md` and `levers_found.json` (70 levers). "pp" means points of the overall score (0.5 x tests % + 0.5 x rubric %). The loss partition in sections 3-4 does not overlap and adds up exactly to each task's recorded score (821.8 pp lost across 10 tasks; inputs and arithmetic in `notes/loss_partition.py`). There was one run per task, so every conclusion rests on n=1 per task. Phase B (section 8) confirmed the three runtime SUSPECTs as broken grades; the rows below keep the recorded scores and add the corrected ones.

## 1. Summary table

| task | overall | tests | rubric | genuine? (step 2) | main failure causes | lever families |
|---|---|---|---|---|---|---|
| 01 assay-plate-triage | 5.51 | 3.33 | 7.69 | GENUINE (+ design cap: 42/90 test weight sits on bit positions no shipped file identifies) | 12 undocumented mode bits never recovered; digest oracle only at all-bits-set | NEW (hash oracle), E, B, D |
| 02 modulus-sieve-replay | 5.90 | 6.25 | 5.56 | GENUINE | ~52 constants fitted to 7 rows + 1 object; additive model vs multiplicative truth; one wrong core constant fails every probe | NEW (aggregate-only evidence), B, E |
| 03 inference-gate-replay | 6.54 | 10.75 | 2.33 | GENUINE | example exercises one mode only, so carry/tolerance/budget constants are unobservable; 4-hash oracle with no partial signal | NEW, B, E |
| 04 speculative-decode-arbiter | 11.83 | 15.96 | 7.69 | GENUINE | void/reclaimed window ratio is defined only by omission and feeds the K fixed point, then every downstream file; closing summary refused | A + B, NEW (format, refusal) |
| 05 quillfen-sla-settlement-repair | 13.03 | 15.91 | 10.14 | GENUINE | 19 of 20 defects repaired; the missed one (6.3) sits behind a decoy runbook, no defect count is given, and it feeds every graded output | C + B, NEW (bundled-figure judge) |
| 06 grain-intake-settlement | 23.97 | 6.38 | 41.56 | SUSPECT-design (no runtime breaker; 78/94 test weight grades bit positions no shipped file identifies) | positions unidentifiable; 13 undocumented bits, 16/49 bin digests | NEW (design), NEW (oracle), B |
| 07 fdc5a20d (logistic batch report) | 25.49 (corrected 67.65) | 15.69 (corrected 100) | 35.29 | BROKEN GRADE (confirmed by Phase B) | script is 0600 (traj step 13) and run as uid 65532 with no chmod: 27/27 EXEC fail, 4/4 READ pass; judge probes the instruction never asks for; honesty -5 | NEW (harness), C, NEW (honesty) |
| 08 registry-lock-footprint-resolution | 27.40 (corrected 47.18) | 2.16 (corrected 41.73) | 52.63 | PARTLY BROKEN GRADE (trap tier confirmed by Phase B; held-out loss genuine) | program is 0600 (traj 35/36/41) and run as `setpriv nobody`: 0/27 EXEC; also a real inverted cross-file field (`quarantined_records`) that voids every held-out doc; stated ordering conduct rules missed | NEW (harness), A + cascade, NEW (ordering) |
| 09 ninefold-crown-settlement-recompute | 29.18 (corrected 71.53) | 15.29 (corrected 100) | 43.06 | BROKEN GRADE (confirmed by Phase B, incl. the false -5 brand) | 0/19 EXEC incl. clean-exit manifest checks, 8/8 READ byte-exact; false -5 replayer brand; 13 "name one example" judge criteria | NEW (harness), NEW (narration) |
| 10 reefer-power-dispatch-recompute | 29.35 | 8.06 | 50.63 | GENUINE (runtime hazard present but irrelevant: 4/5 READ shipped blocks already wrong) | a staged-allocation defect cascades through every stage block; "name one example" judge criteria | B + A, D, NEW (narration) |

Template families: 01, 02, 03 and 06 share one template ("the engine was lost; its constants or bit meanings are withheld; digests are the oracle"). 09 and 10 share another (14 stage specs, office papers, 31 byte-exact documents). The 10 tasks are therefore about 6 independent designs.

## 2. Instruction-writing patterns vs low scores; ours side by side

Finding: the operator's hypothesis is half right. Our instructions do not over-specify the procedure; several low scorers are more procedural than any of ours. They do over-specify the trap map: how many hidden rules there are, which files hold them, and which topics matter (through the final-reply asks). Two non-wording differences, the shipped oracle and the grading granularity, explain as much as the wording does.

Against "a precise procedure causes high scores":
- Six low scorers state a method or procedure:
  - 02: `instruction.md:17` (held-back block, rival input, second calculation) and `:49` ("Give the hard part at most half your working time").
  - 03: `:17` and `:34-36`.
  - 06: `:7` ("the search is decidable one bin at a time").
  - 09: `:7` (full stage order).
  - 10: `:7` ("Allocate against the nominal capacity, then withhold the standing reserve ...").
  - 07: `:18-57`, close to pseudo-code.
- None of ours gives a procedure (`notes/ours.md`).
- Length does not separate them either: the low scorers run 552-2406 words, ours 350-571.

For "ours signpost the traps". The evidence comes from the cleanest fair-and-genuine low scorer (05) and from 04 and 08:

| pattern | low scorer (quoted) | ours (quoted) |
|---|---|---|
| Count of hidden rules or defects | 05 gives none, only the precedence rule: "Where a clause binds the engine to a practice instead, the practice is the one the shipped records establish" (`05 instruction.md:3`). The count, 20, exists only in the tests (`test_output.py:4259-4280`). | "fifteen rules you must work out" (vendor `:3`); "54 numbered rules (K, M, N, C, P and T)" (schema `:3`); "Four conventions" (emberforge `:5`) |
| Evidence files named | 05 never names `sensor_waits.xml`, `scheduler_ticks.tsv` or `review_rulings.ods`; only the contract does (`settlement-contract.md:76-78`) | vendor `:3` names all 9 rule files and the reading order; schema `:3` names every file down to the comment headers |
| Trap topics in the final-reply asks | 05 asks for figure families F1-F13, not rule topics (`:9-29`) | vendor `:13`: checksum coverage, frame start, unknown extension, non-shortest integer, reject order. district `:19-24`: pool cents, rounding inside the search, waiver weights, duplicate rows. district `:15`: "Empty groups, missing optional fields, rejected rows, exact boundaries, ties and zero denominators" |
| Rule defined by omission | 04: the agreed prefix is defined only "for every other window" (`SPEC-SDA.md:198`), so a void window's ratio is never stated; about 67 pp lost | none found in ours (numbered rules, e.g. emberforge `rulebook_scarcity.md` V1-V9) |
| Field named in one file, defined in another | 08: `quarantined_records` is named in `report-schema.md:17` and defined in `resolution-policy.md:17-19` as the opposite subset to the eligibility rule; the agent inverted it (29 pp) | ours point at one authority: "Treat schema.md as the authority" (district `:1`) |
| Decoy default | 05: the shipped body equals the legacy runbook sentence (`operations-runbook.md:35-38` vs `deps.py:36`); the two readings differ only on a rare equal-nominal boundary (`sensor_waits.xml:12` vs `:20`) | none of ours ships a plausible-but-wrong authority |

Two non-wording differences matter as much:
- **Shipped self-check oracle.** Ours ship a full-answer check: emberforge's calibration slice ("Exactly one draw from that register reproduces what the council published", `:5`), vendor's two example segments, and schema's visible tests. 04 ships no example of any deliverable, and its internal identities (conservation residual 0) hold for any K, so the agent validated a wrong schedule (04 report step 8). In 05 the oracle is the raw records, which only answer once joined with the engine's own interval set.
- **Grading granularity.** Ours have 43-58 positive checks, and their corpora each isolate one rule: emberforge `cap_and_floor_*`, `retired_reagent_*`, `consumed_reference_*` (`test_output.py:3144-3173`); district `waiver_precedence_case`, `tie_break_greatest_tuple_case` and so on (`test_output.py:1535-1565`). One misread rule therefore costs one corpus. The low scorers have 16-32 positive checks and put the weight on whole documents downstream of a chain, so one rule cost 86 pp in 05, about 67 pp in 04, 46 pp in 10 (one stage) and 29 pp in 08 (one field).

Caveat: 3 of the 10 low scores (07, 08, 09) were depressed by a broken grade, now confirmed (section 8). With correct grading 07 scores 67.65 % and 09 scores 71.53 %; the most recipe-like instruction in the set (07, `instruction.md:18-57`) earns 100 % on tests, which supports the operator's view that a precise instruction makes the content easy, and 4 come from one rule-withholding template at the edge of QC solvability (01, 02, 03, 06). The clean evidence for wording levers is 04, 05, 08 (the cross-file field) and 10.

## 3. Lever families ranked by points lost (non-overlapping, 821.8 pp total)

| rank | family | pp lost | tasks | strongest single example |
|---|---|---|---|---|
| 1 | NEW: withheld rules/constants with a weak oracle (hash or aggregate only) | 300.4 | 01, 02, 03, 06 | 02: ~52 constants against 7 form rows + 1 object; the agent's additive model can never fit the multiplicative truth (91 pp) |
| 2 | A + B: documented rules composed wrongly, then a dependent chain | 117.3 (+29.1 for 08's cross-file field) | 04, 10, 08 | 04: the void-window ratio, silent by omission, feeds K -> classes -> costs (~67 pp) |
| 3 | NEW: grader runtime breaker (program unreadable to the dropped uid) | 104.3 (observed in Phase B: 42.2 + 19.8 + 42.4) | 07, 08, 09 | 07: a correct script failed 27/27 EXEC checks; readable, it passes 51/51 (42.2 pp) |
| 4 | C + B: audit/repair with one hidden defect, then a cascade | 86.2 | 05 | 05: 1 missed defect of 20 (86 pp) |
| 5 | NEW: judge requires narration/probes the instruction never asks for | 67.5 | 07, 09, 10 | 09: 13 x w3 "name one concrete example" criteria (26 pp) |
| 6 | NEW: grader design, graded unit unidentifiable | 41.5 | 06 (latent in 01) | 06: all 13! bit permutations give identical output at both shipped mode words |
| 7 | Judge conduct rules stated in the instruction but not followed | 31.3 | 08, 02, 03, 06, 10 | 08: "Write out the comparison ... before you read any field shard" (`instruction.md:9`); 3 of 5 lost (24 pp) |
| 8 | Honesty negative | 14.7 | 07 | 07 R10 -5 for "input file checksums are unchanged" with no baseline |
| 9 | Code-quality criteria | 14.6 | 7 tasks | 01 R15 punished the dead no-op code of the same failure |
| 10 | Other (model refusal) | 12.8 | 04 | 04: closing summary refused; 19 judge points computed correctly but never stated |
| 11 | NEW: output format (unstated serialization) | 2.1 direct (~20 overlapping) | 04 | compact JSON byte-compared, never documented |
| - | D size ladder, E stacked constraints, F rejection paths | ~0 as primary causes | - | the agent beat every F path it met (05 reject codes, 06 screening, 09/10 decoy papers) and every E constraint set (05's nine engagement rules) |

## 4. Failure causes ranked by points lost

| cause | pp | tasks |
|---|---|---|
| Hidden-input generalisation failed (withheld rules not recovered) | 300.4 | 01, 02, 03, 06 |
| Read the doc but misapplied (one hidden defect missed; one cross-file field inverted) | 115.3 | 05 (86.2), 08 (29.1) |
| Two documented rules combined wrongly (cascade) | 117.3 | 04, 10 |
| Other: verifier could not run the program (confirmed by Phase B) | 104.3 | 07, 08, 09 |
| Output: judge narration or probes not produced | 67.5 | 07, 09, 10 |
| Other: graded unit unidentifiable (design) | 41.5 | 06 |
| Stated conduct rules not followed (order of work, held-back block, rival input) | 30.5 | 08, 02, 03, 06, 10 |
| Unsupported claim in the final message | 14.7 | 07 |
| Code quality | 14.6 | 7 tasks |
| Model refusal | 12.8 | 04 |
| Output format | 2.1 | 04 |
| Ran out of time or steps | 0 | none: every agent stopped early by choice (05 at 42/240 min, 04 at 19/120, 07 at 3/120, 01 at 49/90) |

Agent behaviour that recurs across tasks:
- It validates with internal consistency only (04: residual 0; 05: its own mutation harness over its own 19 fixes; 10: "120 violations arise structurally").
- It rationalises anomalies instead of debugging them (10: 101 of 101 removals unspilled; 05: "boundary unexercised").
- It stops with most of its budget unused.

## 5. Judge patterns

Held up (the agent failed them):
- **Exact figures in no file that need the whole chain:** 01 (R2-R11, 32/39), 02 (#7-#26, 64/72), 03 (#6-#15, 36/43). Copying the docs earns nothing.
- **Bundled figure criteria** (3-5 integers per criterion, chosen so every misreading moves one of them): 05 R8-R19, 12 x w5, all failed. They also double-punish what the tests already grade (05 report step 6).
- **"Name one concrete case from your session"** (09 R11-R30, 10 R14-R30): 38/72 and 37/79 lost. These pay for narration the instruction never asks for, which is a QC alignment risk (AL-1).
- **Ordering conduct stated in the instruction** (08 R1-R3: "at the moment you set that rival aside", "before you read any field shard"): lost by an agent that builds first and demonstrates later.
- **Unasked verification probes** (07 R5, R6) and **the honesty negative** (07 R10, -5).

Met by the agent (cheap points):
- Echo criteria that repeat dictated sentences (07 R1-R4, 4/17).
- Honest tallies (06 R19/R20, "0 of 13 bits settled").
- Delivering early (06 R22) and recomputing published digests (01 R12, 03 #4, 06 R25).
- Process steps the agent does anyway: clean regenerate and renamed-copy compare (08 R4/R5), stdlib only (10 R3), starting the service (04 #1).
- Figures insensitive to the hard part (06 R8, R9, R11, R14).

## 6. Rules for our builder prompts

1. Never state the number of hidden rules, defects or conventions, in the instruction or the docs; let completeness be unknowable. (05 vs ours: vendor `:3`, schema `:3`, emberforge `:5`.)
2. Never list trap topics in the final-reply requirement. Ask for figures or outcomes ("state total X, count Y"), never "say how X is rounded". (05 `:9-29` vs vendor `:13`, district `:15`, `:19-24`.)
3. Do not name the evidence files that decide a rule. Name only the authority doc, and let that doc point at "the records of practice". (05 `instruction.md:3`, `settlement-contract.md:76-78`.)
4. Put at least one load-bearing rule either in a scope-by-omission sentence ("for every other X") or split across two files (field named in the schema, defined in a policy). Make sure no other reading is stated, so the rule stays documented and QC-safe. (04 `SPEC-SDA.md:198`; 08 `report-schema.md:17` + `resolution-policy.md:17-19`.)
5. Give one hidden rule a decoy default: the shipped code or legacy doc states the plausible reading, and the authoritative record contradicts it on a rare boundary that the shipped data does show. (05 `operations-runbook.md:35-38`; `sensor_waits.xml:12` vs `:20`.)
6. Route the hidden rule through a dependent chain and grade whole documents downstream of it on regenerated hidden inputs, so one miss costs 30-60 % of the test weight. Keep rule-isolating corpora to at most ~30 % of the weight. (05, 04, 10, 08; contrast ours at `emberforge test_output.py:3144-3173`.)
7. Do not ship an oracle that confirms the full answer. Ship evidence that decides each rule, and make sure the identities an agent can check (conservation, residual 0, row counts) still hold under the wrong reading. (04: residual 0 for any K; contrast emberforge's calibration slice, `:5`.)
8. Every graded unit must be identifiable from shipped files. Never grade bit positions when only composite evidence ships, and never ship an example that exercises one mode while grading the others. (06: 78/94; 01: 42/90; 03: drain-only example.)
9. Make the grader runnable on an editor-written 0600 file: before dropping the uid, `chmod a+r` the program and `a+rx` its parents, or stage a world-readable copy. Run QC Step 10 once with the delivered program at mode 0600. (07, 08, 09 broken; 04 stages a copy, `test_output.py:1841-1853`; 06 grants read, `:1204-1209`.)
10. Cheat detectors must stand down when the program did not run cleanly. (09's `_is_replayer` fired -5 on an unrun program, `test_output.py:6383-6393`; 10 gets it right, `:6451-6471`.)
11. Keep shipped-data READ checks to 5 % of the test weight or less, so replaying the visible data earns little. (09: 18/85 = 21 % for a replay-level result; 08: 3/139.)
12. Judge: one figure per criterion, every figure needing the full chain and absent from all files. Add one honesty negative for a claimed validation the trajectory does not show. Never use bundled multi-figure criteria or echo criteria. Use "name one example" or ordering conduct only when the instruction states that exact ask. (01-03 held; 05 bundles double-punish; 07 R1-R4 echo, R10 honesty; 08 stated ordering held; 09, 10 unstated narration.)
13. Never byte-compare a serialization the docs do not state (JSON whitespace, separators). (04, ~20/94 overlapping.)

## 7. Open questions and RUN REQUESTs

All three RUN REQUESTs (07, 08, 09) were approved ("approved: 07, 08, 09", 22 Oct 09:18 IST) and run; results are in section 8. The pre-run reasoning is kept below for the record.

RUN REQUESTs (Phase B: replay the saved artifacts at V600 and at V644, tests only):

**RUN REQUEST 07**
- Evidence:
  - traj step 13 shows `-rw-------. 1 agent agent 6896 ... derive_report.py`.
  - `test_output.py:296-299, :446-489` runs it as uid 65532 with umask 077 and no chmod.
  - 27/27 EXEC checks failed, including trivial ones; 4/4 READ checks passed, including the independent derivation (w5).
  - `result.json` shows `RewardFileNotFoundError`, so the stored score came from a later grading.
- Expected under V644 (UNVERIFIED): tests ~100 %, overall ~67.6 %.
- Depends on it: whether 07 is a low scorer at all, and whether the most recipe-like instruction in the set actually scores high, which would be direct evidence for the operator's hypothesis.

**RUN REQUEST 08**
- Evidence:
  - traj steps 35/36/41 show `-rw------- optimize.py`.
  - The tests run it under `setpriv nobody` with no chmod (`test_output.py:1878-1889, 1938-1939`).
  - 0/27 EXEC checks passed, while the same decoder passed the READ decode checks.
- Expected under V644 (UNVERIFIED): trap tier ~+55/139, overall ~47 %; the held-out checks still fail on the inverted field.
- Depends on it: how much loss goes to the harness lever versus the cross-file-field lever (sections 3-4).

**RUN REQUEST 09**
- Evidence:
  - 0/19 EXEC checks passed, including 3 manifest checks that need only a clean exit.
  - 8/8 READ checks are byte-exact.
  - The replayer negative (-5) fired falsely (`test_output.py:6383-6393`), although the program holds no event literal.
- Expected under V644 (UNVERIFIED): up to ~+72/85 tests, overall up to ~70 %.
- Depends on it: whether the 09/10 template is hard through its tests or only through its judge.

Not requested:
- 10: the hazard is present, but its shipped READ blocks already fail.
- 01 and 06: the design cap is a property of the shipped data, so a replay cannot test it.

Open questions:
- RESOLVED by Phase B: Harbor 0.24.0's artifact transfer keeps the 0600 mode. V600 reproduced the recorded per-check results exactly for all three tasks; V644 did not.
- 04's refusal ("I'm Kiro", traj step 22) and the "fabricated tool output" retractions in 03 and 06 point to a harness or identity-prompt effect on the model, outside task design. It cost 12.8 pp in 04.
- 03's instruction says 2700 s (`instruction.md:38`), but `task.toml` allows 7200 s (a QC IN-1 mismatch).
- How much of our 84-94 % comes from the oracle plus isolated-corpora structure rather than the wording? A controlled test would be one of our bundles rebuilt with rules 1-3 applied and the grading unchanged. This is an idea, not part of this study.

## 8. Phase B: Docker replay of 07, 08, 09 (tests only)

Method: Harbor 0.24.0 on Docker, using QC Step 10 copies built by `exe_copy.py`. `solve.sh` (oracle agent, uid 1000) copies the saved `artifacts/app/` files into `/app` and sets modes: V600 has every `.py` at 0600; V644 has all files at 0644. One run per variant, 22 Oct 09:19-09:24 IST. The oracle logs show the modes. No trial raised an exception. The judge was not run, so the rubric halves below are the recorded values.

| task | recorded tests | V600 tests (checks differing from record) | V644 tests (checks differing) | corrected overall |
|---|---|---|---|---|
| 07 | 15.69 % | 15.69 % (0) | 100 % (27: every `fresh_*`/hidden check fail -> pass) | 67.65 % |
| 08 | 2.16 % | 2.16 % (0) | 41.73 % (11: all `trap_*` fail -> pass; 16 `held_out_*` still fail) | 47.18 % |
| 09 | 15.29 % | 15.29 % (0) | 100 % (20: 18 hidden-event checks + missing-paper refusal pass, -5 replayer brand gone) | 71.53 % |

What this changes:
- **The replay is faithful.** V600 matches the record check for check in all three, so the editor-written 0600 files are what the verifiers saw, and the grade was broken. The study's static step-2 screen predicted every outcome correctly, including the size of each gain.
- **The genuinely low set is 7 tasks, not 10.** 01-06 and 10 stay below 30 %. 07 and 09 are mid-to-high scorers whose only real losses are judge criteria. 08 is genuinely weak on held-out populations (the inverted cross-file field) but not at 27 %.
- **Instruction precision:** the most procedural instruction (07) gets 100 % on tests; the 806-word stage-by-stage 09 also gets 100 % on hidden events. Both support "precise instructions make the content easy". Neither contradicts section 2's finding that the low scorers hide the trap map, the evidence and the defect count; the remaining genuine low scorers are those that do.
- **Rule 9 (grader must survive 0600) is the highest-yield single fix in the set:** 104.3 pp across 3 tasks. Rule 10 is confirmed too: 09's -5 came only from the non-run.
- **For our bundles:** the same hazard was already hit in emberforge and vendor-archive and is latent in district-heat (`master_chat_work/20261021_v0-rescore/RESCORE_REPORT.md:37-43`). Those bundles still need the fix.

