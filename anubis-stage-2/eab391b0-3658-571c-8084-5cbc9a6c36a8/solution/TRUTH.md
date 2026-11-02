# TRUTH.md - eab391b0-3658-571c-8084-5cbc9a6c36a8

## Defect

A monorepo lost the program that turned a package index, a workspace file, a pins file, the previous lock and a manifest into a new lock, an issue list and a summary. The notes in `/app/data` document most of the behaviour. Six rules were never written down; the two worked examples (`example_a_*`, `example_b_*`) were produced with all six in force under mode word zero, and the handover note describes a wrong reading of every one of them. The live intake carries mode word 254 in `manifest.json`; seven mode bits each change one resolution step, and what each bit does is written nowhere. The live manifest carries a SHA-256 for each report and for each member's share of the lock, so a candidate reading of the bits can be checked per member.

1. Focal: republished copies. The same package and version published twice with different content keeps the copy with the lowest seq. Lazy readings: last line in the file, most recent seq.
2. Focal: release candidate eligibility. A version `X.Y.Z-rc.N` is a candidate only for an OR group that holds a clause whose bound is itself an rc of the same `X.Y.Z`. Lazy readings: rc versions compete like any other version under plain ordering, or an rc is never picked, or an rc is picked only through an exact `=` clause. Each worked example picks an rc through a `>=`, `^` or `~` bound of its own release.
3. Focal: yank timing. A yank removes a version only when its seq is higher than the seq of the kept publish line. Earlier yanks are counted as ignored. Lazy reading: every yank applies.
4. Focal: previous lock honouring. The previous lock entry is kept (sticky) only when its sha equals the kept copy's sha and the version is still a candidate. Lazy reading: honour it whenever the version is still a candidate.
5. Focal: queue order. The requirements of one requester join the FIFO queue in descending package name order. Lazy readings: ascending order, file order.
6. Focal: duplicate pins. When `pins.csv` has two valid rows for one package, the first one wins. Lazy reading: the later row is current.
7. Drift: screening. Malformed lines (bad JSON, bad UTF-8, wrong key set, non integer or boolean seq, bad name, bad version, bad sha, bad range, self dependency, yank flag false) are counted and dropped; byte-canonical repeats of an accepted line are counted as retransmitted; invalid pins rows are ignored.
8. Trap: the misleading pointer. `handover.md` reads as the old team's authoritative notes. `conventions.md` says where the two disagree, the conventions and the worked examples govern, and the instruction says the team does not trust the handover note.
9. Focal: mode bits. Bit 2 widens a caret on a 0.x bound to the next major. Bit 4 ignores the previous lock. Bit 8 takes the queue last in first out. Bit 16 skips pins for requirements whose requester is a workspace member. Bit 32 counts a line that repeats an accepted line in everything except seq as retransmitted. Bit 64 stops the walk: a pick made at depth three or more enqueues no deps. Bit 128 applies a yank only when its seq exceeds the kept publish seq by more than 8. Lazy reading: the handover claim that the mode word is a debugging switch.
10. Trap: stale outputs. The program must replace any report already present in OUT_DIR, and must write `issues.jsonl` even when it has no records.

Decoy ledger:

| Decoy | Where | Why it is wrong |
|---|---|---|
| "keep the most recent republished copy" | handover.md | worked examples keep the lowest seq copy |
| "yanks always applied" | handover.md | examples keep versions whose yank predates the kept publish |
| "previous lock honoured whenever the version is still a candidate" | handover.md | examples drop sticky entries whose sha differs |
| "rc treated like any version" | handover.md | examples pick an rc only for a range group with an rc bound of that release |
| "requirements queued in file order" | handover.md | examples resolve sibling requirements in descending name order |
| "later pins row is current" | handover.md | examples apply the first valid row |
| "the mode word was a debugging switch" | handover.md | the live manifest digests agree only when the seven bits are honoured |

