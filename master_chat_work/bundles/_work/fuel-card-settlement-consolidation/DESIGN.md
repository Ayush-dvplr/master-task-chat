# DESIGN: fuel-card-settlement-consolidation (board 60e9db0)

Shape B (breadth). Sources: S1 primary (42 stated rules, 23 files, 9 formats), S5 partial-authority decoy (2023 standard, one live clause), S6 hidden-only fixtures for 15 quiet stated branches. Levers used as building blocks: L4 (multi-doc composition), L7 (per-line rounding stated in the standard), L8 (half-even with planted ties), L6 (scope by defined term: "tier volume"), L3 (stateful monthly cap), L10 (normalisation in a rarely joined field: card holder by date). Habits targeted: H8, H9, H6, H3, H2. File:line for every rule is filled into RULE_TRACE.md in Phase 2, when the documents exist; the section named here is where the sentence goes.

COUPLING (G1): the account's tier, earned by whole-month tier volume across all five processors, is carried into every ledger row (`tier`, `discount_amount`, `settled_amount`) and so into summary, product, region and segment totals. Contract sentence (group_standard.md, section "Discount"): "Every settled amount uses the discount tier earned by the account's whole-month settled volume across all processors."

## 1. Spine

1. Read processors.json (export file, format, field layout, settlement month).
2. Parse each export with its handbook's conventions into a common record (quantity unit, amount basis, sign, reversal reference, pump-test marker, timestamp zone).
3. Batch status from batches.log (latest event per batch).
4. Resolve site (region, offset, jurisdiction), business date, card holder, account segment, product (alias, kind, tax class, unit).
5. Reject in the stated reason order; duplicates; resubmissions; voids.
6. Pair reversals with originals across all exports.
7. Tier volume per account (all processors, sales minus reversals, fuel only) -> tier -> per-line discount with the monthly cap applied in ledger order.
8. Tax per line (inclusive extraction or exclusive computation), half-even per line.
9. Write normalized.jsonl and the 13 report documents from the ledger rows.

## 2. Input files (23 files, 9 formats)

| # | path | format | rows (shipped) | read by stage | depends on |
|---|---|---|---|---|---|
| 1 | docs/RULES.md | md | ~60 | all | register: names every governing file, the precedence sentence, values that change between months (W12) |
| 2 | docs/group_standard.md | md | ~170 | 4-8 | current standard (2026), carried-forward section names 2023 section 7 |
| 3 | docs/group_standard_2023.md | md | ~120 | 2 (CNG only) | header: superseded by the 2026 standard except what it carries forward |
| 4 | docs/reference_data.md | md | ~90 | 3-4 | conventions of every ref/ file |
| 5 | docs/output_schema.md | md | ~140 | 9 | every output key, value form, order, reason string |
| 6-10 | docs/handbook_{kestrel,lumen,marlow,norvik,oberon}.md | md | ~50 each | 2 | one per processor |
| 11 | ref/processors.json | json | 5 objects | 1-2 | export path, format, lumen fixed-width layout, `home_region` (look-alike), settlement_month |
| 12 | ref/sites.csv | csv | 2,400 | 4 | site_id, region, utc_offset, jurisdiction |
| 13 | ref/cards.csv | csv | 2,600 | 4 | card_number, account_id, valid_from, valid_to |
| 14 | ref/accounts.csv | csv | 2,200 | 4,7 | account_id, segment, effective_from, closed_on |
| 15 | ref/products.xml | xml | ~14 products | 4,7,8 | code, kind, tax_class, unit, per-processor alias |
| 16 | ref/discount_tiers.ini | ini | ~30 lines | 7 | eligible segments, tier floors and rates, monthly cap per segment |
| 17 | ref/tax_rates.tsv | tsv | 2,100 | 8 | jurisdiction, tax_class, rate, effective_from |
| 18 | ref/batches.log | log | 2,050 | 3 | timestamp processor batch EVENT [batch] |
| 19 | exports/kestrel_settlement.csv | csv | 2,300 | 2 | |
| 20 | exports/lumen_settlement.txt | txt (fixed width) | 2,300 | 2 | layout in processors.json |
| 21 | exports/marlow_settlement.jsonl | jsonl | 2,300 | 2 | |
| 22 | exports/norvik_settlement.xml | xml | ~2,300 records | 2 | |
| 23 | exports/oberon_settlement.tsv | tsv | 2,300 | 2 | |

