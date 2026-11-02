# COST_TABLE sentinel-policy-recompute (Harden round 3, P = 52)

Measured with WORK/single_lever.py on the oracle output (one exact edit to the repaired cli.py per row), local scorer, tests channel only. Raw output: OUT harden_r3/local/single_lever.txt. Round 2 table (P = 44): WORK/trap/COST_TABLE_r2.md.

N4 is the only counted lever this round (master decision 25 Oct, see LEVERS.md PL note); N1-N3 stay as feeders of the applied set, L7 as noise, L1 as amplifier.

## Each lever alone and one fact wrong

| lever | reading | earned / 52 | points lost | share of P | tests failed |
|---|---|---|---|---|---|
| N4 timeout pool (counted) | lever off (pool ignored) | 36 | 16 | 0.308 | timeout_pool_hard 5, policy 5, mutation_risk 3, mutation_pool 3 |
| N4 | one fact wrong: fits test taken again on the second share | 36 | 16 | 0.308 | same |
| N4 | one fact wrong: first share kept, pool not shared again | 36 | 16 | 0.308 | same |
| N4 | one fact wrong: only the dropped milliseconds shared again | 36 | 16 | 0.308 | same |
| N4 | one fact wrong: no row dropped below 100 | 36 | 16 | 0.308 | same |
| N4 | one fact wrong: pool shared by the resolved key's rows only | 36 | 16 | 0.308 | same |
| N1 region allowance (feeder) | off / counter per tenant | 29 | 23 | 0.442 | region_hard 5, policy 5, curve 5, trace 5, mutation_allowance 3 |
| N1 | one counter for every row | 32 | 20 | 0.385 | region_hard, policy, curve, trace |
| N2 unit cutover (feeder) | raw / unit from rev | 37 | 15 | 0.288 | cutover_hard 5, policy 5, trace 5 |
| N3 window admit (feeder) | off / resolved tenant only | 29 | 23 | 0.442 | admit_hard 5, policy 5, curve 5, trace 5, mutation_risk 3 |
| draw_order | either refusal still draws the other unit | 37 | 15 | 0.288 | policy, curve, trace |
| L7 per-term rounding (noise) | rounded once on the sum | 44 | 8 | 0.154 | curve 5, mutation_risk 3 |
| L1 controls (amplifier) | stored controls trusted | 47 | 5 | 0.096 | trace 5 |
| carried: row version / half-open window | ignored / inclusive end | 37 | 15 | 0.288 | policy, curve, trace |
| carried: every passing row applies | first passing row only | 16 | 36 | 0.692 | seven w5/w3 checks |
| probe-1 reading (own tenant rows, region value, no admits) | combined | 13 | 39 | 0.750 | nine checks |

## Probe-2 agent program (measured, not a constructed reading)

OUT harden_r3/agent_program/out (claude-opus-5 run 1, all N1-N3 right): 36/52 = 0.6923. Fails hidden_timeout_pool_hard (pool-a 2747 vs 2771), hidden_policy_resolved_document_matches (hidden-c 2610 vs 2565), mutation_risk_delta_moves_only_contribution (2610 vs 2565), mutation_pool_cut_reshares_timeout (2872 vs 2899). Differential fuzz of the N4 rule (OUT harden_r3/proto, 300 corpora, truth identical to the test reference): agent differs on 111/300 (37%).

## All but one right (overall)

overall = (tests + judge) / 2. Measured judge probe 2 = 14/37; with R16 (w3) unpaid = 14/40 = 35.0.

| only this lever wrong | tests | overall at judge 35.0 | below 70 | overall at rubric 90 |
|---|---|---|---|---|
| N4 (any reading) | 69.2 | 52.1 | yes | 79.6 |

## G10

N4 alone and with each one-fact-wrong reading loses 16/52 = 30.8% (>= 25%). N1 and N3 still lose 44.2%, N2 28.8% as feeders; probe 2 showed Opus reads them right, so they are not counted.

# Test-hardening round t1 (26 Oct 2026), measured, P = 80

Program = oracle CORRECT_CLI with one reading changed (WORK/t1_levers.py, scored by local_score.py on the BUNDLE tests; log in OUT harden_t1/local/levers.log). Owned checks weigh 5 (tests_qc W2), the rare-pair check 3.

