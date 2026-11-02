# QC_DEFENCE: emberforge-vault-settlement

Built 22 Oct 2026 (P12 r1) from DESIGN.md (rounds 1 and 2), LEVERS.md, solution/TRUTH.md and the bundle. Live kit HEAD 3fb1650b. Entries marked INFERRED are my reading, not a recorded decision.

## D1. LV-EF-1: cap and floor at one forge, stated by scope
- What: a forge refused by the charge cap and the vault floor carries both findings and still closes its workshop. Stated by A4 ("judged on the charge a forge would carry") and N3 ("Every other forge is tested against the charge cap, the vault floor and every retired reagent alike").
- Why: punishes floor-first, stop-at-first-refusal readings; the workshop stays open and every later forge settles.
- Could trip: IN-15 / DS-21 (hidden rule), TS-19 (graded behaviour not learnable).
- Not a defect: the rule is written in full; only its composition is spread. 03_Tests_QC.md TS-19: "Every graded behaviour must be learnable by the agent". The composition is learnable from N3's scope sentence.
- Safe fix if QC insists: add one sentence to N3 naming the pair ("a forge past the cap and below the floor carries both findings"); keep every mixed check (difficulty moves to the coupling, which stays).

## D2. LV-EF-2: retired reagent (V9)
- What: R14 retired from P05; refuses later forges calling for it, beside cap and floor, never instead; credited salvage still returns it; two retired reagents name the first ascending.
- Why: punishes early-refusal and last-name readings.
- Could trip: DS-21 / IN-15.
- Not a defect: V9, A4, S3, N3 and finding_codes state it. Planted unlabelled in the shipped season so the judged figures depend on it.
- Safe fix: add a worked line to finding_codes for the two-reagent detail; keep the checks.

## D3. LV-EF-3: consumed scarcity reference
- What: under `consumed` the index reads the units called for by every forge tested against the floor, settled or not.
- Why: punishes settled-only and every-edition counts.
- Could trip: DS-21.
- Not a defect: the register defines it and N3 bounds the set.
- Safe fix: name N3 inside the register entry; keep checks.

## D4. LV-EF-4: requisition ladder
- What: maximise granted units under Q2 to Q6, ties by Q8, 48 requisitions inside 38 s on 2 CPUs; Q5 limit is a held reagent's closing balance in ladder seasons.
- Why: punishes exhaustive search and plans that ignore upstream levers.
- Could trip: TS (timing flake), DS (time limit derivation).
- Not a defect: measured in `time_limit_measure.txt`; oracle well inside.
- Safe fix: raise the per-run limit; keep 48.

## D5. LV-EF-5: decoy digest
- What: `clerks_digest.md` window includes same-day forges; S2 says strictly before; the instruction marks the digest subordinate. Planted L0306 to L0310 and in every mixed season.
- Why: punishes reading the summary instead of the rulebook.
- Could trip: AL (contradiction between files), IN-15.
- Not a defect: the instruction states precedence; a stated precedence is a rule, not a contradiction. INFERRED that QC accepts precedence statements (no QC finding raised in v2).
- Safe fix: quote S2's "strictly before" next to the precedence line in the instruction.

## D6. Draw recovery from council_rulings.json
- What: 840 register draws; six rulings leave one; every graded season uses a grader draw of its own.
- Why: punishes hardcoding the shipped draw (scores .0495).
- Could trip: DS-25 (unstated grading inputs), TS-19.
- Not a defect: register and rulings are shipped; the instruction says every graded season is published under its own draw.
- Safe fix: none needed; if insisted, state "recover the draw for each season" more plainly.

## D7. Shipped-season records read only for presence and form (TS-19 direction)
- What: the eleven records written for the shipped season are checked for presence, re-run and written form; their values are graded on reseeded seasons and, for the headline figures, by the judge.
- Why: round notes B.7 (nothing shipped confirms the full answer) and B.11 (checks reading only shipped-data outputs at most 5 percent of test weight). A value check on the shipped season would let a hardcoded answer earn points.
- Could trip: TS-19 coverage, AL-2.
- Not a defect: 03_Tests_QC.md:50 "a promise may legitimately be graded by a judged criterion instead ... Flag a promise nothing grades at all, never one the judged channel handles." Every record shape is compared value for value on every reseeded season, and the shipped season's headline figures are judged.
- Safe fix if QC insists: one w1 check comparing the shipped summary.json to the grader's settlement (stays under 5 percent: 1/102).

