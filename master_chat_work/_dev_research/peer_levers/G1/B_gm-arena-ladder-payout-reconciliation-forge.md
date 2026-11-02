# B: gm-arena-ladder-payout-reconciliation-forge

All paths are relative to the task folder unless stated. `_scratch` = `OUT/_scratch` (my local reproduction).

## 1. Inventory
- Domain: game-economy settlement (survey weighting, calibration, weighted metrics, credit payout, levy).
- Archetype: recompute a rejected multi-stage settlement from a data dump and write 29 deterministic artifacts under `/app/out` (CSV/TSV/PSV/JSON/JSONL/MD/XML plus a digest manifest). Graded on outputs only; no program is run by the tests.
- Agent-visible files: 59 files in `environment/data` (from `ls -la`), about 1.26 MB in total. Largest: `ladder_match_capture_s1.csv` 77.9 KB (988 rows, step 15), `match_trace_index.db` 49 KB, `settlement_checkpoints.ndjson` 33 KB, `verdict_amendment_history.tsv` 36 KB. 9 tiny stage specs (`spec_stage_s1..s9_*.md`, 360-752 B each), `output_artifact_schemas.md` 6.2 KB, and three binary carriers of constants (`ladder_tuning_grid.xlsx`, `payout_cost_policy.pdf`, `settlement_levy_addendum.docx`). There are many decoys (`levy_floor_decoy_table.csv`, `calibration_legacy_multipliers.csv`, and stub "worked example" files with no values: `sample_worked_records.jsonl` rows are `{"match_key":..., "note":"reference worked example - see specs"}`).
- instruction.md: 785 words.
- Tests: 22 positive checks totalling 62 and 1 negative (-5) (`tests/test_output.py` L1992-2140). Weights: 5 x6 (population, weights, metrics_json, per_stratum, payout, levy_summary), 3 x8, 1 x8.
- Isolation: none. Every check is one whole-file byte compare, so a stage-k error fails every file downstream of k.
- Hidden or reseeded inputs: **no**. `_expected()` regenerates only `SAMPLE_SEED` (L1813, L1838), which I proved byte-identical to the shipped data. 100% of test weight is on shipped-data-only checks.
- Judge: 33 criteria (28 positive totalling 106, 5 negatives at -5), mode `batched`, model `openai/gpt-5.6-sol`, atif trajectory (`tests/judge.toml` L1-6).
- Reward split: `reward.toml` test 0.0080645 = 0.5/62, judge 0.0047170 = 0.5/106, so 50/50.

## 2. Rule map (graded rules; S-stage specs are the main carriers)
| Rule | Where stated | Form | Trap explained? | Shipped data separates readings? |
|---|---|---|---|---|
| R-key: economic key = account/hero/seed/split, not per-attempt uid | `spec_stage_s1_canonicalization.md`; `known_traps_and_footguns.md:3` ("match_uid is per-attempt; the key is account\|hero\|seed\|split") | one plain sentence, repeated | yes, in footguns | yes (agent passed) |
| R-anchor: first attempt anchors | S1/S2 spec; footguns:4 | plain sentence | yes | yes (passed) |
| R-verdict order by review_seq, 40-day window, crosswalk held/unmatured excluded | `spec_stage_s2_anchoring_verdicts.md`; footguns:5; instruction.md para 4 | plain + repeated | yes | yes (label_distribution passed) |
| R-baseline S3 running baseline per stratum | `spec_stage_s3_running_baseline.md:3` | plain | n/a | feeds weights.csv |
| R-units S4 exponents + ORE gain from live xlsx sheet | S4 spec; footguns:10; `unit_scale_exponents.json`; xlsx | split across files plus a binary | yes ("ORE gain is spreadsheet-only") | agent got it right (step 9 finds 0.0371) |
| **R-nonresp S5: nonresponse factor = sampled / resolved per SERVER, with "resolved" meaning resolved among the drawn sample** | `spec_stage_s5_two_level_weights.md:3-7`: "Only matches that are resolved AND drawn (`drawn=1`) carry a weight. ... The nonresponse factor is sampled count over resolved count per SERVER - a DIFFERENT partition"; instruction.md para 7 ("documented and different partitions"); footguns:6 ("Weight partitions differ (frozen stratum vs server)") | **implied by a definition**: the drawn-only scope sits in the sentence before it (who carries a weight) and in survey convention. The factor sentence itself says only "resolved count". | The *partition* trap (stratum vs server) is explained 3 times. The *scope* trap (drawn only) is not. | yes: 140 resolved vs 91 resolved-and-drawn (agent step 25 prints "resolved 140 weighted 91"), but there is no reference value, so nothing shows which reading is right |
| R-trim: inflate then trim to cap 240 with mass preserving | S5 spec:7-9; footguns:7 | plain | yes | **no**: max weight 5.245614 (`_scratch/gm_expected/weights.csv`), so the cap never binds |
| R-residue: residue to largest weight, ties by smallest match_key | S5 spec:9-11; `weighting_constants.json`; `rounding_and_precision.yml` | plain, repeated | n/a | passed implicitly once fixed |
| R-calib log-odds, inclusive >= threshold | S6 spec; footguns:8-9; `threshold_semantics.xml` | plain, repeated | yes | decision_distribution passed |
| R-metrics ratio of weighted totals, macro = weight-share mean | S7 spec; instruction para 9 | plain | n/a | yes |
| **R-payround S8: half-even rounding per match term, then sum** | `spec_stage_s8_uncertainty_payout.md:6-10` ("Rewarded credits count true positives times the per-stratum recovery factor ... The review unit cost (PDF only) is charged per flagged match, weighted ... Round half-to-even at each stage."); `rounding_and_precision.yml` (`payout_rounding: half_even_at_each_stage`) | **implied**: "per flagged match" plus "at each stage". "Stage" is ambiguous (pipeline stage S8, or each arithmetic step). | no | yes in value (off by 1-4 credits per stratum), but no reference value |
| R-shares largest remainder, tie by smaller stratum name | `unit_test_vectors.json` has the method (amounts [10,20,70] -> bps) with **no tie-break**; the tie-break appears in no agent-visible file (grep, see A §4) | HIDDEN for the tie-break | no | not separable (hidden behind the rounding diff) |
| R-levy: DOCX-only levy 640 bps, then floor 500 | S9 spec; footguns:13; docx | split into a binary | yes | agent got it right (step 11) |
| R-digest over 4 core files in order | `digest_specification.md` | plain | n/a | manifest fails only through the cascade |

