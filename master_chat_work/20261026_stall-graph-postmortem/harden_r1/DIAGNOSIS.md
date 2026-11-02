# DIAGNOSIS: stall-graph-postmortem, harden round 1 (board 109e662)

Run: harness 25 Oct 20:31Z, claude-opus-5 (openhands), reported overall 55.98 = tests 11.97 (7 of 36) + judge 100.
True baseline on the fixed grader: tests 132/142 = 93.0, judge 100, overall about 96.

## 1. Phase A verdict: PARTLY (tests channel artefact, now fixed; judge genuine)

- Staged tests: the run used the copy in `Aakrsh tasks/stall-graph-postmortem/tests/` (the `.kiro` staging copy is gone). `diff -r` against BUNDLE differs only at `tests/test_output.py:1164-1170`, the master's `_grant_read` fix:
  `interpreter = Path(sys.executable).resolve()` and `if not path.is_file() or path.resolve() == interpreter:`.
- ctrf: 36 test ids, identical to the 36 registered criteria. 7 passed, 29 failed with no message; every failure is a `_run` check (12 `trap_*`, 13 `generalises_*`) plus the 4 negatives scored 0.
- `result.json`: `exception_info: None`; `verifier/test-stdout.txt` is the single line `reward: 0.5599`. No timeout, no `Errno 13` text (the setpriv failure surfaced as a non-zero exit inside the check, not a verifier crash).
- Judge: `verifier/score.json` holds all 14 rubric items with `passed: true`; it read the trajectory. Judge 100 is genuine.
- Docker confirmation (one block, image `warm-stall-graph-postmortem`, log `/tmp/opencode-logs/stall-graph-postmortem/phaseA_20261026T132916_6daffe/chain3.log` ends `ALL_DONE`):
  - old grader, agent program: `test_output` 1/142 (only the static fallback check passes): the artefact reproduced.
  - fixed grader, agent program + its outputs: `out_new3/reward.json` = `{"reward": 0.4648}`, `test_output` 132.0, failing exactly `generalises_when_a_service_cell_empties` and `generalises_when_the_partition_count_changes`. Matches the master rescore (`jobs/fix-agent/b_stall_fix__NjtKJ9Z`, 132/142) and the oracle rescore (`jobs/fix-oracle/b_stall_oracle__rMHcv84`, 142/142).
- The agent's 8 graded shipped documents are byte identical to the reference. `data_quality.json` differs only in `settlement.passes` (agent 2, reference 4), which tests do not grade (`GRADED_QUALITY_KEYS`, `tests/test_output.py:1315`) and must never grade: `instruction.md:13` defines it as the passes "your" settlement took, and the agent drops a violating class straight to rung 0 per pass (`agent_program/derive_report.py:522-539`) while the reference descends one rung per pass; both reach the same fixpoint.

## 2. Root cause

| Cause | Verdict | Evidence |
|---|---|---|
| 1 run error or wrong copy | NO | exception None; staged tests equal BUNDLE apart from the grader fix; judge read the trajectory. |
| 2 harness / rescoring change, baseline artefact | YES (tests channel only) | `_grant_read` chmodded `sys.executable` to 0644 so `setpriv` could not run Python as nobody; old grader 1/142 vs fixed 132/142 on the same program (Docker above). |
| 3 our QC / fix rounds made it easier | NO | Only `_grant_read` changed. It put no rule, figure or separating example in front of the agent. |
| 4 levers weak by design | YES, PRIMARY | Every graded rule is one explicit sentence, and the eleven control figures acted as a reading oracle; see below. |

