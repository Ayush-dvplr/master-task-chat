# DESIGN_SUMMARY backdated-entitlement-replay (99230f0), 31 Oct 13:30 IST
Shape D. Program `/app/out/derive_report.py --input <dir> --output <dir>`, 10 fixed JSON outputs, 14 flat input files in 7 formats (md, json, jsonl, csv, tsv, yaml, log; ~36k lines shipped).
Spine: parse -> per-account anchor day (1-28) + basis (actual|thirty) fit on paid invoices with original events (exactly one fit, else `anchor_none` / `anchor_ambiguous`) -> corrections screened and replayed from the earliest effective date -> every non-void invoice re-rated -> credit ledger re-derived (lots, overpayment lots expiring N cycles later, N from the one live key of the superseded legacy_terms.yaml, transfers capped by the replayed balance) -> region/segment/summary/audit/data-quality documents.
Coupling sentence: as given in the build prompt; anchor/basis and replayed balance flow into every row.

Levers (each alone >= 25% of positive test weight; hidden share 90.4%):
| lever | rule / file | shipped fires | hidden plant |
|---|---|---|---|
| L-FIT (S2+S3, H8/H9) | B2 billing_terms.md | 0 | anchors 2-28 + both bases everywhere; ambient void rated at legacy default; quiet account (all 56 fit) in extract 2 of every tier; PB1/PB1b ambiguous, PB2 none |
| L-REPLAY (S1) | C1-C4 correction_policy.md, K3/K5 credit_policy.md | 0 (cap/N) | every extract; PA4 cap after replay; PS N = 2-3 |
| L-PAIRS (P-A) | B3, B5, K1, K4, C2 | 0 | PA1 cycle start, PA2 expiry day, PA3 same-day transfer, PA5 arrival order, PA6 half-cent |
S5 decoy: legacy_terms.yaml (header demotes it except `credit_expiry_cycles`).

Kill table (Docker, KILL_TEST.md, 2 hidden seeds x 20 extracts): forward-only 1.0; latest-arrival 2.9; shipped anchor carried 2.9; careful wide first fit 2.9; best fit 2.9; void as evidence 2.9; first write 2.9; careful unique fit + 2 pair slips 79.0 (loses 21.7% of lever); + 4 slips 64.4; all-but-one pair 85.4-93.5. Reference / split-by-parent EXACT, 1.33 s max vs stated 60 s. 0 crashes or timeouts, all losses WRONG. Not NO CORE.
BRANCH_FIRE: 12 hard-branch variants, shipped count 0 each, each fires on both seeds.

Tests: 30 hidden checks w5 (10 tiers x ledger/rollup/control, whole-document exact) + 3 shipped w3 + 2 mutation w3 + existence w1 = 36 checks (WARN A3), positive 166; negatives ignores-input -5, mutates-input -3. One wrong fact = 3.0% (CL-4).
Judge: 10 probes w3 (P-a x3, P-b, P-c x2, P-d, P-e, P-g, P-h) + J4 w5 + J6 w5 + J10 w3 = 43, probe share 69.8%; J3a -3, J3b -5, scope -1, grader-read -5. Estimate lower 18.6 / mid 41.9 / upper ~70.

DESIGN READY (v3.7): (a) predicted final (2.9 + 41.9)/2 = 22.4 if the first write uses first fit (PREMORTEM); careful unique-fit writer with 2 slips: (79.0 + 41.9)/2 = 60.5 (FAIL). (b) lever share 90% (w5 held-out tier 90%). (c) blind not yet measured. (d) 25 runs x 60 s = 1500 s <= 2430 s. (e) PASS.
Honest risks: a program that transliterates every sentence is exact (S5 study 3/3); the loss rides on H8 first fit and H9 never building a pair input. Judge mid 41.9 misses the <= 20 target (band cap 70% + outcome criteria passing); final <= 35 needs first-write tests <= ~28.

Decision for Ayush: IDEA line 15 says every account fits uniquely. This design states the unresolved outcome (`anchor_none`/`anchor_ambiguous`) and plants ambiguous/none/quiet accounts on hidden only, because with unique fit everywhere the first fit is the unique fit and row 4 keeps 100% of the fit lever (NO CORE). Fallback if rejected: drop PB tiers + quiet accounts (fit lever then rests on H9 + ambient void only).

