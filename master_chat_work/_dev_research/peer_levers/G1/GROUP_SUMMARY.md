# G1 peer lever mining: group summary (board 98fa054)

- **Anubis HEAD:** `19cdf6989906385943b9ca00acaadcae204b29e8`.
- **Session:** renamed to `98fa054`, and the list shows it.
- **Per-task evidence:**
  - `A_gm-arena-ladder-payout-reconciliation-forge.md`, `B_gm-arena-ladder-payout-reconciliation-forge.md`
  - `A_h3-fleet-migration-scheduler-nk-20260907.md`, `B_h3-fleet-migration-scheduler-nk-20260907.md`
  - `A_lane-dispatch-optimisation.md`, `B_lane-dispatch-optimisation.md`
  - `A_project-schedule-feasibility.md`, `B_project-schedule-feasibility.md`
- **Reproduction:** scripts and outputs are in `_scratch/`. Each test module was imported locally with a stubbed rewardkit, and its own generator and reference were run. In every task the regenerated shipped corpus is byte-identical to `environment/data`. In every task the agent's recorded outputs were reproduced from the agent's own program.

## 1. Scores and verdicts

| task | verdict A | overall / tests / rubric | genuine test points lost | genuine judge points lost |
|---|---|---|---|---|
| gm-arena-ladder-payout-reconciliation-forge | GENUINE | 45.25 / 22.58 / 67.92 | **48 / 62**, all wrong values: 26 from the weight-scope lever (fix it alone and 14 more files match), 22 from payout rounding granularity on top | 34 / 106 lost; about 16 fair (R1, R6, R15, R25, R26, R33). About 18 are on unfair criteria: R13/R14 are w5 preferences, R18 is vacuous (the cap never binds), R24 uses a hidden tie-break. |
| h3-fleet-migration-scheduler-nk-20260907 | PARTLY | 67.19 / 75.28 / 59.09 | 22 lost. **19 come from an undefined/contradicted symbol (`consumed[n,e]`), a HIDDEN rule.** 3 come from ambiguous loop granularity (IN-16). Fair stated lever: 0. | 18 / 44 lost; 15 genuine conduct. 3 are an artefact (R14: trajectory observations null at steps 2, 6, 8). |
| lane-dispatch-optimisation | PARTLY | 33.90 / 3.09 / 64.71 | 94 / 97, all wrong values. **The budget-cap lever (stated, RISKY) is necessary for all 94 and alone accounts for 5.** The other 89 also need a disposition precedence that no file states (HIDDEN). Fixing the precedence alone recovers 0. | 12 / 34, genuine conduct (r18, r19, r20, r22) |
| project-schedule-feasibility | PARTLY | 69.38 / 98.77 / 40.00 | 1 / 81: a BOM on a JSON rule table; the agent was BOM-safe for CSV only | 21 / 35, all named-self-test conduct. 3 of those (r13) are a preference criterion. |

There are no permission or harness artefacts in any test score. All four `test.sh` files are identical and fine. h3, lane and psf run the agent program under setpriv nobody, with explicit chmod of the program, data and out directories. gm never runs agent code.

## 2. Lever patterns (SAFE or RISKY only), ranked by genuine points cost

### P1. Definition, then a later overriding clause in different vocabulary
- **Status:** RISKY. It becomes SAFE if the override uses the field's own name.
- **Points:** necessary for 94 test points in lane.
- **Mechanism:** a file defines a field plainly ("net = charge less rebate"). A later sentence in the same file changes the settled amount using other words ("the order settles the remainder"). The literal reader keeps the definition and reports the excess separately.
- **How it is written:** `lane/environment/data/cost_policy.md:8` and `:9-13`. The agent quoted the definition back in its final message (trajectory step 92).
- **Why the self-test misses it:** the only shipped output example (`probe_region_example.json`) has `capped_micros` 0. The agent's own synthetic generator encodes its own reading, so its self-test is self-consistent. Totals for charge, rebate and capped matched the reference exactly, and only net differed.
- **Family:** NEW, "default + amending clause" (closest to E, stacked constraints).
- **For our tasks:** in cohort-retention, define "retained user = active in week k". A later clause in the reactivation section says reactivated users "count from their return week". The output field keeps the first name. Write the override with the field's exact name so that it is stated.

