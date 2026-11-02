# DIAGNOSIS, cold-chain-backbone-quote, harden round _a4 (board b223662)

Run: gate_run_a4, claude-opus-5 (openhands-sdk), judge gpt-5.6-sol, frozen tree 8ca9c267f59b.
Score: tests 77.98 (85/109), rubric 43.75 (14/32), final 60.87. Agent time 13 min of 7200 s.
Round: harden round 2 of 3 in total (earlier: wave 1 678c839). No round marked LAST.
Kit HEAD 5574d77eb9f22c207ba05fd8f9ac31d42ba45271; `git diff 5574d77e HEAD -- Input_Bundle_QC/` empty.
No `baselines.json` exists for this task; this is the first harness run on record.

## 0. Trajectory read-out
`OUT/TRIP.md` (tool output plus the hand table). Correction to the tool: it labels the six wide losses WRONG.
They are not wrong output. `verifier/test-stdout.txt`:

    _check_fresh: exit -9:            (x3, wide_1/2/3_core)
    _check_wide: exit -9:             (x2, wide_books_report, wide_books_summary)
    _check_wide_feasible: exit -9: timed out after 50 s
    reward: 0.6087

Docker reproduction (python:3.12-slim, `--memory 4g --cpus 2`, agent package from patched-repo.zip, wide_1 from
`_write_corpus`): 50 s cap gives `rc=137 secs=50`, `memory.peak 4294967296`; a 150 s cap gives `oom_kill 1`.
fresh_1: all four documents byte-identical to expected, peak 18.9 MB. So the lever loss class is
CRASH (out of memory at the declared 4096 MB) and TIMEOUT (50 s = 4 s x 10 projects + 10 s), the v3.5 hidden-scale
class, not WRONG. The master's "lost tests all WRONG" line comes from the read-out tool.

| step | what the agent did | what the docs require (file:line) | check/criterion | class |
|---|---|---|---|---|
| 19 | rewrote core.py as Dreyfus-Wagner subset DP over all cold rooms | minimum-cost network, tie vector (api_contract.md:84-89); limit (api_contract.md:91-92) | wide_1/2/3_core, wide report, summary, feasible (24) | LOST_GRADED (CRASH/TIMEOUT) |
| 19-45 | never changed graded logic after first write | | all fresh/shipped/rescaled checks | EASY (exact DW at 8-10 cold rooms) |
| 25 | first command run after the rewrite, timed shipped book only | | R1, R5 | SKIPPED |
| 26-29 | brute force + random-project fuzz vs brute (shipped scale) | | none (H9 shipped-scale self-test) | EASY |
| 30 | re-derived the four documents independently | | shipped_* | EASY |
| 31 | removed links.jsonl + activation.ini, saw E_MISSING_FILE | api_contract.md:19-22 | missing_file_reported, R4 | EASY |
| 32 | test_fixes.json from CI log FAIL/ERROR lines | api_contract.md test_fixes section | test_fixes, R2 skipped (no set compare) | EASY / SKIPPED |
| 40, 43 | unzip, read-only, other cwd, cmp four docs | api_contract.md cwd/read-only invariant | rerun_identical, relocated, R6 | EASY |
| 45 | "verified", rejected list with codes | instruction.md:13 | R10 | EASY (J6) |
| - | no altered copy, no tie book, no larger book, no defect named before first edit | | R3, R5, R7, R8 | SKIPPED |

Why it scored this: every non-lever test (85/109) is solvable by an exact solver that is only exact at shipped scale,
because fresh books were reduced to 8-10 cold rooms in law1_fix 25c745d. The only biting lever (wide books) is 22% of
positive weight. Judge: 4 of 13 criteria were acts the agent does by reflex (missing-file run, byte compare,
maintainable code, rejected list). First write at step 19 (6 min), no stress test above shipped scale, slowness never
noticed, self-checks shipped-scale only (fuzz on random projects of shipped size).

## 1. Phase A: GENUINE
- Staged task `.kiro-staged-tasks/cold-chain-backbone-quote` vs BUNDLE: `diff -rq` shows only `.kiro-staged-from`
  and `task.toml` (harness adds `host.docker.internal` to allowed_hosts). tree_sha BUNDLE = Tasks_INPUT = 8ca9c267f59b.
