# TRUTH.md - d7898e6d-ea74-503d-bfcc-0cc85775b6cd

## Defect

A storage team lost the program that turned a snapshot feed, a retention policy, a holds file and a manifest into a keep plan, a prune list and a summary. The notes in `/app/data` document most of the behaviour. Six rules were never written down; the two worked examples (`example_a_*`, `example_b_*`) were produced with all six in force under mode word zero, and the handover note describes a wrong reading of every one of them. The live intake carries mode word 254 in `manifest.json`; seven mode bits each change or add one step, and what each bit does is written nowhere. Every manifest carries a SHA-256 for each report and for each host's kept lines. Because 254 sets all seven bits, the live digests can confirm a candidate set of seven bit behaviours, per report and per host, but cannot show which bit value carries which behaviour.

1. Focal: bucket representative. Each class keeps the oldest eligible snapshot of a bucket. Lazy reading: the newest one.
2. Focal: week start. Weekly buckets start on Sunday. Lazy reading: the ISO week starting Monday.
3. Focal: hold expiry. A hold is active only while its `until` date is strictly later than the calendar date of the newest snapshot in the series. Lazy reading: active through the `until` date inclusive.
4. Focal: partial standing. A snapshot in state `partial` never stands for a bucket (it may still be kept by a hold or as a parent). Lazy reading: partial snapshots compete like any other.
5. Focal: republished copies. An id arriving with differing content keeps the copy with the lowest seq. Lazy readings: the last copy in the file, the first copy in the file.
6. Focal: bucket clock. Buckets and the newest snapshot date are read on the UTC clock. Lazy reading: the host local wall clock printed in the stamp.
7. Drift: screening. Malformed lines (bad JSON, bad UTF-8, wrong key set, non integer or boolean seq or size, bad host, vol or id, impossible stamp or offset, self parent, unknown state) are counted and dropped; repeats of an accepted line with keys sorted are counted as retransmitted; invalid holds rows are ignored.
8. Trap: the misleading pointer. `handover.md` reads as the old team's authoritative notes. `conventions.md` says where the two disagree the conventions and the worked examples govern, and the instruction says the team does not trust the handover note.
9. Focal: mode bits. Bit 2 keeps the oldest ok snapshot of every series with reason `anchor`. Bit 4 makes monthly buckets calendar quarters. Bit 8 moves the daily boundary four hours later. Bit 16 makes every hold active whatever its date. Bit 32 counts a line that repeats an accepted line in everything except seq as retransmitted. Bit 64 stops the parent walk at a partial parent. Bit 128 applies `max_bytes`: before the parent walk, the oldest kept snapshots that are not held are dropped until the kept size total is within the budget. Lazy reading: the handover claim that the mode word is a debugging switch.
10. Trap: stale outputs. The program must replace any report already present in OUT_DIR, and must write `prune.jsonl` even when it has no records.

Decoy ledger:

| Decoy | Where | Why it is wrong |
|---|---|---|
| "the newest snapshot stands for its bucket" | handover.md | worked examples keep the oldest member of each bucket |
| "weeks are ISO weeks starting Monday" | handover.md | example weekly picks fall in Sunday based weeks |
| "a hold runs through its until date" | handover.md | examples prune a snapshot whose hold ends on the newest date |
| "partial snapshots count like any other" | handover.md | examples never use a partial snapshot as a class representative |
| "the latest republished copy wins" | handover.md | examples use the lowest seq copy |
| "buckets follow the clock printed in the stamp" | handover.md | examples bucket on UTC |
| "the mode word was a debugging switch" | handover.md | the live manifest digests agree only when the seven bits are honoured |

## Load-bearing work

- Screen `snapshots.jsonl` exactly as `conventions.md` states and reproduce the malformed, retransmitted and republished counts.
- Read the policy with host entries replacing the default as a whole, and the holds file with its header and row rules.
- Infer the six unwritten rules by running candidate readings against both worked examples and comparing byte for byte.
- Run the classes in order, then holds, then the parent walk, per series ordered by UTC instant and id.
- Render the three reports in the exact byte form of `reports.md` and compute `plan_digest` from the written plan.
- Read the mode word from `manifest.json`, recover the seven bit behaviours by checking candidate readings against the live report and host digests, and settle which of them an intake's mode word turns on (see Root cause).

