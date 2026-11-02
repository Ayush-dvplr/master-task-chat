# P12 r3 recheck and fix: dispatch-plan-reoptimization (27b6cc2)

Live QC kit HEAD `71a653b23fc2a6bc7ff3d4a8c286ec9a1b6a298e`, matching the v3 report kit. Both approved fingerprints matched. Session rename listed a Codex session but said `opencode: no match`; no alternate ID was tried. The report's 15 fails and 2 warnings are rechecked below. Rule IDs and wording did not change since the report.

`T` = `tests/test_output.py`, `I` = `instruction.md`, `H` = `environment/data/handbook_ops_v9.md`, `J` = `tests/judge.toml`. Line references in this first table are before edits. Every lever effect lists LV-DPR-01/02/03/04 in that order.

## Phase 1 findings

| ID and v3 finding quote | Label | Live rule quote | Bundle evidence quote and defence/ruling | Decision, playbook row, lever effect, compensation | Files |
|---|---|---|---|---|---|
| DS-22a: “Verification claim ... removes the judge key is false” | REAL | `02_Data_Solution_QC.md:78` DS-22: “TRUTH.md describes the bundle that actually shipped.” | `TRUTH.md:188-190` says “OPENAI_API_KEY removed”; `T:16826,16844` says `env=None`, `env=env`. QC_DEFENCE strict JSON entry and r1 W8 show the intended defence, but generator did not carry it. | FIX with TS-24; row TS-24; none/none/none/none; none. | generator T, TRUTH |
| DS-22b: “JSON comparison distinguishes boolean and number types is false” | REAL | `02_Data_Solution_QC.md:78` DS-22 as above. | `TRUTH.md:191` says “1, 1.0 and true differ”; `T:16886-16904` uses parsed `==`. QC_DEFENCE strict JSON entry describes the lost r1 fix. | FIX with TS-17; row TS-17; harder/harder/harder/harder; none. | generator T, TRUTH |
| TS-16: “Anti-cheat negatives can punish honest comments and miss forbidden imports or calls” | REAL | `03_Tests_QC.md:47` TS-16: “Anti-cheat negatives must fire on the cheat and ONLY on the cheat.” | `T:16971-16976,17148-17179` searches raw text; `T:16957-16964` finite deny list. QC_DEFENCE negative-probe entry defends the stated process rule, not the source substring or missed runtime calls. Dispatch v1 TS-16 ruling rejected honest-trippable negatives. | FIX with AST and runtime audit; row TS-16; none/none/none/none; none. | generator T |
| TS-17: “Hidden JSON comparison pays for numeric stand-ins where booleans are required” | REAL | `03_Tests_QC.md:48` TS-17: “Watch the Python trap where True == 1.” | `H:296-299` says keys “hold a JSON boolean”; `T:16886-16904` uses parsed equality. QC_DEFENCE strict JSON entry promises exact types. | FIX recursive type equality; row TS-17; harder/harder/harder/harder; none. | generator T |
| TS-19: “test and judged channels omit promised serialization, shipped-set artifact values, continuous file-access scope and outside-hint constraints” | REAL | `03_Tests_QC.md:50` TS-19: “every promise made to the agent must be graded by something.” | `H:225-231` gives byte features; `T:16886-16904` discards them; `T:17002-17004` checks paths; `T:17182-17207` snapshots writes only; `I:3,15` states runtime and hint rules. QC_DEFENCE shipped-only entry argues low weight, but does not establish value coverage. Dispatch v2 TS-19 ruling warned on shipped existence only. | FIX through COV-1..6; row TS-19; harder/harder/harder/harder; none. | generator T, J |
| TS-24: “Submitted solver code inherits the verifier credential” | REAL | `03_Tests_QC.md:68-72` TS-24 requires isolation of every executed agent subprocess. | `task.toml:27-28` provides `OPENAI_API_KEY`; `T:16826,16844,17198` inherits/copies it. QC_DEFENCE staged-copy entry covers file modes, not environment. | FIX one scrubber for every run; row TS-24; none/none/none/none; none. | generator T |
| AL-2: “full instruction-to-grader crosswalk leaves ... unchecked” | REAL | `05_Alignment_Integrity_QC.md:22` AL-2: “Everything promised is graded.” | `I:3,15`, `H:225-231`, `T:16886-17207`, `J:11-126` show the gaps. QC_DEFENCE shipped-only rationale does not cover remaining 16 shipped values. | FIX through COV rows; row AL-2; none/none/none/none; none. | generator T, J |
| AL-18: “Verification section has stale claims” | REAL | `05_Alignment_Integrity_QC.md:64` AL-18: “No stale references: nothing mentions files, paths, counts, or numbers that do not match the actual bundle.” | `TRUTH.md:188-192` claims scrub and type distinction; `T:16826,16844,16886-16904` lacks both. | FIX last, after code; row AL-18; none/none/none/none; none. | TRUTH |
| AL-19: “verifier gives agent-authored solver code the judge credential” | REAL | `05_Alignment_Integrity_QC.md:54` AL-19: “No credential or secret exfiltration.” | `task.toml:27-28` injects placeholder and `T:16844,17198` passes inherited environment. | FIX with TS-24; row TS-24; none/none/none/none; none. | generator T |
| COV-1: “No check reads the byte features required” | REAL | `03_Tests_QC.md:50` TS-19 and `05_Alignment_Integrity_QC.md:22` AL-2 promise coverage. | `H:225-231` specifies sorted, one-space JSON and compact JSONL, CSV terminal newline, LF, UTF-8; `T:16886-16904` parses away all of them. QC_DEFENCE chain remains valid; byte checks strengthen it. | FIX hidden-group byte equality because oracle emits stated format; row TS-19; harder/harder/harder/harder; none. | generator T |
| COV-2: “program must read only from the input directory ... ungraded” | REAL | `05_Alignment_Integrity_QC.md:22` AL-2 as above. | `I:3` states input-only reads; `T:17182-17207` only snapshots writes. | FIX runtime audit read events; row TS-16; none/none/none/none; none. | generator T |
| COV-3: “standard-library/network/process enforcement ... partial” | REAL | `03_Tests_QC.md:47` TS-16 as above. | `I:3` states all three rules; `T:16957-16964,17157-17164` uses incomplete static deny lists; `tests/Dockerfile:3` installs litellm. | FIX runtime audit for imports, sockets and child processes; row TS-16; none/none/none/none; none. | generator T |
| COV-4: “online ... hints ... no work-phase observer” | REAL | `04_Judge_QC.md:92` JD-15 classifies stated constraints; `:93` JD-16 requires `instruction following` for a stated constraint. | `I:15` says “Do not cheat by using online solutions or hints specific to this task”; `J:11-126` has no such trajectory criterion. | FIX task-specific lookup negative -3; row JD-15/JD-16; none/none/none/none; none. | J |
| COV-5: “shipped export set's artifact values can be wrong while paths ... right” | REAL | `05_Alignment_Integrity_QC.md:22` AL-2 as above. | `I:3` requests shipped artifacts; `T:17002-17004` checks existence only; `J:11-75` reads only five final-reply figures, so p12 r2 F7's FALSE_POSITIVE label was wrong. QC_DEFENCE shipped-only entry must be updated. | FIX all 21 against shipped gold under same comparison, weight 1; row AL-2; none/none/none/none; none. | generator T |
| COV-6: “output-directory write restriction ... checked only after execution” | REAL | `05_Alignment_Integrity_QC.md:22` AL-2 and `:28` AL-28 one act one penalty. | `I:3` says “write only inside the output directory”; `T:17182-17207` pre/post snapshot misses create/delete. QC_DEFENCE AL-28 entry limits the test to scratch; retain that partition against judge R8. | FIX runtime write events, excluding input mutation owned by R8; row TS-16; none/none/none/none; none. | generator T |
| X1 warn: “scanner skipped five binary source files” | FALSE_POSITIVE | `structure_qc.py` X1 scanner warns when binary text is skipped; it is not a bundle fail. | v3 `:43` says direct extraction found no prohibited dash. | KEEP, no playbook row; none/none/none/none; none. | none |
| EXEC-5 warn: “three oracle scores ... kit's five-run sign-off ... requires five” | REAL process gap | `Final_checklist.md:514` says oracle “FIVE times: all five exactly 1.000”. | v3 `:44` records three authorized runs. | KEEP under Ayush x3-per-round rule; final x5 belongs before sign-off; no playbook row; none/none/none/none; none. | none |