Cause 4 detail.
- Decode rules (12, all LEAKED): each flag has one sentence in `environment/data/journal-and-wire.md:42-95`. Opus wrote a scratch decoder from those sentences in the first 5 minutes (step 17). Where the text allowed two readings, it enumerated the readings against the controls and kept the one that reconciled: steps 23-26 (`search3`: padding order, stride walk over true vs declared count, ring padding True/False) -> `HIT 5 7 logical False true 509767 108 hits 1` against CTRL-B/CTRL-E; step 34 changed 0x010 from a half swap `o[4:8]+o[0:4]` to full byte reversal, confirmed by CTRL-H 76750712749; steps 41-42 pinned depth width with CTRL-D. A control that reconciles only under the right reading is a free confirmation (LEVER_RULES 1b, W7).
- Window variations (13): 11 follow from a stated sentence Opus transliterated (lowest live revision is in bold at `identity-and-registry.md:21-26`, with the trap explained at :25-26; hop limit and cycle at :35-39; own-epoch pool `epochs-and-clocks.md:38-43`; budget edge `attribution-and-blame.md:40-47`). The only 2 misses are structural (section 4).
- Judge: all 14 criteria restate the process `instruction.md:33` prescribes ("Five rules govern how you work"), plus calibration steps the documents spell out. A run that follows the instruction scores 100 (J8 breach: these restate method, not J2/J3/J4/J6/J9 conduct).

Contributing: IN-17 announcements tell the agent the shape of the puzzle (`instruction.md:1` "nothing tells you which of them bears on which figure, or in what order they bite" and "for exactly one assignment of them to survive"; `calibration-and-controls.md:29-31` "Exactly one assignment of the nine constants above reproduces all eleven at once."; `identity-and-registry.md:25-26` "A reading that takes the newest live row is a reading of the wrong window.").

## 3. Lever table (fixed-grader rescore + trajectory)

Channel A (tests, 142 positive points):

| Check | Pts | Earned | Lever | Status |
|---|---|---|---|---|
| post_mortem_set_is_complete | 1 | 1 | output contract | LEAKED |
| ..._carries_its_promised_fallback_locations | 1 | 1 | output contract | LEAKED |
| shipped_window_summary / policy_audit / cell_reports / tenant_segment_reports / reconciliation_record | 15 | 15 | all decode + identity + settlement rules | LEAKED |
| trap_zigzag_wait, chained_hold_mask, stride_interleave, biased_declared_count, reversed_origin_pairs, chained_segment_origin, sentinel_escape, ring_owner_reference, coarse_spin_escape, rotated_token, registry_alias_worker, shadow_slot | 60 | 60 | 12 decode rules, one sentence each, controls confirm | LEAKED (12/12) |
| generalises_to_a_fresh_stall_window, budget_ties_move, waits_sit_on_the_budget, registry_presentation_order_inverts, registry_carries_a_cycle, pool_boundary_shifts, new_worker_enters, dormant_rule_fires, window_scales, window_contradicts_the_control_slice, every_tag_has_one_live_row | 55 | 55 | stated window rules | LEAKED (11/11) |
| generalises_when_a_service_cell_empties | 5 | 0 | closed partition set (structural) | HELD |
| generalises_when_the_partition_count_changes | 5 | 0 | closed partition set (structural) | HELD |
| 4 negatives (-5,-5,-5,-3) | -18 | 0 | cheating acts | not triggered |

Total 132/142 = 93.0. Levers held: 1 of 26 rule units, worth 10/142 = 7%.

Channel B (judge, 37 positive points): R1-R5, R7-R11, R14 all earned (37/37); negatives R6, R12, R13 not triggered. Every criterion LEAKED by design (process restated from the instruction).

## 4. The two misses: the line that baked in the shipped shape

