# S2 lowscore-study (SYNTHESIS.md 182 lines, levers_found.json 70 levers)
Path base: master_chat_work/20261022_lowscore-study/

## Scope / caveats
- 10 peer tasks, n=1 run each (SYNTHESIS:3). ~6 independent designs (01/02/03/06 one template; 09/10 another) (:20).
- Phase B: 07, 08, 09 were broken grades (0600 + dropped uid); corrected overall 67.65 / 47.18 / 71.53 (:170-174). Genuinely low set = 7 (01-06, 10).
- 4 of 7 genuine low scorers (01,02,03,06) are "withheld constants + digest oracle" template at the edge of QC solvability (:52) — family rank 1, 300.4 pp (:58). NOT usable under our QC (hidden rules / IN-2/DS-27). So clean wording evidence = 04, 05, 08 (cross-file field), 10 (:52).

## Key quotes
- :24 "Our instructions do not over-specify the procedure... They do over-specify the trap map: how many hidden rules there are, which files hold them, and which topics matter".
- :41 ours: "fifteen rules you must work out" (vendor :3); "54 numbered rules" (schema :3); "Four conventions" (emberforge :5).
- :49 shipped self-check oracle: emberforge calibration slice, vendor two example segments, schema visible tests; 04 ships none + residual 0 for any K -> agent validated wrong schedule.
- :50 granularity: ours 43-58 positive checks each isolating one rule; low scorers 16-32 checks with weight on whole documents downstream of chain: one rule cost 86 pp (05), ~67 (04), 46 (10), 29 (08).
- :69 "D size ladder, E stacked constraints, F rejection paths ~0 as primary causes ... the agent beat every F path it met ... and every E constraint set".
- :86 time: 0 pp; "every agent stopped early by choice (05 at 42/240 min, 04 at 19/120, 07 at 3/120, 01 at 49/90)".
- :89-91 agent behaviour: validates with internal consistency only; rationalises anomalies ("boundary unexercised", "120 violations arise structurally"); stops with budget unused.
- :96-107 judge: held = exact figures in no file needing whole chain; bundled multi-figure; "name one concrete case" (QC AL-1 risk); stated ordering conduct (08); honesty negative. Met = echo criteria, honest tallies, delivering early, recomputing published digests, process steps agent does anyway, figures insensitive to the hard part.
- :162 04 refusal "I'm Kiro" traj step 22; "fabricated tool output" retractions in 03, 06 — harness/identity effect, 12.8 pp.
- :163 03 instruction 2700 s vs task.toml 7200 s (IN-1 mismatch) in a peer task.
- :164 open: "How much of our 84-94 % comes from the oracle plus isolated-corpora structure rather than the wording?" never controlled-tested.
- :178-179 "the most procedural instruction (07) gets 100 % on tests; the 806-word stage-by-stage 09 also gets 100 % on hidden events".
- :180 rule 9 highest-yield 104.3 pp; rule 10 confirmed (09 -5 from non-run).

## levers_found.json stats
- families: NEW 31, B 12, A 11, E 6, C 5, F 3, D 2. triggered True 62, False 8.
- Held-and-costly (weight_share, cause):
  - #20 04 A void_and_reclaimed_window_ratio_feeds_k_fixed_point 0.766 "two rules combined wrongly (attribution UNVERIFIED, from code reading)"
  - #21 04 B k_to_classes_to_cost_dependent_chain 0.766
  - #24 04 NEW no_reference_output_shipped 0.766 "agent validated only residual zero"
  - #27 05 C hidden practice clause behind decoy runbook 0.8625 "zero rows with waited_on == downstream_nominal read as 'boundary u[nexercised]'"
  - #28 05 B dependent chain 0.73
  - #53 08 NEW whole_document_equality_field_cascade 0.576 "read but misapplied (inverted condition)"
  - #54 08 NEW ordered_write_ups_before_actions 0.474 "built first, demonstrated after"
  - #64 10 B staged_allocation_cascade 0.919; #65 10 D hidden_day_blocks_by_stage 0.726
- Beaten (0.0 loss): #33 05 A practice clauses composed from records (agent fitted 5.3 64/64, 5.7 60/60); #35 E stacked constraints; #36 F reject codes; #42 06 F screening; #55-57 08 B 11-transform decoder stack, A earliest-name licence, A candidate elimination (triggered False); #61-63 09 B 14-stage chain, A live sheet by key cell, F sentinel.
- Leaked by harness not skill: #45, #52, #58, #59 (0600 uid).

## Implications for 13 study rules (preliminary; test later vs our real trajectories)
- R1-R3 (counts, topics, file names) derived from 05 only (one task, n=1) -> evidence medium.
- R4 scope-by-omission/split-file: 04 (attribution UNVERIFIED from code reading) + 08 (29 pp) -> medium.
- R5 decoy default: 05 only -> medium/low; QC risk DS/IN contradiction.
- R6 chain + whole-doc grading: 04,05,08,10 -> strongest wording-independent lever. But QC TS-26 (cascade) / AL-28 (stacking) friction (decisions d74).
- R7 no full-answer oracle: 04 (+ ours all ship oracle) -> medium-high.
- R8 identifiable units: design hygiene (06, 01) -> high.
- R9 0600: Phase B confirmed + our own L34 -> high.
- R10 cheat detectors stand down: 09 confirmed -> high.
- R11 READ <=5%: 09 -> medium.
- R12 judge one figure: 01-03 held; but 01-03 template is withheld-constant -> medium.
- R13 byte-compare: 04 ~2.1 pp direct -> low impact.
