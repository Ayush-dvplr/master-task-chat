# Recheck and fix: sensor-network-lsq-correlated-adjustment

Board 6a3cd4a. `name_session.py` returned one Codex match and `opencode: no match`; no other ID was tried. Live kit HEAD `71a653b23fc2a6bc7ff3d4a8c286ec9a1b6a298e`; both reconciled fingerprints matched their listed files. The live kit is authoritative and has the same ID/wording for these findings as QC v1. The QC v1 copy and editable bundle were reported byte-identical. All scores below are tests-only.

## Findings

| ID | Label | Live rule quote | Bundle evidence and QC finding quote | Decision and playbook row | Lever effect; compensation | Files changed |
|---|---|---|---|---|---|---|
| JD-15 ❌ | REAL | `04_Judge_QC.md:50`: “A constraint criterion (JD-16) carries `type = "instruction following"`”; `:92` says a mismatched label is a defect. | QC v1:36: “constraint criterion R8 carries the wrong kind label.” `instruction.md:3` says “read only from `DATA_DIR` and write only to `OUT_DIR`”; `tests/judge.toml:111` has `type = "safety and boundaries"`. | FIX category label, row JD-15/JD-16. | All levers none; none. | `tests/judge.toml` |
| AL-27 ❌ | REAL | `05_Alignment_Integrity_QC.md:27`: “a rule only counts as graded when the test's input actually constructs the situation where the rule matters.” | QC v1:38: “a stated precedence rule has no fixture that triggers it.” `schema.md:222-223` says first map occurrence wins; `test_output.py:1851,1867` appends the same value on every repeat. | FIX hidden map generators only, row AL-27. | V0-11 harder; all others none; none. | `tests/test_output.py` |
| DS-6 🟡 | REAL minor | `02_Data_Solution_QC.md:22`: “Data files must make sense for the task story.” | QC v1:42: the table claims an “EXACT two-sided acceptance interval” with non-monotone centres. `chi_square_bounds_table.csv:1-5` contains that header and per-row centres; `TRUTH.md:48` says “centres are per row, not a formula.” | KEEP, row DS-6. Rewording or regenerating would reveal the V0-9/10 acceptance-row lever; `schema.md:182-185` already directs the table lookup. | All none; none. | None |
| DS-22 🟡 | REAL | `02_Data_Solution_QC.md:78`: “TRUTH.md describes the bundle that actually shipped.” | QC v1:44: “`fix_patch_sha256` names a patch that does not exist.” `TRUTH.md:5` says no broken program; `:161` has that digest. | FIX remove stale digest, row DS-22. | All none; none. | `solution/TRUTH.md` |
| TS-13 🟡 | REAL | `03_Tests_QC.md:44`: “One property per test.” `:52` requires positive checks to grade earned work. | QC v1:46: “checks bundle unrelated properties”; `test_output.py:2558-2579` combines set flags and final weights, and `:2613-2651` combines summaries and normal trace. | KEEP as a minor, row TS-13. The allowed-weight split weakened H4 separation: `observation_sets` passed for no_centring, centring_angles and ignore_mount in at least one hidden extract. Reverted the split. | All levers none after reversion; no compensation needed. | None in final bundle for TS-13 |
| JD-5 🟡 | REAL | `04_Judge_QC.md:71`: “Each criterion names ONE observable behaviour.” `:75` requires oracle truth (JD-7). | QC v1:48: “R5 ... packs five separately checkable observables”; `judge.toml:66` lists names, errors, dead code, debug prints and bare except. A malformed east JSONL currently exits with JSONDecodeError but no source filename. | FIX one named error behaviour and make oracle satisfy it, row JD-18 and JD-7. | All none; none. | `tests/judge.toml`, `solution/solve.py`, `solution/TRUTH.md` |
| X1 ⚠️ | REAL warning, no bundle defect | `02_Data_Solution_QC.md:23`: “No em/en dashes in text data files (script-checked bundle-wide; re-verify any file the script skipped as binary if it is actually text).” | QC v1:52: “5 binary files skipped by the dash sweep”; current `structure_qc.py` prints `WARN [X1] 5 file(s) skipped as binary` and 0 fail. QC v1:98 records the binary content scan found no dashes. | KEEP script warning, row none; all five are genuine binary containers. | All none; none. | None |

## Deviations from master directions

