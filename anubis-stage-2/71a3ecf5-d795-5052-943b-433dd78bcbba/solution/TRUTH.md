# TRUTH.md - 71a3ecf5-d795-5052-943b-433dd78bcbba

## Defect

There is no broken program to repair. `/app/data` holds one survey round in
forty seven flat files: a written standard (`HAS-7-standard.md`), a field index
(`HAS-7-field-dictionary.psv`), three frame registers and a reissue copy, an
address register, a subsample register, five contact files, twelve interview
files, two prior-band files, seven benchmark files with a unit register, a
pilot record, rule files and reference registers. The deliverable is a reusable
program, `/app/out/derive_survey.py DATA_DIR OUT_DIR`, that writes twenty-two
exact reports. The standard states every rule; its sections are grouped by
subsystem and do not follow the order the rules are applied in. Two settings,
the raking margin order and the raking rounding point, are written nowhere and
must be recovered from the pilot record's aggregate figures. Each item below
names the checks it defeats.

1. (focal) Two withheld settings. Of the twelve combinations of six margin
   orders and two rounding points (round every weight at each margin, or carry
   exact ratios through an iteration and round at its end), exactly one
   reproduces the pilot's 27 published figures (its iteration count and the
   raked total of every level). The shipped round uses
   `band, region_tenure, activity` with rounding at the end of each iteration;
   the three hidden extracts use other combinations. Replaying the shipped settings everywhere fails the hidden adjustment groups onward
   and fires `negative_reuses_shipped_margin_order`.
2. (focal) Contact corrections are late evidence at the end of the reference
   wave log: only the net state at the latest instant counts, a reinstatement
   wins a same-instant tie (planted in both line orders), and an out-of-scope
   void of a settling attempt must be ignored. Each of these is decisive in every extract (`*_dispositions` onward).
3. (focal) The contact band of a nonresponse cell is derived from the number of
   attempt records at waves one and two through the contact band register; the
   address register's `Contact-Band` is a stale decoy. Using it fails `*_adjustment` onward.
4. (focal) Trimming is gated on the stratum design effect of the raked weights; trimming every stratum is the plausible superset (`*_trimming` onward).
5. (focal) Replicates replay the whole chain; rescaling final weights fails `*_estimates` onward.
6. (drift) The trimming median of an even count is the lower central value; the upper median fails `*_trimming` onward.
7. (drift) Instants are truncated; rounding fractional seconds fails `*_dispositions` onward.
8. (trap) Benchmark ties: the equal-rank winners of the date and the source case
   sit in files that sort after the losers, so keeping the first offer read, or dropping the source level, fails `*_benchmarks` onward.
9. (trap) The reissue copy is the only source of the PSU for households whose
   surviving register record leaves `psu_code` blank; ignoring it, or treating the copy as a fourth register, fails `*_frame` onward.
10. (trap) A wave two interview that reports hours governs over the stale wave
    two prior band file; reading the prior file first fails `*_adjustment` onward.
11. (trap) A zero dwelling count is never eligible, even with a complete
    interview; reading it as one dwelling fails `*_dispositions` onward.
12. (trap) Stratum names arrive decomposed for Westföld in the shipped and the
    second extract; comparing without NFC fails every shipped and second-extract group.
13. (trap) Tie-breaks that decide planted fixtures: the higher attempt number
    at the same instant is written after the lower one (keeping the first record fails the dispositions groups); a registry sector with no households gives equal coefficients of
    variation in one table, so the cell key decides the screening rank (key descending fails the disclosure groups); clock readings instead of instants; the collapse cap (1 and 2 in hidden extracts); the raking cap, recorded as not converged (the shipped round itself stops at 13 iterations unconverged); the cascade cap. Interview gaps are planted too: households with no reference wave interview (never responding), no wave one interview (no band transition row) and neither interview hours nor prior bands at waves two and three (the zero hours band).

Out of bounds: replaying the shipped reports on unseen extracts
(`negative_hardcoded_sample_answers`), reusing the shipped margin order
(`negative_reuses_shipped_margin_order`), output that varies between runs
(`negative_nondeterministic_output`), with the directory name
(`negative_filename_dependent_behaviour`) or with row order
(`negative_input_row_order_dependence`), stray files in the output directory
(`negative_writes_outside_declared_artifacts`), and third party imports
(`negative_uses_a_third_party_library`).

## Load-bearing work