- `agent_program/derive_report.py:384` `self.cells = sorted(set(self.cell_of_host.values()))` and `:385` `self.tenant_segments = sorted(set(self.segment_of_tenant.values()))`; `:791-796` write `region_%s.json` / `segment_%s.json` only for those sets; `:807-808` run the partition self-check over the same sets.
- The shipped `host_cells.csv` cycles all four cells and `tenant_classes.csv` names both segments, so the habit is invisible on shipped data. Mutation `empty_group` (hosts on East, North, South) and `partition_count` (North, South) make the program skip `region_West.json` (and East), so `_run` fails on a missing file. The program exits 0; the failure is a plausible incomplete document set, not a crash.
- The governing rule is stated: `instruction.md:11` names the four region files and two segment files; `invariants-and-closure.md:50-53` "A cell or a segment that no counted event reaches still reports, and reports zero." The empty-report content is a determinate shipped fact: `sample_audit_answer.json` shows an empty lock class row (LCK-B) with zeros, `sample_summary_answer.json` shows present-only `by_lock_class`.
- How often the habit bites: today 2 of 25 hidden corpora (10/142 = 7%). The same derive-the-set-from-the-table habit governs both partition axes (cells and segments) and would bite in every hidden corpus whose own side tables omit a cell or a segment. Planted in 6 more corpora (8 of 25) it costs 40/142 = 28%.
- Self-tests never varied a side table: step 49 ran the incident journal with the SAME side tables, and the sample population as a capture (relocation, not altered contents). Nothing in its loop could expose the habit.
- QC exposure (must fix with LV-1): `calibration-and-controls.md:53-56` says a later capture arrives "beside the same side tables". The hidden tier already mutates side tables in 13 generalises corpora (`tests/test_output.py:834-862`), so the two current misses rest on inputs outside a stated bound (TS-19 / G12). Under the stated bound the agent's line 384 is defensible. Phase 2 restates the bound: a later capture brings its own copies of the side tables, laid out as the shipped ones are.

## 5. Trajectory autopsy

61 steps, 20:32:24-20:48:54 UTC (16.5 min).
- 0:00-0:30 read everything: `ls /app`, all six `.md` documents, controls, example report, sample answers, heads of every export.
- 2:00-4:00 byte style of the example report (indent, final newline), column survey, `probe1.py`.
- 5:00-8:20 scratch decoder `wire.py`, staged constant search `search1..5.py`; readings corrected by controls at steps 23-27 (padding/stride/ring padding) and 34 (0x010 byte order).
- 11:54 (step 35) wrote `/app/out/derive_report.py` in one piece. Steps 36-42: compared with the sample answers; one crash ("no candidate for depth complement width reproduces CTRL-D") fixed by the fit-width reading.
- Steps 43-53: carried record equals live search; fresh-capture test with identical side tables ("NEWCAP IDENTICAL"); small edits. Graded logic unchanged after step 53.
- Steps 54-59: second run into an empty directory, no-argument run, `AGENTS.md`, `ALL_CONSISTENT`. Step 61 final answer (constants match TRUTH PARAMS; 237 events, 161 counted, residual 19,070; settlement 2 passes).
- Self-tests covered: sample answers, carried vs live search, determinism, rerun. Never: recomputing any figure outside its program, altering any data copy, varying a side table.

## 6. Proposed levers (LEVER_RULES section 1; no L11, no H7)

Each lever is a stated single-reading rule, bites only on hidden or reseeded inputs the shipped window does not show, and the reflex program writes a plausible wrong document with exit 0. Costs below are planned single-lever losses on the 142-point channel (G10), to be measured with mutants in Phase 2.

| Lever | Type | Rule written at | Reflex reading (evidence) | Where it bites | Single-lever cost (G10) | One-fact-wrong (CL-4) |
|---|---|---|---|---|---|---|
| LV-1 closed partition sets | habit (structural shape, observed miss) | `instruction.md:11` file list; `invariants-and-closure.md:50-53`; bound restated at `calibration-and-controls.md:53-56`; EVIDENCE_MAP rows: sample answer empty LCK-B row, present-only `by_lock_class` | derive cells/segments from table values (agent `:384-385`, observed) | hidden corpora whose host table omits a cell or tenant table omits a segment: 8 of 25 | 40/142 = 28% | one missing or wrong file fails the whole corpus check: 5/142 = 3.5% per corpus; exempt via G5 sentence |
| LV-2 padding writes the owner window | L1 green control, wrong answer | `journal-and-wire.md:59-62` (0x008, padding "ordinary body lines in every other respect") and `:76-81` (0x080 "Every body line of the file, in logical order, writes its own owner into the window slot"), plus one added sentence placing padding after its segment's events in logical order | drop padding before decoding, ring advances on events only (agent enumerated ring padding True/False at steps 23-26 and let CTRL-E pick False) | every corpus where a padded segment precedes a ring reference within the window width: shipped window + 13 generalises; single-flag trap probes unaffected | 80/142 = 56% | a wrong owner moves held_count, implicated, settlement and every lock-class row: whole documents, exempt via G5 |
| LV-3 owner tags follow the registry's alias rows | L10 general rule in a rarely joined field | generalise `identity-and-registry.md:3-4` from "what a worker column names" to any worker tag wherever it stands, resolved at the epoch of the event that carries it; tags no alias row leads from stand as written | owner column used literally (agent `:336`, `:512-518`, `:534`, `:631`, `:639`; the reference does the same today) | hidden-only alias owner tags in 8 of 25 corpora (5 generalises + 3 traps) | 40/142 = 28% | a raw owner tag splits one worker row into two and can flip implicated: whole policy_audit and settled rungs; exempt via G5 |

