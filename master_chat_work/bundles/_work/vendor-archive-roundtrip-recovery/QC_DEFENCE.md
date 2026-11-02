# QC_DEFENCE.md - vendor-archive-roundtrip-recovery

Built 22 Oct 2026 (P12 r1) from DESIGN.md (Round 1 changes), LEVERS.md (Round 1 table),
solution/TRUTH.md and the bundle. Live kit: Input_Bundle_QC at harness HEAD 3fb1650b.
Anything not stated in those files is marked INFERRED.

## L1 RUN: state lives per stream run
- What: a segment continues the previous one's dictionary and cumulator only when the
  previous segment's `stream_continues` flag is set; the flag is named in
  format_contract.md and its effect is stated in decoder_appendix.md (split across two docs).
  Checks stream_interleaved, stream_new_run, stream_eval_mix, stream_challenge_mix (5 each, 20).
- Why: punishes "state carries per stream id" and "state resets every segment".
- Could trip: IN-8 / AL-1 (rule not knowable), DS (two-doc split read as hidden).
- Not a defect: IN-8 fails only when the agent "could not have learned from any file it
  can see" (01_Instruction_QC.md:38). Both halves are in shipped docs the instruction points to.
- Safe fix if QC insists: add one cross-reference sentence in format_contract.md pointing to
  the appendix paragraph; the rule still needs both docs joined, so difficulty holds.

## L2 REV: revision is per segment; REV0 decoy
- What: each segment carries its own revision; loader_notes.md says revision 0 inherits
  (decoy, the contract overrides it). Check stream_revision_change (5).
- Why: punishes trusting the stale loader note over the contract.
- Could trip: DS / IN "contradictory docs".
- Not a defect: the contract is the stated authority (instruction points to it); a stale
  note is a realistic distractor, not an unreachable expectation (IN-8 narrow fail, :38).
- Safe fix: mark loader_notes.md "older than format_contract.md" in its first line; the
  agent must still notice the clash. INFERRED wording.

## L3 REMAP: remap before alias; unlisted bytes identity (MAP-OMIT)
- What: the revision map lists only changed bytes; unlisted bytes map to themselves; remap
  is applied before alias lookup. Checks stream_remap_alias 5, single_remapped_modes 5.
- Why: punishes "unlisted means invalid" and alias-before-remap.
- Could trip: AL-4 hidden behaviour.
- Not a defect: identity for unlisted bytes is stated in the contract (DESIGN Round 1).
- Safe fix: none needed beyond quoting the contract line.

## L4 STATE: cumulator by mode (DICT-CUM), reset
- What: raw and delta values set the cumulator; dict values do not; reset clears state.
  Checks stream_reset_mid_run 5, reset_clears_state 3; value rule runs through every
  value-bearing composed check.
- Why: punishes "every value moves the cumulator".
- Could trip: AL-4 (omission read as hidden rule).
- Not a defect: the contract names which modes set the cumulator; an omitted mode is not
  promised to set it. INFERRED: QC v2 did not flag it.
- Safe fix: add "a dict value leaves the cumulator unchanged" to the contract; check stays
  composed, difficulty moves from inference to joining, small easing.

## L5 ESC/EXT: bounded escaping, opaque extensions out of type order
- What: escape rules bounded per escape_rules.md; extensions carried as opaque bytes even out
  of type order. Check single_escapes_ext (5).
- Why: punishes greedy unescaping and sorting/dropping extensions.
- Could trip: none flagged.
- Safe fix: n/a.

## L6 SALV: salvage keeps state across damage, resync
- What: salvage resynchronises after damage and keeps run state. salvage_state 5, salvage_mix 5.
- Why: punishes resetting state at each resync and false resync on stray sync bytes.
- Could trip: none flagged.

## L7 ENC: representation memory, delta_raw_len null, new records
- What: re-encode keeps the original representation of unmodified records, uses shortest
  form for edited ones, `delta_raw_len` null for new records. encode_unmodified 5,
  encode_edited 5, encode_new_record 5.
- Why: punishes canonical re-encoding of everything.
- Could trip: none flagged.

## L8 REJ: header rejection order and fields
- What: magic, version, reserved, record count bound, checksum, in that order; reserved
  error reports the first non zero reserved byte (14 or 15). Five isolated checks (3 each).
- Why: punishes checks in another order and reporting the last reserved byte.
- Could trip: AL-27 (precedence pair without a fixture). QC v2 FOUND this: offset 14 vs 15
  had no fixture with both set. Fixed in P12 r1 by the both_reserved fixture.
- Safe fix applied: both_reserved fixture inside reject_reserved_offset15 (harder, not easier).

## L9 Reports
- What: four report checks; three run the delivered programs on the agent's own examples.
- Why: punishes reports written by hand that the programs do not reproduce.
- Could trip: TS (report checks reading agent text).
- Not a defect: checks are behavioural (programs re-run), not text matching.