## 3. Lever table (failed checks and criteria)
Test levers (proved by counterfactual: `_scratch/gm_agent_settlement.py` reproduces all 29 agent outputs byte for byte; `_scratch/gm_fix_settlement.py` patches only R-nonresp):

| id | w | rule | agent reading | correct reading | mechanism | self-test on shipped data catches? | fully stated? | family |
|---|---|---|---|---|---|---|---|---|
| test_weights_exact | 5 | R-nonresp (+ cascade) | agent code (step 22, L257-274): `for rec in resolved.values(): resolved_by_server[rec["server"]] += 1`, i.e. every resolved match | oracle `tests/test_output.py` L1457-1472 counts only resolved rows with `drawn == "1"` | Scope by omission inside a definition. The spec spends its emphasis on the partition (stratum vs server, in caps, plus a footgun), and the agent got that right. The scope qualifier is one sentence earlier, attached to a different noun ("carry a weight"). | **N**: no reference numbers anywhere (worked-example files are stubs). Both readings give plausible weights (2.29 vs 3.43). | RISKY: derivable from S5 L3 plus survey meaning, but the factor sentence alone is ambiguous (IN-16 exposure) | A hidden composition (scope of one rule set by a neighbouring rule) |
| metrics_json, per_stratum_metrics, stratum_metrics_stream, weight_diagnostics, levy_summary, audit_summary, overall_metrics_md | 5,5,3,1,5,1,1 | cascade of R-nonresp | as above | — | whole-file byte compare of downstream documents | N | — | B dependent chain |
| payout, payout_breakdown, payout_ledger, net_payout_summary, forfeited_shares, reconciliation_report, rollup, manifest | 5,3,3,3,3,1,1,3 | R-payround (+ R-nonresp cascade) | agent L380-398: `rewarded[s] = rhe(rew * recovery)`, `review[s] = rhe(sum(w ...) * review_cost)`, so it rounds once per stratum | oracle L1569-1586: `rewarded += qint_even(wunit * rec_factor)`, `review += qint_even(review_cost * w)` for each match, then rounds the sums | Rounding granularity is implied by "per flagged match" and an ambiguous "at each stage". The differences are 1-4 credits (expected BRONZE-NA net 847671936 vs fixed agent 847671933). | **N**: a sum-then-round gives a self-consistent ledger, and there is no reference | RISKY to NOT ALLOWED (IN-16: two defensible readings of "stage") | NEW: rounding granularity |

Total test points lost 48/62: 26 from R-nonresp alone, 22 from R-payround (on top of the cascade).

Judge levers:
| id | w | what it grades | why failed | fair? |
|---|---|---|---|---|
| R24 | 3 | largest-remainder tie-break by smaller stratum name | agent ties by fixed STRATA order (code L411) | HIDDEN RULE, tie-break not in any file. Not allowed. |
| R13 | 5 | shows that reordering changes p_eff | no demo | conduct preference at w5: JD-15 fail |
| R14 | 5 | demonstrates the thousandfold unit error | no demo | same |
| R18 | 5 | shows trim totals equal | no weight reaches the cap, so nothing to show | RISKY under JD-7 (vacuous on the shipped data) |
| R15 | 3 | keeps a drift-gap match in metrics, drops it from payout | judge: no gap row exhibited | outcome. The test already pays for it (JD-8 overlap) |
| R26 | 3 | attributes the lower recall to the 40-day window (`reviewer_faq.md`) | agent never compared with the rejected run | fair (stated in the FAQ) |
| R25 | 3 | explains a digest change | not explained | conduct, mild |
| R6, R1 | 3, 1 | names the file for each reading; confirms each path | reporting gaps | fair (instruction says to report) |
| R33 | 3 | code quality (JD-18) | one main function, no error handling around the binary parsers | fair |

