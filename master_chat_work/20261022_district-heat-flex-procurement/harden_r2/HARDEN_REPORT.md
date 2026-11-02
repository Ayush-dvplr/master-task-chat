# HARDEN REPORT: district-heat-flex-procurement, round 2 (22 Oct 2026, 17:20 IST)

Verdict: all round 2 fixes applied in place; gates pass (tests-only, labelled so). Judge not run (no API key). No solver (S2/S3/S4) runs, by round notes D; lever numbers below are arithmetic through the real check functions, not solver runs.
Working copy: `master_chat_work/bundles/district-heat-flex-procurement/` (edited in place, never regenerated, no `--force`). Original tree digest: `original_tree.sha256`; final: `final_tree.sha256` (25 files). Notes: `_work/district-heat-flex-procurement/{TODO,PLAN_R2,LOG,README_STALE}.md`, build scripts `test_output.src.py` + `embed.py`, `judge_build_r2.py`, `lever_table.py`, `check_exact.py`.

## Diagnosis (full text: DIAGNOSIS.md)
Master's diagnosis confirmed, no conflict. Both claude-opus-5 runs hit `AgentTimeoutError` at 7200 s. The program ran in about 1 to 8.5 s on the shipped data; the agents then built and timed their own 20 to 22 site stress cases against the 30 s limit (run 1: 21 to 23 s, ended inside a scale test; run 2: 54 to 65 s with out-of-memory kills, self-kills at 120 s and 300 s). Added finding: both delivered `derive_report.py` files are mode 0600, so the round 1 verifier would have scored only the four format checks. Both programs counted `waiver_signed_missing` only for known-site lines (the IN-16 gap). Reading of the programs against the rules is UNVERIFIED (nothing was run).

## Changes per master fix
1. Timing. LV-DH-1 (exact search at 22 sites in 30 s) is removed with its six checks. `schema.md` section 3 now says an event-region has at most 8 sites with candidate offers and at most 3 candidate offers per site (4^8 = 65,536 portfolios) and each run must finish within 120 seconds. The instruction names no size, no limit and does not ask for run times. Verifier timeout is 120 s; `within_contract` guards every composed and hand-built extract against the stated sizes. Oracle `solve.py` is now plain depth-first enumeration with ceiling cuts. Agent limit stays 7200 s.
2. Verifier permissions. `run_agent` copies `derive_report.py` as root into a grader folder (0777), `chmod 0644`, runs the copy under `setpriv` as nobody, kills the process group and then every live process of uid 65534 (scan of `/proc`, zombies skipped), parses the nine reports once and caches the parsed dicts (never a folder). Proof: owner-only oracle run (artifact mode 0600 confirmed) = 1.000; a Docker probe with a `setsid()` child: killed with the reaper, alive with it disabled (state S).
3. REAL rows of `recheck.json` (rows 1 to 9, 11 to 15, 17, 18, 19, 21): see table below. Row 10 (CL-2) false positive untouched. Rows 16 (JD-15, R4) and 20 (TS-20) are UNSURE and left untouched; R4 no longer exists (effort criteria replaced) and the weights it compared changed (segment documents 5, unknown-region isolated case 3), so both are moot but not resolved.
4. Judge. All 17 criteria replaced (see below).
5. Hardness redesign (instruction, composed documents, DH-3, decoy, omission): see below.
6. `tests/test.sh` keeps `chown root:root /logs/verifier` + `chmod 755 /logs/verifier`; `tests/Dockerfile` pip line is `RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0` (K8).

### Recheck rows
| # | Finding | Applied |
|---|---|---|
| 1 | IN-16 `waiver_signed_missing` | schema.md section 9: counted over every data row including lines skipped for an unknown-region site; embedded copy refreshed |
| 2 | DS-24 oracle restated the verifier | `choose_portfolio` rewritten as depth-first enumeration; `search_scale`, `search_units`, scale arithmetic removed; O1 2% shared; `check_exact.py`: 300 extracts, 1,200 event-regions, 338 ties, 0 mismatches between verifier DP, oracle DFS and plain enumeration |
| 3 | TS-19 five offers on a site | all offers per site <= 3 (stated max 3); `within_contract` fails a check setup that exceeds 8 sites or 3 offers |
| 4 | JD-7 R9 vs dead code | dead code removed; new R8 is true of the oracle (every function called) |
| 5 | JD-6 R10 undecidable | criterion removed |
| 6 | AL-27 SAFETY_HOLD over COOLDOWN | `waiver_labels_case` site `S-BOTH` (hold and cooldown), lazy flag `H1hc`; composed guards use it |
| 7 | AL-27 CERTIFICATE_PENDING | site `S-PEND`, lazy flag `H1pend` |
| 8 | AL-27 objective components 4 and 5 | `objective_component_order_case` (three events), flags `C34`, `C45`, `C5drop` |
| 9 | AL-27 weight-0 beneficiary | `residual_ties_descending_id_case` site `BEN-NIL`, flag `W0LIST` |
| 11 | CL-3 R5/R13/R15 copy schema.md | all echo criteria removed |
| 12, 13 | TRUTH.md counts and root cause | TRUTH rewritten: shipped data rejects 14 orphan offers and 36 orphan profile rows; root cause describes `solve.py` (depth-first) and names the verifier's state-merging separately |
| 14 | TS-14 description | `rejected_profile_rows_case` and `unknown_region_site_rows_case` descriptions list exactly what the body reads |
| 15 | JD-5 R9 compound | split into R7 and R8 |
| 17 | A3 WARN over 35 | 32 checks now: no warn |
| 18 | TS-16 negative path matching | AST string literals only (not docstrings): `/tests`, `/tests/...`, strings starting `/logs/`, `judge.toml`, `reward.toml`, `rewardkit`; the bare `test_output` token is gone; fires only if the program ran cleanly |
| 19 | TS-24 setsid / cached folders | see fix 2 |
| 21 | verifier permission | see fix 2 |