| reading | tests | lost | failed checks |
|---|---|---|---|
| Q1 sum, no floor | 72/80 = 90.0 | 10.0% | running_timeout_floor_hard 5, rare_rule_pairs 3 |
| Q1 one clamp after the sum | 72/80 = 90.0 | 10.0% | running_timeout_floor_hard 5, rare_rule_pairs 3 |
| Q2 every row independent | 72/80 = 90.0 | 10.0% | reissued_override_hard 5, rare_rule_pairs 3 |
| Q3 aliases ignored | 72/80 = 90.0 | 10.0% | principal_alias_span_hard 5, rare_rule_pairs 3 |
| Q3 alias span ignored | 75/80 = 93.75 | 6.25% | principal_alias_span_hard 5 |
| Q4 requires ignored | 72/80 = 90.0 | 10.0% | requires_order_hard 5, rare_rule_pairs 3 |
| Q4 order-free requires | 72/80 = 90.0 | 10.0% | requires_order_hard 5, rare_rule_pairs 3 |
| Q5 carry ignored | 72/80 = 90.0 | 10.0% | superseded_carry_hard 5, rare_rule_pairs 3 |
| Q5 carry whatever the window | 75/80 = 93.75 | 6.25% | superseded_carry_hard 5 |
| first write (Q1 sum, Q2, Q3, Q4, Q5 ignored) | 52/80 = 65.0 | 35.0% | all six new checks |
| probe-4 agent program as delivered | 52/80 = 65.0 | 35.0% | all six new checks |

- All-but-one (best single-wrong program): 90.0 (<= 91). First write: 65.0 (<= 70). Combo test charged only through the rare pairs (no old corpus and no owned corpus of another rule moves it).
- Old levers at P = 80 (rule_mutants.py): see RULE_COVERAGE.md t1 section.

# Test-hardening round t2 (27 Oct 2026, board 4a82a12), measured, P = 98

Program = oracle CORRECT_CLI with one reading changed (WORK/t2_levers.py, scored by local_score.py on the BUNDLE tests; log WORK/t2_levers3.log). New owned checks w5 (unique_divisor_fit, curve_reset, reinstated_chain), new rare-state check w3 (combo2-a/b). 0 crashes in every variant.

| reading | tests | lost | failed checks |
|---|---|---|---|
| Q1 sum, no floor | 87/98 = 88.78 | 11.2% | running_timeout_floor_hard 5, rare_rule_pairs 3, rare_state_pairs 3 |
| Q2 every row independent | 87/98 = 88.78 | 11.2% | reissued_override_hard 5, rare_rule_pairs 3, rare_state_pairs 3 |
| Q3 aliases ignored | 87/98 = 88.78 | 11.2% | principal_alias_span_hard 5, rare_rule_pairs 3, rare_state_pairs 3 |
| Q4 requires ignored | 87/98 = 88.78 | 11.2% | requires_order_hard 5, rare_rule_pairs 3, rare_state_pairs 3 |
| Q5 carry ignored | 87/98 = 88.78 | 11.2% | superseded_carry_hard 5, rare_rule_pairs 3, rare_state_pairs 3 |
| U iteration_divisor 10 always (reports ignored) | 90/98 = 91.84 | 8.2% | unique_divisor_fit_hard 5, rare_state_pairs 3 |
| U first fitting divisor (no uniqueness) | 90/98 = 91.84 | 8.2% | unique_divisor_fit_hard 5, rare_state_pairs 3 (combo2-b tie) |
| U fit to the first standing report only | 90/98 = 91.84 | 8.2% | unique_divisor_fit_hard 5, rare_state_pairs 3 |
| D1 resets ignored | 90/98 = 91.84 | 8.2% | curve_reset_hard 5, rare_state_pairs 3 |
| D1 only the first reset counts | 90/98 = 91.84 | 8.2% | curve_reset_hard 5, rare_state_pairs 3 |
| D2 reinstated not drawn | 90/98 = 91.84 | 8.2% | reinstated_chain_hard 5, rare_state_pairs 3 |
| D2 reinstated adds its own deltas | 90/98 = 91.84 | 8.2% | reinstated_chain_hard 5, rare_state_pairs 3 |
| D2 deltas of the first active row | 90/98 = 91.84 | 8.2% | reinstated_chain_hard 5, rare_state_pairs 3 |
| first write (rules shipped data never fires skipped: Q1-Q5, U, D2) | 57/98 = 58.16 | 41.8% | 9 checks |
| blind round-1 program (WORK/blind_r1, as delivered) | 85/98 = 86.73 | 13.3% | unique_divisor_fit_hard 5, reinstated_chain_hard 5, rare_state_pairs 3 |

- Each new lever alone 8.2% (5-12 target). Q rule alone 11.2%. All-but-one (best single-wrong program) 91.84 (<= 92). Blind round-1 86.73 (70-90), no crash. Old checks byte-unchanged in logic; the 28 old corpora give identical reference documents (WORK/snap_before_t2.json).
- Blind r1 passes curve_reset_hard because the d1 corpora resolve to divisor 10 (D1 refines U; a reader that ignores reports gets D1 corpora right by design, so D1 is owned only by readers that use the reports).

