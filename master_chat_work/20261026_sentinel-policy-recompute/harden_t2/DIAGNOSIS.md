# DIAGNOSIS sentinel-policy-recompute, test-hardening round 2 (4a82a12)

Phase 1 only; no bundle edits. Paths are under `environment/data/` unless named.

## P1.1 Phase A: staged tests vs BUNDLE
- `diff -rq Output_RFP/.../tests BUNDLE/tests`: judge.toml, reward.toml and test_output.py differ.
- The staged tests are from probe 4 (25 Oct, before t1). t1 changed test_output.py and reward.toml (Q1-Q5, P = 80), and d0f1870 rebuilt judge.toml. The run tests are the BUNDLE tests (the master note says so), so the difference is expected. BUNDLE vs Tasks_INPUT: `diff -rq` is empty.

## P1.2 Why the blind r1 reader scored 80/80
Program: WORK/blind_r1/app/tool/cli.py (551 lines). It was written in one pass about 5 min after start (BLIND_REPORT.md:4), after it read every data file in order (BLIND_REPORT.md:6-18). Probe-4 Opus did the same: trajectory run_1 step 30 (00:39:49, 7 min in) wrote the whole resolver with N1-N4.

| rule | where stated | blind r1 line | what made it easy |
|---|---|---|---|
| Q1 running timeout floor | units_reference.txt:8-9 | cli.py:382-388 | one sentence plus a toy example; the floor goes in the loop it already had |
| Q2 reissue, last seq wins | override_deltas.json conventions[3] | cli.py:286-304 | a per-id max(seq) filter is one line |
| Q3 alias span | override_deltas.json conventions[1] | cli.py:264-271 | the key-mapping table is in the same file as the rows |
| Q4 requires, ascending seq | override_precedence.conf:7 | cli.py:313-315 | it checks against the set of rows already applied in the seq loop it already had |
| Q5 superseded carry | override_deltas.json conventions[10] | cli.py:350-361 | a filter on status plus a field list |
| N1 region allowance | quota_limits.cfg:6-8 | cli.py:306-323 | a counter keyed by region |
| N3 window admit | override_precedence.conf:5-6 | cli.py:306-323 | a counter keyed by window |
| N4 timeout pool | override_precedence.conf:8 | cli.py:325-347 | the arithmetic is written out in full |
| N2 cutover unit | units_reference.txt:6-7 | cli.py:246-251 | a value is compared with a constant |

What they share: each rule is a filter or a counter over the current row or the one seq loop. Each names its value and is sitting next to its data. Each can be turned straight into code and needs no search and no record built from other records. When a careful reader reads the rule once, it gets it right. Shipped data never fires them, but that does not matter, because no reader needs shipped data to find out what the rule means.

## P1.3 Arithmetic (P = 80 now)
- Blind r1 scores 80/80, and so does every reader who reads every file. If one Q rule is missed alone, the score is 72/80 = 90.0 (w5 owned + w3 rare_pairs). To reach 70-90, a reader must miss 2-3 owned groups.
- Rules with no hidden-only behaviour: archive and config fields, controls (L1), clamp order, per-term rounding (L7), effective version, tier = role_level, B9/B7, and the convergence loop itself. Shipped data exercises all of them fully, so a self-check on shipped data settles them.
- Rules that act only on hidden data: N1-N4 and Q1-Q5. A reader still gets all of them right, because each is a plain statement that needs no evidence.
- No rule yet asks the reader to infer a value from several records or to build state from earlier records. Under LEVER_RULES_v3, those two shapes are the ones that defeat a careful single-pass reader: S3 unique fit (H8 first fit) and derived state (H6 state used too early).

## P1.4 Planned levers (Phase 2, after go)
All three use shipped data that never fires them (BRANCH_FIRE 0). Each states its verdict for "no fit" and "more than one fit" in the contract. Each is one sentence with a toy example on invented values.

