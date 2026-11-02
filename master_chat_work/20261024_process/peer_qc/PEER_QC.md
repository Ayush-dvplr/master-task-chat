# Peer QC study: Aditya Patel's 3 accepted tasks (board 6c287ec, 24 Oct 2026)

P = `Anubis_Tasks_Samples/Pass@1_New/Dinshi_Jain/Aditya Patel`. Scratch = `/tmp/peer_qc-20261024T1612` (copies; oracle and agent programs re-run there in a venv, not in Docker). Overall = 50 x tests% + 50 x judge% (reward.toml in all three: 0.5/P per channel), so "pts" below are overall reward points unless marked "raw weight".

Bottom line: (a) yes, the live kit gives all three 0 FAIL and 0 MINOR. (b) Opus lost points in two ways. One root slip was billed across 10-29 owned-row tests on both tiers (amplification, 17.6-41.4 pts per task). Small judges (18 positive raw points in estate and kvec) also made each verification-conduct criterion worth 2.1-8.3 pts. (c) The design: a short instruction, a long in-data contract with a named arbiter document, a seeded hidden estate, 35-50 tests that own rows per trap family/decoy/concept, one global coupling term, and a judge that pays for checks Opus never runs. (d) Our templates forbid two of these: conduct criteria the oracle cannot show, and rules in a second document. They never use a third: verification-depth criteria in place of "states figure X".

## Phase 1: kit verdict

Kit HEAD 976c1666. `git diff --stat 71a653b2 976c1666 -- '*.py'` gave empty output, so the check code is identical to 71a653b2. Full outputs: `precheck/<slug>.txt`. Raw kit outputs: `precheck/kit_raw/`.

| task | fails | minors | kit warns | our gap-check hits | tests | criteria |
|---|---|---|---|---|---|---|
| detbench-release-gate-eval | 0 | 0 | 40 x S6 (CRLF in environment/data csv/jsonl/tsv/log/ini/ics), X1 | 1 ("structure_qc 40 warn line(s)" counted as a finding) | 35 | 34 |
| estate-manifest-consolidation | 0 | 0 | A3 (50 checks > 35), X1 | 3: `{{...}}`, J3, J4 | 50 | 11 |
| kvec-meter-settlement-reconciliation | 0 | 0 | A3 (36 checks > 35), X1 | 2: `{{...}}`, J4 | 36 | 11 |

Kit scripts: instruction_qc 5 pass, judge_qc 19 pass, tests_qc 36-37 pass, structure_qc 17 pass on every task. The kit's VERDICT line reads "WARN - tasker approval needed" for structure (all three) and for tests (estate, kvec). None of the gap-check hits is a real defect:
- **`{{...}}`** at estate `tests/test_output.py:5835` (`lines.append(f"  - {{{pairs}}}")`) and kvec `solve.py:245,249` (`{{{ns['w']}}}t`). These are Python f-string brace escapes, so this is OUR false positive.
- **J3** (`precheck.sh:93-99` wants a negative criterion whose text matches /claim/). Estate R9 `r9_unsupported_success_claim` (w -3) says "states in its final message that the outputs reconcile or are correct while no check in the trajectory shows it". That is an honesty negative without the word "claim", so this is OUR false positive.
- **J4** (the regex wants exactly 1 code-quality criterion). Estate R10 ("every except clause acts on the caught error") and kvec R6 `r6_transform_code_quality` ("split into functions that each do one job") are both code-quality criteria the regex misses. OUR false positive. The kit's JD-18 (checks.json, 04_Judge_QC.md:99) only asks for at least one.
- **S6 CRLF** is a kit WARN ("hygiene; parsers tolerate it"), and the CRLF is deliberate data noise. precheck counts it as a finding, which makes it STRICTER than the kit.
- **A3** above 35 checks is a kit WARN that needs tasker approval. It was accepted here at 50 checks (FC:521).
- NOTE lines are not findings: DS-22 (TRUTH.md names the sha256 of a file that does not ship: detbench TRUTH.md:530, estate :535) and J1 (detbench R20 is a final-reply figure).

## Phase 2: where Opus lost points

loss.py outputs are in `loss/<slug>.txt`. Attribution comes from re-running the oracle and the agent's delivered program on the visible data. The agent's outputs were byte-identical to the in-container artifacts for every file (`cmp`), so the reproduction is valid.

