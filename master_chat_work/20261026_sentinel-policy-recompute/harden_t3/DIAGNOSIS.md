# DIAGNOSIS sentinel-policy-recompute, test-hardening round 3 (3022cae)

Phase 1 only; no bundle edits. Paths are under `environment/data/` unless named.

## P1.1 Staged tests vs BUNDLE
- `diff -rq Output_RFP/sentinel-policy-recompute/tests BUNDLE/tests`: judge.toml, reward.toml and test_output.py differ.
- The staged tests are from probe 4 (25 Oct), before t1 and t2. The BUNDLE tests are the current ones (P = 98), so the difference is expected. BUNDLE vs Tasks_INPUT: `diff -rq` is empty (rc 0).

## P1.2 Why the fresh blind r2 reader (16ab9fc) scored 98/98
Program: WORK/blind_r2/app/tool/cli.py (885 lines). It read every file in order (BLIND_REPORT.md) and wrote the full tool in one pass about 5 min after start (03:18 to 03:23). It self-checked on shipped data only. Probe-4 Opus did the same: trajectory run_1 step 30, 7 min in, wrote the whole resolver.

| rule | where stated | blind r2 line | what made it easy |
|---|---|---|---|
| Q1 running timeout floor | units_reference.txt:8-9 | cli.py:667-671 | one sentence plus a toy example, dropped into the loop it already had |
| Q2 reissue, last seq wins | override_deltas.json conventions[3] | cli.py:553-562 | a per-id max(seq) filter |
| Q3 alias span | conventions[1] | cli.py:536-543 | the mapping table sits in the same file as the rows |
| Q4 requires, ascending seq | override_precedence.conf:7 | cli.py:580-595 | a membership test inside the seq loop |
| Q5 superseded carry | conventions[10] | cli.py:621-630, 657-663 | a status filter plus a field list |
| U unique divisor fit (t2) | convergence_spec.txt:7, reconciliation_rules.conf:2 | cli.py:699-714 | 9 candidates; it loops over all of them and keeps `fits[0]` only when exactly one fits. The verdict is stated, so the H8 first-fit slip never happened |
| D1 reset withdraws reports | conventions[12] | cli.py:697-698 | a filter on seq greater than the last reset |
| D2 reinstated chains | conventions[11], override_precedence.conf:2 | cli.py:565-569 | the prior active row is looked up by id |
| N1-N4 (earlier rounds) | quota_limits.cfg:6-7, units_reference.txt:6-7, override_precedence.conf:5-8 | cli.py:516-619 | counters and stated arithmetic |

What they share: every rule is a filter, a counter or a loop over a short candidate list. A careful reader turns each into code as soon as it reads the sentence. Even the t2 "unique fit" shape was a 9-way loop with a stated verdict, so it needed no search. Nothing in the task asks for a figure the docs define only by an objective, and nothing grows with the corpus. So adding more stated rules (master note 1) cannot move the score.

## P1.3 Arithmetic (P = 98 now)
- Blind r2: 98/98. Blind r1: 85/98 (86.73). The fully careful reader is at 100.
- To bring a careful reader to 70-90 we need a lever worth about 10-30% that it gets wrong even after reading every word. That means a figure whose right answer cannot be read off the text. The text has to be acted on: a search that grows with the hidden corpus.
- Rules with no hidden-only behaviour: archive/config fields, controls (L1), clamp order, per-term rounding (L7), effective version, tier = role_level, the convergence loop. Shipped data settles all of them.
- Rules that act only on hidden data: N1-N4, Q1-Q5, U, D1, D2. All are transliterated (table above).

## P1.4 Planned lever (Phase 2, after go): computational core R + derived-state cost
### R: cheapest ledger repair (exact optimum defined by objective and constraints only)
- Carrier: the existing per-tenant `controls` block and `ledger_controls` ("ok"/"mismatch") in the trace. Today it is only a parse-and-count check. In shipped data every tenant is "ok".
- New output: resolve also writes `ledger_repair.json`. It is an object keyed by every tenant whose ledger_controls is "mismatch", and each value is the ascending list of seq values of the tenant's repair, or null. It is NOT added to RESOLVE_DOCS, the trace keys or validation_report. So every existing check stays byte-unchanged and none of them cascades.
- Rule text (conventions entry after [13], and output_field_spec.txt line 4 plus a new `ledger_repair` entry). No method words are used:
  "A repair of a tenant whose ledger_controls is mismatch is a set of its stored rows, of any status, whose removal leaves its row count and its max_records_delta sum equal to the figures in controls. The timeout figure does not constrain a repair. The tenant's repair is the one whose removed rows have the smallest total of absolute timeout_ms_delta in milliseconds, read under the stated unit cutover. When totals are equal, it is the set whose seq values, listed in ascending order, come first. When no set qualifies, the value is null."
  It comes with one toy worked example on invented values (4 rows, k = 1, two candidates with equal msum, the cheaper one wins).
