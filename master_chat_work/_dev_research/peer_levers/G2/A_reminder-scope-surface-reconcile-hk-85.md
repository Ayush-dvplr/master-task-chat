# A: reminder-scope-surface-reconcile-hk-85 (73.23 / 90.53 / 55.93)

Verdict: **PARTLY**. The 9 test points are genuine code bugs. The 26 judge points are lost on process criteria, and the instruction asks for none of those processes.

Paths: TASK = `.../Abdus Samad Ali/reminder-scope-surface-reconcile-hk-85/`, RUN = `TASK/trajectories/claude-opus-5/run_1/`.

## 1. Harness health
- `RUN/result.json`: `exception_info` None. The agent ran 12:42:42 to 12:53:40Z (about 11 min, 37 steps, cost $2.84). The verifier ran 12:53:49 to 12:55:12Z. No timeout and no step limit (MAX_ITERATIONS 350).
- `RUN/verifier/test-stdout.txt` is 15 bytes, just `reward: 0.7323`. It shows no traceback, no Errno 13, no collection error. `ctrf.json` lists 35 tests with no failure messages.
- Permissions: `tests/test.sh` does `chown root:root /logs/verifier; chmod 755 /logs/verifier; chmod -R go-rwx /tests`, then runs rewardkit. `test_output.py` `_launch` (L513-543) runs agent code through `setpriv` as an unprivileged uid. `_run_unlocked` (L546-599) first copies the program into a fresh 0644 directory, and the comment at L571-573 says why: "The agent may deliver its program with mode 0600 and the run is unprivileged, so the program ... copied into a fresh directory that the unprivileged user can read". **This explicitly fixes the permission bug that hit our cohort v0.** The agent's outputs were also 0644 (traj step 31 `ls -la out`).

## 2. Did the verifier run the agent's program? Wrong value or artefact?
Yes. The verifier ran it on 13 re-generated variant inputs (generator in test_output.py L442-510). 28 of 31 positive checks passed, including the reproducer checks on the shipped evidence and on most variants, so the program ran under the harness. All 3 failures are bugs in the agent's code, each confirmed by reading the delivered `artifacts/app/out/reproduce_scopes.py`:

| failed check (w) | variant (test_output.py) | agent code | outcome |
|---|---|---|---|
| reproducer_workbook_phonetic_runs (3) | L162: each shared string has `<rPh><t>ヨミ</t></rPh>` after its text | L133-135 joins `item.iter(t)`, every `<t>` including the phonetic one | wrong text in the canonical map, so wrong `active_scopes` (GENUINE) |
| reproducer_absolute_workbook_targets (3) | L156: rels Target is `/xl/worksheets/sheetN.xml` | L143-145 `if not target.startswith("xl/"): target = "xl/" + target.lstrip("/")` gives `xl/xl/worksheets/...` | KeyError, program crashes on this variant, check gets None (GENUINE: the agent tried to handle absolute targets and got it wrong) |
| reproducer_journal_column_case (3) | L82: sqlite columns `c.title()` (e.g. `Line_No`) | L109-114 `SELECT *`, then a dict keyed by `cursor.description`, then `row["line_no"]` | KeyError crash (GENUINE) |

The shipped data contains none of these three cases. The shipped rels Target is relative (`worksheets/sheet1.xml`), sharedStrings has 0 `rPh`, and the sqlite schema is lower case (my `unzip -p` / `sqlite3 .schema`, 07:55 IST).

## 3. Near-zero tests?
No. Tests scored 90.53. No single gate zeroes the score: `_check_variant` (L664-668) compares only the fields in each variant's `VARIANT_FIELDS`, and `_grade` (L680) turns any exception into False for that one check.

## 4. Judge
`judge.toml` uses `mode = "batched"` and reads the trajectory. It has 33 criteria. The 59 positive points are R1-R19 at weight 1 and R20-R27 at weight 5. The negative criteria are R28-R33, and none fired. The judge read the final message: R7, R11-R16 and R18 are final-message criteria that quote artefact values, and they passed (INFERRED from passed=True).

Failed criteria and whether each traces to the contract:
| R | w | what it demands | stated in instruction or policy? | classification (04_Judge_QC JD-15) |
|---|---|---|---|---|
| R19 | 1 | trajectory "shows that control_01 alone is fitted by every window from 3 through 9 and that control_02 narrows the fitting window to 6" | no. The policy (L215-223) defines fitting but asks for no per-control report | outcome with no contract sentence: NOT ALLOWED |
| R20 | 5 | regenerate published_controls.psv from parameters of its own choosing, rerun, check against the tie rule | no | conduct, odds-raising at weight 5: minor |
| R23 | 5 | "reports, for each calibration control in file order, the count of window candidates and the count of weight candidates that still fit" | no. The final-message list (instruction L11) has no such item | outcome/report not in the contract: NOT ALLOWED |
| R24 | 5 | replays control_03 on its own and compares with the published values | no | conduct verification, w5: minor |
| R25 | 5 | builds an extra calibration control from chosen parameters and checks it recovers them | no | conduct, odds-raising, w5: minor |
| R26 | 5 | lists every window and weight vector that fits all controls before applying the tie rule | no | conduct (a derivation method), w5: minor |

The agent really did not do these. Its self-tests (traj steps 28-30) were a minimal evidence directory, an A1-only addendum run and a ledger value mutation. It never enumerated candidates per control and never built a control. So the judge loss is real behaviour, but it is graded against unstated procedures. JD-7 cannot be checked against solve.py for trajectory criteria (INFERRED: the oracle is a script with no trajectory).

## 5. Permission setup
Robust. See section 1: the verifier copies the program to 0644 and runs it unprivileged, and /tests is closed to group and other.

## Points
- Tests: 9/95 lost, all genuine. They are format-robustness variants that the shipped data does not show.
- Judge: 26/59 lost. All 26 are on criteria with no contract sentence: 6 points on outcome items that are not in the instruction (R19 1 + R23 5) plus 20 points on conduct items scored at weight 5 (R20, R24, R25, R26). Treat them as a rubric-design effect, not a task lever.