## 4. Contrast: what the agent passed and why it was easy
- Passed population, label/decision distributions, frame_counts, confidence_intervals. Each of those rules is one capitalised sentence repeated in `known_traps_and_footguns.md` (11 numbered footguns that name every trap). That is exactly our leaked-lever pattern (DIAGNOSIS cause 4: "every rule one explicit sentence, the trap spelled out").
- Binary-only constants (xlsx/pdf/docx) did not cost anything. The agent opened every binary in steps 7-11 with stdlib zip/xml and regex. "Constants hidden in a binary" is a reading chore, not a lever.
- Decoy tables (`levy_floor_decoy_table.csv`, legacy multipliers) did not catch it, because the footguns file names them as superseded.
- The two rules it missed are the only two whose decisive qualifier is **not** in the footgun list and **not** in caps.

## 5. Agent behaviour (trajectory, 35 steps, about 14 min, $2.68)
- Read order: step 2 ls; step 3 cat overview, readme and all 9 stage specs; step 4 schemas; step 5 glossary, footguns, ordering, rounding, digest; step 6 data heads; steps 7-11 binaries; steps 12-21 probes (988 rows, 349 sealed, 140 resolved). It read every spec fully.
- Plan: implicit. Step 22 writes a 596-line `/app/settlement.py` in **one write**. Step 23 makes a small edit (inclusive threshold). Step 24 crashes on a regex. Step 25 fixes it and runs.
- Self-tests: none against independent data. Steps 26-31 only eyeball outputs (a TKN drift row, ORE rows). It never recomputed a weight by hand and never questioned the nonresponse denominator.
- It never noticed either error. The final message (step 34) claims every stage was read and applied per the contract.

## 6. Test design
- Expected values: an oracle at test time (the in-test reference pipeline over the regenerated shipped seed).
- Partial credit only by file. No tolerance (byte exact).
- Negative: `negative_probability_space_calibration` (-5) fires if weights.csv equals the probability-space calibration variant. This is a *wrong reading*, not a cheat. TS-16 asks "could an honest solution trip this?", and an honest agent that misreads S6 would, so RISKY.
- Downstream documents graded whole: yes, 16 of 22 positives are downstream of S5.
- Shipped-data-only weight: 100%.

## 7. Judge design
- Failed criteria and reasons are in §3. Reusable pattern: R26 ("notices that the corrected figure lands below the rejected one and attributes it to rule X per file Y"). That is a fair outcome-of-understanding criterion when the FAQ states the cause.
- Breaks: R24 (JD-15 outcome criterion resting on an unstated tie-break; IN-15). R13/R14 (JD-15: "a preference weighted 5 is a fail"). R18 (JD-7: the oracle cannot demonstrate a trim that never binds on the shipped data). R15 (JD-8 overlap with the payout/metrics byte tests).

## 8. QC safety of the working levers
| lever | IN-15 | IN-16 | TS-16/19/20 | AL-28 | verdict |
|---|---|---|---|---|---|
| Scope qualifier carried by a neighbouring definition (R-nonresp) | stated (S5 L3) | exposed: "resolved count" alone has two readings. Fix: make the definition unambiguous in a glossary entry that is not next to the formula. | TS-19 ok if the glossary defines it | n/a | **RISKY** (safe if the definition is written explicitly somewhere, e.g. a glossary "resolved count = resolved members of the drawn sample") |
| Rounding granularity per item vs per group | "at each stage" is vague | two defensible readings: fail | TS-19 risk | n/a | **NOT ALLOWED as written**. SAFE if the spec says the unit of rounding explicitly, e.g. "each match's credit is rounded before summing". The lever then becomes "the agent must apply it at the right granularity across 3 terms". |
| Whole-file cascade (B) | n/a | n/a | TS-20 weights fine; TS-26 double-payment risk (one error paid 16 times) | n/a | RISKY: it amplifies a lever but is not one itself |
| Wrong-reading negative | n/a | n/a | TS-16 risky | single -5, no stack | RISKY |

## 9. Writing style (how a rule is stated without giving the trap away)
1. "Only matches that are resolved AND drawn (`drawn=1`) carry a weight." (`spec_stage_s5_two_level_weights.md:3`). Technique: state the scope once, as a property of the *output set*, and let the later formula's denominator inherit it silently.
2. "The nonresponse factor is sampled count over resolved count per SERVER - a DIFFERENT partition" (S5:5-6). Technique: a loud decoy emphasis (the partition) draws attention away from the quiet qualifier (the scope).
3. "The review unit cost (PDF only) is charged per flagged match, weighted." (S8:8-9). Technique: the per-item unit is carried by a preposition ("per flagged match"), not by a rounding rule.
4. Anti-example: `known_traps_and_footguns.md` lists every other trap by name, and the agent passed all of those.
