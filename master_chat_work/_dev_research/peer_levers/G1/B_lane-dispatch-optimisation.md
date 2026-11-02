# B: lane-dispatch-optimisation (PARTLY)

Paths below are relative to the task folder `T=.../Abdus Samad Ali/lane-dispatch-optimisation/`. Scratch evidence lives in `OUT/_scratch/` (lane_cmp.py, lane_variants.py/.out, lane_fix_*.py).

## 1. Inventory
- **Domain:** binary packet decoding plus dispatch settlement: client identity, programme revisions, a congestion-admission fixpoint, branch-and-bound lane placement, and money settlement.
- **Archetype:** a reusable program `/app/out/derive_report.py <in_dir> <out_dir>` that writes 10 JSON reports. It must recover 12 withheld encoding constants from a held-out calibration population and its published control figures (`instruction.md`, 890 words).
- **Agent-visible files:** 19 small files under `/app/data`, about 45 KB in total:
  - 9 CSVs with 3-21 lines each (field_orders.csv 11 lines, calibration_orders.csv 9, client_directory.csv 17, lane_roster.csv 17, program_registry.csv 20, block_manifest.csv 21);
  - 9 policy/spec markdown files (packet_encoding.md 7.2 KB, report_schema.md 6.0 KB, the rest 0.8-2.5 KB);
  - probe_region_example.json.
  - The field population is 145 decoded records, 115 genuine.
- **Tests:** 27 positive checks totalling 97 points, plus 6 negatives (-5, -5, -5, -3, -3, -3; none fired). Each positive groups several variant runs with `_all`, and each run is a whole-JSON compare per artifact.
- **Hidden/reseeded inputs:** yes, 38 variants generated at test time by an embedded generator (`tests/test_output.py` VARIANTS L2299; mapping L3207-3305): shipped, 7 format rewrites, 12 single-constant traps, 20 rule/population mutations. The program is run under `setpriv` as nobody.
- **Weight split:** 25 of 97 test points grade only the shipped instance or its format rewrites; 72 grade reseeded or mutated corpora.
- **Judge:** 23 binary criteria (20 positive = 34 pts, 3 negative), batched mode, atif trajectory. The overall score is the mean of tests and rubric ((3.09 + 64.71) / 2 = 33.90), so the split is 50/50.

## 2. Rule map (graded rules relevant to the outcome)
| Rule | Where stated | Form | Trap explained? | Shipped data separates readings? |
|---|---|---|---|---|
| 12 withheld constants | packet_encoding.md (candidates) + calibration_slice.md:12-35 (each control figure defined in an HTML comment), :37-39 says the figures resolve in list order | split across files; definitions in comments | yes, one control per constant in order | yes, by design (exactly one assignment fits) |
| Contention: larger slack keeps the lane | dispatch_policy.md:24-31 | one paragraph | YES ("it reverses the habit of favouring the tighter deadline") | yes |
| Closed merge chain: first identifier governs | identity_policy.md:12-13 | one sentence | no | mutation variant only |
| Retired = reject, not-yet-active = defer | identity_policy.md:14-18; report_schema.md:23-29 | one sentence each | no | yes for single cases |
| Revision gap = reject | revision_policy.md:12-13; report_schema.md:27-29 | one sentence | no | yes |
| **Precedence when inactive AND in a gap** | **nowhere**. instruction.md:68-69 orders client resolution before revision selection, which suggests the opposite | absent | n/a | one field order (W000407) carries both flags; no control separates the readings |
| **Budget cap reduces net** | cost_policy.md:8 (net = charge - rebate) and :9-13 ("the order settles the remainder"); report_schema.md:33-34 (capped total, net total) | **definition + later modifier in different vocabulary** | no | field has binding caps (24020 capped); probe example shows capped 0; no control figure covers money |
| Admission fixpoint pass counting | capacity_policy.md:16-20 | one paragraph | partly | yes |
| Format tolerance (BOM, padding, zero-padded ids, case, draft/archived docs ignored) | packet_encoding.md:11-13 ("spaces around a header name or a cell are not part of it"), instruction | one sentence each | no | format variants only |

