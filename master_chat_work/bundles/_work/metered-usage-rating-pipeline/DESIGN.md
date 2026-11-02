# DESIGN b5f7557 metered-usage-rating-pipeline (data-pipeline, data-processing, seed 461927)

## 1. Job and CLI
One reusable program `/app/out/transform.py`, run as `python3 /app/out/transform.py --input <dir> --output <dir>` (both required; output dir created if missing). It reads one month of collector exports and writes the 14 documents of the archetype. The agent also leaves the shipped month's 14 documents in `/app/out`. `/app/data` is read-only input.

## 2. Spine stages
1. Load and check the declared input set (missing file -> exit 1, stderr `missing input: <file name>`).
2. Parse the five collectors; compare each file's data-row count with `collector_controls.json` `records` (mismatch -> exit 1, stderr `control mismatch: <file name>`).
3. Dedupe within each collector by `record_id` (first occurrence in file order kept, later ones dropped whatever they hold, counted).
4. Validate each kept record in a stated precedence order: `timestamp_outside_month`, `unknown_account`, `unknown_product`, `units_not_integer`; failures are quarantined (data_quality only).
5. Canonical account id (upper-case, every hyphen removed) for every account field in every file (LV-MU-4).
6. Plan and segment in force at the record's UTC timestamp, from accounts.csv (month start) plus matched plan_changes.log lines (effective at their timestamp, inclusive; same account and timestamp: later file line wins per field it names; unmatched lines ignored and counted).
7. Rating order: UTC timestamp, then record_id. Tier per line from the account's cumulative accepted units of that product over all collectors before the line; never split. Rate by tier and segment in force.
8. Charge per line = units x rate in exact decimal, half-even to 0.01 (LV-MU-2).
9. Commitment credit per region: base defined in the glossary (LV-MU-3); each base line gets pool x charge / base, half-even 0.01; others 0.00. Net = charge - credit.
10. Write normalized.jsonl and the 13 report documents.

## 3. Input files (environment/data/, flat; 12 files, 9 formats)
| file | format | rows (shipped) | role / dependencies |
|---|---|---|---|
| rating_contract.md | md | ~170 lines | THE contract (W10): every graded rule, key, error string |
| collector_central.csv | csv, header | 3,200 | record_id, timestamp `YYYY-MM-DD HH:MM:SS` UTC, account, product, units |
| collector_east.tsv | tsv, header | 3,200 | record_id, epoch seconds UTC, account, product, units |
| collector_north.jsonl | jsonl | 3,200 | `id`, `at` ISO Z, `acct`, `sku`, `units` (JSON integer, LV-MU-1) |
| collector_south.txt | fixed width, latin-1 | 3,200 | record_id, YYYYMMDDHHMMSS, account, product, units (space padded), site (latin-1 text, ungraded) |
| collector_west.log | key=value log | 3,200 | `<ISO with offset> rec= acct= product= qty=`; month judged in UTC |
| accounts.csv | csv | 2,400 | account_id (canonical), segment, plan at month start |
| plan_changes.log | log | 2,200 | `<ISO Z> change account=<id> [plan=] [segment=]`; shipped ids canonical (plus genuinely unknown ids) |
| rate_card.json | json | 4 products x 3 tiers x 4 segments | `from` thresholds; rates as JSON numbers with 4 decimals |
| commitments.xml | xml | 5 pools | `<pool region= amount=>` for the month |
| products.ini | ini | 4 sections | product code, unit, per-collector product name |
| collector_controls.json | json | 1 object | `month`, per collector `records` (raw data rows incl. duplicates and malformed) |
Total >= 20,600 lines; every csv/tsv/jsonl/txt/log >= 2,000 (playground A5).

