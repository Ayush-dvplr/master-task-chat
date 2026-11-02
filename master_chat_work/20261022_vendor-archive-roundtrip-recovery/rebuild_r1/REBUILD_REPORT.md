# REBUILD_REPORT: vendor-archive-roundtrip-recovery, rebuild round 1 (22 Oct 2026)

Verdict: DONE. Every gate passes: QC 0 FAIL, validator PASS, oracle 1.0 in all four Docker oracle runs, nop 0.0, forgery 0.0. The judge was not run.

Bundle: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/vendor-archive-roundtrip-recovery/` (edited in place, never regenerated). Work notes: `_work/vendor-archive-roundtrip-recovery/` (PLAN.md "Rebuild round 1", TODO.md, LOG.md, LEVERS.md, DESIGN.md "Round 1 changes", README_STALE.md). File hashes: `bundle_sha256.txt`. Docker results: `docker_results/`.

## Changes per master fix

1. Verifier permissions. `_wrap` copies each agent program into a folder the verifier makes (0755). The copy is set to 0644 and run as `python3 -I <copy>` under setpriv as nobody. Inputs are 0644 files in 0755 folders. The encode output folder is 1777. After each run, leftover processes are killed by process group and by uid nobody. Agent runs go through a single lock, because rewardkit runs checks in parallel. Without the lock, the uid sweep killed other checks' live runs, and the first Docker pass scored the oracle between 0.11 and 0.22. With the lock it scores 1.0. Each run has a 20 s timeout and the whole run budget is 2100 s, which fits the task.toml verifier timeout of 2700.
2. Validity bugs.
   - The contract, the tests and solve.py now follow one value rule: raw and delta frames set the cumulator, a reset zeroes it, and no other frame moves it.
   - Every encode fixture is a decoded real segment with one edit. Values are re-decoded after the edit. An edited or added delta gets `delta_raw_len: null`, and the stale `record_count` is kept. No fixture has `value: null` on a value-bearing record, and every record has the keys a decoded record carries.
3. Recheck rows (26 REAL):
   - Row 1, 27: fix 1 above.
   - Row 2: the TRUTH oracle sentence was added only after Docker measured 1.0.
   - Row 3:
     - Judge R1 to R9 are gone.
     - Every isolated rejection check is gated on a clean hidden segment decoding correctly.
     - report_roundtrip runs encode.py.
     - Forgery: 0.0.
   - Row 4: report_roundtrip runs `encode.py` on each row's decoded value and compares hashes against the row hex.
   - Row 5: no judge criterion overlaps a test field.
   - Row 6 (JD-13, UNSURE): left as is. Its criteria no longer exist after the judge rewrite.
   - Row 7: solve.py core rewritten from the contract. The short-file quirk, malformed_frame and the probe-state copy are gone. Short files are now stated in the contract.
   - Row 8: TRUTH counts match the tests.
   - Row 9: fix 2 above. The appendix "What the encoder reads" section lists the keys a new record carries.
   - Row 10: prefixes checked with `startswith(("cap","rej","eval","sample","field"))`.
   - Rows 11, 12, 15: kept with a different design, which conflicts with the recheck. validate_bundle.py now runs strict by default and FAILs 11.2, 11.3 and 11.5 without these negatives. They were rebuilt as behavioural checks, distinct from each other:
     - filename: the same bytes under three names.
     - nondeterministic: the same path three times.
     - runtime corpus: a planted copy of the tables with poisoned names.
     - rebinding: a `.pth` file or a module named after a standard library or grader module.
     - No source grep and no AST grep remain.
   - Row 13: judge R12 dropped.
   - Row 14: new fixtures for:
     - reset clearing state (reset_clears_state and stream_reset_mid_run);
     - offset 15 alone;
     - the `rec_count*5` bound, exact (decodes) and plus one (overflow);
     - the full crc error object.
   - Row 16: format_contract.md "Field names" now covers a long key that names no field (field = key text, unit and id null). The shipped `probe_vent_7` exercises it.
   - Row 17: seed wording fixed. All three seeds are used.
   - Rows 18, 19: instruction hyphens and the reports clause.
   - Row 20: escape_rules.md wording.
   - Row 21: multi-property checks replaced by whole-document checks.
   - Row 22: strict typed comparison (`_matches`).
   - Row 23: moot.
   - Row 24: code-quality criterion split per program (R5, R6).
   - Row 25: timeout (see fix 1).
   - Row 26: kept with a different design, which conflicts with the recheck. validator 7.2 FAILs without SAMPLE_SEED, CHALLENGE_SEED, EVAL_SEED, `_write_corpus` and the main block, so they stay and now do real work:
     - SAMPLE_SEED: tables and catalog.
     - CHALLENGE_SEED: the stream 3 files.
     - EVAL_SEED: the hidden fixtures.
     - `_write_corpus`: regenerates environment/data.
     - The `width` column is now marked informational in the contract.
4. Hardness redesign.
   - (a) instruction.md: no rule count and no list of evidence files. It names the contract as the authority and asks for four computed figures.
   - (b) Composition: 70% of positive weight is on whole documents from hidden streams. Isolated checks are 18%.
   - (c) Nothing shipped confirms a hidden answer. The appendix decode example is schematic. The values of the shipped stream 3 files are asked for only as judge figures and are absent from every file.
   - (d) RUN rule is split across two files: `stream_continues` is named in the contract and its effect is defined in the appendix `--stream` section ("Every other segment starts from fresh state").
   - (e) DICT-CUM is placed by omission: "No other frame moves the cumulator, except reset". MAP-OMIT is in revision_notes.md: unlisted key bytes are identity, and revision_map.ini lists only the bytes that move.
   - (f) Decoy: loader_notes.md says a revision 0 continuation inherits the previous revision. The contract, which wins, says each segment uses its own revision byte. The shipped boundary is capture_alpha (rev 5, continues) followed by capture_beta (rev 0).
   - (g) Judge rewritten per B.12 (below).
5. tests/test.sh keeps `chown root:root` and `chmod 755 /logs/verifier`. tests/Dockerfile pip line is `harbor-rewardkit==0.2.1 litellm==1.105.0`.

Files touched:
- `instruction.md`, `task.toml` (description).
- `environment/data/`: format_contract.md, decoder_appendix.md, escape_rules.md, revision_notes.md, revision_map.ini, capture_alpha.varc, capture_beta.varc; new capture_gamma.varc and loader_notes.md. capture_catalog.jsonl, field_layouts.csv and symbol_table.tsv are byte identical to v0.
- `tests/`: test_output.py, judge.toml, reward.toml, Dockerfile.
- `solution/`: solve.py, TRUTH.md.

## Check bank (24 positive, total 100; 5 negatives)

| Lever | Checks (weight) | Share |
|---|---|---|
| RUN, per-stream runs | stream_interleaved 5, stream_new_run 5, stream_eval_mix 5, stream_challenge_mix 5 | 20% |
| REV, revision per segment (decoy) | stream_revision_change 5 | 5% |
| REMAP, remap before alias, MAP-OMIT | stream_remap_alias 5, single_remapped_modes 5 | 10% |
| STATE, cumulator and reset | stream_reset_mid_run 5, reset_clears_state 3 | 8% |
| ESC/EXT | single_escapes_ext 5 | 5% |
| SALV | salvage_state 5, salvage_mix 5 | 10% |
| ENC | encode_unmodified 5, encode_edited 5, encode_new_record 5 | 15% |
| REJ | reject_magic_over_version, reject_version_over_reserved, reject_reserved_offset15, reject_count_bound, reject_crc_fields (3 each) | 15% |
| Reports | report_decoded_examples, report_roundtrip, report_error_analysis, report_format (3 each) | 12% |

Weight shares:
- Composed: 70%.
- Isolated: 18%.
- Reports: 12%. Only report_format (3%) reads shipped data alone, under the 5% cap.

Negatives:
- negative_hardcoded_sample_answers -5
- negative_nondeterministic_output -3
- negative_filename_dependent_behaviour -3
- negative_reads_training_corpus_at_runtime -5
- negative_rebinds_verifier_dependencies -3

All behavioural negatives stand down unless the program ran cleanly.

Design-time probe (scratch, not a gate): each of 10 wrong readings changes at least one composed check.
- fresh state per file
- one state per manifest
- always carry
- the segment's own flag
- dict moves the cumulator
- raw keeps the cumulator
- REV0 inherit
- alias before remap
- unlisted byte unknown
- fresh state after damage

## Gates (each run once; the D1 to D3 reruns came after the run lock fix)

- D1 QC: structure_qc, instruction_qc, tests_qc and judge_qc, run with both the local c9e3454a scripts and the f3765e67 snapshot. All have 0 FAIL. structure_qc has 1 WARN (X1, the three binary .varc files). tests_qc: 37 pass, H6 pass. judge_qc: 19 pass, G2 pass on `mode = "batched"`.
- D2: `validate_bundle.py --archetype format-recovery` gives 49 passed, 0 failed, 0 warnings, GATE PASS (live and snapshot).
- D3 Docker, tests-only copies from exe_copy.py, Harbor 0.24.0:
  - oracle run 1: 1.0
  - oracle run 2: 1.0
  - oracle with `chmod 600` on both programs at the end of solve.sh: 1.0
  - owner-only oracle (`--owner-only`): 1.0
  - nop: 0.0
- D4 forgery (decode prints bad_magic, encode writes a stub, reports hand-written from the docs): 0.0, with no negative fired. Target was 0.05 or below.
- D5: judge not run (checked by reading, below).
- Local, no Docker: oracle 100/100, nop 0.

QC changes since 2690e960, each against this bundle:
- tests_qc H6/TS-30 (agent program readable before the uid drop): PASS.
- H6 interpreter-switch skip (f3765e67): PASS.
- K8 litellm pin: FIXED.
- judge_qc G2 `mode = "batched"` (d9f94333): FIXED.
- exe_copy `--owner-only` Step 10 run: PASS (1.0).
- test.sh `chown root:root` + `chmod 755`: PASS.
- TRUTH has no retired provenance keys: PASS.
- judge annotations are exactly mode, type, evaluation_target, importance: PASS.
- The local harness clone is still at c9e3454a. It was not pulled, because only read-only git is allowed. The f3765e67 checks were run from a read-only snapshot.

## Judge check by reading (B.12)

- R1 to R4 each ask for one figure: -786, -23254, 3869, -247191366.
  - R1 needs the run rule, the cross-file state and DICT-CUM.
  - R2 needs the cross-file state, raw-sets-cumulator and DICT-CUM.
  - R3 needs the per-segment revision (the decoy gives 8210), the remap and the unknown long key.
  - R4 needs the rejection rules and the value rules over the whole catalog.
  - None of the figures appears in any shipped file (word-boundary search), and no test grades these inputs.
- R7 is the honesty negative (a claimed validation that the trajectory does not show).
- R8 is the grader-path negative.
- There are no multi-figure criteria, no echo-of-doc criteria and no "name one example" ask.
- R5 and R6, the program structure criteria (3 each), are the one cheap-to-meet risk.

## Not run
Judge channel; real agent trajectory; PL QC. Next step: Ayush runs the PL QC and 1 trajectory.
