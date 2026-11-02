# TRUTH.md - 2b00e081-e9fc-53b7-8e52-01049ac878c2

## Defect

A sign-in gateway team lost the program that replayed its attempt journal against its lockout policy, its per user overrides and the lock table it started from, and wrote a decision log, the final lock table and a summary. The notes in `/app/data` document most of the behaviour. Six rules were never written down; the two worked examples (`example_a_*`, `example_b_*`) were produced with all six in force under mode word zero, and the handover note describes a wrong reading of every one of them. The live intake carries mode word 254 in `manifest.json`; seven mode bits each change or add one step, and what each bit does is written nowhere. The live manifest carries a SHA-256 for each report and for each of the two tables in `locks.json`, so a candidate reading of the bits can be checked against the live digests.

1. Focal: lock end. A user is locked while `t` has not reached its lock end (locked iff `t < until`), so the second of the lock end is already free. Lazy reading: still locked during the `until` second.
2. Focal: window edge. A failure exactly `window` seconds old still counts (`t - f <= window`). Lazy reading: it has already dropped out.
3. Focal: duplicate overrides. When a user has several valid `overrides.csv` rows, the first valid row stands. Lazy reading: the later row.
4. Focal: locked pass. A correct password from a locked user is denied and the lock stands. Lazy reading: it lets the user in and clears the lock.
5. Focal: repeat lock. A lock lasts the policy `lock` length times `2**(strikes - 1)`, so every repeat lock doubles. Lazy reading: every lock lasts the fixed policy length.
6. Focal: same second order. Records in the same second are replayed by kind (reset, pass, fail, probe) and then by seq. Lazy reading: plain seq order.
7. Drift: screening. Malformed lines (bad UTF-8, bad JSON, not an object, wrong key set, non integer seq or at, bad kind, user, src or agent) are counted and dropped; a line equal to an earlier accepted line with keys sorted is counted as retransmitted; a line reusing an accepted seq with different content is conflicting and dropped, the earlier line stands. Invalid `overrides.csv` rows (wrong field count, upper case or bad user name, limit outside 1 to 9) are ignored, and `locks.prev.json` rows need a valid user, an integer `until` and an integer `strikes` of at least 1.
8. Trap: the misleading pointer. `handover.md` reads as the previous operator's notes. `conventions.md` says that where the two disagree the conventions and the worked examples govern, and the instruction says the team does not trust the handover note.
9. Focal: mode bits. Bit 2 does not seed the table from `locks.prev.json`. Bit 4 ignores `overrides.csv` and uses the policy `threshold` for every user. Bit 8 makes a `pass` from an unlocked user clear that user's counted failures. Bit 16 counts failures per source address in the window and bans a source for the policy `ban` length once it reaches `ban_after`, with result `ban`, after which non reset attempts from that source are denied. Bit 32 builds the retransmission fingerprint without `seq`, so a line repeating an accepted one in everything except `seq` is a retransmission. Bit 64 makes a `probe` count as a failed attempt; with the bit clear a probe is ignored but still feeds the per source count. Bit 128 makes a failure during a lock restart the lock from that failure's second with the current length. Lazy reading: the handover claim that the mode word is a debugging switch.
10. Trap: stale outputs. The program must replace any report already present in OUT_DIR, and must write `decisions.jsonl` even when it has no records.

Decoy ledger:

| Decoy | Where | Why it is wrong |
|---|---|---|
| "a lock is still in force during the second its end arrives" | handover.md | example_a seq 11 and 19 and example_b seq 13 act on a user at the second of its lock end |
| "a failure exactly window seconds old has already dropped out" | handover.md | example_a seq 3 and example_b seq 14 only match when the edge failure still counts |
| "the later overrides.csv row is the current one" | handover.md | example_a seq 9 and example_b seq 18 lock only on the first valid row's limit |
| "a good password from a locked user lets them in and clears the lock" | handover.md | example_a seq 2 and example_b seq 12 deny the pass and keep the lock |
| "every lock lasts the policy lock length" | handover.md | example_a seq 8 and the lock ends in example_b_out_locks.json only match when the repeat lock doubles |
| "same second records replay in seq order" | handover.md | example_a seq 11 and 19 at second 3480 and example_b seq 3 and 6 at second 3120 only match with kind order |
| "the mode word was a debugging switch" | handover.md | the live manifest report and table digests agree only when the seven bits are honoured |

## Load-bearing work

- Screen the journal exactly as `conventions.md` states and reproduce the malformed, retransmitted and conflicting counts.
- Read the policy, the override rows with their validity rules and the previous lock table.
- Infer the six unwritten rules by running candidate readings against both worked examples and comparing byte for byte.
- Replay the accepted records in time order with the same second order, settling lock expiry and window drop before each record.
- Render the three reports in the exact byte form of `reports.md` and compute `table_digest` from the written lock table.
- Read the mode word from `manifest.json` and settle what each of the seven bits does by checking candidate readings against the live report and table digests.

## Verification

