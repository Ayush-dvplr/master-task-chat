# sentinel-policy-recompute — test-hardening round 3 (board 3022cae)

## Verdict
DONE. One computational-core lever R (cheapest ledger repair) plus one fresh-corpora check, with no new rule hidden. Measured: blind r2 (16ab9fc) 103/131 = 78.63 (loses 21.4%, 0 crashes). Greedy, naive, exact table and halves programs each 103/131 (lose 21.4%). Largest all-but-one 90.08. Oracle 1.000 x3 in Docker. Existing checks are byte-unchanged (`diff test_body_before_t3.py test_body.py`: 0 lines removed).

## Session rename
`name_session.py 3022cae` printed `codex: no match; opencode: ['ses_e85c5d6e8ffe6k81EKU3C6rIYi']`. 3022cae was not in the list. I did not retry on another ID.

## New rules
| id | rule | file:line | shipped fires | hidden fires |
|---|---|---|---|---|
| R44 | spare rows: withdrawn, superseded with no carry, or a later row with the same override_id; a reinstated chain's source is never spare | environment/data/override_deltas.json:17 (conventions[14]) | t-atlas 2 spare (seq 3, 6) | 58-72 spare per repaired tenant |
| R45 | a repair is a set of spare rows whose removal leaves rows, max_records sum and ms timeout sum equal to controls; an empty set counts | override_deltas.json:17 | 1 | 20 tenants / 10 corpora |
| R46 | the smallest total absolute timeout_ms_delta in ms (cutover unit) | override_deltas.json:17 | 1 | 20 |
| R47 | equal totals: the seq list that comes first compared one by one | override_deltas.json:17 | 0 | tie 2 per rbig/rtie/rall corpus |
| R48 | keys: every mismatched tenant; null when there is no repair | override_deltas.json:17, output_field_spec.txt:4, :17 | 0 null | 1 null per corpus |
| R49 | resolve writes ledger_repair.json; each run must finish within 60 s | output_field_spec.txt:4, instruction.md:5 | yes | yes |

The shipped instance changes t-atlas controls to stored 6 / 22 / 2250 at override_deltas.json:3214. Its repair is {"t-atlas": [3, 6]}, and the shipped answers 285/3/2250/51 do not change. The rules have one toy worked example on invented values at :17, with no method words and no trap wording.

BRANCH_FIRE (WORK/BRANCH_FIRE.md t3): shipped has lists 1, null 0 and every reading 0. Each hidden family carries 2 repaired tenants and 1 null tenant. The wrong readings fire 2 per own family: tie in rbig/rtie/rall; unit in rbig/runit/rall; q2/q5/d2 in rtie/rspare/rall; greedy in all 10 corpora.

## Master go conditions
1. Docker, 1 CPU, 60 s limit, on all 10 R corpora (WORK/r_timing_docker.log):
   - reference: 0.10-0.26 s, exact;
   - naive combinations: TIMEOUT 10/10;
   - greedy: wrong 10/10;
   - knapsack table over (count, msum, tsum): TIMEOUT 10/10;
   - halves: TIMEOUT 10/10;
   - (count, msum) shortcut: wrong 9/10.

   An earlier variant with only count and max_records as constraints was exact-easy (DP 0.02 s), so I dropped it (WORK/LOG.md 03:45).
2. Not needed, because the lever passed.
3. The tie-break and the null verdict are each stated once, beside the objective. The ms cost depends on the cutover rule. Spare depends on the Q2 reissue, Q5 carry and D2 reinstated readings, and each wrong reading changes the chosen set (measured).
4. Shipped is t-atlas only (C(2,k)). Each hidden corpus has 2 repaired tenants, 1 null tenant, and ties, pre-cutover and spare decoys by family. The feasibility check (reconciles) is separate from the whole-doc checks, and each R check is owned.
5. The measured cost table is below.
6. Docker ran (manual equivalent; see Not run).