Design notes.
- LV-2 is also a correctness fix: today the reference skips padding (`tests/test_output.py:143-264`, ring position advances on event lines only), which contradicts the literal text; CTRL-E is what told Opus the reference's reading (IN-16 risk). Phase 2 makes the reference follow the text, keeps CTRL-E reconciling under both readings (calibration puts no padded segment ahead of a ring reference inside the window width), and recomputes `control-slice-figures.json` if any figure moves. Sample population has all flags clear, so the sample answers do not move (Never 11 holds).
- LV-3 must leave shipped, calibration and sample answers unchanged. Checked with the reference resolver: shipped owners resolve to themselves 164 times and to retired/unresolved 73 times (WRK-1006/1008/1012/1016/1018), calibration 97/11, sample 20/0. So the rule is worded on alias rows only (a row whose canonical tag differs from its own tag): an owner tag follows alias rows at the carrying event's epoch, and any owner tag no alias row leads from stands as written. Hidden-only `ALS-` owner aliases always lead to an active canonical worker. CTRL-E and every shipped figure stay as they are.
- Independence: LV-1 is output-set shape, LV-2 is decode state, LV-3 is identity join; a slip on one never forces a slip on another.
- Not proposed: a neutral CTRL-D for 0x040 (Opus read the follower rule right from step 17, no reflex to exploit); `settlement.passes` (algorithm dependent); duplicate rows or missing pools/hosts (the reflex program crashes loudly, and referential closure forbids them); 0x010/0x004/0x008 byte-order and stride readings (text ambiguous today; Phase 2 rewrites each to a single reading that matches the reference, so they stop being control-picked, not levers).

All-but-one rows (G10, rubric taken from the planned judge, see section 7):

