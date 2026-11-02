# BUILD_REPORT counter-page-crash-recovery (board 54e38ee)

Bundle: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/counter-page-crash-recovery/`
WORK: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/counter-page-crash-recovery/`
Archetype build-repair, category Software Engineering, seed 806610, agent timeout 7200 s. tree_sha 831a6b85ba1d.
Session rename: `name_session.py 54e38ee` printed `codex: no match` / `opencode: ['ses_e8c5e56dcffeM7e8KT55xptF2N']`
(the list showed an opencode session, not this ID by name; carried on, no retry).

## Tree (22 files)

| file | lines |
|---|---|
| instruction.md | 15 (2132 chars) |
| task.toml | 47 |
| environment/Dockerfile | 26 |
| environment/data/journal.jsonl | 26436 |
| environment/data/txn_catalog.csv | 2108 |
| environment/data/audit_queries.json | 1340 |
| environment/data/page_map.ini | 566 |
| environment/data/recovery_contract.md (governing) | 219 |
| environment/data/checkpoint.toml | 109 |
| environment/data/expected_targets.json, dependency_manifest.json, ci_config.yaml, compiler_flags.json | 23, 12, 11, 7 |
| environment/data/disk_pages.bin (binary frames), project.zip (shipped package, 10 members) | 37640 B, 15076 B |
| solution/solve.sh, solve.py, TRUTH.md | 5, 861, 142 |
| tests/test_output.py, judge.toml, reward.toml, test.sh, Dockerfile | 1480, 126, 7, 10, 9 |

A5: 30,950 text lines in data; journal.jsonl and txn_catalog.csv each >= 2000. Formats: jsonl, csv, json, ini, toml,
yaml, md, custom binary, zip (9).

## Chains
- checkpoint.toml master_lsn -> checkpoint_end tables in journal.jsonl -> analysis -> redo (disk_pages.bin pageLSN) -> undo -> page image -> module_core, summary sha256 + audits (audit_queries.json).
- page_map.ini -> validation (E_BAD_IMAGE, E_UNKNOWN_PAGE) -> disk frame decode -> pages -> every document.
- txn_catalog.csv -> client totals <- appended CLRs <- undo <- analysis tables.
- expected_targets.json + compiler_flags.json + dependency_manifest.json -> package.zip layout/version -> selftest/build_report.
- ci_config.yaml -> selftest ci_commands; project.zip tests -> selftest tests_run/tests_passed.

## Levers (rules all in recovery_contract.md, the one governing file)

| lever | rule lines | checks it can fail | weight |
|---|---|---|---|
| LV-WR-1 exact page image from analysis/redo/undo | 4.1 analysis L92-107, 4.2 redo L111-119 (pages decided before applying), 4.3 apply L139-140, image L147-148 | 17 document checks | 75 |
| LV-WR-2 compensation chains via undo_next, earlier restarts' CLRs | 4.3 undo point L130-132, CLR undo_next L138 | 17 document checks | 75 |
| LV-WR-3 stated audit sequence | 4.3 first LSN L123-124, END order L126-128, undo step L134-141; redo start L111-112 | 17 document checks | 75 |

No secondary lever. COUPLING sentence verbatim at recovery_contract.md:8-9. IN-17: redo decision and END placement
are stated as the protocol; no sentence contrasts them with textbook recovery or with the shipped method.

## Master changes (go, 22:35) applied
1. Shipped book on the light profile: 36 images (34 recovered, 2 rejected: pcpn85 E_BAD_CHAIN, z0uggz E_BAD_IMAGE); no same-page multi-change record, no CLR-to-CLR stop.
2. H3 timing is its own check `max_within_limit` (w3); `max_core` (5) and `max_summary` (3) grade exactness only.
3. Extra hidden coupled check: `max_summary` (w3). B12 one-hop all-but-one overall now 61.8.
4. Densest interactions: every hidden image is rejection-sampled until all nine cases are present. Images carrying each case:

| book | images | same-page multi-change redone | CLR-to-CLR stop | restarts writing CLRs (>= 2 each) | loser flushed after winner same page | checkpoint tables disagree with tail | loser with no undo point | winners out of id order | redo below master | equal pageLSN skip |
|---|---|---|---|---|---|---|---|---|---|---|
| shipped (light) | 34 valid | 0 | 0 | 17 | 31 | 33 | 15 | 0 | 34 | 34 |
| dense | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 |
| restart | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 |
| max | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 |
| rejection | 11 (2 valid) | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 |
| relocated | 8 | 8 | 8 | 8 | 8 | 8 | 8 | 8 | 8 | 8 |
| scaled (dense x3) | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 |

   Hidden books stay inside the stated limits (max 1149 records, 24 pages, slots 4..8, <= 40 images).