### U: divisor in force settled by reported curves (S3 unique fit, S2 degenerate shipped)
- Data: reconciliation_rules.conf keeps `iteration_divisor = 10`. It gains a section `[reported_curves]` with lines `<name> = <tier> <contribution> <converged>`, which ships empty.
- Rule sentence (in that file): while any curve is reported, the divisor in force is the one whole number from 6 to 14 under which every curve reported after the last reset line reconverges to its reported converged value. Each curve reconverges from the base_threshold of its tier, under the stated iteration_rule, epsilon and max_iterations. `iteration_divisor` holds only while no curve is reported.
- Verdict, stated word for word: when no number or more than one number fits, the threshold is unresolved, iterations is `[base_threshold]`, and converged and risk_threshold are null. output_field_spec.txt names the null form (QL Q3).
- Careful-reader target: it loops over 6..14 and returns the first divisor that fits (H8, `combinations[0]`). Or it tests each candidate against the first listed curve only.
- Hidden corpora: u-tie, where 2+ divisors fit every curve (the measured curves tie often: b=20, c=20 gives 24 for d=9 and d=10) and the reference writes unresolved. u-decoy, where the first curve alone fits a smaller divisor and only all the curves together leave exactly one.
- Wrong document: a numeric threshold where null is due, or the wrong iterations and risk_threshold. Both are plausible, with no crash.
- Blind r1 misses it: it reads the iteration_divisor key and never looks at the new section (configparser flattens all sections; the new keys are unique, so nothing crashes).
- WORK/UNIQUENESS.md will prove, for each hidden corpus, the exact number of fitting divisors (0, 1 or 2+) by checking all 9 candidates. EVIDENCE_MAP rows cover the 0-fit and 2+-fit verdicts (IN-15, IN-16).

### D1: only curves after the last reset count (derived state, order of earlier events)
- Data: lines `<name> = reset` inside `[reported_curves]`; the order is the file order.
- Rule: a curve reported before a later reset line is not evidence. The deciding order is the line order of the section, which is already the order of the reports. No new "process in this order" directive is added.
- Careful-reader target: a filter that keeps every curve line and skips reset lines as noise.
- Hidden corpora d1-a and d1-b: curves before the last reset were reported under another divisor. If they are counted, no divisor fits (unresolved written) or a different one fits.
- Blind r1 misses it (divisor 10).

### D2: reinstated row restores the deltas of its last earlier active row (derived state, revision chain)
- Data: new status value `reinstated` in override_deltas.json rows. It is named in the status sentence and in conventions (QL Q3).
- Rule: a reinstated row draws as an active row does (selection, requires, allowance, admit, pool). It adds the deltas of the last earlier row of its override_id whose status is active, in ascending seq (the existing definition in conventions[2]), not its own deltas. If no earlier active row of its id exists, the row is refused.
- Careful-reader target: it draws the row with its own deltas (per-row), or drops it as not active. Both give a plausible wrong max_records, retry, timeout, contribution and applied_overrides.
- Hidden corpora d2-a and d2-b: >=2 reinstated rows each. The earlier active row has a different seq, and Q2 dedupe has already hidden it. At least one chain is active, then superseded, then reinstated.
- Blind r1 misses it: status != active, so the row is not drawn (cli.py:302); no crash.

### T4 combo2 (own RNG `sentinel-combo2-<seed>`)
Each corpus plants U/D1/D2 on the same records as Q1-Q5 and N1/N3: a reinstated row under an alias (Q3), a reinstated row that is a reissue (Q2), a reinstated row named in requires (Q4), a negative restored timeout under the floor (Q1), and a superseded carry beside the chain (Q5) in north (N1). None of this appears in shipped data.

### Points (G1/G1a whole-document exact per corpus; G3)
- Add w5 hidden_unique_divisor_fit_hard (u-tie, u-decoy), w5 hidden_curve_reset_hard (d1-a, d1-b), w5 hidden_reinstated_chain_hard (d2-a, d2-b) and w3 hidden_rare_rule_pairs_2 (combo2-a, combo2-b). P = 98. No existing weight moves.
- Miss one new lever alone: 90/98 = 91.8 (-8.2%). Miss one Q alone: 87/98 = 88.8 (-11.2%). Every all-but-one score is <= 91.8.
- Blind r1 loses 18 -> 80/98 = 81.6 (inside 70-90). The first-write program loses Q, U, D and both combos -> about 52/98 (to be measured).
- The generator rejects a corpus unless the blind reading (fixed divisor, reinstated not drawn) differs, its own reading differs, and the other quiet readings leave the documents unchanged (ownership).
- Breadth goes from 28 to 31 rules, keeping 56 data files and >=5 formats.
- Judge: kept. Add one w3 probe per new rule only if solve.sh can print `check <id> ok` with a witness. Phase 2 decides.

## Risks I will check
- The configparser in blind r1 is strict: names must be unique, every line must be `k = v`, and comments must sit on their own lines.
- With d in 6..14 the iteration converges well within 64 steps (monotone from the seed), so "unresolved" comes only from the fit count.
- The rule sentences carry no method words and no trap note (IN-17). There is one toy example per rule (W6), and no answer key (W11).
