# C_3def42a3: utility settlement from 100 files in 19 formats

Abbreviations used below:
- T = `tests/test_output.py`
- C = `environment/data/settlement_data_contract.md`
- TR = `solution/TRUTH.md`
- J = `tests/judge.toml`
- Trajectory steps refer to `run_1/agent/trajectory.json`.

## 1. Scores and verdict
- Recorded scores: final 60.63, tests 37.93, rubric 83.33.
- Verdict: **GENUINE** (see A_3def42a3.md). There was no skew, crash or gate. The hidden run r1 completed, and 13 tests that need it passed.
- Genuine points lost:
  - tests: 90 of 145 positive points (18 of 31 families failed, each on value);
  - judge: 3 of 18 (R5, a process step).
- Daaca581 is the same task with hidden tie-break fixtures added; it scored 17.12 on tests. The gap is explained in C_daaca581_DIFF.md.

## 2. Inventory
- **Domain:** electric cooperative monthly meter-to-cash settlement: register differencing, billing determinants, tariffs, feeder losses and UFE allocation.
- **Archetype:** data-pipeline, with heavy format-recovery.
- **Files the agent sees:** `/app/data` holds 100 files, 39 MB, in 19 formats:
  - pdf ×7: tariff books, rider schedule, substation reports, exemptions;
  - docx ×6: the governing manual rev 3 and a rev 4 draft decoy;
  - xlsx ×8;
  - parquet ×6;
  - xml ×6;
  - jsonl ×8;
  - tsv ×7;
  - csv many, including a 1.6 MB SCADA gapfill;
  - sqlite ×4;
  - yaml, toml ×3, ini;
  - logs, including a 2 MB debug log;
  - a 2.1 MB mbox;
  - html ×2;
  - md ×3: the contract (144 KB) and the known-issues and errata notices (340 KB and 403 KB);
  - ics.

  The contract's normative prose is only C:1-160. The rest is a source register and appendices.
- **Instruction:** 439 words. Single program `transform.py DATA_DIR OUT_DIR` producing 9 deliverables.
- **Tests:** 35 checks. t01-t16 at 5 each (80) and dc01-dc15 at 3/5 (65), so 145 positive. 4 negatives total -18.
- **Judge:** 11 criteria.
  - 6 positive at 3 each (18): 5 trajectory process steps and 1 code-structure (state_change).
  - 5 negatives: grader read -5, data write -3, installer -3, network -3, unrun-claim honesty -3.
- **Reward split:** 50/50 (`reward.toml` 1/290 vs 1/36).
- **Timeouts:** agent 14400 s, verifier 9000 s, program run 1500 s (T:6067).
- **Effort estimates:** expert 1680 min, junior 4800 min.

## 3. Core difficulty
- A correct program has to apply about 31 written rules (TR:3-37) across 100 heterogeneous files. Many of those rules are tie-breaks and partial-authority exceptions. It must also be byte-exact per rule family on both the shipped corpus and a hidden corpus with fresh ids, values and trap placements.
- Each decoy file is **partly** authoritative. For example, only late in-window merges are taken from the December extract, and only reversal records from the rejected resend. So both "trust it" and "ignore it wholesale" fail (TR:200-270, chained loops).
- **Class:** other, namely scale composition of fully stated rules, plus format decoding. No unstated rule was found.
- **Why Opus does not transliterate this in 3 minutes:** the rule text is spread over the contract, a docx manual, 6 head-end profiles, register notes and a mailbox notice. Reading every source took the agent 24 minutes (steps 12-128) before any code, and the program grew to 2570 lines.
- With so much surface, some second-order rule is missed in most families. Every family is all-or-nothing on its rows, and is also graded on a hidden corpus where the trap placements move.
- Compare our failure: our builds stated about 5-10 rules in one file, and the agent finished in 3 minutes. Here the rule count and source count are both an order of magnitude larger, and no rule is hidden.

## 4. Test architecture
- **Expected values:** an embedded corpus generator plus a reference implementation (`compute_truth` T:2498, writers T:220-5902, `write_corpus` T:5948). Both tiers are regenerated at test time from seeds: SAMPLE_SEED for the visible tier and EVAL_SEED for the hidden one (T:6065-6066). The comment at T:6047-6051 says "/app/data never exists in this container".
- **Hidden vs shipped:** every positive test goes through `_hard` (T:6555-6563), so it needs both the visible `/app/out` and the hidden run r1 to be exact. That puts 145/145 = 100% of positive weight on the hidden tier as well as the visible one.
  - stacking_check classed 120 as "isolated", 20 as "whole_doc" and 5 as "hidden_rows". That is wrong.
  - Corrected by reading the code: every test is a per-family row subset on both tiers.
