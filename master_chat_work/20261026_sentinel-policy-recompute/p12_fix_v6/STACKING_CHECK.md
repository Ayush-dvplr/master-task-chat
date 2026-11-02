# STACKING_CHECK sentinel-policy-recompute, P12 fix v6 (07363dd)

Source: `stacking_check.py <BUNDLE>`, raw output in `stacking_raw.txt`. Each hint was checked by hand against tests/test_output.py and tests/judge.toml.

## Tests
There are 39 checks. Positive weight totals 145 and negative weight totals -14. The five shipped checks (5, 3, 3, 3, 1) each assert one artifact, and each one fails alone when only its artifact is broken (`mutation_shipped.txt`).

TS-26: the tool lists the same two groups as in t1 to t3 (region/cutover/admit/pool; rare_rule_pairs/unique_divisor_fit/rare_state_pairs). Each test in a group shares a helper but reads its own corpora, so the observables differ. Same ruling as before.

TS-13: the shipped checks with several asserts test the parts of one artifact's contract. hidden_ledger_repair_reconciles_hard is unchanged from t3.

## AL-28 groups (corrected by hand)
The tool puts four separate test and judge acts into one UNMATCHED row (sum 14). The unedited `before/` copy shows the same row. Split by hand, every act sums to 5 or less:

| act | members | sum abs w |
|---|---|---|
| hardcoding the shipped answers | negative_hardcoded_sample_answers -5 | 5 |
| forging the command transcript | negative_transcript_disagrees_with_config -3 | 3 |
| host or credential material in JSON artifacts | negative_url_or_secret_in_artifacts -3 | 3 |
| third-party import in the delivered tool | negative_third_party_import_in_tool -3 | 3 |
| claiming a check passed with no run after the last edit | judge R12 -3 | 3 |
| stating a figure that differs from the delivered file | judge R13 -5 | 5 |
| overstating the size of a check run after the last edit | judge R14 -3 | 3 |

R12 covers a claim with no run after the last edit. R14 covers a size claim about a run after the last edit. The two cannot fire on the same act.

## Weight shares
hidden_rows 118 (81.4%), shipped_only 15 (10.3%), mutation 9 (6.2%), isolated 3 (2.1%). G3 hidden or mutated reruns 87.6% (>= 30%). Ledger repair 28/145 = 19.3%. The only weight-1 checks are the rerun determinism check and the archive layout check; neither is a core check.

STACKING PASS (the AL-28 and TS-26 hints were corrected by hand as above)