## N1-N5 Negatives
- What: hardcoded sample answers -5, nondeterministic output -3, filename dependent -3,
  reads training corpus at runtime -5 (poisoned /app/data), rebinds verifier dependencies -3.
- Why: anti-cheat; each penalises a shortcut.
- Could trip: TS-15 (inline inversion comment). QC v2 warn; fixed in P12 r1 with comments.
- Not a defect on polarity: QC verified polarity correct; 03_Tests_QC.md:46 asks only for a
  comment ("should carry").
- Kept because validate_bundle.py strict FAILs without them (LEVERS.md Round 1 note).

## J1 Judge figures absent from every file (R1-R4)
- What: four figures computed from hidden-chain work on shipped data, each in its own
  criterion, none appearing in any shipped file.
- Why: punishes guessing or reading a doc number; needs the full decode chain.
- Could trip: JD-15 / IN-8 (figure not in files).
- Not a defect: these are final-answer figures the instruction asks for; the method is in
  the docs, only the value is computed (round notes B.12 "each needing the full chain and
  absent from every file").

## J2 Judge code quality criterion (P12 r1)
- What: one weight-3 state_change criterion on decode.py / encode.py quality.
- Why: JD-18 requires one; replaces the unpromised structure criteria R5/R6.
- Could trip: JD-18 "must judge quality, not prescribe a style guide".
- Not a defect: wording is QC's own suggested text.

## J3 Honesty and boundary negatives
- What: R7 unbacked validation claim -3; R8 reads /tests or /logs/verifier -5 (ids unchanged in P12 r1).
- Why: round notes B.12 "one honesty negative for a claimed validation the trajectory does not show".

## J4 Method line criterion R6 (P12 r1)
- What: R6 r6_method_lines, weight 1, instruction following, final_answer: the reply follows each of the four numbers with one line saying how it was obtained.
- Why: instruction.md L13 promises that line; without a criterion the promise was ungraded (AL-2). It also keeps the judge at 8 criteria (JD-12 minimum).
- QC check it could trip: JD-5 (single observable: yes, one act repeated per figure), B.12 "no criteria that echo doc sentences" (INFERRED risk: it restates an instruction sentence).
- Why not a defect: 05_Alignment_Integrity_QC.md:22 AL-2 "For each instruction requirement: point to the test (or criterion) that checks it." Grading an instruction promise is what AL-2 asks; it does not echo a data file.
- Safe fix if QC insists: delete the clause from instruction L13 and replace R6 with another single-figure computed criterion (keeps 8 criteria).

## D1 Hidden EVAL fixtures and seeds
- What: composed checks draw hidden segments at grade time; the generator keeps
  SAMPLE_SEED / CHALLENGE_SEED / EVAL_SEED and `_write_corpus` / `main` in test_output.py.
- Why: hidden fixtures stop memorising visible data.
- Could trip: DS-27 if seed names are narrated in TRUTH.md.
- Not a defect in tests: validator 7.2 requires them in test_output.py (DESIGN Round 1).
  TRUTH.md should not narrate them; removed from TRUTH in P12 r1.

## D2 Batched judge, tests-only score labels
- What: judge mode batched; score labels and oracle/nop gates are tests-only (common rules).
- Could trip: none.

## N6 Filename negative carved from the nondeterminism negative (P12 r2)
- What: negative_filename_dependent_behaviour decodes each of three names twice; it fires only when every name is stable on repeat yet names disagree. negative_nondeterministic_output fires on same-path repeats that disagree.
- Why: QC v3 TS-26 / AL-28 found both firing on a nondeterministic decoder (-6). The carve is the fix AL-28 names ("carve the triggers into genuinely non-overlapping conditions").
- Could trip: TS-26, AL-28 again only if a decoder is random but happens to repeat per name; that is chance, not shared logic.
- Not a defect: both are required by validate_bundle.py section 11 strict, so neither can be dropped.

## N7 Rebinds negative now fires at run time (P12 r3, replaced trigger)
- What: negative_rebinds_verifier_dependencies keeps its name and -3 weight. It still scans the workspace and /app/out, and now also runs decode.py and encode.py on one fixture with the run folder as cwd and fires if the run writes a .pth file or a module or folder named after a standard library or grader module into the run folder, the staged program folder, the temp dir or site-packages (baseline taken at import).
- Why: QC v5 TS-16-1 showed the static scan alone could never fire in separate mode. The act is the same (plants shadow modules), so the AL-28 group stays at 3.
- Could trip: TS-16 (honest trip). An honest program writes only to stdout and the target path the tests give it; none of the names in _SHADOWS.
- Not a defect: 03_Tests_QC.md:47 "fire on the cheat and ONLY on the cheat"; local cheat probe (decode.py writing json.py into cwd) fired, oracle and agent program did not. validate_bundle.py section 11.5 strict needs the name.
- Safe fix if QC insists: drop it and run validate_bundle.py --lenient (warn), no lever effect.

## D7 Neutral capture ids (P12 r3, DS-4-1)
- What: every catalog line has capture_id cap-NNNNN, numbered in file order after decodable and rejected lines are mixed.
- Why: QC v5 DS-4-1 found cap-/rej- prefixes made catalog_ok_count and catalog_error_count readable from names.
- Could trip: DS-4 again only if ids carried status; they no longer do.
- Not a defect: the field is named in format_contract.md:9; no prefix rule is stated anywhere.

## J5 Oracle programs are role-specific (P12 r2)
- What: solve.py --build emits /app/decode.py (decoder only, schema baked in) and /app/encode.py (encoder only) by AST selection of the definitions each role reaches.
- Why: QC v3 JD-7 found both programs were the same 568-line source with build and report code, at odds with judge R5 (no dead code).
- Not a defect now: outputs byte-identical to the previous oracle on all shipped segments and reports.

## Harden lp1 r1 (23 Oct 2026, board 52dbb3c)

### H1 L2 count unsigned behind value_sum (make-it-match)
- What: format_contract.md Field names states that a raw record whose `unit` is `count` is read unsigned, "in place of the signed reading under Value by mode". The catalog line carries `value_sum`, defined in the catalog bullet of the same file.
- Why: it punishes reading signed everywhere, which the control flags, and the all-unsigned repair, which the control accepts on the shipped captures because every non-count raw there is non-negative.
- Could trip:
  - IN-16 (two readings of raw signedness);
  - DS (control that the "obvious" reading fails);
  - B.7 (shipped settled outputs).
- Not a defect:
  - The override names the field and the value exactly (W4) and says it replaces the Value by mode reading, so there is one reading.
  - The control is truthful and says what it sums (W7).
  - value_sum is a per-capture total, not a document answer. It holds under both the correct and the all-unsigned reading, so it confirms nothing beyond what the rule already says.
- Safe fix if QC insists: add "(see Field names for count fields)" to the Value by mode raw bullet. The control and the hidden non-count negatives keep the lever.

### H2 L6 cumulator per field name in Terms
- What: Terms defines "cumulator" as kept per field name; Value by mode uses the bare term and points at Terms.
- Why: it punishes one running total per stream.
- Could trip: IN-15/IN-16 (scope only in a definition); AL-4 hidden behaviour.
- Not a defect: the definition is explicit, with one reading. LEVER_PLAN_v1 L6 and W3 "a definition with a branch and no warning".
- Safe fix: write "the record's field's cumulator" in the delta bullet. The shipped data still does not separate it, so it stays hidden-graded.

### H3 L3 run ledger with resends
- What: decoder_appendix.md Runs. A seq_no that is not larger than the run's last means a resend, which leaves the run untouched.
- Why: it punishes letting every listed segment update the state.
- Could trip: TS-19 (learnable?); IN-8.
- Not a defect: the rule is stated in full in the file that defines manifests. The instruction says manifests are fresh inputs and every document is graded whole.
- Safe fix: none needed.

### H4 L5 JSON boolean / JSON integer beside trim rules
- What: the stream_continues override only as a JSON boolean, beside "every text value in a manifest is trimmed"; delta_raw_len exact only as a JSON integer, beside "hex read case-insensitively after trimming". stream3_manifest.json ships a string override.
- Why: it punishes coercing "true"/" TRUE "/1/0 or "3" into typed values.
- Could trip:
  - IN-16 (is a trimmed "true" a boolean?);
  - DS-21 (shipped decoy row).
- Not a defect:
  - "JSON boolean (`true` or `false`)" names the type exactly, and "Otherwise (null, or any other value)" closes the branch.
  - The trim rule changes text, not its type.
  - The shipped row is the separating case W5 allows for this lever.
- Safe fix: add "a string is never a JSON boolean" to the Runs paragraph. This loses some bite but stays graded.

### H5 Instruction without figure asks; judge conduct criteria (JD-7)
- What: the instruction asks for "a short account of what you built and how you checked it". Judge R1-R4 are w3 conduct criteria ("builds its own ... and compares"), R6 is a w1 catalog round trip check, R5 is named-shape code quality, R7 is honesty and R8 is grader paths.
- Could trip:
  - JD-7: the oracle solve.sh builds no test inputs;
  - JD-15 step 1/2.
- Not a defect: Ayush accepted conduct criteria under JD-7 (LEVER_PLAN_v1 J2, 08:23). Each one is odds-raising (it checks a stated rule on a case the shipped data lacks), weighted 3, never 5. R5 is true of solve.py: it uses `except BadFrame` and `except UnicodeDecodeError` only.
- Safe fix: lower R1-R4 to weight 1 (keeps 8 criteria).

### H6 Failure messages on stdout, not ctrf (G7)
- What: `_note` prints `[check] <name>: <reason>` for each failed check and each fired penalty.
- Could trip: G7 "messages recorded in ctrf".
- Not a defect: rewardkit 0.2.1 Score has no message field; Harness scripts/normalize_ctrf.py drops `results.tests[i].message`; tests_qc B4 FAILs a tests .py that names /logs/verifier. test-stdout.txt is kept per trial.