### kvec 50.23 (tests 25/146 raw = 17.12%, judge 15/18 = 83.33%)
| item | what the agent did | evidence | class | pts |
|---|---|---|---|---|
| 29 failed tests (t01-t03, t05-t09, t11-t16, dc03-dc05, dc08-dc15), -121 raw | **Root 1 (energy).** The agent ignored 6 VALIDATED `mdm_read_corrections.csv` rows dated 2025-11-01 (KV0053296 68356.830 vs Oct close 68366.46, plus KV0213982, KV0760410, KV0858286, KV2409989, KV7202308) and kept the Oct-close value. Billed import came out 139,551 Wh low (oracle 55173529026 vs agent 55173389475; this sum equals the entire summary delta). UFE = injection - billed is allocated by largest remainder to every account (test_output.py:3008-3009, 3091), so all 6153 account rows differ by about 2 Wh. | Trajectory steps 12-13 read the precedence paragraph. Step 119 loaded VALIDATED corrections. Step 153 listed the 6 conflicts ("KV0053296 corr 68356.830 \| oct 68366.46 ACTUAL"), but the final program did not apply them. | **GENUINE root, then AMPLIFICATION** | 41.44 |
| (same tests) | **Root 2 (reporting).** 166 Oct-close rows with status ESTIMATED were reported as ESTIMATE boundaries. The oracle treats every close read as actual. | The file header says "validated boundary reads". No contract or manual sentence addresses the ESTIMATED status (grep found none). | AMBIGUITY (affects meter_summary/read_resolution only, not energy) | inside the above |
| (same tests) | **Root 3.** About 8 MISSING-boundary mismatches. aurora `data_rows` counts are 1-2 too high (contract:151). | rule not confirmed | UNVERIFIED | inside the above |
| judge R5 `exercises_transform_on_another_directory` (w3) | The agent ran only `/app/data` into different OUT dirs and never ran an altered copy. | judge_response.txt R5: "does not show copying or altering the input data into another DATA_DIR" | CONDUCT | 8.33 |

The instruction settles Root 1. Contract:3-6: "The settlement procedures manual (`kvec_settlement_procedures_manual.docx`, revision 3) defines which source is authoritative when sources disagree". Manual paragraph 6: "For each meter boundary the value is taken from the first source that has one: (1) a VALIDATED correction in mdm_read_corrections.csv for the meter and read date, highest revision; (2) the selected actual read ...". The literal-reading pull is contract:17: "The 2025-11-01 boundary comes from `mdm_october_close_reads.csv` (already validated by MDM at the scheduled instant)." The arbiter sentence resolves that pull. instruction.md:21 states the amplification out loud: "a single misread record anywhere changes the totals and every account row that carries them; rows and figures only count when they are exact." The 7 tests that passed (t04 locale, t10 encoding, feeder_balance_shape, dc01, dc02, dc06, dc07) own no account or UFE rows. The exact per-test split between roots is UNVERIFIED (grader not run).

### estate 67.39 (tests 106/206 = 51.46%, judge 15/18 = 83.33%)
| item | what the agent did | evidence | class | pts |
|---|---|---|---|---|
| 20 tests x -5 raw (families t1, t3, t8, t10-t15; decoys inv_fin01_q3_r2_csv, ecs_annex_hosts_rev7_pdf, journal_mkt01_q3_b_log; concepts c2-c8, c10), "on both tiers" | **Root A.** `exceptions()` skips every record in `self.applied` (agent estatectl.py:3405-3415, 3496-3504). As a result, applied CREATE records whose entry is later DELETED, REPLACED or PURGED are never reported: 1892 oracle-only validation rows (prod DELETED 4281 vs 3171, REPLACED 767 vs 465, PURGED 10729 vs 10252). The oracle marks the origin anyway (oracle estatectl.py:2113-2138). | ECS-standard.md:258-261 "CREATE makes a live entry (... a live entry already at that path becomes REPLACED). ... DELETE removes a live entry (its origin becomes DELETED)" vs :267-268 "Each record that does not end as the origin of a manifest entry, and is not an applied journal event, is reported once ...". The agent's final message (step 255) restates the literal :267 reading. | **AMBIGUITY root, then AMPLIFICATION** | 24.27 |
| (same) | **Root B.** 33 agent-only rows (ORPHAN_EVENT on FIN journals, HARDLINK_ALIAS) | cause not confirmed | UNVERIFIED | inside the above |
| judge R10 `repaired_error_handling` (w3) | `except (UnicodeDecodeError, LookupError): pass` | agent estatectl.py:340-341 | CONDUCT (artefact-quality criterion) | 8.33 |

No instruction line settles Root A unambiguously. The kit raised no IN-16 finding, but under IN-16 both readings can be written out, so this is luck rather than design.

