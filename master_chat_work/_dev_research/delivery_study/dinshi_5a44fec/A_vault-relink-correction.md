# A vault-relink-correction (Step 1)

**Verdict: ARTEFACT** (grading contradiction, not a run crash). Genuine test points lost: 0 proven; 13 of 89 lost to one figure whose expected value contradicts the literal stated rule.

## Run health
- exception_info null; no negative fired; ctrf messages empty (s1.py scan).
- Agent 21:45:41-22:00:26 UTC (15 min, 44 steps).
- `tool_materializes_unseen_tree` and `tool_accepts_three_directories` PASSED, so the program ran under the privilege drop on the hidden seed (no permission artefact). `_guarded` setpriv (tests/test_output.py:18747), `_open_wide` chmod (:18753), `_invoke` (:18777).
- Score note: verifier stdout says reward 0.6598; result.json 0.907; score.json final 62.7. Recorded score.json used. QC re-grade: test channel unchanged 76/89 = 85.39% (QC report :147).

## Failed checks (13 of 89 positive)
| check | w | kind |
|---|---|---|
| integrity_report_matches | 3 | wrong value on ONE field, `orphan_prior_entries` |
| tool_rebuilds_unseen_corpus | 5 | whole 25-artifact equality on hidden seed 48271093 (:19002); INFERRED same field |
| tool_rebuilds_second_corpus | 5 | same on seed 90210477 (:19040); INFERRED same field |

All other 16 shipped artifacts passed byte equality, including drift_ledger, prior_run_diff and run_summary.

## Root cause (evidence)
- Rule as written: prior_run_notes.md:60-62 "`orphan_prior_entries` counts the lines of `prior_manifest.jsonl` whose `rel_path` appears nowhere in the `prior_path` column of `prior_placement.tsv`." And :21-22 "One row per object the prior run released. The reference is unique in the file."
- Shipped data contradicts :22: prior_placement.tsv carries 40 refs twice (e.g. lines 162-163 `AL-000219`), my count from a read-only script: `dup refs 40`.
- Test's reference: `self.was = {object_ref: prior_path ...}` (tests/test_output.py:18144-18147), so a duplicated ref keeps only its LAST path; orphans = manifest lines whose rel_path is not in `set(self.was.values())` (:18615-18616). The oracle does the same (solution/solve.py:159-161, 797-798).
- My read-only recompute of both readings on shipped data: full column 214, last-wins dict values 254. The agent shipped 214 (artifacts integrity_report.json). Expected 254 (derived from the test's code above; not executed).
- Generator cause: `build_prior` (tests/test_output.py:17975-18021) writes one row for each keeper AND one `withdrawn-folio` row for each ref in `orphaned`; `_hidden_corpus` (:18733-18734) builds `orphaned` from `draft.dropped | draft.echoes`, and a ref can be dropped in one vendor copy and kept in another. INFERRED: every hidden corpus also carries duplicate refs, so both whole-corpus checks fail on this field.

## Agent did reach the oracle value, then left it on purpose
- Step 23 (21:53:59) program output had `"orphan_prior_entries": 254`.
- Steps 26-31 (21:54-21:57) it found the duplicates ("40 / identical prior_path among dups: 0"), computed both readings ("orphans using full column: 214 / orphans using last-wins dict values: 254", step 27).
- Step 34 output has 214. Final message step 43: "`prior_placement.tsv` claims one row per reference but actually carries 40 references twice ... the last row in the file wins for the reference->path map - while `orphan_prior_entries` uses the full `prior_path` column as the prose specifies."
- So the agent followed the literal sentence; the test grades a reading the sentence does not state, produced by a generator that breaks the uniqueness promise. Not a lever: a doc/data contradiction (our "never used" list, LEVER_RULES line 24: answer key contradicting contract).

## QC
QC report :88 discusses CL-4 cascade (worst case 20 of 89), :108 CL-10 every fact traced; nobody flagged the duplicate refs or the :22 uniqueness claim. Passed QC with this defect.
