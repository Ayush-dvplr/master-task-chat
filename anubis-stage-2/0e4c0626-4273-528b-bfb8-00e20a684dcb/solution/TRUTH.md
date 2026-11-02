# TRUTH.md - 0e4c0626-4273-528b-bfb8-00e20a684dcb

## Defect

Nothing is broken in code; the close itself is the work. `/app/data` holds fifty exports (42 authoritative sources and documents, 8 mirrors, drafts and working copies) of the October 2025 build-minute chargeback for four CI fleets: about 550,000 data rows in 20 formats (csv, tsv, jsonl, jsonl.gz, xlsx, json, xml, sqlite, log, yaml, toml, ini, md, html, docx, pdf, fixed-width text, mbox, ics and a lockfile). Every file is at least 10,000 rows. Almost every row is written in a codec chosen by a context that lives in another file, and the correct figure for one attempt passes through a chain of up to nine files. The deliverable is `/app/out/settle.py` plus the thirteen artifacts it writes. The program is rerun on a freshly generated close with new identifiers, values and convention placements, so every figure has to come from the written rules.

Concepts (all load-bearing), and the chain they form: corrected start (C1) -> runner revision and placement (C2) -> exclusion order with errata and deferred approvals (C3) -> billable seconds at SKU granularity (C4) -> bitemporal rate resolution (C5) -> exact rational cost with one half-even rounding (C6) -> last-match ownership with renames (C7) -> effective-dated team and merged cost center (C8) -> ledger roll-forward (C9). A second chain: Cargo caret toolchain resolution (C10) -> invalidation closure over src and toolchain edges (C11) -> cache outcome classification with hermeticity, evictions and staleness (C12) -> cache credit -> team net. Expert-only variants: Cargo caret on 0.x (C10; 666 visible-close resolutions change under an npm-style caret), half-open drain windows with SEQUENCE supersession (C3), last-match-wins ownership with negation (C7; the owner of 10,167 of 10,200 visible targets changes under first-match and 1,114 under ignoring negation), monotonic durations under clock skew (C1), recorded-at bitemporality with a knowledge cutoff (C5).

