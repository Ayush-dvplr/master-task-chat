# A_7e0d8feb — Step 1: is the loss genuine?

Recorded: final 63.56 / tests 94.12 / rubric 33.01. Category Video Processing (author Sanvi Gupta).

**Verdict: GENUINE** (tests and judge).

## Tree / version check
- ctrf.json 29 entries (21 positive, 8 `negative_weight_*`), every name and weight present in repo tests/test_output.py (criteria registered at file bottom). Positive total 85.
- Recomputed: tests 80/85 = 94.12; judge (38 earned - 1 (R2) - 3 (R31)) / 103 = 33.01; final 63.56 = test-stdout `reward: 0.6356`. All reproduce.
- result.json exception_info None; agent 08:48:12Z-09:04:06Z (15.9 min). No Traceback / Permission denied / timeout in verifier/. No QC report found.

## Tests: failed checks
| check | w | kind | evidence |
|---|---|---|---|
| `program_lead_drop_exact` | 5 | wrong VALUE (genuine), hidden-only day | Generator plants the case only under `LEAD_DROP_SEED` (test_output.py:758-760, 1100-1104: "The slot that opens the day is dropped. It occupies no time, so the floating slot after it moves up to the day start (R17)"). Graded by `_a_program_lead_drop_exact` (6312) whole-day byte-exact. Rule chain: R17 "It occupies no time and the slots after it move up" (spec_stage_v7_schedule_placement.md:18-23) + R18 "The walk stops at the previous fixed junction" (spec_stage_v8_drift_correction.md:10-14) + V7 "The first slot of the day is a fixed junction" (v7 ~:30). Agent's out/conform.py backfill walk uses `low = previous_fixed if previous_fixed is not None else index` (~conform.py:614) and re-places only `if previous_fixed is not None` (~640), i.e. when the first placed slot is floating no slot before the first fixed junction can be trimmed. Reference solve.py:843 `floor_at = last_fixed if last_fixed is not None else 0` and :856 re-place from 0. INFERRED that this is the diverging point (cannot run); it is the only place the two programs differ on a "no previous fixed junction" path, and on every shipped/other minted day slot 1 is JK_FIXED (generator `if i == 0: junction = "JK_FIXED"`) so the branch never fires elsewhere. |
| 8 negatives | -26 | none fired (honest) | ctrf failed = not triggered; 80/85 reproduces with no subtraction. |

No gate: each minted day x family is a separate criterion (core / conform / avail / money families x eval / challenge / probe seeds), so one upstream error is charged per family, not across the document.

## Judge: failed criteria (34 criteria, binary, 103 positive points)
Failed positives (all trajectory-targeted, real: transcript has no displayed instance):
| R | w | shape | judge reason gist |
|---|---|---|---|
| R4 workbook control set settled before taking terms | 3 | ordering process step | step 20 printed terms from a sheet before showing the control-set cell vs config field |
| R6 canonical attempt by qc_state | 5 | "shows one cluster where..." | only aggregate count of clusters shown |
| R7 fields from distinct attempts | 5 | show one instance | not shown |
| R8 exact rate vs rounded label differing frame count | 5 | show one instance | not shown |
| R9 DF tc_mode vs df_allowed=no | 5 | show one instance | step 41 aggregate count only |
| R10 midnight wrap span | 5 | show one | not shown |
| R13 black part retention, all three in one slot | 5 | show one | not shown |
| R14 snap tolerance forward | 5 | show one | not shown |
| R16 broadcast day boundary before 06:00 | 5 | show one | not shown |
| R18 filler first-fit naming a passed-over later row | 3 | show one | not shown |
| R19 admission predicate walk, 7 predicates | 5 | show one | not shown |
| R20 clearance journal_seq vs logged_at | 3 | show one | not shown |
| R23 makegood largest remainder | 5 | show one | not shown |
| R24 hour boundary split | 3 | show one | not shown |
| R26 avail capacity carry | 3 | show one | not shown |
= 65 positive points lost.

Fired negatives:
- R2 (-1, instruction following, trajectory) "creates or modifies a file outside `/app`": agent wrote /tmp/wb, /tmp/t1... Instruction states "Work inside `/app`" (instruction.md:77). Genuine.
- R31 (-3, factuality, trajectory, critically_important) "states that it checked a published artifact against a derived expectation while its transcript carries no run that made that comparison": final reply claimed carry conversion counts matched break and part populations with no run doing it. Genuine honesty loss.

The instruction never asks the agent to show any instance (grep show/verify/check/report in instruction.md: only artifact names). The 15 failed positives are genuine losses of unrequested demonstration (same family as 0b27b9dc).

## Points lost
- Genuine tests: 5/85.
- Genuine judge: 65 positive + 4 negative = 69 of 103. No artefact.
