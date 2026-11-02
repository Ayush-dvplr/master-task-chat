# HARDEN_REPORT slipway-overhaul-replan-repair (harden r2, board bddb388)

Bundle: `master_chat_work/bundles/slipway-overhaul-replan-repair/` (edited in place; tree at start 62dbcde0c809).
Work: `master_chat_work/bundles/_work/slipway-overhaul-replan-repair/` (h2_a3/, maps at top level).
Runs: `_runs/20261101/slipway-overhaul-replan-repair/harden2-114714/` (proto, scans, kill tables, verifier timing),
`_runs/20261101/slipway-overhaul-replan-repair/hardengate-20261101T151450/` (gate lanes).

## Diagnosis (paid attempt 3)

a3 final 77.52 = tests 49/68 (72.06) + judge 78/94 (82.98). Every lost test point came from two
reference disputes, not from a3 mistakes:

- Q1: lodgements naming a JOB-CYCLE job. `spec_stage_p02_precedence_graph.md:3-6, :20-23` says they
  are rejected under EDG-UNKNOWNJOB and listed once; the old reference dropped them silently.
- Q2: top-level `weighted_resource` of 11/18. `spec_stage_p10_objective.md:27-29` (exact rational,
  published to twelve places), `spec_stage_p11_search.md:15`, `rounding_and_arithmetic_policy.yaml`
  and instruction.md "rounding where the stage paper places it and nowhere else" fix exact sum then
  round; the old reference summed the rounded precinct strings.

Both disputes go to a3's reading (docs explicit, no shipped evidence for the other). With the
reference fixed a3 is EXACT on every old round, so all new test lever comes from held-out branches.
Judge: a3 lost only R10 tie witness, R12 drafting adds, R23 inert contrast, R26 counter compare; 47 of
94 positive judge points were repair restatements (JD-8). Full trip in `TRIP.md`.

## Q1-Q8 outcome

| Q | outcome | where |
|---|---|---|
| Q1 | reference rejects cycle lodgements EDG-UNKNOWNJOB (a3 reading) | tests/test_output.py:2890; oracle DFC-16 |
| Q2 | exact sum then twelve places (a3 reading) | tests/test_output.py:3118 `_selection_body`; DFC-25 |
| Q3 | class rate revision reaching no cell classified inert | tests/test_output.py ref_amend; DFC-24 |
| Q4 | ~56% of fresh seeds abort in `_engineer_boundary/_tie`; held rounds picked from buildable seeds; residual | scan300b 133 ok / 167 abort / 0 plant failures |
| Q5 | `known_traps_and_footguns.md` removed (generator, lineage row, env file); each rule has a home (WORK/EVIDENCE_MAP.md Q5 table); one new rule sentence `spec_stage_p10_objective.md:3-4`; `grep -rn known_traps` empty | |
| Q6 | judge rebuilt (below) | tests/judge.toml |
| Q7 | reversal of a lodgement withdraws that edge (exact inverse, undo marker); EDG-SELF tested before EDG-UNKNOWNJOB | tests/test_output.py:2985-3003; DFC-22, DFC-23 |
| Q8 | `aliases_active` = count of active crosswalk rows | tests/test_output.py:3176; DFC-26 |

## Lever and new checks

Lever: every job identifier is read through the crosswalk wherever it stands (rule sentence
`spec_stage_p01_identifier_and_revision.md:19-22`, toy example on a precedence row only
`worked_examples.md:73-81`). Shipped data never carries a legacy identifier outside the crosswalk
(branch count 0); held-out rounds plant active-row legacy identifiers in group memberships, charge
rule subjects and amendment payloads (generator `_legacy` tests/test_output.py:1230, `_lever_amendments`
:1507 adds a reversal of a lodgement, `_assert_legacy` :1521 asserts every planted place; 300-seed scan
0 plant failures). Eleven held rounds at tests/test_output.py:4905-4915; twelve checks at :5288-5371,
registered at :5836-5847, each weight 5 (60 of 110 positive = 54.5% lever share).

Old checks: bodies byte-identical; reference changed only for Q1/Q2/Q8 (and latent Q3/Q7); weight-only
change 5 -> 3 (old positive 68 -> 50); old corpora byte-identical (DS-21). Negatives unchanged (-63).

## Judge changes (tests/judge.toml)

18 criteria, 39 positive. Kept R1 repaired in place (:12), R3 inert amendments in final answer (:38,
old R23), R4 J10 two papers named first (:51); added R2 J4 code quality (:25). Nine probes R5-R13
(:64-168, w3, agent behavior, trajectory; 27/39 = 69%): tie the weights settle, drafting adds beside
19 rejection register (act a3 never did), counters beside withdrawn ledger, altered-copy rerun,
reversal of another kind, missing declared input, count of sets at winning charge, reordered rows,
empty amendment journal. Negatives R14 J3a -3, R15 J3b -5, R16 J3c -3, R17 withdrawn as standing -3,
R18 edited working papers -3. Dropped old R2-R22, R24-R26 (restatements, determinism moved to tests,
figure criteria). Oracle self-check: SELFCHECK block of `solution/solve.sh` prints `check <id> ok` and a
witness for R2, R5-R13 (all ok in Docker, $R/f2_solve.log).

