# Stage-2 test-design study — board 191d357

**Session:** Codex, not renamed. **Scope:** read-only inspection; all new files are under this study directory. No network, Docker, harness, or repo mutation.

## Method and coverage

`scripts/inventory.py` reads `task.toml`, `reward-details.json`, `test-stdout.txt`, test source and git history for every UUID task. It writes `inventory.csv` and the capped selection. `scripts/cards.py` indexes selected instruction, docs, tests, judge and trajectory steps without printing a whole trajectory. `scripts/metrics.py` regenerates pattern and Easy-contrast totals. The current repository HEAD is the user-specified `48251f80`; the task list is the checked-out stage-2 set. **110 tasks scanned; 25 deep-read cards; 60 qualifying IDs omitted by the cap** (`scratch/selection.json`, scripts above). Of 25 cards, 24 have only `reward: x` in verifier stdout; their first differing field and true failure kind cannot be reconstructed from verifier files. `inventory.csv` records unresolved weight separately; hidden share inferred from criterion names is a lower bound, not a complete data-flow audit.

## Five findings

1. **P1 fresh exact extracts:** 7 selected tasks lost 655.51 test points in total, or 93.64 per task (`scripts/metrics.py`). `59417607` passes its seven shipped checks and fails all 18 hidden weight-5 extracts (`cards/59417607.md`; `solution/TRUTH.md:54-59`). Its hidden per-day clock change conflicts with the copied “never adjusted” sentence (`record_dictionary.md:19`), so that specific variant would fail our IN-16/TS-19 review.
2. **P2 carrier/source variation:** 7 tasks lost 645.16 summed test points (`scripts/metrics.py`). `1d61e794` varies seed, workbook, memo, profile and filenames (`tests/test_output.py:2201-2253`, `instruction.md:3`). Recorded agents mostly passed form/presence, not the core reports, so carrier variation is a promising architecture but not isolated as the cause in those runs.
3. **P3 inference and carried state:** 6 tasks lost 569.79 summed test points (`scripts/metrics.py`). `aa314fee` propagates shortfall across cycles (`solution/TRUTH.md:8`); `8defd7be` relies on an unbounded family of withheld forms (`solution/TRUTH.md:3-20,121-127`) and is AVOID under our DS-21/IN-16.
4. **Full-size and time limits:** one selected task's full-size check failed to finish cleanly (`fabbe645/verifier/test-stdout.txt:24`), but **zero timeouts are proven** by these verifier logs (`scripts/metrics.py`). A stated service limit is visible in `fabbe645/instruction.md:19`; the stored failure does not separate timeout, crash and missing output. TS-11 requires timed prototype distributions and a wide reference margin.
5. **Exact grading exposes prior logic errors:** `59417607` compares all reports bytewise (`tests/test_output.py:1357-1368`), while `5048c412` promises byte-exact text and value-exact workbook/database outputs (`instruction.md:5`). Tightening alone did not make a contract-correct program fail in any verified card. Whole-document gates can multiply one upstream error and need a CL-4 one-fact-wrong audit.

## Hypothesis verdict

**R0 confirmed within the verified sample, with an evidence limit:** INFERRED classification: 0 of 25 cards verifies that *most* TEST loss is a misread documented rule on shipped-like data (`scripts/metrics.py`, `cards/`). Some fail shipped core checks, but the verifier gives no first difference to prove that mechanism. The best transferable design isolates shipped-pass/hidden-fail; this does not establish a universal claim over the 60 omitted tasks. Stage-2 acceptance is not our QC pass: no task-local QL/PL note file was found, and `PATTERNS.md` records explicit IN-16, DS-21 and TS-27 risks.

## Fix-plan summary

- **Slipway:** read the pending paid a4 score before changing frozen bytes; its already-built crosswalk P1 tier predicts a3 loss, while a careful enumerator passes. Consider P5 scale only after an oracle-safe timing bracket; otherwise park (`FIX_PLAN.md`).
- **Hangar:** implement the reviewed nine legal Word carrier variants and independent field views; DESIGN.md predicts a1 loses the new tier while a careful reader passes. This is the concrete go candidate (`FIX_PLAN.md`).
- **Flood:** the shared-crew cap defeats a3-style programs but both blind programs remain exact. Prototype a stated, oracle-safe P5 runtime gap once; otherwise park (`FIX_PLAN.md`).
- **Depot:** a2 matched 2,312 determinate folders (`a2_score/A2_SCORE.md:5-37`). No current contract-valid wrong case exists; park unless a 120-second runtime gap is proved (`FIX_PLAN.md`).

## What was not read or verified

The 60 omitted qualifying task trees were inventoried but not deep-read; `scratch/selection.json` lists them. No task's tests or oracle were executed. No independent output diff was possible for 24 reward-only stdout files. This study does not certify any teammate task against our QC kit or verify timing margins on grader hardware. Pattern totals assign one primary design per card; overlapping mechanisms are discussed in `PATTERNS.md` rather than double-counted.

## Lessons for the master

- Require a paid-program differential on a contract-valid hidden input before reweighting tests.
- Treat byte/whole-document exactness as a score multiplier, with CL-4 localisation proof.
- Hidden carrier forms and inferred rules need an explicit semantic ground and branch witness.
- A low final band can conceal high test pass or judge rescue; inspect both channels.
- Stop route-1 work when careful programs match all targeted branches and no timing gap appears.
