# JUDGE_REWORK, dispatch-plan-reoptimization (board cc4bb7f, P12 judge r1)

Date 23 Oct 2026. Harness HEAD `71a653b23fc2a6bc7ff3d4a8c286ec9a1b6a298e` (matches fingerprint; QC kit 12/12, GEN 160/160 files match). Session rename: `opencode: ['ses_e96987bf3ffeJYcs4MmrPDKKlK']` (listed). No Docker.

## 1. Oracle figures (shipped set, produced in this round)

Command (B = bundle):
```
T=$TMPDIR/dpr_oracle; mkdir -p $T; ln -s "$B/environment/data" $T/data
cd $T && APP_ROOT=$T python3 "$B/solution/solve.py"      # rc=0, writes $T/out/ (21 artifacts + solver.py)
```
Output read from `$T/out`:
- `data_quality.json` totals: `{"out_of_scope_rows": 1835, "rejected_rows": 1002, "sources_seen": 55, "void_rows": 1622}`
- `rejected_records.csv`: 1003 lines = 1002 rows; reasons `retired_item` 151, `sentinel` 797, `unknown_item` 54.
- retired_item rows joined to their source row's effective_seq (helper script over `environment/data`, cutoff `plan_sequence_cutoff: 8140` from `runbook_params.yaml:3`): `retired_item rows 151 {dmd_block_a2.tsv: 59, dmd_block_c1.ndjson: 53, mesh_dump_01.ndjson: 24, mesh_dump_02.txt: 15}`, `above cutoff 28 {dmd_block_a2.tsv: 6, dmd_block_c1.ndjson: 6, mesh_dump_01.ndjson: 10, mesh_dump_02.txt: 6}`, items `{K07: 81, K19: 70}`.
- `reconciliation.txt` line 9 `rejected_rows=1002`; `audit_summary.md` line 11 `- rejected_rows: 1002`.

## 2. Agent (a2) vs oracle

`cmp` over the 21 artifacts: 17 byte identical; 4 differ.

| File | Oracle | a2 |
|---|---|---|
| data_quality.json | rejected_rows 1002, out_of_scope_rows 1835 | 974, 1863 (void 1622 and sources 55 equal) |
| rejected_records.csv | 1002 rows, retired_item 151 | 974 rows, retired_item 123 (0 above cutoff) |
| reconciliation.txt | `rejected_rows=1002` | `rejected_rows=974` |
| audit_summary.md | `- rejected_rows: 1002` | `- rejected_rows: 974` |

The 28 missing rows are exactly the retired_item rows above the cutoff (e.g. `dmd_block_a2.tsv,U000356,K07:P01,retired_item`; source row `dmd_block_a2.tsv:201` has effective_seq 8422). Cause: a2 `solver.py` `sweep()` (line 1280) runs `if self.above_cutoff(rec): self.out_of_scope_rows += 1; continue` (lines 1290-1293) before the unknown_item / retired_item / sentinel checks (1296-1301). Oracle `audit_pass` (generated solver.py 461-500) rejects first, then tests the cutoff. Rule: `handbook_ops_v9.md:330-336` ("The first reason in that order is reported. `totals.rejected_rows` is the row count of the rejection artifact. `totals.out_of_scope_rows` counts sweep rows that survive rejection, carry an `effective_seq`, and sit above the cutoff.") and `:80-81` (retired item: "its demand rows are rejected with reason `retired_item`").

## 3. Criteria before and after

Instruction sentence for the new rows (`instruction.md:1`): "publish the corrected plan with its audit artifacts. The operating contract, the register schemas and the shape of every artifact are written out inside the export set."