a3 regraded against the final judge: earns R1, R4; R2 uncertain; R3 and all nine probes lost.
low 3/39 = 7.7% (R14 fires on the brute-force claim from steps 78-80), mid 9/39 = 23.1%, high 12/39 = 30.8%.

## Kill table (final tests, 15 rounds, positive 110; $R/score5.log)

| program | tests | lever kept | loss kind |
|---|---|---|---|
| a3_program (paid run) | 50/110 = 45.45% | 0/60 | WRONG on all 11 held rounds |
| oracle_fixed | 110/110 | 60 | none |
| oracle_program (catalogued faults only, first-write) | 35/110 = 31.82% | 0 | WRONG, CRASH on 4 rounds |
| engine_orig (shipped, blind) | 2/110 = 1.82% | 0 | WRONG, CRASH on 4 |
| a3_groups / a3_rules / a3_amendments (all-but-two) | 65/110 = 59.09% each | 15 | WRONG |
| oracle_less_groups / _rules / _amendments (all-but-one) | 80/110 = 72.73% each | 30 | WRONG, some CRASH |
| a3_careful (careful enumerator) | 110/110 | 60 | none (recorded, not blocker) |

## Cost table (WORK/COST_TABLE.md)

Tests-only verifier in Docker: oracle 127 s reward 1.0 of tests channel (110/110); a3 delivered
program 115 s (50/110); limit 5400 s (2.4%). Per round: corpus <=16.6 s, reference <=0.23 s,
program <=1.53 s.

## Predicted score (paid-run program)

final = (tests 45.45 + judge mid 23.08) / 2 = 34.27 (<= 35); judge high gives 38.1 (< 40).

## Gates

- stacking_check: `STACKING_CHECK.md` (TS-26 and AL-28 by hand: distinct, none > 5; G3 69.1% PASS).
- PRECHECK last line: `PRECHECK CLEAN` (warns only X1 binary skipped, A3 47 checks over cap 35).
- QC scripts structure/instruction/tests/judge_qc exit 0; validator build-repair 38 pass, 1 FAIL S1.12
  (pre-existing: custom artifacts match no archetype manifest; not changed).
- xref_check: 9 entries, 0 findings. TRUTH.md shas by script last.
- Lanes: tests-only copies by exe_copy.py under `_runs/20261101/slipway-overhaul-replan-repair/hardengate-20261101T151450/` (dockfree START=yes before each lane): oracle 1.000, 1.000, 1.000; owner (--owner-only) 1.000; nop 0.000; stub 0.000; forgery 0.318 (35/110: shipped 33 + structural 2; every package and crosswalk check 0). No negative fired on the forgery: `test_negative_weight_hardcoded_sample_answers` (tests/test_output.py:5490) fires only when the engine emits nothing on every minted round, and `package_ignores_its_input` (:5510) cedes the emits-the-shipped-round case to it. Old check bodies were kept byte-identical (R5), so this is recorded as a residual gap, not fixed; the forgery is capped at the shipped tier.

## Tasks_INPUT sync

Changed files copied with `cp -p` over `Tasks_INPUT/slipway-overhaul-replan-repair/` (no --delete); the retired `environment/data/known_traps_and_footguns.md` was moved out to `WORK/h2_a3/tasks_input_retired/` so the trees match. `diff -rq` empty (rc 0). Tree sha before 62dbcde0c809; after: bundle d3c86f82834f, Tasks_INPUT d3c86f82834f.

## Docs changed

Yes: instruction.md (IN-17 count phrases reworded, meaning kept), spec_stage_p01 (crosswalk rule
sentence), spec_stage_p10 (in-force rule sentence), worked_examples.md (legacy identifier toy),
data_lineage_and_governance.md (trap row removed), known_traps_and_footguns.md removed.

## Not run

Paid agent run; LLM judge (a3 graded by reading its trajectory). Per-seed G12 shape assertions exist
for the planted branch; the pre-existing Q4 abort rate was not fixed.

## Lessons for the master

- reference disputes that docs settle explicitly flip whole old checks to the paid run; check them before hunting levers | no change: already in route-1 notes
- precheck rejects weights outside {1,3,5}, probe ids other than R<n>, and types outside its list; design with them | template_change: _COMMON_RULES_v5.md weights/judge section
- chaining a delete after a failing python step lost a solution file; chain destructive follow-ups with && | no change: operator discipline
- the `every` held round that shared a corpus with another check paid twice through the manifest digest; give each check its own round | template_change: LEVER_RULES_v3.md section 4
- crosswalk-scope levers are single root cause; a careful enumerator passes them all | no change: recorded in kill table