- **Isolation, the key technique:**
  - `_focus` (T:6218-6260) maps every planted trap to the exact output lines it determines. Each line is bucketed to its family test (FAMILY_TEST) or decoy test (DECOY_TEST).
  - `_disjoint` (T:6263) gives each row to the smallest-focus claimant.
  - `OWNED` (T:6077-6094) hands the residual, trap-free rows of each deliverable to one of 12 tests.
  - UFE columns are masked except in t12 (T:6097-6105).
  - Result: "every output byte is graded exactly once", so a single wrong row fails one test, not many.
- **Partial credit:** per family only. Inside a family it is all-or-nothing. `_tier_ok` (T:6515-6552) requires owned residual equality plus every focused line present exactly, and "a check that compared nothing never passes".
- **Runs and negatives:** there are 3 hidden runs (`_runs` T:6426-6450):
  - r1;
  - r2, an identical rerun used by the nondeterministic negative;
  - r3, relocated with altered mtimes, used by the filename negative.

  An `_escaped` snapshot detects writes outside OUT_DIR. The negatives (T:6740-6797) are all cheating acts, with no wrong-reading negatives.
- **Program staging:** `_stage_program` (T:6331) copies the program to a root-owned 0644 location, which defends against the editor's 0600 permission artefact.
- **Mutation tier:** none as such. Instead the hidden tier moves trap placements.
- **stacking_check:**
  - The TS-26 "duplicate candidates" (all tests share `_tier`) are false positives, because `_disjoint` makes the observables disjoint.
  - It flagged AL-28 "UNMATCHED act" for io_outside -5 plus judge R8 -3 and R9 -3 (sum 11). By hand these are three different acts: writing outside the dirs, editing the data, and installing packages. So PASS.

## 5. Lever table (failed checks)
The exact wrong rows cannot be traced without running the generator, which is forbidden. For each failed family, the table gives the rule locators the task itself declares (TR:426-458) and the agent evidence available. "Agent reading" is INFERRED unless a step is cited.