| id | text (short) | w before | w after | target | type / importance after | contract |
|---|---|---|---|---|---|---|
| R1 | reply states objective 446527364 cents | 5 | 5 | trajectory | task completion / critically_important | instruction.md:13 reply request |
| R2 | reply states setup cost 19229000 | 3 | **1** | trajectory | task completion / important | instruction.md:13 reply request |
| R3 | reply states holding cost 31756967 | 3 | **1** | trajectory | task completion / important | instruction.md:13 reply request |
| R4 | reply states 75 production lots | 3 | **1** | trajectory | task completion / important | instruction.md:13 reply request |
| R5 | reply states 33012 units uncovered | 3 | **1** | trajectory | task completion / important | instruction.md:13 reply request |
| R6 | solver.py integer cents | 1 | 1 | state_change | agent behavior / important | instruction.md:9, handbook_ops_v9.md:70 |
| R7 | reply contradicts own artifacts | -5 | -5 | trajectory | factuality / critically_important | conduct |
| R8 | touches /app/data | -3 | -3 | state_change | instruction following / important | instruction.md:3 |
| R9 | solver.py code quality | 3 | 3 | state_change | agent behavior / important | conduct (JD-18) |
| R10 | task-specific online lookup | -3 | -3 | trajectory | instruction following / important | instruction.md:15 |
| **R11** | "The agent delivers a solver.py whose accounting sweep counts a row as out of scope only after that row has passed the unknown_item, retired_item and sentinel rejection checks." | n/a | **5** | state_change | task completion / critically_important | instruction.md:1; handbook_ops_v9.md:330-336, :80-81 |
| **R12** | "The agent delivers a solver.py that writes the rejected_rows figure of data_quality.json, reconciliation.txt and audit_summary.md from the same list of rows it writes to rejected_records.csv." | n/a | **3** | state_change | task completion / important | instruction.md:1; handbook_ops_v9.md:334, :357-360, :362-364 |

Importance for weight 1 is `important` (04_Judge_QC JD-13: important pairs with 1 or 3). Each new criterion carries `#` comments naming the instruction sentence and handbook lines.

Why behaviour form, not figure form (master direction 4): `all_artifacts_exist` compares all 21 shipped artifacts (including data_quality.json, rejected_records.csv, reconciliation.txt, audit_summary.md) with goldens, and `hidden_hN_quality` / `hidden_hN_totals` read the same figures on H1..H4. 04_Judge_QC JD-8: "answer == 42 | The response states the correct calibration value | FAIL"; "decoder handles the delta case | The agent derives the delta rule from the data rather than guessing | OK". LEVER_RULES J1 also bans "states figure X" criteria for new work. R11 grades the order of checks in code, R12 the source of the count: neither names a figure, and they grade different observables (JD-14).

## 4. Phase A paper scores

Evidence for a2 comes from `judge_response.txt`, the final reply (last step of `agent/trajectory.json`) and the final `artifacts/app/out/solver.py`.

| id | w | a2 old | a2 new | reference new | evidence |
|---|---|---|---|---|---|
| R1 | 5 | 5 | 5 | 5 | reply "Corrected total objective: **446 527 364 cents**" |
| R2 | 3 to 1 | 3 | 1 | 1 | "Total setup cost: **19 229 000 cents**" |
| R3 | 3 to 1 | 3 | 1 | 1 | "Total holding cost: **31 756 967 cents**" |
| R4 | 3 to 1 | 3 | 1 | 1 | "Production lots opened: **75**" |
| R5 | 3 to 1 | 3 | 1 | 1 | "Demand units left uncovered: **33 012**" |
| R6 | 1 | 1 | 1 | 1 | judge_response R6 score 1 |
| R7 | -5 | 0 | 0 | 0 | judge_response R7 0; steps 37/40 print 974 and the reply makes no rejected-row claim |
| R8 | -3 | 0 | 0 | 0 | reply "`/app/data` is untouched"; judge_response R8 0 |
| R9 | 3 | 0 | 0 | 0 | judge_response R9 0: "emit spans roughly 300 lines" (reference keeps a2 code quality) |
| R10 | -3 | 0 | 0 | 0 | judge_response R10 0 |
| R11 | 5 | n/a | **0** | 5 | a2 solver.py:1290 `if self.above_cutoff(rec):` then `continue` before the reason checks at 1296-1301; visible in step 28 `file_editor create /app/out/solver.py`. Reference: sweep fixed (oracle order) |
| R12 | 3 | n/a | 3 | 3 | a2 solver.py:1660 `'rejected_rows': len(plan.rejected)` and :1680 `('rejected_rows', len(plan.rejected))`, one `figures` list writes reconciliation and audit (1682-1689); `plan.rejected` is the list written to rejected_records.csv |
| total | | **18/21** | **13/21** | **18/21** | |

Old a2 reproduces 18/21 = 85.71 (report.json rubric 85.71). Overall = 0.5 x tests + 0.5 x rubric:
- a2 old: 0.5 x 67.33 + 0.5 x 85.71 = 76.52 (matches report.json).
- a2 new: rubric 13/21 = 61.90; overall 0.5 x 67.33 + 0.5 x 61.90 = **64.62** (below 70 by 5.38; rubric 61.90 is at most 66: target met).
- reference new: rubric 18/21 = 85.71; overall 0.5 x 100 + 0.5 x 85.71 = **92.86** (at least 85: target met).
- Oracle (JD-7): R11 PASS (`audit_pass` rejects first, cutoff after), R12 PASS (`len(rejects)` at :1346 and `len(sorted_rejects(S["ctx"]))` at :1367; `rejects = sorted_rejects(ctx)` is the list written to rejected_records.csv at :1351).