- ctrf ids = the @criterion names of `tests/test_output.py` (33 entries), same file mtime in both trees.
- `result.json` exception_info null; verifier 400 s of 2700; no `Permission denied`/`Errno 13`; the only stderr lines
  are the six lever kills above; the judge reasoning quotes trajectory steps (31, 40, 43, 45), so it read the run.
Verdict: GENUINE.

## 2. Root cause
- Cause 1, run error or wrong copy: NO. Current tree, no errors (above).
- Cause 2, harness or rescoring change: NO. Kit diff empty; no earlier harness baseline exists (all earlier numbers
  are author kill tables), so nothing was rescored.
- Cause 3, our fix rounds made it easier: PARTLY.
  - law1_fix 25c745d, `tests/test_output.py` fresh draw `randint(16,17)` -> `randint(8,10)` cold rooms: made
    fresh_1..3 (core/report/summary 39), rescaled 5, relocated 3, feasible 3, rollups 3, rerun 1 free for any
    exact-at-shipped-scale solver (54 points). Done for Law-1 condition 3 (lever cost confined to lever checks), but
    it left the lever at 24/109 = 22%, below the v3.7 40% share.
  - P12 v1-v3 (5951927, 905cf6e, b0aca9b): wording and metadata fixes; archived_package_metadata w1 added (free).
    No rule, figure or separating example put in front of the agent.
- Cause 4, levers weak by design: YES (tests share), YES (judge).
  - Wide books (P-1, hidden-scale): HELD. The agent's DW is exponential in cold rooms; 30-41 cold rooms OOM. Nothing
    gave it away; it lost all 24 points. Weakness is weight only.
  - LV-CC-1 exact optimum, LV-CC-3 activation once, parser rules (closed links, override case, numeric slot),
    share_bp floor, E_MISSING_FILE, tie vector: all LEAKED by design, the contract states each rule and the shipped
    book plus regression_cases.jsonl fires every branch (step 14-16 the agent derived them; step 26-29 brute force
    confirmed). These are stated rules; they are now the floor, not levers.
  - Judge: PASS R4 (step 31), R6 (steps 40/43), R9 (step 19 core.py layout), R10 (step 45). FAIL R1 (step 25 first
    run after edit), R2 (step 13/32 count only), R3, R5 (step 25 shipped only), R7, R8. R10 restates a figure the
    shipped run prints (J1/J6 free); R4 and R6 are acts Opus does by reflex (P-h missing, byte compare); R9 is an
    opinion criterion a tidy rewrite passes (not behavioural J4).
PRIMARY CAUSE: 4 (lever share 22% plus four reflex judge criteria). Contributing: 3 (fresh books shrunk to shipped scale).

## 3. Lever table (reward-details.json)
| check / criterion | pts | earned | lever / template | status |
|---|---|---|---|---|
| wide_1/2/3_core | 15 | 0 | P-1 hidden scale | HELD (CRASH/TIMEOUT) |
| wide_books_report, wide_books_summary | 6 | 0 | P-1 | HELD |
| wide_networks_feasible | 3 | 0 | P-1 | HELD |
| shipped core/parser/report/summary | 16 | 16 | stated rules | LEAKED (floor) |
| fresh_1..3 core/report/summary | 39 | 39 | LV-CC-1/3 at shipped scale | LEAKED |
| rescaled, relocated, feasible, rollups, rerun | 15 | 15 | robustness | LEAKED |
| missing, rejections parser, tie core | 9 | 9 | stated codes / tie rule | LEAKED |
| archive, metadata, test_fixes, repair_report | 6 | 6 | deliverable format | LEAKED |
| R1 R2 R3 R5 R7 R8 | 18 | 0 | P-f, P-c, P-d, P-a, P-g, defect-first | HELD |
| R4, R6 | 6 | 6 | P-h, byte compare | LEAKED |
| R9 maintainable | 5 | 5 | opinion code quality | LEAKED |
| R10 rejected list | 3 | 3 | J6 enumeration | LEAKED |
| R11-R13 negatives | 0 | 0 | J3a-c | not fired |