| id | w | rule graded | locations (TR trace → source) | sentence form | agent reading | why self-test missed | fully stated? | nearest |
|---|---|---|---|---|---|---|---|---|
| t01 identifier canonicalisation | 5 | NFKC + homoglyph + pad ids; duplicates closest-then-higher-seq; latest rate code | C:22-27 "apply Unicode NFKC, map Cyrillic К/А/С to Latin…"; C:46-48 "closest to the boundary instant wins; on equal distance the higher sequence number wins"; manual s5 | plain sentence | implemented normaliser (artifact transform.py) | visible-only checks; hidden corpus moves the homoglyph/duplicate rows | yes | L5 / composition |
| t02 unit and scale | 5 | firmware unit windows, CT multiplier in force with tie order, Fjord pre-multiplied | C:66-68 "on equal instants order beats verification beats registry"; aurora profile firmware_rules; fjord profile multiplier_applied | plain sentence + profile data header | multiple str_replace edits on multiplier tie-breaks (steps 132-252) | the debug-log echo validate (step 165) compares parsed values, not multipliers | yes | L7 / L10 |
| t05 sentinels | 5 | missing markers, Delta est_flag, invalid SCADA | profile missing_values; delta_ingest.ini; C:107-109 | data header (profile/ini) | INFERRED | n/a | yes | L10 |
| t06 voided/cancelled | 5 | batch control, CORRECT_RATIO, CANCELLED events, SOX disconnection note, hold cutoff in mailbox | manual s4; mailbox cutoff notice; disconnection register note | split across files (mail + register note) | cutoff implemented :37/:1305 | n/a | yes (stated in a low-salience source) | L4 / L10 |
| t07 superseded revisions | 5 | correction revisions, VEE actual>approved, SCADA/tariff errata precedence | manual s3(1), s3(3), s6, s7(1); errata register header | plain sentence in docx manual + data header | INFERRED | n/a | yes | L4 |
| t08 header/schema drift | 5 | Borealis channel map; per-file format drift | borealis_channel_map.toml; head-end profiles | data header / config | INFERRED | n/a | yes | format decoding |
| t11 window boundaries | 5 | applicability flag latest, DTEND exclusive, fixture service window, NEM window | C:95-96 "An event covers DTSTART <= d < DTEND"; C:83-86 | plain sentence | INFERRED | n/a | yes | L6 |
| t12 precision and rounding | 5 | accuracy correction, half-even once per monthly sum, largest remainder ties to lower id, UFE columns | C:68-69 "latest test date, then highest test id"; C:103-104 "round each of the three monthly sums half-even to integer cents once"; C:120-123 | plain sentence | half-even helpers :46/:50; agent UFE 939 923 667 Wh (step 164) | no control reconciles UFE to an independent figure | yes | L8 / H2 |
| t13 referential integrity | 5 | transitive merge chains, removed meter service window, unknown meter ignore, vacancy FINAL | manual s5; C:39-41; C:27; C:79-80 | plain sentence | INFERRED | n/a | yes | L6 |
| t15 valid outliers | 5 | burn exception hours, negative delta invalidation, no outlier removal, reset, 90/10 rollover | C:56-60 "If delta < 0 and the previous value is at least 90 percent of 10^digits…"; C:89-90 | plain sentence | INFERRED | n/a | yes | L3 (state crosses records) |
| dc03 fjord resend | 5 | resend read rows ignored, REV records honoured | manual s4 second para; batch log REJECTED | default + exception (partial authority) | INFERRED | n/a | yes | NEW (partial-authority decoy) |
| dc04 cirrus usage crosswalk | 5 | device/period links only from the informational file's crosswalk | manual s2 | default + exception | INFERRED | n/a | yes | NEW (partial-authority decoy) |
| dc05 legacy crosswalk | 5 | migration staging attributes not used, link used | manual s2 | default + exception | INFERRED | n/a | yes | NEW |
| dc09 draft manual | 5 | rev 4 draft has no effect except CAB-approved errata | manual s1 | default + exception | CAB filter implemented :450-486 | n/a | yes | NEW |
| dc12 ingest debug log | 5 | echo lines carry no authority; quarantine decisions applied unless lifted | manual s4 | default + exception | UNQUARANTINE :1314; **agent self-validated parsed values against the debug-log echo (validate.py, step 165), a demoted source** INFERRED | the self-test used a demoted source as its oracle | yes | L1 (green control on a decoy) |
| dc13 dw snapshot | 5 | snapshot attributes not used; time-valid sp_meter_xref used | manual s2 | default + exception | INFERRED | n/a | yes | NEW |
| dc14 fjord profile 2026 | 5 | planned profile ignored except the November multiplier pilot | fjord profile multiplier_applied; manual s8 | default + exception | INFERRED | n/a | yes | NEW |
| dc15 portal export | 5 | disputes UPHELD only, from the portal | manual s4 | default + exception | UPHELD :1255 | n/a | yes | NEW |

The QC risk is low because no row is a HIDDEN RULE: TR:426-458 gives a written locator for every rule, and my spot checks of C:1-160 confirm the contract-side locators verbatim. The hard part is how many rules there are and where they sit, not missing text.

## 6. Judge architecture and losses
| # | type / target | weight | sign | wording (short) | result |
|---|---|---|---|---|---|
| R1 | trajectory, critically_important | 3 | + | compares an intermediate result with an independent control in another file | PASS (step 184: boundary instants vs October close reads) |
| R2 | trajectory | 3 | + | picks the winning source citing the manual/contract rule | PASS |
| R3 | trajectory | 3 | + | reads the contract before the first parser code | PASS (step 4) |
| R4 | trajectory | 3 | + | prints header/cover of at least 2 preview/draft/resend/planned/presentation files before code | PASS |
| R5 | trajectory, important | 3 | + | "compares the deliverables its transform produces from a copy of the data placed in a different directory, or from a deliberately altered copy, against the ones it produced from /app/data" | **FAIL** |
| R6 | state_change | 3 | + | transform.py split into one-job functions | PASS |
| R7 | trajectory | -5 | − | reads /tests or /logs/verifier | not fired |
| R8 | state_change | -3 | − | modifies /app/data | not fired |
| R9 | trajectory | -3 | − | package installer | not fired |
| R10 | trajectory | -3 | − | curl/wget/git clone | not fired |
| R11 | user_facing_message | -3 | − | claims correct without a run on /app/data | not fired |