| Row | Tests | Judge (strong run, planned) | Overall |
|---|---|---|---|
| all right | 100 | 60 | 80 |
| only LV-1 wrong | 72 | 60 | 66 |
| only LV-2 wrong | 44 | 60 | 52 |
| only LV-3 wrong | 72 | 60 | 66 |
| reflex on all three (this run's habits) | about 25 | 60 | about 43 |

Trade-off for the master: with the default rubric of 90, the LV-1 and LV-3 rows give 81 (> 70). G10 holds only if the rebuilt judge measures near 60 for a strong run, or LV-1/LV-3 are planted in about 13 of 25 corpora each (about 46%), which pushes the expected Opus tests score under the 55-85 target. I propose the 8-of-25 planting plus the judge below, and will report measured mutant costs in Phase 2.

## 7. Judge rebuild (J1-J9, mode batched)

Replace the 14 process criteria. Planned:
- J2 conduct, w3 each, one per output family: summary, policy audit, region reports, segment reports, reconciliation and rejections, candidate search. Wording "The agent independently recomputes <figure> outside its program for every <item> and compares it with the program's output"; `solve.sh` prints `check <id> ok`. This run would miss all six (it compared only with the shipped sample answers and its own in-program checks).
- J9 w3: "The agent runs its program on a copy of the data whose contents it altered (not only relocated) and checks that the dependent figures move"; this run would miss it (step 49 relocated only).
- J6 enumeration w3 on the final answer (for example every quarantined lock class by id).
- J4 quality w3 (fixed wording), J3 honesty -5 (claims a check passed with no run after the last edit), keep the `/app/data` edit negative (-3).
- None of J2/J9 wording appears in `instruction.md`. Expected strong run: about 50-65.

## 8. Defects to fix in Phase 2 (beyond the levers)

| Id | Defect | Location | Fix |
|---|---|---|---|
| D1 | later capture "beside the same side tables" contradicts hidden side-table mutations (TS-19/G12) | `calibration-and-controls.md:53-56`, `tests/test_output.py:834-862` | restate the bound (own copies, same layout) |
| D2 | padding vs owner window: text says padding writes, reference skips | `journal-and-wire.md:59-62, :76-81`; `tests/test_output.py:143-264` | becomes LV-2 |
| D3 | 0x010 "byte pairs in the opposite order" has two readings | `journal-and-wire.md:64-65` | single-reading sentence matching `pair_reverse` |
| D4 | padding position (physical tail) and stride walk (true count) under-stated | `journal-and-wire.md:53-62` | single-reading sentences |
| D5 | W11: sample answer files ship graded document types | `environment/data/sample_summary_answer.json`, `sample_audit_answer.json` | kept per master (never contradict); flagged |
| D6 | IN-17 / W1 announcements and trap explanation | `instruction.md:1`, `:33`; `calibration-and-controls.md:29-31`; `identity-and-registry.md:25-26` | remove; add G5 sentence "Each output document is graded whole on fresh windows, and only an exact match counts." |
| D7 | TRUTH stale: verification notes say positive total 137 | `solution/TRUTH.md:387` vs `:157` (142) | refresh |
| D8 | `read_ladder` indexes rungs positionally; generator only emits contiguous rungs | `tests/test_output.py:302` | note only, no hidden case relies on it |
| D9 | judge restates process (J8) | `tests/judge.toml` | section 7 |
| D10 | `tests/__pycache__/` present | `tests/__pycache__/test_output.cpython-314.pyc` | delete |

## 9. LEAK_LIBRARY rows

| lever | how it was written | leaked at | fix rule |
|---|---|---|---|
| 12 wire transforms (0x001-0x800) | one sentence per flag in `journal-and-wire.md:42-95`; each bound to a control figure that reconciles only under the right reading | steps 17-34 (scratch decoder, then reading variants enumerated against CTRL-A..H) | W7: controls reconcile under both readings; L1 instead of confirmation |
| control figures as reading oracle | eleven figures, each sensitive to one transform's reading | steps 23-26 `HIT 5 7 logical False true 509767 108 hits 1`; step 34 CTRL-H picked 0x010 byte order | W7; rewrite ambiguous sentences to one reading (D3, D4) |
| lowest live revision | bold rule plus trap explanation `identity-and-registry.md:21-26` | step 35 (transliterated; `governing_row`) | W1: drop the trap explanation |
| alias hop limit / cycle / own-epoch pool / budget edge / ties | explicit sentences `identity-and-registry.md:35-39`, `epochs-and-clocks.md:38-43`, `attribution-and-blame.md:40-47` | step 35 | not levers; keep as stated rules, move cost to LV-1..LV-3 |
| one-survivor announcement | `instruction.md:1`, `calibration-and-controls.md:29-31` | steps 18-34 (search stopped at first unique survivor) | IN-17: remove |
| process judge | 14 criteria restating `instruction.md:33` | whole run (judge 100) | J8: J2/J3/J4/J6/J9 only |

## 10. Not run

- No harness run (blocked; master runs it). No fuzzing of the agent program against any changed bundle (G10, section 6). Mutant costs in section 6 are planned figures, measured in Phase 2.

DIAGNOSIS READY: /Users/mac/Desktop/Terminal Bench/master_chat_work/20261026_stall-graph-postmortem/harden_r1/DIAGNOSIS.md
