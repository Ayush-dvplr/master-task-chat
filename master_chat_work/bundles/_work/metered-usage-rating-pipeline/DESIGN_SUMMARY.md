# DESIGN_SUMMARY b5f7557 metered-usage-rating-pipeline (data-pipeline, seed 461927)
Job: one reusable `/app/out/transform.py --input <dir> --output <dir>` rates a month of metered usage from 5 regional collectors and writes the 14 archetype documents; shipped month 2026-09.
Contract (W10): every graded rule in `environment/data/rating_contract.md`; instruction states the job, 14 paths, whole-doc exactness on fresh months, arbiter sentence, no rule.

Inputs (12 files, 9 formats, ~20.6k lines): rating_contract.md; collector_central.csv, collector_east.tsv (epoch), collector_north.jsonl, collector_south.txt (fixed width, latin-1), collector_west.log (key=value, ISO offsets, month in UTC); accounts.csv (2,400); plan_changes.log (2,200); rate_card.json (3 tiers x 4 segments x 4 products); commitments.xml (pool per region); products.ini (per-collector product names); collector_controls.json (month + raw row counts, honest L1 control).
Chains: products.ini->row->rate->charge->credit->reports; plan_changes id->canonical->plan/segment at ts->rate+base->reports; controls month->UTC->membership->tier state->other regions; north units->quarantine->tier state->other regions.

| lever | habit | rule written in rating_contract.md | hidden case | shipped separates? |
|---|---|---|---|---|
| LV-MU-1 | H1/L5 | north field block + malformed list: units JSON integer only; global trim rule for text | quoted ints, "12.0", true/false, 12.5, null on accounts crossing tiers later | yes (L5 only) |
| LV-MU-2 | H2/L8 | Rating: exact decimal on rate as written, half-even 0.01 per line, totals of rounded | >=3 ties per region/segment/product | no tie shipped |
| LV-MU-3 | H3/L9 | glossary once: credit base = committed-plan lines at line ts in region | ~35% payg + mid-month switches every region | pool fully allocated either way |
| LV-MU-4 | H4/L10 | Identifiers: upper-case + remove hyphens; plan_changes account "is an account id" | ~60% of matched log ids mixed case/hyphenated | log canonical only |

Why no shipped self-test separates LV-MU-2/3/4: no shipped half-cent product or credit tie; every base reading balances and allocates the pool, no output states the base check; canonical ids make raw and normalised joins identical.
Noise (not levers, each with a RULE_COVERAGE mutant): latin-1 south, dedupe by record_id (first kept), validation precedence, west offsets.
Deviation from IDEA: controls carry no unit sums (a sum would confirm LV-MU-1 on shipped data).

Tests (row-owned, per master change 1; 51 checks, positive 199, no test negatives; WARN A3 kept):
- 23 families, each owning its rows, exact equality, first differing path: accepted_lines; rating_<r> x5 (segment, tier, unit_rate, charge); credit_<r> x5 (plan, credit, net); region_<r> x5; segment_<s> x4; product_summary; summary; data_quality. Visible `<name>` w3 on shipped /app/out; `<name>_hard` w5 on a fresh hidden month (embedded seeded generator, renamed dir, run as nobody from temp cwd).
- M1 mutation_tier_scale w5 (thresholds x1.0375, shuffled); M3 missing_collector w3; M4 determinism w3; M5 control_mismatch w3; transform_exists w1. Hidden/mutated share 64.8% (G3).
COUPLING (change 2): region credit base (glossary) decides every line's credit in its region; hidden pools = k/8 of the true base (k 1..3, inside "less than half") so 12-25% of committed lines carry exact half-cent credits.

Predicted cost table (G10 + CL-4, rubric 90; one-fact-wrong = score with one wrong fact of that lever):
| lever | alone % of test pts | all-but-this overall | one-fact-wrong score |
|---|---|---|---|
| LV-MU-1 | 95.0 | 47.5 | 88% |
| LV-MU-2 | 55.3 | 67.4 | 85% |
| LV-MU-3 | 66.8 | 61.6 | 87% |
| LV-MU-4 | 57.8 | 66.1 | 50% (one unmatched id of an account active in all regions) |
Weakest: LV-MU-2 and LV-MU-4; strengthened only through the coupling quantity if measured short. Kill-risk swap: H5/H6.

Judge (13, change 4): R1-R6 conduct w3 'independently recomputes ... for every region/segment/product/collector' (line charges, credit base+applied, segment charge, product units, summary totals, collector counts); R7 J9 altered-content copy w3; R8 J4 code quality w3; R9 J6 lists 14 paths w1; R10 foreign-cwd run after last edit w3; R11 J3 honesty w-3; R12 grader read w-5; R13 instruction following /app/data write w-3. selfcheck.py prints `check R<n> ok`.
Files: WORK/PREMORTEM.md, WORK/DESIGN.md, WORK/QC_DEFENCE.md.
