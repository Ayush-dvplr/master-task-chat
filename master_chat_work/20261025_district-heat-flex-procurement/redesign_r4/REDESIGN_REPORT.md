# REDESIGN_REPORT: district-heat-flex-procurement, redesign r4 (board 7743264)

25 Oct 2026, 00:51-02:28 IST. Phase 1 design (DESIGN_PROPOSAL.md) approved by night master 01:50 ("go"), then Phase 2 and Phase 3 gates once. Status: **DONE**.
Session rename: `name_session.py 7743264` matched the opencode session (`ses_e90a38693ffew0WFLS99brnDIr`); codex: no match.
Tree sha before 12: `c3c5b97731b5` (matched last QC'd tree); after: `154b299ee9ad` (27 files).

## Levers before / after

| round | lever | shape | where written | measured on agent program |
|---|---|---|---|---|
| r2/r3 | L1 receipt, L3 season allowance, L4 rate composition, L7 per-interval half-even | stated step-by-step recipes | data-file comments | blind program 98/98; class a/e (REVEALING) |
| r4 | M1 grant re-share after minimum drop (H7 re-entry) | three-branch apportionment; second pass shares every cent of F in proportion to weight across survivors | `schema.md` section 7 (~lines 226-250), keys `program.ini` `[grants]` (claim 40, minimum 25), schema section 1 bullet | one-fact-wrong REENTRY 128/173 (lost 26.0%) |
| r4 | M2 allowance holder by `draws_from` chain (H6, recursive, no depth sentence) | counter keyed by resolved holder | `site_allowances.tsv` comment lines 2-11; schema section 1 bullet | CHAIN1 118/173 (lost 31.8%); CHAIN0 73 |
| r4 | M3 credited relief ticks (H3 defined term) | term used in `rate_cards.xml` comment, defined in schema section 6 | `rate_cards.xml` comment; `schema.md` section 6 | RELIEF 115/173 (lost 33.5%) |
| r4 | CARRY (coupling, counts 0) | unallocated cents carried to same region's next event in season order | `schema.md` section 7 funded-pool paragraph | NOCARRY 107/173 (lost 38.2%) |

Shipped data never separates the wrong readings (W5): 60 one-link chains only, 0 profile rows with relief and recovery in one interval, no minimum drop on shipped (claims-fit dominates). Separating cases are in the seeded hidden extracts only (H1 season with 2-4 link chains, H2 settlement with planted separating grant pools in every region).

## Counts and weights
- Tests: 50 checks (47 positive = 173 points, 3 negatives = -13). 20 owned-row families, each visible w3 (shipped) + hidden `_hard` w5; 3 mutations w3 (segment_rate_adder, allowance_ticks, minimum_grant NEW); 4 format w1.
- Shares: format 2.3%, visible families 34.7%, hidden 57.8%, mutations 5.2%; hidden + mutated 63.0% (G3).
- Judge: 12 criteria, +27 / -5 (kept R1-R8; new conduct R9 grants, R10 drawn allowance, R11 credit recompute, w3 each, `check R9/R10/R11 ok` printed by the solve.sh self-check stage; R12 J4 code quality w1 added because precheck required one). `mode = "batched"`. reward.toml 0.5/173 tests, 0.5/27 judge.

## Reflex gate and single-lever table (real new tests, local, tests channel)
| program | earned/173 | score |
|---|---|---|
| oracle | 173 | 1.000 |
| saved blind program | 31 | **0.179** |
| saved harness program | 28 | **0.162** |
| REENTRY / CHAIN1 / RELIEF / NOCARRY | 128 / 118 / 115 / 107 | 0.740 / 0.682 / 0.665 / 0.619 |
| REENTRY+CHAIN1 / REENTRY+RELIEF / CHAIN1+RELIEF / all three | 98 / 110 / 85 / 85 | |
Reflex gate <= 0.20: PASS (no merge fallback needed). All-but-one overall at judge 62.5: 64.5-68.2 (< 70).
Fuzz on final generator: 320 seeds x (H1, H2) = 640 corpora, 0 crashes, 0 out of contract; differing share 100% for REENTRY, DROPLEFT, NOCARRY, CHAIN1 (H1), RELIEF; NODROP 88.4% (H1); saved programs 100%.

## Gates
- STACKING_CHECK: PASS (OUT/STACKING_CHECK.md). RULE_COVERAGE: 44 rules, every mutant fails >= 1 test.
- QC kit HEAD 976c1666 (expected): instruction_qc 5/0/0; tests_qc 36 pass, 1 WARN A3 (50 checks > 35, recorded), 0 fail; judge_qc 19/0/0; structure_qc 17/0/0; validator 40 passed 0 failed GATE PASS; playground: absent in kit (not run). xref_check 45 entries 0 findings. **PRECHECK CLEAN**. No `__pycache__`.
- Docker (one chain, ALL_DONE, copies from exe_copy.py): oracle 1.0 / 1.0 / 1.0; owner-only 1.0; nop 0.0; stub 0.0058; forgery 0.341.
- Forgery 0.341: shipped answers pass the 20 visible family tests (G3 allows shipped-data tests without a share cap) and the 4 format checks; the hardcoded negative fires (-5); every hidden and mutation test fails. Above the old temporary 0.05 target; flagged for the master.

## Not run
- Judge channel (no API key): criteria checked by reading and against the oracle (JUDGE_MAP.md).
- Real harness probe (master queues it next). Playground (not present in kit).

## Files changed
BUNDLE: environment/data/{schema.md, program.ini, site_allowances.tsv, rate_cards.xml, export_manifest.tsv}, solution/{solve.py, solve.sh, TRUTH.md}, tests/{test_output.py, judge.toml, reward.toml}. instruction.md unchanged.
WORK: r4_data.py, r4_tests.py, r4_truth.py, TRUTH_r4_body.md, test_output.src.py, self_check_r4.py, DESIGN.md, LEVERS.md, QC_DEFENCE.md, XREF.md, COST_TABLE.md, RULE_COVERAGE.md, JUDGE_MAP.md, README_STALE.md, bundle_pre_r4/ (backup).

## Lessons for the master
- Measure a lever's one-fact-wrong on the real tests before writing docs: M1 came in at 26.0% only because of the CARRY coupling (23.7% without) | no change: COST_TABLE gate already requires it
- Owned-row visible families on shipped data let a forgery earn 0.34 | template_change: LEVER_RULES_v1.md G1: run visible family tests on a row-shuffled copy of the shipped data, or cap visible share
- structure_qc S3 rejects extra files in solution/; put self-check stages inline in solve.sh | template_change: LEVER_RULES_v1.md J2 (say "inline in solve.sh")
- precheck J4 needs an explicit maintainability criterion even when a structure criterion exists | no change: J4 already says so
- pool.map stalls on long fuzz runs; use imap_unordered with maxtasksperchild | no change: tooling note
