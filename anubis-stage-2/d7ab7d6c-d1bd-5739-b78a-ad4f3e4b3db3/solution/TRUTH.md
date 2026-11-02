# TRUTH.md - d7ab7d6c-d1bd-5739-b78a-ad4f3e4b3db3

## Defect

A game hosting crew lost the program that replayed its match server request journal against its server list, its owned server rows and the session table it started from, and wrote a decision log, the final session table and a summary. The notes in `/app/data` document most of the behaviour. Six rules were never written down; all four worked examples (`example_a_*` to `example_d_*`) were produced with all six in force, and the handover note describes a wrong reading of every one of them. `conventions.md` names the step each of the seven mode bits touches but not exactly what it does there; `example_a` and `example_b` run under mode word zero, `example_c` under mode word 170 (bits 2, 8, 32, 128) and `example_d` under mode word 84 (bits 4, 16, 64), so every bit is visible in exactly one worked example. The live intake carries mode word 254 in `manifest.json` together with a SHA-256 for each report and for each of the two tables in `sessions.json`.

1. Focal: server scan. When neither an owned server, the named server nor the remembered server is usable, servers are scanned largest slot count first, then by name (never by `servers.json` order). Lazy reading: the smallest server first.
2. Focal: session end. A session or a cooldown is over at the second it ends (live iff `t < until`), for its player and for its server alike. Lazy reading: it is still live during its `until` second.
3. Focal: duplicate owned rows. When a player has several valid `owned.csv` rows, the first valid row stands. Lazy reading: the later row.
4. Focal: released server. A released server cools down until the second the released session would have ended. Lazy reading: it is free at once.
5. Focal: returning player. A player who claimed before is offered their last claimed server after the named server and before the scan, if it is usable. Lazy reading: they are treated like anybody else.
6. Focal: same second order. Records in the same second are replayed by kind (release, extend, claim, ping) and then by seq. Lazy reading: plain seq order.
7. Drift: screening. Malformed lines (not UTF-8, not JSON, not an object, wrong key set, seq, at, party or span not an integer or out of range, bad kind, player, server or clan) are counted and dropped. A line whose content, keys sorted, equals an earlier line that passed validation is counted as retransmitted, including when that earlier line was itself dropped as conflicting. A line reusing the seq of an accepted line with different content is conflicting and dropped; the earlier line stands. Invalid `servers.json` rows (not an object, bad name, slots not an integer of at least 1, repeated name after the first) are skipped, invalid `owned.csv` rows (wrong field count, bad name, unlisted server) are ignored, and `sessions.prev.json` rows need to be objects with a listed server, a valid player, an integer `until` and a null or valid clan; a second valid row for a server already seeded is skipped.
8. Trap: the misleading pointer. `handover.md` reads as the previous operator's notes. `conventions.md` says that where the two disagree the conventions and the worked examples govern, and the instruction says the team does not trust the handover note.
9. Focal: mode bits. Bit 2 ignores the server a claim names. Bit 4 skips seeding from `sessions.prev.json`. Bit 8 caps the cooldown of a released server at 600 seconds after the release; the shipped solution uses `min(end, t + 600)`. Bit 16 refuses a player whose owned server is unusable, with no fall through. Bit 32 builds the retransmission fingerprint without `seq`. Bit 64 makes an `extend` from a player with no live session act as a claim; the shipped solution gives that claim no named server. Bit 128 refuses a claim when another player holds a live session for the same non null clan. Lazy reading: the handover claim that the mode word is a debugging switch.
10. Trap: stale outputs. The program must replace any report already present in OUT_DIR, and must write `decisions.jsonl` even when it has no records.

Points the shipped evidence leaves open, and how grading treats them:

- Under bit 8, a cooldown of exactly 600 seconds after the release fits every worked example and every live manifest digest as well as `min(end, t + 600)` does. Under bit 64, an extend that acts as a claim of the server the record names fits them as well as a claim naming no server. No fresh corpus separates either pair (`OPEN_READINGS` and `_open_readings_agree` in `tests/test_output.py`), and the judged criteria for bits 8 and 64 are worded so both readings satisfy them.
- In `example_a`, `example_c` and `example_d` one server is owned by two players. The shipped solution, like the replay that produced the examples, keeps such a server for the player whose standing `owned.csv` row comes last. The worked examples cannot tell that order from name order, so no fresh corpus has a server owned by two players (`_solo_owners`); only the worked example check, whose answers ship, meets one.
- When no record is replayed, the end second is 0. The empty journal corpus has no previous table, so nothing depends on that choice.