Total about 25,000 lines (A5: every csv/tsv/jsonl/txt/log file >= 2,000 lines). Every file feeds a graded value (the 2023 standard through CNG lines, RULES.md through precedence; processors.json through the layout and month).

Chains of length >= 4:
- C1 export row -> cards.csv (holder on business date) -> accounts.csv (segment in force, closed_on) -> discount_tiers.ini (eligibility, tier, cap) -> discount_amount.
- C2 export row -> sites.csv (offset, jurisdiction, region) -> business date -> tax_rates.tsv (rate in force for jurisdiction x tax class from products.xml) -> tax_amount.
- C3 export row -> processors.json (file, layout) -> batches.log (latest event) -> duplicate / resubmission resolution -> ledger membership -> tier volume.
- C4 export product code -> products.xml alias -> unit `kg` -> group_standard.md carried-forward section -> group_standard_2023.md section 7 factor -> litres -> tier volume.

## 3. Rule register (42 graded rules)

Q = quiet on shipped (fires only on hidden corpora). Wrong reading = PREMORTEM first fit. "Visible cannot confirm" = no answer is shipped (W11) and, for Q rules, the branch never fires on shipped.

| id | governing file / section | rule (plain sentence, final wording in Phase 2) | Q | wrong reading (habit) | hidden construction |
|---|---|---|---|---|---|
| R01 | group_standard / Dates | Business date = calendar date of the dispense instant at the site's UTC offset (sites.csv). | | export's own date; UTC date (H8) | every corpus, many rows 20:00-04:00 local |
| R02 | group_standard / Scope | Only lines whose business date falls in the settlement month settle; others are rejected `out_of_period`. | | | far-off dated rows (both readings agree) |
| R02b | same sentence | (boundary) a dispense at 23:xx local on the last day that is next day in UTC settles; mirror at day 1. | Q | UTC or export date filter (H8, H9) | 3+ rows per boundary per hidden corpus, own RNG |
| R03 | group_standard / Attribution | A line's region is its site's region in sites.csv, whatever processor settled it. | | processors.json `home_region` (H8) | processors settle sites in all regions |
| R04 | group_standard / Attribution | A line's account is the card's holder on the business date (cards.csv validity, both ends inclusive, blank valid_to open); no holder -> `unknown_card`. | | | |
| R04b | same | card reassigned mid-month: lines before/after go to different accounts. | Q | last or first card row (H8) | 2+ cards per corpus |
| R05 | reference_data / accounts | The segment is the accounts.csv row with the latest effective_from on or before the business date. | | first row (H8) | history rows before the month |
| R05b | same | segment change mid-month. | Q | last row (H8) | 2+ accounts per corpus |
| R06 | group_standard / Products | A line's product is the products.xml product whose alias for that processor equals the export code; no match -> `unknown_product`. | | match on product code across processors | |
| R07 | group_standard / Quantities | Litres = quantity converted to litres, rounded half-even to 3 decimals, once per line. | | round after summing (H2) | |
| R08 | group_standard / Products | Non-fuel lines (kind nonfuel, including litre-measured AdBlue) carry litres 0.000, no discount and no tier volume. | | AdBlue counted as volume (H3) | |
| R09 | reference_data / tax_rates | Rate = row for the site's jurisdiction and the product's tax_class with the latest effective_from on or before the business date. | | | |
| R09b | same | rate change mid-month. | Q | latest row overall (H8) | 2+ jurisdiction changes per corpus |
| R10 | group_standard / Tax | Tax-inclusive amounts: net = gross / (1 + rate) rounded half-even to cents; tax = gross - net. | | tax = gross x rate | |
| R11 | group_standard / Tax | Tax-exclusive amounts: tax = net x rate rounded half-even to cents. | | | |
| R12 | group_standard / Rounding | Every rounding in the standard is half-even, per line, before any total; totals are sums of rounded lines. | | half-up / float round (H2) | >= 3 planted ties per corpus (shipped too, both readings reconcile no control) |
| R13 | group_standard / Discount | Tier volume = account's fuel litres over all processors, sale lines minus reversal lines, rejected lines excluded (COUPLING sentence). | | per processor (H3) | accounts split across 2-4 processors |
| R14 | discount_tiers.ini + standard | Tier = highest tier whose floor is at most the tier volume. | | | |
| R14b | same | volume exactly on a floor. | Q | `>` floor (H8) | 2 accounts per hidden corpus |
| R15 | group_standard / Discount | Discount = litres x tier rate, half-even to cents, per fuel line; ineligible segments (ini `eligible`) get tier `none`. | | | |
| R16 | group_standard / Discount cap | An account's month discount stops at its segment cap (ini); lines are discounted in ledger order; the line that crosses gets the remainder; later lines 0.00. | Q | uncapped, or cap applied to total (H6) | 2+ accounts per corpus over cap |
| R17 | group_standard / Reversals | A reversal is a ledger row with entry `reversal` carrying the negative of each amount and litres of its original and the original's account, site, product, tier; its own business date. | | own card / own site lookup | |
| R18 | group_standard / Reversals | A reversal reverses its original wherever it was settled; the reference names another processor as `<processor>:<id>`. | Q | own export only (H8) | 2+ per corpus |
| R19 | group_standard / Reversals | A reversal whose original is not among the month's settled sale lines is rejected `orphan_reversal`. | | | |
| R19b | same | original exists but was itself rejected (superseded, out of period). | Q | match raw record (H8) | 2 per corpus |
| R20 | group_standard / Duplicates | Two surviving lines with the same ledger_id: the one from the batch logged first in batches.log stays; the other is rejected `duplicate`. | | keep last | |
| R21 | reference_data / accounts | A line dated after the account's closed_on is rejected `account_closed`. | Q | ignored (blank on shipped traders) | 2+ per corpus |
| R22 | group_standard / Settled | settled = net + tax - discount. | | net - discount then tax on discounted net | |
| R23 | reference_data / batches.log | A batch's status is its latest event: SUPERSEDED or WITHDRAWN rejects its lines `superseded_batch` / `withdrawn_batch`. | | | |
| R23b | same | WITHDRAWN then REINSTATED: lines settle. | Q | any WITHDRAWN final (H6) | 2 batches per corpus |
| R24 | output_schema / rejection order | A line with several reasons is rejected for the first in the stated order. | | | rows carrying 2 reasons |
| R25 | reference_data / sites | Offsets are fixed (no daylight saving), sign as written. | | | |
| R26 | group_standard / Ledger | ledger_id = `<processor>:<source id>`; lumen lines append `-<line_no>`; oberon tenders append `/<tender>`. | | | |
| R27 | group_standard_2023 s7 (live via group_standard carried-forward) | CNG quantity is kilograms in every export; one kilogram counts as F litres (F re-rendered per month). | Q | ignore 2023 file; read kg as handbook unit (S5) | CNG lines on 2 processors per corpus |
| R27d | group_standard_2023 dead sections | half-up rounding, tier by transaction count | | following the decoy's dead rules | graded on shipped (R12, R13) |
| R28 | handbook_kestrel | Timestamps UTC (`Z`); quantity litres; amount tax-inclusive dollars. | | | |
| R29 | handbook_kestrel | Type `REV` = reversal, positive values, `orig_txn` reference; type `<code>` (re-rendered) = pump test -> `pump_test`. | | hard-coded code (H9/W12) | code differs per month |
| R30 | handbook_lumen | Fixed-width per processors.json layout; quantity hundredths of a US gallon (3.785411784 L). | | | |
| R31 | handbook_lumen | Amounts integer cents, tax-exclusive; a trailing minus marks a reversal. | | | |
| R32 | handbook_lumen | Times are site local `YYMMDDHHMM`; a card of all zeros is a pump test. | | treat as UTC | |
| R33 | handbook_marlow | Times naive in head-office time `UTC<offset>` (re-rendered); quantity litres; amount tax-exclusive decimal. | | site local; hard-coded offset (W12) | offset differs per month |
| R34 | handbook_marlow | `kind: void` cancels its original: neither reaches the ledger; original rejected `voided`, void record rejected `void_record`. | | void as reversal row | |
| R35 | handbook_marlow | `"test": true` is a pump test. | | | |
| R36 | handbook_marlow | `resubmission_of` replaces the named earlier line, which is rejected `replaced`. | Q | keep both / later as duplicate | 2+ per corpus |
| R37 | handbook_norvik | Quantity imperial gallons (4.54609 L); amount tax-inclusive. | | US gallons | |
| R38 | handbook_norvik | Times ISO-8601 with offset; negative quantity and amount with `<reverses>` = reversal. | | | |
| R39 | handbook_norvik | `<purpose>calibration</purpose>` is a pump test. | Q | missed marker | 2+ per corpus |
| R40 | handbook_oberon | Times epoch seconds UTC; quantity millilitres; amount integer cents tax-inclusive. | | | |
| R41 | handbook_oberon | entry `R` = reversal (positive values, `ref`). | | | |
| R42 | handbook_oberon | A sale paid with two cards is two rows with one txn_id and tender 1 and 2; each is its own line for its card's account. | Q | second tender rejected duplicate (H8) | 2+ per corpus |