5. IN-17 checked in contract and instruction (no contrast sentence).
6. Docker timing of the reference on H3 (12 images, up to 1149 records): 0.54 / 0.29 / 0.33 s against 60 s; recorded in TRUTH.md.
7. Stopped at BUILD READY; no probe run.

## Tests (27 checks, positive 95, negatives -8) and judge (9 criteria, positive 19, batched)
Weights: build facts 11 (11.6%), shipped-book documents 12 (12.6%), hidden or mutated reruns 72 (75.8%); whole-document
checks 81 (85.3%). Negatives: negative_hardcoded_sample_answers -5, negative_shipped_tests_dropped -3 (each trigger is a
contract sentence, L185-187 and L199-201). Judge: R1-R4 recompute figures (w3 each), R5 altered-copy rerun (w3), R6
rejected images listed (w3), R7 maintainability of recovery.py (w1), R8 honesty (-3), R9 grader files (-5).
reward.toml: test_output 0.5/95, judge 0.5/19.

## Cost table (G10) and expected loss
| lever | variant | lost of 95 | alone % | all-but-one overall | checks lost |
|---|---|---|---|---|---|
| LV-WR-1 | B16 eager pageLSN | 53 | 55.8 | 67.1 | hidden core/metrics/summary of every book |
| LV-WR-1 | B15 per-record redo / B2 / B3 | 62 | 65.3 | 62.4 | core/metrics/summary everywhere |
| LV-WR-1 | B1 shipped method / B8 | 75 | 78.9 | 55.5 | all 17 document checks |
| LV-WR-2 | B12 one-hop | 63 | 66.3 | 61.8 | all hidden documents |
| LV-WR-2 | B5 prev walk | 75 | 78.9 | 55.5 | all 17 |
| LV-WR-3 | B4 per-txn / B6 redo from master / B7 END placement | 62 | 65.3 | 62.4 | core/appended/summary or core/metrics/summary everywhere |
| LV-WR-3 | B9 ENDs without LSN | 75 | 78.9 | 55.5 | all 17 |
| combined | textbook ARIES (B7+B16) | 72 | 75.8 | 57.1 | all except some shipped metrics |
One fact wrong: one wrong slot in one max image loses 8 (tests 91.6%, overall about 0.91).

## Scripts and results
- instruction_qc 5/0/0 PASS; structure_qc 17 pass, 1 WARN X1 (disk_pages.bin and project.zip are real binaries); tests_qc 36/0/0 PASS (after renaming negatives with the `negative_` prefix); judge_qc 19/0/0 PASS.
- validate_bundle.py --archetype build-repair: 40 passed, 0 failed, GATE PASS (negative renamed to the required `negative_hardcoded_sample_answers`).
- check_exact.py (independent closed form + forward truth): 300 generated images + shipped book, 0 mismatches.
- cost_table.py: reference equal on every book; numbers above. mutants.py: 32 mutants of the oracle archive, every one loses points (RULE_COVERAGE.md, 0 uncovered).
- Local stub grader on Docker oracle output: 95/95.
- QL oracle/nop procedure (Harbor 0.24.0, judge removed, test_output weight 1/95): oracle 1.0 / 1.0 / 1.0 (1m28s, 1m17s, 1m27s), nop 0.0 (verifier/reward.json of each job).
- STACKING_CHECK.md: STACKING PASS.
- precheck.sh last line: `PRECHECK CLEAN`.

## Open conflicts / not run
- No probe or blind read run (master issues 3 P13 blind reads next).
- Honest risk: a program that transliterates sections 4.1-4.3 and decides each record's pages before applying is exact on every book; the losses rest on interaction slips and stated-rule habits (eager pageLSN, textbook END placement).
- precheck NOTE DS-22: `fix_patch_sha256` names solve.sh by convention of the template; validator 15.7 checks it against solve.sh.

## Lessons for the master
validate_bundle 7.4 requires the exact name `negative_hardcoded_sample_answers`; tests_qc W6 requires the `negative_` prefix on every negative | template_change: build-repair test_output.py template, criteria block: no change: template already uses that name; my rename broke it
harbor run prompts for verifier.env keys even with judge.toml removed; QL procedure needs `export OPENAI_API_KEY=unused` and `yes |` | template_change: knowledge/intake/ql_oracle_nop_procedure.md step 3
stacking_check groups whole-document checks on different hidden books as TS-26 duplicates by helper name | no change: corrected by reading, as the tool says