Decoy ledger:

| Decoy | Where | Why it is wrong |
|---|---|---|
| "the smallest free server is offered first" | handover.md | example_a seq 9 at second 35100, example_b seq 8 at second 42000 and seq 7 at second 43800, and example_c seq 2 at second 31800 and seq 24 at second 28500 match only with the largest first scan; the session servers in example_a_out_sessions.json agree |
| "a session is still live during the second it ends" | handover.md | example_a seq 9 at second 35100 and seq 13 at second 36900, and example_c seq 5 at second 30300, match only when the session is over at its end second |
| "the later owned.csv row is the current one" | handover.md | example_a seq 1 at second 35700, example_b seq 16 at second 34800, example_c seq 15 at second 37200 and example_d seq 27 at second 28200 match only on the first valid row |
| "a released server is free again at once" | handover.md | example_a seq 14 at second 38100 is refused, and example_b seq 21 at second 41100 and example_d seq 13 at second 49500 match only with the cooldown |
| "a returning player is handled like anybody else" | handover.md | example_a seq 7 at second 41100 and example_b seq 3 at second 44700 land on the remembered server, and the session servers in example_a_out_sessions.json and example_b_out_sessions.json match only when the last server is remembered |
| "same second records replay in seq order" | handover.md | example_a seq 18 and 16 at second 46200, example_b seq 21 and 5 at second 41100, example_c seq 24 and 6 at second 28500 and example_d seq 23 and 10 at second 34200 match only with kind order |
| "the mode word was a debugging switch" | handover.md | example_c and example_d reproduce, and the live manifest report and table digests agree, only when the seven bits are honoured |

## Load-bearing work

- Screen the journal exactly as `conventions.md` states and reproduce the malformed, retransmitted and conflicting counts.
- Read the server list, the owned rows with their validity rules and the previous session table.
- Infer the six unwritten rules by running candidate readings against all four worked examples and comparing byte for byte.
- Replay the accepted records in time order with the same second order, settling session and cooldown expiry before each record.
- Render the three reports in the exact byte form of `reports.md` and compute `table_digest` from the written session table.
- Settle what each mode bit does in its named step using `example_c` and `example_d`, then confirm the live reading against the live report and table digests.

## Verification

Test channel: 36 checks in `tests/test_output.py`, positive total 107, negative total 17. Every check generates fresh intakes inside the verifier, or regenerates the four shipped worked examples, and runs `/app/out/arena.py` on them as an unprivileged user in a temporary directory with a per run time budget (90 seconds, 60 seconds for the thousand request journal).

| Check | Weight |
|---|---|
| plain_journal_sessions_match | 1 |
| plain_journal_decisions_match | 1 |
| plain_journal_summary_matches | 1 |
| screening_counts_match | 1 |
| screened_journal_replays | 1 |
| server_scan_isolated | 5 |
| session_end_isolated | 5 |
| duplicate_owned_isolated | 5 |
| released_server_isolated | 5 |
| returning_player_isolated | 5 |
| same_second_order_isolated | 5 |
| mixed_journal_alpha_replays | 1 |
| mixed_journal_beta_replays | 1 |
| table_digest_agrees_with_sessions | 1 |
| empty_journal_outputs_written | 1 |
| stale_outputs_replaced | 1 |
| worked_example_reproduces | 1 |
| mode_bit_two_resolves | 5 |
| mode_bit_four_resolves | 5 |
| mode_bit_eight_resolves | 5 |
| mode_bit_sixteen_resolves | 5 |
| mode_bit_thirty_two_resolves | 5 |
| mode_bit_sixty_four_resolves | 5 |
| mode_bit_one_hundred_twenty_eight_resolves | 5 |
| mode_word_alpha_resolves | 5 |
| mode_word_beta_resolves | 5 |
| mode_pairs_with_bit_two_resolve | 5 |
| mode_pair_twenty_four_resolves | 3 |
| mode_pair_ninety_six_resolves | 3 |
| large_journal_replays | 5 |
| mode_pairs_forty_eight_and_one_hundred_thirty_six_resolve | 5 |
| negative_input_folder_mutated | -5 |
| negative_hardcoded_shipped_answers | -5 |
| negative_third_party_dependency | -3 |
| negative_nondeterministic_output | -3 |
| negative_bare_except_clause | -1 |