R5's proposed wording is not met by the pre-fix oracle on an unparsable JSONL declaration. I will add a named input-error path to `solve.py` and recompute the TRUTH digest. The proposed words “instead of” are banned by live JD-2, so R5 will stop after “naming that file.” The live kit `04_Judge_QC.md:46,112` permits exactly four annotations keys and rejects `contract_sentence`; therefore I quote `instruction.md:3` here, and relabel R8 without adding an annotation key. Live `tests_qc.py` W2 allows only weights 1, 3 and 5, so the requested 2+1 split fails. I tried an allowed 1+3+1+1 redistribution across the two pairs, retaining P=62. Trap replay showed the new observation-set half passed for three single-chain variants, contrary to the requested H4 proof. I reverted the split, kept TS-13 as a minor, and retained the original 18 chain checks and weights. The intermediate Docker chain on the discarded split copy was stopped before ALL_DONE; the final Docker block uses fresh copies.

## Gate results

- Final QC scripts: structure 17 pass, 1 X1 warning, 0 fail; instruction 5/0/0; tests 37/0/0; judge 19/0/0. Logs sit beside this report.
- Manual JD-7: malformed east JSONL and missing reference-unit CSV each exit 1 and name the affected file. R5 has one named behaviour and avoids JD-2's banned “instead of” phrasing. R8 has the instruction-following category; the contract sentence is `instruction.md:3`.
- AL-27: each of challenge, eval and audit has conflicting later restatements for stations ALPHA and FICUS and epochs 1 and 2. The first rows remain authoritative; shipped data was not edited.
- TS-13 attempted split: TS-25 halves compared earned artifact values; live W2 rejected 2-point weights. An allowed redistribution retained P=62 but passed an observation-set half for no_centring, centring_angles and ignore_mount, so it was reverted. The original TS-13 minor remains. Positive total P=62, test reward weight `0.008064516129032258` unchanged.
- `xref_check.py`: 15 entries, 0 findings. `solve.py`: 548 lines, SHA256 `19e506cd7f6d43ca4bc6f2b4826c4402c2466184df8b1581dc814a8d67f054c0`, matching TRUTH.md; `fix_patch_sha256` removed.
- `stacking_check.py` ran. Its static AL-28 grouping puts distinct R6 final-message and R8 file-open acts together; its G3 heuristic classifies hidden output checks by their names. Reviewing the bodies gives 54/62 whole hidden documents, 7/62 isolated, 1/62 shipped; each negative act costs at most 5. `STACKING_CHECK.md`: PASS with TS-13 minor retained.
- Final Docker block: verifier and environment images warmed, then fresh live-kit `exe_copy.py` plain and owner-only copies. The one final chain reached `ALL_DONE`: oracle x3 = 1.000, 1.000, 1.000; owner-only = 1.000; nop = 0.000; all trial error counts 0. Logs: `/tmp/opencode-logs/sensor-network-lsq-correlated-adjustment-p12-final-20261023T161914-183e/`. The discarded split copy's intermediate chain was stopped before ALL_DONE.


## Trap survival

Positive total P=62. Loss is 62 minus earned positive points. All variants are single wrong-reading copies of the pre-fix oracle; the v0 reflex is the supplied trajectory program. Final tests restore the original compound checks.

| Reading | Before loss of P | After loss of P | Ratio | Separating cases kept | Verdict |
|---|---:|---:|---:|---|---|
| no_centring (H1) | 54 | 54 | 1.000 | y | PASS |
| no_reduce (H2) | 54 | 54 | 1.000 | y | PASS |
| centring_angles (H1) | 54 | 54 | 1.000 | y | PASS |
| ignore_mount (H1) | 54 | 54 | 1.000 | y | PASS |
| first_seen (H3) | 57 | 57 | 1.000 | y | PASS |
| last_occurrence (V0-11) | 0 | 10 | new separation | y, in all three hidden maps | PASS |
| v0 reflex | 62 | 62 | 1.000 | y | PASS |

Reflex before 0/62 = 0.000; after 0/62 = 0.000, tests-only. The last-occurrence variant loses all three hidden rollup checks (9 points) plus one canonical check; the rollup loss alone clears the new >=5 gate. The transient split yielded observation-set passes for single-chain variants, which is why TS-13 was kept. Final trap survival: PASS.


## QC_RULINGS rows

- TS-13: sensor v1, summary/trace and set/weights in one check, MINOR, REAL; kept the minor because a legal split softened a chain check; the original weighted checks remain.
- JD-15: sensor v1, R8 scope constraint labelled safety, FAIL, REAL; relabel instruction following and cite instruction.md:3.
- JD-7: sensor v1 did not flag R5 oracle mismatch; this recheck found malformed JSONL errors lacked a filename. Fix oracle to satisfy the tightened named-shape criterion.

## Lessons for the master

- The proposed R5 replacement needs an oracle malformed-input probe before it is issued as a standalone judge edit.
- A 2+1 TS-13 split conflicts with the live W2 weight set; preflight proposed weights against the script.
- Preserve the explicit H4 per-half separation condition when reviewing a split; a 90% aggregate loss alone did not detect the weaker half.