Concepts: identity canonicalisation under NFC; frame deduplication with a three
level survivor chain and eight counted repair classes; PSU completion from the
reissue copy; disposition resolution by severity, instant and attempt with
net-state corrections; contact bands derived from prior-wave attempt counts;
band carry-forward with source authority; benchmark vintage selection with unit
conversion; design weights with subsampling; bounded nonresponse collapse;
raking with a recovered margin order and rounding point; design-effect-gated
trimming; delete-one-PSU jackknife with merged groups and a full chain replay per
replicate; four cross tables; primary screening, an iterated cascade and a cross
table ranking; closure.

Shipped figures: 840 resolved households, repairs M1 to M8 of 187, 254, 253, 57,
34, 89, 252 and 425, 707 eligible and 512 responding, 39 cells after 3 collapse
rounds, 13 raking iterations without convergence, 24 households trimmed, 36
replicates in 8 groups (26 not converged), 34 primary and 10 secondary
suppressions, a final total 1 micro-unit below 331500000000 and a post trim
deviation of 377738084.

Inputs: every non-.md file except the field dictionary feeds at least one
shipped report; the configuration files stop the program when emptied, and the
record files change between 5 and 20 of the 22 reports. Every report is also graded on three extracts the verifier
builds itself, so removing a shipped file never touches 105 of the 128 points.

## Verification

`tests/test.sh` clears stale reward files, locks `/logs/verifier` to root with
mode 755, restricts `/tests` and ends with `exec rewardkit /tests --workspace
/app --output /logs/verifier/reward.json`. `tests/reward.toml` gives each
channel half of the reward: `test_output = 0.00390625` (0.5 / 128) and
`judge = 0.01282051282051282` (0.5 / 39).

The test channel has 35 checks: 28 positive with total weight 128 and 7
negative with total weight -25. The verifier rebuilds the shipped extract from
its own generator, runs the delivered program on it, and runs it on three
hidden extracts: challenge (420 households, `activity, band, region_tenure`,
rounding at each margin, collapse cap 1, cascade cap 1, no decomposed names),
second (560 households, four regions, `region_tenure, activity, band`, rounding
per iteration, iteration cap 4 so the round does not converge, no repeated clock
hour) and third (480 households, `band, activity, region_tenure`, rounding at
each margin, collapse cap 2, cascade cap 3, neither decomposed names nor a
repeated clock hour). Program runs are serialised, each limited to 120 seconds,
as `nobody`.

Positive checks at weight 1: `artifact_set_exists_and_parses`,
`report_serialization_format`, `unseen_run_writes_complete_report_set`.
Positive checks at weight 5 on the shipped extract, each requiring the delivered
file and the program's own run to equal the standard's bytes:
`shipped_frame_to_design_reports`, `shipped_weighting_reports`,
`shipped_replication_and_estimates`, `shipped_disclosure_reports` (20 points).
Positive checks at weight 5 on the hidden extracts, seven report groups each
(frame, benchmarks, dispositions, adjustment, trimming, estimates, disclosure):
`challenge_frame`, `challenge_benchmarks`, `challenge_dispositions`,
`challenge_adjustment`, `challenge_trimming`, `challenge_estimates`,
`challenge_disclosure`, `second_frame`, `second_benchmarks`,
`second_dispositions`, `second_adjustment`, `second_trimming`,
`second_estimates`, `second_disclosure`, `third_frame`, `third_benchmarks`,
`third_dispositions`, `third_adjustment`, `third_trimming`, `third_estimates`,
`third_disclosure` (105 points).

Negative checks: `negative_hardcoded_sample_answers` (-5),
`negative_reuses_shipped_margin_order` (-5, stands down when the hardcoding
check fires), `negative_nondeterministic_output` (-3),
`negative_filename_dependent_behaviour` (-3), `negative_input_row_order_dependence`
(-3, stands down when the renamed copy already moves the output),
`negative_writes_outside_declared_artifacts` (-3),
`negative_uses_a_third_party_library` (-3).

Each one-rule change of the reference program loses the groups of every extract where that rule
fires and keeps the rest. Measured on the test channel only, graded on the host with the verifier module
and a stand-in rewardkit: the reference program scores 1.000; an empty run
0.000; a program that re-emits the shipped reports 0.141; a program that springs
none of the traps 0.023; carrying a wave two interview forward to the reference
wave 0.258; giving a household with no wave one interview the zero hours band
0.688; a wrong final band fallback 0.414; a program whose output embeds its input
path 0.820 with only `negative_filename_dependent_behaviour` firing. The judged
channel has no oracle score.