### detbench 61.62 (tests 98/151 = 64.90%, judge 42/72 = 58.33%)
| item | what the agent did | evidence | class | pts |
|---|---|---|---|---|
| baseline_rows, detections_r2/r3/r4, class_metrics, operating_points, leaderboard, eval_estate_detections/scoring/reconciliation (10 x -5 raw) + reconciliation_counts (-3 raw) | **Root 1.** 2 GT boxes missing on IMG4992755 (NL-0228940, NL-0228941). They exist only in `nl_boxes_batch02_reextract.csv` (lines 5595-5596), in header-drifted rows. **Root 2.** R2-R4 detection scores and det_ids differ (R2 4 rows, R3 about 54, R4 5; R1 none), which shifts mAP values in the 4th-6th decimal. | The visible-tier diff gives gt_boxes 49289 vs 49287. Judge r5: "the final logic takes 88 rows for partition 56". eval_standard_v3.md:131 says short deliveries are recovered per the Data Authority Policy. Root 2's rule is UNVERIFIED. | GENUINE roots (rule citations UNVERIFIED), then AMPLIFICATION | 17.55 |
| judge r5, r7, r10, r19, r29, r30, r31, r32, r33, r34 (10 x w3, all scored 0) | The agent never independently recomputed per-run detections, operating points or release decisions. It never checked knot monotonicity, the score range, multi-reason candidates or the per-image cap order. It ran the engine only on an exact copy of the estate (r7: "No estate with reduced or edited file contents was run"). | judge_response.txt | CONDUCT | 20.83 |

instruction.md:29 states the exactness bar: "A value that is almost right is wrong, and a row that is right on all but one field is wrong." No negative fired in any of the three tasks. No ARTEFACT or HIDDEN RULE loss was found.

## Phase 3: design anatomy

| | detbench | estate | kvec |
|---|---|---|---|
| instruction | 35 lines / 3231 B | 9 lines / 2322 B | 25 lines / 3010 B |
| how rules are stated | No rules in the instruction. All rules sit in an in-data standard (`eval_standard_v3.md`, PES-3), which names the deciding document per question. | `ECS-standard.md` is the authority ("Where any other file disagrees with the standard, the standard wins"). `source-register.md` covers the dialects. | 144 KB contract plus manual rev3 (the authority arbiter, contract:3-6) plus head-end profiles |
| shape | write `evalctl.py ESTATE_DIR OUT_DIR` | repair a 119-line stub `estatectl` from tool.zip and deliver the zip | write `transform.py DATA_DIR OUT_DIR` |
| data | 100 files, ~18 formats, 115 MB, CRLF noise, re-extracts/decoys | 100 files, 205 MB | 100 files, 49 MB, 15 decoy files (DECOYS test_output.py:3134) |
| hidden tier | test_output.py is a seeded generator (build_estate(seed, scale)) | EstateSet generator, `_eval_run` | build_all/compute_truth; `_runs` 6426 runs 2 identical runs + 1 relocated/renamed run with utime changes, snapshots writes |
| tests (raw weights) | 35: 29 x 5 + 2 x 3; whole-output tests plus family_t01-t16 | 50: 40 x 5 + 6 x 1 (shape/presence); family/decoy/concept | 36: 26 x 5 + 5 x 3 + 1; t01-t16 + dc01-dc15; each test owns rows (`_owned_part_ok` 6475), visible must pass, then hidden (`_hard`) |
| tests one bug touched | 11 | 20 | 29 |
| negatives (all three) | hardcoded_sample_answers -5, filename_dependent -5, reads shipped estate/corpus or IO outside args -5, nondeterministic -3 | same | same |
| judge | 34 criteria: 21 x 3, 9 x 1, -3 x 2, -5 x 2; mostly "independently recomputes X for every run/class" | 11: 6 x 3, 5 negatives (incl. R9 honesty, R10 code quality) | 11: 6 x 3 (reads contract first, documented invariant, conflicts by rule, non-authoritative declarations, altered-dir rerun, code quality), 5 negatives |
| solve.py | 1673 lines | 2505 (embeds repaired tool) | 1796 |
| oracle conduct | solve.sh = 7 lines, a plain program run | 4 lines | 6 lines; grep of solve.py for copytree/alter/verify/recompute = no hits |

Our contrast bundles. dispatch: 15-line instruction, 55 files / 1.1 MB, 36 tests (28 hidden = 4 seeds x 7 documents, 7 negatives), judge 10 criteria with R1-R5 "reports figure X" (w5/3); scored tests 67.33, judge 85.7. cohort: 9 lines, 13 files / 60 KB, 25 tests (11 hidden + 8 isolated rule checks), judge 8 criteria with R1-R6 "states figure X"; scored 100/100/100. Our judges pay for figures Opus already gets right. Theirs pay for checks Opus does not run.