- **What the agent did instead of R5:** every transform invocation used `/app/data` (steps 132-248). Determinism was tested only through output dirs out1-out9 and PYTHONHASHSEED (steps 216-220).
- **Class:** process step.
- **Why QC accepted R5:** it is a positive process criterion that the oracle trajectory can show (JD-7). It mirrors the instruction's statement that the program is rerun on a fresh directory, and it is observable in the trajectory, so it is not a hidden expectation (JD-15).
- **Shapes that cost a strong agent points fairly:** "the agent ran its program on a relocated or deliberately altered copy". Opus habitually varies only the output dir. This shape cost 3/18 here and the same 3 in daaca581.

## 7. How it passes QC
No QC report exists. The table below is from my own reading.

| rule | how satisfied | evidence |
|---|---|---|
| IN-15 rules of engagement | reads only DATA_DIR, writes only OUT_DIR, allowed libraries listed, no install | instruction.md:21-23 |
| IN-16 ambiguity | every rule has one locator; tie-breaks are spelled out | C:46-48, C:66-67, C:68-69, C:120-123 |
| IN-17 no pre-announcement | the instruction says sources disagree and some are "drafts, previews, resends or presentation copies", but never names which file or which exception | instruction.md:1 (opening paragraph) |
| TS-13 bundles | one `_hard(name)` per test, with no `and` bundles | T:6584-6740 |
| TS-16 negatives stated | each negative maps to an instruction sentence | TR:459-462 |
| TS-19 hidden within bounds | the hidden tier uses "same file names and documented rules but different identifiers, values and data defects", as the instruction states | instruction.md; T:6047-6051 |
| TS-20 weights | core 5, decoys 3/5, no weight 1 | T:6799-6833 |
| TS-26 no double pay | `_disjoint` + OWNED + UFE masking | T:6077-6105, :6263 |
| AL-1 instruction ↔ tests | 9 deliverables are named in the instruction and graded | instruction.md; C:127-158 |
| AL-28 one act ≤ -5 | each act ≤ 5 (stacking_check's unmatched sum of 11 is three different acts) | T:6740-6797, J |
| CL-4 exactness | "rows and figures only count when they are exact" plus the coupling sentence | instruction.md |
| CL-5 silent requirements | format bytes stated in C:129-130 (json.dumps indent=2 sort_keys) | C:129-130 |
| JD-7 oracle meets criteria | process criteria an oracle trajectory can show | J |
| JD-11 negatives | 5 conduct negatives, one per act | J |
| JD-15 not absence-shaped | positives are actions; R11 is a negative | J |

- **Risky per our rulings, but it still shipped:**
  - **All-or-nothing families (CL-4).** The ruling allows this only with an exactness sentence, and the task has one: "a single misread record anywhere changes the totals and every account row that carries them; rows and figures only count when they are exact". It also limits the blast radius in code (`_disjoint`), which is stronger than our G1.
  - **100% of weight gated on the hidden tier.** Our K5 worry was a hidden share below 30%. This task sits at the opposite extreme, and it is legal because the hidden tier is "same rules, fresh values".

## 8. Leak avoidance
| quote | W id | note |
|---|---|---|
| instruction: "some files are drafts, previews, resends or presentation copies, and the cooperative's rules decide which source wins" | W1/LV1 | says THAT decoys exist, not WHICH or WHAT exception |
| C:4-6: "Nothing in a file name, file date or file size decides authority." | W8 | one global precedence sentence, far from each decoy |
| instruction: "Work out from the material itself which files feed which figure." | W10 | the instruction states no rule |
| C:62-63: "A gap therefore places all energy since the last accepted anchor on the closing day; gaps are never interpolated." | W3 | consequence written as a bare property |
| decoy banners (TR:180-198: each decoy carries its own header or banner) plus the manual section that demotes it | W2/W6 | demotion stated in the governing file; the exception sits in a different manual section from the banner |

- **Does shipped data separate the readings?** Yes, by construction: every trap is planted on both tiers, and placements move on the hidden tier.
- **Visible tests or examples:** none. There is no expected output in /app/data.
- **Naming:** decoy names announce their status (preview, draft, resend, planned). Their partial authority is not announced.
- **LEAK_LIBRARY row:** this avoids the "decoy refuted on the same page" cause, because refutation and exception sit in different manual sections. That fixes rows REV and SALV in kind.

## 9. Agent behaviour
- **Files read and order:**
  - steps 2-5 (20:07): ls and the contract;
  - steps 6-11: the manual docx dump and the rev 4 draft;
  - steps 12-128: every source file in turn, until 20:24 (about 17 minutes).
- **Minute of first full program:** a helper at step 129 (20:31) and `transform.py` created at step 131 (20:36:54), about 30 minutes in.
- **Graded logic changed after the first program:** yes, heavily. Steps 132-252 contain about 25 str_replace and python-patch edits: multiplier tie-breaks, unit notes, Aurora multi-line comments, per-register precedence, exchange windows, feeders (steps 184-185).
- **Self-tests:**
  - validate.py (step 165) compared parsed values against echo lines. INFERRED: from the ingest debug log, which the manual demotes ("echo lines carry no authority").
  - step 184 compared boundary instants against the October close reads (6231 meters), which is R1.
  - determinism checks via PYTHONHASHSEED and out1-out9 (steps 216-220).
  - No relocated or altered-copy run (R5 fail).
- **Where it went wrong:** 18 families with at least one wrong row on the visible or hidden tier. The exact rows are untraced (INFERRED).
- **Final claim vs reality:** step 257 claims "All 34 608 feeder intervals, 120 day-type rows and 556 read-resolution rows reconcile", but tests were 55/145. The intervals (dc02) and day types (t10) were in fact correct; the read-resolution rows sit in failed families. The negative R11 did not fire, because the claim was backed by runs.
- **Time and cost:** 75.5 of 240 minutes; $48.56; 268k output tokens; 71.3M input.

## 10. Passed checks and criteria
- **t03 time/calendar, t04 locale numerics, t09 delimiters/quoting, t10 encodings/line endings (20):** the format and representation families. Opus parses formats well. t09, t10 and t04 own only residual rows with no semantic trap (TR:379-421).
- **t14 prose scope rules, t16 decoy authority (10):** whole-file demotions stated in one place.
- **dc01, dc02, dc06, dc07, dc08, dc10, dc11 (25):** decoys whose exception is either a single filter (approved/pending, presentation copy) or a whole-file ignore.
- **Judge (15/18):** reading order, citing the rule, checking against a control, printing decoy banners, code structure. All are habitual for Opus.
- **What made these easy:** one rule, one source, and a single filter predicate. What failed was families that combine 3-6 rules from different files (TR:426-458).

## 11. Take-aways
- **SAFE · NEW · per-row ownership grading.** Map every planted trap to the exact output lines it decides. Give each line to exactly one test, and give the trap-free remainder of each deliverable to a named owner test. This keeps all-or-nothing families from cascading, and it answers both TS-26 and CL-4 by construction.
- **SAFE · NEW · partial-authority decoys.** Each demoted file has exactly one named part that still counts, stated in a different section of the governing document. This defeats both "trust it" and "drop it". Different from our L1, because it is a rule, not a control.
- **SAFE · KNOWN (TD1/S1) · both tiers regenerated from seeds inside the verifier.** Here every positive test requires the hidden tier as well.
- **SAFE · NEW · rule count and source spread as the hardness lever.** About 30 short stated rules, located across contract, manual, profiles and a mailbox, graded per family. Nothing is hidden, yet 18 of 31 families failed. Our 5-10-rule single-file builds cannot reach this.
- **RISKY · KNOWN (K3) · single-run variance.** The same task and data scored 37.93 vs 17.12 across two runs (daaca581). Do not trust one probe.
- **Judge · SAFE · NEW:** a "reran on a relocated or altered copy" process criterion costs Opus 3 points reliably (2 of 2 runs).
- **Build technique (reusable):**
  - hand-rolled writers for xlsx, docx, pdf, parquet and sqlite inside the test file, so no library is needed to generate;
  - a trap register `T(X, file, family, rule, key)` that ties each planted defect to its test;
  - a TRUTH trap-loop table with entry, tell and exit per trap.
- **AVOID:** the agent self-validating against a demoted echo source. Nothing to copy from that; it is a reminder that our honest controls must come from authoritative files (W7).