Test channel: 35 checks in `tests/test_output.py`, positive total 59, negative total 22. Every check generates fresh intakes inside the verifier from its own seed and runs `/app/out/lockout.py` on them as an unprivileged user in a temporary directory with a per run time budget (90 seconds, 60 seconds for the thousand line journal). No graded intake is a copy of a shipped worked example.

| Check | Weight |
|---|---|
| program_is_delivered | 1 |
| plain_journal_locks_match | 1 |
| plain_journal_decisions_match | 1 |
| plain_journal_summary_matches | 1 |
| screening_counts_match | 1 |
| screened_journal_replays | 1 |
| lock_end_isolated | 1 |
| window_edge_isolated | 1 |
| duplicate_override_isolated | 1 |
| locked_pass_isolated | 1 |
| repeat_lock_isolated | 1 |
| same_second_order_isolated | 1 |
| mixed_journal_alpha_replays | 1 |
| table_digest_agrees_with_locks | 1 |
| empty_outputs_written | 1 |
| stale_outputs_replaced | 1 |
| thousand_line_journal_replays | 1 |
| journal_boundary_records_screened | 1 |
| previous_table_rows_screened | 1 |
| mode_word_alpha_resolves | 5 |
| mode_effect_previous_table_skipped | 5 |
| mode_effect_overrides_skipped | 5 |
| mode_effect_pass_clears_failures | 5 |
| mode_effect_source_ban | 5 |
| mode_effect_seqless_retransmission | 5 |
| mode_effect_probe_counts | 5 |
| mode_effect_lock_slides | 5 |
| negative_input_folder_mutated | -5 |
| negative_hardcoded_shipped_answers | -5 |
| negative_third_party_dependency | -3 |
| negative_nondeterministic_output | -3 |
| negative_bare_except_present | -1 |
| negative_debug_print_present | -1 |
| negative_no_named_functions | -1 |
| negative_network_module_imported | -3 |

Each isolated rule check uses a mode zero intake where only its own rule changes the output. Each `mode_effect_*` check uses an intake with mode word 254 where switching off exactly that one effect changes the output and where none of the six rules moves it, so one wrong rule reading or one wrong bit costs only its own checks and no check depends on which numeric bit carries which effect. `mode_word_alpha_resolves` replays a noisy mode 254 journal where every bit moves the output. `thousand_line_journal_replays` runs 960 records within 60 seconds. `journal_boundary_records_screened` adds records at the field limits (31 character user, 40 character agent, `at` 0, source 255.255.255.255) next to records just past them (32 character user, empty, 41 character and non string agent, boolean `at`, octet 256, upper case kind); removing any one of the eleven added lines changes the reports. `previous_table_rows_screened` adds a second row for the seeded user, upper case and digit led user names, string and float `until`, and boolean, string, zero and float `strikes`; the fixture is chosen so that accepting any one of these skipped rows in its lenient reading changes the reports, so every row is load bearing. `empty_outputs_written` replays a journal whose every line is damaged against an empty previous table, so all three reports must exist, `decisions.jsonl` is empty and the lock table is empty. The source negatives read the program with `ast` and `tokenize`: shipped answers as literals, a module outside the standard library, a network module from the standard library, a bare `except`, a `print` to standard output, a `breakpoint` call or a `pdb` import (a `print` aimed at another stream, such as a usage line on stderr, does not count), and a program with no `def`.

Measured on the test channel with the local verifier: reference 59 of 59, normalized 1.0; no-op 0.0. A single wrong rule reading costs at most 9 of 59 (lock end kept one second 55, window edge dropped 51, later override row 56, locked pass admitted 50, fixed repeat lock 55, seq order in a second 50). Ignoring any single mode bit scores 49 of 59; ignoring the mode word entirely scores 19 of 59. The checks that need no undocumented rule or bit (delivery, digest agreement, the three plain checks, empty outputs) carry 6 of 59.

Judged channel: 32 criteria in `tests/judge.toml`, positive total 64, negative total 24. R1 to R9 check the closing report figures for the live intake (events, allows, fails, locks, denies, ignored, retransmitted, active, banned; 5 each). The live `table_digest` is not judged, because `manifest.json` already carries the same value under `tables.locks`. R10 to R13 check the three live locks and the one banned source (1 each). R14 to R19 check that the report states the right reading of each of the six rules with a worked example file and seq (1 each); a wrong reading, the handover one included, costs only that criterion. R20 to R22 check the reproduction statement, the manifest agreement statement and that each mode bit is either explained with the live digests compared or left open (1 each). R23 to R26 check the trajectory and the delivered program: the live run goes outside `/app/data` (1), the three notes are read before the first program (1), the program's outputs are compared against the example answer files (3), and the program writes each of the six rule readings in a single place (1, agent behavior). R27 to R32 are negatives: editing `/app/data` (-5), seeking online hints (-3), a false reproduction claim (-5), a figure that disagrees with the program's own summary (-3), a false manifest agreement claim (-5), and the claim that the live intake replays under mode zero rules (-3). `solve.sh` reads the three notes, compares its program's output on both examples against the answer files, runs the live intake into `/tmp/lockout-live`, compares the live digests against the manifest and prints a closing report that meets every positive criterion.

