# Harden R0: sensor-network-lsq-correlated-adjustment

Board: 868afdf. Status: PAUSED, not approved to ship. The approved skdir_csv build and executable gates are complete, but the requested zero-FAIL validator gate is not satisfied. Five failures already existed before this round; master disposition is required before freeze or a new paid model attempt.

## Measurement and Primary Lever

Kind (a): value-preserving carrier variation inside the named RFC 4180 CSV standard. Some sigma_kind and dir cells are quoted in the hidden CSV shard; unquoted rows remain. TSV, PSV and JSONL serialization is unchanged. No shipped observation value or shard byte changed.

The literal sigma_kind-only CSV experiment lost 23/86 points (26.7%), below the 40% bar: challenge/eval CSV shards store variance, so that branch did not fail. The one approved redesign, skdir_csv, loses 69/86 positive points (80.2326%), exceeding both the 40% bar and 35/86 minimum. The paid program silently returns WRONG documents with exit 0 on all three hidden extracts, not a crash or timeout.

Reference parsed values and complete oracle output trees are byte-identical before/after quoting on challenge, eval and audit. Old/new verifier-reference digests also match on the shipped extract. Reference maximum across the measurement runs: 2.54 seconds, below the 30-second bar and stated 120 seconds. Final-build reference range: 1.29-2.06 seconds. The generator shape assertion passes 300/300 distinct seeds (65.4 seconds in Docker).

| Q1 component | Location |
|---|---|
| Public governing rule | environment/data/schema.md:38, mirrored in tests/test_output.py:3405 |
| Rule text | The CSV shard is written to RFC 4180, so any of its fields may be enclosed in double quotes; the quotes are not part of the value. |
| Serialization | tests/test_output.py:606 and :610, _rfc4180_quoted / write_csv |
| Shape assertion | tests/test_output.py:645, _assert_csv_quote_shape |
| Hidden flags | tests/test_output.py:1024, :1055, :1079 |
| Independent RNG | tests/test_output.py:1235, Rng(CFG["seed"] ^ 24) |
| Oracle branches | solution/solve.py:80 csv.DictReader; :250 dir; :262 sigma_kind |
| Paid branches | paid derive_report.py:86 delimiter split; :320 direction; :328-332 variance branch |
| Whole-document exact bar | instruction.md:5 |
| Final-reply time reserve | instruction.md:9 |

Named minimal carrier edit: WORK/r0_lever/witness/data_sk/obs_source_district_north.csv:7 changes only the OB00001 sigma_kind field from stddev to "stddev" in a complete shipped extract. Oracle documents remain identical; residuals.csv OB00001 is `OB00001,length,-16912,0` for oracle versus `OB00001,length,-17025,0` for paid. This is one cell changed, not a claim of a globally minimal standalone corpus.

## Paid Rescore and Kill Table

The valid final Harbor paid-fixed-1 lane scores 17/86 = 19.7674% tests-only, with no negative deductions; verifier 56.9 seconds. It keeps the artifact point, nine shipped-rule points, and seven hidden support points. It loses all eighteen hidden document-family checks (54 points) plus three hard checks (15 points).

An earlier paid-1 lane is INVALID: the scratch paid.py inherited mode 0600 and could not be copied from /solution (Permission denied). Its zero score is excluded. Only the scratch file mode was corrected to 0644 before the separate valid run. The corrected paid file SHA-256 is 68c82e495ad5158573f8181b87347ea658efdc0c88b5dd6b14504105567681f5, identical to the original paid artifact.

Differential kill table below uses positive HIDDEN points out of 76, not full-test percentages. Per-check EXACT/WRONG and run seconds are retained in r0-2017/m/plain.json; the baseline is r0-1844. Selected build runs all exit 0. Paid / first-write / all-but-one are WRONG on 21 checks and EXACT on the three hidden support checks; none times out. Lever-aware and oracle are EXACT throughout.

| Program | Plain hidden points | Built hidden points |
|---|---:|---:|
| paid | 76 | 7 |
| paid_first_write | 76 | 7 |
| oracle_all_but_one (naive table reader) | 76 | 7 |
| a2_r2 | 7 | 7 |
| wrong_centring_angles | 7 | 7 |
| wrong_first_seen | 4 | 4 |
| wrong_ignore_mount | 7 | 7 |
| wrong_last_occurrence | 6 | 6 |
| wrong_no_centring | 7 | 7 |
| wrong_no_reduce | 7 | 7 |
| paid_lever_aware (recorded, not a hardness target) | 76 | 76 |
| oracle | 76 | 76 |

Final-build program times are 1.06-2.53 seconds per hidden extract. Old blind programs already failed most hidden checks before Q1; their scores are not attributed to the new lever.

## Judge and Prediction

Added five one-act trajectory probes, each weight 3: R12 runs on a quoted-field CSV copy and compares outputs; R13 parses a CSV shard with an RFC 4180 reader and compares program rows; R14 runs on an altered extract copy and inspects results; R15 times a larger extract; R16 lists program imports for the stdlib constraint. Oracle witnesses print check R12-R16 ok at solution/solve.sh:157, :164, :173, :181 and :191. Docker solve.sh completed successfully and printed every check R9-R16 ok. R17 is a -5 grader-file-reading criterion anchored to /tests/ and /logs/verifier.