### P2. Scope qualifier carried by a neighbouring definition, under a loud decoy
- **Status:** RISKY. It becomes SAFE if the scope is also written into a glossary entry for the term.
- **Points:** 26 test points in gm, plus 22 that it gates.
- **Mechanism:** the formula's denominator ("resolved count per server") silently inherits a scope ("resolved AND drawn") stated one sentence earlier as a property of the output set. Meanwhile the text shouts about a different trap (the partition, stratum vs server), and the agent fixes that one.
- **How it is written:** `gm/environment/data/spec_stage_s5_two_level_weights.md:3-7`. The partition is emphasised 3 times (instruction.md, S5, `known_traps_and_footguns.md`), the scope once.
- **Why the self-test misses it:** the shipped "worked records" files are stubs with no values. The agent's only check was that outputs looked plausible on shipped data ("resolved 140 weighted 91" printed at step 25 and never questioned).
- **Family:** A (hidden composition).
- **For our tasks:** in vendor-archive, "invoice count per vendor" in a rate formula should inherit "matched AND not superseded" from the population definition. The trap list loudly covers currency partitions instead.

### P3. Rounding unit is per item, not per aggregate
- **Status:** RISKY. As written in gm ("at each stage") it is IN-16 bait. The SAFE form states the unit ("each match's credit is rounded half-even before summing") in the stage file, not in the formula line.
- **Points:** 22 test points in gm, together with P2.
- **Mechanism:** the agent rounds stratum sums once. The reference rounds each per-match term, then sums. The result is off by 1-4 credits, which fails byte-exact checks on 8 files.
- **How it is written:** `spec_stage_s8_uncertainty_payout.md:6-10` ("charged per flagged match ... Round half-to-even at each stage") and `rounding_and_precision.yml` (`half_even_at_each_stage`).
- **Why the self-test misses it:** there is no shipped expected value, and both readings give plausible integers.
- **Family:** E (stacked constraints).
- **For our tasks:** in district-heat, round each meter-day delivery to integer kWh before the monthly billing sum. Our self-tests can never tell the two readings apart without a worked figure. Ship one worked figure only for a case where the two readings agree.

### P4. Named-edge-case conduct criteria in the judge
- **Status:** SAFE (odds-raising per JD-15, w3).
- **Points:** psf 18 (21 minus r13), lane 12, h3 about 6 (R11, R12). About 36 judge points in total.
- **Mechanism:** each criterion reads "runs its program on an extract it constructed in which <the case the shipped data does not contain> and checks <observable>". Agents test the cases they think of. These criteria pay for the cases the shipped data does not show.
- **How it is written:** `psf/tests/judge.toml` r6 and r14-r18, and `lane/tests/judge.toml` r18-r22. The criteria are not visible to the agent, but every rule they probe IS stated in the spec.
- **Why the agent misses it:** it self-tests on shipped data plus a few adversarial cases of its own (psf step 13: cycle, ghost predecessor, overflow). It covered r14 by chance and missed the other 6.
- **Family:** NEW, "self-test coverage of the non-shipped case".
- **For our tasks:** for each lever, add one w3 criterion of the form "constructs an extract where <reactivation week == cohort week> and checks <retained_count>".
- **Caveat:** JD-7. The shipped oracle has no trajectory, so QC must accept conduct criteria (open question 1).

### P5. Whole-document byte-exact cascade (amplifier, not a lever)
- **Status:** RISKY (TS-26 double payment).
- **Points:** amplifies P1-P3 (gm: one scope error fails 16 files; lane: one cap error fails 24 checks).
- **Mechanism:** downstream artifacts are compared whole, so a single upstream misreading fails every dependent check.
- **Family:** B (dependent chain).
- **For our tasks:** do not copy it. Grade isolated views of each document (as psf does with `_schedule_rows` and `_float_view`) so that each lever is paid once.

### P6. Inconsistent input robustness
- **Status:** RISKY. It becomes SAFE if the spec says "any input file may carry a byte-order mark".
- **Points:** psf 1 test point.
- **Mechanism:** the spec says only "UTF-8 encoded text" (`psf/environment/data/schema.md:13-14`). The agent guarded CSV reading (`utf-8-sig`) but not JSON reading, so a BOM on a JSON rule table crashed the program (test-stdout traceback).
- **Family:** F (error path).
- **For our tasks:** state the BOM/CRLF tolerance once in the schema, covering all files. Then apply it in the hidden corpus to the one file type the agent is least likely to guard, a JSON or YAML rule table. This is untested whether it bites once it is stated (INFERRED).