## Load-bearing work

- Screen `index.jsonl` exactly as `conventions.md` states and reproduce the malformed, retransmitted and republished counts.
- Implement the documented range grammar: `|` OR groups, `,` AND clauses, operators `>=`, `<`, `=`, `^` (npm caret including 0.x), `~`, `*`.
- Infer the six unwritten rules by running candidate readings against both worked examples and comparing byte for byte.
- Run a FIFO breadth first resolution from the workspace members in file order, never revising a pick, recording conflicts and unresolved requirements.
- Render the three reports in the exact byte form of `reports.md` and compute `lock_digest` from the written lock.
- Read the mode word from `manifest.json` and settle what each of the seven bits does by checking candidate readings against the live report and member digests.

## Verification

Test channel: 32 checks in `tests/test_output.py`, positive total 80, negative total 16. Every check generates fresh intakes inside the verifier and runs `/app/out/lockres.py` on them as an unprivileged user in a temporary directory with a per run time budget.

| Check | Weight |
|---|---|
| program_is_delivered | 1 |
| plain_intake_lock_matches | 3 |
| plain_intake_issues_match | 1 |
| plain_intake_summary_matches | 1 |
| screening_counts_match | 1 |
| screened_intake_resolves | 1 |
| republished_copy_choice_isolated | 3 |
| release_candidate_eligibility_isolated | 3 |
| yank_timing_isolated | 3 |
| previous_lock_honouring_isolated | 3 |
| queue_order_isolated | 3 |
| duplicate_pin_choice_isolated | 3 |
| mixed_intake_alpha_resolves | 3 |
| mixed_intake_beta_resolves | 3 |
| lock_digest_agrees_with_lock | 1 |
| empty_issues_file_written | 1 |
| stale_outputs_replaced | 1 |
| worked_example_reproduces | 1 |
| mode_bit_two_resolves | 5 |
| mode_bit_four_resolves | 5 |
| mode_bit_eight_resolves | 5 |
| mode_bit_sixteen_resolves | 5 |
| mode_bit_thirty_two_resolves | 5 |
| mode_bit_sixty_four_resolves | 5 |
| mode_bit_one_hundred_twenty_eight_resolves | 5 |
| mode_word_alpha_resolves | 3 |
| mode_word_beta_resolves | 3 |
| large_intake_resolves | 3 |
| negative_input_folder_mutated | -5 |
| negative_hardcoded_shipped_answers | -5 |
| negative_third_party_dependency | -3 |
| negative_nondeterministic_output | -3 |

Each isolated check uses an intake where only its own rule changes the output, and each mode bit check uses an intake whose mode word is that bit alone and where only that bit moves the output, so one wrong reading costs only its own points. The rc check needs two intakes, one separating the plain ordering and whole range readings, one separating the never and exact clause readings. Easy share (delivery, plain intake, digest, empty file, stale outputs, worked example) is 10 of 80, 0.125. Measured in process: reference 80 of 80; all six rules right with every mode bit ignored 36 of 80; that plus the whole range rc reading 25 of 80; whole range rc reading alone 63 of 80; last republished copy alone 60 of 80; every yank applies alone 55 of 80; only bit 128 ignored 69 of 80.

