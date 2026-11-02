# QC_DEFENCE - district-heat-flex-procurement

Written 22 Oct 2026 (P12 r1) from DESIGN.md (sections 6 and "Harden round 2"), LEVERS.md (round 2 table),
solution/TRUTH.md and the bundle. Live kit: Terminal_2.0_Harbor_Harness HEAD 3fb1650b. Rule quotes are from
Input_Bundle_QC/*.md at that HEAD. INFERRED marks a reason I reconstructed rather than found written down.

## Levers (one wrong reading each; weight lost of 100 from LEVERS.md)

### L1 H1 compliance precedence (flags H1, H1order, H1pend, H1hc; 33 to 43)
- What: SAFETY_HOLD > COOLDOWN > CONTINUITY_WAIVED > CERTIFICATE_PENDING > CLEAR (schema.md 2.6).
- Punishes: first populated flag wins; pending certificate always CERTIFICATE_PENDING; waived ranked above a hold.
- Could trip: AL-4 / IN-8 (graded rule not in the instruction).
- Not a defect: IN-8 "has to be knowable from something the agent can reach: the prompt, a specification or schem[a]"; the rule is in schema.md, which the instruction names as "the authority on every rule".
- Safe fix if QC insists: quote the schema.md 2.6 line in TRUTH.md; never name the precedence in instruction.md.

### L2 H2 tie among equal objective tuples, greatest sorted offer-id tuple (flag H2; 48)
- Punishes: first found or smallest tuple.
- Could trip: TS-20 (weight 3 on an edge case). Not a defect: TS-20 "3 = an important sub-goal or key edge case".
- Safe fix: none needed; if asked, keep the composed weight and move nothing.

### L3 H3 cap after uplift, min(base + uplift, cap) (flag H3; 63)
- Punishes: min(base, cap) + uplift. Could trip: AL-4. Not a defect: stated in schema.md section 6 (INFERRED section number from DESIGN.md 5).
- Safe fix: cite the schema line in TRUTH.md.

### L4 H4 largest remainder, ties by descending beneficiary id; zero-weight beneficiaries not listed (flags H4, W0LIST; 23)
- Punishes: ascending id, first seen; listing W = 0 rows.
- Could trip: DS-21 (omission makes W = 0 unknowable). Not a defect: DESIGN.md round 2 "the W = 0 outcome is only in the section 9 count and the allocation arithmetic"; DS-21 asks "could a determined expert ... work it out", and the arithmetic gives zero cents with no row to write.
- Safe fix: add one schema.md sentence on W = 0 rows; keep the descending-id tie.

### L5 H5 per-value tick rounding and per-site credit rounding before summing (flags H5t, H5c; 45 to 60)
- Punishes: summing raw Wh or raw credits and rounding once. Could trip: TS-20 weight concentration. Not a defect: read through whole composed documents, each a core outcome (TS-20 "5 = a core outcome").
- Safe fix: none needed.

### L6 DH-2 ticks inside the search (flag DH2; 48), DH-3 funded pool after credits (flag DH3; 40)
- Punishes: raw Wh compared to the ceiling; raw pool shared. DH-3 is read only through composed documents.
- Could trip: TS-26 (one wrong reading costs several composed checks). Not a defect: TS-26 "two tests reading genuinely different aspects of the same object ... add distinct signal"; each composed check reads a different report file of a different extract.
- Safe fix: none; if QC insists, merge one extract's region and segment checks, same total weight.

### L7 DH-4 malformed rows: out-of-range interval, unknown-region site row, duplicate profile row (flags DH4range, DH4unknown, DH4dup; 30 to 42)
- Punishes: wrapping or keeping bad rows, last duplicate wins. Stated in schema.md section 1 row precedence (INFERRED from DESIGN.md 5).
- Could trip: AL-4 hidden edge cases. Not a defect: AL-4 fails only when "the contract forbids or omits it"; schema.md states it.
- Safe fix: cite the schema line in TRUTH.md.

### L8 DH-5 waiver doubles the weight only through the label (flag DH5raw; 30)
- Punishes: doubling from raw waiver fields. Stated in schema.md section 7 grant weights.
- Safe fix: cite the line.

### L9 DH-6 decoy `program.ini [export] waiver_signed = Y` (flag SIGNEDY; 43)
- What: legacy export default; schema.md says other sections of program.ini carry no rule; blank-signature waiver rows exist on pending, valid, critical public sites.
- Could trip: DS-21 / IN-8 (trap). Not a defect: the rule is stated ("other sections of the file carry no rule"); DS-21 is about information that is "unreachable from every agent-visible file", which this is not.
- Safe fix: none; if QC insists, add "an [export] default never fills a blank field" to schema.md 2.6 (keeps the lever: the agent still has to read 2.6).

### L10 DH-7 objective component order (flags C34, C45, C5drop; 33 to 63)
- Punishes: overdelivery before cost, offer count before overdelivery, offer count ignored.
- Could trip: TS-20. Not a defect: component order decides every selected portfolio, a core outcome.
- Safe fix: none.

## Deliberate design choices

### D1 Instruction names no rule, size or time limit; schema.md is the authority
- Why: round 2 hardness (1) "no rule count or trap topic in the instruction". The 120 s limit lives only in schema.md section 3.
- Could trip: IN-8. Not a defect: IN-8 counts "a specification or schema" the instruction points to.
- Safe fix: add one instruction sentence "schema.md section 3 states the size and time limits", no figure.

### D2 Composed extracts graded as whole documents (72 of 100)
- Why: removes isolated partial credit; LEVERS isolated share 0.24.
- Could trip: TS-26 and TS-20. Not a defect: see L6.
- Safe fix: none.

### D3 Format checks on shipped /app/out (4 x 1)
- `artifact_set_exists_and_parses`, `canonical_serialization_and_integer_units`, `report_keys_match_schema`, `report_arrays_in_schema_order`.
- Could trip: TS-25 (a format check that passes on empty documents). This is real for `canonical_serialization_and_integer_units` as written in round 2 (passes on `{}`).
- Safe fix: make the check require earned content of a different observable from the key-set check: every value schema.md types as an integer is present in the agent's report as a JSON integer (presence and type, not key sets), plus the existing sorted-keys, no float, no constant, no boolean and trailing-newline rules. Effect: harder (a stub of empty objects loses the point). APPLIED in P12 r1.

### D4 Negatives: hardcoded sample (-5), reads grader (-5), external dependency (-3), hollow summary (-3)
- The first two fire only after a clean run on a composed extract (TS-16 "fire on the cheat and ONLY on the cheat").
- Safe fix: none.

### D5 Judge R1 to R6, closing-reply figures (weight 3 each)
- Why: the instruction asks for the six figures "as your program wrote them for the shipped data".
- Could trip: JD-8 overlap with tests. Not a defect: tests read files, the judge reads the reply (INFERRED from the report's G-rows passing).

### D6 Judge code-quality criteria R7, R8 (JD-18)
- R7 (round 2): "names a specific exception type in every except clause it contains", weight 1. It pays a program with no except clause, which is an absence (04_Judge_QC.md:54 "Never turn a bad behaviour into a positive").
- Safe fix: R7 becomes a negative: the final derive_report.py contains a bare except clause or an except clause that discards the caught error, weight -1, importance important (JD-13 "important requires 1 or 3"). R8 stays as the positive code-quality criterion, so JD-18 still holds. reward.toml judge weight becomes 0.5 / 19. Effect: none to harder (the vacuous point is gone). APPLIED in P12 r1.

### D7 Judge R9 grader read (-5), R10 unshown cross-check (-5)
- Different act from the test negatives (TRUTH.md "none shares a trigger with judge R9 or R10").
- Safe fix: none.

### D8 Verifier runs the program as nobody from a 0644 staged copy (round notes C)
- Could trip: TS-12 isolation questions. Not a defect: grades artifact behaviour.

### D9 TRUTH.md Verification section
- Round 2 carried "The judge was not run here (no API key); no oracle score exists for it." This is process history (DS-27 "What does not belong is any narrative of the production process").
- Safe fix: "No oracle score exists for the judged channel." Effect: none. APPLIED in P12 r1.

## Harden lp1 r1 additions (23 Oct 2026, kit HEAD 71a653b2)

### N1 export_manifest.tsv receipt (L1)
- What: per-file records and written-field sums; its header says it shows "a file arrived whole", and schema.md says "No report figure is taken from it".
- QL2 (29 Oct, session 19f8e1f): the records column is gone (CL-3, 05_Alignment_Integrity_QC.md:87: 13 of 14 counts equalled `data_quality.json` `rows`). The receipt now names each file and gives written-field sums only; header `file`, `field`, `field_sum`.
- Punishes: treating a green receipt as proof that the reading rules above the parse are right (MULT0 + OVR0, lose 76 of 113).
- Could trip: DS-21/IN-15 (a misleading file), B.7 (shipping something that confirms the answer).
- Not a defect: the receipt is truthful (every line equals the as-written sums) and confirms no graded figure; W7 "what it checks is stated in the same file".
- Safe fix: add "it does not check any reading rule" to its header. That keeps the lever, because the agent still has to apply the rules.

### N2 register_multiplier (L2)
- Rule: schema.md:53-57. One reading: Wh = reading x multiplier, then 2.3 ticks.
- Could trip: IN-16 if a reviewer reads "ticks of the reading x multiplier". The text names the Wh value as the product, and 2.3 converts Wh values.
- Safe fix: add "before 2.3 applies" to the profiles sentence.

### N3 rate composition across three files (L4)
- Rules: rate_cards.xml:4-5 (start rate), schema.md:36-37 (uplift), program.ini:21-22 and schema.md:23-25 (adder), schema.md:134-135 (cap).
  schema.md:193-201 only points at the pieces.
- Could trip: IN-15 "fully stated". Each piece is a full sentence; section 6 names all three files and says "each as that file states".
- Could trip: W4 (override names the field). The override sentence names the `override` element and the `base` element exactly.
- Safe fix: add the sum "start rate + uplift + adder" to section 6. That weakens W2 but keeps the composition with the cap and the rounding.

### N4 per-interval half-to-even credit (L7)
- Rule: rate_cards.xml:6-9, a defined term with the half-even definition inline. The global 2.2 half up stays the default for every other figure.
- Could trip: IN-16 (two rounding rules). Not a defect: the credit rule names `credit_cents` exactly (W4), and 2.2 defines only "rounded half up".
- Safe fix: one schema.md 2.2 sentence "rate_cards.xml states the rounding of credit_cents".

### N5 rules in data-file comments
- schema.md:4-6 says the comment lines of the data file schema.md names for a figure are binding, and section 1 names each comment.
- Could trip: IN-8 (the rule is outside the instruction). IN-8 counts any file the instruction points to, and the instruction now says "schema.md, together with the data files it names".

### N6 conduct judge criteria R1-R4 (JD-7, JD-15)
- These are odds-raising conduct criteria at w3 (JD-15 step 2). The oracle does not build extracts. Ayush accepted conduct criteria under JD-7 (LEVER_PLAN_v1 section 0).
- Safe fix if the PL rejects: lower them to w1 and keep them.

### N7 G7 failure messages
- rewardkit 0.2.1 `Score` has name/value/raw/weight/description and no message field, and a raising criterion aborts the whole reward. So every check prints one `[check]` JSON line (test-stdout.txt) instead of writing into ctrf. tests_qc B4 forbids writing under /logs/verifier, so no file is written.

### P12 r2 (QC v4 53c71e3) additions
- D10 TS-23 / tests_qc A3 WARN (38 checks above 35). Our common rules cap at 70 checks; the WARN is recorded, not a failure. Folding the four format checks would grade four properties in one check (TS-13). KEPT.
- D11 R9 named functions (JD-18). Positive, single property, w1, holds for solve.py (load, choose_portfolio, credit_cents, share_pool, main). QC proposed a w3 compound with "no dead blocks, bare except or debug prints"; that is absence-shaped (JD-15) and grades several properties (JD-5), so only the named-function part was taken.
- D12 DH4seen (AL-27). The rule is stated at schema.md:62-63; the case adds a repeated out-of-range row without explaining it (W1). Safe fix if QC insists on more coverage: add the same row shape to composed extract C generation.

## Harden lp1 r2 additions (23 Oct 2026, kit HEAD 71a653b2, board eb6f232)

### R2-1 season allowance ledger (L3, new; replaces the multiplier lever)
- Rules: site_allowances.tsv:1-7 (drawn by events in the order of the instants they start; equal instants by the programme
  conventions; remaining and exclusion defined), schema.md:36-38 (dispatch_start is an instant with its UTC offset), schema.md:95-98,
  schema.md:130-136 (2.4 descending identifier service), schema.md:152-158 (candidates), schema.md:334-335 (blocked count).
- Could trip: IN-15/IN-16 (order of events). Not a defect: the comment names the order (instant of `dispatch_start`), the tie rule
  (2.4, served one at a time in descending identifier order) and the draw (relief ticks over all intervals of chosen offers).
  One reading only; outputs stay ordered by event_id (schema section 8), which is a separate, stated rule.
- Could trip: AL-4 hidden rule / DS-21 knowable. Every term is defined in the file that governs the data; no figure depends on
  an unstated choice. The shipped data does not separate the order readings (W5): allowances there are either below every offer of
  the site or above all its offers. The rule is still fully stated, so a careful reader codes it; only a self-check that relies on
  shipped data alone misses it.
- Safe fix if QC insists: add to schema.md 2.4 "an event reached first is the one that starts first", never in the instruction.

### R2-2 receipt now covers site_allowances.tsv (L1)
- The receipt checks rows and sums as written; it is truthful (W7) and says what it checks in its own comment. It agrees with every
  reading of the ledger, so it proves the file arrived whole and nothing more. No report figure is taken from it.

### R2-3 section 6 checklist removed (L4 class d)
- Section 6 no longer lists the three files; each piece stays in the file that governs its data (rate_cards.xml start and
  effective rate, events.json uplift in schema.md:37-38, program.ini adder comment, 2.5 cap). IN-15 holds: every piece is a full
  sentence where its data lives. Safe fix: re-add "rate before cap = start + uplift + adder" to section 6.

### R2-4 shipped relief_wh cleaned of exact-half interval amounts (L7 class c)
- lp2_data.py raised 3720 relief readings by 10 Wh so no shipped interval amount is an exact half cent. Not volume or puzzle: the
  rule is one sentence in rate_cards.xml:8-11 with "rounded half to even" defined in schema.md 2.2. Hidden extracts carry halves.
- Could trip: DC-x synthetic data realism. Readings stay multiples of 10 Wh, as before.

### R2-5 isolated checks reduced to four cases and two mutations (G3)
- Isolated share 18.4% (<= 30%), whole documents 77.6% (>= 50%), shipped only 4.1% (<= 5%). The seven dropped isolated checks keep
  their cases planted in the composed extracts, graded through whole documents (TS-26 avoids double counting).
- allowance_ticks_mutation changes one site's allowance (130 to 190): only the ledger family moves (candidate counts, selections,
  blocked count); policy_audit site_labels stay fixed (G6).

### R2-6 judge (8 criteria, +17/-5)
- R1-R4 w3 conduct, one per lever (JD-7 accepted, JD-15 odds raising); R5 named ledger function w3 (JD-18 named shape);
  R6 exact arithmetic w1; R7 final run after last edit w1; R8 honesty negative -5. No criterion states a figure or endorses a
  reading the tests penalise. mode = "batched".

## Redesign r4 additions (25 Oct 2026, board 7743264, kit HEAD 976c1666)

Every rule below is stated in a visible file (IN-15); the shipped data never separates the wrong readings (W5); the
separating cases sit in the seeded hidden extracts H1 (season, draws_from chains) and H2 (settlement, no chains).

### R4-M1 grants: minimum drop and second share (schema.md section 7, program.ini `[grants]`)
- Rule ids: IN-15, IN-16, AL-27, TS-19, CL-4. Quoted rule: "When some beneficiaries receive nothing this way and others do
  not, every cent of F is shared again, in proportion to weight by largest remainder, across only the beneficiaries whose
  share was `minimum_grant_cents` or more, with W now the sum of their weights; each of them receives this second share."
- Why it passes: one reading; amount (every cent of F), method (largest remainder in proportion to weight) and set are all
  named; the claims sentence applies to F, before the first share. Every branch (claims fit, no drop, some dropped, all
  dropped) is planted per region in the hidden extracts (AL-27, G12). One-fact-wrong cost about 26% of test points (CL-4
  honest band).
- Safe fallback: row IN-16 DO: "one settling clause in the governing file, written for the general case": add "The claims
  sentence applies only to F before the first share." to section 7 (no example). Row AL-27 DO if a branch is called
  untriggered: add hidden reseeded rows constructing it.

### R4-CARRY carried cents (schema.md section 7 funded-pool sentence)
- Rule ids: IN-15, DS-6, CL-4. Quoted: "The carried cents of an event-region are the unallocated cents of the same region in
  the event reached just before it in season order ... the first event of a region carries nothing."
- Why it passes: stated coupling quantity (G1); a slip in it moves later rows legitimately. The shipped summed
  `grant_funded_cents` is large because carried cents are counted in every event's funded figure; that is the stated sum.
- Safe fallback: row DS-6 DO (keep names/units consistent; KEEP as minor with the sentence quoted). Row CL-4 DO: report
  one-fact-wrong per rule (COST_TABLE.md).

### R4-M2 draws_from chains (site_allowances.tsv comment, schema.md section 1)
- Rule ids: IN-15, IN-16, TS-19, AL-27. Quoted: "A site whose draws_from names another site draws on the allowance that the
  named site draws on, and its own allowance_ticks figure carries no rule. No draws_from chain returns to a site already on
  it."
- Why it passes: recursive definition with one reading; the guarantee sentence makes every chain end. Shipped chains are one
  link (W5); hidden H1 chains are 2 to 4 links with binding holder allowances, inside every stated bound (_assert_bounds).
- Safe fallback: row IN-15 DO (state as a bare property in the governing file; no example); row TS-19 DO (bring generator
  inside bounds) if a reviewer reads a bound into the text.

### R4-M3 credited relief ticks (rate_cards.xml comment, schema.md section 6)
- Rule ids: IN-15, IN-16, W2. Quoted: "An offer's credited relief ticks in an interval are its relief ticks in that interval
  less its recovery ticks in that same interval, or 0 when its recovery ticks there are the larger."
- Why it passes: the term is defined once and used once; shipped profiles have no interval with both relief and recovery,
  so the shipped credits are the same under both readings (W5); hidden extracts plant such intervals.
- Safe fallback: row SUGGEST KEEP (definition at schema.md section 6 plus kit 01:45 delegation); if IN-15 is raised, row
  IN-15 DO: repeat nothing, add a pointer "(defined in schema.md section 6)" in the rate_cards.xml comment.

### R4-D1 owned-row families (20 x visible w3 + hidden `_hard` w5), mutations x3, format x4
- Rule ids: TS-13, TS-26, TS-20, TS-23 (50 checks, warn recorded), G1/G3. Each family owns distinct fields; hidden/mutated
  share 109/173. Safe fallback: rows TS-26 DO (narrow wording to distinct observables), TS-23 KEEP with count.

### R4-D2 judge R9-R11 conduct recompute criteria (w3)
- Rule ids: JD-7, JD-15, JD-14. solve.sh runs solution/self_check.py, which prints `check R9 ok`, `check R10 ok`,
  `check R11 ok` (WORK/JUDGE_MAP.md). Safe fallback: row JD-15 DO (label as agent behavior, odds-raising at w3); row JD-14
  DO (narrow R1 to own-extract fixture vs R10 shipped recompute).

### R4-D3 judge R12 code quality (J4, JD-18)
- Rule: precheck J4 / JD-18 "exactly one code-quality criterion". R12 (w1, agent behavior, state_change) uses the LEVER_RULES J4 wording as one judgement. Oracle solve.py meets it (named functions, no bare except). Fallback: playbook row JD-18 DO (keep one criterion, conduct label, w1-3).

## Wave 1 (board 7d95b18): P-3 wide extracts

### W1-S1 schema.md section 3 bound sentence (lines 162-163)
- Rule ids: IN-15, IN-16, IN-17, AL-1, AL-2, CL-4. Quoted: "A site has at most 3 candidate offers in an event. Each run
  of the program on an extract must finish within 120 seconds."
- Why it passes: one plain bound and a run cap (QC_RULINGS dispatch v2:49-50 asks for stated run caps); no method word,
  no size statement that hands over a decomposition, no 'note that' (IN-17); it replaces a sentence rather than adding a
  quiet rule. Every generator (shipped, H1, H2, cases, wide) is inside it (within_contract + _assert_bounds, G12).
- Safe fallback: row TS-19 DO (bring generator inside bounds) if a reviewer reads another bound; row IN-17 KEEP (requirement).

### W1-T1 wide_k_portfolios_feasible (w3, k = 0, 1)
- Rule ids: TS-13, TS-20, TS-26, AL-27, G1, G1a. Quoted description: "Run on the first seeded wide season extract, where every
  event-region has 20 to 26 sites with candidate offers, every event entry in the four region files lists distinct
  candidate offers of its event-region, at most one per site, within both ceilings in every interval."
- Why it passes: feasibility is checked apart from optimality (G1); it reads only `selected_offer_ids` and the event order
  of region files, keys named in schema section 8; owner-only oracle passes; the empty portfolio is always feasible
  (EVIDENCE_MAP row 2), so there is no no-feasible case.
- Safe fallback: row TS-26 DO (narrow wording to the distinct observable).

### W1-T2 wide_k_selection_match, wide_k_tie_decisions_match (w5), wide_k_intervals_match (w3)
- Rule ids: TS-13, TS-20 (core w5, never 1), TS-26, AL-27, CL-4, G1, G1a, G5. Each compares one owned row family whole
  (selection = event_id, candidate_offer_count, selected_offer_ids; tie_decisions; intervals) against the reference on a
  fresh wide extract; the instruction's G5 sentence ("Each output document is graded whole on fresh inputs ...") covers it.
- Why it passes: every compared value is defined by schema sections 2.4, 5 and 8 (objective, constraints, tie order, count);
  no method is stated; reference 9.3 s max in Docker vs 120 s limit (<= 1/4); expected values from an independent
  reference in tests, equal to solve.py on all corpora (CHECK_REF.txt).
- Safe fallback: row TS-20 KEEP (weights 3/5 match the file); row G1a DO (split a family) if a reviewer sees overlap.

## P12 fix of QC v6 (board 9a85fdc, 27 Oct 2026); ids below are the current judge ids
- Judge renumbered: R5 (named allowance-ledger function, w3) deleted after QC v6 JD-15 (layout preference); old R6-R12 are now R5-R11 (R5 exact arithmetic w1, R6 final run w1, R7 honesty -5, R8-R10 recompute w3, R11 code quality J4 w1). Positive 24, reward.toml judge 0.5/24. Entries R4-D2 and R4-D3 above use the old ids (R9-R11 -> R8-R10, R12 -> R11).
- JD-7 R1-R4 (own extracts): solve.sh now has an own-extract stage that writes four small schema extracts, runs /app/out/derive_report.py on each and prints the program figure beside the hand figure (WORK/JUDGE_MAP.md). Lines print plain descriptions, no criterion ids. If QC still objects: the stage is the oracle-shows evidence QL Q1 asks for ("phrase your rubric so it passes oracle").
- TS-25 wide_k_portfolios_feasible: now fails an empty portfolio wherever the reference portfolio is non-empty (assert on earned output). Weights unchanged (w3). Lever P-3 none to harder.
- TS-23 58 checks: KEEP as a recorded warn (03_Tests_QC.md:62 warn only; Ayush decision 3 option A); nothing merged.
- DS-27: TRUTH.md carries no round, board, probe or blind narrative; scores are the current oracle's and named wrong readings' out of 205.

## Gate v3.6 harden (board dcd21a3, 28 Oct 2026): wide_2_*, wide_3_*
### G36-T1 wide_k_portfolios_feasible (w3, k = 2, 3)
- Rule ids: TS-13, TS-14, TS-20, TS-25, TS-26, CL-2, CL-4, AL-27, G1. Quoted description: "Run on the third seeded wide
  season extract, where every event-region has 20 to 26 sites with candidate offers, every event entry in the four region
  files lists distinct candidate offers of its event-region, at most one per site, within both ceilings in every interval,
  and a non-empty list wherever the optimal portfolio is non-empty." (fourth for k = 3).
- Why it passes: the body is the QC v7-passed wide_0/1 body with K changed (one observable: admissibility of the reported
  portfolios; TS-25 non-empty assert inside wide_feasible :2119-2124); own corpus and own program call, so it never pays for
  the same output as wide_0/1 (TS-26: different seed, different extract); oracle passes (honest-untrippable, TS-14); a
  program that writes nothing fails (CL-2). w3 like its siblings (TS-20).
- Safe fallback: row TS-26 DO (narrow wording); never merge with wide_0/1 (TS-23 option A).
### G36-T2 wide_k_selection_match, wide_k_tie_decisions_match (w5), wide_k_intervals_match (w3), k = 2, 3
- Rule ids: TS-13, TS-20 (core w5), TS-26, CL-4, G1, G1a, G5, AL-1, AL-2, IN-15, IN-16, IN-17. Each compares one owned row
  family whole on a fresh wide extract; every compared key is named in schema.md sections 2.4, 5, 8 (`selected_offer_ids`
  :268, `tie_decisions` / `tied_portfolio_count` :322-325); the instruction's whole-document sentence covers CL-4 (FC:491).
- No new sentence, rule, data or judge item: IN-15/16/17, AL-1, AL-28, JD-5, JD-6, JD-14, JD-15, DS-17 unaffected (files
  byte-unchanged). AL-27: the corpora fire the same stated optimum and tie rules as wide_0/1. DS-22/DS-27: TRUTH.md
  regenerated by WORK/w1_truth.py, counts updated (66 checks, 237 points), no production narrative.
- TS-23: 66 checks, recorded warn (03_Tests_QC.md:62; Ayush decision 3 option A); nothing merged.
- Verifier time: two more wide program calls per check family (<= 120 s each); measured grader time in WORK/COST_TABLE.md
  gate36 section, under the 2700 s verifier timeout.

## Gate v3.6 judge harden (board 8d509b8, 28 Oct 2026): R4, R8, R9, R10 re-targeted
Touched files: tests/judge.toml (4 criteria), solution/solve.sh (`|| true` own-extract stage only), solution/TRUTH.md
(regenerated by WORK/w1_truth.py, DS-22). tests/test_output.py, reward.toml, instruction.md, docs, data, solve.py and
solve.sh lines 1-229 byte-unchanged (G7). Common to all four: type "agent behavior", evaluation_target trajectory,
importance important, w3 (P-5 probe band, peer pass rate ~25%); one change, one observable (JD-5); no criterion id is
printed by the oracle (DS-17); the oracle's altered copies live under the stage's mkdtemp dir, never /app/out (DS-18,
TS-24). Instruction ties (JD-15, CL-2): instruction.md:3 "It will also be run on other extracts in the same schema, so it
must follow the rules in general and must not depend on the shipped records." and :9 "reply with a short report of what
the program does and how you checked it." AL-1/AL-2: no new rule, no new sentence, no counterfactual figure (the agent's
own program and recompute supply every compared figure; AL-2b/J1 AVOID kept). IN-15/IN-16/IN-17: instruction unchanged,
no criterion names a method, file layout or function. AL-27: every probe exercises a stated schema rule. AL-28: R7 (-5)
is the only negative and is disjoint from every positive (honesty of the reply vs an act in the trajectory). TS-13,
TS-20, TS-23 (66 checks, recorded warn, option A), CL-4: tests untouched. DS-27: TRUTH.md gets no round narrative.
JD-14: the four re-targeted acts are disjoint from R1-R3, R5, R6, R11 and from each other (own extract vs three
different altered files; each a different observable).
### R4 two half-cent interval amounts on its own extract
- Quoted: "The agent constructs its own extract in which one chosen offer has two interval amounts of exactly half a
  cent, one whose whole cent below is even and one whose whole cent below is odd, works out that offer's credit_cents by
  hand, runs derive_report.py on the extract, and compares the two." Rules: schema.md:118-122 (half to even), :200-206, rate_cards.xml top comment (interval amounts).
- Why passes: one act (build and compare one extract); observable is the agent's extract and comparison in the
  trajectory (JD-6); oracle extract 4 prints "own extract, credit_cents of OWN-0401: program 4, by hand 4, agrees"
  ([1500, 2500] Wh at base 1000: 1.5 -> 2, 2.5 -> 2; half up gives 5) (JD-7). Vacuity: an agent that never builds an
  extract earns nothing (G5).
- Safe fallback: drop the "even / odd" clause back to one half-cent amount (QC v8-passed wording).
### R8 rerun with a pool too small for the claims
- Quoted: "The agent runs derive_report.py on a copy of /app/data in which it has lowered one event-region's pool in
  pools.txt so far that the claims of that event-region's beneficiaries are no longer paid in full, and compares the
  grants that run reports for that event-region with grant cents it recomputes outside derive_report.py." Rules:
  schema.md:93-96, :211-251.
- Why passes: one change (one pool line), one observable (that event-region's grants vs an outside recompute); the
  shipped pools are all claims-paid, so the altered copy is the only way to see the largest-remainder branch on real
  data; oracle altered copy 5 prints "altered copy of the shipped extract, grants of <event> <region> with its pool
  lowered to N cents: program {...}, recomputed outside the program {...}, agrees" (JD-7). Overlaps grants_match* only
  as the act of checking, never re-charging the grant figure (J2b).
- Safe fallback: "lowered one event-region's pool in pools.txt" without the claims clause.
### R9 rerun with an allowance below a chosen offer
- Quoted: "The agent runs derive_report.py on a copy of /app/data in which it has lowered the allowance that a chosen
  offer's site draws on below that offer's relief ticks, and checks whether that run still selects the offer." Rules:
  schema.md:97-100 and site_allowances.tsv:1-11 comment (draws_from, relief over all intervals > remaining).
- Why passes: one change (one allowance_ticks value), one observable (is the offer still selected); oracle altered copy
  6 prints "... <offer> still selected with allowance <site> lowered to N ticks: program False, recomputed outside the
  program False, agrees" (JD-7).
- Safe fallback: name the site's own allowance instead of the one it draws on.
### R10 rerun with an uplift that lifts a rate above its cap
- Quoted: "The agent runs derive_report.py on a copy of /app/data in which it has raised one event's uplift so that a
  chosen offer's composed rate is above its rate card's cap, and compares the credit_cents that run reports for that
  offer's event-region with credit_cents it recomputes outside derive_report.py." Rules: schema.md:39, :140-143,
  :200-209.
- Why passes: one change (one event's uplift_millicents_per_kwh in events.json), one observable (that event-region's
  credit_cents vs an outside recompute); oracle altered copy 7 prints "... credit_cents of <event> <region> with its
  uplift raised to N: program X, recomputed outside the program X, agrees" (JD-7). JD-14 vs R3: R3 is a hand-built
  extract with override + uplift + adder and also checks cap_binding_count; R10 is a shipped-data copy, one changed
  field, credit_cents only.
- Safe fallback (if JD-14 is raised against R3): re-target R10 to a recipient weight set to zero in a copy, with the
  oracle stage changed to match.

## P12 fix ql1 (session 8556721, 29 Oct 2026)
Touched: tests/test_output.py (tie_decisions_match body, negative_external_dependency_or_network body/description,
hidden generators H1/H2 and seven new wrong-reading flags in the reference), tests/judge.toml (R3 split, R12 added),
tests/reward.toml (judge 0.5/27), solution/solve.sh (`|| true` own-extract stage: two `check <id> ok` lines),
instruction.md (line 9 removed), solution/TRUTH.md (counts and hidden-extract text). Data, schema, solve.py,
Dockerfiles, test.sh byte-unchanged (OUT G7_tests_diff.txt). The R4-D2/G36 paragraphs above that quote instruction.md:9
are superseded: the instruction no longer asks for a report; R7 judges any reply the agent writes.
### tie_decisions_match (w3, TS-25)
- Now grades the generated tie case (case_spec "tie", T2-0001 North, tied_portfolio_count 2) instead of the shipped
  data, where the reference has no tie and an empty list passed. Want is asserted non-empty (grader fault otherwise).
### Hidden extracts (AL-27, new hidden rows inside stated bounds)
- H1/H2 draw `wh_per_tick` in {4,5,20,25}, `millicents_per_cent` in {400,500,2000}, two or three fresh region codes per
  region and one or two segment codes per segment (schema.md:19-27: program.ini governs units and codes; several codes
  can name one region). H2 omits the `public` adder option (schema.md:23-25: no option means adder 0). H1 drops two kept
  profile rows of chosen offers (schema.md:57-59: 0 Wh), plants a cross-region draws_from pair in one event and an
  allowance exactly equal to an offer's relief (site_allowances.tsv comment: drawn by events reached before; excluded
  only when more than what remains). H2 plants a pool whose claims sum exactly to F (schema section 7: claims paid when
  they fit). Every plant is a guard in HIDDEN_GUARDS: a seed is kept only when each wrong reading (UNIT10, CODESHIP,
  ADDmiss, GAPdrop, LEDwithin, ALWge, CLAIMlt) changes a graded family; _assert_bounds still runs.
### Judge R3 / R12 (JD-5)
- R3 now asks only for credit_cents, R12 (new, w3, agent behavior, trajectory, important) only for cap_binding_count, both
  on the same composed-rate-above-cap own extract. Oracle prints `check R3 ok` / `check R12 ok` (JD-7). JD-2 positive
  wording, JD-9 one observable each, JD-15 tie instruction.md:3, IN-8 no instruction change needed. Positive 24 -> 27.
### negative_external_dependency_or_network (TS-16)
- Fires only on an imported root module outside `sys.stdlib_module_names`; stdlib socket/http no longer trip it
  (instruction asks for the Python 3.12 standard library only). Name kept to avoid renaming every cross-reference.

## P12 fix ql2 (session 19f8e1f, 29 Oct 2026)
Touched: tests/test_output.py, tests/reward.toml (test_output 0.5/261), environment/data/export_manifest.tsv,
environment/data/schema.md, solution/TRUTH.md. Data rows of the receipt, solve.py, solve.sh, judge.toml, instruction.md,
Dockerfiles and test.sh unchanged. Hunk map: OUT/G7_NOTE.md.
### Test truth (DS-24, QL2-F2)
- `bounded` (a copy of solve.py's branch search: twin classes, lanes by relief, min(cap, reach) bound, strict cut) is gone.
  The reference now uses `_exact`: a layered table over sites (state = relief and recovery per interval and segment relief
  capped at its floor; equal states merge, keeping the cheaper, adding ways on a tie), pruned only by a lower-bound key
  with uncapped reachable relief. No twin collapse, no cut on components 3 to 5. Equal to the old truth and the oracle on
  shipped (2000 event-regions), H1, H2 and all 320 wide event-regions (p12q2/gen_wide_truth.log, check_repair.py).
- Wide optima are computed once by `_exact` (host 20-47 s per extract) and stored in `_WIDE_TRUTH` by event-region digest
  (master 18:00 direction); shipped, H1, H2 stay live. Wide inputs (WIDE_SEEDS, WIDE_BUMPS), 120 s and 64 old wide points
  unchanged.
### Projections (TS-26, QL2-F3)
- Shipped quality_counts_match leaves out unallocated_pool_count (graded on shipped by residual_match); both hard checks keep it.
### New value checks (AL-2, QL2-F4)
- bid_cost_rows and compliance_rows: shipped w3, H1 w5, each wide extract w1 (24 points). Each is a value nothing else graded.
### Event count (IN-16, QL2-F1)
- schema.md 8.3 names event_count as the count of events in events.json and scopes the sum sentence to the keys from
  candidate_offer_count to grant_unallocated_cents.
### Hidden H1 (AL-27, QL2-F15)
- Unplanted case specs allowance_order and allowance_consumption removed; start-instant ordering stays graded by the
  mut_allowance pair (allowance_ticks_mutation: start order differs from id and string order) and the
  LEDid guard on H1. H1 seed now also requires that a
  Wh-feasibility reading (DH2) changes selection; the H1 seed changed.
### TRUTH (DS-22, QL2-F6/F7/F17)
- draws_from grader list drops allowance_ticks_mutation; tie family light check named as generated extract; step 4 bound
  described as the five-part key. Rewritten by WORK/q2_truth.py (sha lines by script).
