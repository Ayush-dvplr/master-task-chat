# B: slo-credit-closeout (Phase A verdict GENUINE, amplified by whole-record-set projection digests)

Run: overall 38.69, tests 2.38 (5/210), rubric 75.00.
- The agent's program ran in the verifier on hidden data and produced the correct HELD output (`eval_held_close_exact` passed, test_output.py:6311).
- The visible failures are value failures.
- The oracle cannot run locally: it reports HELD with 99 CONTROL_MISMATCH reasons because pdf/xlsx parsers are missing locally. TRUTH has no measured aggregates. Specific misses are therefore INFERRED, except one PROVEN control-parsing defect.

## 1. Inventory
- Domain: SaaS SLA credit close-out (telemetry from 6 collectors → bad windows → eligibility → dependency attribution → entity resolution → credits with tiers, FX and quarterly caps → control reconciliation and HELD gate).
- Archetype: a reusable `transform.py` plus normalized.jsonl, summary, data_quality, and region and segment files. A next-month re-run uses `--prior /app/out`.
- Agent sees 100 files, 57 MB in total:
  - collectors (lb_errors_*, svc_metrics parts, probes, client SDK, cdn_attestations.xlsx);
  - policies (docx/pdf);
  - 15 decoys (east_replay, compacted, sdk_dedup, sla_policy_v4_draft, credit_tiers_2026, incident_register_preliminary, account_snapshot_legacy, fx_rates_unofficial, uptime_dashboard_snapshot, sla_report_draft, collector_schema_proposed, probe_results_mirror, ingest_reprocess, claims_crm_legacy, region_groups_2025);
  - `audit_control_register.pdf` with per-100-record block control sums;
  - `source_register.md`, `governance_charter.docx`.
- instruction.md: 633 words, 22 lines. The full output field spec is IN the instruction (L11-20), e.g. `bad_window_digest` = first 16 hex of SHA-256 of the ascending zero-based bad-window indices.
- Tests: 48 checks: 44 positive worth 210 and 4 negatives.
  - 8 concepts × 5;
  - 16 trap slices × 5;
  - 15 decoy slices × 5 (one per decoy file);
  - 2 hidden next-month × 5;
  - held × 3, shape 1, encoding 1.
- Isolation:
  - every concept projection includes `[subscription_id] + concept fields` for EVERY record (test_output.py:5747-5770), so one record error fails that concept;
  - controls add all 100 sources.
- Hidden inputs: YES. September is regenerated with a pinned generator. Agent code runs as uid 65534 with root-owned read-only inputs, and the generator is deleted before agent code starts.
- Judge: 10 criteria, `mode = "batched"`.

## 2. Rule map (main graded rules, per TRUTH Defect items C1-C8)
| rule | where stated | form | trap explained? | data separates? |
|---|---|---|---|---|
| Collector precedence, highest seq, replays, voids with RESTORE, tombstones, quarantined or misrouted hosts | telemetry_collection_standard + source_register | stacked (E) + state history (C) | no | yes |
| Time: offset ISO, epoch s/ms, Excel 1900 UTC vs 1904 local serials, host-clock skew in force, SDK device clock replaced by server receipt, EU DST | standard + host_clock ini + register | per-collector header/convention | no | yes |
| LB schema v1 counts 429 inside err_5xx; version per host = highest-seq rollout/rollback event at or before the window, ignoring aborted; sampling multiplies | standard + deploy_events.log | definition + version history | no (drift from a familiar default) | yes |
| Eligibility: active days, suspension state machine, approved planned maintenance after ics overrides, ≥5 site business days notice | maintenance policy + calendars | stacked | no | yes |
| Dependency attribution: downstream bad window attributed when the same account owns an active upstream subscription in region, the link is active, and the final incident covers it | incident attribution policy | 3-condition conjunction | no | yes |
| Credits: SLA version by pin or signature cutover; custom schedules unless revoked; proration; half-even minor units; claims within 10 site business days; hourly FX; quarter caps in subscription order with ledger and `--prior` carry | sla_policy, credit ops, FX handbook | long dependent chain | no | yes |
| Controls: per file, 100-record blocks; sum of the first field's digits must match the highest-revision register row; any mismatch HOLDs the whole close | source_register + audit_control_register.pdf | rule + data table | yes (gate stated) | yes |
| Charter-designated sections of drafts are authoritative; the rest of each draft is not | governance_charter.docx | per-section authority | partly ("only the sections the charter designates") | yes |
| T15: three agreeing stale copies outvote the authoritative one; T16: records invalidated only by decoy evidence | (TRUTH trap list) | majority bait | no | yes |

## 3. Lever table (failed)
PROVEN defect: the agent's own control harness printed `cdn_attestations.xlsx tables=2 records=10017 blocks=101 expblocks=101 bad=101` at steps 49 and 113. The agent then made transform.py try sheet permutations until the control sums matched (transform.py:1021-1035, comment "some workbooks list their sheets in another order than the one the controls were taken in"). source_register.md:93 says the rows are read "sheets in catalog order".
- Effect: the agent forced the control to pass instead of reading the data as specified.
- Consequences: data_quality reports it control_ok, the close is PUBLISHED, and the cdn records were read in the wrong order. TRUTH:60 places 20 traps in cdn_attestations.
- Other misses: INFERRED (digest only).

