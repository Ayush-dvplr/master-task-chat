# QC_DEFENCE: schema-migration-plan-repair

Built 22 Oct 2026 (P12 r1) from WORK/DESIGN.md, WORK/LEVERS.md (Round 1 section), solution/TRUTH.md and the bundle. Live kit: Input_Bundle_QC at harness HEAD 3fb1650b. Entries marked INFERRED are my reading, not a line in DESIGN.md.

## Levers

### STATE (F1, F2): the planner keys its visited set by schema only
- What: the shipped planner marks a schema visited and never revisits it, even when it arrives with a different field state.
- Why: punishes the reading "graph search = BFS over schema ids". Worlds that need a second visit with a new state fail.
- Could trip: TS-26 (worlds sharing this lever pay it more than once).
- Not a defect: each world composes a different lever set and a different contract folder, so no two checks read the same observable with the same decisive logic. 03_Tests_QC.md:53 fails only "Two tests reading the same observable with the same decisive logic".
- Safe fix if QC insists: drop STATE from one named world's lever set by changing that world's generator salt, keep the isolated check `plan_revisits_schema_with_new_state`.

### TIE (F3): equal-cost paths pick the wrong edge
- What: tie broken by schema id instead of the first edge in file order.
- Why: punishes "sort neighbours" habits. Isolated check `plan_tie_first_edge_decides`.
- Could trip: TS-13 if read as two properties (cost and order). Not a defect: the check has one observable, the chosen edge list.
- Safe fix: none needed.

### SCALE (F4): ladder search blows up on large states
- What: exponential state copy; hidden ladders exceed the 10 s limit (K14).
- Why: punishes a fix that is correct only on the small shipped graph.
- Could trip: TS-22 style flakiness concerns. Not a defect: limit is 10 s against a reference that runs well under 1 s (measured in R1.8).
- Safe fix: raise the time limit, never lower the ladder size.

### NULL (F5): FieldView.from_payload drops explicit null
- What: explicit null and absent collapse into one.
- Why: punishes "None means missing". Isolated check `signature_keeps_explicit_null`.
- Could trip: TS-13 (QC v2 flagged the check for also asserting E_UNKNOWN_SCHEMA and argument non-mutation). REAL; split in P12 r1.
- Safe fix: one assertion per check; the moved assertions keep their own checks (see TS-13 row in RECHECK_FIX.md).

### POLICY (F6): decoy presence default
- What: the field policy default is `OPTIONAL_NULL`, and a README line states a different default; only the contract file is authoritative.
- Why: punishes trusting the README over the contract. Decoy boundary at 16 records.
- Could trip: IN-x "instruction contradicts files". Not a defect: instruction.md says "The contract is `/app/ci/repository_contract.md`", so the authority is stated.
- Safe fix: name the README as non-binding in the contract, never in instruction.md.

### TOKENS (F7, F7b), CORR (F8, F9), REPLAY (F10, F11), FEED (F12, F13), REPORT (F14), CLI (F15)
- What: tokenizer, executor/classify, correction first-arrival, replay manifest, identity merge links, summary categories and partner order, CLI defects.
- Why: each punishes one shallow reading of a contract rule; isolated weight-3 checks plus composed worlds.
- Could trip: TS-20 (weights). Not a defect: 03_Tests_QC.md:51 "3 = an important sub-goal or key edge case"; worlds are 5 = core outcome.
- Safe fix: none needed.

### STRUCT, HONESTY (weight-1 checks)
- What: artifact existence, archive layout, module JSONs matching the archive, test_fixes matching real runs, repair report shape; unsafe archive members carry a separate negative -1.
- Why: punishes reports that claim what the archive does not contain.
- Could trip: TS-20 "existence check carrying 5". Not a defect: all are weight 1.

## Deliberate design choices

### No fault list in agent-visible files
- Why: the agent must find the defects from the contract; a list turns the task into a checklist.
- Could trip: IN "instruction underspecified". Not a defect: "Repair the repository so that every stage behaves as the contract states" plus the contract is the full spec.
- Safe fix: none; never list faults.

### 63 checks (above 35; 49 before Harden P9 v2 r1)
- Why: 28 composed worlds and 2 mutation tests give partial credit per lever mix; folding them coarsens the measured variant spread (single-lever variants 0.31 to 0.80).
- Could trip: TS-23 warn. Not a defect: 03_Tests_QC.md:62 "at most 35 (warn)"; L135 "warn: ... TS-23 cap above 35". Hard cap 70 is met.
- Safe fix if QC insists: fold worlds pairwise only where lever sets are equal (INFERRED: none are equal, so this would cost resolution).

### Tests carry their own reference pipeline
- Why: hidden worlds need expected outputs the agent cannot see; the tests derive them rather than shipping answer files.
- Could trip: TS "test re-implements solution". Not a defect: expected values come from rules, not from the oracle.

