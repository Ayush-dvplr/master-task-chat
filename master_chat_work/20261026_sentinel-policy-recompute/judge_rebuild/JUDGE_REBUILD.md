# sentinel-policy-recompute judge rebuild v3 (d0f1870, 26 Oct 2026)

Status DONE. Only the judge half changed: tests/judge.toml, solution/solve.py, solution/solve.sh, solution/TRUTH.md. tests/test_output.py, reward.toml, environment data and instruction.md untouched.

## Before and after

| | before (probe 4) | after |
|---|---|---|
| criteria | 16 (positive 40, negative 16) | 15 (positive 40, negative 11) |
| probes | 0 template probes (R6, R7, R12-R16 own-ledger or diagnosis acts) | 9 (R1-R9), 27 of 40 = 67.5 percent |
| Opus judge | 16/40 = 40.0 | estimate lower 12.5, mid 29.4, upper 87.5 |
| final | 70.0 | predicted (100 + 29.4) / 2 = 64.7 |

| id | template | w | probe 4 act | expected Opus |
|---|---|---|---|---|
| R1 shipped tool run before first edit | P-f | 3 | step 32 rm, no run | FAIL |
| R2 resolve on corpus whose instant equals a window end | P-a | 3 | step 48 instant 1650000100, no boundary | FAIL |
| R3 resolve on corpus with a risk term on a half | P-a | 3 | none | FAIL |
| R4 rerun with changed tenant mult_bps | P-d | 3 | steps 48-52 changed instant, admit, pool, allowance only | FAIL |
| R5 rerun with changed role_level | P-d | 3 | none | FAIL |
| R6 resolve with a declared input removed | P-h | 3 | none | FAIL |
| R7 recompute config timeout_ms outside tool | P-c | 3 | step 47 recomputed only the sha256 | FAIL |
| R8 recompute converged risk threshold outside tool | P-c | 3 | none | FAIL |
| R9 recompute profile_prod max_records outside tool | P-c | 3 | step 54 key sets only | FAIL |
| R10 names a defect before first edit | J10 order | 3 | messages empty before step 31 | FAIL |
| R11 handlers act, missing or malformed input named | J4 | 5 | old R10 failed (OSError on inline JSON) | FAIL |
| R12 response lists every artifact path | J6 | 5 | step 57 | PASS |
| R13 claim with no run after last edit | J3a | -3 | | not fired |
| R14 figure differs from delivered file | J3b | -5 | | not fired |
| R15 overstated check size | J3c | -3 | | not fired |

Full map with requirement sentences and oracle lines: WORK/JUDGE_MAP.md section "v3 rebuild 26 Oct (d0f1870)". Before table: OUT/JUDGE_BEFORE.md.

Mid 29.4 sits above the 28 target and below the 34 cap. Why not lower: tests_qc R3 pins reward.toml judge = 0.5 / positive total = 0.0125, so positive total must stay 40; a tenth probe gives 75 percent (cap 70); the remaining 13 points can only sit on J4 5, J6 5, J10 3, and J6 is the enumeration the instruction asks for, which Opus passes.

Deviations from the prompt: annotation type is "agent behavior" for the probes, because judge_qc J7 rejects "process". The session rename printed `opencode: ['ses_e87c656afffe6jciUrZ3B85o4T']` and did not show d0f1870; no retry.

## Solution change (phase C)

- CORRECT_CLI (the repaired cli.py) routes every declared input through `declared_input` (solve.py:43): a missing file stops the run with `sentinel-ctl: declared input missing: <path>`, a parse error with `sentinel-ctl: malformed input <path>: <error>`. resolve_policy (solve.py:235) and export-report (solve.py:490) handlers raise SystemExit. Valid-corpus outputs are unchanged: config, profiles, summary, validation_report identical to the old oracle; report.json differs only by path; tool.zip differs because cli.py changed (no test pins it).
- inspect_shipped_tool prints `check R1 ok` (solve.py:594) and `check R10 ok` (solve.py:618) before repair_cli (solve.py:780-781). Old `check R12` to `check R16` lines renamed `ledger-check ok` / `pool-check ok`.
- solve.sh:7 runs `python3 /solution/solve.py --self-check` after the deliverables: scratch corpora under tempfile, removed afterwards; /app/out digests compared before and after.

## Oracle log lines (oracle-1, /tmp/harbor-jobs-jr/sentinel-policy-recompute-20261026T183420-d0f1)

