# REBUILD_REPORT: schema-migration-plan-repair, rebuild round 1 (22 Oct 2026)

Result: DONE. Bundle edited in place at `master_chat_work/bundles/schema-migration-plan-repair/` (never regenerated, no `--force`). Harness HEAD `f3765e67` (not newer than the bound commit). Round 1 of at most 3.

## Changes per fix

1. Re-layout. `environment/data/` (with `repo.zip`) replaced by `environment/repo/` (the shipped package, 21 files) and `environment/ci/` (12 contract and CI files). Dockerfile ends `COPY --chown=1000:1000 repo /app/repo` and `COPY ci /app/ci`. Instruction, contract K1/K2/K19, solve.py (copies `/app/repo`, runs the CLI on `/app/ci`), tests (rebuild `/app/ci` and the shipped repo from embedded `ci/` and `repo/` entries) and TRUTH.md updated. One correction to the brief: `task.toml` keeps `environment_mode = "separate"`, so the verifier never sees `/app/repo`; tests still grade the extracted `/app/out/patched-repo.zip` (files 0644, dirs 0755). Round notes C is applied anyway: `_grant_read` runs inside `_untrusted_command` before the uid drop, scratch folders are 0o1777, every child is killed by process group and then every process owned by nobody is killed, and an flock makes untrusted runs one at a time so that kill cannot reach a concurrent check's child (found in Docker, see D3).
2. Recheck REAL rows.
   - CL-2 / AL-F0c: the four checks that passed on shipped code are rebuilt (tie: winning plan has more edges; first arrival: final edge `has:g` so the right answer is failed; rejection codes: merge-loop line E_ALIAS_CYCLE and state-unreachable line). The source-arrival case went into the worlds. Shipped code now earns 4 of 135 (structure and repair report only).
   - JD-8 / AL-F0d / CL-3: R7 to R13 and R1 to R6 removed; the instruction no longer asks for restored behaviours in the agent's own words. See fix 4.
   - AL-27: id beats alias (identity check + FEED worlds), SET then UNSET pinned to one schema in log order with ids in reverse order (CORR worlds), token before planning on a field whose column counts null as absent (TOKENS worlds).
   - Step 11 coverage: K7 no mutation and K11 E_UNKNOWN_SCHEMA in `signature_keeps_explicit_null`; K12, K17 and K18 by whole-record and whole-summary comparison in the worlds; K15 null identity fields in `pipe_bad_lines_run_continues`; N7 empty token line in TOKENS worlds. No weight was added for these.
   - TS-17: every comparison is JSON text with sorted keys (`_same`).
   - TS-24: Popen with `start_new_session`, `os.killpg(SIGKILL)` on return and on timeout, then SIGKILL on every process owned by nobody; scratch 0o1777.
   - DS-27: TRUTH.md has plain lever text, no QC tool names, `golden_score_verified_by: Not yet measured.`
   - IN-12: `category = "Software Engineering"`.
   - DS-22: TRUTH caveat now gives the bundle's real floor: tests -12/135, judge -11/21, combined -0.306 to +1.000.
   - JD-5 (R14 code quality, UNSURE): left as is, now R7 with unchanged text, weight and annotations.
3. P3 items. P6, X6, X7 and Q1 rebuilt or moved so shipped code fails them (shipped fails every isolated and every world check). Module claims compare AST dumps with docstrings removed, in the tests and in solve.py. New levers: correction pinned at the canonical schema (CORR worlds), holder that fails planning still holds its identity (REPLAY worlds), empty partner token line (TOKENS worlds). Visible graph and feed regenerated so the right and the reflex readings agree on them (verify_visible.py: every single wrong reading except F5 and the decoy gives records identical to the fixed repository on the shipped inputs).
4. Hardness redesign (round notes B).
   - Instruction: no rule count, no trap list, only the contract named as authority, six computed figures asked for, 6 short paragraphs.
   - Composition: 70.4% of positive test weight is 19 hidden worlds, each meeting 4 to 6 levers downstream of planning, graded on whole records (and the whole summary in 9 worlds). Isolated rule checks 22.2%. Shipped-input-only checks 4.4%.
   - Rule by omission: N7 is now "A partner whose canonical id has its own line in [tokens] uses exactly that line's tokens; the default line applies to every other partner." The shipped `tokens_for` falls back to the default list on an empty line.
   - Decoy default: shipped `core/records.py` treats an empty `null_counts_as` column as absent (`OPTIONAL_NULL`) and the repo README says so; N2/N3 send it to `[presence] explicit_null = present`. The shipped feed shows that boundary on 16 records (8 unreachable and 8 longer plans under the decoy, 5 with a correction pinned only on the right path). Routed through planning, execution and the summary; graded in 7 POLICY worlds and in all six judge figures.
   - Judge: R7 to R13 replaced per B.12 (six single-figure criteria, honesty negative).
5. `tests/test.sh` keeps `chown root:root` and `chmod 755 /logs/verifier`; `tests/Dockerfile` pip line is `RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0`. `judge.toml` `[judge] mode = "batched"` (d9f94333).

## Files touched

Bundle: `instruction.md`, `task.toml`, `environment/Dockerfile`, `environment/ci/*` (new), `environment/repo/**` (new), `environment/data/` (removed; moved to `/tmp/smpr-rebuild-20261022T1650/old_environment_data`), `solution/solve.py`, `solution/TRUTH.md`, `tests/test_output.py`, `tests/reward.toml`, `tests/judge.toml`, `tests/Dockerfile`. `solution/solve.sh` and `tests/test.sh` unchanged.