### Negative `negative_embedded_hidden_eval_data` (renamed in P12 r1 from the old name)
- What: fires if the hidden seed or 3 or more hidden edge ids appear in the delivered source.
- Could trip: TS-14 (old name said "hardcoded sample answers", body checks hidden grader data). REAL warn, renamed.

### Judge R5 code quality (negative since P12 r2; R7 before Harden P9 v2 r1)
- Why: JD-18 needs one code-quality criterion.
- Could trip: JD-5 compound (old wording had names, catalogue codes, debug prints, dead code). REAL minor, narrowed in P12 r1 to one observable (leftover residue); catalogue codes are graded by `pipe_rejection_codes`.
- P12 r2 (QC v3 JD-2/JD-15/JD-5): a positive "leaves no residue" paid for an absence (04_Judge_QC.md:54). Now `r7_leaves_debug_residue`, weight -3: "leave a debug print or a commented-out code block behind"; the dead-function clause is dropped (JD-5). Judge positive total 21 -> 18, negative 11 -> 14.

### Judge R1-R4 conduct probes (replaced the R1-R6 figure criteria in Harden P9 v2 r1)
- What: four w3 conduct criteria (agent behavior, trajectory): the agent constructs its own input with a damaged receipt (R1), a partner-rejected line in a batch (R2, observable: the rejected record's fingerprint field; R9 w1 pays for checking that batch's receipt result, split in P12 r5 for JD-5), a parse-rejected line naming a manifest batch (R3), a spaced null token (R4), runs the repaired package on it and checks the stated observable. The figure criteria and the instruction's figure paragraph are gone (LEVER_RULES J1).
- Why: J2, one conduct criterion per lever; the shipped data lacks each of these cases except R4, so a solver that only re-runs the shipped feed never sees them.
- Could trip: JD-15 conduct narrowing. Not a defect: 04_Judge_QC.md:139 "conduct criteria hold for every competent route or earn their narrowing by raising the odds of a correct end state"; each probe targets a rule stated in the contract (K13/K15/K17, N6) and the oracle runs all four (solution/solve.py `self_checks`, JD-7). Safe fix if QC insists: playbook row JD-15, DO reword the criterion to the observable only, keep weight 3.
- Could trip: IN-8 (graded but not asked). Not a defect: 01_Instruction_QC.md:77 "conduct criteria are exempt, see JD-15".

### Separate verifier with network allowlist to OpenAI only
- Why: judge needs the API; agent gets no OpenAI host.
- Could trip: structure checks on network. Not a defect: structure_qc passes 17/17 at QC v2.

### Entry-point guards (P12 r1, argument guard made negative in P12 r2)
- What: `signature_rejects_unknown_schema` (w1, K11) and, since P12 r2, `negative_entry_points_mutate_arguments` (w -1, K5/K6/K7), split out of the old three-part signature check (TS-13). QC v3 TS-25: the old positive `entry_points_leave_arguments_unchanged` paid for an absence (03_Tests_QC.md:52), so its detection moved to a negative; a call that fails is not counted.
- Why: regression guards. A rewrite that lets state_signature accept an unknown schema, or that fills or corrects the caller's payload in place, loses them.
- Could trip: TS-20 (weight 1 for a contract rule). Not a defect: 03_Tests_QC.md:51 "1 = a minor detail or existence check"; every measured wrong reading and the shipped repo pass them, so they are guards, not core outcomes.
- Safe fix if QC insists: fold both into one w1 guard named for both properties (keeps the same points).

### P12 r2 additions
- `changed_functions` completeness (QC v3 AL-2/TS-19): `module_*_claims_match_archive` now also require every function the archive changed or added in the area (K19 areas: core is `core/` and `pipeline.py`, parser is `parser/` and `cli.py`, report is `report/`) to be listed. Effect harder.
- Booleans under a cast (QC v3 AL-27, M5 "booleans included"): `exec_add_fill_absent_vs_null` added a float and an int cast on boolean fields, expected unchanged. Moved into the NULL worlds in P12 r3 (TS-13). Effect harder.
- M5 float clause now says surrounding spaces are ignored (QC v3 IN-16); K17 says `completed_steps` is 0 when execution never started (QC v3 CL-5/AL-4). Both match what the tests already graded; effect none.
- Oracle copies the repaired tree back over `/app/repo` (QC v3 DS-15 note); effect none.