## 3. Writing patterns that keep a rule stated but not reflexively solvable
1. **Amend in a later sentence, in other words** (lane cost_policy:8 then :12-13). The definition reads as complete, and the amendment reads as a side note.
2. **Scope as a property of the output set, inherited silently by a later formula** (gm S5:3 and then :5-6). The formula sentence itself carries no qualifier.
3. **Loud decoy emphasis.** Repeat one trap three times (gm partition) so the agent's attention budget goes there.
4. **A partial footgun list.** gm `known_traps_and_footguns.md` names 11 traps. The agent passed every listed trap and failed only the 2 unlisted ones. A list sets the agent's checklist. Leave the real levers stated in the spec but off the list.
5. **Per-item units in a preposition** ("charged per flagged match"), not in the rounding rule.
6. **Shipped examples that never exercise the binding case.** In lane, the cap is 0 in the probe example. In gm, the worked examples are stubs. Every rule stays stated, but no shipped figure lets the agent check it. Our cohort data did the opposite (DIAGNOSIS cause 4: "shipped boundaries let agent see each rule fire").

## 4. Anti-patterns (looked hard, cost nothing, or only work because the rule is hidden)

These cost 0 points:
- **Withheld constants or settlements with separating evidence.** h3 withheld 4 rules and shipped 6 seals; the agent brute-forced 24 combinations and exactly one fit (steps 14-15). lane withheld 12 encoding constants with control figures; the agent recovered all 12 (steps 8-24). Neither cost a point.
- **Hidden reseeded corpora on unambiguous rules.** psf put 63 of 81 points on unseen corpora and the agent passed every one. A generator only pays when a rule has a reading the shipped data does not separate.
- **Traps explained in the text.** Examples are psf "does not re-check capacity" (schema.md:100), lane "it reverses the habit of favouring the tighter deadline" (dispatch_policy.md:27) and all 11 gm footguns. The agent passed every one. This matches our DIAGNOSIS cause 4.
- **CSV-level format noise.** psf BOM-CSV, CRLF and trailing fields, and lane's 7 fmt_* variants (correct once the value levers are fixed) were all handled.

These only work because the rule is hidden, so they are NOT ALLOWED for us:
- h3 `consumed[n,e]`. It is never defined, and README:16 says MTU units, which contradicts the reference's stream count (19 points).
- lane disposition precedence. No file states which of deferred or rejected wins; instruction.md:68-69 and judge r5 point the other way (89 points co-required).
- gm R24 tie-break by stratum name.
- h3 loop granularity, per-epoch vs "across all tenants and epochs" (README:31 vs :106). This fails IN-16.

Unfair judge criteria:
- gm R13/R14, preference demos at w5 (fail JD-15).
- gm R18, vacuous because the trim never binds (fails JD-7).
- psf r13, checksum-before-first-run is a preference.

## 5. Score artefacts found (Phase A)
- **h3 judge R14 (3 points):** trajectory observations are null at steps 2, 6 and 8, so the judge saw no output for the header print. The same scan found psf step 2 null (no criterion affected), and none in gm or lane.
- **lane `result.json` timing:** it shows 73 s, but the trajectory runs 15:54-16:40 (about 46 min). This is metadata only; the score is unaffected.
- **h3 embedded verifier data:** `case-brigantine.json` differs from the shipped copy, but its test passed. No effect.
- **No test score anywhere comes from a permission or path problem.** Do not read the lane tests score of 3.09 as a "hard gate". It is two value levers cascading through whole-JSON comparisons.

## 6. Open questions for the master chat
1. **JD-7 vs conduct criteria.** Our oracle `solve.sh` leaves no trajectory. Does our QC accept "runs its program on a constructed extract where X" criteria (P4)? All four peers rely on them.
2. **IN-16 ruling on P1.** Is a field definition plus a later amending clause acceptable if the amending clause names the field explicitly? Or is any later override "two defensible readings"?
3. **Does stating it kill it?** Do P2 and P3 still bite once the scope and rounding unit are written unambiguously (the SAFE forms)? No peer evidence exists. This needs one pilot run on our task.
4. **TS-26 double payment.** Should we keep any whole-document comparison, or only isolated views? The peers' big test losses (gm 48, lane 94) come largely from cascade amplification.
5. **Judge weight.** lane's peer judge rewarded the very precedence its tests penalised (r5 passed, tests failed). Should we add a QC check that no judge criterion endorses a reading the tests penalise?