# Test-hardening round t3 (27 Oct 2026, board 3022cae), measured, P = 131

Programs = oracle CORRECT_CLI with one reading changed (WORK/t3_levers.py, scored by local_score.py on the BUNDLE tests; log WORK/t3_levers_local.log), plus the blind programs as delivered (WORK/blind_r1, WORK/blind_r2). New checks: five R checks w5 (reconciles, cheapest, tie, unit, spare), hidden_rare_repair_pairs_hard w3 (rall-a/b) and hidden_fresh_state_corpora_hard w5 (seed-3 corpora of q1-q5, utie, udecoy, d1, d2). 0 crashes in every variant.

| reading | tests | lost | failed checks |
|---|---|---|---|
| Q1 sum / Q2 / Q3 / Q4 / Q5 (each) | 115/131 = 87.79 | 12.2% | own check 5, rare_rule_pairs 3, rare_state_pairs 3, fresh 5 |
| U none / first fit / first report (each) | 118/131 = 90.08 | 9.9% | unique_divisor_fit 5, rare_state_pairs 3, fresh 5 |
| D1 none / first (each) | 118/131 = 90.08 | 9.9% | curve_reset 5, rare_state_pairs 3, fresh 5 |
| D2 none / own / first (each) | 118/131 = 90.08 | 9.9% | reinstated_chain 5, rare_state_pairs 3, fresh 5 |
| R no ledger_repair.json | 103/131 = 78.63 | 21.4% | all six R checks |
| R greedy (k cheapest spare rows) | 103/131 = 78.63 | 21.4% | all six R checks (wrong) |
| R every k-subset (itertools.combinations) | 103/131 = 78.63 | 21.4% | all six R checks (60 s timeouts) |
| R exact table over (count, max_records sum, timeout sum) | 103/131 = 78.63 | 21.4% | all six R checks (60 s timeouts) |
| R table over (count, max_records sum) then timeout check | 103/131 = 78.63 | 21.4% | all six R checks (wrong) |
| R halves joined on (count, sums) | 103/131 = 78.63 | 21.4% | all six R checks (60 s timeouts) |
| R ties to the last list | 118/131 = 90.08 | 9.9% | cheapest 5, tie 5, rare_repair_pairs 3 |
| R cost read raw (no cutover) | 118/131 = 90.08 | 9.9% | cheapest 5, unit 5, rare_repair_pairs 3 |
| R reissued earlier rows not spare (Q2 in R) | 118/131 = 90.08 | 9.9% | tie 5, spare 5, rare_repair_pairs 3 |
| R carry rows spare (Q5 in R) | 118/131 = 90.08 | 9.9% | tie 5, spare 5, rare_repair_pairs 3 |
| R reinstated source spare (D2 in R) | 118/131 = 90.08 | 9.9% | tie 5, spare 5, rare_repair_pairs 3 |
| first write (t2 list: Q1-Q5, U, D2 skipped; writes no ledger_repair.json) | 85/131 = 64.89 | 35.1% | Q, U, D2, combo, fresh and six R checks |
| first write + R greedy | 57/131 = 43.51 | 56.5% | as above plus coupling checks |
| blind round-1 program | 85/131 = 64.89 | 35.1% | U, D2, rare_state_pairs, fresh, six R |
| blind round-2 program (16ab9fc, as delivered) | 103/131 = 78.63 | 21.4% | exactly the six R checks; no crash |

- All-but-one (best single-wrong program): 90.08 (<= 92). Blind r2 78.63 (70-90). Greedy and naive-exact each lose 21.4% (>= 15). Exact table and halves (meet in the middle) each lose 21.4% (>= 15).
- Docker timing (warm verifier image, --cpus 1, 60 s limit, WORK/r_timing.py, log WORK/r_timing_docker.log), every R corpus (rbig, rtie, runit, rspare, rall; a and b):

| program | result on the 10 R corpora | seconds |
|---|---|---|
| reference | exact on 10/10 | 0.10-0.26 (max 0.26; limit 60) |
| greedy | wrong on 10/10 | 0.12-0.19 |
| table over (count, max_records sum) | wrong on 9/10 (exact on rtie-b) | 0.20-0.26 |
| exact table over (count, both sums) | TIMEOUT on 10/10 | 60 |
| halves (meet in the middle) | TIMEOUT on 10/10 | 60 |
| every k-subset | TIMEOUT on 10/10 | 60 |
| blind r2 | no ledger_repair.json on 10/10 | 0.17-0.28 |

- Spare-row counts of repaired tenants 58-72 (k = 8 rows removed); null tenants 6-17 spare rows.

## Gate v3.6 harden (217875e, 27 Oct 2026)
Test lever and every check body unchanged except the F3 split (shipped config w3 + shipped profiles w3 replace the shipped config-and-profiles w5 check). Positive test total 146, negative -14, 40 checks. Judge positive 37, negative -11, 16 criteria.