Expected live intake figures (mode word 254): events 44, allows 5, fails 18, locks 6, denies 8, ignored 6, malformed 11, retransmitted 6, conflicting 2, overrides 2, unlocks 0, active 3, bans 1, banned 1, table_digest `8ee9acf781bd866078b4a5886e4dcc688bf7b19660ebc0c9ffef7bd59c72a752`. Live locks: ivo strikes 1 until 9000; kai strikes 2 until 10740; vik strikes 1 until 8100. Live bans: 10.23.112.58 until 10800. A program that ignores the mode word gives events 47, allows 6, fails 14, locks 7, denies 9, ignored 10, retransmitted 3, unlocks 1, active 3, bans 0, banned 0. Ignoring a single bit moves: bit 2 active 4, ignored 5, unlocks 1 and the table digest; bit 4 allows 4, denies 12, fails 14, locks 7; bit 8 denies 9, fails 17; bit 16 banned 0, bans 0, fails 19; bit 32 events 47, allows 6, denies 9, ignored 7, retransmitted 3; bit 64 active 2, allows 6, denies 5, fails 17, ignored 10, locks 5 and the table digest; bit 128 active 2, allows 6, denies 5, fails 20 and the table digest.

## Root cause

The replay's behaviour lives in six choices that no document states and seven mode bits whose meaning no document states. Each choice leaves a journal internally consistent under either reading, so only the worked examples can settle the six rules. The bits are only ever met together, as mode word 254, so the graded target is the behaviour of that one mode word; the live manifest's five digests are the evidence for it, and a candidate set of effects can be checked against them without knowing which numeric bit carries which effect.

## Solution shape

`solution/solve.py` is a single stdlib program. `is_count`, `is_address` and `is_user` validate fields and `record_ok` validates one record. `screen_journal` screens the journal and counts malformed, retransmitted and conflicting lines, with the fingerprint dropping `seq` under bit 32. `read_policy`, `read_overrides` (the first valid row stands), `read_previous` and `read_mode` read the policy, the limits, the previous table and the mode word. `Ledger` holds the accounts, the per source failure times and the ban table: `entry_for` creates an account, `seed` loads the previous table, `lock_span` returns the policy lock times `2**(strikes - 1)`, `in_window` keeps a failure exactly one window old, `is_locked` frees the lock end second, `record_failure` counts failures and locks, `record_source` counts and bans sources under bit 16, and `decide` applies each kind and bit. `replay_order` sorts by second, kind rank and seq; `table_lines` and `build_reports` render the three reports; `replay` runs one intake; `write_reports` replaces the outputs; `main` reads IN_DIR and writes OUT_DIR. Named constants hold the seven mode bit values and the kind ranks.

## Ordered plan

1. Read `conventions.md`, `reports.md` and `handover.md`; treat the handover note as unverified.
2. Implement screening and check the counts against both example summaries.
3. Implement the policy, the overrides, the previous table and the documented decision order.
4. For each of the six open rules, try each reading and keep the one that reproduces both examples byte for byte.
5. Render the reports exactly and confirm `table_digest`.
6. For mode word 254, try candidate sets of effects and keep the one whose reports and table digests agree with the live manifest.
7. Run over `/app/data` into a separate output directory and report the figures and readings.

## Pitfalls

- Trusting `handover.md` on any of the six rules.
- Keeping a user locked during the second of its lock end, or dropping a failure exactly one window old.
- Letting a later override row replace the first valid one.
- Letting a correct password from a locked user in and clearing the lock.
- Giving a repeat lock the fixed policy length instead of doubling it.
- Replaying same second records in seq order.
- Leaving an old report in OUT_DIR, or skipping an empty `decisions.jsonl`.
- Believing the handover note that the mode word is a debugging switch.
- Writing into `/app/data`.

## Provenance

```yaml
instance_id: 2b00e081-e9fc-53b7-8e52-01049ac878c2
task_name: terminal-bench/2b00e081-e9fc-53b7-8e52-01049ac878c2
solve_sh_sha256: cc5e46693509fb9dd7f4fdb37161676481ee1815bb206a57ec0fe0c15f4c1268
solve_py_sha256: b44a7a6dfe3cda5ff5282f88d940520f290665ed8c44246e932018d4f64f11c3
language: python
category: Security
program: /app/out/lockout.py
live_intake:
  journal_lines: 64
  mode_word: 254
  overrides_rows_valid: 3
  previous_locks_valid: 2
  policy: window 300, threshold 2, lock 1800, ban_after 4, ban 3600
test_channel:
  checks: 35
  positive: 59
  negative: 22
judged_channel:
  criteria: 32
  positive: 64
  negative: 24
golden_test_channel_score_measured: 1.0
```

