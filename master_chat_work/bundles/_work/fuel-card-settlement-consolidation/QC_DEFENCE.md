# QC_DEFENCE (board 60e9db0)

One entry per lever / source and per cascade. Fallback = QC_FIX_PLAYBOOK_v2 row id and its DO fix for this bundle; never a NEVER-column fix. Rule sentences are quoted at their final wording in Phase 2; file:line filled in RULE_TRACE.md.

## D1 S1 breadth (42 rules over 23 files)
- Rules: IN-15, IN-16, AL-2, AL-27, TS-23.
- Live rule: every rule is one plain sentence in the file that governs its data; docs/RULES.md names every governing file and the precedence order.
- Why it passes: IN-15 needs every rule of engagement stated in a copied file; each R-id has a sentence (RULE_TRACE). AL-27: each quiet branch has hidden fixtures (BRANCH_FIRE, RULE_COVERAGE). TS-23: checks 30 (10..35).
- Fallback: IN-15 row DO = add the bare property sentence to the governing file named in RULES.md. AL-27 row DO = add hidden reseeded rows constructing the case in the embedded generator.

## D2 S5 partial-authority decoy (group_standard_2023.md, live s7 CNG factor)
- Rules: IN-16, AL-1, IN-17, W8.
- Demotion (decoy header), `docs/group_standard_2023.md:3`: "Status: replaced by the 2026 group settlement standard (`docs/group_standard.md`)."
- Live clause kept, `docs/group_standard.md:166-167`: "14.1 Section 7 of the 2023 group settlement standard (`docs/group_standard_2023.md`) remains in force under this standard."
- The live fact, `docs/group_standard_2023.md:35-36`: "7.1 Every processor reports CNG quantities in kilograms. Settlement converts them to litres at 1.52 litres per kilogram." It is reached through `docs/group_standard.md` 6.3 ("the conversion that governs that product's quantities"); no handbook gives a kg factor.
- No other sentence says the 2023 file is ignored or kept: `RULES.md:19` lists it neutrally ("the 2023 group settlement standard"), last in the table under the general precedence sentence `RULES.md:21` "Where two documents disagree, the one listed higher in this table governs." (grep of docs_src for "2023" returns only these lines.)
- Graded both sides: dead sections (s1 home region, s2 half-up after totals, s3 tiers by transaction count, s4 own-export reversals, s5 later record wins, s6 tax on discounted net, s9 UTC day) are each contradicted by a 2026 section and move shipped figures if followed; the live s7 moves CNG rows on the 2 hidden months planting Q11.
- Why it passes: one reading; the precedence sentence settles every pair (QC_RULINGS REUSE vendor v4:129; global default + exception in another section, district-heat v3:120). Not an IN-17 announcement: the sentence states authority, not what the data establishes.
- Fallback: IN-16 row DO = one settling clause in group_standard.md "Carried forward" naming the section number and subject. Never delete the decoy's dead sections.

## D3 S6 quiet branches (15)
- Rules: AL-27, TS-19, IN-16, AL-1.
- Live rule: each branch is a clause of a stated sentence (e.g. "both ends inclusive", "the line that crosses the cap is discounted the remainder").
- Why it passes: stated, single reading, fires on every hidden corpus; generator draws inside contract bounds and asserts them (TS-19).
- Fallback: AL-27 DO = plant >=2 hidden rows per branch; TS-19 DO = bring generator inside bounds and add a bounds assert.

## D4 L3 stateful cap (R16)
- Rules: IN-16, AL-1, TS-19.
- Live rule, `docs/group_standard.md:104-110` (9.4): "The discounts of one account in one month may not add up to more than the `[cap]` value for the row's segment. Sale rows are taken in ledger order (`docs/output_schema.md`); a row whose discount would take the running total past the cap gets the remainder, and later sale rows get 0.00." plus one toy example on made-up values (cap 10.00).
- Why it passes: ledger order is defined in output_schema.md (business date then ledger id); single reading.
- Fallback: IN-16 DO = add "ledger order (output_schema.md, Ordering)" to the sentence.

## D5 L4/L6 tier volume composition + COUPLING cascade (R13-R16 into every family)
- Rules: CL-4, TS-13, TS-26, AL-28, IN-16.
- Live rule: "Every settled amount uses the discount tier earned by the account's whole-month settled volume across all processors." plus the tier-volume definition.
- Why it passes: CL-4 exemption FC:491 "An instruction that states out loud that only an exact match counts has set that bar deliberately"; instruction carries the exactness sentence. One whole-doc test per family per corpus passes TS-26/TS-13 (QC_RULINGS cascade ruling). One-fact-wrong score reported in COST_TABLE.
- Fallback: CL-4 DO = REBUT quoting FC:491 with the one-fact-wrong score; second fallback partition corpora (smaller corpora each owning fewer rows).