## 3. Lever table (failed checks and criteria)
| id | weight | rule graded | agent reading | correct reading | mechanism | self-test on shipped data catches it? | fully stated? | family |
|---|---|---|---|---|---|---|---|---|
| L1 budget cap | necessary for all 94 lost test pts; alone it would flip only population_shapes w5 | net after cap | step 26 code keeps `net_micros` = charge - rebate and stores `capped` separately; step 92 "net_micros is charge less rebate as cost_policy.md defines it" | net = remaining room under the ceiling (test_output.py L738-775) | a **default definition followed by an exception clause** in other words ("settles the remainder" vs "net value"). The output schema has both `capped_micros` and `net_micros`, so "net = charge - rebate, capped beside it" looks self-consistent, and the conservation invariant holds under both readings | N: no control figure or worked example covers money; the probe has capped 0; the agent's own invariants (conservation) pass either way | YES (cost_policy.md:9-13) | NEW "definition + overriding clause" (close to E) |
| L2 disposition precedence | necessary for 89 pts (all except population_shapes) | inactive+gap order is rejected | step 70 AGENTS.md: "rejects on retirement, then defers an inactive client, then rejects a revision gap. The task statement fixes this order" | revision gap rejects before deferral (test_output.py L509-540) | two definitions overlap and no precedence is written; the instruction's work order points the other way | N (no control separates them, step 70) | **NO, HIDDEN RULE** | F (error path), NOT ALLOWED |
| judge r18 | 3 | rewritten-table self-run | no such run | run on BOM/padded copy | conduct | n/a | yes (criterion) | conduct |
| judge r19 | 3 | extra-document self-run | none | run with decoy doc | conduct | n/a | yes | conduct |
| judge r20 | 3 | rule-perturbation self-run | none | change a rate, rerun | conduct | n/a | yes | conduct |
| judge r22 | 3 | merge-cycle self-run | none | constructed cycle corpus | conduct | n/a | yes | conduct |

Evidence for the attribution: `_scratch/lane_variants.out`. fix_both is OK on all 38 variants. fix_cap alone is OK on 7 variants (only population_shapes complete). fix_prec alone is OK on none.

## 4. Contrast: what the agent passed and why
- **All 12 withheld constants** (judge r8-r13 passed; all 12 trap_* variants OK after the two money/disposition fixes). Each control figure carries an HTML-comment definition, and calibration_slice.md:37-39 tells the agent the figures resolve one at a time in list order. That is a guided search with a perfect oracle in the data, the same failure as our levers ("shipped boundaries let agent see each rule fire").
- **Contention reversal.** The trap is explained in the text ("it reverses the habit..."), so it leaked exactly like our CR-1.
- **Format rewrites** (BOM, padding, zero-padding, case, draft/archived documents). Each is one plain sentence; the agent handled all of them (fmt variants differ only by the money/disposition errors).
- **Optimal placement.** The agent brute-forced and proved optimality itself (steps 41-66).
- Pattern: every rule that comes with a control figure, or that has its trap spelled out, was solved. The only stated rule it missed has no control figure and no example output, and is written as a definition followed by a later amendment.

## 5. Agent behaviour
- 93 steps, about 46 min.
- Steps 2-7 read every policy file, the schema, the probe example and all CSVs in full.
- Steps 8-24 recover the constants one by one against the controls (`/app/work/explore.py`).
- Step 25 plan; step 26 writes the program in one go; steps 27-36 edits; steps 37-38 run.
- Step 39 runs on a probe-as-field corpus and matches the probe rollup byte for byte.
- Steps 41-66 stress the placement against brute force on random synthetic sites.
- Step 60 lists the dual-flag orders and sees W000407.
- Steps 74-79 build its own corpus generator with different constants; the program recovers all 12 and decodes 430/430.
- Steps 80-82 check schema and invariants.
- Step 92 final claim: "All twelve published figures are reproduced exactly", 242910 net (reference 218890).
- The agent noticed both ambiguous readings and recorded them in AGENTS.md, but it resolved both the wrong way.
- Its self-tests used a generator that encodes the agent's own rule reading, so they could not catch L1 or L2. Self-consistent synthetic data is blind to interpretation errors.

