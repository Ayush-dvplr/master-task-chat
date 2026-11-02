# cold-chain-backbone-quote: Law-1 fix 25c745d (27 Oct 2026, tests-only)

BUNDLE: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/cold-chain-backbone-quote/`
WORK: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/cold-chain-backbone-quote/`
QC kit HEAD 5574d77e. Fingerprints re-hashed: GEN 160 and QC 12 files, 0 differences.
Session rename: `name_session.py 25c745d` gave "codex: no match / opencode: ['ses_e821dc79bffeBbz3QAjw6uyKNb']", so it was renamed in opencode.

## Cause
`_fresh_book_parts` still drew 16 or 17 cold rooms per fresh project, a leftover of the pre-wave-1 design (M6), which moved the hidden books to 16-17 cold rooms so that DW would time out. The shipped book has 4-10. A subsets method (3^k) takes 41-128 s per project at 16-17 cold rooms, against a 4 s limit. So DW and blind eac8712 timed out on fresh_1..3, rescaled, relocated and rerun, which cost 54 non-lever points. See `DIAGNOSIS.md`.

## Change (one helper, data only)
- `tests/test_output.py:6088`: the docstring now reads "Ten hub projects with 8 to 10 cold rooms, ...".
- `tests/test_output.py:6098`: `rng.randint(16, 17)` became `rng.randint(8, 10)`. 8-10 is the top of the shipped range. Sites (38-52) and links (65-92) were already inside the shipped range (up to 52 sites and 94 links).
- `tests/test_output.py:6104`: the assert now reads `8 <= len(P["terms"]) <= 10`.
- The source is `WORK/test_template.py:876/886/892`, rebuilt with `embed_tests.py`. G7 diff against `WORK/runs/pre_l1/`: 3 hunks, all named. AST compare: only `_fresh_book_parts` changed. All check bodies, criteria, weights, the wide generator and the wide checks are byte-unchanged. No doc sentence was changed, and `api_contract.md:91-92` is untouched. Hole grep: nothing added to agent-visible files.
- The books that change are fresh_1..3, rescaled, relocated and missing (all built from fresh seeds). Rejections, ties and wide_1..3 are unchanged. Expected values come from the in-test reference (`_expected_documents`), so nothing is hard-coded.
- `solution/TRUTH.md` was rewritten by `WORK/truth_l1.py` (trap bullet :24-30, timing table :62-71, :73 "8 to 10 cold rooms", measured :119-123, pitfall :160-161), then `finalize_truth.py`.
- WORK records: LEVERS.md, COST_TABLE.md, KILL_TEST.md, QC_DEFENCE.md, XREF.md (new key "fresh book cold rooms") and RECHECK_FIX.md (G4 rows, plus FIX_SIDE_EFFECTS IN-15 regeneration -> DS-22, TS-17, TS-24, AL-18, AL-19 re-checked). `w1_variants.py` now also deletes the copied oracle docs when a variant's shipped build crashes.
- Generator sweep (Docker): `sweep300.py` gave `SWEEP PASS seeds 300 worst reference seconds per project 0.262` (wide skipped because it is unchanged; log `runs/sweep_l1.log`).

## Timing per project in Docker (s; `runs/time_before.log`, `runs/time_books_l1.json`, kill logs)
| program | shipped (4-10 cold, 10-52 sites) | old fresh/rescaled/relocated (16-17 cold) | new fresh books (8-10 cold), full tests |
|---|---|---|---|
| blind eac8712 (DW) | max 0.19, sum 2.24 | >12 (capped) | all fresh, rescaled, relocated and rerun checks pass within 50 s |
| DW over all cold rooms | max 0.16, sum 1.89 | >12 (capped) | pass |
| probe, span lifted | max 0.10 | <=0.012 | pass |
| d7a0, span lifted | max 0.10 | <=0.006 | pass |
| 2611, span lifted | 9.0 s, P4080 >12 s, OOM at 4 GB | <=0.013 | fresh pass; shipped crashes |
| oracle CLI per book | - | - | fresh 0.08-0.10, rescaled 0.09, relocated 0.08, wide 0.14-0.15 (limit 50) |
The after-fix per-project timing of DW and eac8712 was not re-run with `time_projects.py`. The evidence is the full test run, where every fresh check passes within the 50 s book limit.