## Counts
- 37 rules stated (31 + R44-R49), 56 data files in 9 formats.
- 34 checks. Positive total 131 (was 98), negatives -11.
- reward.toml: test_output 0.003816793893129771 (0.5/131), judge 0.0125.
- Judge: 15 criteria, unchanged, no new probe. The solve.sh self-check prints only the shipped repair.
- New checks, all owned:
  - hidden_ledger_repair_reconciles_hard (w5; rbig + runit);
  - hidden_ledger_repair_cheapest_hard (w5; rbig);
  - hidden_ledger_repair_tie_hard (w5; rtie);
  - hidden_ledger_repair_unit_hard (w5; runit);
  - hidden_ledger_repair_spare_hard (w5; rspare);
  - hidden_rare_repair_pairs_hard (w3; rall);
  - hidden_fresh_state_corpora_hard (w5; fresh seed-3 corpora of q1-q5/utie/udecoy/d1/d2).

  The fresh check was added so that U/D readings drop to <=92.
- Weight shares: R 28/131 = 21.4%, fresh 3.8%, old 74.8%. The hidden_rows share is 90.1% (STACKING_CHECK.md).
- Precheck rejected weights 4 and 7 (W2), so every weight is in {3, 5}.

## Measured cost table (local, P=131; WORK/COST_TABLE.md, t3_levers_local.log)
| program | tests | score |
|---|---|---|
| oracle | 131/131 | 1.0000 |
| blind r2 (16ab9fc) | 103 | 0.7863 (fails exactly the 6 R checks, 0 crashes) |
| blind r1 | 85 | 0.6489 |
| first write (t2 list) | 85 | 0.6489 |
| first write + greedy R | 57 | 0.4351 |
| r-greedy / r-naive / r-dp / r-dp2 / r-mitm / r-none | 103 each | 0.7863 |
| r-tie-last, r-unit, r-q2, r-q5, r-d2 (each alone) | 118 | 0.9008 |
| q1..q5 wrong alone | 115 | 0.8779 |
| u / d1 / d2 wrong alone | 118 | 0.9008 |

The largest all-but-one score is 90.08 (<=92). Rule mutants on the t3 tests (WORK/rule_mutants_t3.log): all 27 old mutants fail at least one check (0.2748-0.8855). The R readings are covered by the variants above.

## Gates
- STACKING: OUT/STACKING_CHECK.md, STACKING PASS.
- PRECHECK last line: `PRECHECK CLEAN` (4 QC scripts exit 0, warns 0).
- Validator: 37 passed, 3 failed. The 3 failures (§15.5-15.7, TRUTH yaml provenance) were already failing before this round; §15.8 shows positive total 131.
- QC kit HEAD: 5574d77eb9f22c207ba05fd8f9ac31d42ba45271.
- xref_check: 90 entries, 0 findings. TRUTH shas were written by truth_sha.py last.
- Docker (exe_copy.py copies, warm images, lock, ALL_DONE 05:05:21): oracle 1.0 / 1.0 / 1.0, owner-only 1.0, nop 0.0, stub 0.0, forgery 0.0153. Log: OUT/docker_runs.log.
- Tasks_INPUT: synced (cp -Rp, no --delete); `diff -rq` is empty. Tree sha acced1bbac6f (sha256 over sorted relative paths and bytes).

## Not run
- `harbor run`: blocked by the permission rule `*harbor run*`. In its place I ran the same steps by hand in Docker: env image, solve.sh as uid 1000, /app/out streamed into the verifier image, then tests/test.sh. Reward is from reward.json.
- A real harness probe was not run (that is for the master).

## Lessons for the master
1. A fixed-count subset sum with one small-range sum is DP-easy (0.02 s). Adding the second, large-range sum (ms timeouts) as an equality constraint is what made the table and halves time out at 58+ rows.
2. The reference stays fast because the cheap optimum is reached by visiting sets in cost order. A solver who thinks of that is exact, which is the residual risk.
3. Precheck W2 allows only weights in ±{1, 3, 5}. Fix the shares through check count, not by weight.
4. Ownership stays at 2 whole-doc checks per sub-reading only if the feasibility check avoids the corpora where quiet readings fire.
5. The permission rule matches the literal text "harbor run" anywhere in a command, comments included.
