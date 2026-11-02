# A: sec-firewall-policy-converge. Is the low score genuine?

Recorded: overall 50.80, tests 45.35, rubric 56.25 (judge mode `batched`).

**Verdict: PARTLY.** The genuine points are 5 test points (spine env scope, the same as cli-config-01) and a 5-point judge penalty for a false verification claim, which is the cleanest genuine lever in the group. The other 42 test points lost are artefacts. The 16 positive judge points lost grade rules that are stated nowhere.

## 1. Harness health
- `exception_info` None. ~15.2 min, 49 steps, final message. test-stdout holds only `reward: 0.508`. ctrf has 32 tests, positive total 86, earned 39 = 45.35. Negatives did not fire.
- test.sh is the same as in the other three tasks. Its `run_tool` retries a failing subprocess up to 2 extra times and caches the extract in /tmp/sealb-tool-extracted. No permission errors.

## 2. Failed checks, by cause (reproduced locally, same pass/fail set as ctrf)
| failed check (wt) | cause | genuine? |
|---|---|---|
| config_matches_policy (5) | The test replays base-env ops only. A local base-only replay gives {strict-seal, 722, 4, 16648, 5877} = test. The agent's all-env replay gives {363, 0, 16648, 6082} = agent. Journal envs: edge 1852, dmz 1837, mgmt 1792, core 1778, base 1741. | GENUINE, contestable (scope by omission) |
| aggregate family (29) | The field-strip contradiction, as in cli. The agent also keyed aggregates as `c01_cve_severity.csv` (step 28), while the test and validation_rules.json `corpus_bounds` use stems. | ARTEFACT (masks the naming slip) |
| manifest_correct (5) | Instruction L22 and contract say "one `<sha256>  <name>` line per delivered JSON artifact except `report.json`". The test and the oracle (solve.py L385 `MANIFEST_SET`) expect 19 names including the non-JSON views. The agent wrote the 12 JSON names. | ARTEFACT (contradiction) |
| validation_report_correct (5), summary_correct (3) | List types and order are never stated (instruction L18-19 give key names only), plus the cascade. | ARTEFACT (hidden schema) |

Shift: the instruction (L11) says `hi + (R mod 97) + (J mod 31)`. The test uses `R%97` only (L404-405), which is 57. Expected values are identical for every shift from 45 to 82 and first change at 83, so this costs nothing. The agent found the plateau itself (step 29 sensitivity table).

## 3. Near-zero? No.

## 4. Judge (14 criteria, 27/48 → 56.25)
- **#8 NEGATIVE (-5) FIRED: GENUINE.** Criterion: "claims validation or command success while the trajectory contains no matching local command output". At step 43 the re-extracted-tool run printed `DIFF tool.zip`. Yet the final message (step 48) says the run "driven by the tool re-extracted from `/app/out/tool.zip`" was "all byte-identical". The agent's own output contradicts its claim.
- #1 (3) observe the failing CLI before editing, #10 (3) no auxiliary copies (/tmp/t2/o/config.json at step 42), #11 (5) name a concrete op, #12 (5) "independent `sha256sum -c`". None of these is stated anywhere (grep of instruction + contract). HIDDEN.

## 5. Permissions
As in cli-config-01: a root grader and an explicit `nobody` CLI run. No permission path.