### Hardness redesign
- Instruction (2,037 bytes): no rule count, no trap topic, no sizes or limits, no run-time ask. The closing reply asks six computed figures: global `credit_cents`, `grant_funded_cents`, `grant_allocated_cents`, `residual_cents`, number of `CONTINUITY_WAIVED` site rows and `unallocated_pool_count`.
- Whole documents: four composed extracts graded as region files, segment files, summary with audit, data quality. Isolated share 24 of 100; shipped-data reads 4 of 100.
- DH-3 (funded pool, derivable, careful solver 0.381 when right in round 1) is read only through composed documents; no standalone funded-pool check remains (lost weight 40, all composed).
- Decoy: `program.ini` ships `[export] waiver_signed = Y` ("defaults the legacy export tool applies to fields it did not record"). schema.md says any other section of `program.ini` carries no rule, and 2.6 makes a waiver valid only when `waiver_signed` is `Y`. The shipped waiver file has 9 blank-signature rows on pending, valid, critical public rows (and 21 with `Y`), so the boundary shows in the data. Lazy flag `SIGNEDY` loses 43 of 100.
- Omission and split: section 7 gives the no-recipient pool and then "for every other event-region" (the W = 0 outcome is only in the allocation arithmetic and the section 9 count wording); `waiver_signed` is declared optional in section 1 and constrained in 2.6.
- Every rule stays documented in `schema.md` (round notes B hard limit); no hidden rule.

## Before and after
Round 1 numbers are the master's recorded ones (41 checks, positive 139). Round 2 numbers are weight lost by one wrong reading out of 100, by arithmetic (`lever_table.json`).

| Lever | Round 1 weight needing it (of 139) | Round 2 reading, weight lost (of 100) | Isolated part |
|---|---|---|---|
| LV-H01 waiver precedence | 11 (0.079) | H1 43, H1order 43, H1pend 43, H1hc 33 | 3 |
| LV-DH-6 decoy `waiver_signed` | - | SIGNEDY 43 | 3 |
| LV-H02 greatest tuple | 13 (0.094) | H2 48 | 3 |
| LV-H03 cap after uplift | 8 (0.058) | H3 63 | 3 |
| LV-H04 descending ids | 8 (0.058) | H4 23, W0LIST 23 | 3 |
| LV-H05 quantise when derived | 6 (0.043) | H5t 60, H5c 45 | 0 |
| LV-DH-1 exact search at 22 sites | 26 (0.187) | removed | - |
| LV-DH-2 per-value ticks in the search | 25 (0.180) | DH2 48 | 3 |
| LV-DH-3 funded pool | 26 (0.187) | DH3 40 | 0 |
| LV-DH-4 rejected rows | 27 (0.194) | DH4dup 30, DH4range 42, DH4unknown 35 | 3 |
| LV-DH-5 waived weight | 13 (0.094) | DH5raw 30 | 0 |
| LV-DH-7 component order | - | C34 33, C45 33, C5drop 63 | 3 |

Round 1 measured: S0 0.000, S1 -0.007, S2 0.086, S4 0.194, S4b 0.381, S5 1.000, shortcut -0.007. Round 2: S2, S4, S1 not run (round notes D). Nop, oracle, owner-only oracle, forgery and replay below.