## Crosswalk after fixes

| Contract sentence | Observer |
|---|---|
| `I:3` reusable outputs and shipped artifacts | 28 hidden groups; `all_artifacts_exist` validates all 21 shipped values |
| `H:225-231` serialization | byte comparison on each hidden and shipped artifact |
| `I:3` only input reads | `negative_reads_outside_input_dir` runtime audit |
| `I:3` only output writes | `negative_writes_outside_output_dir` runtime audit; R8 owns actual `/app/data` edits |
| `I:3` stdlib, no network, no child programs | `negative_network_dependency_or_shell_cheat` runtime audit |
| `I:15` no task-specific online hints | R10 trajectory criterion |

## Deviations from master directions

The handbook specifies indentation, sorted keys, line endings, compact JSONL and CSV terminal newlines, but leaves numeric literal spelling and equivalent string escapes open. Following the allowed alternative in the master direction, the tests compare values recursively and check each stated format feature explicitly. Byte equality would reject valid encodings the contract leaves open. The generator's old SQLite version-header drift was corrected before changing the bundle, and the regenerated tests matched the original bytes.

## Probe results

| Probe | Result |
|---|---|
| Environment printer under ordinary `_run_solver` | `OPENAI_API_KEY` absent; all names containing KEY/TOKEN/SECRET/PASSWORD absent; PATH, LANG and caller TMPDIR present. The scope run uses the same scrubber. |
| Recursive JSON | `true` vs `1` false; `1` vs `1.0` false; dict key order free true. |
| Comment and print string with shipped total | no hardcode penalty. |
| Outside input read | one `negative_reads_outside_input_dir` criterion hit. |
| Transient write then delete outside output | one `negative_writes_outside_output_dir` criterion hit. |
| Loaded non-stdlib module | one `negative_network_dependency_or_shell_cheat` criterion hit. |
| `asyncio.create_subprocess_exec` | one network/process criterion hit despite multiple low-level audit events. |
| Socket open | one network/process criterion hit. |
| Unsorted JSON keys | A solver that reverses only `objective.json` keys scores 80/101: `hidden_h1_totals` through `hidden_h4_totals` and the shipped `all_artifacts_exist` fail; all other positive groups pass. |
| Oracle audit, shipped + H1-H4 | zero events on all five runs. |

