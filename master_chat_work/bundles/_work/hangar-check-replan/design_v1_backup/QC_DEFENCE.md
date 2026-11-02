# QC_DEFENCE af5dddf hangar-check-replan

One entry per lever and per cascade. Rule ids per entry; quoted live rule; why it passes; fallback (QC_FIX_PLAYBOOK_v3 row, DO column only).

## R1 shared overtime pool + compression
- Rule ids: IN-15, IN-16, IN-17, AL-1, AL-27, CL-4, TS-19, TS-20, AL-28.
- Live rule (docs/overtime_policy.md): "The fleet has one overtime pool for the season: the overtime shifts of all compressed checks at all four bases together may not exceed `overtime_pool_shifts` in fleet_limits.toml." Compression: "A check may be shortened by up to `max_compress_days` of its type; each day taken off uses `overtime_shifts_per_day` shifts."
- Why it passes: IN-15 the rule is stated in the governing file; IN-16 one reading (a sum over the fleet bounded by one number); IN-17 no sentence says the pool binds or that bases interact (the instruction states only the job); AL-1 no unstated deliverable property; AL-27 every hidden corpus plants a binding pool (BRANCH_FIRE); TS-19 hidden pools and compress limits stay inside the bounds stated in docs/data_conventions.md; CL-4 whole-document exactness is stated in instruction.md, exemption FC:491 "An instruction that states out loud that only an exact match counts has set that bar deliberately", one-fact-wrong score reported in COST_TABLE.
- Fallback: IN-16 row DO: add one general settling clause to docs/overtime_policy.md ("the pool is shared by every base; shifts are counted once per compressed day"); AL-27 row DO: add a hidden corpus that constructs the binding case; never state that the pool binds.

## R2 four-term order with the moved term
- Rule ids: IN-15, IN-16, IN-17, AL-1, AL-27, CL-4, TS-13, TS-26.
- Live rule (docs/planning_policy.md): "Plans are compared on these terms in order, and a plan is better when it is smaller on the first term where they differ: first, ...; second, ...; third, the number of moved requests, where a request is moved when it is scheduled with a start other than its published start in published_plan.csv, or deferred."
- Why it passes: one reading (start equality with a named field); no sentence says early starts are allowed but costly; the shipped data has available_from equal to the published start, so the shipped input does not establish the branch and no IN-17 sentence announces it.
- Fallback: IN-16 DO: REBUT quoting 01:46 with the 3-part check (one field, one comparison, one count); AL-1 (4b): EVIDENCE_MAP row naming published_plan.csv column `published_start`; never add an example where readings differ.

## R3 deferral penalty and reasons
- Rule ids: IN-15, IN-16, IN-17, AL-27, DS-25, CL-4.
- Live rule (docs/deferral_policy.md): "Any open request may be deferred to next season instead of being scheduled. A deferred request adds the `deferral_penalty` of its class to the first term and counts as moved. Its reason is `no_slot` when the check cannot finish by season end at any compression on a line with no other check, and `plan_trade` otherwise."
- Why it passes: DS-25 both literals are in the governing file; IN-16 the reason split is a determinate test on stated fields; AL-27 every hidden corpus plants a `plan_trade` deferral.
- Fallback: AL-27 DO: add a hidden fixture that forces a `plan_trade`; IN-16 DO: REBUT with the 3-part check; never name which request is deferred.

## S3 tie-break (supporting)
- Rule ids: IN-16, DS-20, AL-27, CL-4.
- Live rule (docs/planning_policy.md): "When plans tie on all three terms, compare the list of start days of every request in request_id order (a deferred request counts as the day after season end), followed by the list of finish days in the same order; the smaller list at the first difference wins."
- Why it passes: a total order on distinct plans; DS-20 brute-force check over 400 tiny instances (proto/brute.py) and check_exact.py per-record diff.
- Fallback: DS-20 DO: fix the oracle; IN-16 DO: REBUT (total order, one reading).

## Cascade C1: one plan feeds every output (COUPLING)
- Rule ids: TS-13, TS-26, CL-4, AL-28, G1a.
- Live rule (docs/output_schema.md): "Every scheduled check, base total and fleet total is taken from the single season plan that is optimal under the stated order for the whole fleet, including the shared overtime limit."
- Why it passes: TS-13 each check grades one view of one corpus (whole document per view, district-heat PASS); TS-26 the shared `fleet_overtime_used` copy is masked outside the summary owner, so no two checks read the same observable with the same logic; CL-4 FC:491 exemption.
- Fallback: TS-13 DO: split the regions view into one check per base file; TS-26 DO: name the observable and narrow one check.

## Cascade C2: rejects feed the planning set
- Rule ids: DS-25, IN-16, TS-19.
- Live rule (docs/data_conventions.md): reject reasons `unknown_tail`, `retired_tail`, `bad_date`, `bad_duration`, `unknown_base`, `unknown_check_type`, `duplicate_request`, `no_published_start`; first row of a duplicated request_id kept.
- Why it passes: every literal stated; hidden generators draw rejects only from those forms; no contract sentence lists the malformed values of a typed field (LV-ENUM).
- Fallback: TS-19 DO: add the grader check on the hidden forms; DS-25 DO: state the missing literal once in docs/data_conventions.md.

## Judge (probe band)
- Rule ids: JD-7, JD-8, JD-15, JD-18, AL-28.
- Each probe is shown by a solve.sh self-check stage (`check <id> ok` + witness); JUDGE_MAP lists it. No criterion reads a test observable. One J4 conduct criterion. Negatives one act each, disjoint.
- Fallback: JD-7 DO: add the self-check stage to solve.sh; JD-8 DO: delete the overlapping criterion and renumber; JD-15 DO: relabel type.

## Lessons for the master
- none yet | no change: design stage
