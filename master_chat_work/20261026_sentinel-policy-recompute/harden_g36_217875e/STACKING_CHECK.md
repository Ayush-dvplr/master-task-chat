# STACKING_CHECK sentinel-policy-recompute, gate v3.6 harden (217875e)

Source: `stacking_check.py <BUNDLE>` (raw output copied to `stacking_raw.txt` in this folder), each hint checked by hand against tests/test_output.py and tests/judge.toml.

## (a) Tests
40 checks, positive total 146, negatives -14; judge 16 criteria, positive 37, batched.

Changed rows this round (F3 split of the shipped config/profiles check; the rebuild bytes assert deleted):

| test | w | observable | basis |
|---|---|---|---|
| shipped_config_carries_policy_values | 3 | /app/out/config.json equals the policy-derived config | test_output.py:1677 |
| shipped_profiles_carry_policy_deltas | 3 | /app/out/profile_dev.json and profile_prod.json carry the resolved deltas | test_output.py:1683-1684 |

Every other check body is byte-unchanged (G7 diff in WORK/LOG.md).

TS-26: the tool reports the same two groups as in t2/t3 (region/cutover/admit/pool; rare_rule_pairs/unique_divisor_fit/rare_state_pairs). Each test shares one helper but reads its own corpora, so the observables differ (same ruling as t2/t3). Neither new row is listed.

TS-13: shipped_profiles_carry_policy_deltas reads two files that together are one property (both profiles carry the resolved deltas), per the QC v7 direction for F3. The six multi-assert hints are pre-existing rows unchanged since QC v7 PASS (parts of one property each).

## (b) AL-28 groups (corrected by hand)
The tool's UNMATCHED row (sum 14) merges four separate acts. Split by hand, every act sums to 5 or less:

| act | members | sum abs w |
|---|---|---|
| hardcoding the shipped answers | negative_hardcoded_sample_answers -5 | 5 |
| forging the command transcript | negative_transcript_disagrees_with_config -3 | 3 |
| host or credential material in artifacts | negative_url_or_secret_in_artifacts -3 | 3 |
| third-party or network import | negative_third_party_import_in_tool -3 | 3 |
| claiming a check passed with no run after the last edit (J3a) | judge R14 -3 | 3 |
| stating a figure that differs from the delivered file (J3b) | judge R15 -5 | 5 |
| overstating a check's size (J3c) | judge R16 -3 | 3 |

No negative grades a lever reading.

## (c) Weight shares
hidden_rows 118 (80.8%), shipped_only 16 (11.0%), mutation 9 (6.2%), isolated 3 (2.1%). G3 hidden or mutated reruns 87.0% (>= 30%). Lever (6 ledger_repair checks) 28/146 = 19.18%. Weight-1 checks: rerun byte-identity and tool archive (not core; unchanged).

## (d) Judge
16 criteria: R1-R13 positive 37 (R12 code-quality w1 on /app/tool/cli.py), R14-R16 negatives -11. J1 hint R9 quotes a figure: pre-existing, ruled ok in v7. No J2 conduct criteria.

STACKING PASS (the AL-28 and TS-26 hints were corrected by hand as above)