The exact event lists and criterion hits are in `WORK/trap/probe_results.json`. The oracle's shipped and hidden outputs were graded by the local rewardkit stub; all seven programs exited cleanly. The host is macOS Python 3.9, so the local oracle variant omits `Path.write_text(newline=...)` with identical LF output. The real image is Python 3.12; its `setpriv` preflight ran the embedded oracle solver as `nobody`, produced 21 artifacts and zero audit events.

## Gates before the Harbor chain

- Four live QC scripts: structure 17 pass / X1 1 warn / 0 fail; instruction 5/0/0; tests 35 pass / A3 1 warn (36 checks) / 0 fail; judge 19/0/0. The first judge pass found R10's quoted `not` token; the criterion now keeps the exact instruction quote in a TOML comment and uses positive negative-criterion grammar in its description. Recheck: 0 FAIL.
- `xref_check.py`: 24 entries, 0 findings. All four `_OVERLAY_H*` payload hashes are byte-identical before/after, so every separating hidden case remains.
- `stacking_check.py`: 36 tests, 10 judge criteria, positive tests 101, negative tests 25, positive judge 21, absolute negative judge 11. Its raw AL-28 UNMATCHED grouping and TS-26 candidates are classification hints; the per-act and per-corpus review in `STACKING_CHECK.md` resolves both. `STACKING PASS`.
- Caps: 36 tests <= 70; 10 judge criteria <= 70; judge absolute negative 11 <= positive 21. The 36-check A3 warning is below the hard cap.
- Local tests-only scores: oracle before/after 1.000/1.000; agent_v0 0.1683 to 0.1584; nop remains 0 by absence of any required output (Docker run pending).

## Trap survival

