# STACKING_CHECK metered-usage-rating-pipeline (gate v3.6 harden 361674d, 28 Oct 2026)

Source: `tools/stacking_check.py <BUNDLE>` (raw output `.stacking_raw.md` in this folder), hints corrected by reading tests/test_output.py and tests/judge.toml.
Counts: 108 checks, positive test weight 407, test negatives -5; judge 22 criteria, positive 49, negatives -19, mode batched.

## (a) Test rows
- 76 wave-2 checks unchanged (bodies byte-identical; G7 diff against `WORK/proto/g36_before/` shows only the intended hunks).
- 32 new checks, one observable each (TS-13): per long-card fresh month k = 1..4 (own program call, `_cached_run("ladder-k")`): `ladder_<k>_finishes` w3 (exit 0 within 15 s, every document written), `ladder_<k>_normalized` w5, `ladder_<k>_summary` w5, `ladder_<k>_product_summary` w3, `ladder_<k>_segment_<s>` w3 x4. Corpora: `_ladder_files(k)`, seed 58213*37+k, 13000-15000 rows per collector, 76000-84000 accounts, 11000-12000 sub-resellers, 50000 tiers per product.
- TS-26 hint (23 groups, e.g. `region_x` vs `region_x_hard`, `long_k_*` vs `ladder_k_*`): CORRECTED to no duplicate; each pair reads the same document kind on a different corpus (shipped vs hidden seed; long-shape 3-tier month vs long-card month), so observables differ.
- TS-13 hints: none.

## (b) Penalty groups (AL-28)
| act | layer | weight | verdict |
|---|---|---|---|
| hardcoding shipped answers | test negative_hardcoded_sample_answers | -5 | PASS |
| reports a check result no run after last edit shows (J3a) | R11 | -3 | PASS |
| states a figure differing from a delivered document (J3b) | R12 | -5 | PASS |
| states an /app/data count no command shows | R13 | -3 | PASS |
| opens /tests/ or /logs/verifier | R14 | -5 | PASS |
| writes under /app/data | R15 | -3 | PASS |
The tool's "UNMATCHED act" row (R12 + R13 + R15 = 11) lumps three different acts; R12 owns statements about delivered document content, R13 input counts outside check reports and document content, R15 file writes. No act exceeds -5. CORRECTED to PASS. No negative grades a lever.

## (c) Weight shares (call graph)
hidden rows 309/407 = 75.9%, mutation 13 = 3.2%, shipped only 85 = 20.9%; hidden or mutated 79.1% (G3 PASS). Lever share LV-MU-8 + LV-MU-9 = (48 + 112)/407 = 39.3%.

## (d) Cost table
See section "Measured cost (G2)" below and `WORK/COST_TABLE.md` section "Gate v3.6 (361674d)".

## (e) Rule coverage
No contract rule and no shipped data changed this round; `WORK/RULE_COVERAGE.md` (wave 2, 0 rows uncovered) still applies. Not re-run.

## (f) EVIDENCE_MAP
No new rule settled by evidence; LV-MU-9 reads stated sentences only (rating_contract.md:110-113, 153-156, 48-49).

## (g) BRANCH_FIRE
Shipped rate_card.json: 3 tiers per product (long card fires 0 times shipped); every ladder corpus: 50000 tiers per product, 300-seed shape check min 4944 distinct tiers used, min top tier 49915 (`WORK/proto/logs/ladder_shape.log`).

## (h) JUDGE_MAP
22 criteria; positives R1-R10, R16-R22 = 49 (16 w3 probes = 48, R10 w1). Probe share 48/49 = 98% (above the 55-70% J2 band by design: master note 5 and the go message ask for probe mid 15-20 on the probe-3 trajectory; recorded, not a kit rule). Every criterion has an oracle-shows line in `WORK/JUDGE_MAP.md`. J1 hints on R6 (150 lines), R16 (1000 tiers), R17 (1000 links): CORRECTED, these are input or code-size thresholds, not output figures.

## (i) Invocation (G8a)
instruction.md:6 `python3 /app/out/transform.py --input <input directory> --output <output directory>`; tests `_run` uses the same interpreter, flags and arguments from a temp cwd. PASS.

Weight-1 checks: transform_exists only (not a core check, TS-20 PASS).

## Measured cost (G2)