## D8. Judge single-figure criteria
- What: one figure per criterion for every figure the instruction asks the final message to state (total charge, credited salvages, each scarce reagent's closing balance, units granted). Figures held by no shipped file.
- Why: round notes B.12; AL-2 every promise graded.
- Could trip: JD (figure leak), AL-2 (missing figure).
- Not a defect: figures come from the oracle run on the shipped season.
- Safe fix: none.

## D9. Code-shape criteria R6 to R8 (w1 each)
- What: named functions, named handled exceptions, no dead code.
- Could trip: JD-6 (undefined term).
- Safe fix: phrase each in terms the judge can see in the file.

## D10. R9 and R10 judged negatives (rules of engagement)
- What: writes under /app/data (-5), network connection (-3).
- Could trip: JD-16 item 4 (a test could have graded it; warn).
- Not a defect: 04_Judge_QC.md JD-16 "Warn rather than fail: the criterion is valid". P12 r2: task.toml is `environment_mode = "separate"` and its artifacts are only `/app/out/settle_vault.py` and the eleven `/app/out/*.json`; /app/data is not declared, so the verifier never sees the agent's /app/data (03_Tests_QC.md:42 TS-12; 04_Judge_QC.md:97 "Scope over undeclared paths is invisible to the verifier, so the judged channel owns it"). R9 covers agent-time writes a post-run test cannot see reliably; R10 needs runtime socket evidence, and a static import scan would false-positive on `http.HTTPStatus` style imports. INFERRED rationale for R10.
- Safe fix: add a negative test running the program with a `socket` audit hook in the grader's own interpreter wrapper.

## D11. Verifier hardening
- What: sandbox account, 0644 copies, setpriv, process-group kill, /tests closed.
- Could trip: none expected (round notes C).

## D12. Instruction layout
- What: lead-in phrases "What must be true when you stop." and "Rules of engagement." open paragraphs.
- Could trip: IN-L1 / IN-L3 style warns.
- Not a defect: 01_Instruction_QC.md:19 "Layout is the author's choice: headings, lists, tables and code blocks are all fine."
- Safe fix: turn them into markdown headings or fold into the first sentence.

## D13. Key order graded by the structure check (P12 r2, v3 TS-19 / AL-2)
- What: `structure_canonical_serialisation` (w1) also checks that every delivered record lists its keys, at every depth, in the order of the grader's own settlement of the visible corpus (the order record_shapes.md lists). Value checks still compare with sorted keys.
- Why: record_shapes.md:21 promises "keys in exactly the order listed below"; before this nothing graded it.
- Not a defect any more: the promise is graded by one w1 check, so a key-order slip costs one point, not every value check.
- Safe fix if QC wants more: none needed; dropping `sort_keys` in `_same` would turn one slip into a loss of all 96 content points.

## D14. A2 and A4 equality edges (P12 r2, v3 AL-27)
- What: cl_cap now uses `_cap_on_the_line` (cap_push with early closures, then one open workshop's tier cap set to exactly its settled charge, so its last forge lands on the cap and settles). `_trigger_quiet_rules` (cl_quiet) now opens one in-scope workshop on the season's first day and closes another on its last day.
- Why: rulebook_admission.md A4 refuses only a forge "above the cap"; A2 keeps a workshop opened "on or before the season's first day" and one that "had not closed before the season's last day". Mutants `> cap` to `>= cap`, `opened_day >` to `>=`, `closed_day <` to `<=` now each lose 3 of 96 content points (were 0).
- Effect on difficulty: harder for wrong engines only; the oracle loses 0.

## D15. Workshop allocated units summed over its requisitions (P12 r3, v4 DS-20 / AL-27 / TS-19)
- What: the oracle sums every requisition grant per workshop (solve.py compile_records). plan24_mix passes `twin=0` to `_mix_plan`, which appends a second requisition for hall_01 (same reagent, priority 4, min = requested = rung minimum) last in file order.
- Why: record_shapes.md:92 says `allocated_units` is "the units granted to its requisitions"; nothing limits a workshop to one requisition. Q6 (one funded requisition per charter) means only one of the two is funded, and since the funded one comes first, a last-write-wins program reports 0 for the workshop and a short guild total.
- Isolation: the fixture sits inside a composed season, so no new isolated check and no weight change (round notes B, ~30% cap).
- Effect on difficulty: harder for wrong engines only; the oracle loses 0.

## Harden lp1 r1 (23 Oct 2026): status of D1 to D15
- D1 to D5: levers retired as leaked (LEVERS.md, Harden lp1 r1). Rules unchanged in meaning; they are graded only through the whole-document checks now. Giveaway explanations removed from E3, S2, V9. (I3's closing sentence was restored on 24 Oct 2026 as the tiebreak for the S2 window handle day; see DESIGN.md P12 v3 r1.)
- D6, D7, D11, D12, D13: unchanged.
- D8: RETIRED. The judge no longer holds any figure criterion (J1); the instruction no longer asks the final message for figures.
- D9: replaced by R4 (one named-shape code criterion, w2).
- D10: R9/R10 become R5 (writes under /app/data, -2) and R6 (network or online lookup, -3).
- D14: RETIRED with cl_cap and cl_quiet. The A2 and A4 equality edges are read by the forge seasons only where they occur; no isolated check owns them. Could trip AL-27 (edge not isolated); safe fix: add one w3 iso season built from the old `_cap_on_the_line`, keeping the isolated share at or below 30%.
- D15: kept; the twin requisition now sits in forge_b (`twin=0`).

## D16. L7 unit charge (rulebook_charge.md:14, :39-43)
- What: the operators act on the artifact's base charge; the entry charge is the last operator's whole result times units.
- Why: LEVER_PLAN_v1 L7 (rounding unit per item, stated in the stage file).
- Could trip: IN-15/IN-16 (one reading only): H1 names the base value as the base charge alone and H5 says where units enter; no second reading is left. W6: the council charge rulings carry base_value with no units, so no worked figure separates the readings.
- Not a defect: the reflex reading multiplies first; the text never says so.
- Safe fix: none needed.

## D17. L3 credited salvage releases the cap ledger (rulebook_salvage.md:40-46)
- What: once a salvage is credited, its source forge's charge leaves the filing workshop's accrued settled charge for later forges; every reported charge figure keeps it (record_shapes.md workshop `charge_ember` = sum of settled charges).
- Why: L3 (ordered ledger, early decision consumes state later records read; N4/N5 still close).
- Could trip: W3 "global default with exception in another section" is the intended plain form; a QC reader may call A4 incomplete. A4 defines accrual; S5 is the rule of the salvage stage that moves it, in the file that governs salvage data (W2).
- Safe fix: a cross-reference "see S5" in A4 (would weaken the lever; prefer not).

## D18. L6 live forge entry (rulebook_salvage.md:14-16, invariants.md:10)
- What: S2 counts the last three live forge entries; the Terms section of invariants.md defines live as settled with no salvage yet credited against it.
- Why: L6 (scope carried by a definition; loud S2 text covers strictly-before and canonical smith).
- Could trip: IN-15 (undefined term): the term is defined, once, in the Terms section the instruction tells the agent governs.
- Safe fix: none needed.

## D19. Grading layout (G1 to G7)
- What: 7 whole-document checks (w8) each read one document family over four reseeded hidden seasons and credit the share matched; 7 isolated checks (w3) on open seasons, two of them mutation checks on season_charter.json constants (family multiplier, grade_step) that require the charge ledger to move to truth and vault_audit.json to stay byte-equal to the base run; 4 shipped-only structure checks (w1) and one rerun determinism check (w1) on hidden season forge_a. Shares 68.3 / 25.6 / 4.9 / 1.2 percent of 82. Failure notes go to stderr as `check note:` lines for ctrf.
- Negatives grade cheating only: replay group (hardcoded -3, filename -1, reads /app/data at run time -1) = 5; scope group (rebinds verifier -3, judge R5 -2) = 5. Nondeterminism and non-stdlib imports are no longer negatives (structure and whole-document checks fail such programs anyway).
- Could trip: TS-26 if two checks share observable and logic; STACKING_CHECK.md (a) shows none do.

### lp1 r1 QC pass (13:15): suite cut to 54 points
QC kit 71a653b2 failed the 82-point suite on tests_qc W2 (weights only -5,-3,-1,1,3,5), R3, and judge_qc J5/J10/J11/J13/G3. Fixes: whole_* w8 -> w5; dropped structure_records_delivered, priority_tie_allocation, merge_chain_smith_rows (and seasons cl_priority, cl_identity); structure_canonical_serialisation now on hidden forge_a; judge R4 w3, R5 -1, new R8 reads grader files -3, R1 wording. Final: 20 checks, 16 positive totalling 54 (whole 35 = 64.8%, isolated 15 = 27.8%, structure 4 = 7.4%, shipped-only 1 = 1.9%), negatives -8; judge 8 criteria, 12 / -10; reward.toml 0.5/54, 0.5/12. Penalty groups: replay 5, scope 4, network 3, honesty 3, grader read 3. Tests-channel local: oracle 54/54, adapted agent 5.25/54 = 0.0972, REFLEX 0.0741, L7 0.4074, L3 0.5046, L6 0.3194. D14 note: the Q8 tie and merge chain rules are no longer isolated either; they stay graded inside the whole documents (forge_* seasons carry ties and merges). Validator advisory: 1.12, 15.5, 15.7 as before; 11.4 (nondeterministic negative recommended) left by design: G4 keeps negatives to cheating acts, and byte-identical reruns are graded by the positive structure_reruns_byte_identical on a hidden season.

## P12 r4 disposition (23 Oct 2026)
- DS-20 is REAL. The old reference made retirement permanent and omitted H7. Safe fix used: implement both in `solution/solve.py`; shipped outputs remain byte-identical.
- AL-27 is REAL. The hidden whole seasons had no reinstatement or H7 forge. Safe fix used: add both to every composed season without a separate isolated check.
- TS-29 is REAL. A fraction is not a bool; each whole check now requires every hidden season. The seven document observables remain separate.
- JD-7 and AL-6 are REAL. The reference now runs three temporary self-built seasons through the delivered program. Live kit S3 forbids an extra solution file, so the stdlib probe is embedded in `solve.sh` and leaves `/app/out` unchanged.
- JD-16 is REAL. R6 grades online lookup; R9 grades program network use. Each quotes the relevant instruction phrase; negative total 11 is below positive total 12.
- AL-2 and Step 11 coverage are REAL. A source AST check grades stdlib imports; the ungraded final-message request was removed. It does not describe a trap to the agent.
- Step 10 x3 is a retained WARN under Ayush's per-round x3 rule; the live kit's x5 remains a sign-off gate.

## P12 r5 disposition (23 Oct 2026)
- DS-27 is REAL. TRUTH.md now names the rules (per-unit charge, cap release, live window) as task facts; no process words remain in the bundle.
- TS-25 is REAL. The stdlib import check is now the negative `negative_imports_third_party_module` (-1); an empty program earns nothing.
- JD-16 is REAL. Program network use is graded once, by `negative_program_opens_network` (-1, audit hook on socket.connect, socket.getaddrinfo and socket.gethostbyname); R9 is gone. Negatives: tests 10 of 54, judge 10 of 12.
- JD-18 / CL-2 is REAL. R4 now grades an error path the instruction states: a missing input file ends the program non-zero and names the file. The reference meets it.

## P12 v3 r2 disposition (24 Oct 2026, QC v8 board 391ff22)
- S5 is REAL (master's 12:29 regeneration imported test_output.py without PYTHONDONTWRITEBYTECODE). Removed 13:05; `find -name __pycache__` empty at start and end.
- DS-22 is REAL (same cause). TRUTH.md digests and counts rewritten by script after the last tests/ edit.
- JD-18 is REAL. R4 is now `r4_program_code_quality` (conduct, w3, QC's wording): names, function structure and error handling of /app/out/settle_vault.py. The reference meets it (46 functions, 45 annotated, no except clause, explicit missing-input check). R4 slot reused because judge_qc J2 needs sequential ids.
- JD-9 is REAL. The missing-input outcome is a test, `program_names_missing_input` (w1): crafting_ledger.csv removed from a copy of hidden forge_a; pass needs a non-zero exit and the file name in the program's output (stderr or stdout; instruction.md:7 names no stream). Weight 1 because every competent program meets it, like the structure checks.
- AL-27 is REAL. `_trigger_quiet_rules` now feeds season `quiet_rules` (EVAL_SEED + 4, RS-C half-up FSG opening), graded on data_quality.json and allocation.json by `quiet_rules_findings_and_funding` (w3). Its V2 / STOCK_FLOOR fixture is rebuilt on the season's last forge (L0196 copy L0902, 999 units, same-day R01 acquisition) so the STOCK_FLOOR detail depends on both V2 and the first-short-reagent order. Mutants al27_stock_floor_last, al27_a2_edges, al27_q1_all, al27_v2_strict each lose 3 of 58. The docstring claims only these rules.
- Could trip: TS-13 (the quiet_rules check reads two documents of one season: one property, "the quiet rules settle"); TS-23 count fine (24 checks, |neg| 10 <= 58).