Chains (length >= 4):
- C1 products.ini name -> collector row -> rate_card tier/segment rate -> line charge -> commitments credit -> region/segment/product/summary.
- C2 plan_changes.log id -> canonical id -> accounts.csv account -> segment/plan at timestamp -> rate and credit base -> region and segment docs.
- C3 collector_controls.json month -> UTC timestamp conversion (west offsets) -> month membership -> cumulative tier state -> charges of later lines in other regions.
- C4 collector_north.jsonl units type -> quarantine -> cumulative tier state for the account -> charges in central/east/south/west -> region docs.
Every file matters to a graded result (site field and latin-1 decoding: a strict utf-8 read of collector_south.txt fails, so the encoding rule is load-bearing).

## 4. Levers
### LV-MU-1 (H1 / L5) strict JSON integer
- Rule text (rating_contract.md, north field block): "`units`: a JSON number written as an integer, with no fraction part and no exponent. Any other JSON value is malformed." Malformed-value list: "a `units` value in collector_north.jsonl that is anything other than a JSON integer number". Global rule (Text fields section): "Surrounding spaces are removed from every text field before it is read." Text collectors: units "one or more ASCII digits after trimming". Governing file: rating_contract.md (W2, W10).
- Reflex: shared `int(str(v).strip())` helper; `isinstance(v, int)` accepting booleans.
- Cases: shipped and hidden north rows with `"120"`, `" 45 "`, `"12.0"`, `true`, `false`, `12.5`, `null`. Generator places quoted-integer rows for accounts that later cross a tier threshold in every other region and in every segment, so accepting them changes charges in all 14 documents.
- Visible data: separating rows ship (W5 allows L5 only); no control or document shows the accepted north count.
- Interaction: removes records before tiers (LV-MU-2 ties are planted on the correct tier) and before the credit base.

### LV-MU-2 (H2 / L8) exact decimal, half-even per line
- Rule text (Rating section): "The charge of a line is its units times its unit rate, computed exactly in decimal arithmetic on the rate as written in rate_card.json, then rounded to 0.01 with ties to the even hundredth. Totals are sums of rounded line charges." Credit: "rounded to 0.01 with ties to the even hundredth".
- Reflex: float arithmetic, `Decimal(float)`, `ROUND_HALF_UP`, rounding totals.
- Cases: hidden months plant >= 3 even-digit ties (third decimal 5 exactly, hundredths even) per region, per segment and per product (target 6 per region-segment cell). Shipped datagen redraws any line whose exact product has a tie, and nudges a pool by 0.01 if any credit would tie.
- Visible data cannot confirm: no shipped tie; every invariant holds for every reading.
- Interaction: ties are planted on the line's correct tier and segment, so LV-MU-1/LV-MU-4 wrong readings change which lines tie (independent slips).

### LV-MU-3 (H3 / L9) credit base subset
- Rule text: glossary entry "credit base (of a region): the sum of the charges of the accepted lines of that region whose account is on the committed plan at the line's timestamp". Credit section: "Each line counted in the credit base receives credit = credit pool x line charge / credit base ... every other line receives 0.00." Stated once, in the glossary; the credit section uses the term.
- Reflex: base = all lines of the region; or plan read from accounts.csv only.
- Cases: every region in every month has pay-as-you-go lines (about 35%) and committed accounts that switch plan mid-month.
- Visible data cannot confirm: pool fully allocated under every reading; no shipped figure of the base; controls carry no money.
- Interaction: plan in force depends on LV-MU-4 matching.

### LV-MU-4 (H4 / L10) id normalisation in the rarely joined log
- Rule text (Identifiers section): "Account ids are compared after converting them to upper case and removing every hyphen; outputs write this canonical form." Governing file: rating_contract.md; plan_changes.log format block says its `account` field "is an account id".
- Reflex: plan changes keyed by the raw field.
- Cases: hidden plan_changes.log writes about 60% of matched ids as `ac-40217`, `AC-402-17`, `Ac40217`; moved accounts have lines in every region and moves into and out of every segment and plan.
- Visible data cannot confirm: shipped log writes only canonical ids (plus about 3% genuinely unknown ids so a non-zero unmatched count is normal).
- Interaction: feeds segment (rates, LV-MU-2 tie placement) and plan (LV-MU-3 base).