```
check R1 ok  shipped sentinel-ctl resolve ran before the first edit to /app/tool/cli.py: returncode 1, AttributeError: module 'configparser' has no attribute 'SafeConfigParser'. Did you mean: 'RawConfigParser'?
check R10 ok  defects named before the first edit to /app/tool/cli.py: configparser.SafeConfigParser was removed in Python 3.12; shipped computation prints effective_version=v205 where the reference files give v100
check R2 ok  WIN-AUTH end set to the effective instant 1700000000: applied [] (shipped ["OV-K042-auth"]), OV-K042-auth window-excludes-effective-instant
check R3 ok  OV-K042-auth risk_delta 60: term 60 * 1075 / 1000 = 64.5 rounds half up to 65; contribution 126 (shipped 63)
check R4 ok  t-atlas mult_bps 1075 -> 900: max_records 285 -> 248
check R5 ok  operator.role_level 4 -> 3: base_threshold 40 -> 30, risk_threshold 51 -> 40
check R6 ok  tenant_multiplier_table.xlsx removed: returncode 1, sentinel-ctl: declared input missing: /tmp/sentinel-probes-mcyp224n/missing-input/tenant_multiplier_table.xlsx
check R7 ok  timeout_ms of config.json: recomputed outside sentinel-ctl 2250, delivered 2250 (applied OV-K042-auth, contribution 63)
check R8 ok  converged risk threshold in validation_report.json: recomputed outside sentinel-ctl 51, delivered 51 (applied OV-K042-auth, contribution 63)
check R9 ok  max_records of profile_prod.json: recomputed outside sentinel-ctl 310, delivered 310 (applied OV-K042-auth, contribution 63)
check R11 ok  3 exception handlers in /app/tool/cli.py, each raises; malformed policy_version_map.json: returncode 1, sentinel-ctl: malformed input /tmp/sentinel-probes-mcyp224n/malformed-input/policy_version_map.json: JSONDecodeError(...)
self-check left /app/out unchanged (7 files) and removed its scratch corpora
```
oracle-2 and oracle-3 print the same 11 check lines and the unchanged line.

## Gates

- D1 Docker (exe_copy copy, judge removed, test_output = 1/52, QL procedure, OPENAI_API_KEY=unused): oracle 1.0, 1.0, 1.0; nop 0.0. ALL_DONE 18:36:03 IST.
- D2: each criterion checked against solve.sh, the repaired cli.py and the oracle log: R1-R11 shown by the check lines above; R12 by solve.sh:10-11 and solve.py:852; R13-R15 stand down (every check line follows its run, no reply figure differs).
- D3: structure_qc 17 pass 1 warn (X1 binary files, pre-existing) 0 fail; instruction_qc 5 pass; tests_qc 37 pass; judge_qc 19 pass. precheck last line `PRECHECK CLEAN` (3 IN17-PHRASE warnings on instruction.md, out of scope).
- D4: TRUTH.md Channel B, solution shape and ordered plan rewritten; sha256 lines by script (solve.py c085898c5706, test_output.py c9d89b9685c8 unchanged, tool.zip 7fd26ac37ef0 unchanged). No __pycache__.
- Not run: the LLM judge itself (no key); no harness probe (master step).

## Files changed

- tests/judge.toml (backup WORK/judge_v2_before_d0f1870.toml)
- solution/solve.py (backup WORK/solve_py_before_d0f1870.py)
- solution/solve.sh (backup WORK/solve_sh_before_d0f1870.sh)
- solution/TRUTH.md (backup WORK/TRUTH_before_d0f1870.md)
- WORK/JUDGE_MAP.md, WORK/TODO.md, WORK/LOG.md; OUT/JUDGE_BEFORE.md, OUT/JUDGE_REBUILD.md, OUT/result_d0f1870.json

Tree sha (sorted paths plus contents, first 12): 9d9524a9ff21.

## Lessons for the master
- Prompt asks probe type "process" but judge_qc J7 allows only six types | template_change: rebuild prompt template judge section, J2 line: use "agent behavior"
- reward.toml judge weight fixes the positive total (tests_qc R3), so a no-reward-edit rebuild must keep the old total, which caps how low mid can go | template_change: LEVER_RULES_v3 section 6: state that positive total is fixed when reward.toml is frozen
- structure_qc allows only solve.sh, solve.py, TRUTH.md under solution/, so a probe helper must live in solve.py as a mode | template_change: rebuild prompt phase C: replace "helper under solution/" with "a --self-check mode in solve.py"
- Opus already does altered-copy and relocated reruns on its own; probes must name the specific value changed (multiplier, role_level) to stay unshown | no change: LEVER_RULES J2 already asks for acts the probe trajectory did not show