1. (focal) Codec conventions. Each coded column is written in a codec that depends on a context taken from another file (the runner's first placement region, the job register target's language, the handle's org, the vendor locale, or a printed batch). The Field conventions tables are spread over seven documents. The header names lie: `duration_ms` columns hold microseconds, nanoseconds or decimal seconds in some segments.
2. (focal) Corrected start. Reported starts inside a clock_sync.txt window are ahead by the window skew; durations come from monotonic counters, never wall-clock differences.
3. (focal) Runner revision and placement. The revision in force at the corrected start decides SKU, class, spot and region; the region comes from the Runner placements table, which overrides fleet_policy.ini.
4. (focal) Exclusion order. Out of period, revoked, provider drain (highest SEQUENCE, CANCELLED ignored, half-open), platform cancel (origin only in the v3 mirror), quarantined flake (inclusive windows, every failing case), preemption grace, retry budget, exempt scope; first match wins.
5. (focal) Deferred errata. An erratum changes the status only when its latest decision by Decided-At, at or before the cutoff, is APPROVED; the mail Date header lags.
6. (focal) Bitemporal rates. Rows recorded after the cutoff are ignored, a later recorded_at wins for the same effective instant, and the applicable row is the latest effective at the corrected start.
7. (focal) Exact cost. Billable seconds round up to SKU granularity; the cost multiplies class, spot and reservation factors exactly and rounds once, half to even.
8. (focal) Ownership. Last matching pattern wins, a trailing negation unowns, `*` stops at `/` and `:`, unowned targets fall back to the job submitter, renames effective by the cutoff apply, and roster and cost-center rows stay under the earlier name. In the visible close 10,169 of 10,200 targets match more than one registry line; first-match changes 10,167 owners, ignoring negation changes 1,114 and fnmatch-style globbing changes 14.
9. (focal) Toolchain resolution and invalidation. Cargo caret (0.x locks the minor; 666 visible-close resolutions differ under an npm-style caret), integer semver comparison, yanks at or before the instant, and closure through src and toolchain edges only.
10. (focal) Cache outcomes. Replay by home shard, then miss, non-hermetic hit, evicted hit (eviction after the last archive write and at or before the lookup), stale hit (resolution changed since the write), and hit. 467 visible non-hermetic hits also have a qualifying eviction, so the non-hermetic check must come first.
11. (drift) Re-exports. A row repeated field for field is one record, which changes control figures and source audit counts.
12. (drift) Header drift. Tabular exports restate a reordered header mid-file, and keyed exports rename one column after a documented record.
13. (drift) Mixed encodings. Text exports carry Latin-1 lines among UTF-8 lines; CSV notes carry quoted commas and newlines.
14. (drift) Wall-clock zones. local and iso_off times are in the runner's clock zone, including EU fall-back with the +fold marker and the AU spring-forward.
15. (drift) Cost-center merges and transfers are effective-dated, and so are team transfers.
16. (drift) Invoice weeks. The last week ends at the period end; status priority is closed, match, credited, mismatch (213 visible closed lines bill exactly the computed amount, so closed must win over match).
17. (trap) attempt_events_v3.jsonl looks newer and more complete but is a mirror: its starts are uncorrected, about 5% of its durations drift and its statuses apply unapproved errata. Only cancel_origin is authoritative.
18. (trap) usage_export_legacy.log looks discardable, yet its REVOKE lines are the only revocations.
19. (trap) lookups_archive.jsonl.gz looks like an old archive; its write records are the only cache write times, and its mirrored lookups must never be counted.
20. (trap) toolchain_pins_resolved.json offers precomputed versions under a naive caret reading and string version order; only its digest table is authoritative.
21. (trap) ownership_patterns_approved.tsv is labelled approved but flattens ownership with first-match semantics (its map rows name the wrong owner for 10,167 of 10,200 visible targets); only its handle_rename rows count.
22. (trap) rate_card_final.xlsx is labelled FINAL and includes rows recorded after the cutoff; only its Spot credits sheet counts.
23. (trap) invoice_restatement.csv restates amounts from the decoy rate world; only its dispute_closure rows count.
24. (trap) control_totals_draft.html counts re-exports in its draft figures; its annex block figures and Late voids list are final.
25. (trap) The attempt-row target is stale for about 4% of jobs; the job register wins.
26. (trap) fleet_policy.ini keeps the base region for moved revisions.
27. (trap) A drain window ending exactly at an attempt start does not cover it.
28. (trap) A quarantine window starting one second after an attempt start does not cover it.
29. (trap) An eviction in a foreign shard never evicts; one at the same second as the lookup does.
30. (trap) Data edges look like dependencies but never propagate invalidation.
31. (trap) Reviewer flags (dup?, void?, late?, recheck) mean nothing; acting on them corrupts bait rows.
32. (trap) Reissued annex blocks publish pre-reissue figures that are expected to disagree.
33. (trap) Case-distinct twin targets are both real; folding case merges two owners.
34. (trap) Postings that reverse or are reversed both drop out; voids come from the draft list.

The reference is Python 3.12 standard library only: a 1181-line driver that installs and runs the close program. Oracle figures reported here are scores of the deterministic channel only.

## Load-bearing work

14 artifacts are collected, and every one of them is graded:

- `/app/out/settle.py`
- `/app/out/attempts.jsonl`
- `/app/out/lookups.jsonl`
- `/app/out/targets.jsonl`
- `/app/out/actions.jsonl`
- `/app/out/artifacts.jsonl`
- `/app/out/invoice_reconciliation.jsonl`
- `/app/out/team_chargeback.json`
- `/app/out/cost_center_ledger.json`
- `/app/out/rate_resolution.json`
- `/app/out/cache_effectiveness.json`
- `/app/out/control_reconciliation.json`
- `/app/out/source_audit.json`
- `/app/out/close_summary.json`

Every input file contributes rows that reach a graded artifact. A global invariant also ties all fifty files to every output: each file's primary table is covered block by block in the annex controls, and the annex's own blocks are covered in the draft. Every row's control column therefore enters control_reconciliation.json and close_summary.json.

## Verification

Grader entrypoint: `tests/test.sh`. It hardens the verifier and runs `exec rewardkit /tests --workspace /app --output /logs/verifier/reward.json`. Channel A (`tests/test_output.py`) holds the corpus generator itself. It rebuilds the visible close's truth from the sample seed and compares the artifacts in `/app/out` field by field. It then generates a hidden close from `EVAL_SEED = 2339907786676870586`, runs the delivered program three times (twice in one directory, once relocated) and compares the hidden artifacts. A canary close from `CHALLENGE_SEED = 7647325660253833414` sits at the default input location to expose a program that ignores its arguments. Channel B (`tests/judge.toml`) grades the trajectory.

Channel A declares 29 positive and 6 negative tests. Its positive weight total is 95 and its negative magnitude is 22. The checks cover attempt timing, revision, status, exclusions, billing and attribution; lookup resolution; target resolution, invalidation and ownership; action hermeticity and toolchains; artifact retention, storage and attribution; invoice reconciliation; ledger balances, postings and charges; rates; controls; team chargeback; cache effectiveness; the close summary; source audit; artifact shape; and the reusable program interface. The six negative checks cover shipped-answer hardcoding, path-dependent behavior, reads from the default training corpus, nondeterminism, writes outside the output directory and input mutation.

Channel B declares 24 positive and 7 negative criteria. Its positive weight total is 74 and its negative magnitude is 27. The positive criteria grade post-write comparisons against freshly derived values for each settlement domain, narrow exception handling, written errata precedence, the pre-run and post-run data hash comparison, and the required final explanation of demoted exports. The negative criteria cover grader access, finalizing before control reconciliation, writing decoders before reading convention documents, skipping the copied-corpus comparison, combining the program layers, copying provisional figures and third-party package use.

## Root cause

The close cannot be read file by file. A coded column's codec depends on a context from a second file, which is itself coded under a context from a third. An attempt's cost depends on clock_sync.txt, fleet_policy.ini, the placements in settlement_authority.md, instance_classes.csv, the granularity table in rate_methodology.pdf, rate_card.xlsx, the Spot credits sheet of rate_card_final.xlsx, close_parameters.toml, amendment_minutes.docx, the errata and approval mail, the drain calendar, junit and quarantine windows, retry_policy.yaml, scope_rules.md and the job register. Each locally sensible reading (trust the header unit, trust the newest file, trust the FINAL label, fold case, first match wins, carets lock the major, round half up) yields plausible intermediate figures. The block controls in audit_annex.pdf falsify the decoding of each file's control column and its re-export handling: a wrong codec or a counted re-export in that column shows up as a disagreeing block, and only reissued blocks may disagree. Decoding errors in other columns are caught by the invoice lines and the hidden-corpus run, not by the controls.

## Solution shape

1. Parse every file into rows by format, honouring restated headers, aliases, mixed encodings and fixed-width layouts.
2. Gather every Field conventions, Column aliases, Source catalog, Context dimensions, Codec glossary, Sentinel register, Region zones and Fixed-width layouts table from all documents.
3. Decode in dependency order: placements, package metadata and roster (batch context); then vendor statements, revisions, SKUs and rates; then the job register; then attempts, errata, mail, junit; then the cache, target, artifact, invoice and ledger files.
4. Remove re-exports, apply the written rules, and write the thirteen artifacts sorted and compact.
5. Recompute every annex block and confirm that only reissued blocks disagree.

## Ordered plan

1. Read settlement_authority.md fully, then every document's tables. R23 penalizes writing coded-column decoders first.
2. Build the readers and confirm the block controls file by file. R22 penalizes finalizing the decoding first.
3. Implement the attempt chain and check it against the invoice lines; most vendor lines match exactly.
4. Implement toolchain resolution, invalidation and cache outcomes.
5. Settle conflicts by the Precedence table. R18 checks the errata precedence decision.
6. Run the program on a copy elsewhere and compare (R24); keep reading, decoding, rules and writing separate (R25) with narrow exception handling (R17).
7. Close with a message naming the demoted exports and the rule behind each (R20).

## Pitfalls

- Trusting header units, the newest-looking file or the FINAL label.
- First-match or most-specific ownership instead of last match.
- npm-style caret on 0.x, or string version order.
- Wall-clock durations, or ignoring clock skew windows.
- Counting archive mirror lookups, foreign-shard evictions or data edges.
- Applying errata that were never approved, or by the mail Date header.
- Half-up rounding, or rounding per factor.
- Treating reviewer flags as voids or duplicates.

### Corpus inventory (measured)

`primary-table rows` counts the data rows of each file's primary table (the table the Source catalog names), re-exports included.

| file | type | primary-table rows | role |
|---|---|---|---|
| action_keys.lock | lock | 10280 | in scope |
| amendment_minutes.docx | docx | 10295 | in scope |
| approval_thread.mbox | mbox | 10304 | in scope |
| artifact_registry.db | db | 10300 | in scope |
| attempt_events.jsonl | jsonl | 10302 | in scope |
| attempt_events_v3.jsonl | jsonl | 10296 | decoy |
| audit_annex.pdf | pdf | 10680 | in scope |
| change_freeze.ics | ics | 16465 | in scope |
| clock_sync.txt | txt | 10269 | in scope |
| close_parameters.toml | toml | 10290 | in scope |
| control_totals_draft.html | html | 10897 | decoy |
| cost_centers.csv | csv | 10793 | in scope |
| edges.csv | csv | 10300 | in scope |
| env_allowlist.json | json | 10299 | in scope |
| errata_register.docx | docx | 10300 | in scope |
| evictions.log | log | 10322 | in scope |
| field_precedence.html | html | 19427 | in scope |
| flaky_windows.tsv | tsv | 10301 | in scope |
| fleet_north.log | log | 10301 | in scope |
| fleet_policy.ini | ini | 10296 | in scope |
| fleet_south.log | log | 10288 | in scope |
| gc_events.csv | csv | 10295 | in scope |
| input_manifests.tsv | tsv | 10321 | in scope |
| instance_classes.csv | csv | 10305 | in scope |
| invoice_lines.xlsx | xlsx | 10321 | in scope |
| invoice_restatement.csv | csv | 10806 | decoy |
| junit_results.xml | xml | 10297 | in scope |
| lookups_archive.jsonl.gz | jsonl.gz | 24773 | decoy |
| lookups_shard1.jsonl | jsonl | 10300 | in scope |
| lookups_shard2.jsonl | jsonl | 10286 | in scope |
| lookups_shard3.jsonl.gz | jsonl.gz | 10293 | in scope |
| opening_balances.json | json | 10292 | in scope |
| owners_registry.txt | txt | 10291 | in scope |
| ownership_patterns_approved.tsv | tsv | 10566 | decoy |
| package_metadata.xml | xml | 10300 | in scope |
| rate_card.xlsx | xlsx | 11369 | in scope |
| rate_card_final.xlsx | xlsx | 11514 | decoy |
| rate_methodology.pdf | pdf | 10284 | in scope |
| retry_policy.yaml | yaml | 10290 | in scope |
| scope_rules.md | md | 10282 | in scope |
| settlement_authority.md | md | 10324 | in scope |
| settlement_ledger.db | db | 10300 | in scope |
| shard_index.tsv | tsv | 10312 | in scope |
| targets.csv | csv | 10300 | in scope |
| team_roster.xlsx | xlsx | 10293 | in scope |
| toolchain_pins.yaml | yaml | 10298 | in scope |
| toolchain_pins_resolved.json | json | 10296 | decoy |
| usage_events.jsonl | jsonl | 10313 | in scope |
| usage_export_legacy.log | log | 10646 | decoy |
| vendor_statement.xml | xml | 10299 | in scope |

Totals: 549571 primary-table rows, 52.39 MB, 20 formats.

### Decoys

| decoy | why it looks authoritative | rule that demotes it | what it alone supplies |
|---|---|---|---|
| attempt_events_v3.jsonl | newer schema, more columns | settlement_authority.md S-3 | cancel_origin |
| usage_export_legacy.log | legacy label, garbled export | settlement_authority.md S-3 | REVOKE lines |
| lookups_archive.jsonl.gz | archive of the lookups | settlement_authority.md S-15 | cache write times |
| toolchain_pins_resolved.json | precomputed versions | scope_rules.md Constraints | digest table |
| ownership_patterns_approved.tsv | approved label | settlement_authority.md S-13 | handle renames |
| rate_card_final.xlsx | FINAL label | rate_methodology.pdf Rate | spot credits |
| invoice_restatement.csv | restated amounts | field_precedence.html Precedence | dispute closures |
| control_totals_draft.html | control figures | settlement_authority.md S-17 | annex block figures, late voids |

### Check table

The deterministic channel contains 35 checks: 29 positive checks worth 95 and 6 negative checks with magnitude 22. Core billing and attribution errors cost 5; important settlement sub-goals cost 3; shape, source-audit and interface details cost 1. A single failed core property therefore removes 5/95 of the test-channel score. The judged channel contains R1 through R31: 24 positive criteria worth 74 and 7 negative criteria with magnitude 27. Each post-write domain comparison costs 3, while the data-integrity verification costs 5.

### Expert time

About 28 hours. Reading the seven rule documents and the fifty files: 6 h. Twenty format readers with header drift, aliases, mixed encodings and fixed-width layouts: 6 h. The convention interpreter and the decode dependency order: 5 h. The attempt chain, errata, drains, quarantine and rates: 5 h. Toolchain resolution, invalidation and cache outcomes: 3 h. Invoices, ledger and controls, then debugging against the annex: 3 h.



## Provenance

```yaml
uuid: 0e4c0626-4273-528b-bfb8-00e20a684dcb
instance_id: 0e4c0626-4273-528b-bfb8-00e20a684dcb
task_name: terminal-bench/0e4c0626-4273-528b-bfb8-00e20a684dcb
fix_patch_sha256: d2822d76339eedd74cd69172693f190f81b2abc8045421e84b5d954c3d3bbd23
solve_py_sha256: 3c70af4f04bd14002266fee4b6f70054debcb74ad0f9d897691ffd2fa7aa7ea9
language: python
golden_score_measured: 1.0  # test channel only
golden_score_channel_a_pct: 100
golden_score_channel_b_pct: null  # the judged channel has no oracle score
golden_score_runs: 1
golden_score_trial_id: null
golden_score_verified_by: >
  One local direct execution of the bundled oracle through every deterministic
  criterion read 1.000 (95 of 95). This was not a Harbor trajectory run.
caveat: >
  The test channel carries 29 positive checks worth 95 weight and 6 negative
  checks worth -22 weight. The judged channel carries 24 positive criteria
  worth 74 and 7 negative criteria worth -27.
  tests/reward.toml divides each channel's weighted sum by its positive
  total and gives each half of the reward, so the combined reward runs from
  -1.000 to +1.000 with no clamp.
```