Skeptical judge check (Phase A4): both new criteria are state_change on solver.py. The a2 judge already read solver.py for R6 and R9 (its R9 reason quotes a function length), and the sweep code is printed in full inside the step 28 create call, so `gpt-5.6-sol` can see the cutoff test before the reason checks. A correct agent passes R11 by any code order that rejects first (a single loop or a second pass that drops rejected rows before counting), so the wording is not tied to one shape. R12 passes for any program that counts the rows it writes; a program that recounts independently in two places would fail, but the handbook line 334 defines the figure as the row count of the rejection artifact.

## 5. Caps (04_Judge_QC JD-12, JD-S13; LEVER_RULES caps)

12 criteria (min 8, WARN above 35, cap 70); 9 positive, 3 negative; positive total 21 (unchanged), absolute negative total 11 (11 <= 21); weights only in {1, 3, 5, -3, -5}. `tests/reward.toml` judge weight 0.023809523809523808 = 0.5/21 still holds, so reward.toml stays untouched.

## 6. QC scripts, xref, stacking

- `python3 judge_qc.py <BUNDLE>` (live kit): `SUMMARY: 19 pass, 0 warn, 0 fail` / `VERDICT: PASS` (G1 12 criteria, G6 positive total 21, negative total 11).
- `python3 structure_qc.py <BUNDLE>`: `SUMMARY: 17 pass, 1 warn, 0 fail`; the one WARN is X1 (5 binary data files skipped), present before this round.
- `xref_check.py <BUNDLE> <WORK>/XREF.md`: `xref_check: 32 entries, 0 findings` (new entries 1002, 1835, 151, 28, cutoff 8140, sweep rule, R11 and R12 names).
- `stacking_check.py <BUNDLE>`: tests 36, criteria 12; J1 hints R1 to R5 (reply figures kept for AL-2, now w1 except R1); J2 conduct criteria none; TS-26 7 candidate groups and AL-28 hint FAIL are the same test-side hints the p12_r3 STACKING_CHECK.md resolved (tests unchanged).

## 7. Files changed and tree hash

Hash method (in BUNDLE): `find . -type f | sort | while read f; do shasum -a 256 "$f"; done | shasum -a 256 | cut -c1-12`.
- Before: `e931391c733f` (66 files). After: `d2abee833b88`.
- `diff` of the per-file lists: only `./tests/judge.toml` changed (`c9639bc305bf...` to `da224e66db7a...`). The list without judge.toml hashes to `d3478315c912` before and after, so tests, goldens, data, solution and reward are byte identical: oracle, owner, nop, reflex and trap replay results from p12_r3 stand unchanged.
- WORK files updated: QC_DEFENCE.md (3 entries), XREF.md (8 entries), LEVERS.md (cc4bb7f table), TODO.md, LOG.md.

Not edited (scope lock): `solution/TRUTH.md:217-226` still says "Channel B holds ten judge criteria: five figures ... two code criteria ...". Suggested replacement for the master to authorise: "Channel B holds twelve judge criteria: five figures for the shipped export set that the final reply must state (corrected total `446527364` at weight 5; setup cost `19229000`, holding cost `31756967`, 75 production lots and `33012` uncovered units at weight 1 each), two sweep criteria (rejection checks run before the out of scope count, weight 5; the rejected row figure comes from the rows written to the rejection artifact, weight 3), two code criteria ...".

## Lessons for the master
- `solution/TRUTH.md:217` now says "ten judge criteria"; it needs the twelve-criterion wording above before the P11 rerun, or AL alignment may flag it (scope lock kept me out).
- Handbook §2 (`handbook_ops_v9.md:26-28`) says a row above the cutoff is "never counted as rejected", which the sweep paragraph (330-336) and §5 (80-81) override for retired items without saying so; a2 followed §2. QC may call the trap contract-ambiguous; a fix would sit in the generator's handbook text, not the judge.
- Behaviour-form judge criteria (code order, count source) let the judge pay for a trap that the tests also grade without re-reading the same figure (JD-8).
- Keeping the positive total at 21 avoided touching reward.toml (JD-S13); plan judge reworks around a fixed total.