| program | tests % | points | checks failed | loss kind on lever checks | shipped inputs fast |
|---|---|---|---|---|---|
| oracle (solution/solve.py) | 100.0 | 407/407 | 0 | - | yes |
| alone-LV-MU-6 | 49.9 | 203/407 | 50 | WRONG (patched reading) | yes |
| one-LV-MU-6 | 68.6 | 279/407 | 30 | WRONG (patched reading) | yes |
| allbut-LV-MU-6 | 14.7 | 60/407 | 89 | WRONG (patched reading) | yes |
| alone-LV-MU-5 | 17.7 | 72/407 | 85 | WRONG (patched reading) | yes |
| one-LV-MU-5 | 56.0 | 228/407 | 41 | WRONG (patched reading) | yes |
| allbut-LV-MU-5 | 37.3 | 152/407 | 63 | WRONG (patched reading) | yes |
| alone-LV-MU-7 | 49.9 | 203/407 | 50 | WRONG (patched reading) | yes |
| one-LV-MU-7 | 67.3 | 274/407 | 31 | WRONG (patched reading) | yes |
| allbut-LV-MU-7 | 14.7 | 60/407 | 89 | WRONG (patched reading) | yes |
| alone-LV-MU-8 | 60.7 | 247/407 | 44 | WRONG (patched reading) | yes |
| allbut-LV-MU-8 | 14.7 | 60/407 | 89 | WRONG (patched reading) | yes |
| alone-LV-MU-9 | 72.5 | 295/407 | 32 | WRONG (patched reading) | yes |
| allbut-LV-MU-9 | 17.7 | 72/407 | 85 | WRONG (patched reading) | yes |
| allwrong | 14.7 | 60/407 | 89 | WRONG (patched reading) | yes |
| noise-LV-MU-1 | 13.8 | 56/407 | 89 | WRONG (patched reading) | yes |
| noise-LV-MU-3 | 36.9 | 150/407 | 61 | WRONG (patched reading) | yes |
| kill-agent_p3 | 60.7 | 247/407 | 44 | TIMEOUT (hidden-scale, 15 s) | yes |
| kill-blind_9d66 | 72.5 | 295/407 | 32 | TIMEOUT (hidden-scale, 15 s) | yes |
| kill-blind_c60b | 72.5 | 295/407 | 32 | TIMEOUT (hidden-scale, 15 s) | yes |
| kill-blind_d576 | 60.7 | 247/407 | 44 | TIMEOUT (hidden-scale, 15 s) | yes |
| kill-ref_solve | 100.0 | 407/407 | 0 | - | yes |
| kill-s10_tierscan | 72.5 | 295/407 | 32 | TIMEOUT (hidden-scale, 15 s) | yes |
| kill-s11_tierbreak | 72.5 | 295/407 | 32 | TIMEOUT (hidden-scale, 15 s) | yes |
| kill-s12_tierrev | 72.5 | 295/407 | 32 | TIMEOUT (hidden-scale, 15 s) | yes |
| kill-s13_tiermax | 72.5 | 295/407 | 32 | TIMEOUT (hidden-scale, 15 s) | yes |
| kill-s1_probe | 60.7 | 247/407 | 44 | TIMEOUT (hidden-scale, 15 s) | yes |
| kill-s2_perline | 60.7 | 247/407 | 44 | TIMEOUT (hidden-scale, 15 s) | yes |
| kill-s3_label | 17.7 | 72/407 | 85 | WRONG | yes |
| kill-s4_endonly | 12.5 | 51/407 | 92 | WRONG | yes |
| kill-s5_greedy | 17.7 | 72/407 | 85 | WRONG | yes |
| kill-s6_naive | 60.7 | 247/407 | 44 | TIMEOUT (hidden-scale, 15 s) | yes |
| kill-s7_recursive | 60.7 | 247/407 | 44 | CRASH (long) / TIMEOUT (ladder) | yes |
| kill-s8_memo | 72.5 | 295/407 | 32 | TIMEOUT (hidden-scale, 15 s) | yes |
| kill-s9_plainwalk | 60.7 | 247/407 | 44 | TIMEOUT (hidden-scale, 15 s) | yes |
| probe-3 agent program (run 3 final) | 60.7 | 247/407 | 44 | TIMEOUT (hidden-scale, 15 s) | yes |
| first write (run 3 step 13, docs followed plainly) | 60.7 | 247/407 | 44 | TIMEOUT (hidden-scale, 15 s) | yes |

Lever share 160/407 = 39.3% (v3.6 band 25-40%); all-but-one 72.5, first write 60.7 (<= 75).

STACKING PASS