| # | design choice | tasks | points it produced | kit check | our v3 templates | verdict |
|---|---|---|---|---|---|---|
| D1 | Verification-depth conduct criteria ("independently recomputes <figure> for every run/class"), several per output family, no instruction sentence beyond "say which checks you ran" (detbench:33), and NOT shown by the oracle (solve.sh is a plain run) | detbench (21 x w3), kvec R1/R4 | detbench 20.83 | JD-9 (04:86 "verification habits"), JD-15 NOTREQ "needs no instruction sentence"; JD-7 (04:76, oracle must satisfy) not enforced by judge_qc: 0 findings | forbidden: _COMMON_RULES_v3.md:53 ("only if the oracle trajectory can actually show it"), P2_build_v3.md:96-97 (J2 "only if solve.py shows the act and the instruction asks"; JUDGE_MAP), LEVER_RULES_v1.md:68 | **adopt** (flag JD-7 risk to PL, as in LEVER_PLAN_v1 :85 Q46) |
| D2 | Altered-copy rerun as a judge criterion (edited contents, not just a relocated copy) | kvec R5, detbench r7 | 8.33 + 2.08 | JD-15, JD-8 (trajectory vs artefact) | never used: we test relocation as a mutation (LEVER_RULES_v1.md:57 G6) and have no judge line | **adopt** |
| D3 | Small judge (11 criteria, 18 positive raw), so each w3 is worth 8.33 pts | estate, kvec | 8.33 per miss | JD-12/G3 floor 8 | allowed (_COMMON_RULES_v3.md:60 floor 8), but our small judges are filled with figure criteria Opus passes (cohort R1-R6) | **adapt**: keep it small, fill it with D1/D2 |
| D4 | Tests partitioned by trap family / decoy file / concept, each owning its rows, gated "on both tiers", 35-50 tests mostly w5 | all | estate 24.27, kvec 41.44, detbench 17.55 | CL-4 NOTREQ (stated exactness bar; one test may own most of the reward), TS-26 NOTREQ (different observables), TS-13, A3 warn >35 accepted | not used: P2_build_v3.md:83 (G1/G2, one whole-document test per downstream document) and :86 (G10 cost table) | **adopt** |
| D5 | One global coupling term stated in the instruction (kvec UFE allocated to every account, instruction.md:21; detbench mAP/leaderboard; estate ledger) | all | it is what turns a 6-meter slip into 29 tests | CL-4 NOTREQ; LEVER_COMPAT.md:30 (G5 + isolated checks) | allowed (LEVER_RULES_v1.md:52 G1 amplification wanted; P2_build_v3.md:104 G5), but no template asks for a term that touches every row | **adopt** (make it an explicit build field) |
| D6 | Short instruction + long contract + a named arbiter document for conflicts (kvec contract:3-6 delegates authority to manual rev3; the lever sits in contract:17 vs manual paragraph 6) | all | kvec Root 1 (41.44 with D5) | AL-1 (05:21, contract = instruction + files it points to), IN-14, DS-21 NOTREQ ("data scattered across many files") | partly forbidden: LEVER_RULES_v1.md:48 (W10 "One rule document ... A rule in two places is two readings"); allowed: P2_build_v3.md:43, LEVER_RULES_v1.md:46 (W8 arbiter) | **adapt**: allow a second rule document when the contract names it as the arbiter |
| D7 | Decoy files as owned test partitions (dc01-dc15, decoy_*) | kvec, estate | lost only through amplification (kvec dc01/dc02/dc06/dc07 passed) | DS-21 | P2_build_v3.md:44, LEVER_RULES_v1.md:34 ("noise only, never a scoring lever") | **agree with ours**: partition only, never a lever |
| D8 | Volume (100 files, ~18 formats, 49-205 MB, CRLF) | all | 0 traced (t04 locale and t10 encoding passed) | DS-21 "None of that is a defect"; S6 warn | P2_build_v3.md:45, :72 ("volume is not the difficulty") | **avoid as lever** (agrees with ours) |
| D9 | Two sentences of the standard with two readings (ECS 258-261 vs 267) | estate | 24.27 | IN-16 (01:46) would fail it if raised; the kit script did not raise it | forbidden: LEVER_RULES_v1.md:47 (W9), _COMMON_RULES_v3.md:25 | **avoid** |
| D10 | Named-shape code-quality criterion | all | estate 8.33 (bare except/pass) | JD-18 (04:99) | _COMMON_RULES_v3.md:51 J4, LEVER_RULES_v1.md:70 | **same** (keep) |
| D11 | 50/50 channels, seeded hidden generator, untrusted subprocess runs, cheat-only negatives | all | 0 (no negative fired) | TS-11, TS-24, TS-30, TS-14/15/16 | _COMMON_RULES_v3.md:38, P2_build_v3.md:82, :90 | **same** |
| D12 | Repair-a-stub-tool shape | estate | not separable | none specific | not in P2_build_v3/LEVER_RULES (grep "repair\|stub" hits only L2/H5 make-it-match) | UNVERIFIED value |