## Tests (32 checks, positive 100, negative -16)
- Format on shipped `/app/out` (1 each, total 4): `artifact_set_exists_and_parses`, `canonical_serialization_and_integer_units`, `report_keys_match_schema`, `report_arrays_in_schema_order`.
- Composed extracts (72): A grants (waivers, holds, pools), B search (ties, twin and zero offers, groups up to 8 sites), C rejects (repeated, out-of-range, orphan, unknown-region rows, rows reversed), D mixed (shuffled rows). Per extract: four region files (5), both segment files (5), summary.json with policy_audit.json (5), data_quality.json (3). Each extract is the first seed in a deterministic list for which every wrong reading named in `GUARDS` changes the document that is graded; the hand-built events of the isolated cases are planted inside.
- One rule family each, weight 3 (24): `waiver_labels_case`, `tie_break_greatest_tuple_case`, `cap_after_uplift_case`, `residual_ties_descending_id_case`, `tick_feasibility_case`, `objective_component_order_case`, `rejected_profile_rows_case`, `unknown_region_site_rows_case`.
- Negatives: `negative_hardcoded_sample_answers` -5 (needs a clean run), `negative_reads_tests_or_reward_files` -5 (needs a clean run), `negative_external_dependency_or_network` -3, `negative_missing_substantive_sections` -3.
- Weight shares: isolated 24 percent, composed 72 percent, format 4 percent. Known risk for TS-26: `summary.json` (in the summary-and-audit check) rolls up what the region files already carry.

## Judge (10 criteria, positive 20, negative -10, `mode = "batched"`; judge not run)
R1 to R6 (3 each): the response states, as written by the program for the shipped data, the global `credit_cents` 1959002, `grant_funded_cents` 207152618, `grant_allocated_cents` 197369679, `residual_cents` 3602, 18 `CONTINUITY_WAIVED` site rows, `unallocated_pool_count` 89. R7 (1): every except clause in the final `derive_report.py` names an exception type. R8 (1): every function it defines is called. R9 (-5): opens a file under `/tests` or `/logs/verifier`. R10 (-5): the response says its figures were checked against a second, independent calculation while no command in the trajectory computes them a second way.
Read against B.12 (not run): one figure per criterion; each figure needs the whole chain (ticks, cap, funded pool, label ranking, doubling, largest remainder, the decoy, the no-recipient rule) and appears in no shipped file (grep of the four large figures in `environment/data`: none); one honesty negative; no multi-figure criterion; no criterion echoes a schema sentence; no effort criterion remains. The instruction asks for exactly these six figures.

## QC changes since 2690e960 (`qc_diff_2690e960.patch`)
| Change | Result |
|---|---|
| TS-2 / K8 litellm pin | FIXED (tests/Dockerfile) |
| TS-S11 `ENV LITELLM_LOCAL_MODEL_COST_MAP=True` | PASS (already present) |
| TS-30 / H6 agent program readable before the uid drop | FIXED (staged copy); script pass; owner-only oracle 1.000 |
| judge `mode = "batched"` (G2) | FIXED |
| Step 10 owner-only oracle run | PASS (1.000, derive_report.py arrived 0600) |
| TS-S13 / O1 oracle independence | PASS (2 percent of 376 lines) |
| Final_checklist litellm and owner-only text | PASS |

## Gates (tests-only, run on the final bundle)
- QC scripts: structure 17 pass / 0 warn / 0 fail; instruction 5/0/0; tests 37/0/0 (A3 32 checks, O1 2 percent, H6 pass); judge 19/0/0. Logs: `gate_final_*_qc.log`.
- `validate_bundle.py --archetype domain-calculation`: 41 passed, 0 failed, 0 warnings, GATE PASS (`gate_final_validate.log`).
- `exe_copy.py` copies, Harbor 0.24.0 in Docker, tests only: oracle run 1 = 1.000, oracle run 2 = 1.000, nop = 0.000, owner-only oracle (0600) = 1.000. Whole-job wall times 29 to 34 s (image already built).
- Tests-channel forgery (nine correct-looking JSON files, a `derive_report.py` that exits 1): 0.04 (paid the four format checks). Replay of the shipped outputs from a program: -0.01 (hardcoded negative fires). Both on the host with the stub rewardkit, not in Docker.
- Exactness: `gate_check_exact.log` (300 random extracts, 0 mismatches), run with the same reference and oracle before the final edits that did not touch either.

## Oracle wall times per graded case
Docker `--cpus=2 --memory=4g`, pinned base image, median of 3 (`oracle_times_docker.txt`). Limit stated to the agent: 120 s; the oracle's slowest graded case is under 0.35 s.
case_cap 0.037, case_components 0.039, case_rejected 0.037, case_residual 0.038, case_tick_feasibility 0.037, case_tie 0.037, case_unknown_region 0.038, case_waiver 0.042, composed_A 0.047, composed_B 0.336, composed_C 0.049, composed_D 0.337, case_full (8 sites x 3 offers, planted in B and D) 0.316; shipped data 1.003 s (all in seconds).

## Not run or not verified
- Judge channel (no `OPENAI_API_KEY`); S1/S2/S3/S4 solver runs (round notes D); a real model trajectory; the five-run oracle block of Step 10 (two oracle runs were run, as the round notes ask); the stub run (forgery was priced instead, on the host); the model gates IN, DS, TS, AL, JD of the PL QC (Ayush runs them).
- Open points for the PL QC: the decoy may draw IN-16 or AL scrutiny (schema.md states the authority explicitly); recheck rows 16 and 20 are UNSURE and untouched; a wrong-reading arithmetic table does not predict a real model.
