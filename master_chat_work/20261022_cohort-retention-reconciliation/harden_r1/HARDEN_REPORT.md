# HARDEN_REPORT cohort-retention-reconciliation, harden r1

Bundle: `master_chat_work/bundles/cohort-retention-reconciliation/` (edited copy;
v0 tree sha ae77ceb8...1694 in `_work/.../baselines.json`).
Harness HEAD: f3765e67 at Phase 0; 3fb1650b at Phase 3 (one commit, T14 author
spelling in structure_qc.py and Final_checklist.md; no effect on this bundle).

## 1. Diagnosis summary (full: DIAGNOSIS.md)

- v0 run (claude-opus-5): tests channel 36/85 = 0.4235. The judge did run
  (27/36 = 0.75), although the prompt said no judge key; reward 0.5868.
- Permission trap FIRED: 18 x `Errno 13 Permission denied` on
  `/app/out/derive_report.py` under the dropped uid. All 49 points on
  program-run checks were lost to it.
- Local probe with the trap removed: the agent's program passes all 12
  program-run checks (85/85). Every v0 lever (V0-1..V0-8) LEAKED: each rule sat
  at its point of use in schema.md, was shown by a shipped row, and the agent hand
  traced it (step 5) and built its own synthetic extract (steps 13-25).
- v0 composition: shipped-data-only 45.9%, rule-isolating fixtures 38.8%, hidden
  whole documents 15.3%. Judge criteria were process or echo items.

## 2. Changes per fix

1. Format. `tests/Dockerfile` pins `litellm==1.105.0`; `tests/judge.toml` header
   carries `mode = "batched"`; `test.sh` keeps `chown root:root` and
   `chmod 755 /logs/verifier`. The grader now calls `_grant_read()` on the program
   and every `/app/out` file (parents `|0o555` up to `/app`), serialises runs
   with a thread lock plus an `fcntl` file lock, and after each run kills the
   process group and every leftover process whose real uid is `nobody`.
2. QC v3 recheck at HEAD: DS-27 FIXED (no process state in Provenance); TS-17
   FIXED (`_emitted` rejects any bool or float in a document); JD-5 FIXED (R7 is
   one observable); DS-22 FIXED (Solution shape describes solve.py: bisect
   Calendar, DatedLookup, MergeHistory); TS-14 FIXED (checks renamed to the
   property they grade); JD-16, JD-15 FIXED (criteria replaced, figures asked
   plainly); AL-8 PASS (150 / 420 minutes kept).
   QL diff 2690e960..HEAD changed checks: TS-2 / K8 litellm pin PASS; TS-30 /
   H6 readable program PASS ("dropper grants read on the program"); TS-S11 PASS;
   TS-S16 PASS; judge_qc G2 batched PASS; structure_qc T14 / FC-S18 PASS;
   exe_copy `--owner-only` run: see gates.
3. Hardness redesign.
   - Data: events e029 refund 4900, e030 ooc+excluded, e031 ooc duplicate,
     e032 Feb 30, e033 value "45.00" repeat, e034 unknown a777; revenue types
     [purchase, refund]; new `plan_history.csv` (a002 enterprise from
     2026-02-12, the date of purchase e009; a004 pro from 2026-04-10); new
     `audit_policy.md` (plan in force; rejection register); `schema.md`
     rewritten.
   - Instruction: no rule, residual or artifact counts; names `schema.md` "read
     together with the study records it points to"; asks for six computed figures.
   - Split across files: `rejections` named in schema.md, defined only in
     audit_policy.md; plan in force likewise.
   - Scope by omission: "A purchase adds its value_cents; every other revenue
     event type subtracts it."
   - Decoy default: accounts.csv `plan` and schema.md "its account's plan",
     contradicted by plan_history on the shipped e009 boundary.
   - Dependent chain: weighted revenue feeds revenue maps, weighted shares,
     segment and per-cohort weighted figures and the weighted residual.
   - Nothing confirms the full answer: no worked figures shipped; the residual
     identities hold under every wrong plan or sign reading.
   - Tests: independent functional reference `derive()`, hidden generator that
     redraws calendar, plans, plan history (boundary, tie, merged-away rows),
     merges (chain, overlap, merge into excluded, ghost source), exclusions,
     strangers, revenue type names, minimum value, offset flag, horizon and
     malformed / duplicate / ooc injections. Reference and solve.py agree on 120
     random seeds.