| program | tests | lever points kept | loss kind | rubric (a7 trajectory) | final |
|---|---|---|---|---|---|
| a7 agent program (run 07363dd) | 118/146 = 80.82 | 0/28 | TIMEOUT x6 (hidden scale, limit stated instruction.md:5) | 3/37 = 8.11 (R2 only) | 44.47 |
| a7, R12 code quality counted passed (master ask) | 118/146 = 80.82 | 0/28 | TIMEOUT x6 | 4/37 = 10.81 | 45.82 |
| a7, R12 and R13 artifact paths passed | 118/146 = 80.82 | 0/28 | TIMEOUT x6 | 7/37 = 18.92 | 49.87 |
| blind a9b1d42 (rescored) | 118/146 = 80.82 | 0/28 | TIMEOUT x6 | not judged | - |
| harden_t3 generic solvers (greedy, naive, full table, (count,sum) table, halves) | 118/146 = 80.82 | 0/28 | TIMEOUT x6 (wrong document for greedy) | - | - |

- Lever share 28/146 = 19.18%. Arithmetic from the measured per-check results of each program (no new kill test: lever, corpora and checks byte-unchanged; master note 4). The two new shipped checks are passed by every program that passed the old w5 check (same observables, rebuild assert removed).
- CL-4 one-fact-wrong after F3 (arithmetic from QC v7 CL-4 check lists, not re-measured): misreading `requires` fails the requires check 5, rare rule pairs 3, rare state pairs 3, fresh state corpora 5 = 16 -> 130/146 = 0.890; one wrong shipped timeout fails the shipped config check 3 and the shipped validation report check 3, plus the shipped profiles check 3 when the profiles inherit it -> 137/146 or 140/146 (was 137/145).
- Judge: probes R1-R11 33 of 37 (89%), generic probe-rate mid (25% of probes, R12 and R13 as passed) = (8.25 + 4) / 37 = 33.1; a7-trajectory prediction 10.81 (conservative). Target rubric <= 12, final <= 46.5: met at 45.82.

### Measured on the final tests (Docker g36ver-sentinel, 4g/2cpu, 27 Oct 23:11-23:24)
| program | tests | lever points kept | verify secs |
|---|---|---|---|
| a7 agent program (07363dd) | 118/146 = 0.8082 | 0/28 (TIMEOUT x6) | 379 |
| blind 20261026T222609-b1f1 | 97/146 = 0.6644 | 0/28 (+ divisor fit, reinstated chain, rare state pairs, fresh state corpora, shipped validation report) | 17 |
| blind 20261027T031809-7230 | 115/146 = 0.7877 | 0/28 (+ shipped validation report 3) | 20 |
| blind 20261027T051903-d6d5 | 118/146 = 0.8082 | 0/28 (TIMEOUT x6) | 379 |
| oracle x3 / owner-only | 146/146 = 1.0 | 28/28 | 21-22 |
| nop / stub | 0.0 / 0.0 | 0 | - |
| forge (oracle shipped artifacts + forged hidden) | 17/146 = 0.1164 | 0/28 | - |
| F3 isolation: config.json max_records +1 | 137/146 = 0.9384 (config check 3, report digest 3, transcript -3; profiles check passes) | 28/28 | - |
| F3 isolation: profile_dev.json max_records +1 | 143/146 = 0.9795 (profiles check 3 only) | 28/28 | - |

## P12 fix QC v8 (3157183, 28 Oct 2026): restored tool-use check
One check added, `shipped_config_produced_by_repaired_tool` w1 (config.json byte-identical to what the delivered init and set write on the shipped values; the assert the F3 split dropped, now its own check). Every other check body byte-unchanged (OUT/G7_tests_diff.txt). Positive test total 147, negative -14, 41 checks. Judge unchanged in weight (R12 reworded only): +37 / -11.

| program | tests | lever points kept | rubric | final |
|---|---|---|---|---|
| a7 agent program (passed the old combined check, so passes the restored assert) | 119/147 = 80.95 (arithmetic) | 0/28 (TIMEOUT x6) | 4/37 = 10.81 | 45.88 |
| blind d6d5 / a9b1d42 / generic solvers (same per-check results as a7) | 119/147 = 80.95 (arithmetic) | 0/28 | - | - |
| forge (oracle shipped artifacts) | 18/147 = 0.1224 (arithmetic) | 0/28 | - | - |
| hand-written config.json with the right values but not the tool's byte layout | loses the new check 1 | - | - | - |
- Lever R share 28/146 = 19.18% -> 28/147 = 19.05%, ratio 0.993 (trap survival PASS, lever checks byte-unchanged).
