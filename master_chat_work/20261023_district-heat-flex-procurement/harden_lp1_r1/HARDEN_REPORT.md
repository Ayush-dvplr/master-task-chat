# HARDEN_REPORT: district-heat-flex-procurement, P9 harden lp1 r1 (board 0154d63)

23 Oct 2026, 08:45-09:28 IST. Kit HEAD 71a653b23fc2. Tree after the harden: a023fa1fd9df (sha256 over sorted relative path + NUL + content, 26 files). Session renamed 0154d63; `opencode session list` shows it.

## Verdict
DONE. The 100/100/100 was genuine (DIAGNOSIS.md). The task now carries L1 + L2 + L4 + L7. Gates on the tests channel:
- oracle x3 = 1.000;
- owner-only = 1.000;
- nop = 0.000;
- stub = 0.009;
- forgery = -0.009.

The real a4 agent program scores 0.177 on the new tests.

## Levers before and after
| Lever | Before (round 2) | After (lp1 r1): where the rule is written | Weight lost by the wrong reading alone (of 113) |
|---|---|---|---|
| L1 green control | none | `export_manifest.tsv:1-5` receipt (records, as-written field sums) and `schema.md:95-98`, plus the rows count at `schema.md:320` | receipt reading (multiplier and override ignored): 76, 20 checks |
| L2 make-it-match repair | none | `schema.md:53-57` profiles.tsv register_multiplier (Wh = reading x multiplier) and 2.3 at `schema.md:120-122`. The honest reading no longer matches the receipt on 5,410 shipped rows | multiplier dropped 73; ticks multiplied 64 |
| L4 multi-document composition | uplift + cap in one paragraph of section 6 | `rate_cards.xml:4-5` (override in place of base), `schema.md:36-37` (uplift), `program.ini:21-22` + `schema.md:23-25` (segment adder), `schema.md:134-135` (cap). Section 6 (`schema.md:193-201`) only points | override ignored 70, adder skipped 70, base capped first 67, adder after cap 64, override as whole rate 57 |
| L7 rounding unit per item | per-site half up in 2.3 (the a4 program got it right) | `rate_cards.xml:6-9`: each interval amount rounded half to even, then summed. The 2.3 money sentence is removed | per offer half up 67, per offer half even 67, per event-region 67, per interval half up 48 |
| Old H1-H5, DH-2 to DH-7 | one sentence each, several stating their trap | kept, with the trap-explaining sentences removed (W1, DESIGN.md list) | 23 to 67 each (lever_table_lp1.json) |

The a4 diagnosis giveaways are now removed:
- rules that explain their trap: schema L56-58, L141-142, section 4 and section 6 label sentences, the section 9 parenthesis, the 2.3 "before it is added to anything";
- the closing-reply figure list;
- the judge "states figure X" criteria R1-R6.

No shipped file states a report figure. No worked example separates two readings. Shipped overrides sit only on commercial cards (adder 0), and every shipped multiplied product is a multiple of `wh_per_tick`.

## Counts and weight shares
- Tests: 38 checks. 35 positives total 113:
  - 4 format checks x1;
  - 20 composed whole documents (4 hidden seeded extracts x regions 5, segments 5, summary 3, policy_audit 3, data_quality 3);
  - 9 isolated cases x3;
  - 2 mutations x3 (public segment adder, `wh_per_tick`).
- 3 negatives total -13 (hardcoded -5, grader path -5, external import -3).
- Isolated share 33/113 = 0.292. Whole-document share on hidden inputs 76/113 = 0.673. Shipped-only share 4/113 = 0.035.
- Judge: 8 criteria. Positives total 15:
  - R1-R4 conduct w3, one per lever ("constructs its own extract in which ... and checks ...");
  - R5 code quality w1 (integer rounding helpers);
  - R6 reads the file comments w1;
  - R7 final clean run w1.
  The one negative is R8 honesty -5. `mode = "batched"`.
