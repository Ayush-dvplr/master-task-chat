# DIAGNOSIS cohort-retention-reconciliation, v0 real run (claude-opus-5, Run 1)

Evidence copy: `baseline_v0/trajectory_job_cohort-retention-reconciliation_e5d428/`.

## 1. Recorded score and the permission trap
- reward.json 0.5868. reward-details.json does carry a judge result (the prompt
  said "no judge key"; the file says otherwise): judge 27 of 36 (0.75), tests 36
  of 85 (0.4235). 0.5 x 0.4235 + 0.5 x 0.75 = 0.5868.
- Tests-channel (tests-only label): 0.4235.
- Permission trap FIRED. verifier/test-stdout.txt holds 18 lines of
  `/usr/local/bin/python3.12: can't open file '/app/out/derive_report.py': [Errno 13] Permission denied`.
  v0 `_run_untrusted` runs the program under `setpriv --reuid=nobody` straight
  from /app/out with no `_grant_read()` copy. Every check that runs the program
  failed (49 points): cohorts_schema, 7 single-rule fixtures, exact_rate_formatting,
  hidden_seeded, second_seeded, deterministic. The 36 points earned were all
  shipped-data or file-shape checks.

## 2. Levers (detail in _work/.../LEVERS.md)
Local probe (/tmp/crr_probe: v0 test_output.py, rewardkit stubbed, program run
without the uid drop): the agent's own derive_report.py passes 12 of 12
program-run checks; solve.py also 12 of 12. Without the trap the tests channel
would have been 85/85 = 1.0. Every v0 lever LEAKED:
- V0-1 cleaning order: numbered sentence at point of use, hand trace step 5.
- V0-2 pre-cohort activity: sentence next to the active rule, shipped e026 shows it.
- V0-3 exclusion on resolved account: shipped a901 -> a900 row, step 5.
- V0-4 merge history: full rule in one paragraph; agent built a synthetic extract (steps 13-25) with chained and overlapping merges.
- V0-5 minimum value, V0-6 offset-zero flag: one key and one sentence each; both exercised by the agent's /tmp/alt extract.
- V0-7 exact rates, V0-8 running-minimum survival: explicit format block and one-line rule.
What made them derivable: every rule sits next to its use in one file; the
instruction lists the topics ("the cleaning and identity rules, ... the
identities"); the schema counts the residuals ("three residuals") and artifacts
("Ten JSON artifacts"); each fixture isolates one rule so a per-rule handler
passes it; the agent's synthetic extract mirrors the fixtures one for one.

## 3. Score composition (positive weight 85)
- Shipped-data-only: 39 (45.9%): artifact_set 1, seven visible_* 28,
  per_cohort 3, study_audit 1, canonical_serialization 3, rerun_byte_for_byte 3.
- Rule-isolating single-rule fixtures: 33 (38.8%).
- Whole-document on reseeded hidden inputs: 13 (15.3%), and the seeded
  generator only redraws events over a001-a008 with the shipped merges and
  exclusions, so even these never move a boundary the shipped data does not show.
Both study rule 6 (isolated <= ~30%) and rule 11 (shipped-only <= 5%) are broken.

## 4. Judge
18 criteria, all process or echo items (read schema first, ran on /app/data,
hand-counted a duplicate, named functions, no bare except). The agent met 16;
nothing needs a figure from the full chain. Honesty negative R13 fired (claims
verification passed without a run that showed it), dead-branch R17 fired.

## 5. Causes mapped to Phase 2
| cause | fix |
|----|----|
| program unreadable to dropped uid, no uid kill | P2.1 `_grant_read()` copy, kill by uid and process group, file lock |
| every rule beside its use, counts of rules and artifacts stated | P2.3 drop counts, split rules across files, scope-by-omission, decoy default |
| single-rule fixtures dominate, shipped-only 45.9% | P2.3 re-weight; whole documents on reseeded hidden extracts |
| hidden generator never moves merges, exclusions, plans | P2.3 new generator redraws every input file |
| judge criteria met from process | P2.4 figure criteria needing the full chain |

No cause found outside Phase 2. No DIAGNOSIS CONFLICT.