G-7 pilot record:
| pattern | where in the bundle | measured effect (kill rows, blind) |
|---|---|---|
| P-A many small hidden extracts, one stated pair each | 10 tiers x 2 extracts, tests embedded generator; pairs in billing_terms/correction_policy/credit_policy | one pair slip loses 6.5-14.6%; 2 slips 21%, 4 slips 36%; blind: pending |
| P-B finite latent anchor/basis, unique fit | billing_terms.md B2; generator asserts unique fit per account per extract | first fit / best fit / shipped anchor / void evidence each keep 0% of lever; unique-fit transliteration exact; blind: pending |
| P-C per-document/per-field checks | 3 families per tier, first differing JSON path in messages, no hash, no broad except | one wrong fact 3.0%; blind: pending |

Files: WORK/PREMORTEM.md, DESIGN.md, KILL_TEST.md, BRANCH_FIRE.md, QC_DEFENCE.md, kill/{core,gen,run_kill,branch_fire}.py.

## Design blind ready
- Path: `WORK/design_blind/` (instruction.md + environment/data/: 5 rule docs, legacy_terms.yaml, 8 data files; shipped seed 731905, 400 accounts, degenerate: every pair variant 0 differing docs).
- Scoring seeds: 101 and 202 (kill-table seeds), all 10 tiers x 2 extracts each = 40 extracts, at `_runs/20261031/backdated-entitlement-replay/proto-20261031T1257/scratch/bhid101`, `bhid202`; spare seed 303 (`bhid303`).
- Scoring command (WORK/proto/score_blind.py, reference = WORK/proto/solve_proto.py, 60 s cap per run = stated limit):
  `python3 ".../master_chat_tasks/tools/dockfree.py" --need-mb 4096 --cpus 2` (must print START=yes), then
  `perl -e 'alarm 3000; exec @ARGV' docker run --rm --memory 4g --cpus 2 -v WORK/proto:/p:ro -v <blind dir>:/b:ro -v WORK/design_blind/environment/data:/ship:ro -v <scratch>:/s:ro python:3.12-slim python3 -B /p/score_blind.py /b/derive_report.py /ship /s/bhid101 /s/bhid202`
- Pass bar for the lever: the blind loses >= 40% of lever (hidden) points by WRONG output, else NO CORE.

## Design blind 1861cfe (31 Oct 14:58 IST)
Program `WORK/proto/blind/derive_report.py` (sha256 6e24c9d7cf98..., 652 lines, first full write ~3 min, self-check on shipped only). Scored with score_blind.py in Docker (log `_runs/20261031/backdated-entitlement-replay/score-1861cfe/logs/score.log`).
| scope | lever points kept | lost | loss kinds |
|---|---|---|---|
| total (30 hidden checks, 150 pts) | 100.0% | 0.0% | 0 WRONG, 0 TIMEOUT, 0 CRASH |
| L-FIT (PB1, PB1b, PB2 tiers + quiet/void ambient on all) | 100% | 0% | none |
| L-REPLAY (PA4 cap after replay, PS live legacy key) | 100% | 0% | none |
| L-PAIRS (PA1, PA2, PA3, PA5, PA6) | 100% | 0% | none |
Seconds: shipped 1.11; seed 101 4.76 total (max 0.40 per extract); seed 202 5.75 total (max 0.42). Tests kept 100.0% (309/309).
Rule pairs wrong: none. Fit cases wrong: none (it fits 56 candidates on paid invoices only and reports anchor_none/anchor_ambiguous with the count, i.e. it transliterated B2 including uniqueness).
Pilot record (G-7, measured):
| pattern | where in the bundle | measured effect (kill rows, blind) |
|---|---|---|
| P-A one stated pair per small hidden extract | 10 tiers x 2 extracts | kill: one slip 6.5-14.6%; blind 1861cfe: 0 of 7 pair/replay tiers lost (every pair sentence implemented as written) |
| P-B finite latent anchor/basis, unique fit | billing_terms.md B2 | kill: first/best/fixed/void-evidence keep 0%; blind 1861cfe: unique fit implemented, 0 of 3 fit tiers lost; ambient quiet/void accounts 0 lost |
| P-C per-document/per-field checks | 3 families per tier | blind 1861cfe: nothing to measure (0 differing documents) |
Predicted final with the blind's tests: (100 + 41.9)/2 = 71.0. VERDICT: NO CORE (blind lost 0% < 40% bar). Stated-rule levers leak again, as in LEVER_RULES 1C S5 (now 4/4).
