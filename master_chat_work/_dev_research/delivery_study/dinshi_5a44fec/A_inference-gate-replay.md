# A — inference-gate-replay

**Verdict: GENUINE** (wrong recovered constants / state rules; no crash, path or permission artefact found). One open scoring question noted below (INFERRED).

Recorded: overall 21.77 / tests 36.56 / rubric 6.98 (score.json). Positive weight 93. Passed = 7×1 + 9×3 = 34 → 34/93 = 36.56 exactly.

## Task shape
Constant-recovery task: instruction.md says the notes give the stages but "What they do not give is any of the numbers … working out what that list even holds is part of the job" (instruction.md:3). Evidence = one worked older shift (example_probes.jsonl + example_verdicts.jsonl) and sha256 digests over the four reports of the recorded shift (digest.json), "There is no partial signal underneath it" (instruction.md:7). Deliver `/app/out/gate.py`; tests drive it over generated shifts.

## Artefact evidence (none decisive)
- result.json `exception_info: null`; agent 19:03:32-20:10:18 UTC (67 min of 7200 s; instruction asks to stop constant work after 1500 s).
- Only gate.py in artifacts/app/out (expected: reports are written by tests' runs).
- Negatives (-5,-3,-3,-3) all not fired.
- The program ran with exit 0 on a generated unseen-type shift: `program_writes_the_four_reports_from_two_directory_arguments` PASSED and it calls `_run("shape", SHAPE_SEED)` → `build_unseen(seed)` and asserts `code == 0` (test_output.py:1345-1346, 1136-1143). Empty-shift test also passed.

## Failed checks
| test | w | kind |
|---|---|---|
| accelerator_responses_match_the_reference | 1 | wrong VALUE: reference `fpga` → `figure - (figure % 7)` (test_output.py:113-114); agent `ACCEL_ADJ 'fpga': ('a', 0)` (gate.py:40) |
| segment_boundary_resets_the_accumulator | 3 | wrong VALUE (state rule) — detail Step 2 |
| backlog_stops_at_its_ceiling | 3 | wrong VALUE (ceiling constant) — Step 2 |
| segment_budget_reads_the_whole_shift | 3 | wrong VALUE (budget scope) — Step 2 |
| verdict_ladder_takes_the_first_condition | 3 | wrong VALUE (ladder order) — Step 2 |
| endpoint_total_counts_the_reference_verdicts | 3 | wrong VALUE — Step 2 |
| endpoint_dispositions_follow_strikes_and_backlog | 3 | wrong VALUE — Step 2 |
| full_ledger_on_unseen_shift_alpha…hotel | 8×5 | scored by `_score`/`_ledger_fraction` (1200-1279): fraction of per-record decisions; whole verdict record must match |

All `_holds` checks compare whole report bytes on small built probes (`_probe`/`_state`/`_state_rollup`, 1282-1299) — a failure is a wrong value, the program ran (exit asserted first).

## Open scoring question (INFERRED, cannot run)
The 8 unseen-ledger criteria are fractional (`_score` returns float in [0,1], test_output.py:1325-1340), yet the total is exactly 34/93, i.e. all 8 fractions contributed ~0. `shift.json` keys include copied counts (`SHIFT_KEYS` 1051: "endpoints", "probes"…) that a running program should hit, so a true 0.0 needs either exit ≠ 0 / timeout (25 s budget, 1108-1129) on those seeds, or the recording pipeline storing only pass/fail (report.json has only `passed` bool per test). Either way the agent's ledgers were not fully correct (several component rules fail on isolated probes), so the verdict stays GENUINE; the size of the loss on these 40 points may be overstated by binarisation — flag for master.

Points lost: 59/93 positive weight (63.4 test points); of those 40 sit in the unseen-ledger tests.