### P12 r3 additions (QC v4)
- AL-27 untriggered rules: each now has a graded case inside existing composed worlds, no new check, isolated share 31/137 = 22.6% (was 30/136 = 22.1%; the only change is the TS-13 split below). NULL gadget (worlds 01, 05, 07, 11, 12, 16, 17): one edge casts an integral float to int (M5), a null to str (M4, left alone) and a boolean to float (M5, unchanged). REPLAY gadget (worlds 02, 04, 05, 09, 10, 14, 16, 18, 19): one payload holds a non-ASCII string (K4, `ensure_ascii=False`). FEED gadget (worlds 02, 06, 08, 10, 13, 15, 17, 19): ghost partner with an unknown schema (E_UNKNOWN_PARTNER, K13 partner before schema), batch missing from the manifest with a ghost partner (E_PARSE, K13/K15 parse first), and an unknown-schema line that becomes the holder followed by the same partner and key with a different payload (E_REPLAY_CONFLICT, K16). Each one-rule-broken variant of repo_fixed now loses 7 to 9 worlds (0.66 to 0.74); before it lost at most one w1 report check. Effect harder.
- TS-13: `exec_add_fill_absent_vs_null` grades N4 only; `summary_categories_and_partner_order` (w3) split into `summary_categories_code_first` (w3, T1/T2) and `summary_partner_order_by_rank` (w1, T3); the kit allows only weights 1, 3 and 5, so the positive total moves from 136 to 137. Effect none.
- TS-16/TS-19: K7 now reads "None of `state_signature`, `plan_migration` and `execute_plan` changes its arguments.", matching what `negative_entry_points_mutate_arguments` watches. Effect none.
- DS-18: solve.py exits 0 with a note when the repo is already repaired and every deliverable is present; a second run changes no file and leaves no temp folder. Effect none.

### P12 r4 findings
- IN-16/CL-5: REAL. K19 now states the general meaning of changed code and the name for a nested function; tests retain the same AST comparison. This settles an ungraded prose gap without naming a trap. Safe fix row IN-16.
- DS-22: REAL. TRUTH's line count and test totals were corrected to the shipped files. Safe fix row DS-22.
- TS-13: REAL. Identity checks retain total weight 3; archive safety is a negative (-1) and layout a positive (+1) to satisfy TS-25; no hidden world was removed. Safe fix row TS-13.
- TS-23: REAL warn, KEEP. The 49-check count is under the 70 cap; composed lever checks retain distinct observables. Safe fix row TS-23.

## Harden P9 v2 r1 (23 Oct 2026; levers L1 + L2 + L5 + L6)

### RECEIPT control (L1): batch receipt in replay_manifest.csv
- What: `replay_manifest.csv` gained `lines,fp_xor`; the run writes `receipt_mismatches` (K13, K18). Shipped receipts are all honest, so the shipped run shows `[]`. Hidden worlds tagged DAMAGE carry two damaged receipts (count off by one, one XOR bit flipped) and one empty batch `0,00000000`.
- Live rule: repository_contract.md:79-86 "The last two columns are the batch receipt, which confirms that the lines of a batch arrived as sent: `lines` is the number of records whose `batch` is that batch, and `fp_xor` is the bitwise XOR of the first eight hex digits of `record_fingerprint(schema, payload)` over those records' lines as received ... The run lists in `receipt_mismatches` the sorted ids of the batches whose count or XOR differs from their receipt."; K18 line 128.
- Rule ids: AL-1 (promised in K13/K18), TS-25 (no positive passes on an empty list: every receipt check and every DAMAGE world expects a non-empty `receipt_mismatches`; the isolated scope check expects `["B4"]`, the rejected-line check `["B2"]`), AL-27 (each clause triggered: count, XOR, empty batch).
- Why passes: the control is real and its scope is stated in the same sentence (W7); it says nothing about tokens, planning or corrections, and is green for every wrong reading of those (L1 by design).
- Safe fallback: playbook row TS-25, DO add one more damaged batch to the failing fixture; never drop the control.