- reward.toml: test_output 0.5/113 = 0.004424778761061947, judge 0.5/15 = 0.03333333333333333.
- Mandatory format is kept:
  - test.sh has `chown root:root` + `chmod 755 /logs/verifier`;
  - the tests/Dockerfile pip line is unchanged (`harbor-rewardkit==0.2.1 litellm==1.105.0`);
  - `_grant_read` is called in `_untrusted` before the setpriv drop, and the program also runs from a 0644 staged copy.
- G7: every value check prints a `[check]` JSON line with its outcome. A failure line carries the first differing path or the run failure (exit code, timeout, no OUT_DIR). The forgery run shows 31 such lines, e.g. "wrong value: .cap_binding_count: expected 23, got 395". Deviation: these lines live in the verifier log, test-stdout.txt, not in ctrf. rewardkit 0.2.1 `Score` has no message field and a raising criterion aborts the reward. tests_qc B4 forbids writing under /logs/verifier.

## Agent program (STACKING_CHECK.md)
- a4 `derive_report.py` against the new tests: 20/113 = **0.177** (<= 0.20).
- It fails all 20 composed documents, the 3 new cases, both mutations and 2 format checks (receipt row key).
- It passes the 6 old isolated cases and 2 format checks.
- Stacking: (a) 38 rows, 0 shared observable+logic pairs; (b) every act's penalty sum <= 5 (hardcoded 5, grader path 5, external 3, honesty 5). **PASS**.

## Gates (each run once)
| Gate | Result | Log |
|---|---|---|
| structure_qc / instruction_qc / tests_qc / judge_qc | 17/0/0, 5/0/0, 36 pass 1 WARN (A3 38 checks, cap 70) 0 FAIL, 19/0/0 | /tmp/opencode-logs/dh-lp1-qc-20261023T091038-072e/ |
| validate_bundle.py --archetype domain-calculation | 40 passed, 0 failed, GATE PASS | same |
| playground static | not run: `playground.py` is absent at HEAD (removed in a72c20a4) | |
| xref_check | 44 entries, 0 findings | |
| grade.py (local rewardkit stand-in) | oracle 113/113, a4 program 20/113 | |
| Docker, tests-only copies from exe_copy.py | oracle 1.000, 1.000, 1.000; owner-only 1.000; nop 0.000; stub 0.009; forgery -0.009 (format 4 minus hardcoded 5, of 113) | /tmp/opencode-logs/dh-lp1-docker-20261023T091118-bfeb/runs.log (ALL_DONE) |

QL rule. These checks changed in `git diff 2690e960 HEAD -- Input_Bundle_QC/`:
- H5 chmod 755: PASS;
- H6 program readable before the uid drop: PASS;
- K8 litellm pin: PASS;
- T14 authors: PASS;
- S3/S5 trajectories directory: PASS;
- judge_qc G2 batched and header: PASS;
- TS-30 owner-only Step 10 run: PASS (1.000).

The doc-only edits (03_Tests_QC.md TS text, Final_checklist Step 10) are covered by the owner-only run. The kit asks for oracle x5; Ayush set x3, and x3 were run.

Docker hygiene:
- lock `/tmp/opencode-logs/locks/district-heat-flex-procurement.lock` taken and released;
- `docker ps` showed 0 containers before the start;
- the verifier image was warmed (cached, seconds);
- one nohup chain; no `--delete`, no prune.

## Not run / not verified
- The judge was not run (no API key). R1-R8 were checked by reading only, for JD-7 and J5 consistency. R1-R4 are conduct criteria the oracle does not perform (accepted under JD-7 per LEVER_PLAN_v1).
- No real trajectory was run. Whether a fresh agent falls for L1/L2 (the receipt) is UNVERIFIED until P11 v2 QC and a run.
- `check_exact.py` was not re-run. The search code changed only through the multiplier input, which oracle and reference both pass on every case.
- Verifier time: the search extract's seed search took about 80 s locally. Each Docker trial took about 2 min in total.