Graded rules: 42 ids without b/d suffix plus 15 quiet branches (R02b, R04b, R05b, R09b, R14b, R16, R18, R19b, R21, R23b, R27, R36, R39, R42, and R17 reversal-own-date-out-of-month inside R02b). Shipped-firing rules: 27.

Interactions: R13 tier depends on R01/R02 (which lines are in month), R04 (which account), R17-R19 (reversals reduce volume), R20/R23/R36 (which lines survive), R27 (CNG litres); every tier error moves R15/R16 on every fuel line of that account, which moves every family. R24 order meets R02 x R23 and R21 x R20.

Rejection paths: `out_of_period`, `unknown_card`, `unknown_product`, `pump_test`, `superseded_batch`, `withdrawn_batch`, `duplicate`, `replaced`, `voided`, `void_record`, `orphan_reversal`, `account_closed`. Run-level: a missing or unreadable declared input stops with a non-zero exit and a stderr line naming the file (output_schema.md, "Failure").

## 4. Outputs (all keys stated in docs/output_schema.md, G-5)

- normalized.jsonl: one object per ledger row, keys in order ledger_id, processor, source_id, entry, business_date, account_id, segment, region, site_id, product, kind, litres, net_amount, tax_amount, discount_amount, settled_amount, tier; decimals as strings with fixed places; sorted by business_date then ledger_id.
- summary.json: month, ledger_rows, totals {litres, net_amount, tax_amount, discount_amount, settled_amount}, accounts [ {account_id, segment, tier_volume, tier, discount_amount, capped} ] sorted by account_id.
- data_quality.json: processors {name: {rows_read, rows_settled, rows_rejected}}, rejected [ {processor, source_id, reason} ] sorted, reason_counts.
- product_summary.json: products {code: {kind, lines, litres, net_amount, tax_amount, discount_amount, settled_amount}}.
- region_<r>.json, segment_<s>.json: same totals block plus `by_processor` (region) or `by_tier` (segment).
- JSON written with `indent=2, sort_keys` as stated in output_schema.md; one trailing newline.