## 6. Test design
- Expected values are recomputed at test time by an embedded reference engine on generated corpora; `_materialise("shipped")` regenerates the shipped data byte-identically.
- There is no partial credit inside a check: each check is the `_all` of several variants, each a whole-JSON compare.
- 6 negatives cover hardcoding, filename dependence, reading the answer/probe files, nondeterminism and rebinding dependencies. None fired.
- Every value check grades whole downstream documents. One money-stage error therefore cascades into 24 of 27 checks.
- Shipped-only weight is 25/97; the rest are reseeded variants, but these did not add separation here because L1 and L2 already fail on the shipped data.

## 7. Judge design
- The failed r18-r22 are odds-raising self-test conduct at w3, allowed under JD-15 (04_Judge_QC.md:92: odds-raising 1/3 passes).
- **Reusable patterns:**
  - r8-r13: a derivation record that must report intermediate figures, checked against the reference. This grades upstream stages separately from the final money.
  - r16/r17: a self-run on a probe-free corpus or a re-encoded corpus.
- **QC concerns:**
  - r5 "identity before revision" rewards the very ordering that produced the wrong disposition, so the rubric and the tests disagree on precedence (AL risk).
  - JD-7 (04:76, "Every criterion must be satisfied ... by the shipped oracle in solution/"): conduct-only criteria r16-r22 cannot be shown by `solve.sh` (INFERRED RISKY).
  - JD-18: r23 code quality is present (w1), so JD-18 is met.
  - JD-8: r8-r13 grade derivation-record figures; the tests compare policy_audit only on format (policy_audit is not in VALUE_ARTIFACTS), so there is no overlap.

## 8. QC safety
| Lever | IN-15 | TS-16 | TS-19 | TS-20 | AL-28 | Verdict |
|---|---|---|---|---|---|---|
| L1 definition + overriding clause (budget cap) | stated (cost_policy.md:9-13) | n/a | learnable from a spec file the instruction points to | weight 5 on core outputs, fine | n/a | **SAFE if** the clause names the field it changes (e.g. the overriding clause uses the same term as the field). As written it is **RISKY**: "settles the remainder" vs the field `net_micros` defined as charge less rebate is IN-16 bait (two defensible readings) |
| L2 precedence of overlapping dispositions | **fails** (no file states it; instruction suggests the opposite) | n/a | fails | n/a | n/a | **NOT ALLOWED** |
| Whole-document cascade (one upstream error fails 24 checks) | n/a | n/a | n/a | RISKY: TS-26 double payment, because one misreading is charged in many checks | not a penalty | RISKY |

## 9. Writing style (how rules are stated without giving the trap away)
1. cost_policy.md:8 then :12-13, "The net value of a placed order is its charge less its rebate." ... "the order settles the remainder." Technique: a clean definition first, then a later bullet amends it in different vocabulary, so a literal reader keeps the definition.
2. calibration_slice.md:13, a control figure defined only in an HTML comment ("the sum ... of the first four bytes of each block payload read as one big endian word once that payload sits at its true origin"). Technique: the precise definition sits outside the visible text, but it is still fully stated.
3. instruction.md:10-12, "they deliberately stop short of telling you the order in which the rules bind or the values of the constants". Technique: it announces that ordering must be recovered, but in this task that becomes a hidden rule; don't copy it.
4. capacity_policy.md:18-20, "that confirming pass is counted along with the passes that moved a tier". Technique: counting edge cases are written into the definition as a subordinate clause. The agent got this one, since a control (pass count) was visible to the judge.
5. dispatch_policy.md:27, "it reverses the habit of favouring the tighter deadline". This is an ANTI-example: the text explains the trap, and the agent passed it.