Each isolated check uses an intake where only the readings of its own rule change the output, and each single bit check uses an intake whose mode word is that bit alone and where only that bit moves the output, so each of those checks names one rule or one bit. The scan order and session end intakes are also moved by a further reading of the same rule that the worked examples rule out (`RULE_FACETS`): scan ties broken in `servers.json` order, which `example_b` refutes, and a server kept taken through the end second of a session its player no longer holds, which `example_c` and the live digests refute. The mixed, pair, mode word, large and worked example checks need every reading in play at once, so a wrong reading also costs those. The four pair checks use mode words 24, 96, 48 together with 136, and 6 together with 130, where both set bits move the output. The screened journal intake carries one row for each written validation rule the corpus builder otherwise never breaks (string and float party values, string, float and zero span values, a line with a byte that is not UTF-8, server rows that are not objects or whose slots are a string, a float or zero, previous table rows that are not objects or carry a bad player, a string `until` or a bad clan, and a second valid previous row for an already seeded server). `table_digest_agrees_with_sessions` needs a non empty session table, so a program that writes empty reports earns nothing from it. The worked example check runs all four shipped examples.

Measured against the real checks: reference 107 of 107, normalized 1.0; no-op 0.0; all six rules right with every mode bit ignored 40 of 107, 0.3738; all six handover readings with every bit ignored 11 of 107, 0.1028 (the three plain journal checks, the screening counts, the screened journal, the empty journal, and the returning player check, whose intake the six handover readings together leave unmoved). One rule wrong alone: smallest server first 0.6262; session live in its end second 0.6916; later owned row 0.7009; released server freed at once 0.6262; returning player forgotten 0.8411; seq order 0.6262; scan ties in `servers.json` order 0.6542; server kept taken through its end second 0.7570. One bit ignored alone: bit 2 0.7570, bit 4 0.8037, bit 8 0.7757, bit 16 0.7757, bit 32 0.7290, bit 64 0.8224, bit 128 0.7570. Both open bit readings and the alphabetical owner reading for a server two players own score 1.0.