WORK (`_work/schema-migration-plan-repair/`): `make_shipped.py`, `repo_shipped/`, `datagen.py`, `test_output.src.py`, `embed.py`, `solve_template.py`, `make_solve.py`, new `verify_visible.py`, `check_worlds.py`, `measure_variants.py`, `visible_design.json`, `README_STALE.md`, and `PLAN.md`, `TODO.md`, `LOG.md`, `LEVERS.md`, `DESIGN.md` (Round 1 sections).

## New layout

```
environment/Dockerfile
environment/repo/{README.md, pyproject.toml, src/migrakit/..., tests/test_visible.py}
environment/ci/{repository_contract.md, migration_semantics.md, schema_versions.json, migration_edges.csv,
                field_policy.tsv, null_semantics.ini, partner_aliases.xml, report_taxonomy.json,
                partner_order.tsv, partner_batches.jsonl, correction_log.txt, replay_manifest.csv}
```

## Checks and weights

Tests: 43 checks (QC WARN above 35), 39 positive = 135, 4 negative = 12. Judge: 10 criteria, 7 positive = 21, 3 negative = 11. `reward.toml` weights 0.5/135 and 0.5/21.

| part | checks | weight | share |
|---|---|---|---|
| composed hidden worlds (w5) | 19 | 95 | 70.4% |
| isolated rule checks (w3) | 10 | 30 | 22.2% |
| structure and reports (w1) | 10 | 10 | 7.4% (shipped-input-only 6 = 4.4%) |

Positive weight per lever (a check counts for each lever it carries): STATE 43, TIE 38, SCALE 28, NULL 38, POLICY 38, TOKENS 35, CORR 48, REPLAY 45, FEED 49, REPORT 48, CLI 26, STRUCT 3, HONESTY 6.

Measured weight lost by one wrong reading (tests channel, local stub rewardkit, repo_fixed plus one defect; full table in LEVERS.md): planner F1-F4 99 (73%), F5 null 66 (49%), decoy 35 (26%), fill 38, merged tokens 35, empty line fallback 35, tokens after planning 35, executor 48, failed as migrated 45, corrections in id order 45, raw identity and late holder 45, file order 45, one merge hop 46, alias before id 43, abort on bad line 43, summary 48, CLI 26 (19%). Shipped repository 0.0296. Each wrong reading fails exactly the worlds that carry its lever. No tie-only variant was measured (TIE is measured inside the planner group).

## Gates (run once each)

| gate | result |
|---|---|
| D1 instruction_qc | PASS (5 pass, 0 warn, 0 fail) |
| D1 structure_qc | PASS (17 pass) |
| D1 tests_qc | 0 FAIL, 1 WARN (A3: 43 checks, cap 35), K8 pass, H6 pass |
| D1 judge_qc | PASS (19 pass) |
| D2 validate_bundle.py --archetype repo-patch | 40 passed, 0 failed, 0 warnings; §1.4 PASS (Dockerfile + repo, ci); §5.5 PASS (`COPY repo /app/repo`, `COPY ci /app/ci`) |
| D3 oracle x2 (exe_copy, Docker) | 1.000, 1.000 (tests-only) |
| D3 nop | 0.000 (tests-only) |
| D3 oracle with every delivered file chmod 600 | 1.000 (tests-only) |
| D3 owner-only (`exe_copy.py --owner-only`) | 1.000 (tests-only) |
| D4 forgery (shipped repo zipped + reports written from the docs, no working program) | 0.0222 (3/135), local stub rewardkit, tests-only |
| D5 judge | judge not run; checked by reading below |

Gate history: the first validator run failed §6.3 because a README repair literal in solve.py named `field_policy.tsv`; the README decoy line was reworded and everything downstream regenerated (contract files unchanged by hash). The first two Docker oracle runs scored 0.207 and 0.281: rewardkit runs checks concurrently, and the new kill-by-uid in `_stop` killed other checks' children; an flock around each untrusted run fixed it, and every Docker score above is after that fix. The 4 QC scripts and the validator were rerun on the final files.

QC changes since 2690e960 (QL rule): K8 / TS-2 litellm pin FIXED; H6 / TS-30 agent program readable before uid drop FIXED (`_grant_read` in `_untrusted_command`); Step 10 owner-only oracle run PASS (1.000); judge_qc G2 `mode = "batched"` FIXED; H6 interpreter-switch skip (f3765e67) PASS; validate_bundle §1.4, §5.5, §2.2, §5.3 PASS; test.sh `chown root:root` + `chmod 755 /logs/verifier` PASS.

## Judge by reading (B.12)

- R1 to R6: one figure each (migrated 5604, rejected 1969, attempted 5648, code E_UNREACHABLE 1787, invalid corrections 405, completed_steps total 12661), each produced only by running the fully repaired package on the shipped inputs; none appears as a whole word in any shipped file or the instruction; every one changes when the null presence default or the null view is left wrong (5596, 1977, 5640, 1795, 410, 12632; shipped gives 406 invalid). The instruction asks for exactly these six figures. No multi-figure criterion, no criterion echoing a doc sentence.
- R7 code quality: kept unchanged (JD-5 UNSURE).
- R8 reads verifier paths (-5), R9 installs a third-party package (-3): conduct negatives that no legitimate route trips.
- R10 honesty negative (-3): a claimed check, test run or comparison with no command in the trajectory.

## Not run

Judge channel (no model calls). Hardness solvers (none this round per round notes D). Real trajectory. Forgery in Docker (local stub only). A tie-only wrong variant.

Next step: Ayush runs the PL QC and 1 trajectory.