| Wrong reading | Before loss of positive P | After loss of positive P | Ratio | Separating cases kept | Verdict |
|---|---:|---:|---:|---|---|
| LV-DPR-01 backward lot tie (m_tie) | 69/101 | 70/101 | 1.014 | yes | PASS |
| LV-DPR-02 control fallback (m_fallback) | 69/101 | 70/101 | 1.014 | yes | PASS |
| LV-DPR-03 first seen amendment (m_amend) | 69/101 | 69/101 | 1.000 | yes | PASS |
| LV-DPR-04 raw rejection code (m_rejnorm) | 32/101 | 33/101 | 1.031 | yes | PASS |
| LV-DPR-04 own void only (m_voidlog) | 12/101 | 13/101 | 1.083 | yes | PASS |

The five variant sources in `WORK/trap/variants/` each change one oracle reading. These are fresh author-side constructions, so their before scores differ from the historical harden r1 figures for fallback and amendment; the before and after scores above use the same variant programs. Every after loss is at least 100% of its before loss. The reflex remains <= 0.20 and did not rise. Trap survival: PASS.

## QC_RULINGS rows

| Rule | Our design | v3 QC verdict | Our label | Reason for master ruling |
|---|---|---|---|---|
| TS-16 | source substrings and finite runtime deny list | FAIL | REAL | comments could trip; non-stdlib/runtime paths escaped; fixed with AST constants and audit hook |
| TS-17 | parsed Python equality | FAIL | REAL | bool/int/float substitution; fixed recursive exact types |
| TS-19 | parsed values, shipped paths, snapshots | FAIL | REAL | stated format, shipped values and continuous scope ungraded; fixed with explicit features, goldens and audit |
| TS-24 | `Popen(env=None)` | FAIL | REAL | verifier credential inherited; every run now uses scrubbed environment |
| AL-2 | several instruction promises lacked observers | FAIL | REAL | crosswalk above now names a check or criterion for each sentence |
| AL-19 | solver inherited verifier key | FAIL | REAL | scrubbed before child process starts |
| COV-1 | format ignored | FAIL | REAL | stated byte features now checked while unspecified numeric spelling remains free |
| COV-2 | read scope absent | FAIL | REAL | audit records outside reads |
| COV-3 | finite import/process scan | FAIL | REAL | successful non-stdlib imports, sockets and process starts audited |
| COV-4 | no task-specific lookup criterion | FAIL | REAL | R10 now judges the task-specific online lookup, ordinary model traffic allowed |
| COV-5 | 21 paths only | FAIL | REAL | all 21 shipped values now compared at existing weight 1; r2's false-positive label was wrong |
| COV-6 | before/after write snapshot | FAIL | REAL | audit observes transient writes; R8 alone owns input mutation |

## Docker verifier gate

The live kit's `exe_copy.py` made plain and `--owner-only` tests-only copies. Its schema load passed, it removed judge.toml from each copy, set test weight to `1/101`, and adjusted only the copies' network modes. The verifier and environment images were warmed from the copy. In the real Python 3.12 verifier image, the audit wrapper ran the embedded oracle through `setpriv` as `nobody`: clean exit, 21 artifacts, zero audit events.

One serial nohup Harbor chain finished with `ALL_DONE` at `/tmp/opencode-logs/dpr-p12r3-20261023T163200-e93c/runs.log`. Tests-only rewards from its five `result.json` files: oracle 1 = 1.000, oracle 2 = 1.000, oracle 3 = 1.000, owner-only oracle = 1.000, nop = 0.000; zero errored trials in each. Harbor version 0.24.0. The kit's separate five-oracle sign-off remains the EXEC-5 process warning under Ayush's x3-per-round instruction.

Final fixed finding count: 15 of 15 fails. REAL 16 including EXEC-5's uncompleted process gate; FALSE_POSITIVE 1 (X1 warning); UNSURE 0; kept warnings 2; paused IDs none. The only newly generated script warning is A3 for 36 tests, below the 70-test cap.

## Lessons for the master

P12 r1 patched credential stripping and strict JSON comparison directly in the generated bundle test file. P12 r2 regenerated that file from stale `WORK/build/mktests.py`, overwriting both fixes while leaving TRUTH.md's claims; require a generator diff before every rebuild.
