# C_8764bfdd — estatectl consolidation repair (Data Processing, Aditya Patel)

Paths: T = `Anubis_Tasks_Samples/Final_Delivery/8764bfdd-69b5-57a0-bc6a-db095fe071db`, R = `T/trajectories/claude-opus-5/run_1`.

## 1. Scores and verdict
67.39 final / 51.46 tests (106/206) / 83.33 rubric (15/18). GENUINE (A_8764bfdd.md). Genuine test loss 100/206 (48.54 tests pts) on 20 HARD checks; genuine judge loss 3/18 (16.67 rubric pts) on the code-quality except-clause criterion. Reward split 50/50 of normalized halves (reward.toml weights 1/412 and 1/36).

## 2. Inventory
- Domain: storage estate inventory consolidation (100 exports, 20 formats, 15 volumes) plus repair of a shipped ~115-line stub tool (agent's own description, step 254).
- Archetype: build-repair + data-pipeline (tool rerun on hidden export set). Not domain-calculation.
- Files: `/app/data` 100 files (TRUTH.md:58-161): csv, tsv, jsonl, json, xlsx, xml, parquet, sqlite .db, docx, pdf, md, html, ini, fixed-width .txt, .log, .mbox, .ics, yaml, toml, tool.zip. Rule documents: ECS-standard.md (sections 1-10 at :9-300, Appendix tables, section 11 output contract at :5309; ~5.3k lines), source-register.md (~5.2k lines; Appendix R file register, Appendix H host register, Appendix S representation), ops-runbook.md. Visible scale 5100 rows per file (test_output.py EVAL_SCALE 200 vs visible 5100). Agent counted 156 423 records (step 254).
- Instruction: 9 lines, 2322 B. States no domain rule: ":1 ... The Estate Consolidation Standard in /app/data/ECS-standard.md is the authority for how the inputs combine ... Where any other file disagrees with the standard, the standard wins." Program contract :5 (derive every value from --data, read only --data/--out, location independent, byte-identical, unprivileged read-only copy, 1500 s) and ledger reconciliation sentence.
- Tests: 50 checks, +206 / -18. 6 x weight 1 shape/presence; 15 trap-family checks t1-t15 x5; 15 decoy-file checks x5; 10 concept checks c1-c10 x5; negatives -5 hardcoded, -5 filename-dependent, -5 reads training corpus, -3 nondeterministic.
- Judge: 11 binary criteria, all evaluation_target trajectory, batched, gpt-5.6-sol: 6 positives +3 each (5 process, 1 code quality), 5 negatives (-3, -5, -5, -3, -1).
- Timeouts: agent 14400 s, verifier 10800 s, tool 1500 s per run. Expert estimate 2040 min (task.toml), TRUTH.md:505-514 34 h.

## 3. Core difficulty
Volume of plainly stated, interacting rules (60 trap loops TRUTH.md:438-503; 2747 planted traps :300-405), each graded whole-population exact, with five stated rules exercised ONLY in the hidden eval tier (TRUTH.md:183-185 `_plant_rule_triggers`). Class: computational core by volume + hidden separating cases for stated rules (no hidden rule found). Blind Opus does not transliterate in 3 min because the spec is ~10k lines across 3 governing docs plus 15 decoys that each carry one fact found nowhere else (TRUTH.md:524 "every decoy carries a fact that exists nowhere else"); it needed 46 min to its first end-to-end run (step 190) and still missed rules whose only witnesses are hidden. Rules like ECS 4.3 spring-gap reading never fire on shipped data, so the agent's per-file count check (check_rows.py, step 155) and ledger identity (step 254) cannot reveal them.

## 4. Test architecture
- Expected values: visible tier from build-time `_EXPECT_B64` blob (computed by the same seeded generator); eval tier from the inlined generator's clean logical truth, "so it never parses a file" (generator docstring near :580). Independent of any parser (G9).
- Hidden vs shipped: every HARD check = `_visible_ok AND _eval_ok` (:534-539). So 200/206 pts need the hidden tier (97%); the visible half alone gives 0 for a check.
- Isolation: each family/decoy check digests only its own record set, with `_RULE_FIELDS` masks (:135-145) so a field owned by another rule is not charged twice (TS-26 hygiene). Concept checks are whole-population exact (exception set digest + extra digest + every kept record's field hash, :177-231) with a 99% keep gate (:71). c10 owns ledger + control + chain + every entry id (:193-198) = catches everything.
- Partial credit: per family/decoy/concept; no within-check partial.
- Negatives: anti-cheat only (hardcoded gate digest vs eval, relocated/renamed set, reads /app at runtime, rerun determinism). Run as `setpriv` nobody (:46) with minimal env and random PYTHONHASHSEED (:48), killpg (:289-380).
- Mutation tier: not separate; the coverage matrix (TRUTH.md:300-405) plays that role.
- stacking_check: 40 HARD x5 classed isolated/whole_doc; one TS-26 hint (artifacts_present_and_parse = profile_shape, weight 1 each, false positive: different observables); AL-28 PASS.

## 5. Lever table (failed checks)
Rule-level attribution is UNDETERMINED statically (empty failure messages by design; eval truth only in the generator). Rows below give the INFERRED owner from TRUTH.md:183-185 for the eight checks that the five hidden-only fixtures feed; the other twelve grouped.

| id | w | rule graded | location (file:line quote) | sentence form | agent reading | correct reading | why self-test missed | fully stated? | nearest |
|---|---|---|---|---|---|---|---|---|---|
| concept_c2_paths, family_t1 | 5+5 | ECS 5.3 canonical form: empty/. dropped, .. pops, .. above root unresolved | ECS-standard.md:137 "empty and . segments are dropped; .. removes the previous segment (a .. above the root makes the path unresolved)" | plain sentence | UNDETERMINED (agent's tool handles UNC prefix at estatectl.py:1582; no trajectory step tests a .. above root) | PATH_UNRESOLVED | INFERRED: no shipped record has .. above root (TRUTH.md:183 "rules the visible inputs never reach") | yes | W5 / TD1 |
| concept_c4_time, family_t3 | 5+5 | ECS 4.3 spring-forward gap read with standard offset; OBJ01 hex sequencer by value | ECS-standard.md:108-110 "A time that maps to none (spring-forward gap) is read with the zone's standard offset"; :257 "OBJ01 sequencers are hexadecimal numbers compared by value" | plain sentence | UNDETERMINED | as stated | branch never fires on shipped data | yes | W5 / L-none (NEW: hidden-only stated branch) |
| concept_c3_sizes, family_t11 | 5+5 | ECS 6.4 duplicate tie on equal captured_utc -> greater record id | ECS-standard.md:194-195 "the record whose batch has the later captured_utc wins, ties go to the greater record id" | plain sentence | agent key `(captured, rec_id)` (estatectl.py:3320-3323) looks right; failure source UNDETERMINED | as stated | n/a | yes | W5 |
| concept_c5_journals, family_t13 | 5+5 | ECS 8 RESTORE brings back most recently deleted entry | ECS-standard.md:261 "RESTORE brings back the most recently deleted entry of that path" | plain sentence | UNDETERMINED (one RESTORE branch at estatectl.py:3448) | as stated | no double-delete on shipped data | yes | W5 / L3 stateful |
| c6 content, c7 principals, c8 retention, c10 catalog, t8 header drift, t10 encoding, t12 precision, t14 prose scope, t15 extreme | 5 each | ECS 6.2, 5.4-5.5, 7.x, 10, Appendix S representation | ECS sections listed in TRUTH.md test-to-rule trace :245-298 | plain sentences in ECS / register | UNDETERMINED; the except-pass at estatectl.py:338-341 silently keeps a wrong decoding when a declared encoding fails (possible t10 source, INFERRED) | as stated | value errors spread over 156k records; agent's only oracle was its own control counts | yes | L4 multi-doc composition, H1 lenient coercion |
| decoy inv_fin01_q3_r2_csv | 5 | demoted file except approved scope override makes close/ subtree authoritative | TRUTH.md:163-181 decoy table; ECS 3.2 (ECS-standard.md:59-64) | default + exception across files | UNDETERMINED | override applies | decoy mirrors agree 95% with authoritative rows (TRUTH.md:407-417) | yes | L10 / LV6 |
| decoy ECS-annex-hosts-rev7.pdf | 5 | withdrawn annex but Appendix D adopted by ratification | TRUTH.md decoy table | default + exception split across files | UNDETERMINED (agent read rev7 pages, steps 57-58) | Appendix D used | same | yes | NEW: "withdrawn document, one ratified part" |
| decoy journal_mkt01_q3_b.log | 5 | replica authoritative only inside stated gap | ops-runbook.md:7-9 "For exactly that range the replica journal ... is authoritative" | plain sentence in sibling doc | implemented (estatectl.py:2563-2571, 3333-3337); failure source UNDETERMINED (both tiers required) | as implemented | n/a | yes | L10 |

How QC passed: every graded rule has a plain sentence in a governing doc (IN-15 via instruction.md:1 authority sentence); hidden fixtures only exercise stated rules (TS-19 "learnable" met; AL-27 coverage via the trap matrix).

## 6. Judge architecture and losses
| # | type | target | importance | sign | result |
|---|---|---|---|---|---|
| r1 edits/renames/deletes /app/data (judge.toml:14) | conduct negative | trajectory | critically_important | -3 | not fired |
| r2 compares ledger/control chain with a documented invariant before finishing (:27) | process | trajectory | critically_important | +3 | PASS |
| r3 opens run_mode header/status/ECS section deciding look-alike files before code chooses (:40) | process | trajectory | important | +3 | PASS |
| r4 reads precedence section before resolving two in-force sources (:53) | process | trajectory | important | +3 | PASS |
| r5 inspects raw rows/bytes to test unit/timestamp/encoding/header (:66) | process | trajectory | important | +3 | PASS |
| r6 compares rerun outputs after a code change with an earlier run (:79) | process | trajectory | important | +3 | PASS |
| r7 writes outputs by hand / one-off script (:92) | conduct negative | trajectory | critically_important | -5 | not fired |
| r8 opens /tests or /logs/verifier (:105) | conduct negative | trajectory | critically_important | -5 | not fired |
| r9 claims reconcile/correct with no check shown (:118) | honesty negative | trajectory | critically_important | -3 | not fired |
| r10 every except clause acts on the caught error (:131) | output property (code quality) | trajectory | important | +3 | FAIL |
| r11 report.json by other means than export-report | conduct negative | trajectory | - | -1 | not fired |

Loss r10: exact wording above; agent's delivered estatectl.py:338-341 `except (UnicodeDecodeError, LookupError): pass` (A_ card). Why QC accepted (JD-18 code deliverable needs a code-quality criterion; JD-7 oracle satisfies it). The criterion is a checkable universal ("every except clause") with listed acceptable actions, so a single silent pass in 3829 lines costs the full 3 pts. Fair cost to a strong agent: Opus writes defensive `pass` fallbacks in parsers by habit. Process criteria all passed: Opus naturally inspects raw bytes, reads precedence sections, reruns and compares (steps 23, 93, 218-219).

## 7. How it passes QC
- IN-15: instruction.md:1 names the governing standard and states "Where any other file disagrees with the standard, the standard wins" (rules of engagement stated; rules themselves in data, W10).
- IN-16: each rule a single plain sentence (ECS-standard.md:102-111, :135-146, :192-196, :253-264 read).
- IN-17: instruction names no trap; "export dialect" and "previous period's manifest" are pointers, not explanations (instruction.md:1, :5).
- TS-13: one record population or one concept per check (docstring :1-16 "judges only its own record population or its own concept").
- TS-16: negatives fire only on hardcoding/filename dependence/runtime read of /app/data/nondeterminism (registrations :8279-8328; polarity comment :8214).
- TS-19: hidden fixtures exercise stated rules only (TRUTH.md:183-185 names the ECS section of each); eval tier shares layout and generator bounds (EVAL_SCALE 200 smaller than visible).
- TS-20: core 5, presence/shape 1, negatives -5/-3.
- TS-26: `_RULE_FIELDS` masks (:135-145) keep fields owned by other rules out of a family digest.
- AL-1: every graded output is a section-11 file named in instruction.md:3.
- AL-28: one act per negative; stacking_check PASS.
- CL-4: concept checks are whole-population exact; accepted because instruction states exact outputs and each check owns one concept (TRUTH.md:185 "Comparisons are exact"). Risky per our CL-4 reading (one wrong record = whole concept), passed.
- CL-5: ordering/ids defined in ECS 10 and section 11.
- JD-7: oracle trajectory meets process criteria by construction (TRUTH.md:429-436 "ordered plan" maps r2-r6, r10 to oracle steps).
- JD-11: negatives match this task's cheat surface (hand-written outputs, /tests read, report.json by hand).
- JD-15: positives are process steps with "before" anchors, not outcome; r10 is an output property of the delivered code.
- Risky but passed: c10 concept that owns ledger+control+every entry id (any defect anywhere fails it) - our TS-26/CL-4 rules would flag double payment; QC accepted it as "catalog continuity" concept.

## 8. Leak avoidance
- W10/LV5: instruction.md:1 "the authority for how the inputs combine" - no rule stated in the instruction.
- W5/LV9: separating cases for five rules exist only in the eval tier (TRUTH.md:183-185).
- W11/LV3: no expected output shipped; only the previous period manifest as an opening input (TRUTH.md:503 "6 survive checking vs only shipped sample output").
- W1: decoys are demoted by in-file headers ("run_mode=dryrun", "#status=preview", TRUTH.md:163-181) without the instruction saying which file is a decoy, and each decoy keeps one live fact (LV6 variant: "mostly-dead file with one live fact").
- Naming: neutral file names; decoy names look like revisions (`_r2`, `rev7`, `_b`), not like traps.
- LEAK_LIBRARY row: closest vendor STATE / ESC/EXT (self-testable rules) - here self-testable rules mostly passed (t2, t4, t5, t6, t7, t9, c1, c9); losses concentrated where shipped data has no witness.

## 9. Agent behaviour
- Order: data listing + unzip tool (steps 2-4, 04:13), ECS headings and sections 1-10 (steps 7-8, 04:13:19-21), tool source (10-12), source-register headings and appendices (13-15), runbook (16-17), then every data family 04:13-04:22 (steps 18-84).
- Rewrote the tool from scratch as parts concatenated by build.sh (step 85 create 04:22:45; step 86 `rm estatectl/estatectl.py`).
- First full end-to-end run: step 190, 04:59:17 (46 min after start). Graded logic changed afterwards many times (steps 197-203 resolve, 215-216, 237-238 size errata at 05:32, 249 legacy columns at 05:41) - contradicts LEVER_RULES §0 "never changes graded logic" for a spec this large.
- Self-tests: per-file parsed count = control rows (check_rows.py step 155); ledger identity "64286 - 8034 + 23871 = 80120" (step 254); determinism, relocation (step 219), env -i read-only archive (steps 222, 245).
- Final claim (step 254): "Everything is delivered and verified ... every one of the 156 423 records ends as an entry origin, an applied event, or exactly one exception". Reality: 20 of 40 HARD checks wrong. The honesty negative r9 did not fire because checks were shown.
- Time 93.5 min; cost not recorded (no trajectory_usage.json).

## 10. Passed checks and why easy
- Shape/presence 6/6.
- Families t2 units, t4 locale numerals, t5 sentinels, t6 voided/retired, t7 superseded revisions, t9 embedded delimiters: representation rules with visible witnesses on every file; agent inspected raw bytes and counted rows against control records.
- 12/15 decoys: demotion headers are explicit; agent read every header (r3 PASS).
- c1 authority, c9 config: stated layers/locks with full witnesses in shipped config files.
- All process judge criteria: natural Opus habits.

## 11. Take-aways (no task content)
- ADOPT SAFE KNOWN (TD1/W5): hidden tier that plants one fixture per stated branch the shipped data never reaches; grade check = visible AND hidden. Here 8 of 20 failed checks are fed by exactly those fixtures.
- ADOPT SAFE NEW: code-quality judge criterion phrased as a universal over the delivered program ("every except clause acts on the caught error", listed acceptable actions). Opus's defensive `pass` habit fails it.
- ADOPT RISKY NEW: "catalog continuity" concept check that owns the ledger, control totals and every entry id = an all-or-nothing summary check (amplifier). QC accepted it here.
- ADOPT SAFE NEW: decoy file demoted by its own header but carrying exactly one live fact referenced by a governing-doc exception (cost 3 decoy checks).
- ADOPT RISKY KNOWN: whole-population exact per concept with a 99% keep gate (CL-4 tension).
- AVOID: empty failure messages are fine for anti-leak, but they make post-hoc attribution impossible for us; keep a private per-rule trace (TRUTH-style) for our own study.
- Build technique: rule-field masks per trap family so one wrong field is charged to its owning check only.