## D6 L7/L8 rounding (R07, R10-R12)
- Rules: IN-15, IN-16, TS-19.
- Live rule, `docs/group_standard.md:80-85` (8.1, 8.2): "Every rounding in this standard rounds half to even, one line at a time, at the step that names it." "A total is the sum of the rounded row values. It is never rounded again and never recomputed from unrounded figures." Shipped sample has 145 cent ties where half-up differs (BRANCH_FIRE).
- Why it passes: stated once in the standard, applied at the litre, tax and discount stages; >=3 planted ties per corpus; shipped has no control figure.
- Fallback: IN-16 DO = name the stages in the sentence.

## D7 L10 card holder by date (R04/R04b) and segment in force (R05/R05b)
- Rules: IN-16, AL-1.
- Live rule: `docs/reference_data.md:4` global default "a date range given by two dates includes both"; `reference_data.md:32-36` cards ("A card is held by the account of the row whose range contains the date; an empty `valid_to` means the row has no end. A card can pass from one account to another, giving one row per holder."); accounts section L45-59 (segment = latest `effective_from` on or before the date; `closed_on` is the last date the account may settle). Each with one toy example on made-up 2041 values.
- Fallback: IN-16 DO = repeat the inclusive clause in the cards section of reference_data.md.

## D8 Per-month values (no re-rendered prose)
- Rules: IN-15, TS-19, AL-1, W12.
- Docs are byte-identical across months. Every per-month value sits in `ref/processors.json` (settlement_month, marlow head_office_offset, kestrel pump_test_type, lumen layout, export paths), each field defined in `docs/reference_data.md:10-22`. No "values that change" table anywhere (master change 4).
- Fallback: IN-15 DO = name the field in reference_data.md's processors.json section.

## D9 Grading layer
- TS-20 core 5/3/1; TS-25 no absence positive (_tier_ok); TS-29 checks never raise; G4 one negative act (hardcoded shipped outputs, -5), AL-28 group sum 5; J3a/J3b distinct acts in judge. G8a invocation exactly as instruction states.
- Fallback: AL-28 DO = keep each act in one layer, group sum <= 5. TS-26 DO = narrow wording to different observables.

## D10 Judge probe band
- Rules: JD-7, JD-15, JD-8, JD-18, JD-S4, JD-S8.
- Each probe performed and printed by solve.sh self-check (`check <id> ok` + witness), so the oracle shows it (JD-7, QL 26 Oct Q1). No probe reads an output a test reads with the same logic (JD-8). One J4 criterion met by solve.py line by line (JD-18).
- Fallback: JD-7 DO = fix the oracle (add the self-check stage). JD-8 DO = delete the criterion tests settle and renumber R1.. sequentially.

## D11 TRUTH provenance (DS-27 vs VB 15.5)
- Keep the scaffold provenance lines; if the validator and QC disagree, report OPEN CONFLICT Q18, no third option.

## D12 S3 unique fit for empty-reference reversals (R2, 21:35)
- Rule ids: IN-15, IN-16, IN-17, AL-1, AL-27, TS-19, CL-4, JD-7.
- Live rule: `group_standard.md` 11.4-11.5 (quoted in DESIGN.md 9.1; file:line fixed in Phase 2): the fit conditions, "Reversals that carry a reference are resolved first", "matched one at a time in ledger order", zero fits `orphan_reversal`, more than one `ambiguous_reversal`.
- Why it passes: the candidate space is closed and stated (IN-16 settled by a closed candidate space, LEVER_RULES 1A row 3; 18b5d99f QC :63-66); the order is stated (ledger order is defined in `output_schema.md`), so every sub-branch has one reading; every key and value form (`ambiguous_reversal`, empty `<reverses>` / `ref`) is named in the docs (QL Q3); TRUTH and WORK/UNIQUENESS.md list, per planted reversal, every candidate and why it fits or not. AL-27: U1-U5 planted on hidden months (BRANCH_FIRE). TS-19: the generator only writes empty references in the two processors whose handbooks allow them.
- Fallback: QC_FIX_PLAYBOOK IN-16 DO: add one settling clause to `group_standard.md` 11.5 for the general case the reviewer names (for example "an ambiguous reversal does not consume a sale line"), never a sentence naming the planted cases. AL-27 DO: add a reseeded hidden row constructing the case.

## D13 Q16 reversal across a tax change
- Rule ids: IN-16, AL-1. Live rule: `group_standard.md` 11.3 "amounts negated" of the reversed row, with 7.1 tax by business date. One reading: 11.3 names the reversed row's values; 7.1 applies to sale lines. Fallback IN-16 DO: one clause in 11.3 "a reversal's tax is the reversed row's tax negated" (general, not the case).
