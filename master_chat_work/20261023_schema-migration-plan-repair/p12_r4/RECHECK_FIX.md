# P12 r4 recheck and fix: schema-migration-plan-repair

Board `922c9f2`; QC v5 board `20508e3`; live kit HEAD `71a653b23fc2a6bc7ff3d4a8c286ec9a1b6a298e`. The live kit is authoritative and matches the report's kit. Saved GEN/QC fingerprints are older: `FORMAT_SPEC.md` and `structure_qc.py` differ from the `3fb1650b` fingerprint; the named live kit remains `71a653b2`.

## Finding decisions

| ID | Label | Live rule quote | Bundle evidence and QC finding | Decision / playbook | Lever effect; compensation | Files changed |
|---|---|---|---|---|---|---|
| IN-16 / CL-5 | REAL | `01_Instruction_QC.md:46`: “something graded depends on the answer”; “two readings that a competent practitioner could both defend”; “nothing in any file the agent can read picks between them.” `Final_checklist.md:492` CL-5: silent exact requirements must be stated or compared insensitively. | QC v5:38: “module reports grade a meaning of ‘changed’ the contract never states.” K19 `environment/ci/repository_contract.md:130-132` says “every function or method you changed or added”; `tests/test_output.py:9166-9189,9204-9208` ignores comments, docstrings and layout and names only module functions/class methods. A text-only edit can be honestly listed but fails `module_core_claims_match_archive` (QC measured 136/137). | FIX, row IN-16. Add one general clause to K19 in its own voice, defining the syntax tree comparison and nested-function naming. All three kit parts are met; CL-5 is the same defect. | Every lever none; none. | `environment/ci/repository_contract.md`, TRUTH digest |
| DS-22 | REAL | `02_Data_Solution_QC.md:78`: “TRUTH.md describes the bundle that actually shipped”; compare solution shape and verification counts with code and registrations. | QC v5:43: “TRUTH.md gives a stale line count”; `solution/TRUTH.md:182` says 604; `wc -l solution/solve.py` is 617, agreeing with TRUTH:249. | FIX, row DS-22. Correct line count, then all test counts/shares affected by TS-13. | Every lever none; none. | `solution/TRUTH.md`, `WORK/TRUTH.src.md` |
| TS-13 | REAL | `03_Tests_QC.md:44`: “One property per test. A test asserting two unrelated properties hides which one failed and skews the weight.” | QC v5:45: “two checks join separate properties.” `tests/test_output.py:9339-9341` joins P1/P2/P3; :9238-9245 joins member safety with K1 layout. | FIX, row TS-13. Three separate resolve cases at weight 1 each; archive layout positive +1 and unsafe-member detection negative -1. TS-25 rechecked on every half. | Every lever none by code inspection; compensation is revert a harmful split if a valid variant retains <90% of its before loss. | `tests/test_output.py`, `tests/reward.toml`, `solution/TRUTH.md`, `WORK/TRUTH.src.md`, `WORK/LEVERS.md`, `WORK/XREF.md`, `WORK/QC_DEFENCE.md` |
| TS-23 / A3 | REAL warn | `03_Tests_QC.md:62`: “at most 35 (warn)”; live `tests_qc.py:295` prints “cap is 35 (warn)”. | QC v5:50: “46 checks, above the 35 cap”; live script on current bundle: `WARN [A3] 46 checks; cap is 35 (warn)`, 0 FAIL. | KEEP, row TS-23. Splitting TS-13 gives 49 checks, below the 70 hard cap; merging lever checks would lose separate properties. | Every lever none; none. | None |

For every row, the effects on STATE, TIE, SCALE, NULL, POLICY, TOKENS, CORR, REPLAY, FEED, REPORT, CLI, STRUCT and HONESTY are `none`; no compensation changes a lever. The TS-13 survival measurement below verifies this where replayable variants exist.

The ID and wording of all four live rules match the report. QC v5 QL coverage has 11 PASS and 0 FAIL rows. QC_DEFENCE's 49-check choice and the P12 r2 changed-functions entry support the decisions; QC_RULINGS records TS-13 split precedent and IN-16 settlement precedent.

## Deviations from master directions

The suggested clause “docstrings alone do not change it” was also tightened to “after omitting its leading docstring”: `_code_dump` removes only the named function’s leading docstring, and a nested helper remains in its containing function’s tree. The grader stayed unchanged.

The requested positive `archive_members_safe` half would violate live TS-25 (`03_Tests_QC.md:52`): its decisive assertion passes when an unsafe member is absent, including on an empty archive. It is a negative weight-1 check; `archive_src_layout` remains positive weight 1. Hence the final positive total stays 137, not the proposed 138. An empty archive earns no archive point; an archive with `../escape.py` fires the negative. No hidden case was changed. The archived r3/auditor variant set cannot be replayed on the rebuilt layout; the existing current-branch `measure_variants.py` definitions provide 24 valid before/after tests-only comparisons. No new wrong-reading definition was made.

## Trap baseline limitation

