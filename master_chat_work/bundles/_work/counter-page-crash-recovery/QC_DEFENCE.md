# QC_DEFENCE counter-page-crash-recovery (board 54e38ee)

Live rule quotes from `20261024_process/qc_reverse/A/checks.json` (kit file:line); fixes from
`knowledge/QC_FIX_PLAYBOOK_v2.md` (row id, DO column). Never-column fixes are not used.

## LV-WR-1 exact recovered page image
- IN-15 (01_Instruction_QC.md:45) "A rule that is graded but appears in no file the agent can read
  costs the honest agent reward". Passes: analysis, redo (per-page decision before the record's
  changes, `>=` recLSN, `>` pageLSN) and the CLR application are sentences in
  `recovery_contract.md`; instruction.md points to it. Fallback IN-15 DO: state the missing clause
  once as a bare property in recovery_contract.md (Redo section), no example.
- IN-16 (01_Instruction_QC.md:46) "show all three parts or you do not have a finding". Passes: the
  redo sentence fixes the decision point ("decided before any of its changes is applied"), so the
  eager reading is not defensible. Fallback IN-16 DO: one general settling clause in the Redo
  section ("for every record, whatever pages it changes ..."), never for a specific record.
- IN-17. Passes: no sentence says the shipped method is wrong, that disk pages hold loser writes,
  or that CLRs are skipped; the contract states the method, not the input's properties. Fallback
  IN-17 DO: delete the announcing sentence, then re-run W9.
- AL-1 (05_Alignment_Integrity_QC.md:21) "Everything graded is promised". Passes: every graded key
  and value is defined in the contract's output sections. Fallback AL-1 DO: state the rule (IN-15).
- AL-27 (05:27) "a rule only counts as graded when the test's input actually constructs the
  situation". Passes: H1/H2/H3 construct same-page multi-change records, flushed loser pages,
  partial rollbacks; RULE_COVERAGE mutants B3/B15/B16/B1/B2 each fail tests. Fallback AL-27 DO:
  add hidden reseeded rows constructing the case inside every stated bound.
- TS-19 (03_Tests_QC.md:50). Passes: generator asserts records <= 1200, pages <= 24, slots 4..8,
  deltas in the stated range; every promise has a check. Fallback TS-19 DO: bring generators inside
  the bounds; add the missing grader.

## LV-WR-2 compensation chains
- IN-15/IN-16: the undo-point walk (update -> itself, CLR -> undo_next, other -> prev, null -> none)
  and the CLR's undo_next are sentences in the Undo section; one reading. Fallbacks as above
  (Undo section).
- IN-17: the contract never says the log holds CLRs of an earlier restart; it states the walk for
  every CLR. Fallback IN-17 DO: delete any sentence naming earlier restarts.
- AL-27: H2 stops earlier restarts after a CLR whose undo_next names a CLR and before a loser's
  END; mutants B5 (prev walk) and B12 (one hop) fail H2 checks. Fallback AL-27 DO: raise hop forcing
  in the hidden H2 generator.

## LV-WR-3 stated audit sequence
- IN-15: LSN numbering, ENDs for winners (ascending id), ENDs for no-undo-point losers (ascending
  id), global largest-undo-point order, END at once, redo start = smallest recLSN: all stated in
  the Appended records and Redo sections. Fallback IN-15 DO: state the missing clause there.
- AL-27 (precedence/tie-break triggered): H1/H2 hold images with several winners lacking ENDs,
  several no-undo-point losers and interleaved losers; B4/B6/B7/B9 mutants fail. Fallback AL-27 DO:
  add hidden images constructing both orders at once.
- IN-16: "largest LSN" undo points are unique, so the order has one reading; END order is by
  ascending integer transaction id (ids are integers). Fallback IN-16 DO: one general clause.

## Cascade: whole-document checks per hidden book (H1a-d, H2a-d, H3, H4, M1, M2)
- CL-4 (05_Alignment_Integrity_QC.md:77) "Partial credit tracks partial correctness". REBUT:
  instruction.md states that each output document is graded whole on fresh inputs and only an exact
  match counts; FC:491 "An instruction that states out loud that only an exact match counts has
  set that bar deliberately"; one-fact-wrong score in COST_TABLE.md. Fallback CL-4 DO: partition
  into owned-row tests per trap family (image rows, appended list, client totals) at the same
  weights.
- TS-26 (03_Tests_QC.md:53) "Two tests reading the same observable with the same decisive logic
  pay one behaviour twice". Passes: each check reads a different document or a different input
  (H1 vs M1 = mutated copy); QC_RULINGS PASS district-heat v3:185, cohort v2:183 (whole document
  per view per hidden extract). Fallback TS-26 DO: narrow one check to a different observable, or
  merge at the larger weight inside the same lever family.
- TS-13 (03_Tests_QC.md:44) "A test asserting two unrelated properties". Passes: one document per
  check; H3 asserts the document and the stated time limit (one promise: recovery at the limits).
  Fallback TS-13 DO: split H3 into document (5) and time (3).
- TS-20 (03_Tests_QC.md:51). Passes: hidden whole-doc checks 5, sub-goals 3, existence 1. Fallback
  TS-20 DO: raise the core check.
- AL-28 (05:28) "No penalty stacking". Passes: four acts, one negative each (copied documents -5,
  neutered tests -3, network imports -3, fake artifact -5); judge grader-read negative is a fifth
  act. Fallback AL-28 DO: one layer per act, group sum <= 5.

## Cascade: judge
- JD-7 (04_Judge_QC.md:76) "Every criterion must be satisfied ... by the shipped oracle". Passes:
  solve.sh self-check prints `check J2a ok` .. `check J2d ok`, `check J9 ok`; JUDGE_MAP lists each.
  Fallback JD-7 DO: fix the oracle (and TRUTH.md) to meet the criterion.
- JD-15 (04_Judge_QC.md:92). Passes: conduct criteria labelled conduct, the code-quality criterion
  carries concrete conditions. Fallback JD-15 DO: re-label; strike unstated idiom words.