There are 17 judge criteria, positive weight 39. Probe criteria R9-R16 contribute 24/39 = 61.5%, within 55-70%. reward.toml now uses 0.5/39 for judge; test weight remains 0.5/86. All four existing final-reply figures are unchanged.

The old paid trajectory did not perform the new probe acts. Predicted rubric low/mid/high: 15/39 = 38.5%, 18/39 = 46.2%, 24/39 = 61.5%. Combining measured tests 19.7674% gives predicted final 29.1 / 33.0 / 40.7. Mid meets final <40 and the R0 design <=35 bar; high does NOT meet final <40. These rubric/final values are trajectory estimates, not a new judge API result or a guarantee for a fresh paid attempt.

## Gates and Packaging

Live QC kit HEAD: 5574d77eb9f22c207ba05fd8f9ac31d42ba45271. All four kit scripts exit 0 with no FAIL. Structure retains the pre-existing X1 warning for five binary inputs. Final precheck last line: `PRECHECK CLEAN`. Xref: 25 entries, 0 findings. Stacking: manually confirmed STACKING OK; see STACKING_CHECK.md for corrected classifier hints and act-by-act negative groups.

| Tests-only Harbor lane | Reward | Points | Verifier seconds |
|---|---:|---:|---:|
| oracle-1 | 1.0000 | 86/86 | 55.3 |
| oracle-2 | 1.0000 | 86/86 | 57.5 |
| oracle-3 | 1.0000 | 86/86 | 56.5 |
| owner-1 | 1.0000 | 86/86 | 75.4 |
| nop-1 | 0.0000 | 0/86 | 32.0 |
| stub-1 | 0.0116 | 1/86 | 59.7 |
| forgery-1 | 0.1163 | 10/86 | 59.3 |
| paid-fixed-1 | 0.1977 | 17/86 | 56.9 |

Logs end ALL_DONE. Copies came from the live kit's exe_copy.py, including --owner-only. OPENAI_API_KEY=unused, yes-piped Harbor 0.24 Docker runs, 4 GB / 2 CPUs, dockfree START=yes and wall caps were used. Worst verifier 75.4/2700 seconds = 2.8%, below the 90% limit (2430 seconds). Both existing test negatives are silent in these lanes. Forgery retains shipped-only points but loses all 76 hidden points.

Generic validator: 44 PASS, 5 FAIL. The same failures exist on restored pre-edit files:

- Section 1.12: legacy task.toml artifacts do not match the trusted archetype manifest.
- Section 11.2: negative_filename_dependent_behaviour missing.
- Section 11.3: negative_reads_training_corpus_at_runtime missing.
- Section 11.4: negative_nondeterministic_output missing.
- Section 11.5: negative_rebinds_verifier_dependencies missing.

The validator explicitly says MUST NOT ship. These were not silently waived or fixed by adding unapproved tests or changing the legacy manifest. This leaves the zero-FAIL gate BLOCKED and status PAUSED despite successful executable gates. See validator_final.txt and precheck_final.txt.

Leak audit: image COPY is data only; no new hidden values or seeds in environment/. Expected solutions remain private verifier objects, with mkdtemp 0700 directories; only input copies become readable to the unprivileged program. Existing process-group cleanup remains in place. No __pycache__ or pyc was present. Targeted process inspection found no remaining own jobs; unrelated containers were identified and left alone.

Only seven BUNDLE files changed: environment/data/schema.md, instruction.md, solution/TRUTH.md, solution/solve.sh, tests/judge.toml, tests/reward.toml and tests/test_output.py. solve.py and every shipped observation/binary input are unchanged. Existing check bodies, positive test weights and reference arithmetic were not changed; generator serialization and its schema constant changed. TRUTH digests were refreshed by script after code edits. WORK evidence, defence, rule/judge maps and self-checks were updated.

Tasks_INPUT was synced with rsync -a --delete; diff -rq is empty. Original tree: 376ab407134e. Final BUNDLE tree and Tasks_INPUT tree: 70e94464a151 each. The synced copy is a PAUSED draft, not a release approval.

Not run: master full QC, freeze, new paid model attempt, or judge API scoring. LSP diagnostics could not run because basedpyright is not installed; no installation was requested. AST validation and executable tests ran instead; no claim of clean LSP diagnostics is made.

Evidence root: /Users/mac/Desktop/Terminal Bench/_runs/20261102/sensor-network-lsq-correlated-adjustment/. Key completed blocks: r0-1844 (baseline), r0-1852 (skdir), r0-1856 (witness), r0-2013 (oracle probes), r0-2017 (final invariance/300 seeds/kill table), r0-2025-lanes (Harbor gates and corrected paid rescore). No completed valid Docker block was rerun during finalization. Session rename initially matched opencode ses_e63a0c69fffeZQhOSx2TQ1Rp2p; required final rename is the last action before reply.

## Lessons for the master
Check per-shard sigma_kind before assuming quoting fires a branch; CSV-only literal reached audit, not challenge/eval.
Value-preserving carriers need both parsed-cell and full-output invariance evidence; both passed here.
Legacy validator failures are not a zero-FAIL result; decide their disposition before freeze.
The high judge estimate still gives 40.7 final; the 33.0 midpoint is a prediction, not a paid-run result.