`WORK/wrong/r3/` contains only `summary.json`, with no variant programs or deliverables. Its `make_wrong.py` reads `environment/data`, which this bundle no longer ships. The existing `auditor_r1/solvers/*.py` are from the earlier `/app/data/repo.zip` contract. An unchanged `S3_F.py` run on a staged copy of the current inputs exited 1: `src/migrakit/core/records.py: expected exactly one occurrence of the shipped text`. Therefore these archived files cannot produce valid current-test scores as they are. No new wrong-reading implementation was built. The blind r1 deliverables score 137/137 tests-only before the fix.

## Gate results

- Live QC scripts: `structure_qc.py` 17 pass/0 fail; `instruction_qc.py` 5/0; `judge_qc.py` 19/0; `tests_qc.py` 36 pass, A3 warn for 49 checks, 0 fail. The live kit is the report's `71a653b2` revision.
- `xref_check.py`: 38 entries, 0 findings. TRUTH: 33 listed environment digests all match, `solve.py` 617 lines; registrations are 49 total, 43 positive worth 137 and 6 negative worth 14; judge 10 criteria.
- Manual TS-13/TS-25: each identity half compares one P1/P2/P3 result. `archive_src_layout` fails on an empty archive; `negative_unsafe_archive_members` fires on `../escape.py`. The diff from `WORK/trap/before/tests/test_output.py` changes no hidden world or its separating data.
- Manual IN-16/CL-5: copied blind deliverables, added only a comment to `core.fingerprint.record_fingerprint` in the archive and listed that name in `module_core.json`. `_module_claims` still rejects the name (136/137 tests-only versus blind 137/137); K19 now states that comment-only edits do not count. The same test logic remains.
- `stacking_check.py` static hints were corrected by hand in `STACKING_CHECK.md`; distinct world observables and separate negative acts yield STACKING PASS. Shares: isolated 31/137 = 22.6%; composed hidden worlds 95/137 = 69.3%; shipped-only 6/137 = 4.4%; counts below the 70 caps.
- Verifier images warmed from the live `exe_copy.py` plain copy. One serialized, no-delete Docker chain has `ALL_DONE`: oracle tests-only 1.000/1.000/1.000, owner-only 1.000, nop 0.000. Final-byte jobs: `/tmp/smpr-p12r4-final-20261023T160318-7483/jobs` (ALL_DONE). A first chain on the earlier draft also completed but is not the final-byte result.
- Session rename at start printed a Codex UUID and `opencode: no match`, so the list did not show `922c9f2`; no other ID was tried.
- A diagnostic `uv run` in the harness root recreated its ignored `.venv` before it was stopped; `git status --short` shows no tracked harness changes. All later QC runs used the direct Python 3.12 interpreter.


## Trap survival

The requested archived set is not replayable on this bundle. Under the common baseline-validity rule, a program that exits before producing artifacts cannot supply a loss baseline; the existing current-branch variant definitions are the valid substitutes for the survival decision. `wrong/r3/` has scores only; `wrong/make_wrong.py` points to removed `environment/data`. The direct audit ran all 17 unchanged auditor solver files on staged current inputs: every S3 single-wrong-reading program exited 1 before producing any artifact (`expected exactly one occurrence of the shipped text`). `S2_lazy`, `S2_shipped`, and `SC1_claim_padding` produced artifacts but are not single-wrong-reading variants. No grader error was counted as a score. The current-branch `measure_variants.py` definitions were replayed as the valid substitute trap check; no new wrong-reading rule was authored.

