# RECHECK_FIX depot-charge-plan, P12 fix v2 (board 0d6348c)

QC report: `QC/reports/depot-charge-plan/v1.md`. Kit HEAD 5574d77e. Bundle tree before 7e3ade15a78b (after efdb667's DS-21 fix, kept as is).
Digests: `WORK/fix2/digest_before.txt` vs `digest_after.txt` (Docker, ALL_DONE rc 0); G7 diffs `WORK/fix2/g7_*.diff`.

## G4 rows

| id | touched how | rules re-checked | verdict |
|---|---|---|---|
| shipped_policy_audit_exact, shipped_summary_exact, shipped_data_quality_exact, shipped_segment_public_exact, shipped_region_east_exact | expected bytes changed (shipped derating binds, 3 two-fault roster rows); body reads /app/out under the shared lock | TS-13, TS-14, TS-20, TS-25, TS-26, CL-2, CL-4, CL-3 | PASS: same names, weights, one document each; shipped plan now differs from published_plan.csv in all four depots (buses_changed 28: East 24, North 1, South 1, West 2) |
| fresh_h1..h4_summary_exact, fresh_h1/h3_data_quality_exact | expected bytes changed (records_rejected and data_quality rows from the new two-fault rows) | TS-13, TS-14, TS-26, AL-27 | PASS: policy, region and segment expectations of h1..h4 byte-identical (30 untouched checks identical) |
| relocated_fresh_summary_exact (was relocated_copy_summary_exact) | own seed 47713, placed under base/archive/2026/inputs, run from base/cwd; weight 3 kept | TS-13, TS-14, TS-20, TS-25, TS-26, CL-2 | PASS: expected b85c38925b3b differs from fresh_h3_summary_exact 4ec2b5f3f922; observes a folder no other check grades |
| default_paths_run_summary_exact (new, w3) | flagless run `python3 /app/out/derive_report.py` on seed 55109 placed at /app/data; /app/out restored byte for byte after | TS-12, TS-13, TS-14, TS-25, TS-26, CL-2, AL-2 | PASS: earned output, own seed; nop fails (no program) |
| negative_run_writes_outside_output_folder (new, -1) | holds when the flagless run creates files of the run user outside /app/out | TS-12, TS-14, TS-15, TS-16, TS-25, AL-2 | PASS: absence check kept on the negative side; oracle writes only into --out |
| malformed_tariff_stops_naming_file (new, w3) | shipped data with tariff.xml cut halfway; rc != 0 and stderr names tariff.xml | TS-13, TS-14, TS-25, JD-5, JD-8 | PASS: rule 22 "cannot be read as these rules describe"; oracle guarded() raises InputError naming the file |
| r9_exception_handling | handler clause only; input behaviour moved to the two tests | JD-2, JD-5, JD-7, JD-8, JD-9, JD-13, JD-15, JD-18, IN-8 | PASS: one act, code quality (conduct, JD-15/JD-18 kept), oracle solve.py:48,65,72,81,83 shows it |
| r16_changes_data_folder | unchanged text and weight (the end-state test was tried and withdrawn: validator 1.12 fixes task.toml artifacts to the archetype manifest, so /app/data cannot reach the separate verifier) | JD-2, JD-7, JD-15, JD-16, AL-28 | PASS: quotes instruction.md:19; JD-16 stays a recorded warn |
| r17_reports_summary_totals (new, w3) | final answer gives the eight summary.json totals | JD-2, JD-5, JD-6, JD-7, JD-9, JD-13, IN-8, AL-2 | PASS: instruction.md:23; R13 (-5) penalises a differing figure, R17 rewards the listing (pair, not double pay) |
| rule 13 sentence (charging_rules.md:28) | "A row whose `bus_id` is not a bus on the plan is ignored and is not rejected." | DS-20, IN-17, DS-21 | PASS: matches oracle read_published skip; hidden fixture row for retired[0] exercises it; no trap word |
| rule 4 order fixtures | 3 rows meet two conditions at once (unknown+bad window, retired+bad window, duplicate+bad window), shipped and hidden | AL-27, DS-20, IN-17 | PASS: shipped lines 2434, 2497, 4329; every hidden tree has unknown 2, retired 2, duplicate 2 |

## FIX_SIDE_EFFECTS rows
- JD-5 -> JD-2 (positive grammar: R9/R16/R17 carry no banned token), JD-7 (oracle shows R9 and R17, avoids R16), JD-9 (R9 still a state of the code, probes untouched), JD-15 (R16 labelled instruction following, R9 conduct), IN-8 (malformed tariff behaviour stated in rule 22).
- TS-26 -> TS-14 (renamed check so the name states its own folder).
- AL-2 -> TS-25 (write-scope check registered negative, not positive).
- AL-27 -> TS-13 (each data_quality check still one document).
- CL-3 -> DS-21 (shipped notice derating stated in disruption_notice.md:10; rule 11 replaces the feeder limit in derated slots).