## Kill table (Docker, final data, 108 positive points; `runs/kill_l1_{a,b}.log`)
| solver | tests% | lever lost | non-lever lost | kind | shipped fast |
|---|---|---|---|---|---|
| oracle | 100.0 | 0 | 0 | - | yes |
| blind eac8712 (DW over cold rooms) | 77.78 | 24 | 0 | TIMEOUT | yes |
| DW over all cold rooms | 77.78 | 24 | 0 | TIMEOUT | yes |
| hybrid DW<=14 else corridor sweep | 77.78 | 24 | 0 | TIMEOUT | yes |
| probe package, span removed | 77.78 | 24 | 0 | TIMEOUT | yes |
| blind d7a0, span removed | 77.78 | 24 | 0 | TIMEOUT | yes |
| last-use sweep, corridor order | 75.0 | 24 | 3 (tie, no rank bit) | TIMEOUT + WRONG | yes |
| last-use sweep, min-waiting order | 75.0 | 24 | 3 (tie) | TIMEOUT + WRONG | yes |
| blind 2611, span removed (window = widest link) | 62.96 | 24 | 16 (shipped docs) | CRASH on shipped + TIMEOUT | no |
| window frontier, corridor order | 60.19 | 24 | 19 | CRASH on shipped + TIMEOUT + WRONG | no |
| window frontier, BFS order | 10.19 | 24 | 73 | TIMEOUT + WRONG | no |
| naive relay-subset search | 10.19 | 24 | 73 | TIMEOUT + WRONG | no |
| KMB / shortest-path / greedy | 22.22 | 21 | 63 | WRONG | yes |
| blind 2611 / d7a0 / probe as shipped (span 4) | 60.19 | 24 | 19 | WRONG | yes |
Pass: every plausible exact program that is fast on the shipped book (eac8712, DW, hybrid, probe, d7a0) loses only the 24 lever points (22.2%, inside 10-30%) and 0 non-lever points. Before the fix, DW and eac8712 scored 30/108. The last-use prototypes' tie loss is a prototype defect (WRONG), unchanged from wave 1.
Open for the master: the window sweeps (2611 span-lifted, window frontier) crash on the SHIPPED book. That failure is visible to the agent (v3.5 condition (1) does not apply to them). Making them fast would need short-reach shipped links, which is the span-regularity hidden rule that wave 1 removed, so the shipped data was left unchanged.

## Gates
- Stacking: `STACKING_CHECK.md`, `STACKING PASS`. The AL-28 split was done by hand, carried over from 678c839, and the automatic part is byte-identical.
- PRECHECK last line: `PRECHECK CLEAN`. Pre-existing notes: DS-22 fix_patch_sha256 names no file, and SELF_CHECKS.md is missing.
- QC: structure, instruction, tests and judge_qc all PASS. Validator: `SUMMARY: 41 passed, 9 failed, 0 warnings`. These are the same 9 pre-existing FAILs from the core.py artifact (§1.12 cascade), which is the master's choice from 678c839; none is new.
- xref_check: 11 entries, 0 findings.
- Docker harbor (tests only, exe_copy copies, `runs/gates_l1.log`): oracle 1.0 / 1.0 / 1.0, owner-only 1.0, nop 0.0, stub 0.0, forgery 0.1944.
- Tasks_INPUT: tests/test_output.py and solution/TRUTH.md copied (`cp -p`). `diff -rq BUNDLE Tasks_INPUT` is empty (rc 0). Tree sha 61ec481d33a6 (was b2df10e170e9).

## Not run
- No blind read, probe or real-model run. The judge was not run (no API key), so all scores are tests-only.
- Old `WORK/mutants.py` was not re-run (as in wave 1).

## Lessons for the master
- A cold-room count chosen for a retired lever stayed in the hidden generator and turned a valid exact method into a non-lever timeout | template_change: anubis harden prompt should list every hidden-book size knob to re-check when a lever is retired
- A crashed variant build left the oracle's docs in place (w1_variants caught only timeouts) | no change: fixed in WORK/w1_variants.py
- A window sweep sized by the widest link fails on the shipped book itself, so v3.5 cannot count it either way | no change: master decision recorded in DIAGNOSIS.md
