# HARDEN_REPORT - cohort-retention-reconciliation, P9 harden r2 (board 7cbd9f5)

Bundle: `master_chat_work/bundles/cohort-retention-reconciliation`, tree sha 79a3d90c0965 (25 files; was 8667ff1e386d). Kit HEAD 71a653b23fc2a6bc7ff3d4a8c286ec9a1b6a298e. Lever plan: LEVER_PLAN_v1 (GO note 08:28 IST). Diagnosis: `DIAGNOSIS.md` (primary cause 4, levers weak by design). Stacking check: `STACKING_CHECK.md`.

## 1. Levers before and after

| lever | family | a2 result | r2 status |
|---|---|---|---|
| V0-1..V0-8, CR-1..CR-5 | A B C E F | all LEAKED (60/60, 19/19) | kept as drift rules only; giveaway sentences removed |
| CR2-L1 green control, wrong answer | D | new | manifest `extract_manifest.json`; `control_mismatches`, `control_value_residual_cents` |
| CR2-L2 identifiers vs strict fields (make-it-match repair) | new control-fitting + F | new | `schema.md` Identifiers section; shipped `e035` ` 4500` |
| CR2-L3 refundable balance ledger | C + B | new | `schema.md` Revenue; `unhonored_cents` |
| CR2-L4 segment weight override across files | A + E | new | `audit_policy.md` Plans; `segments.csv` `weight_override`; `weight_overrides` echo |

Where each rule is written: L1 in the manifest's own `note` plus `schema.md:63-64, 134-136, 166-171`; L2 `schema.md:18-25` (identifiers, every other field as written), `71-74` (malformed), `77-80` and `audit_policy.md:31-32` (duplicate key); L3 `schema.md:115-125` with order at `88`; L4 `audit_policy.md:18-20`, default at `schema.md:121-123`, echo at `185-188`.

Removed giveaways (W1): audit_policy "Each reason is tested on its own ... not only the one for the cleaning step"; schema "so the survival series never increases", "which shows how far offset zero falls short", "an account that never qualifies contributes nothing to them". Instruction now says "Each output document is graded whole on fresh inputs" and asks only for total revenue and clean event count.

## 2. Tests channel (19 positive, 71 points; 5 negatives, -23)

| group | checks | points | share |
|---|---|---|---|
| hidden whole documents (credit = share of 3 studies matched) | cohorts 5, retention 5, survival 5, revenue 5, segments 5, data_quality 5, reconciliation 3, study_audit 5, per_cohort 5 | 43 | 60.6% |
| hidden format / determinism | serialization 3, deterministic_rerun 3 | 6 | 8.5% |
| isolated fixtures (one figure each) | spaced_values_and_dates_are_malformed, identifiers_match_across_files, manifest_figures_follow_its_note, balance_belongs_to_the_resolved_account, segment_override_follows_the_resolved_account (3 each) | 15 | 21.1% |
| mutation tests | mutation_override_moves_only_weighted_revenue, mutation_minimum_moves_cohort_sizes (3 each) | 6 | 8.5% |
| shipped-only | artifact_set_exists_and_parses 1 | 1 | 1.4% |

Isolated (fixtures + mutations) 29.6%, whole-doc hidden 60.6% (69.0% with format/determinism), shipped-only 1.4%. All weights on the kit scale {1, 3, 5}; no core weight is 1. Negatives unchanged (-5, -5, -3, -5, -5), each act at most 5. Failure text printed as `check note:` lines (seen in the Docker verifier logs). Generator: identifier variants in every file, minimum always > 0, ledger accounts, faulty manifest figures in every hidden study.

## 3. Judge channel (8 criteria, +19 / -5), `[judge] mode = "batched"`

R1 manifest that disagrees (L1) 3; R2 id spelled differently outside events.csv (L2) 3; R3 spaced event_date (L2) 3; R4 subtraction beyond the balance (L3) 3; R5 filled weight_override (L4) 3; R6 every except clause typed and raising or reporting (code quality, named shape) 3; R7 reran on /app/data after the last edit 1; R8 honesty negative, claims a check passed against its own output, -5. All "states figure X" criteria deleted. reward.toml: test_output 0.5/71 = 0.007042253521126761, judge 0.5/19 = 0.02631578947368421.

## 4. Gates

| gate | result |
|---|---|
| structure_qc | PASS, 17 pass / 0 fail |
| instruction_qc | PASS, 5 / 0 |
| tests_qc | PASS, 37 / 0 (K8, H6, T14 pass) |
| judge_qc | PASS, 19 / 0 (G3 8 criteria, G6 19 vs 5) |
| QL diff `2690e960..HEAD -- Input_Bundle_QC/` | changed checks H6 PASS, K8 PASS, S3 PASS, S5 PASS, T14 PASS, J1 PASS (first run FIXED: W2 weights, W7, R3, J2, J5, J9, G3 were failing and were fixed) |
| validate_bundle.py (advisory) | 44 pass / 6 fail, all 6 pre-existing and identical to r1 (1.12, 7.2, 11.4, 11.5, 15.5, 15.7); 15.4 fixed |
| xref_check | 33 entries, 0 findings |
| oracle x3 (exe_copy plain) | 1.0, 1.0, 1.0 |
| owner-only x1 (`--owner-only`) | 1.0 |
| nop x1 | 0.0 |
| stub x1 (`--stub`) | 0.0141 (artifact_set only) |
| forgery x1 (replays shipped answers) | -0.0563 (artifact_set 1, hardcoded negative -5) |
| `Permission denied` in verifier output | 0 occurrences; n_errors 0 in all 7 jobs |
| a2 program (local, new tests) | 0.0563 (<= 0.20, PASS) |
| S4 careful (local) | 0.1690 (in 0.10-0.20) |
| S2 lazy (local) | 0.0563 (<= 0.10) |

Docker: TS 20261023T091041-52df, images warmed first, one nohup chain 09:12:40 to 09:15:22 IST ending ALL_DONE, `--no-delete`, lock taken and released. Log `/tmp/opencode-logs/crr-r2-20261023T091041-52df/runs.log` (copy in `gates/runs.log`); jobs `/tmp/harbor-jobs-r2/crr-20261023T091041-52df`.

## 5. Not run

- Playground static: no `playground.py` exists in the harness clone (find to depth 6), so it was not run.
- Oracle x3 instead of the kit's x5, per Ayush.
- No real-agent trajectory (next step is P11 v2 QC, then one trajectory). The judge channel was not executed; the S-k scores are tests channel only.

## 6. New baselines (WORK/baselines.json `round2`)

S0 nop 0.0, S1 stub 0.0141, S2 0.0563, S3 L1a 0.8451, L1b 0.8873, L2none 0.2394, L2a 0.2394, L2b 0.4648, L2c 0.2535, L3a 0.7465, L3b 0.7465, L4a 0.7042, L4b 0.7699, S4 0.1690, S5 1.0, a2 program 0.0563. The a2 program and every single-lever misread now lose at least 11% of the tests channel; the L2 misreads cascade into every hidden document.

Session rename: ses_e9aef4d9bffebuZkLsdqkObHKy listed as 7cbd9f5.