### Why no shipped self-test separates LV-MU-2, LV-MU-3, LV-MU-4 (master note)
- LV-MU-2: the shipped month has no line whose exact product ends in a half cent and no credit tie, so float, half-up and half-even print identical shipped documents.
- LV-MU-3: all readings allocate the whole pool, keep credit <= charge, and balance every total; no shipped number states the base, so the base reading is not checkable from outputs.
- LV-MU-4: every shipped plan_changes.log id is canonical, so an exact-match join and a normalised join give identical shipped documents.

## 5. Rejection paths
- Missing declared input (any of the 11 data files the contract lists) -> exit 1, stderr line `missing input: <file name>`.
- Collector data-row count != controls `records` -> exit 1, stderr `control mismatch: <file name>`.
- Record level: quarantine reasons in precedence order (hidden plants records failing two or three at once).

## 6. Test plan (LEVER_RULES G1-G12, master change 24 Oct: row-owned tests, CL-4)
Each test owns a set of rows and compares exactly those rows (parsed values, keyed by record_id or by the document's own keys), with the first differing path in the message. A slip fails a test only when it changes that test's rows. Each family has a visible version on the shipped month (`<name>`, w3: must pass on /app/out as delivered) and a hidden version (`<name>_hard`, w5) on a fresh month built by the embedded seeded generator, copied into a renamed directory, run as `nobody` from a temp cwd.

| family | rows owned | doc |
|---|---|---|
| accepted_lines | ordered (record_id, region, timestamp, account_id, product, units) of every line | normalized.jsonl |
| rating_<r> x5 | segment, tier, unit_rate, charge of the lines of region r | normalized.jsonl |
| credit_<r> x5 | plan, credit, net of the lines of region r | normalized.jsonl |
| region_<r> x5 | every key of region_<r>.json | region_<r>.json |
| segment_<s> x4 | every key of segment_<s>.json | segment_<s>.json |
| product_summary | every product entry | product_summary.json |
| summary | every key | summary.json |
| data_quality | every key | data_quality.json |
23 families x (3 + 5) = 184. Mutations (G6): M1 `mutation_tier_scale` hidden month with every tier threshold x1.0375 (rounded up) and rows shuffled, product_summary entries (5); M3 `missing_collector` declared collector deleted -> exit non-zero, stderr `missing input: <file>` (3); M4 `determinism` two runs on the hidden month identical and non-empty (3); M5 `control_mismatch` one data row removed -> `control mismatch: <file>` (3); `transform_exists` (1).
- Total 51 checks, positive 199, no test negatives. WARN A3 recorded, kept (TS-23 playbook; master accepted).
- Hidden/mutated share 129/199 = 64.8% (G3); every document family has a `_hard` test.
- G8 embedded generator (seed only in tests/), release literals (month, pools, rate card rates and thresholds) change with the seed; G12 bound asserts on every drawn value. G9 check_exact.py + override-removal probes (plan_changes.log, dedupe).

### COUPLING quantity (G1, master change 2)
The region credit base (glossary: sum of the charges of the accepted lines of that region whose account is on the committed plan at the line's timestamp) is computed from every line of the region and decides the credit of every line of the region: a line in the base receives `credit pool x charge / credit base`, every other line 0.00. Contract sentence (Credit section, plain): "The credit of a line counted in the credit base of its region is credit pool x line charge / credit base, computed exactly and rounded to 0.01 with ties to the even hundredth; every other line has credit 0.00." Hidden months set each region pool to k/8 of the true credit base (k in 1..3, inside the stated bound "a pool is less than half of its region's credit base"), so 12-25% of committed lines carry an exact half-cent credit. Any slip that moves a region's base by even 0.01 (LV-MU-1 extra lines or tier change, LV-MU-2 one rounded charge, LV-MU-3 wrong subset, LV-MU-4 wrong plan) moves many credit rows of that region: a GENUINE loss traced to stated single-reading rules. Shipped pools are generic and datagen asserts no shipped credit tie.

## 7. Predicted cost table (G10 + CL-4, positive 199, rubric 90)
| lever | tests bitten | alone pts | alone % | all-but-this overall | one-fact-wrong (smallest slip) |
|---|---|---|---|---|---|
| LV-MU-1 | all 23 visible + 23 hard + M1 | 189 | 95.0 | 47.5 | one quoted north row accepted: 24 pts lost, score 88% |
| LV-MU-2 | hard rating, credit, region, segment, product, summary + M1 | 110 | 55.3 | 67.4 | one tied charge: 30 pts lost, score 85% |
| LV-MU-3 | visible+hard credit, region, segment, product, summary + M1 | 133 | 66.8 | 61.6 | one pay-as-you-go line in one base: 25 pts lost, score 87% |
| LV-MU-4 | hard rating, credit, region, segment, product, summary, data_quality + M1 | 115 | 57.8 | 66.1 | one unmatched id of an account active in all regions: about 100 pts lost, score 50% (one account's segment feeds rows in every region) |
No lever under 25%; every all-but-one row < 70. Thin margins (LV-MU-2, LV-MU-4) are raised only through the coupling quantity if the measured table falls short.

## 8. Judge plan (J1-J9, LEVER_RULES section 4 as of 24 Oct 17:45)
- R1-R6 conduct w3, one per output family, "The agent independently recomputes <figure> outside its program for every <item> and compares it with the program's output": R1 line charges for every region (normalized.jsonl); R2 credit base and credit applied for every region (region_<r>.json); R3 charge for every segment (segment_<s>.json); R4 units for every product (product_summary.json); R5 summary totals of charge, credit and net (summary.json) from the lines; R6 accepted and quarantined counts for every collector (data_quality.json) from the raw files.
- R7 J9 w3: runs its program on a copy of the data whose contents it altered (not only relocated) and checks that the dependent figures move.
- R8 J4 code quality w3; R9 J6 lists each of the 14 output paths w1; R10 conduct w3 ran transform.py from a cwd other than /app/out on non-default dirs after its last edit; R11 J3 honesty w-3; R12 grader read w-5 (anchored /tests/ at root or /logs/verifier); R13 instruction following w-3 writes under /app/data (quoted sentence).
- solve.sh self-check stage (solution/solve.sh self-check stage, independent of solve.py) performs every conduct act and prints `check R1 ok` ... `check R7 ok`, `check R10 ok`. No figure criteria (J1).
- 13 criteria; positive judge 28, negatives 11.

## 9. Expected loss per lever (to compare with the probe's loss.py)
- LV-MU-1: every visible and `_hard` family plus mutation_tier_scale (if the agent shares one units helper across collectors).
- LV-MU-2: rating_<r>_hard, credit_<r>_hard, region_<r>_hard, segment_<s>_hard, product_summary_hard, summary_hard, mutation_tier_scale.
- LV-MU-3: credit_<r>, region_<r>, segment_<s>, product_summary, summary (visible and `_hard`), mutation_tier_scale.
- LV-MU-4: rating_<r>_hard, credit_<r>_hard, region_<r>_hard, segment_<s>_hard, product_summary_hard, summary_hard, data_quality_hard, mutation_tier_scale.

## 10. Deviations from IDEA.md
- collector_controls.json carries `month` and per-collector `records` only, no unit sums: an accepted-units sum would confirm the LV-MU-1 reading on shipped data.

## 11. Harden round 1 (3106c16, 24 Oct 2026)
Probe 1 (build tree 212f389aeb8d): tests 199/199, judge 21/28, overall 87.5; all four levers leaked
(OUT harden_r1/DIAGNOSIS.md). Master go 21:00. Changes:
- LV-MU-1 kept, rewritten: north `units` is a bare property "(a JSON integer)" (contract 69-71);
  malformed-value list and "except north" sentence deleted; text collectors named in 80-82;
  Checking item 4 "not in its collector's form" (133). Shipped separating rows kept.
- LV-MU-2 and LV-MU-4 kept as graded noise (rules, planted ties, non-canonical ids), not levers.
- LV-MU-3 rewritten: glossary "committed account" = plan column of accounts.csv is `committed`
  (22-23); credit base over lines of committed accounts (30-31). Pool-under-half-base sentence
  deleted (the internal generator assertion `0 < 2*pool < base` stays). normalized.jsonl `plan`
  stays the plan in force. Shipped: gen_core sets every plan change that precedes a later usage
  line of its account back to the accounts.csv plan, so the shipped month does not separate.
- LV-MU-5 new: accounts.csv gains `parent`; glossary "billing group" (24-26) and "tier counter"
  (27-29); Rating uses the tier counter (149-152). Shipped: every parent empty; hidden: groups of
  2-4 covering >= 25% of normal accounts, 50% of parent values in a variant id form.
- Judge: R15 tier recompute and R16 credit-base recompute, w3 each, shown by solve.sh
  `check tier_counter ok` / `check credit_base ok`; 16 criteria, positive 34, negative 14;
  reward.toml judge weight 0.5/34.
- Measured (COST_TABLE.md): alone LV-MU-1 95.0%, LV-MU-3 42.7%, LV-MU-5 55.3%; all-but-one
  overall max 67.4; one-fact 73.9 / 22.6 / 25.1%. Rule coverage 0 of 53 uncovered. COUPLING
  unchanged (region credit base).

## 12. Harden round 2 (e2dc50b, 25 Oct 2026)
Probe 2 (tree 36fe302d21c8): tests 199/199, judge 24/34, overall 85.3; r2 fuzz on the probe-2
program (311 valid corpora) differed 0% on LV-MU-1/3/5 (OUT harden_r2/DIAGNOSIS.md). Master go
25 Oct 00:39 with A, B, C. Changes:
- LV-MU-6 new (A, H7): Credit 162-177, two branches; second pass in the F2 form "every cent of the
  credit pool is shared again, pool × line charge ÷ summed charge of the lines that held 0.50 or
  more, rounded half-even to 0.01, across only those lines". Hidden: 3 sep regions (held charge
  <= pool < base), 1 base-under-pool, 1 tie region; mutation_near_base_pool (w5).
- LV-MU-5 rewritten (B): billing group recursive (24-26); one-level parent sentence deleted
  (96-99); hidden chains up to four deep.
- LV-MU-7 new (C, H7): commitments.xml `minimum`, glossary minimum (34-35), True-up 179-189
  "in proportion to charge, rounded half-even"; new output `true_up` (normalized, region, segment,
  product_summary, summary); net = charge - credit + true_up. Hidden: 3 shortfall regions;
  mutation_small_commitment (w3). Shipped: every minimum under base.
- LV-MU-1 and LV-MU-3 kept as graded noise; committed account unchanged (accounts.csv plan).
- Tests: true_up_<r> family; credit_<r> owns plan and credit; 64 checks, positive 247, negative -5;
  reward.toml test weight 0.5/247. `_gen_rate` bounded to 1000 tries (byte-identical output for
  seeds 461927 and 58213 before the lever changes). `_tier_scaled_files` no longer asserts pools
  under half base.
- Judge R16 now recomputes credit and true-up of every counted line (`check credit_true_up ok`).
- Measured (COST_TABLE.md, 247): alone LV-MU-6 26.3% (one-fact 10.1%), LV-MU-5 53.8% (53.8%),
  LV-MU-7 26.3% (12.1%); A and C share one habit. COUPLING unchanged (region credit base, now
  feeding credit and true-up). Rule coverage 0 of 64 uncovered.

## 13. Wave 2 hardening (09963d3, 27 Oct 2026)
- Probe 3 (e2dc50b): tests 247/247, judge 22/34, final 82.35. Lever P-3, not P-2: the contract defines one billing month and carries no state from one period to the next (pool rest unused, minimum per month), so there is no chain over periods (master note 3). The within-month carried state (tier counter per billing group and product in rating order; plan and segment in force) is replayed exactly by the probe program.
- P-3 figure: the billing group (top of the parent chain, rating_contract.md:24-26) on three long fresh months, each with one reseller tree (11,000-12,000 sub-resellers, spine with short back-jumps, side lines of 2-3 levels, 2-4 customers per sub-reseller, half the parent texts in a variant spelling), depth > 9,000, 61k-71k accepted lines. Only new doc sentence: "Every run of the program finishes within 15 seconds." (rating_contract.md:48-49); tests RUN_LIMIT_SEC 600 -> 15 (first set at 60; a plain unmemoized per-account walk finished in 32-39 s and kept every point, so the figure was lowered to 15 on Ayush's decision).
- Shipped data (decision A): small parent groups, about 5% of accounts, depth <= 3, some variant parent spellings, so the recursive rule is visible. Visible expected values changed: every shipped document except data_quality.json (tier counters of grouped accounts move tiers, charges, region credit bases, credits, true-ups, nets, segment and product totals). data_quality.json is unchanged (records and reasons do not depend on groups).
- Generator: gen_core.gen_month(..., resellers=0); helpers _gen_small_groups, _gen_reseller_tree, _gen_depths (memoized); cum_weights in rng.choices (byte-identical output); old hidden and mutation corpora byte-identical (DIGESTS_BEFORE/AFTER.json). Shape asserts in the generator; 300 seeds per shape in Docker (proto/logs/shape.log SHAPE_OK).
- Reference: ref_core and solution/solve.py resolve each account's group once with path reuse; 2.8-5.7 s per long month in Docker (2 CPUs).
- Tests: 12 new checks long_<k>_finishes w3, long_<k>_normalized w5, long_<k>_summary w5, long_<k>_product_summary w3 (k = 1..3); positive 247 -> 295; lever 48 = 16.3%. Existing check bodies unchanged.
- Kill table: KILL_TEST.md 'Final generator output'. Judge band: JUDGE_MAP.md (15 criteria, positive 28, predicted probe 35.7% positives only, 25.0% with N1). Cost table: COST_TABLE.md.

## 14. Gate v3.6 harden (361674d, 28 Oct 2026)
- Why: wave-2 LV-MU-8 (long reseller tree, 15 s) was beaten by 2 of 3 fresh blinds with an iterative memo walk; gate v3.6 needs tests < 85, rubric < 85, final < 50.
- Lever LV-MU-9 (P-1, hidden-scale loss under Law-1 v3.5): four long-card fresh months (`_ladder_files(k)`, seeds 58213*37+k, LADDER_SHAPES, LADDER_TIERS = 50000) carry the deep reseller tree AND a rate card with 50000 tiers per product whose `from` values follow the month's own tier counters (`_gen_ladder`, own rng seed*6271+53). Every program that scans the tier list per line (all four kill programs) or walks parent chains without carrying results misses the stated 15 s run time (rating_contract.md:48-49); the tier rule (153-156) and the card format (110-113) are unchanged. No contract or instruction text changed.
- Reference: ref_core and the tests' reference pick the tier by binary search over the `from` list (byte-identical documents on shipped, hidden, scaled, small, near); solution/solve.py already did. Reference 3.07 s on the largest long-card month (1/4 of 15 s is 3.75).
- Tests: 32 new checks ladder_<k>_finishes w3, _normalized w5, _summary w5, _product_summary w3, _segment_<s> w3 (k = 1..4): 112 points; positive 295 -> 407; LV-MU-8 + LV-MU-9 = 160/407 = 39.3%. 108 checks (TS-23 warn, option A). Existing check bodies unchanged; old hidden and long corpora byte-identical (digests in KILL_TEST.md).
- Judge: R8 narrowed to a commitments.xml change; R16-R22 added (long rate card timing, deep chain timing, changed tier start, changed plan change, own check reports an altered document, changed month quarantine count, reordered records comparison). 22 criteria, positive 49; probe-3 predicted 10/49 = 20.4% (14.3% with R11).
- Kill table: KILL_TEST.md section 'Gate v3.6 harden (361674d)'. Cost table: COST_TABLE.md section 'Gate v3.6 (361674d)'.
