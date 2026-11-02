# EVIDENCE_MAP sentinel-policy-recompute (t1, IN-16)

Stored `controls` in override_deltas.json are figures the tests check through `ledger_controls` (ok / mismatch per tenant). The control sentence (override_deltas.json:14) counts "every stored row of that tenant, whatever its status, window, version or allowance". The rows below show that only that reading reconciles every control figure once Q2 and Q5 rows exist. Shipped: 228 rows, no repeated override_id and no carry row, so both readings agree there (t-atlas 8 rows, max_records sum -23).

| rule | corpus | sentence | tenant | stored rows / max_records sum | every stored row | one row per override_id (Q2 misread into controls) | reconciles |
|---|---|---|---|---|---|---|---|
| Q2 controls | shipped | `override_deltas.json:14` | t-atlas | 8 / -23 | 8 / -23 | 8 / -23 | both |
| Q2 controls | q2-a | `override_deltas.json:14` | t-atlas | 6 / 2 | 6 / 2 | 5 / -12 | every stored row only |
| Q2 controls | q2-a | `override_deltas.json:14` | t-aurora | 2 / 6 | 2 / 6 | 1 / -9 | every stored row only |
| Q2 controls | q2-b | `override_deltas.json:14` | t-atlas | 8 / 17 | 8 / 17 | 6 / 2 | every stored row only |
| Q2 controls | q2-b | `override_deltas.json:14` | t-aurora | 2 / -4 | 2 / -4 | 1 / 4 | every stored row only |
| Q2 controls | combo-a | `override_deltas.json:14` | t-atlas | 13 / -1 | 13 / -1 | 10 / 2 | every stored row only |
| Q2 controls | combo-a | `override_deltas.json:14` | t-cinder | 4 / -15 | 4 / -15 | 3 / -10 | every stored row only |
| Q2 controls | combo-b | `override_deltas.json:14` | t-atlas | 13 / -74 | 13 / -74 | 10 / -60 | every stored row only |
| Q2 controls | combo-b | `override_deltas.json:14` | t-cinder | 4 / -16 | 4 / -16 | 3 / -6 | every stored row only |

Q2 reading: the reissue sentence (override_deltas.json:6) removes earlier rows from selection and the draw only; the control sentence keeps counting them. A reader who drops them from the controls reports `mismatch` for an honest tenant.

Q5 (a carried delta adds to its principal but the row is not applied):

| rule | corpus | sentence | carry rows (id, carry, window) | carried for K042 | applied_overrides | check |
|---|---|---|---|---|---|---|
| Q5 carry | q5-a | `override_deltas.json:13` | OV-K042-1656 risk_delta WIN-AUX; OV-K042-5033 max_records_delta WIN-AUTH; OV-K042-1950 max_records_delta WIN-PRE | 1656, 5033 (WIN-PRE ends at the instant, half-open) | [OV-K042-1171] | controls count all three (superseded rows are stored rows); r-north draws 2 = applied rows of r-north, carry rows draw none |
| Q5 carry | q5-b | `override_deltas.json:13` | OV-K042-8982 risk_delta WIN-AUX; OV-K042-7006 max_records_delta WIN-AUX; OV-K042-3160 risk_delta WIN-AUTH-V099 | 8982, 7006 (V099 window carries v099) | [OV-K042-8085] | same |

Only the stated reading reconciles the trace: a carry row read as applied would appear in applied_overrides and draw a region unit (refusing a later row where the allowance is tight); a carry row ignored leaves risk_threshold or max_records at the uncarried value.

# Test-hardening round t2 (27 Oct 2026): stated verdicts and determinate facts

| rule | test ids | settling fact (file:line) | wrong readings it contradicts |
|---|---|---|---|
| U no single divisor -> unresolved | hidden_unique_divisor_fit_hard (utie-a, utie-b), hidden_rare_state_pairs_hard (combo2-b) | convergence_spec.txt:7 "When the reports fix no single divisor, the threshold is unresolved: iterations holds only the seed value, and converged and risk_threshold are null"; output_field_spec.txt:14-15 null forms | first fitting divisor; fallback to iteration_divisor 10 |
| U no fit at all | never generated (generator rejects 0-fit corpora) | convergence_spec.txt:7 same verdict ("fix no single divisor" covers zero) | n/a (IN-16 settled by the verdict, cohort v2:120 pattern) |
| U candidate range | all U corpora | reconciliation_rules.conf:3 "whole number from 6 to 14" | divisors outside 6..14 |
| D1 which reports stand | hidden_curve_reset_hard (d1-a, d1-b), combo2 | override_deltas.json:15 "A reset withdraws every curve report at a lower seq"; seq order defined at line 5 | all reports count; only the first reset counts |
| D2 which deltas a reinstated row adds | hidden_reinstated_chain_hard (d2-a, d2-b), combo2 | override_deltas.json:14 "the deltas of the last active row of its override_id at a lower seq" + toy OV-Z1 example (invented values) | own deltas; first active row; row not drawn |
| D2 reinstated with no earlier active row | never generated (check_bounds asserts an earlier active row) | override_deltas.json:14 "when there is no such row it passes no selection" | n/a |
| combo2 Q-dependence (master go 2) | hidden_rare_state_pairs_hard | convergence_spec.txt:7 "computed for the role it names ... by the rules that give the resolved principal its curve"; generator accepted(): at least 2 of the Q2-Q5 wrong readings change the fitted divisor of combo2 | fit by curve alone with an earlier rule wrong |

## Test-hardening t3 (27 Oct 2026)

| rule | where tested | sentence | wrong reading |
|---|---|---|---|
| R no repair | every R corpus (null tenant, max_records sum off by 1) | override_deltas.json:17 "A tenant with no repair has null" | empty list, closest set, omitted key |
| R several cheapest repairs | rtie, rbig (duplicated cheap row) | override_deltas.json:17 "equal totals go to the set whose seq values, in ascending order, come first compared one by one" | last found, larger list |
| R zero rows to remove | not generated on hidden (shipped tenants other than t-atlas are ok, so not keys) | override_deltas.json:17 "(an empty set counts)" -> [] when sums already match, null otherwise | n/a |
| R stored rows above recomputed | not generated | override_deltas.json:17 "a set of its spare rows whose removal leaves" (removal cannot add rows) and "A tenant with no repair has null" | n/a |
| R tenant keys | every R corpus | output_field_spec.txt:17 "keyed by every tenant whose ledger_controls is \"mismatch\"" | all tenants, only repaired tenants |