The judged channel has 18 criteria, positive total 39 and negative total -17.
R1 to R8 are the closing-summary answers, which no report carries; the
reference model computes them in `disclosure_facts` and they agree with reruns
of the reference program on edited copies of the extract: a last-iteration
deviation of 5393301 under the other rounding point (R1, 3), 13 of 27 pilot
figures for the best losing combination (R2, 5), 4 status changes at a minimum
count two higher (R3, 5), 5 at a coefficient of variation ceiling 500 basis
points lower (R4, 5), a finished total of 331499999995 under the rule file's
margin order (R5, 5), 3 strata trimmed at a trigger 100 basis points higher (R6,
3), 15 iterations for the slowest replicate at a doubled limit (R7, 3), and 43
suppressed cells with a single cascade pass (R8, 3). R9 (3) is the pilot comparison habit; R10 (1) is
code quality; R16 (3) is rerunning the derivation under a changed setting for a
what-if question; R11 (-5) and R12 (-1) quote the instruction's leave-unchanged
and nothing-else sentences; R13, R14, R15, R17 and R18 price unchecked pilot
claims, false pass claims, summary answers that differ from the agent's own
printed figures, repeated failing commands and unread sources.

## Root cause

Every number is an integer: weights and totals in micro-units, rates in basis
points, division rounded half away from zero. Reports compare byte for byte, so
a slip in one rule shows in every report downstream of it and nowhere upstream,
and grading on four extracts with different trap mixes keeps a slip that only
one extract exercises from costing the others.

## Solution shape

Read the standard and the field index, then parse each file in its own format.
Fold identifiers and codes under NFC. Resolve the frame and its repairs,
complete PSUs from the reissue copy, settle dispositions with net corrections,
derive contact bands from prior-wave attempts and bands with carry forward,
select controls and compute design weights. Recover the margin order and
rounding point by raking the pilot under all twelve combinations and comparing
the aggregates. Run the chain once for the round and once per replicate,
tabulate, screen, cascade, rank, audit and reconcile.

## Ordered plan

1. Read the standard end to end and map each section to its files.
2. Write readers for every format; fold identifiers and codes under NFC.
3. Resolve the frame, the corrections, the dispositions and the contact bands.
4. Recover the two raking settings from the pilot and confirm exactly one match.
5. Build the chain with the caps and the trim gate, then replay it per replicate.
6. Tabulate, screen, cascade, rank and close; confirm identical bytes across
   repeat, renamed and row-shuffled runs.
7. Answer the eight what-if questions by rerunning the relevant stages.

## Pitfalls

- Reading the address register's contact band, or the stale wave two prior band.
- Treating the reissue copy as a register, or ignoring the PSU it supplies.
- Keeping the first benchmark offer read in file name order.
- Deciding correction ties by line order, or honouring an inactive correction.
- Rounding at every margin by habit, or fixing a margin order from the rule file.
- Trimming every stratum, rescaling replicates, or ignoring a cap the shipped
  round does not reach.

## Provenance

```yaml
uuid: 71a3ecf5-d795-5052-943b-433dd78bcbba
instance_id: 71a3ecf5-d795-5052-943b-433dd78bcbba
task_name: terminal-bench/71a3ecf5-d795-5052-943b-433dd78bcbba
fix_patch_sha256: 2e0d5282f643b95d47bbd457a494ab79f5d0cca1a2d159d36e9e8ad106860de6  # sha256 of solution/solve.sh
solve_py_sha256: c9cf78d70595ffb07c4a27fad5925837d414655c3103b2e965589bab1135b773  # informational; solve.py is 1032 lines
language: python
golden_score_measured: null  # not measured for this instance
golden_score_channel_a_pct: null
golden_score_channel_b_pct: null
golden_score_runs: 0
golden_score_trial_id: null  # no model trial has been run
golden_score_verified_by: >
  Test channel only, graded on the host with the verifier module and a
  stand-in rewardkit: the reference program scored 1.000 and an empty run
  0.000. The judged channel has no oracle score.
caveat: >
  The test channel carries 28 positive checks worth 128 and 7 negative checks
  worth -25, so on its own it ranges from -0.195 to 1.000. The judged channel
  carries 18 criteria worth 39 positive points. tests/reward.toml divides each
  channel's weighted sum by its positive total and gives each half of the
  reward, so the combined reward runs from -0.316 to +1.000 with no clamp.
```
