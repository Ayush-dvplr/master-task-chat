# HARDEN REPORT: match-replay-desync-audit, P9 v2 r1 (91cc2af)

Status: DONE. Bundle tree sha 2f20060e94d2 (pre edit 6711dce7a011).

## Diagnosis in one paragraph

Phase A GENUINE. The run scored 0.8043 = (103/163 + 42/43) / 2. Every one of the
twelve trap tests failed only because the agent's program asserted that exactly one
candidate reproduces each control (induced by the old instruction line 3 promise);
the one line change `!= 1` to `< 1` scored 163/163. Primary cause 4: every rule was
stated plainly and fingerprinted by a calibration control, so all levers leaked.

## Before and after

| lever / check family | before | after |
| --- | --- | --- |
| 12 wire transform traps | LEAKED (lost by accident, uniqueness crash) | kept, now whole document on heavy fresh sets, fail under every amount misread |
| per entry charter cap | LEAKED | replaced by L3 running allowance walked in settlement order |
| allowance renewal | absent | L4, renewal at first tick of every live window, needs 4 files |
| calibration controls | covered every rule | L1 green control: controls, seal and reconciliation stay green under amount misreads |
| judged figures list (instr l11) | 35 free judge points | removed; judge R7 to R9 are J2 conduct criteria |
| shipped slice promise (instr l3) | present | removed |

## Counts and weights

- Tests: 41 checks, 37 positive totalling 157, 4 negatives totalling -20 (each act <= 5).
- Shares: whole document hidden 140 (89.2%), isolated plus mutation 10 (6.4%), shipped only 7 (4.5%).
- Judge: batched, 11 criteria, positive 17, negative -8. reward.toml 0.5/157 and 0.5/17.
- STACKING PASS (OUT/STACKING_CHECK.md).

## Reflex gate

Real agent program on new tests: 17/157 = 0.1083 (gate <= 0.20 PASS). Adapted copy
0.1083. Single lever variants: per entry cap 0.1083, no renewal 0.1083, draw on
opening charter 0.1401, cancelled entries draw 0.1401. Scores in OUT/local_scores/.

## Gates

- structure_qc PASS 17/0/0; instruction_qc PASS 5/0/0; tests_qc 36 pass, 1 WARN A3 (41 checks over 35), 0 FAIL; judge_qc PASS 19/0/0; validator advisory GATE PASS 40/0/0.
- QL rule (git diff 2690e960 HEAD): H6 FIXED, K8 FIXED, S3 PASS, S5 PASS, T14 PASS, G2 FIXED, owner only run PASS.
- xref_check: 16 entries, 0 findings.
- Docker block TS 20261023T184333-d355 (log OUT/docker_block/runs.log, ALL_DONE): oracle x3 1.000, owner only 1.000, chmod 600 programs 1.000, nop 0.000, stub 0.0064 (format check only), forgery 0.0127 (7 shipped checks, hardcoding negative fired -5).

## Not run

- Playground static: removed upstream (a72c20a4), skipped.
- No live agent trial on the hardened bundle; the judge channel was not scored locally.
- Session rename: name_session.py lists only the opencode id; 91cc2af not shown.

## Lessons for the master

- A shipped slice uniqueness promise can make an agent crash on hidden sets; it hid a fully leaked task behind an 0.80 score.
- When calibration controls fingerprint every decode stage, put the lever above the control layer (amount side settlement).
- A running allowance only bites on hidden sets if hidden amounts are scaled; HELD_OUT_HEFT 40 kept shipped data non binding.
- tests_qc H6 misreads `[sys.executable, *FLAGS, program]`; inline the flags.
