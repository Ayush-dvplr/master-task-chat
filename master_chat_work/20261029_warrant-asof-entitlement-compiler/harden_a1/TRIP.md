# TRIP: run a1 (tree 4c85938aa8d4), claude-opus-5 Run 1

Score: tests 51/72 (70.83), judge 61/73 (83.56), final 77.19; 70 trajectory steps (68 agent), $8.96.
Program measured: `WORK/a1_program/` (unzipped from the delivered `/app/out/tool.zip`), all runs in Docker (`--memory 4g --cpus 2`).

## Why a1 lost each test (all WRONG, 21 pts): one reference defect, not an agent error

Diff of the delivered artifacts against the reference (`WORK/harness/diff_a1.py`, `sweep.py`):
- Shipped `validation_report.json`: rejects 980 vs reference 978. Extra rows: `mfa-003431`, `mfa-003436`
  (`idp_mfa_events.log` lines whose `<at>` reads `2026-10-18 19:30:00Z`, a space instead of `T`). Every other
  part (unresolved 241, held_grants 420, unattested 450, sod 289) and both profiles are exact.
- Cause: the reference reads the log with `MFARX = (\S+) (\S+) (\S+) handle=(\S+) recorded=(\S+)` and `fullmatch`
  (tests/test_output.py:46, :157). A space inside `<at>` adds a field, the line fails to match and is dropped
  silently: not counted in `self_check` records, not rejected.
- The docs say a1 is right: time_rules.md:5 (a space instead of `T` is unreadable; a record carrying one in a
  field the compiler must read is rejected `bad_timestamp`), corpus_index.md:37 (line format),
  output_contract.md:26 (self_check `records` = the file's row count). a1 saw the space lines at step 21 and
  followed the doc.

| lost check | w | a1 artifact vs reference | doc line a1 followed |
|---|---|---|---|
| audit_rejects_exact | 5 | +2 mfa bad_timestamp rows | time_rules.md:5 |
| self_check_partition_exact | 3 | idp_mfa_events.log records/rejected +2 | output_contract.md:26 |
| summary_identity_triangle | 5 | audit_counts.rejects 980 vs 978 | output_contract.md (summary counts) |
| heldout_audit_exact | 5 | tier_a rejects +1 and self_check (tier_b exact) | time_rules.md:5 |
| heldout_summary_exact | 3 | tier_a audit_counts.rejects +1 | same |

If P11 aligns the reference with time_rules.md:5, the a1 program scores 72/72 on the current tests.

## Why a1 earned each judge criterion

| id | w | earned | cheap or real probe | trajectory steps |
|---|---|---|---|---|
| R1-R8 figure groups | 5 each | 8/8 | cheap: figures printed by its own `answers.py` from its compiler (outcome, not process) | 54-57, 70 |
| R9 window ends vs observations | 3 | 0 | skipped: global closed/half-open variant replay only | 36-38 |
| R10 HR clock on termination days | 3 | 0 | skipped: site-local vs UTC variant replay of all rows, no termination-day inspection | 36-38 |
| R11 grant start from approvals | 3 | 0 | skipped: requested-start variant only, no decided_at vs effective_from compare | 38, 42-44 |
| R12 recorded_at units | 3 | 1 | cheap: judge credits the implementation (seconds vs ms cutoff), no probe | 22-26 |
| R13 max_grant_hours through layers | 3 | 1 | real: printed the prod.max_grant_hours journal history (144, 40, null, 168) before relying on 72 | 8, 17 |
| R14 DST for shifts | 3 | 1 | real: inspected tz transitions around as_of, printed concrete LA shifts | 18, 63-64 |
| R15 resolved shard priority | 3 | 1 | real: grouped accounts by handle/generation, found equal top generations | 39-41 |
| R16 nested group two routes | 3 | 0 | skipped: one spot key only | 63-64 |
| R17 figures match own output | 3 | 1 | cheap (self-consistency) | 70 |
| R18 repairs stay in modules | 3 | 1 | cheap (and-bundled) | 22-27 |
| R27 code quality | 3 | 1 | cheap | 22-27 |
| R19-R26 negatives | -1..-5 | 0 hit | R24 claim: step 70 says byte-identical after a rerun at step 62/69 (run after last edit, so J3a would not fire) | 62, 69 |

Cheap points: 40 (R1-R8) + 12 (R12, R17, R18, R27) = 52 of 61. Real probe points: 9 (R13-R15).

## Levers today

- Held-out corpora run through the delivered tool: tier_a 51017 / tier_b 62029 (heldout, scale 0.05), tier_c 73031
  (boundary, 0.04), tier_a_shuffled (row order). Checks: tier_a/b profiles (10), heldout_audit (5),
  heldout_summary (3), boundary (3), config_resolution (3) = 24/72 = 33%.
- a1 passes every held-out profile/config/boundary check; it loses heldout_audit/summary only through the MFA defect.
- Extra sweeps of the a1 program on 32 more generator corpora (seeds 11-15, 101-106, scales 0.01-1.0, all three
  variants) and 40 single-rule mutations plus a 26-mutation combined corpus: EXACT except the MFA defect
  (`WORK/proto/fuzz_a1_101.txt`, `combo_a1.txt`, `scale_a1.txt`).