## 5. Test plan (LEVER_RULES v3 G1-G13)

Families F1 ledger, F2 summary, F3 data_quality, F4 product, F5 regions (5 files), F6 segments (4 files). Corpora: S shipped (the agent's /app/out), H1, H2 (reseeded months, re-rendered prose values, quiet branches planted from their own RNG stream), H3 `_hard` (rare tier: every quiet branch >= 3 times, ties, floors). Each family x corpus is one whole-document exact test (G1); OWNED map: each output file of each corpus belongs to exactly one test (G1a), `_tier_ok` fails a test that compared nothing.

| check | weight | count |
|---|---|---|
| transform_exists (runs on shipped dir, writes 14 files) | 1 | 1 |
| F1-F6 shipped | 3 | 6 |
| F1-F6 H1, H2, H3 | 5 | 18 |
| mutation_shuffle_relocate (G6: rows rotated, data dir renamed, H1, ledger exact) | 3 | 1 |
| mutation_scale_rates (G6: tier rates x2 and cap scaled in H2's ini, summary exact) | 3 | 1 |
| determinism (foreign cwd, foreign uid, run twice, byte-identical, H2) | 3 | 1 |
| missing_export (delete one export: non-zero exit, stderr names the file) | 3 | 1 |
| negative_hardcoded_sample_answers (program emits shipped documents on H1) | -5 | 1 |

30 checks; positive weight 121; hidden share (call graph) 90/121 = 74%. Invocation exactly `python3 /app/out/transform.py --data <dir> --out <dir>` with absolute directories, from any working directory (G8a; the instruction states both), so every hidden run uses uid 1000 and a foreign cwd without leaving the stated command. Seeds live only in tests/; H3 rare fixtures use `random.Random(seed ^ 0x5A17)`. Generator asserts every value inside the contract's stated bounds (TS-19) and survives 300 seeds (G12).

Instruction exactness sentence (G5, CL-4 FC:491): "Each output document is graded whole, on this month's data and again on fresh months laid out the same way, and only an exact match counts." No axis list.

## 6. Judge plan (J1-J10)

8 probes x 3 = 24, J4 (critically_important) 5, J6 3, J10 order 3: positive 35, probe share 68.6%. Negatives J3a -3, J3b -5 (final_answer), J10 work dir -1. Probes:

| id | template | requirement served |
|---|---|---|
| R1 | P-a | cross-processor reversal sentence (group_standard Reversals) |
| R2 | P-a | business date at the month boundary (Dates + Scope) |
| R3 | P-b | handbook conventions: one source line of 3 processors next to its ledger row |
| R4 | P-c | region totals (output_schema region block) recomputed outside transform.py |
| R5 | P-d | altered copy (one tier floor or tax rate changed) moves a dependent figure |
| R6 | P-e | relocated `--data` / `--out` run (instruction invocation sentence) |
| R7 | P-h | missing declared input stops naming the file (output_schema Failure) |
| R8 | P-b | one account whose tier volume spans >= 2 processors, per-processor litres shown (COUPLING) |
| R9 | J4 | code quality behavioural |
| R10 | J6 | final reply lists every processor with rejected lines and each reason with its count |
| R11 | J10 | runs from /app with the stated command order (instruction) |
| R12-R14 | J3a, J3b, J10 dir | negatives |

Estimate (section 6 formula): lower 3/35 = 8.6 (J6 only), mid (probes at 25% = 6, J6 3, J4 2.5, J10 1.5) 13/35 = 37, upper (probes at 50% = 12, all others) 23/35 = 66. Recipe said judge 29 (upper 46): measured design numbers will be reported in JUDGE_MAP.

## 7. Expected loss per lever / rule (where a careful solver loses)

| rule | hidden input | checks lost |
|---|---|---|
| R02b | H1-H3 boundary rows | F1-F6 H1-H3 (litres move totals; DQ counts) |
| R04b, R05b | mid-month reassignment / segment change | F1, F2, F5?, F6 H1-H3 |
| R09b | mid-month tax change | F1, F2, F4, F5, F6 H1-H3 |
| R13/R14b/R16 | split accounts, floors, caps | F1, F2, F4-F6 H1-H3 (COUPLING) |
| R18, R19b | cross-processor and rejected-original reversals | F1-F6 H1-H3 |
| R21, R23b, R36, R39, R42 | closed accounts, reinstated batches, resubmissions, calibration, split tender | F1-F6 H1-H3 |
| R27 | CNG kg lines | F1, F2, F4-F6 H1-H3 |
| W12 prose values (R29, R33, R27 factor) | re-rendered handbooks | F1-F6 H1-H3, mutation checks |
| shipped-firing misreads (R03, R08, R10, R12) | shipped + hidden | all six families on every corpus |

A careful solver that misses 3 of the 15 quiet branches loses the 18 hidden family checks (90 of 121) unless the misses touch only one family, so tests land 25-45; the cost table in Phase 4 measures each rule alone.

## 8. Master changes (go, 26 Oct 18:15) and how they are applied

1. Quiet branches: each of the 15 is stated in its governing document with every key, field and value form a test reads, and carries one toy worked example on invented values (year 2041, cards starting 1111, sites with letters, ids of 1-3 digits; the generator never draws these). EVIDENCE_MAP gets one row per quiet branch.
2. Variance: hidden corpora are partitioned. 9 hidden months H1-H9, each graded on exactly 2 families (each family graded on 3 hidden months), whole-document exact; each quiet branch is planted on exactly 2 hidden months whose graded families it changes. A quiet miss costs 4 checks (20 of 121 points), the tier rule and shipped-firing misreads still cost every family (accepted). Check count unchanged (6 shipped + 18 hidden + 6 others = 30).
   | month | graded families | quiet branches planted |
   |---|---|---|
   | H1 | ledger, summary | Q2 card reassign, Q5 floor, Q12 resubmission, Q15 duplicate order |
   | H2 | data_quality, product | Q7 cross-processor reversal, Q11 CNG, Q13 calibration |
   | H3 | region, segment | Q4 tax change, Q6 cap, Q14 split tender |
   | H4 | ledger, data_quality | Q1 month boundary, Q8 rejected original, Q12 resubmission |
   | H5 | summary, region | Q5 floor, Q9 closed account, Q10 reinstated |
   | H6 | product, segment | Q3 segment change, Q4 tax change, Q11 CNG |
   | H7 | ledger, region | Q6 cap, Q13 calibration, Q14 split tender, Q15 duplicate order |
   | H8 | summary, segment | Q2 card reassign, Q3 segment change, Q10 reinstated |
   | H9 | data_quality, product | Q1 month boundary, Q7 cross-processor reversal, Q8 rejected original, Q9 closed account |
   Q1 R02b, Q2 R04b, Q3 R05b, Q4 R09b, Q5 R14b, Q6 R16, Q7 R18, Q8 R19b, Q9 R21, Q10 R23b, Q11 R27, Q12 R36, Q13 R39, Q14 R42, Q15 R20b (duplicate kept by batches.log order where file order disagrees; shipped duplicates agree in both orders).
3. Decoy: only two sentences speak to the 2023 edition's authority: its own header and the 2026 "Carried forward" clause; both quoted with file:line in QC_DEFENCE. RULES.md lists the 2023 file neutrally (title only) under a general precedence sentence.
4. No re-rendered prose: every value that changes between months lives in ref/processors.json (settlement_month, head_office_offset, pump_test_type); the documents are byte-identical across months, so W12 needs no value table and RULES.md has none.
5. CNG (products.xml unit kg) has aliases on kestrel, marlow and norvik only; handbooks state units "for products sold by volume", so the 2023 s7 kg factor is the only conversion for CNG.
6. Rejection checks run in the order listed in output_schema.md (batch standing, pump test, void record, out of period, unknown product, unknown card, account closed, voided/replaced, duplicate, orphan reversal); checks 5-7 apply to sale lines, a reversal takes product, holder and account from its original.

## 9. Redesign R2 (21:35, after the design-stage blind read was exact on shipped and 3 seeds)

Evidence (DESIGN_BLIND.md): the blind program wrote all 42 rules and all 15 quiet branches correctly in about 4 minutes; after the lumen field-class fix it was exact on 13/13 documents on shipped, h11, h22 and h33. Breadth (S1), the decoy (S5) and quiet branches (S6) are each one plainly stated sentence with a toy; a careful reader turns each into one `if`. Nothing in the design needs a search over candidates or state that a streaming program consumes in the wrong order. Kept: everything in sections 1-8 (rules R01-R42, Q1-Q15, partition H1-H9, COUPLING, decoy, tests, judge), with the lumen field-class sentence (`handbook_lumen.md:4-7`) and real previous-holder accounts.

### 9.1 Added source S3: unique fit for reversals with no reference (LEVER_RULES 1A row 3, H8 + H6)
Norvik `<reverses>` and oberon `ref` may be empty. New text, `group_standard.md` section 11 (governing file for reversals, W2):
- 11.4 "A reversal line with an empty reference reverses the sale line that fits it. A sale line fits when it comes from the same processor, has the same card and the same product, carries the quantity and amount the reversal repeats, settled as a sale line this month, has a business date on the reversal's business date or one of the six days before it, and is not reversed by another line."
- 11.5 "Reversals that carry a reference are resolved first. Reversals with an empty reference are then matched one at a time in ledger order, and a sale line matched by an earlier one no longer fits a later one. When exactly one sale line fits, the reversal reverses it; when none fits it is rejected `orphan_reversal`; when more than one fits it is rejected `ambiguous_reversal`."
- One toy (W6, invented values): card 1111000000000009, DSL 40.000 litres 80.00, sale 61 on 2041-07-28 and sale 62 on 2041-08-04, reversal 63 with an empty reference on 2041-08-06: only 62 fits (61 is nine days earlier), so 63 reverses 62.
- `output_schema.md`: check 10 becomes "orphan_reversal, ambiguous_reversal (reversal lines)"; reason_counts lists 13 reasons. Handbooks norvik and oberon: "`<reverses>` (`ref`) names the line reversed; it is empty when the terminal did not record it." (field form only; the matching rule lives in the group standard).
- Shipped: about 30 norvik and 30 oberon reversals with an empty reference, each with exactly one fitting sale line under every reading (no same card+product+quantity+amount sibling anywhere in the exports, no rejected twin, no sibling outside the window). Readings coincide on shipped (W5).
- Hidden sub-branches (plant RNG stream, each on 3 hidden months):
  | id | case | first-fit / streaming reading | right answer |
  |---|---|---|---|
  | U1 | two identical settled sale lines inside the window | reverses the first in file order | `ambiguous_reversal` |
  | U2 | two empty-reference reversals; the later in file order is earlier in ledger order and fits only one line | file-order streaming takes the shared line for the first-read reversal and leaves the other ambiguous or wrong | ledger order: each gets its own line |
  | U2r | identical lines A, B; a referenced reversal of A sits later in the file than an empty-reference reversal U | U takes A (or is ambiguous); the referenced one then double-reverses A | referenced first: U reverses B |
  | U3 | twin A of the matched line is rejected (superseded batch copy, or out_of_period last-month line within six days) and sits earlier in the file | indexes every parsed line: takes A or calls it ambiguous | only the settled twin fits |
  | U4 | the first candidate in file order is seven or more days before the reversal, or dated after it | takes it | the in-window line |
  | U5 | U2 built on a card that passes between accounts mid-month | wrong match moves litres between two accounts | tier volume of both accounts changes, so the COUPLING carries the slip to every discounted row of both accounts |
- Placement (partition of section 8, each month still graded on its 2 families; revised 21:58 after the design COST_TABLE so U2 lands on ledger/data_quality months): U1 H2 H5 H8; U2 H1 H4 H9; U2r H3 H6 H7; U3 H1 H3 H6; U4 H2 H7 H8; U5 H4 H5 H9. Every hidden month carries 2 U branches; a program that is first-fit everywhere loses all 18 hidden checks; one wrong sub-branch costs 6 hidden checks (30 of 121 points); the ledger family on H1, H4, H7 sees every sub-branch at least once.

### 9.2 Added interaction plant Q16 (11.3 negated amounts x 7.1 tax by business date)
A referenced reversal dated after a mid-month tax change of a sale dated before it. 11.3 keeps the original's net and tax negated; a program that recomputes the reversal's tax at its own date's rate is off by the rate step. Planted on H4, H7, H9 (graded ledger/DQ, ledger/region, DQ/product: the product family moves through tax_amount totals). This answers master point 2.

### 9.3 Unstated cases (master point 1): never generated
Date before the first `effective_from` (tax, segment), card whose account is missing from `accounts.csv`, unknown site, two referenced reversals naming one line: the generator asserts none occurs (G12) and EVIDENCE_MAP records "never occurs in any corpus".

### 9.4 Judge change
Probe R8 (P-b multi-processor tier) is replaced by P-g: "The agent shows one input where more than one sale line was checked as the match for a reversal with an empty reference and states how many fit." (requirement `group_standard.md` 11.5). solve.sh builds that input in its self-check stage and prints `check R8 ok` with the count. Band stays 8 probes x3 = 24 of 35 positive (68.6%).

### 9.5 Tests and estimate
Checks unchanged (30, positive 121); the U plants ride on the existing hidden months. Expected loss for a careful solver: U2, U2r, U5 (ordering and consumption) are the likeliest misses; U1 and U3 lost by an index-and-pop matcher. Estimate: one ordering sub-branch wrong: tests about 75, final (75 + 37) / 2 = 56; first fit everywhere: tests about 26, final about 31; all exact: tests about 100, final about 64 to 68. The blind read decides.
