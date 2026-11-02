# B: project-schedule-feasibility (PARTLY; tests 98.77, rubric 40.00)

## 1. Inventory
- **Domain:** resource-constrained project scheduling (serial SGS, calendar of working days, lags, total float, critical set).
- **Archetype:** a reusable program, `/app/out/derive_report.py DATA_DIR OUT_DIR`, plus 10 JSON reports from the shipped extract.
- **Files the agent sees** (`environment/data`):

  | File | Size |
  |---|---|
  | `schema.md` | 8973 B, 158 lines: the full rule contract |
  | `baseline_report.json` | 8024 B: decoy prior schedule, "known to disagree" |
  | `calendar.csv` | 3274 B |
  | `tasks.csv` | 1240 B |
  | `precedence.csv` | 489 B |
  | `crew_roster.csv` | 110 B |
  | `capacities.json` | 61 B |
  | `config.json` | 58 B |
  | `priority.json` | 47 B |
  | `phase_map.json` | 47 B |

  No shipped file has a BOM, CRLF line endings or extra columns.
- **Instruction:** 417 words (`instruction.md`, 41 lines).
- **Tests:** 29 positives totalling 81, plus 5 negatives (hardcoded -5, missing_sections -3, reads_tests -5, external_dependency -3, copies_faulty_baseline -5). Weights are at `tests/test_output.py` L1165-1199.
  - 8 checks (18 points) compare whole artifacts on the shipped extract.
  - The other 63 points come from the program run on regenerated corpora: relabelled, ssgs, float, infeasible, cycle, undeclared, calendar_edge, unused, 4 BOM variants, CRLF, trailing_field, and the eval/challenge/boundary generator seeds (L544-561).
  - Most checks are isolated views, such as `_schedule_rows` or `_float_view` (L787-830), rather than whole documents.
- **Hidden inputs:** yes. They come from an in-test deterministic generator, `write_case(root, seed, n)` (L342), with seeds L34-44, and from hand-built fixtures `*_TASKS`/`*_PREC`. Expected values come from `reference()` (L385), computed at test time.
- **Judge:** 18 criteria (17 positive totalling 35, plus r10 at -5), batched, `openai/gpt-5.6-sol`, ATIF trajectory.
- **Reward split:** `reward.toml` gives 0.5 to tests (1/81 per point) and 0.5 to the judge (1/70 per point = 0.5/35).

## 2. Rule map (graded rules)
Every scheduling rule is one plain numbered sentence in `schema.md` L73-103. The instruction (L9-10) says only "follow the serial scheduling, tie-breaking and float rules the contract spells out".

| Rule | Where stated | Form | Trap explained? | Shipped case separates readings? |
|---|---|---|---|---|
| Kahn's sort, smallest ready id; cycle means downstream tasks unscheduled | schema.md:73-76 | one sentence | yes (states the consequence) | INFERRED no cycle in shipped data |
| Window skips non-working days | :77-79 | one sentence | yes | yes (calendar has weekends) |
| Earliest start: unscheduled predecessor imposes no constraint; no working day left means number of rows | :80-83 | default + exception, both stated | yes | not in shipped data |
| SGS key `(rank, earliest start, task_id)`, capacity on every window day | :84-90 | one sentence | yes | INFERRED partly |
| Infeasible conditions (undeclared crew, units > capacity, duration <= 0, window past last row); missing class ranks last | :32-37 | list in file description | yes | partly |
| Unknown-id edge rows ignored but counted | :43-44 | one sentence | yes | INFERRED no |
| Lag = `(lag+1)`-th working day after finish | :41-43 | definition | yes | yes |
| Float backward pass anchored on RC makespan, no capacity recheck | :93-100 | one sentence + negation | yes (the trap is named) | yes |
| Declared crew with no tasks keeps `crew_type`/capacity; undeclared means null/0 | :143-149 | default + exception | yes | INFERRED no |
| Ratios round half up; utilisation bps formula | :103, :141-142 | one sentence | yes | yes |
| Files are UTF-8, CSV keyed by header | :13-14 | one sentence, scope by omission (BOM, CRLF and trailing fields never named) | no | no (no shipped file has a BOM) |

