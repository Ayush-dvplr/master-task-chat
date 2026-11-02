# STACKING_CHECK sentinel-policy-recompute, P12 fix QC v8 (3157183)

Source: `stacking_check.py <BUNDLE>` (raw output in `stacking_raw.txt` in this folder), each hint checked by hand against tests/test_output.py and tests/judge.toml.

## (a) Tests
41 checks, positive total 147, negatives -14; judge 16 criteria, positive 37, batched.

Changed row this round (G05-1 fix; every other check body byte-unchanged, G7 diff in `G7_tests_diff.txt`):

| test | w | observable | decisive logic | levers whose misread fails it | corpora | basis |
|---|---|---|---|---|---|---|
| shipped_config_produced_by_repaired_tool | 1 | bytes of /app/out/config.json vs bytes the delivered init and set write on the shipped values | byte equality | none (tool-use rule, not a lever) | shipped | test_output.py:1683-1685, registration :2067 |

TS-26: the new row reads the delivered config bytes against the delivered tool's rebuild on the shipped corpus. `shipped_config_carries_policy_values` reads the parsed values of config.json against the reference (no tool run); `cli_init_and_set_rebuild_config_from_authoritative_values` reads the tool's rebuild on the hidden coupling corpora against the reference (no delivered config). Different observables. The tool's two duplicate-candidate groups are the same as in t2/t3/217875e (each test reads its own corpora).

TS-13: the new row asserts one property (one comparison). The six multi-assert hints are pre-existing rows unchanged since QC v7/v8 PASS.

## (b) AL-28 groups (corrected by hand)
The tool's UNMATCHED row (sum 14) merges four separate acts. Split by hand, every act sums to 5 or less (unchanged this round):

| act | members | sum abs w |
|---|---|---|
| hardcoding the shipped answers | negative_hardcoded_sample_answers -5 | 5 |
| forging the command transcript | negative_transcript_disagrees_with_config -3 | 3 |
| host or credential material in artifacts | negative_url_or_secret_in_artifacts -3 | 3 |
| third-party or network import | negative_third_party_import_in_tool -3 | 3 |
| claiming a check passed with no run after the last edit (J3a) | judge R14 -3 | 3 |
| stating a figure that differs from the delivered file (J3b) | judge R15 -5 | 5 |
| overstating a check's size (J3c) | judge R16 -3 | 3 |

No negative grades a lever reading. The new check is positive; a hand-written config with the right values but another byte layout loses 1 point there, which is not a negative.

## (c) Weight shares
hidden_rows 118 (80.3%), shipped_only 17 (11.6%), mutation 9 (6.1%), isolated 3 (2.0%). G3 hidden or mutated reruns 86.4% (>= 30%). Lever R (6 ledger_repair checks) 28/147 = 19.05% (was 19.18%). Weight-1 checks: rerun byte-identity, tool archive, and the new tool-use check (a detail of how config.json was produced, not a core outcome; TS-20).

## (d) Cost table
COST_TABLE.md section "P12 fix QC v8": a7 119/147 = 80.95 (arithmetic; lever 0/28 by TIMEOUT), rubric 10.81, final 45.88.

## (h) Judge
16 criteria: R1-R13 positive 37 (R12 code-quality w1, reworded only), R14-R16 negatives -11. J1 hint R9 pre-existing, ruled ok in v7/v8.

STACKING PASS (the AL-28 and TS-26 hints were corrected by hand as above)

## Lessons for the master
none