Arithmetic: final = (77.98 + 43.75) / 2 = 60.87. A probe-band judge rebuild alone at the peer 25% probe rate:
probes 21 x 0.25 = 5.25 + R9 5 + R10 3 = 13.25/32 = 41.4% -> final (77.98 + 41.4)/2 = 59.7; with R9 rebuilt as a
behavioural J4 the a4 run fails (no handler for malformed JSON/CSV; tracebacks without naming the file): 8.25/32 =
25.8% -> final 51.9. Judge-only cannot reach 35; the tests half must fall to about 45.

## 4. Autopsy (B1)
Read order: file list, api_contract.md (step 4), ci configs and data heads (5), repo files (6-8), visible tests, lint,
CI log (9), regression cases and shipped duplicates (14-16). Wrote core.py at step 19 (22:32:41, 6 min in); later
edits steps 20-24 parser/report/main/pyproject, 36-37 cosmetics; the graded algorithm never changed after step 19.
Self-tests: brute force on shipped projects (26), fuzz 421 random projects of shipped size (27-29), independent
re-derivation (30), missing-file run (31), regression compare (34), unittest (38), archive rerun read-only from another
cwd with cmp (40, 43). Levers covered: all stated rules at shipped scale; none at hidden scale. Time: reading 5.5 min,
writing 1.5 min, self-tests 5 min, packaging 1 min. Slowness never noticed (shipped 96 projects 3.2 s).

## 5. Agent program
`OUT/agent_program/out/` (seven run artifacts) and `OUT/agent_program/repo_from_zip/` (unzipped patched-repo.zip;
core.py identical to the artifacts copy). Diagnoses 8ca9c267f59b only (G10).

## 6. Planned fix (Phase 2, needs go)
Tests (keep wide-book lever, N2 shape): add six held-out wide books wide_4..wide_9 (`_make_wide(BOOK_SEED+4+k)`,
same generator bounds as wide_1..3), each with core w5, report w5, summary w3 (+78). No reweighting of existing checks.
Positive 187; wide 102/187 = 54.5%; held-out w5 tier (fresh core/report, rescaled, wide core/report) 110/187 = 58.8%.
a4 program on new tests: 85/187 = 45.5%. Each new book is its own `_run_cli` call (v3.5 condition 3). Verifier worst:
about 1700 s of 2700 (target <= 2430).
Judge (probe band): keep failed probes R1, R2, R3, R5, R7, R8; replace R4 and R6; add P-a override case, P-b
one-project witness, P-h malformed links line, toward 12 probes w3; R9 rebuilt as behavioural J4 (exception handlers
act on what they catch; malformed declared input stops naming the file), oracle made to meet it; keep J3a -3, J3b -5,
J3c -3. Decision for the master: the J6 final-reply criterion (R10, instruction.md:13). With it (layout A: 36 + J4 5 +
J6 3) a4-like mid = 27.3% and final needs 7 new books (42.5 + 27.3)/2 = 34.9; without it (layout B: drop the final-reply
request and R10) mid = 22.0% and six books give (45.5 + 22.0)/2 = 33.7. Both put probes above the 55-70% band, because
mid <= 20 at a 25% probe rate is impossible inside that band unless the non-probe criteria also fail. Default: layout B.
QC v4 MINOR G05-M1 (AL-18, TRUTH.md:24-25 author-facing) fixed while editing TRUTH.

## LEAK_LIBRARY rows
| lever | how it was written | leaked at | planned fix |
|---|---|---|---|
| fresh books exact (LV-CC-1/3) | hidden books drawn at the top of the shipped size range (8-10 cold rooms) after law1_fix | step 19 (first write already exact at that scale) | not a lever any more; weight moved to held-out wide books |
| R4 missing-file probe | P-h with the code stated in the contract | step 31 | replace with a malformed-line probe |
| R6 byte-compare probe | "two runs compared byte for byte" | steps 40/43 | drop; rerun is a test |
| R9 maintainable | opinion code-quality criterion | step 19 | behavioural J4 |
| R10 rejected list | final reply restates the shipped run's rejections (J6) | step 45 | drop with the request, or keep at w3 under layout A |