Against the earlier mining (`_dev_research/peer_levers/G1..G5/GROUP_SUMMARY.md`; the prompt path omits `G*/`):
- **Agree:**
  - G2 P5 / G1 P4: Opus never builds its own adversarial or altered input (D1, D2).
  - G4 §4:57: decoys are handled (D7).
  - G4 P2: named-shape code quality (D10).
  - LEVER_PLAN_v1.md:54 G1: keep natural cascades.
- **Disagree:**
  - G1 P5 (:62-67) and G2 §4 (:86) said not to copy whole-document cascades or one behaviour billed many times. These accepted tasks do exactly that, with 0 kit findings (D4).
  - G4 §4:64 said trajectory-conduct criteria with no instruction sentence fail IN-15/JD-15. These carry them with 0 findings (D1).
  - LEVER_PLAN_v1.md:67/:68 (J1 delete figure criteria; J2 one conduct per lever) was right in direction, but our v3 templates still pay for final-reply figures (LEVER_RULES_v1.md:74 J8).

## What we change (proposals only; no edits made)
1. **`_COMMON_RULES_v3.md:53`, `P2_build_v3.md:96-97`, `LEVER_RULES_v1.md:68`**: drop "only if the oracle trajectory / solve.py shows the act and the instruction asks". Replace it with: "conduct criteria grade verification habits (JD-9, JD-15 needs no instruction sentence); add the JD-7 risk to PL notes". Evidence: D1, detbench 20.83 pts lost, 0 kit findings, peer solve.sh are plain program runs.
2. **`P2_build_v3.md:96` (J2) and `LEVER_RULES_v1.md:68`**: replace "one w3 conduct criterion per lever" with "one w3 'independently recomputes <graded figure> outside the program for every <run/class/item> and compares' per output family, 6-20 criteria". Evidence: D1 (detbench r29-r33).
3. **`LEVER_RULES_v1.md:57` (G6) plus a new J line after `:72`**: add the standard criterion "runs the program on a copy of the data whose contents it altered (not only relocated) and checks that the dependent figures move". Evidence: D2 (kvec R5 8.33, detbench r7 2.08).
4. **`LEVER_RULES_v1.md:74` (J8) and `P2_build_v3.md:96` (J1 clause)**: stop sourcing rubric points from final-reply figures. Opus states figures it computed (cohort R1-R6 judge 100, dispatch R1-R5 85.7). Keep a final reply that names checks run (detbench:33) as the hook for item 2. Evidence: D3 and the contrast bundles.
5. **`P2_build_v3.md:83` (G1/G2) and `:86` (G10)**: replace "one whole-document test per downstream document" with "one test per trap family / source file / concept, each owning its rows, visible must pass then hidden (`_hard`), 30-50 tests at w5; accept the A3 warn". Evidence: D4 (estate 20 tests and kvec 29 tests from one root).
6. **`P2_build_v3.md:34` (LEVERS field) and `LEVER_RULES_v1.md:52`**: add a required field COUPLING: one stated quantity computed from all records and carried into every row (an allocation, residual or metric). The instruction states it the way kvec instruction.md:21 does. Evidence: D5.
7. **`LEVER_RULES_v1.md:48` (W10)**: allow a second rule document when the contract names it as the arbiter for conflicts (kvec contract:3-6), keeping W8/W9. Evidence: D6 (kvec Root 1 GENUINE).
8. **`master_chat_tasks/tools/precheck.sh:93-99` plus a new `QC_FIX_PLAYBOOK_v2.md` row after `:36`**:
   - Widen J3 to honesty negatives without the word "claim".
   - Widen J4 to "except clause" and "split into functions".
   - Skip `{{` inside f-strings.
   - Do not count S6 CRLF warns in environment/data as a finding.
   - Playbook row: "S6 CRLF in data = keep warn".

   Evidence: Phase 1, where 6 precheck hits on accepted tasks were all false positives or stricter than the kit.