## Verification

Test channel: 35 checks in `tests/test_output.py`, positive total 73, negative total 16. Every check generates fresh intakes inside the verifier and runs `/app/out/prune.py` on them as an unprivileged user in a temporary directory with a per run time budget.

| Check | Weight |
|---|---|
| program_is_delivered | 1 |
| plain_intake_keep_matches | 1 |
| plain_intake_prune_matches | 1 |
| plain_intake_summary_matches | 1 |
| screening_counts_match | 1 |
| screened_intake_resolves | 1 |
| bucket_member_choice_isolated | 1 |
| week_start_isolated | 1 |
| hold_expiry_isolated | 1 |
| partial_standing_isolated | 1 |
| republished_copy_choice_isolated | 1 |
| bucket_clock_isolated | 1 |
| mixed_intake_alpha_resolves | 1 |
| mixed_intake_beta_resolves | 1 |
| plan_digest_agrees_with_keep | 1 |
| empty_prune_file_written | 1 |
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
| mode_pairs_with_bit_two_resolve | 5 |
| mode_pair_twenty_four_resolves | 3 |
| mode_pair_ninety_six_resolves | 3 |
| large_intake_resolves | 3 |
| negative_input_folder_mutated | -5 |
| negative_hardcoded_shipped_answers | -5 |
| negative_third_party_dependency | -3 |
| negative_nondeterministic_output | -3 |

Each isolated check uses an intake where only its own rule changes the output, and each mode bit check uses an intake whose mode word is that bit alone and where only that bit moves the output. The six rules are in force in every other intake as well, so a wrong rule reading also costs points outside its own isolated check (newest bucket member alone scores 43 of 73, below). The three pair checks use mode words 24 and 96, and 6 together with 130, where both set bits move the output, so they catch bits that are each right alone but wrong together. Easy share (delivery, plain intake, digest, empty file, stale outputs, worked example) is 8 of 73, 0.110. Measured in process: reference 73 of 73; all six rules right with every mode bit ignored 18 of 73; all six handover readings 29 of 73; both together 9 of 73; newest bucket member alone 43 of 73; inclusive hold expiry alone 57 of 73; only bit 2 ignored 54 of 73; only bit 128 ignored 57 of 73.