| variant | before loss of P | after loss of P | ratio | separating cases kept | verdict |
|---|---:|---:|---:|:---:|---|
| current/F1-F4 planner | 101/137 | 101/137 | 1.000 | y | PASS |
| current/F5 from_payload | 69/137 | 69/137 | 1.000 | y | PASS |
| current/F6 decoy null | 38/137 | 38/137 | 1.000 | y | PASS |
| current/F6 fill | 40/137 | 40/137 | 1.000 | y | PASS |
| current/F7 parser merge | 37/137 | 37/137 | 1.000 | y | PASS |
| current/F7b tokens_for or | 37/137 | 37/137 | 1.000 | y | PASS |
| current/F8 executor | 50/137 | 50/137 | 1.000 | y | PASS |
| current/F9 classify | 48/137 | 48/137 | 1.000 | y | PASS |
| current/F10 admit | 72/137 | 72/137 | 1.000 | y | PASS |
| current/F11 order | 47/137 | 47/137 | 1.000 | y | PASS |
| current/F12 identity | 48/137 | 47/137 | 0.979 | y | PASS |
| current/F13 feed | 45/137 | 45/137 | 1.000 | y | PASS |
| current/F14 summary | 53/137 | 53/137 | 1.000 | y | PASS |
| current/F15 cli | 29/137 | 29/137 | 1.000 | y | PASS |
| current/W_alias_before_id | 45/137 | 43/137 | 0.956 | y | PASS |
| current/W_corrections_sorted_by_id | 47/137 | 47/137 | 1.000 | y | PASS |
| current/W_tokens_after_planning | 38/137 | 38/137 | 1.000 | y | PASS |
| current/W_cast_int_drops_integral_float | 42/137 | 42/137 | 1.000 | y | PASS |
| current/W_cast_touches_null | 37/137 | 37/137 | 1.000 | y | PASS |
| current/W_cast_converts_booleans | 37/137 | 37/137 | 1.000 | y | PASS |
| current/W_fingerprint_ascii_escaped | 47/137 | 47/137 | 1.000 | y | PASS |
| current/W_schema_before_partner | 43/137 | 43/137 | 1.000 | y | PASS |
| current/W_partner_before_batch | 42/137 | 42/137 | 1.000 | y | PASS |
| current/W_holder_needs_known_schema | 42/137 | 42/137 | 1.000 | y | PASS |
| r3/W1_prereq_on_received | n/a | n/a | n/a | y | unavailable: summary only |
| r3/W2_last_edge_tie | n/a | n/a | n/a | y | unavailable: summary only |
| r3/W2b_fewest_steps | n/a | n/a | n/a | y | unavailable: summary only |
| r3/W3b_schema_dijkstra | n/a | n/a | n/a | y | unavailable: summary only |
| r3/W4_fill_nulls | n/a | n/a | n/a | y | unavailable: summary only |
| r3/W4b_ini_only | n/a | n/a | n/a | y | unavailable: summary only |
| r3/W4c_merged_tokens | n/a | n/a | n/a | y | unavailable: summary only |
| r3/W5_fp_after_tokens | n/a | n/a | n/a | y | unavailable: summary only |
| r3/W5m_fp_after_migration | n/a | n/a | n/a | y | unavailable: summary only |
| r3/W5b_file_order | n/a | n/a | n/a | y | unavailable: summary only |
| r3/W5c_raw_alias_key | n/a | n/a | n/a | y | unavailable: summary only |
| r3/W6_null_fix_at_call_site | n/a | n/a | n/a | y | unavailable: summary only |
| r3/W7a_corrections_up_front | n/a | n/a | n/a | y | unavailable: summary only |
| r3/W7b_no_recheck | n/a | n/a | n/a | y | unavailable: summary only |
| r3/W7c_failed_as_migrated | n/a | n/a | n/a | y | unavailable: summary only |
| r3/W7d_every_arrival | n/a | n/a | n/a | y | unavailable: summary only |
| r3/WF1_one_merge_hop | n/a | n/a | n/a | y | unavailable: summary only |
| r3/WF2_abort_on_bad_line | n/a | n/a | n/a | y | unavailable: summary only |
| r3/WR_summary_by_status | n/a | n/a | n/a | y | unavailable: summary only |
| r3/WC_cli_paths | n/a | n/a | n/a | y | unavailable: summary only |
| r3/W3_enumeration | n/a | n/a | n/a | y | unavailable: summary only |
| auditor_r1/S3_C | n/a | n/a | n/a | y | invalid: exited 1 before artifacts |
| auditor_r1/S3_D | n/a | n/a | n/a | y | invalid: exited 1 before artifacts |
| auditor_r1/S3_F | n/a | n/a | n/a | y | invalid: exited 1 before artifacts |
| auditor_r1/S3_LV-MR-1 | n/a | n/a | n/a | y | invalid: exited 1 before artifacts |
| auditor_r1/S3_LV-MR-2 | n/a | n/a | n/a | y | invalid: exited 1 before artifacts |
| auditor_r1/S3_LV-MR-4 | n/a | n/a | n/a | y | invalid: exited 1 before artifacts |
| auditor_r1/S3_LV-MR-5 | n/a | n/a | n/a | y | invalid: exited 1 before artifacts |
| auditor_r1/S3_LV-MR-6 | n/a | n/a | n/a | y | invalid: exited 1 before artifacts |
| auditor_r1/S3_LV-MR-7 | n/a | n/a | n/a | y | invalid: exited 1 before artifacts |
| auditor_r1/S3_REPORT | n/a | n/a | n/a | y | invalid: exited 1 before artifacts |

Trap survival on the 24 replayable current-branch variants: **PASS** (minimum ratio 0.956; F12 identity 48→47 and alias precedence 45→43). The exact archived-variant replay remains unverified because those single-wrong-reading programs are unavailable or incompatible; this substitution is a deviation from the requested artifact set. The TS-13 compensation rule is not triggered by a measured loss; no variant with a valid before/after score fell below 90%. No separating hidden case was removed. Blind r1: **137/137 before and 137/137 after**, tests-only; the reflex 0.20 gate is excluded by this round.

## QC_RULINGS rows

- IN-16: module claims define “changed” only in prose; QC FAIL; REAL; AST-based grader and prose differed on text-only edits and nested helpers, settled neutrally in K19.
- TS-13: combined identity and archive assertions; QC MINOR; REAL; split by rule with weight retained, then recheck TS-25 and trap loss.

## Lessons for the master

- Preserve executable wrong-reading deliverables for later P12 rounds; the r3 summary alone cannot be replayed against the current verifier.