4. Judge: 8 criteria. R1..R6 one figure each for the shipped extract
   (35700; 138900; mid 54000; 13 register reasons; P1 share 460/463; 23 clean
   events), each needing the full chain and absent from every shipped file;
   R7 code quality (cleaning and writing in separate named functions); R8 honesty
   negative (figures stated from a program never run). Removed all v0 process
   and echo criteria.
5. DESIGN.md, LEVERS.md, TRUTH.md updated; `_SHIPPED_DATA` re-embedded (13
   files), reward.toml `test_output = 0.5/60`, `judge = 0.5/19`, TRUTH shas
   match solve.sh and solve.py.

## 3. Levers before / after

| v0 lever | family | v0 verdict | r1 status |
|----|----|----|----|
| V0-1 cleaning order | E | LEAKED | folded into CR-5, graded in hidden documents |
| V0-2 pre-cohort | A | LEAKED | fixture 1 + hidden retention |
| V0-3 resolved exclusion | B | LEAKED | hidden generator (merge into excluded) |
| V0-4 merge history | C | LEAKED | fixture 3 + hidden cohorts |
| V0-5 minimum value | A | LEAKED | hidden seed with minimum 1200 |
| V0-6 offset-zero flag | A | LEAKED | hidden seed with flag true |
| V0-7 exact rates | E | LEAKED | fixture 1, now signed shares |
| V0-8 running-min survival | B | LEAKED | hidden survival |

| r1 lever | family | rule | wrong reading, tests score |
|----|----|----|----|
| CR-1 | A | register lists every reason true of the raw row | one reason per row 0.850 |
| CR-2 | B | plan in force on the event date, resolved account | accounts.csv plan 0.700; strictly after 0.700 |
| CR-3 | E | purchase adds, every other revenue type subtracts | all add 0.550 |
| CR-4 | F | textual malformed test, dropped first | fromisoformat 0.400; int-like 0.450 |
| CR-5 | B | dedup among rows left after steps 1-2 | dedup over all raw rows 0.417 |

The v0 agent program scores 1/60 = 0.017 on the new tests channel.

## 4. Counts and shares

- Tests: 20 positive checks (60), 5 negative (-23). Hidden whole documents on
  three regenerated studies 42/60 = 70%; rule-isolating fixtures 17/60 = 28.3%;
  shipped-data-only 1/60 = 1.7%.
- Judge: 8 criteria, 7 positive (19), 1 negative (-5).

## 5. Gates

| gate | result |
|----|----|
| structure_qc | 17 pass / 0 warn / 0 fail |
| instruction_qc | 5 / 0 / 0 |
| tests_qc | 37 / 0 / 0 (K8, H6 pass) |
| judge_qc | 19 / 0 / 0 |
| validate_bundle.py (advisory) | 44 pass / 6 fail; all 6 also fail on v0 (1.12 archetype manifest, 7.2 seed/main shape, 11.4, 11.5 recommended negatives, 15.5, 15.7 fix_patch_sha256) |
| oracle run 1 (tests only, exe_copy) | 1.0 (60/60) |
| oracle run 2 | 1.0 |
| oracle `--owner-only` copy | 1.0 |
| oracle with delivered program chmod 600 (`-rw------- agent agent` logged) | 1.0 |
| nop | 0.0 |
| stub (11 empty artifacts) | 0.0333 (artifact_set 1 + hidden_serialization_is_canonical 1; the canonical check passes trivially on `{}`) |
| forgery (replays the shipped answers for any input) | 0.0 (artifact_set 1 + canonical 1 + deterministic 3, minus hardcoded -5) |
| `Permission denied` in any verifier stdout | 0 occurrences across all 7 jobs |

Jobs: `gates/jobs/crr2-*`. A first attempt (`gates/errored_build_timeout/`) errored with
`EnvironmentStartTimeoutError` after 900 s while the verifier image downloaded the pinned
litellm wheel at about 63 kB/s; the image was pre-built by hand and the gates re-run.
Infrastructure only, no task change between attempts.

Judge channel: not run (no key); checked by reading. R1 to R6 each name one figure for
/app/data that needs the full chain and appears in no shipped file (35700, 138900, 54000,
13, 460/463, 23); R7 is the code-quality criterion; R8 is the honesty negative.

Not run: a real agent trajectory on the hardened bundle, the judge, PL QC, P8, P7.
Known weak spot: the stub earns 1/60 from the canonical-serialization check on empty objects.