Judged channel: 35 criteria in `tests/judge.toml`, positive total 100, negative total 25. R1 to R8 check the closing report figures for the live intake (snapshots, kept, pruned, held, parents, retransmitted, republished, plan_digest); R9 to R14 check that the report names a worked example snapshot id as evidence for each unwritten rule; R15 checks the reproduction statement; R16 to R19 check conduct (running over the live intake, reading the notes first, comparing against the examples, named functions); R20 to R24 are negatives (editing shipped data, following a handover reading, a false reproduction claim, a figure that disagrees with the program's own output, a bare except or debug print left in the program); R25 to R27 and R31 to R34 check that the report states the right meaning of mode bits 2, 16, 128, 4, 8, 32 and 64; R28 checks the manifest agreement statement; R29 and R30 are negatives (a false manifest agreement claim, the claim that the live intake prunes under mode zero rules); R35 checks the live reason counts (8 hourly, 3 daily, 0 weekly, 3 monthly, 6 hold, 6 parent, 2 anchor).

Expected live intake figures (mode word 254): snapshots 66, kept 28, pruned 38, held 6, parents 6, partial 12, holds 6, malformed 9, retransmitted 8, republished 4, plan_digest `b603ecda33518e7dc26e35866f0e3e5d4bb3d89acc8f5f6f9293e12bae63d242`. Kept reasons: hourly 8, daily 3, monthly 3, anchor 2, hold 6, parent 6. A program that ignores the mode word gives held 2, kept 32, parents 8, pruned 34, retransmitted 4. Ignoring a single bit moves: bit 2 kept 26, pruned 40; bit 4 kept 29, parents 7; bit 8 kept 29, parents 7; bit 16 held 2, kept 23, parents 4, pruned 43; bit 32 retransmitted 4 only; bit 64 kept 30, parents 8; bit 128 kept 33, pruned 33.

## Root cause

The pruner's behaviour lives in six choices that no document states and seven mode bits whose meaning no document states. Each choice leaves an intake internally consistent under either reading, so only the worked examples can settle the six rules. The live manifest digests settle the seven bit behaviours as a set, but since mode word 254 sets every bit, no shipped intake shows which bit value carries which behaviour, and the live digests leave the daily shift open (any shift from one to ten hours reproduces them). Every intake the program is run on carries its own report digests in `manifest.json`, so a program can settle both per intake by trying the candidate behaviour sets its mode word allows and keeping the one whose reports match.

## Solution shape

`solution/solve.py` is a single stdlib program. `is_count`, `utc_of` and `well_formed` validate one record and its stamp. `Snapshot` holds a screened record. `screen_lines` screens the feed, counts malformed, retransmitted and republished lines and keeps the lowest seq copy. `read_holds` applies the header and row rules. `bucket` maps a UTC instant to an hourly, daily, Sunday based weekly or monthly key. `plan_series` runs the classes with the oldest eligible ok member per bucket, the holds with a strict date comparison, the byte budget and the parent walk. `write_reports` renders the three reports. The program never ties a behaviour to a bit value: `BEHAVIOURS` names the seven bit behaviours, `Reading` holds the behaviours in force and the daily shift, and `candidate_readings` yields every set of behaviours with as many members as the mode word has bits set, each with a daily shift of one to twenty three hours when the later day boundary is among them. `plan_intake` plans one intake under one reading, and `settle` screens the feed once for each retransmission reading, tries the candidates in order and keeps the first whose three reports match the digests in that intake's `manifest.json`, or else the candidate matching the most digests. `main` reads IN_DIR and writes OUT_DIR. It reproduces every graded intake byte for byte, and a thousand line intake whose digests match no reading, which forces the full search, finishes in about three seconds.

## Ordered plan

1. Read `conventions.md`, `reports.md` and `handover.md`; treat the handover note as unverified.
2. Implement screening and check the counts against both example summaries.
3. Implement policy, holds, buckets and the documented class order.
4. For each of the six open rules, try each reading and keep the one that reproduces both examples byte for byte.
5. Render the reports exactly and confirm `plan_digest`.
6. Try candidate readings of the seven bits with all of them in force and keep a set whose reports and host digests agree with the live manifest. Then, for each intake, keep the subset of those behaviours, as many as its mode word has bits set, whose reports match that intake's own manifest digests.
7. Run over `/app/data` into a separate output directory and report the figures and readings.

## Pitfalls

- Trusting `handover.md` on any of the six rules.
- Picking the newest snapshot of a bucket, or ISO Monday weeks.
- Keeping a hold active on its `until` date.
- Letting partial snapshots stand for buckets.
- Using the last republished copy.
- Bucketing on the local clock printed in the stamp.
- Leaving an old report in OUT_DIR, or skipping an empty `prune.jsonl`.
- Believing the handover note that the mode word is a debugging switch.
- Writing into `/app/data`.

## Provenance

```yaml
instance_id: d7898e6d-ea74-503d-bfcc-0cc85775b6cd
task_name: terminal-bench/d7898e6d-ea74-503d-bfcc-0cc85775b6cd
solve_sh_sha256: 5e78c55c393ada135a703e9724ec5d986039c8b34eeaccebad3b61c320c486ca
solve_py_sha256: 14cff383386ddfb0a7127493e42adc7d36be7e6dce83e9f57de8bc53479623c7
language: python
category: System Administration
live_intake:
  snapshot_lines: 88
  mode_word: 254
  series: 6
  hosts: 4
  holds_rows_valid: 6
test_channel:
  checks: 35
  positive: 73
  negative: 16
judged_channel:
  criteria: 35
  positive: 100
  negative: 25
golden_test_channel_score_measured: 1.0
```
