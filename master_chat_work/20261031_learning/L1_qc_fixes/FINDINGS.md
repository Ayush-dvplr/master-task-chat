VERDICT: QC fixes closed many reported defects, but subsequent rounds repeatedly found new contract, test, judge and prose errors; the documented file links do not prove isolated causality.

# 1. All QC findings

**Finding.** `QC_FINDINGS.csv` indexes 585 active finding rows from 95 `v*.md` reports across 17 tasks: 270 fails, 150 minors and 165 warns. Method: `python3 scripts/build_l1.py` reads the first consolidated Findings section, takes numbered, bulleted and bold finding entries, applies the local severity heading or emoji, captures the first QC check ID and named file:line, and excludes explicitly acknowledged or fixed-only entries. Each row has a report path:line. `parse_summary.json:$.parse_issues` = none. A report can have zero active findings; `ROUNDS.csv` retains it. **UNVERIFIED:** 10 rows lack a standard check ID, and some reports repeat the same root in different gates; these are separate report entries rather than deduplicated defects. Evidence: `scripts/build_l1.py`, `parse_summary.json:$.reports`, `$.findings`, `$.severity`, `QC_FINDINGS.csv:report_evidence`.

**Change:** Make `master_chat_tasks/tools/` ingest the CSV after each QC round and require a primary check ID plus source line for each consolidated finding. **Expected gain:** query all rounds and spot repeated defects without rereading 95 reports. **Could break:** irregular report prose can be misparsed; `check_id=UNVERIFIED` rows need hand classification. **Check:** compare per-report CSV counts to the report's Overall row and inspect every `UNVERIFIED` ID before promoting the index. Evidence: `scripts/build_l1.py`, `QC_FINDINGS.csv`, `parse_summary.json:$.check_tasks`.

# 2. What happened after each fix

**Finding.** `QC_FINDINGS.csv:status_next` links each active row to the next numbered report for its task. The current index has 170 “FIXED”, 40 “CAME BACK”, 22 “MOVED”, 20 “KEPT”, 1 “REBUTTED” and 332 “NOT RECHECKED” rows. It uses same check ID plus text and named place for recurrence; “FIXED” requires explicit fixed/resolved/pass wording in the next report's comparison. A matching P12 `KEPT.md` or `PL_NOTE.md` line, or a task KEPT line acknowledged in the next report, overrides recurrence. P12 `RECHECK_FIX.md` notes are linked where their folder names identify the QC version; 24 such notes were found. **UNVERIFIED:** absence of a finding is not counted as fixed, and a shared check ID may describe a different defect. Evidence: `scripts/build_l1.py:match`, `QC_FINDINGS.csv:status_next,next_evidence,fix_note`, `parse_summary.json:$.status, $.notes`.

**Change:** Add a per-finding stable key (check ID, rule phrase, file, observable) and a fix receipt to `master_chat_tasks/prompts/templates/` and each P12 `RECHECK_FIX.md`: exact files and hunks changed, prior finding ID, disposition and next report link. **Expected gain:** separate true closure from renamed or moved problems. **Could break:** more bookkeeping and unstable line numbers. **Check:** rerun this linkage on a new round and manually verify all same-ID pairs and all NOT RECHECKED rows. Evidence: `QC_FINDINGS.csv`, `FIX_EFFECTS.csv`, `scripts/build_l1.py`.

# 3. New errors after fixes

**Finding.** `FIX_EFFECTS.csv` has 27 links from a new or newly exposed next-round finding to a file/criterion documented as edited. The match is by task, adjacent round, new finding, and the same named file in a P12 change note or changed-hunk table; explicit report comparisons supplement this. This is the requested operational “caused by fix” label; **INFERRED**, because the record does not isolate a single edit. It extends S4's 11-row `FIX_MAP.csv` without copying its broad score-history rows. The sharp examples are: cold-chain v4→v5 corrected corridor prose but created a 30/31 cold-room contradiction and took checks from 33 to 54 (`QC/reports/cold-chain-backbone-quote/v5.md:386-393`); schema v13→v14 removed the planner give-up and bounded child time but introduced TS-11 scheduling-dependent scoring and a stale DS-14 note (`QC/reports/schema-migration-plan-repair/v14.md:348-353`); district v9→v10 narrowed an import negative and left `_or_network` in its name (`QC/reports/district-heat-flex-procurement/v10.md:389-393`). Evidence: `FIX_EFFECTS.csv`, `scripts/build_l1.py`, S4 `FIX_MAP.csv`.

**Change:** Add a side-effect receipt to `QC_FIX_PLAYBOOK_v3.md`: for every edited file, recheck its contract statement, oracle, test name/weight, judge overlap and TRUTH prose, then run the next QC comparison. **Expected gain:** catch the documented stale-prose and weight/count regressions before a new round. **Could break:** broad receipt scope can slow small fixes. **Check:** replay the 27 indexed links against source diffs; keep `INFERRED` until a hunk directly changes the faulty behavior. Evidence: `FIX_EFFECTS.csv:matched_file,why_linked,fix_evidence`.