- Stated runtime limit, added to instruction.md (one sentence): resolve finishes within 60 s on any reference corpus. The test subprocess timeout is already 60 s (test_body.py:420). The reference must run in at most 15 s in Docker on every hidden corpus.
- Shipped instance: t-atlas (8 rows). Its stored controls drop 2 planted rows (rows 6, msum and tsum adjusted), which gives C(8,2) = 28 candidates and one unique optimum, so naive search is exact and instant. This is a data edit, so common rule 6 applies: regen _SHIPPED_DATA, reward.toml, and TRUTH sha last.
- Hidden corpora (own RNG `sentinel-rpr-<seed>`, same distribution, inside stated ranges -60..60 and -900..900):
  - rpr-big-a/b: one tenant with about 56 bulk rows (superseded, no carry, so no policy effect) and k about 8 planted removals. C(56,8) is about 1.4e9, so naive search times out at 60 s. Greedy (cheapest |timeout| first, or gap-closing) gives an infeasible or costlier set.
  - rpr-tie-a/b: many equal |timeout| values, so several optima tie on cost and only the ascending-seq-first one is right. A DP that keeps the first set it finds writes a valid but wrong set.
  - rpr-unit-a/b: candidates in versions before the cutover (value x 1000). A reader using raw timeout values picks the wrong set.
  - Each corpus also carries one null tenant (stored rows greater than recomputed, or no msum subset fits), with an EVIDENCE_MAP row (IN-15/IN-16).
- Reference: an exact search over (rows removed, msum) for the minimum cost, with the lexicographic tie settled by a suffix table over ascending seq. It is checked against brute force on 300 small seeds (G12) and lives in test_body.py, stdlib only.
- Careful-reader target: it reads the objective, has no stated bound to decompose on, writes `itertools.combinations` (exact on shipped data, under 1 ms) or a greedy, and self-checks on shipped data, which passes. On hidden data it times out (no file, so the R tests fail; the other docs were written earlier, no crash) or writes a plausible non-optimal set.
- Blind r2 program: it writes no ledger_repair.json, so it loses all R points and keeps the rest.

### Tests (feasibility separate from optimality; existing checks unchanged)
- w5 `hidden_ledger_repair_feasible`: on every R corpus, each listed set is distinct seqs of that tenant whose removal reconciles rows and msum, and null appears exactly where the reference has null.
- w6 `hidden_ledger_repair_cheapest_hard`: whole doc exact on rpr-big-a/b.
- w6 `hidden_ledger_repair_tie_hard`: whole doc exact on rpr-tie-a/b.
- w6 `hidden_ledger_repair_unit_hard`: whole doc exact on rpr-unit-a/b.
- Total +23, so P = 121 and reward test_output = 0.5/121. A G5 sentence is added (reference corpora regenerated at grading). Judge criteria are kept; a w3 probe is added only if the solve.sh self-check shows it.
- Projection: blind r2 = 98/121 = 81.0%. Greedy loses 17-23 (81-86%). Naive exact loses 23 on big plus the tie/unit corpora if those are also big, about 81%. Tie-wrong alone loses 6 (95%). Unit-wrong alone loses 6 (95%). Every target is in the 70-90 band for blind r2, greedy and naive; all-but-one is at most 92 for the R family.

## Risks
- Tie and unit corpora must also be big enough that naive search times out. Otherwise, naive exact and greedy have to be measured on them separately (COST_TABLE).
- Verifier timeout 2700 s: 6 R corpora x 60 s of timeouts is fine.
- A smart solver that writes a DP gets full marks. That is intended (the hardness is real, not hidden).
- IN-17: the text says nothing about size or difficulty, and gives no "at most k" or width bound.