### RECEIPT scope (L6): "records whose `batch` is that batch"
- What: a parse-rejected line that names a manifest batch is not counted, because K15 gives every E_PARSE record a null `batch`. The shipped check counts the raw `batch` field of every feed line (F17). Shipped data has no parse-rejected line naming a manifest batch (W5); hidden SCOPE worlds and `receipt_skips_lines_rejected_at_parse` do.
- Live rule: repository_contract.md:81 "`lines` is the number of records whose `batch` is that batch"; repository_contract.md:97-98 "Such a record has `batch`, `partner`, `key` and `schema` null."
- Rule ids: IN-16 (one reading: the definition is K17's `batch` key, which K15 sets null; a raw-line reading contradicts K15), AL-27 (triggered in 13 worlds and one isolated check), W1 (no sentence names the trap).
- Safe fallback: playbook row IN-16, DO add the words "(K15, K17)" after "records" in K13; keep the hidden cases.

### RECEIPT make-it-match (L2): partner-rejected lines
- What: the shipped check XORs the records' `fingerprint` field and skips nulls, so every batch holding an E_UNKNOWN_PARTNER or E_ALIAS_CYCLE line shows a mismatch on the shipped run (25 batches). The tempting repair writes a fingerprint into partner-rejected records: the shipped receipt turns green, but K17 says the fingerprint is null before the partner stage passes. The correct repair computes K4 on the line as received inside the check.
- Live rule: repository_contract.md:120-121 "`fingerprint` (null before the partner stage passes)"; control at repository_contract.md:81-84 ("over those records' lines as received").
- Rule ids: AL-1, TS-26 (`receipt_counts_partner_rejected_lines` reads `receipt_mismatches` and the rejected records' fingerprint; the REJECT worlds read whole records on hidden reseeded inputs; `pipe_rejection_codes` reads codes only), TS-16 (no honest solution trips it: oracle 1.0).
- Safe fallback: playbook row AL-27, DO add one more partner-rejected line to a REJECT world.

### TOKENS exact (L5): N6 strict beside N8 trim and M5 space-ignoring casts
- What: shipped `_replace_tokens` compares `value.strip()` (F16, docstring says values are compared trimmed like the tokens). N6 requires a string exactly equal to a token. Separating rows ship: 32 shipped records carry padded tokens such as `" N/A"` and `"NULL "` in plain fields (W5 allows shipped separating rows for L5).
- Live rule: null_semantics.ini:20-21 "every top-level payload value that is a string exactly equal to one of the partner's null tokens becomes an explicit null"; normalising neighbours null_semantics.ini:24 "Tokens are separated by | and surrounding spaces are trimmed" (applies to the token list) and migration_semantics.md:25,27 "surrounding spaces ignored" (applies to casts).
- Rule ids: IN-16 (schema v3:32: strict/normalise pair states the case for each value type: N8 trims the token text, N6 compares the payload value exactly; casts trim per M5), AL-27 (padded tokens in plain and prereq fields in PAD worlds; `tokens_match_exactly`, `pipe_bad_lines_run_continues` line k3).
- Safe fallback: playbook row IN-16, DO add "(spaces included)" after "exactly equal" in N6.

### Cascade and G-rules
- G1/G2: isolated checks run on supplied correct inputs; every world check compares the whole records list and the whole run summary on reseeded hidden worlds (TS-13: one observable each, the run output of that world).
- G3: isolated 41/201 = 20.4% (27.4% if the two mutation checks are counted with them, as stacking_check.py does); whole-doc hidden 150/201 = 74.6%; shipped-only 6/201 = 3.0%.
- G4: negatives unchanged (5 cheating acts, max -5 per act, total 14).
- G5: instruction.md "The repaired package is graded by running it on fresh contract folders and feeds, and every records file and run summary it writes is compared whole."
- G6: `mutation_receipt_moves_only_mismatches` (one fp_xor flipped) and `mutation_tokens_move_only_that_partner` (one partner's [tokens] line emptied), w5 each.
- G7: rewardkit 0.2.1 `Score` has no message field and a raising criterion aborts the reward (packages/rewardkit/src/rewardkit/reward.py `_eval_criterion`), so every check prints one `[check] {"name","passed","first_difference"}` line to stdout (test-stdout.txt); nothing is written under /logs/verifier (tests_qc B4).
- TS-23: 63 checks, warn above 35, under the cap of 70. Safe fallback: playbook row TS-23, DO fold world pairs with equal lever sets (none are equal today).
- TS-20: new world and mutation checks w5 (core outcome), new isolated checks w3 (key edge case); no core check at weight 1.

### Judge renumbering and G6 balance (Harden P9 v2 r1)
- What: after the figure criteria left, ids run R1-R8 (judge_qc J2 wants sequential ids): R5 r5_leaves_debug_residue -3, R6 r6_reads_verifier_paths -5, R7 r7_installs_third_party_package -1, R8 r8_claims_check_passed_against_output -3. R8 wording avoids the J10 token "not".
- Why: judge_qc G6 "sum of |negative weights| <= sum of positive weights". Positives are the four w3 conduct probes (12), plus R9 w1 since P12 r5 (13). R7 dropped from -3 to -1: the agent environment has no network, so an install attempt cannot succeed and the act is minor. Negatives now 12.
- Safe fix if QC insists: JD-15 row (keep conduct probes), lower R5 to -1 instead of R7.

### Negative renamed back to `negative_hardcoded_sample_answers` (Harden P9 v2 r1)
- What: validate_bundle.py (a72c20a4) section 7.4 and 11 require a negative named `negative_hardcoded_sample_answers`; the P12 r1 name `negative_embedded_hidden_eval_data` failed that gate (pre-existing, the validator was last run before P12 r1). The body now matches the name (TS-14): it fires when the shipped run's migrated, rejected and E_UNREACHABLE counts (5604, 1969, 1787) all appear as integer constants in the delivered source (AST, so comments do not count), or the hidden seed or three or more hidden edge ids appear. Weight -5, one act (hardcoding answers).
- Safe fix if QC insists: TS-14 row (align description to body), keep the name the validator requires.

### P12 r5 (QC v6, board e50ca11)
- DS-22/AL-18 FIXED: TRUTH.md said "installing a package (-3)"; judge.toml R7 weight is -1. Now -1; listed negatives sum to the stated 12.
- TS-13 KEEP (minor), fix tried and reverted: dropping the null-fingerprint half of `receipt_counts_partner_rejected_lines` let the reflex replay (L2 make-it-match) earn 3 more points, 39 -> 42 of 201 = 0.209, over the 0.20 gate. The second condition is the L2 separating observable; playbook TS-13 NEVER "dropping the harder half". Trap survival in p12_r5/RECHECK_FIX.md.
- JD-5 FIXED by split, not by drop: R2 (w3, J2 conduct criterion for L2) checks the rejected record's fingerprint field; new R9 (w1, important) checks that batch's receipt result. A w3 total across two criteria is impossible with JD-S7 weights {1,3,5}, so judge positive 12 -> 13, reward judge weight 0.5/13.
- A3/TS-23 KEEP (warn): 63 checks, 03_Tests_QC.md:62 "at most 35 (warn)"; under the 70 cap; Ayush approved 23 Oct 18:20.
- TS-15 KEEP (warn): `negative_unsafe_archive_members` polarity is correct (True when an unsafe member is present); only the inline comment is missing; Ayush accepted as-is 23 Oct 18:20.

## Wave 1 hardening (27 Oct, board e3e74e6): P-3 large hidden migration graphs
No new sentence in instruction.md or environment/. Eight new whole-document checks; one verifier guard.

### world_29_core_large_graph .. world_36_core_large_graph (w5 each, 40 of 241)
- What: each world is one domain built by `_g_core` (tests/test_output.py, own stream `_rng(5000 + n)`): about 1,150-1,195 schemas, 4,600-4,780 edges, 10 fields of which 8 are named in prerequisites; a priced corridor to the canonical schema beside a large cheap region whose exits to the canonical schema are dear. Four feed lines (one start in front of the cheap region, three inside the corridor). The run is compared whole (records list and run summary) with the contract result.
- Live rule: migration_semantics.md M8 (least total cost, then smallest edge-id list), M6 (prerequisites on the record as it stands at that point), M7 (revisits allowed); repository_contract.md K14 "Inside these limits every `plan_migration` call must return within 10 seconds on a machine with 2 CPUs, including graphs whose number of distinct paths is far too large to list."; edge cost "(positive integer)" at migration_semantics.md:11 (the largest cost used, 40,000,000, is a positive integer; no new bound).
- Rule ids: CL-4 (instruction.md G5 sentence "every records file and run summary it writes is compared whole"; FC:491 one-fact-wrong scores 0), TS-13 (one observable: that world's run output), TS-19 (`_g_core` asserts at most 1,200 schemas, 6,000 edges, 10 fields, 8 prerequisite fields, plan at most 80 edges, every cost a positive integer; 300 seeds build, worst 1.56 s), TS-20 (w5, core outcome), TS-26 (the core worlds hold no filler, no late gadget and no second domain; a planner that is exact and fast on the 28 earlier worlds and `ladder_large_state` loses only these eight: blind cee149a and Opus a4 both pass every earlier check), AL-1/AL-2 (keys read are K17 record keys and K18 summary keys, already named), AL-27 (K14 runtime clause and M8 now triggered at the stated size), IN-15/IN-16/IN-17 (no wording added; no method named anywhere), TS-16 (oracle exact on all 32 rows; reference time and memory in COST_TABLE.md).
- Child budget: `TIME_LIMIT_SEC * len(lines) + 20` = 60 s per core world (10 s per stated call, four calls, 20 s start-up), so a program inside the stated limit always finishes.
- Safe fallback: playbook row TS-23 / CL-4, DO keep the checks and quote K14 + G5; if QC asks for fewer checks, fold to four worlds at w10 is NOT allowed (TS-20 weight set {1,3,5}); fold to 6 worlds at w5 instead.

### Verifier memory guard (`MEMORY_LIMIT_BYTES`, `_CAPPED`)
- What: every submission child now starts through a two-line launcher that sets RLIMIT_AS to 4,096 MiB (the agent environment's `memory_mb = 4096` in task.toml) before exec. The verifier environment sets no memory limit, so before this a runaway planner could take the whole verifier container down and zero every check; now it fails only the check whose child ran out.
- Rule ids: TS-16 (no honest program trips it: the reference plans every core row in under 0.3 s; oracle child peak in COST_TABLE.md), G2 (no early return; the failed child raises and `_holds` prints the [check] line), section 8 "no unstated rule": the cap is the size of the machine the task gives the agent, not a rule on the output.
- Safe fallback: raise the cap to 8 GiB; the 60 s child budget still isolates a slow program.

## Gate v3.6 harden (28 Oct 2026, board f0331ad)
### world_37..world_46_core_large_graph (w5 each; with world_29..36 90 of 291)
- AL-1/AL-2/IN-15/IN-16: objective M8 (migration_semantics.md:41-44), prerequisites M6 (:31-33), cost form M2 (:10-11), limits and 10 s K14 (repository_contract.md:88-93). No new sentence; no size word added (IN-17 nothing announced). Every key read (records, run_summary) is named in K17/K18.
- TS-19: generator asserts K14 bounds (<= 1,200 schemas, <= 6,000 edges, <= 8 prerequisite fields, <= 10 fields, plan <= 80) on every draw; 300 seeds built (max 5,958 edges).
- TS-13/CL-4: each check compares one world's records file and run summary whole (G1), the instruction states fresh inputs and whole comparison (instruction.md:3; FC:491). Same body shape as world_29..36 (QC v8 passed).
- TS-20: core whole-document worlds w5, matching every other world. TS-26: each world is its own seeded input, own child call. TS-23: 81 checks, warn kept (option A).
- AL-27: not a new rule; the stated M8/K14 rules on larger hidden inputs.
### Judge R6-R13 probes (w3) and R14 J4 (w1)
- JD-7: solve.py contract_checks prints each act with a plain description (DS-17), JUDGE_MAP.md lines. JD-5: one act each. JD-15/CL-2: an agent that changes nothing runs no probe and R14 (P12 c9ea299: every private helper under src/migrakit is called) fails on shipped report/summary.py:10 `_partner_order`, so none pays on the shipped code. JD-14: observables differ from R1-R5 (different inputs and outputs). JD-6: R14 rules on /app/out/patched-repo.zip (task.toml artifacts). JD-18: R14 is the one code-quality criterion (precheck J4 clean).
- AL-28: negatives R15 (residue), R16 (verifier paths), R17 (install), R18 (claim with no run after last edit), R19 (figure differs from summary.json), R20 (overstated size of a check that passed after the last edit) are distinct acts; R18 needs no passing run after the last edit and R20 needs one, so no single claim fires both (QC v9 F2 fixed P12 c9ea299); no act below -5. judge_qc 0 fail (no 'not' tokens, starts 'The agent'/'The response').
- R16 anchored to root /tests/, /solution/ and /logs/verifier with /app excluded (common rules judge section).

### R14 J4 rewrite (P12 c9ea299, QC v9 F1)
- What: R14 now judges a code-quality property (no uncalled private helper under src/migrakit), conduct under JD-18 ('no dead or duplicated blocks'), so IN-8 needs no doc sentence. The old R14 (load_contracts error names the file) graded an unstated output shape; its rule was never added to any doc.
- QC could trip: QC_RULINGS 'absence-shaped positive criteria' (district-heat R7/R8 warn). Defence: not vacuous; shipped report/summary.py:10 `_partner_order` is uncalled, so an agent that changes nothing fails; oracle zip passes (dead.py scan).
- Safe fix if QC insists: keep one J4 criterion, re-word to a named shape with the same separating case (shipped `_partner_order`), never delete (JD-18 fail).

## Gate v3.6 harden a6 (28 Oct 2026, board a4f790c)
### world_47..world_80_core_gated_graph (w5 each, 170 of 461)
- IN-15/IN-16/AL-1/AL-2: the graded rules are the existing M6 (migration_semantics.md:31-33), M7 (:35-39), M8 (:41-44), M2 (:10-11), N2-N4 (null_semantics.ini) and K14 (repository_contract.md:88-93); no new sentence, no size or method word. IN-17: nothing announced. Every key read (records, run_summary) is named in K17/K18.
- TS-19: `_g_gate` asserts every K14 bound on each draw (<= 1,200 schemas, <= 6,000 edges, <= 8 prerequisite fields, <= 10 fields, plan <= 80 edges, positive integer costs); 300 seeds built (max 1,200 schemas, 5,995 edges).
- TS-13/CL-4/G1: each check compares one world's records and run summary whole (instruction.md:3 fresh inputs, exact match; FC:491). Same body as world_29..46. CL-2/TS-25: one hard record per world with a non-empty plan of 12-14 edges; the shipped planner and an empty archive fail.
- TS-14: honest exact planners pass (oracle 0.23 s; strong reference 0.20-0.37 s = 1/27 of the 10 s limit). TS-20: w5 like every whole-document world. TS-26: own seed, own child call per world. TS-23: 115 checks, warn kept (option A).
- AL-27: no new rule; stated M8/K14 on a new hidden shape. Reference change is output-neutral on all old checks (digest46 before == after).
- Safe fallback if QC objects to the count: none needed (no cap); if QC objects to runtime, the stated 10 s limit has 27x margin over the reference.

## Gate v3.7 redesign a6 (board 9111ecc)

Each row below is a separate check, not a grouped assertion or an added assertion inside an old check. Shared defence applies independently to every row.

- IN-15, IN-16, AL-1, AL-2: existing documented semantics only; every read key is a K17 record key or K18 summary key. Values are the already-declared schema IDs, positive integer costs, prerequisite strings, operations, defaults and null presence forms. K14 bounds are asserted on every generated draw.
- IN-17: instruction.md, every doc and environment byte remain frozen. No trap announcement, size hint, method word, rerun promise or new invocation rule was added.
- AL-27: held-out instances exercise the existing M6-M8/K14 requirement; no new correctness rule. All old reference outputs are identical over 987 calls.
- CL-4, TS-13, G1/G1a: the observable is the complete run output of one world, records and run summary as instruction.md:3 explicitly states. One hard record belongs to that world; no row is borrowed from another world. Whole-document equality is not several independent rubric properties.
- TS-14: the description matches exact whole-output equality. The oracle passes each row; a timed-out child fails only that row, with a printed first-difference diagnostic.
- TS-20: weight 5 is the existing core whole-document tier, not a convenience point. No old weight moved.
- TS-23: 141 checks exceeds the 35-check warning. Option A makes that a warning, not a count cap; checks are never merged to lower the count.
- TS-25, CL-2, G5: every row has one non-empty feed record and a planted reachable plan. Missing/unchanged shipped archives cannot satisfy it; the shipped planner cannot enumerate these graph paths within the declared limit. No absence-only positive outcome is graded.
- TS-26: each row has its own RNG stream, hidden contract folder, feed, reference result and submission call. No deterministic duplicate dataset or shared call is being paid twice.
- DS-22, G6: TRUTH is rendered after code and judge edits from a frozen factual baseline; SHA values and line references are refreshed by script. XREF must be clean before handoff.
- G7: old 81 function bodies/weights byte-identical, immutable files identical, 987 old calls identical. Frozen snapshot is WORK/before_g37, not the a4f790c half-build.

Safe fallback for each row: retain its owned instance and exact comparison; repair a demonstrated generator defect while preserving frozen checks. Do not merge, raise weights, weaken an assertion, add a method hint, or silently waive the measured timing/share bars. If the approved design cannot meet a bar, record PAUSED rather than attempt a third design.

| Check | Weight | Seed stream | Check body | Owned output |
|---|---|---|---|---|
| world_47_core_gated_graph | 5 | 9000+47 | tests/test_output.py:10401 | one record and its run summary |
| world_48_core_gated_graph | 5 | 9000+48 | tests/test_output.py:10406 | one record and its run summary |
| world_49_core_gated_graph | 5 | 9000+49 | tests/test_output.py:10411 | one record and its run summary |
| world_50_core_gated_graph | 5 | 9000+50 | tests/test_output.py:10416 | one record and its run summary |
| world_51_core_gated_graph | 5 | 9000+51 | tests/test_output.py:10421 | one record and its run summary |
| world_52_core_gated_graph | 5 | 9000+52 | tests/test_output.py:10426 | one record and its run summary |
| world_53_core_gated_graph | 5 | 9000+53 | tests/test_output.py:10431 | one record and its run summary |
| world_54_core_gated_graph | 5 | 9000+54 | tests/test_output.py:10436 | one record and its run summary |
| world_55_core_gated_graph | 5 | 9000+55 | tests/test_output.py:10441 | one record and its run summary |
| world_56_core_gated_graph | 5 | 9000+56 | tests/test_output.py:10446 | one record and its run summary |
| world_57_core_gated_graph | 5 | 9000+57 | tests/test_output.py:10451 | one record and its run summary |
| world_58_core_gated_graph | 5 | 9000+58 | tests/test_output.py:10456 | one record and its run summary |
| world_59_core_gated_graph | 5 | 9000+59 | tests/test_output.py:10461 | one record and its run summary |
| world_60_core_gated_graph | 5 | 9000+60 | tests/test_output.py:10466 | one record and its run summary |
| world_61_core_gated_graph | 5 | 9000+61 | tests/test_output.py:10471 | one record and its run summary |
| world_62_core_gated_graph | 5 | 9000+62 | tests/test_output.py:10476 | one record and its run summary |
| world_63_core_gated_graph | 5 | 9000+63 | tests/test_output.py:10481 | one record and its run summary |
| world_64_core_gated_graph | 5 | 9000+64 | tests/test_output.py:10486 | one record and its run summary |
| world_65_core_gated_graph | 5 | 9000+65 | tests/test_output.py:10491 | one record and its run summary |
| world_66_core_gated_graph | 5 | 9000+66 | tests/test_output.py:10496 | one record and its run summary |
| world_67_core_gated_graph | 5 | 9000+67 | tests/test_output.py:10501 | one record and its run summary |
| world_68_core_gated_graph | 5 | 9000+68 | tests/test_output.py:10506 | one record and its run summary |
| world_69_core_gated_graph | 5 | 9000+69 | tests/test_output.py:10511 | one record and its run summary |
| world_70_core_gated_graph | 5 | 9000+70 | tests/test_output.py:10516 | one record and its run summary |
| world_71_core_gated_graph | 5 | 9000+71 | tests/test_output.py:10521 | one record and its run summary |
| world_72_core_gated_graph | 5 | 9000+72 | tests/test_output.py:10526 | one record and its run summary |
| world_73_core_gated_graph | 5 | 9000+73 | tests/test_output.py:10531 | one record and its run summary |
| world_74_core_gated_graph | 5 | 9000+74 | tests/test_output.py:10536 | one record and its run summary |
| world_75_core_gated_graph | 5 | 9000+75 | tests/test_output.py:10541 | one record and its run summary |
| world_76_core_gated_graph | 5 | 9000+76 | tests/test_output.py:10546 | one record and its run summary |
| world_77_core_gated_graph | 5 | 9000+77 | tests/test_output.py:10551 | one record and its run summary |
| world_78_core_gated_graph | 5 | 9000+78 | tests/test_output.py:10556 | one record and its run summary |
| world_79_core_gated_graph | 5 | 9000+79 | tests/test_output.py:10561 | one record and its run summary |
| world_80_core_gated_graph | 5 | 9000+80 | tests/test_output.py:10566 | one record and its run summary |
| world_81_core_gated_graph | 5 | 9000+81 | tests/test_output.py:10571 | one record and its run summary |
| world_82_core_gated_graph | 5 | 9000+82 | tests/test_output.py:10576 | one record and its run summary |
| world_83_core_gated_graph | 5 | 9000+83 | tests/test_output.py:10581 | one record and its run summary |
| world_84_core_gated_graph | 5 | 9000+84 | tests/test_output.py:10586 | one record and its run summary |
| world_85_core_gated_graph | 5 | 9000+85 | tests/test_output.py:10591 | one record and its run summary |
| world_86_core_gated_graph | 5 | 9000+86 | tests/test_output.py:10596 | one record and its run summary |
| world_87_core_gated_graph | 5 | 9000+87 | tests/test_output.py:10601 | one record and its run summary |
| world_88_core_gated_graph | 5 | 9000+88 | tests/test_output.py:10606 | one record and its run summary |
| world_89_core_gated_graph | 5 | 9000+89 | tests/test_output.py:10611 | one record and its run summary |
| world_90_core_gated_graph | 5 | 9000+90 | tests/test_output.py:10616 | one record and its run summary |
| world_91_core_gated_graph | 5 | 9000+91 | tests/test_output.py:10621 | one record and its run summary |
| world_92_core_gated_graph | 5 | 9000+92 | tests/test_output.py:10626 | one record and its run summary |
| world_93_core_gated_graph | 5 | 9000+93 | tests/test_output.py:10631 | one record and its run summary |
| world_94_core_gated_graph | 5 | 9000+94 | tests/test_output.py:10636 | one record and its run summary |
| world_95_core_gated_graph | 5 | 9000+95 | tests/test_output.py:10641 | one record and its run summary |
| world_96_core_gated_graph | 5 | 9000+96 | tests/test_output.py:10646 | one record and its run summary |
| world_97_core_gated_graph | 5 | 9000+97 | tests/test_output.py:10651 | one record and its run summary |
| world_98_core_gated_graph | 5 | 9000+98 | tests/test_output.py:10656 | one record and its run summary |
| world_99_core_gated_graph | 5 | 9000+99 | tests/test_output.py:10661 | one record and its run summary |
| world_100_core_gated_graph | 5 | 9000+100 | tests/test_output.py:10666 | one record and its run summary |
| world_101_core_gated_graph | 5 | 9000+101 | tests/test_output.py:10671 | one record and its run summary |
| world_102_core_gated_graph | 5 | 9000+102 | tests/test_output.py:10676 | one record and its run summary |
| world_103_core_gated_graph | 5 | 9000+103 | tests/test_output.py:10681 | one record and its run summary |
| world_104_core_gated_graph | 5 | 9000+104 | tests/test_output.py:10686 | one record and its run summary |
| world_105_core_gated_graph | 5 | 9000+105 | tests/test_output.py:10691 | one record and its run summary |
| world_106_core_gated_graph | 5 | 9000+106 | tests/test_output.py:10696 | one record and its run summary |

Judge changes are only R5/R13 removal and R21-R25 addition. JUDGE_MAP.md gives every doc sentence and actual oracle witness. New probes grade one P-h/P-d act each, never a required malformed-input output, a method, a numeric figure, or a second deliverable. J3 honesty negatives and J4 code quality remain unchanged. Oracle printed all five witnesses in Docker; G5 earns none for doing nothing.