Every rule except the encoding-robustness group is written exactly as one plain sentence, with its trap stated. This is the same style as our leaked cohort levers.

## 3. Lever table (failed checks and criteria)

| id | w | Rule graded | Agent reading (evidence) | Correct reading | Mechanism | Self-test on shipped data catches it? | Fully stated? | Family |
|---|---|---|---|---|---|---|---|---|
| test_bom_rule_tables_are_echoed | 1 | JSON rule tables may carry a UTF-8 BOM | agent `derive_report.py` L28-35: `read_json` opens with `encoding="utf-8"`, while `read_csv_rows` uses `utf-8-sig` | read every file BOM-tolerant | inconsistent defensive handling: the agent guarded CSV but not JSON | N (no shipped file has a BOM) | borderline: only "UTF-8 encoded text" (schema.md:13); BOM never named, so **near-HIDDEN, RISKY** | F error path / input robustness |
| judge r6 | 3 | run a constructed same-rank capacity tie | steps 13 and 15 corpora contain no same-rank tie | construct and run one | conduct criterion naming a specific edge case | n/a | yes, as a judge criterion (not visible to agent) | NEW: named self-test conduct |
| judge r12 | 3 | rerun on a perturbed copy (shuffle/CRLF/BOM) | none | run one | same | n/a | same | same |
| judge r13 | 3 | checksums of /app/data before the first run and after the last | none (step 14 diff compares outputs only) | checksum | preference criterion (JD-15 step 2) | n/a | same | same |
| judge r15 | 3 | run a relabelled copy | none | run one | same | n/a | same | same |
| judge r16 | 3 | run a case with a non-working first row | step 15 tc2 has a single non-working row but **no tasks**, so the "first start_index" check is impossible | first row non-working, tasks present | same | n/a | same | same |
| judge r17 | 3 | successor past the last working day becomes unscheduled | none | run one | same | n/a | same | same |
| judge r18 | 3 | duplicate edges with different lags, larger wins | none | run one | same | n/a | same | same |

## 4. Contrast: what the agent passed and why it was easy
The agent passed all value checks on 19 corpora: all 16 hidden fixtures, the 3 seeds, the relabelled corpus, CRLF, trailing-field and the 3 BOM-CSV checks. They were easy for three reasons:
- Each rule is a single numbered sentence that names its edge case ("An unscheduled predecessor imposes no constraint", schema.md:81-82; "does not re-check capacity", :100).
- The rules come in application order.
- The decoy (`baseline_report.json`) is labelled as wrong in both files.

This matches our cohort DIAGNOSIS cause 4 exactly (one plain sentence per rule, trap stated, decoy refuted on the same page). Hidden generators do not help when the rule is unambiguous: the agent's first write (step 7) generalised to every seed. **Lesson:** hidden reseeded corpora carry no difficulty on their own. They only pay out when a rule has a reading that the shipped data does not separate.

## 5. Agent behaviour
- **Steps 2-6:** ls/wc (step 2 observation null), full `schema.md` (step 3), all small files (step 4), baseline head/keys (steps 5-6). It read every spec file fully.
- **Steps 7-9:** a 450-line program in one write (step 7), one edit (step 8), and a run on shipped data (step 9). There was no written plan beyond the reasoning.
- **Self-tests:**
  - step 10: an independent recheck of placements against the calendar
  - step 11: rollup arithmetic
  - step 13: corpus TC-1 (unknown crew, cycle, ghost predecessor, unknown class, zero duration, overflow, rank order)
  - step 14: chmod 644, byte-compared rerun, float grep
  - step 15: trailing newline check and an empty corpus
  - steps 16-18: an attempted unprivileged run that hung and was abandoned