Judged channel: 35 criteria in `tests/judge.toml`, positive total 84, negative total 25. R1 to R11 check the closing report figures for the live intake; R12 to R17 check that the report names a worked example package as evidence for each unwritten rule; R18 and R19 check the evidence and reproduction statements; R20 to R24 check conduct (running over the live intake, reading the notes first, comparing against the examples, probing a fresh input, named functions); R25 to R29 are negatives (editing shipped data, following a handover reading, a false reproduction claim, a figure that disagrees with the program's own output, a bare except or debug print left in the program); R30 to R32 check that the report states the right meaning of mode bits 4, 8 and 128; R33 checks the manifest agreement statement; R34 and R35 are negatives (a false manifest agreement claim, the claim that the live intake settles under mode zero rules).

Expected live intake figures (mode word 254): picked 34, sticky 0, conflicts 4, unresolved 0, yanks_applied 5, yanks_ignored 14, republished 7, malformed 9, retransmitted 13, pins 5, lock_digest `7fdb189fb52705abb34811da3271a33cf8ff04ac189b3f918725634e198c5f77`. A program that ignores the mode word gives picked 39, sticky 4, conflicts 18, unresolved 3, yanks_applied 14, yanks_ignored 7, republished 12, retransmitted 6. Ignoring a single bit moves: bit 2 conflicts to 5; bit 4 sticky to 4; bit 8 picked to 31; bit 16 conflicts 3, picked 30; bit 32 picked 33, republished 12, retransmitted 6, unresolved 1, yanks_applied 7; bit 64 conflicts 9, picked 36; bit 128 conflicts 5, picked 35, unresolved 1, yanks_applied 12, yanks_ignored 7. Each changes the lock digest.

## Root cause

The resolver's behaviour lives in six choices that no document states and seven mode bits whose meaning no document states. Each choice is a tie break or a timing rule that leaves an intake internally consistent under either reading, so only the worked examples can settle the six rules, and only the live manifest digests can settle the bits.

## Solution shape

`solution/solve.py` is a single stdlib program. `Version` and `read_version` parse and order versions with a release sorting after its rcs. `Range` parses the grammar and decides satisfaction, including the rc eligibility rule. `classify` screens one index line. `Index` keeps the lowest seq copy of each release, counts republished copies, and applies only yanks later than the kept publish. `read_pins` keeps the first valid row per package. `queue_order` sorts one requester's requirements by descending name. `settle` runs the FIFO resolution with sticky entries checked by sha and renders the three reports; `main` reads IN_DIR and writes OUT_DIR. Named constants hold the seven mode bit values, the yank gap span and the depth limit; `Index` takes the mode word and `settle` applies the bits at the screening, pinning, queueing, picking and walking steps.

## Ordered plan

1. Read `conventions.md`, `reports.md` and `handover.md`; treat the handover note as unverified.
2. Implement screening and check the counts against both example summaries.
3. Implement versions, ranges and the documented resolution loop.
4. For each of the six open rules, try each reading and keep the one that reproduces both examples byte for byte.
5. Render the reports exactly and confirm `lock_digest`.
6. For each set bit of the live mode word, try candidate readings and keep the one whose reports and member shares agree with the live manifest digests.
7. Run over `/app/data` into a separate output directory and report the figures and readings.

## Pitfalls

- Trusting `handover.md` on any of the six rules.
- Keeping the last republished copy, or applying every yank.
- Treating rc versions like releases.
- Honouring the previous lock without comparing sha.
- Queueing requirements in file or ascending order.
- Letting a later pins row override the first.
- Leaving an old report in OUT_DIR, or skipping an empty `issues.jsonl`.
- Believing the handover note that the mode word is a debugging switch.
- Writing into `/app/data`.

## Provenance

```yaml
instance_id: eab391b0-3658-571c-8084-5cbc9a6c36a8
task_name: terminal-bench/eab391b0-3658-571c-8084-5cbc9a6c36a8
solve_sh_sha256: d3398f03c8b8fc65b325fd1c295992b650f5f7af99c9f8e9fe2e4f787b67750e
solve_py_sha256: faa03847c8d5d372ec5b6937efcfca99bdfeab09bcfe1b5c9fa2139015af1e0a
language: python
category: Software Engineering
live_intake:
  index_lines: 257
  mode_word: 254
  members: 4
  pins_rows_valid: 5
test_channel:
  checks: 32
  positive: 80
  negative: 16
judged_channel:
  criteria: 35
  positive: 84
  negative: 25
golden_test_channel_score_measured: 1.0
```