# 4. Recurring check recipes

**Finding.** `FIX_RECIPES.md` covers the top 20 check IDs by distinct tasks, excluding unclassified IDs; its examples cite the report, next-round disposition and any P12 note. The highest-frequency IDs are DS-22 and JD-5 (14 tasks each), AL-27 (13), TS-23 (12), then DS-27, AL-2, TS-13 and JD-15 (11 each). Evidence: `parse_summary.json:$.check_tasks`, `FIX_RECIPES.md`, `scripts/write_outputs.py`.

**Change:** Put each recipe's one-line build-time action in `master_chat_tasks/knowledge/QC_FIX_PLAYBOOK_v3.md`, with a required cross-file recheck for DS-22, AL-27 and AL-28. **Expected gain:** fewer repeated QC rounds on common faults. **Could break:** applying an old example mechanically to a new task can create wrong fixtures or weights. **Check:** require a live kit rule citation and one task-specific counterexample for each applied recipe. Evidence: `FIX_RECIPES.md`, `QC_FINDINGS.csv`.

# 5. Rounds and sole blockers

**Finding.** Report counts by task are below. These count existing QC report versions, not necessarily all build/fix attempts. Evidence: `find TB/QC/reports -maxdepth 2 -name 'v*.md'` (95 files), `parse_summary.json:$.rounds`, `ROUNDS.csv`.

| Task | QC reports |
|---|---:|
| assay-plate-triage | 1 |
| b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042 | 3 |
| caldermoor-commitment-closure | 1 |
| cohort-retention-reconciliation | 5 |
| cold-chain-backbone-quote | 5 |
| dispatch-plan-reoptimization | 8 |
| district-heat-flex-procurement | 11 |
| emberforge-vault-settlement | 9 |
| match-replay-desync-audit | 7 |
| metered-usage-rating-pipeline | 4 |
| outage-window-replan | 2 |
| schema-migration-plan-repair | 14 |
| sensor-network-lsq-correlated-adjustment | 2 |
| sentinel-policy-recompute | 9 |
| tariff-engine-audit-repair | 5 |
| vendor-archive-roundtrip-recovery | 6 |
| warrant-asof-entitlement-compiler | 3 |

A sole active fail appeared in 16 rounds with a later report; it was the only fail in that round, though minors/warns and other work may also have motivated the recheck. Evidence: `ROUNDS.csv:sole_fail_forced_next_round`.

| Round | Sole fail ID | Report |
|---|---|---|
| cold-chain-backbone-quote v2 | AL-2 | `TB/QC/reports/cold-chain-backbone-quote/v2.md` |
| dispatch-plan-reoptimization v7 | AL-28 | `TB/QC/reports/dispatch-plan-reoptimization/v7.md` |
| emberforge-vault-settlement v2 | AL-2 | `TB/QC/reports/emberforge-vault-settlement/v2.md` |
| match-replay-desync-audit v4 | DS-22 | `TB/QC/reports/match-replay-desync-audit/v4.md` |
| match-replay-desync-audit v5 | CL-4 | `TB/QC/reports/match-replay-desync-audit/v5.md` |
| metered-usage-rating-pipeline v2 | AL-27 | `TB/QC/reports/metered-usage-rating-pipeline/v2.md` |
| metered-usage-rating-pipeline v3 | AL-27 | `TB/QC/reports/metered-usage-rating-pipeline/v3.md` |
| schema-migration-plan-repair v2 | DS-27 | `TB/QC/reports/schema-migration-plan-repair/v2.md` |
| schema-migration-plan-repair v4 | AL-27 | `TB/QC/reports/schema-migration-plan-repair/v4.md` |
| schema-migration-plan-repair v5 | IN-16 | `TB/QC/reports/schema-migration-plan-repair/v5.md` |
| schema-migration-plan-repair v6 | DS-22 | `TB/QC/reports/schema-migration-plan-repair/v6.md` |
| schema-migration-plan-repair v13 | DS-20 | `TB/QC/reports/schema-migration-plan-repair/v13.md` |
| sentinel-policy-recompute v3 | TS-26 | `TB/QC/reports/sentinel-policy-recompute/v3.md` |
| sentinel-policy-recompute v7 | CL-2 | `TB/QC/reports/sentinel-policy-recompute/v7.md` |
| sentinel-policy-recompute v8 | CL-1 | `TB/QC/reports/sentinel-policy-recompute/v8.md` |
| tariff-engine-audit-repair v3 | DS-22 | `TB/QC/reports/tariff-engine-audit-repair/v3.md` |

**Change:** Record `next_round_reason` in each QC report and board decision; label a check “forced” only when the decision explicitly says it blocked progress. **Expected gain:** a defensible round-cost ranking. **Could break:** retroactively calling a sole fail causal would overstate the evidence. **Check:** compare each next-round reason to its prior report and P12 note. Evidence: `ROUNDS.csv`, `QC_FINDINGS.csv`, `master_chat_tasks/decisions.jsonl` (not independently matched here, **UNVERIFIED**).