Judged channel: 51 criteria in `tests/judge.toml`, positive total 103, negative total 20. R1 to R7, R42 and R43 check the closing report figures for the live intake (claims, extends, releases, refusals, ignored, retransmitted, active, events and cooling, 1 each); R8 checks that the reported table_digest is the one the program wrote (1); R9 to R14 check that the report names a worked example file and journal seq as evidence for each of the six unwritten rules (1 each); R15 to R20 check that the report states the reading of each of the six unwritten rules (5 each), so a handover reading costs its criterion; R21 checks the statement on reproducing all four worked examples (1); R22 to R25 check conduct and stated rules (running over the live intake, reading the three notes first, comparing against the example outputs, named functions, 1 each); R26 to R29 are negatives (editing shipped data -3, a false reproduction claim -5, a count that disagrees with the program's own summary -3, a debug print left in the program -1); R30 to R36 check that the report states the meaning of mode bits 2, 4, 8, 16, 32, 64 and 128 (5 each); R37 checks the manifest agreement statement (1); R38 and R39 are negatives (a false manifest agreement claim -5, the claim that the live intake replays under mode zero rules -3); R40 checks the live session list (5) and R41 the cooling server (3); R44 to R50 check that the report names the worked example and a live manifest digest used to settle each bit (1 each); R51 checks that the agent compares its live digests with the manifest (1). Every oracle score in this file is a test channel score; no judged channel oracle score exists.

Expected live intake figures (mode word 254): events 80, claims 32, extends 2, releases 4, refusals 22, ignored 20, malformed 12, retransmitted 9, conflicting 3, owned 2, active 3, cooling 1, table_digest `df55791c7fc8a92696c073c6bcaa75af9cb3e525dd01c561bf6665d3f38955a3`. Live sessions: cinder vexx until 77700 clan null; frost embr until 74100 clan vipers; lumen mycel until 76500 clan ravens. Live cooldowns: basalt until 73200. A program that ignores the mode word gives events 84, claims 28, extends 5, releases 3, refusals 13, ignored 35, retransmitted 5, active 2. Ignoring a single bit moves: bit 2 only the table digest; bit 4 ignored 19, releases 5 and the decisions; bit 8 active 2, claims 31, cooling 2, refusals 23 and the table digest; bit 16 claims 33, extends 3, refusals 20 and the table digest; bit 32 events 84, ignored 23, refusals 23, retransmitted 5; bit 64 active 2, claims 27, extends 1, ignored 37, refusals 13, releases 2 and the table digest; bit 128 claims 31, extends 5, ignored 21, refusals 20, releases 3.

## Root cause

The replay's behaviour lives in six choices that no document states and seven mode bits whose exact effect no document states. Each choice leaves a journal internally consistent under either reading, so only the worked examples can settle the six rules, and only `example_c`, `example_d` and the live manifest digests can settle the bits.

## Solution shape

`solution/solve.py` is a single stdlib program. `Mode` is a frozen dataclass over the mode word with one property per bit. `is_count`, `shaped`, `shaped_or_null` and `record_is_valid` validate one record against the key set and field rules; `decode_line` decodes one line and `screen_journal` applies screening steps 1 to 4, keeping a content fingerprint for every line that passed validation (without `seq` under bit 32) and the first accepted line per seq. `listed_servers` keeps the first valid row per name, `owned_servers` the first counted row per player and `previous_rows` the valid previous table rows. `Seat` holds one session and `Arena` the table: `seat_of` finds a player's live session, `open_for` tests a server for a player and party (slots, live session, cooldown, someone else's owned server), `clan_taken` serves bit 128, `candidates` yields the named server (unless bit 2), the last server played and then the servers largest first and by name, and `claim`, `extend` (a claim under bit 64) and `release` (cooldown until the session end, capped at 600 seconds under bit 8) apply one record. `replay` seeds the table unless bit 4 is set and replays the records ordered by second, kind and seq, `build_reports` renders the three reports with `digest_lines`, `write_reports` writes OUT_DIR and `main` reads the arguments.

## Ordered plan

1. Read `conventions.md`, `reports.md` and `handover.md`; treat the handover note as unverified.
2. Implement screening and check the counts against all four example summaries.
3. Implement the server list, the owned rows, the previous table and the documented decision order.
4. For each of the six open rules, try each reading and keep the one that reproduces `example_a` and `example_b` byte for byte.
5. For each bit, try candidate behaviours in the step `conventions.md` names and keep the one that reproduces `example_c` or `example_d`.
6. Render the reports exactly, confirm `table_digest`, and check the live run against every live manifest digest.
7. Run over `/app/data` into a separate output directory and report the figures and readings.

## Pitfalls

- Trusting `handover.md` on any of the six rules.
- Scanning the smallest server first, or breaking scan ties in `servers.json` order.
- Keeping a session live during its end second, or keeping its server taken through that second.
- Letting a later owned row replace the first valid one.
- Freeing a released server at once, or forgetting a returning player's last server.
- Replaying same second records in seq order.
- Reading the whole journal as text, so that one line that is not UTF-8 stops the program.
- Accepting string or float numbers, or zero slots and spans, in the journal, the server list or the previous table.
- Leaving an old report in OUT_DIR, or skipping an empty `decisions.jsonl`.
- Believing the handover note that the mode word is a debugging switch.
- Writing into `/app/data`.

## Provenance

```yaml
instance_id: d7ab7d6c-d1bd-5739-b78a-ad4f3e4b3db3
task_name: terminal-bench/d7ab7d6c-d1bd-5739-b78a-ad4f3e4b3db3
solve_sh_sha256: 65e6303bc61eb321a86d939d24deaf7d4e5f01b36b9f380b041ce7908298f40d
solve_py_sha256: 984d00311f48d2e42ea30537b3ef8e3a64806dccb5aa2a122bcbc350560be060
language: python
category: Reverse Engineering
program: /app/out/arena.py
live_intake:
  journal_lines: 105
  mode_word: 254
  servers_valid: 6
  owned_rows_valid: 2
  previous_sessions_valid: 1
test_channel:
  checks: 36
  positive: 107
  negative: 17
judged_channel:
  criteria: 51
  positive: 103
  negative: 20
golden_test_channel_score_measured: 1.0
```