- **Final claim** (step 21): "Done. I read the contract...". That matches the reality for values (98.77). The agent did not claim BOM robustness.
- 22 steps, about 5.5 min. The agent stopped early, using about 4.5% of its budget. Spending more effort on self-tests would have earned judge points.

## 6. Test design
- Expected values come from the in-test `reference()` (L385), run on fixtures and seeded generator corpora built at test time. There is no fixed answer file.
- Partial credit comes from views: start/finish, float/critical, makespan/counts, policy/data-quality, region and segment are checked separately per corpus set. One error therefore costs only the views it touches, not the whole document.
- Negatives: `copies_faulty_baseline` -5 (anti-decoy), hardcoded -5, reads_tests -5, external_dependency -3, missing_sections -3.
- Share of weight on shipped-data-only checks: 18/81 = 22%.
- Robustness checks (BOM x4, CRLF, trailing fields) total 12 points for behaviour the spec never names. That is TS-19 RISKY (only "UTF-8" and "keyed by its header row" support it).

## 7. Judge design
- **Failed:** 7 w3 conduct criteria, each naming one constructed edge case (r6, r12-r18).
- **Reusable pattern (SAFE when written well):** "runs its program on an extract it constructed in which <the separating case for rule X>, and checks <observable>". It rewards building exactly the case the shipped data lacks, so it pays out the self-test gap that a test cannot reach. r14 (infeasible predecessor) is the template. The agent passed it because its own corpus happened to include that case.
- **QC concerns:**
  - **r13:** "before its first program run" is a preference. JD-15 (`04_Judge_QC.md:92`), step 2, requires removing it, so it is RISKY/fail.
  - **JD-7** (`04:76`): "Every criterion must be satisfied ... by the shipped oracle in solution/". `solve.sh` has no trajectory of self-tests, which is RISKY for all conduct criteria (INFERRED).
  - **JD-8** (`04:77`): no observable overlap, because the judge grades the act and the tests grade the values. Pass.
  - **JD-18** (`04:99`): r8 is the code-quality criterion (descriptive names). Pass.
  - Weighting: 7 of 9 w3 criteria are "ran a specific test case". That is a heavy conduct share (21/35 of judge points), and a fully correct program can still score 40 on the judge.

## 8. QC safety

| Lever | IN-15 | TS-16 | TS-19 | TS-20 | AL-28 | Verdict |
|---|---|---|---|---|---|---|
| BOM on JSON rule table (w1) | "UTF-8 encoded text" only, BOM never named: weak | n/a | RISKY: not learnable from the spec | w1 fits minor | n/a | **RISKY**. It becomes SAFE if the spec says inputs may carry a byte-order mark and CRLF line endings, without saying which files. |
| Named-edge-case conduct criteria (r6, r12, r14-r18) | judge-only, fine | n/a | n/a | w3 = sub-goal | no stacking | **SAFE** (odds-raising per JD-15), with a JD-7 note |
| r13 checksum-before-first-run | n/a | n/a | n/a | n/a | n/a | **NOT ALLOWED** (preference) |
| Anti-decoy negative `copies_faulty_baseline` -5 | stated (schema.md:157-158) | fires only on copying: SAFE | n/a | n/a | single -5 | **SAFE** (did not fire) |

## 9. Writing style (how the rules are stated)
1. "An unscheduled predecessor imposes no constraint." (schema.md:81-82). The exception sits inside the rule, with the trap named. It is easy to solve, and the pattern to AVOID.
2. "The backward pass is anchored on this resource-constrained makespan and does not re-check capacity." (:99-100). This is a negation that kills the obvious CPM reflex. It leaked.
3. "Every file is UTF-8 encoded text, and each CSV file is keyed by its header row." (:13-14). This is scope by omission: robustness to a BOM, CRLF and column reordering is implied by "keyed by its header row". The agent caught the CSV half and missed the JSON half. This is the only statement in the task that cost a test point.
4. "a single misplaced rule shifts the schedule and flips the critical set across the whole report" (instruction.md:30-31). This warns of a dependent chain but did not create one, because no rule had two readings.