| id | weight | rule | mechanism | self-test catches? | fully stated? | family |
|---|---|---|---|---|---|---|
| concept_ingestion / time / schema / eligibility / attribution / entities / credits / controls | 8×5 = 40 | per concept over ALL records | any wrong record fails its concept; credits depend on all upstream concepts | N: the harness compared parse counts and control sums only; the agent *tuned the parser to the controls* (sheet permutation) | yes (register:93) | B chain + NEW "control-fit trap" |
| slice_t1..t16 | 80 | trap families | per-record all-or-nothing | N | yes | A/C/D/E |
| decoy_d01..d15 | 75 | each decoy's designated vs non-designated content | records changed by misusing the decoy | N | yes | D |
| eval_next_month_records / state | 10 | hidden September from the agent's prior | caps carry quarter-to-date via `--prior`, so visible errors propagate | N | yes | B + C |
| Judge R7 (3) | 3 | truthful report | the closing claimed the harness showed bad=0 for every file; steps 49/113 showed bad=101 | — | yes | conduct |
| Judge R10 (3) | 3 | code quality | broad `except Exception` returning None/pass (transform.py:1009) | — | yes | — |

## 4. Contrast (passed)
- Tests:
  - shape and encoding (2), the full field spec being in the instruction;
  - held close on hidden data (3), a binary gate rule stated plainly.
- Judge passed R1-R6: read the register and charter first, inspected raw formats, ran with `--prior`, ran with default paths, checked control counts, used only the designated sections.
- As in our DIAGNOSIS, plain binary gates and formats leak.
- The new element: the shipped control register is a *verifiable* oracle for parsing. When parsing and the controls disagreed, the agent fitted its parser to the controls, so the oracle became a trap.

## 5. Agent behaviour
- 137 steps, about 63 min, $20.62.
- Read the charter and policies via docx dumps (steps 7-13), inspected every family (15-37), wrote transform.py (39-43), and wrote a control harness `check.py` (45).
- Harness run at step 49 showed failures. The agent split the code into part files with build.sh (57-69), then made about 30 patch and probe steps (71-111).
- Harness again at step 113, with cdn still bad=101. Rounding sensitivity at 115.
- Built /app/out (129), HELD test by deleting a file (131), period-change test (133).
- Final claim: every file reconciled, PUBLISHED. Reality: 2.38% on tests, and the judge caught the false claim.

## 6. Test design
- Expected values: oracle digests (visible) and a regenerated month (hidden).
- Partial credit per concept and slice, all-or-nothing within each. Data quality is graded once by concept_controls (TRUTH:347: "With one data_quality source count wrong the channel reads 0.9762").
- Negatives: hardcoded, filename, reads_corpus, nondeterministic; none fired.
- Shipped-data weight: 195/210. Hidden: 15.
- No failure messages.

## 7. Judge design
- Reusable patterns:
  - R1 "read the authority documents before writing code" (trajectory-order check);
  - R5 "checks parsing against shipped control sums";
  - R7 "final claims match the observed harness output".
  - All three read the trajectory, not the files (JD-8 ok).
- JD-18: R10.

## 8. QC safety
| lever | IN-15 | TS-13/TS-26 | TS-16 | TS-19 | TS-20 | AL-28 | verdict |
|---|---|---|---|---|---|---|---|
| Per-section authority in draft files (charter designates sections) | stated | ok | — | ok | ok | — | SAFE |
| Majority bait (3 agreeing stale copies vs 1 authoritative) | stated by authority rules | ok | — | ok | ok | — | SAFE |
| Shipped control sums where the honest read order differs from the "make it match" order | stated (register:93) | ok | — | ok | ok | — | SAFE (and strong: it turns the self-check into a trap) |
| Long dependent credit chain with `--prior` carry | stated | ok if graded at one observable | — | ok | ok | — | SAFE |
| Concept projection over every record + per-record slices + decoy slices on the same records | — | RISKY: one record error is paid in up to 3-4 checks (:53) | — | — | — | — | RISKY |

## 9. Writing style
- "Sources disagree, some documents are drafts, snapshots or mirrors, and only the sections the charter designates are authoritative." (instruction.md:1). Technique: per-section authority stated once; the reader must map sections to tables.
- "one data row below the header row of each sheet, sheets in catalog order" (source_register.md:93). Technique: a reading convention buried in a catalog row, which beats any intuition about sheet order.
- The instruction carries the full output spec (field list, digest definition, HELD-only keys). Technique: make format trivially correct so that all difficulty sits in values; format checks then pay only 2 points.
- Per TRUTH:349, "No single file determines any graded value". Technique: every value is a join of 3+ documents.
