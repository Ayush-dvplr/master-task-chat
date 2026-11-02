# BUILD_REPORT ed7b0c2 flood-repair-portfolio

Status: DONE (BUILD READY). Bundle `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/flood-repair-portfolio/`, WORK `.../bundles/_work/flood-repair-portfolio/`. Session rename: `name_session.py ed7b0c2` printed `codex: no match` and `opencode: ['ses_e8c03a050ffe0YJMutfOlJc0ur']`; no retry. Fingerprints GEN (160 files) and QC (12 files) 0 DIFF 0 MISSING at start (22:27) and at end (00:33); nothing written inside GEN, QC or the harness.

## Tree (22 files, tree_sha 29adcbbb62e2)
- environment/Dockerfile (26), environment/data/: manifest.json 14, proposals.csv 2725, segment_codes.tsv 2727, sites.jsonl 2600, region_codes.csv 2601, crews.tsv 2401, permits.csv 3792, exclusions.json 1929, benefits.ini 10, audit_queries.txt 2424, contract.md 78. Data lines 21223 + contract 78 (A5 met; every csv/tsv/jsonl/txt >= 2000). Formats 7: json, csv, tsv, jsonl, ini, txt, md.
- instruction.md 15 lines / 1537 chars; task.toml 47; solution/ solve.py 366, solve.sh 172, TRUTH.md 193; tests/ Dockerfile 9, test.sh 10, test_output.py 1485, judge.toml 152, reward.toml 7.
- Chains (length >= 4): C1 proposal > site > region > region docs; C2 proposal > segment > rate > benefit > portfolio > segment docs; C3 proposal > site > risk class unless risk_override > uplift > benefit; C4 site-named exclusion > proposals at site > conflict pairs > portfolio; C5 proposal > crew > mode > conflicts > every doc.

## Levers (rule written where)
| lever | rule | where | wrong program measured | tests lost |
|---|---|---|---|---|
| LV-FP-1 exact optimum + tie-break | greatest total benefit, sorted-id tie-break | contract.md:62 | greedy, greedy+swaps, colour B&B / ILS capped at 8 s, no/largest tie-break | 74-77% |
| LV-FP-2 conflicts from 3 files | exclusive crew, held/applied permit, exclusion either order, site name = its proposals | contract.md:27-29, 56-58 | each source dropped or misread | 94-97% |
| LV-FP-3 valuation | households x (rate + uplift) + premium; risk_override precedence | contract.md:23, 48-50 | override, premium or uplift skipped / wrong level | 88-94% |
| LV-FP-4 secondary fault order | manifest order, whole-file rows, first check, NONPOSITIVE after | contract.md:19-21, 35-42 | order mutants | 3-15 (planned share 11%) |
Coupling sentence contract.md:64; stdlib single-file rule contract.md:5 and instruction.md.

## Tests and judge
- 34 checks (32 positive = 108, negatives -5 `/tests` read, -3 hardcoded shipped answers); weights 5/3/1. Shares: hidden + mutated 92/108 = 0.852; shipped-only 16/108 = 0.148; whole-document 77/108 = 0.713; isolated feasibility + optimality per hidden book 24/108 = 0.222.
- Judge 11 criteria (10 positive = 30, R11 honesty -5), batched, five-key header. reward.toml 0.5/108 tests, 0.5/30 judge.
- Agent program run as `sys.executable -I -S` via setpriv nobody from a foreign cwd; hidden books H1 714301, H2 721402, H3 731503, M 742604 (+ MS scaled/shuffled, MR rotated) regenerated in tests and sha pinned; expected docs computed at grade time by an independent min-fill elimination reference (O1 overlap 3%).

## Results
- validate_bundle.py --archetype domain-calculation: 41 passed, 0 failed, 0 warnings, GATE PASS.
- instruction_qc 5/0/0, structure_qc 17/0/0, judge_qc 19/0/0, tests_qc 37/0/0: all VERDICT PASS (no C6).
- Oracle x3 (harbor 0.24, tests channel): 1.0, 1.0, 1.0 (verifier 21.4, 23.8, 22.7 s); nop 0.0.
- run_tests local: oracle 108/108; check_exact 0 record diffs on 7 books, 315 rounds brute-forced, 300 small books 0 bad; gen300 300 seeds 0 errors; all 19 fault kinds planted.
- Mutants: 22 lever + 25 rule mutants, every rule row fails >= 1 check (RULE_COVERAGE: 0 uncovered).
- STACKING: VERDICT STACKING PASS (OUT/STACKING_CHECK.md). PRECHECK last line: `PRECHECK CLEAN`.

## Timing (M2)
Limit 20 s per book (contract.md:15). Reference in Docker python:3.12-slim: shipped 0.16-0.49 s (--cpus=1), 0.16-0.25 s (--cpus=2); hidden books 0.08-0.12 s (<= 1/40 of the limit). Generic exact (colour B&B, memo + reductions + component split, reduce_bnb) time out at 20 s PER ROUND at --cpus=2 on every hidden large round; per-round baseline losses in WORK/COST_TABLE.md (every baseline loses >= 1 large round per hidden book; lp_round+swaps and 10 s ILS non-exact on >= 1 large round per book).

## M1c environment facts
- task.toml: [agent] network_mode allowlist, allowed_hosts ["api.anthropic.com", "api.z.ai"], timeout 7200 s, user 1000:1000; [environment] network_mode no-network, cpus 2; [verifier] network allowlist ["api.openai.com", "*.openai.com"], timeout 2700 s, environment_mode separate.
- Agent image: /usr/bin/python3 = Debian Python 3.13.5 (pulled by apt nodejs/npm); PATH python3 = /usr/local/bin/python3 3.12.13. Tests image python3 3.12.15; the agent program runs there under `-I -S`, so any agent-installed package is unreachable. No solver-import negative (M1d).

## Expected loss per lever (share of 108 if wrong)
LV-FP-1 0.74-0.77 (most likely loss: opus first-write greedy/B&B with cap), LV-FP-2 0.94-0.97, LV-FP-3 0.88-0.94, LV-FP-4 0.03-0.14.

## Open conflicts / not run
- Q18: scaffold TRUTH provenance keys hold none of the validator 15.5 forbidden keys; validator and DS-27 agree; no OPEN CONFLICT.
- Not run: judge channel (no API key; golden_score_channel_b_pct null), probe/blind reads (per M7).

## Lessons for the master
- A shipped book of many small rounds plus 2 large rounds meets A5 without inflating instance size | no change: per-task data design.
- Rule mutants exposed 3 rules with no triggering fixture (missing file, zero-benefit boundary); plant boundary values, not just faults | template_change: master_chat_work/20261024_process/test_depth/kit/fam/cm_family.py:1 add boundary plant per stated threshold.
- Validator 7.4 requires a check named `negative_hardcoded_sample_answers` | template_change: LEVER_RULES_v2.md G4 list it as mandatory for domain-calculation.
- tests_qc B4 rejects `/logs/verifier` literal in tests/*.py | no change: already in common rules for judge text, extend reading to tests.
- Clique LP is integral on full triangular lattices; drop diagonals to p=0.7 to make LP rounding fail | no change: recorded in PREMORTEM.
