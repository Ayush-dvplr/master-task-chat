# Kestrel CI build-minute settlement authority, October 2025 close

This document is the settlement authority for the October 2025 build-minute close of the Kestrel monorepo CI fleets. Where any export, mirror, draft or working copy disagrees with a rule written here or in the documents this one names (scope_rules.md, field_precedence.html, rate_methodology.pdf, amendment_minutes.docx, errata_register.docx, audit_annex.pdf), the written rule decides. Some exported values are wrong or superseded by design; the rules below say which.

S-1 Period. An attempt belongs to the close when its corrected start instant t satisfies 2025-10-01T00:00:00Z <= t < 2025-11-01T00:00:00Z. Attempts outside it are still listed, with exclusion out_of_period.

S-2 Knowledge cutoff. The close knows what was recorded at or before 2025-11-04T00:00:00Z. Rate rows recorded after it, approval decisions taken after it, amendments ratified after it and handle renames effective after it have no effect.

S-3 Attempt sources. fleet_north.log, fleet_south.log, attempt_events.jsonl and usage_events.jsonl are the attempt records of fleets north, south, east and west. attempt_events_v3.jsonl and usage_export_legacy.log are mirrors and never supply attempts, starts, durations or statuses; attempt_events_v3.jsonl is the only source of cancel_origin and usage_export_legacy.log is the only source of REVOKE lines.

S-4 Corrected start. Runners report wall-clock starts. clock_sync.txt lists windows of reported time [window_from, window_to) during which a runner clock ran ahead by skew_ms (negative means behind). A reported start inside a window of that runner is corrected by subtracting the skew; a reported start outside every window is already correct.

S-5 Durations. An attempt duration is the difference of its monotonic counters (mono_end minus mono_start in the fleet logs) or the duration field of the east and west records. Wall-clock end times are informational.

S-6 Runner revision. The revision in force at the corrected start is the one with the greatest effective_from not after it. Its sku gives instance class, architecture and spot status through instance_classes.csv. The region of a revision is the one in the Runner placements table of this document, which overrides the region written in fleet_policy.ini.

S-7 Re-exports. A data row that repeats an earlier row of the same file field for field is a re-export and is one record.

S-8 Reviewer annotations. The flag column, X-REVIEW-FLAG property, Flag body line and flag key are reviewer annotations with no settlement meaning; WARN log levels only mirror them.

S-9 Column aliases. Some exports renamed one column part way through; the Column aliases tables give the alias and the column it stands for. Tabular exports instead restate the header in a new column order; read every header.

S-10 Conventions. Coded columns are written in a codec that depends on the row's context. Wall times in the local and iso_off codecs are in the clock zone of the runner the row is about. The Field conventions tables list, for every file, coded column and context value, the codec in force. Context dimensions and the Codec glossary define the terms. Columns not listed use the first codec of their kind in the glossary.

S-11 Exclusions, applied in this order, first match wins: out_of_period; revoked (a REVOKE line for the attempt); provider_drain (corrected start inside [DTSTART, DTEND) of a drain event on the attempt's runner, using the highest SEQUENCE of each UID and ignoring events whose final status is CANCELLED); platform_cancel (final status cancelled and cancel_origin platform); quarantined_flake (final status failed and every testcase junit_results.xml lists for the attempt has a quarantine window for the attempt's target and that testcase with from <= start <= until); preempt_grace (final status preempted and duration below the fleet grace in retry_policy.yaml); over_budget (attempt number above the job budget in retry_policy.yaml, default from its defaults table); exempt_scope (target scope exempt in scope_rules.md).

S-12 Final status. The status on the attempt record, replaced by the new value of an erratum whose latest decision at or before the cutoff is APPROVED (errata_register.docx, approval_thread.mbox).

S-13 Attribution. The target of an attempt is the target of its job in the job register of field_precedence.html, which lists every job; the target written on attempt records is informational. The owner handle of a target is the handle of the last line of owners_registry.txt (by seq) whose pattern matches the label; a pattern starting with ! that is the last match leaves the target unowned. In patterns * matches within one path segment and never matches / or :, ** matches anything. An unowned target's attempts go to the job's submitter. A handle renamed by a handle_rename row of ownership_patterns_approved.tsv effective at or before the cutoff is reported under its new name; roster and cost-center rows stay recorded under the earlier name.

S-14 Team and cost center. The team of a handle at instant t is its Roster row, replaced by a Transfers row effective at or before t. The cost center is the cost_centers.csv row with the greatest effective_from not after t, then followed through the Cost center merges table of field_precedence.html when the merge is effective at or before t. Attempts use their corrected start; targets and artifacts use 2025-10-31T23:59:59Z.

S-15 Cache outcomes. A lookup logged in a shard other than the home shard of its action (shard_index.tsv, prefix = first six characters of the action key) is a replay. Otherwise MISS is a miss; a HIT on a non-hermetic action is nonhermetic_hit; a HIT with an eviction of that action in its home shard at e where last_write < e <= lookup time is evicted_hit, reporting the earliest such eviction; a HIT whose target resolves to a different toolchain version at last_write than at the lookup is stale_hit; anything else is a hit. last_write is the latest write record in lookups_archive.jsonl.gz for the action at or before the lookup. The archive's lookup records are mirrors and never lookups.

S-16 Hermetic actions. An action is hermetic when its input manifest row is declared and every environment variable it reads is in the allowed list of env_allowlist.json.

S-17 Controls. audit_annex.pdf publishes, for every file and every block of 50 consecutive data rows of its primary table in file order, the number of distinct records and the sum of the canonical value of the file's control column over distinct records. Canonical values: timestamps in epoch seconds, durations in milliseconds, money in micro-dollars, integers and byte counts as integers. control_totals_draft.html carries the figures for the annex's own blocks.

S-18 Chargeback. Compute is the cost of billable attempts. Storage is the artifact storage cost. Each lookup with outcome hit earns the cache credit of close_parameters.toml for the team of its attempt. Net is compute plus storage minus cache credit.

**Table: Runner placements**

| runner | rev | region | batch | flag |
|---|---|---|---|---|
| RN-EAST-10003 | 1 | ap-south-5 | B1 |  |
| RN-EAST-10003 | 2 | ap-south-5 | B1 |  |
| RN-EAST-10003 | 3 | ap-south-5 | B1 |  |
| RN-EAST-10003 | 4 | ap-south-5 | B1 |  |
| RN-EAST-10003 | 5 | ap-south-5 | B1 |  |
| RN-EAST-10033 | 1 | eu-central-2 | B1 |  |
| RN-EAST-10033 | 2 | eu-central-2 | B1 |  |
| RN-EAST-10033 | 3 | eu-central-2 | B1 |  |
| RN-EAST-10033 | 4 | eu-central-2 | B1 |  |
| RN-EAST-10033 | 5 | eu-central-2 | B1 |  |
| RN-EAST-10062 | 1 | ap-south-5 | B1 |  |
| RN-EAST-10062 | 2 | ap-south-5 | B1 |  |
| RN-EAST-10062 | 3 | ap-south-5 | B1 |  |
| RN-EAST-10062 | 4 | ap-south-5 | B1 |  |
| RN-EAST-10062 | 5 | ap-south-5 | B1 |  |
| RN-EAST-10089 | 1 | eu-central-2 | B1 |  |
| RN-EAST-10089 | 2 | eu-central-2 | B1 |  |
| RN-EAST-10089 | 3 | eu-central-2 | B1 |  |
| RN-EAST-10089 | 4 | eu-central-2 | B1 |  |
| RN-EAST-10089 | 5 | eu-central-2 | B1 |  |
| RN-EAST-10115 | 1 | ap-south-5 | B1 |  |
| RN-EAST-10115 | 2 | ap-south-5 | B1 |  |
| RN-EAST-10115 | 3 | ap-south-5 | B1 |  |
| RN-EAST-10115 | 4 | ap-south-5 | B1 |  |
| RN-EAST-10115 | 5 | ap-south-5 | B1 |  |
| RN-EAST-10140 | 1 | eu-central-2 | B1 |  |
| RN-EAST-10140 | 2 | eu-central-2 | B1 |  |
| RN-EAST-10140 | 3 | eu-central-2 | B1 |  |
| RN-EAST-10140 | 4 | eu-central-2 | B1 |  |
| RN-EAST-10140 | 5 | eu-central-2 | B1 |  |
| RN-EAST-10172 | 1 | ap-south-5 | B1 |  |
| RN-EAST-10172 | 2 | ap-south-5 | B1 |  |
| RN-EAST-10172 | 3 | ap-south-5 | B1 |  |
| RN-EAST-10172 | 4 | ap-south-5 | B1 |  |
| RN-EAST-10172 | 5 | eu-central-2 | B1 |  |
| RN-EAST-10200 | 1 | eu-central-2 | B1 |  |
| RN-EAST-10200 | 2 | eu-central-2 | B1 |  |
| RN-EAST-10200 | 3 | eu-central-2 | B1 |  |
| RN-EAST-10200 | 4 | eu-central-2 | B1 |  |
| RN-EAST-10200 | 5 | eu-central-2 | B1 |  |
| RN-EAST-10227 | 1 | ap-south-5 | B1 |  |
| RN-EAST-10227 | 2 | ap-south-5 | B1 |  |
| RN-EAST-10227 | 3 | ap-south-5 | B1 |  |
| RN-EAST-10227 | 4 | ap-south-5 | B1 |  |
| RN-EAST-10227 | 5 | ap-south-5 | B1 |  |
| RN-EAST-10256 | 1 | eu-central-2 | B1 |  |
| RN-EAST-10256 | 2 | eu-central-2 | B1 |  |
| RN-EAST-10256 | 3 | eu-central-2 | B1 |  |
| RN-EAST-10256 | 4 | ap-south-5 | B1 |  |
| RN-EAST-10256 | 5 | eu-central-2 | B1 |  |
| RN-EAST-10280 | 1 | ap-south-5 | B1 |  |
| RN-EAST-10280 | 2 | ap-south-5 | B1 |  |
| RN-EAST-10280 | 3 | eu-central-2 | B1 |  |
| RN-EAST-10280 | 4 | ap-south-5 | B1 |  |
| RN-EAST-10280 | 5 | ap-south-5 | B1 |  |
| RN-EAST-10309 | 1 | eu-central-2 | B1 |  |
| RN-EAST-10309 | 2 | eu-central-2 | B1 |  |
| RN-EAST-10309 | 3 | eu-central-2 | B1 |  |
| RN-EAST-10309 | 4 | eu-central-2 | B1 |  |
| RN-EAST-10309 | 5 | eu-central-2 | B1 |  |
| RN-EAST-10342 | 1 | ap-south-5 | B1 |  |
| RN-EAST-10342 | 2 | ap-south-5 | B1 |  |
| RN-EAST-10342 | 3 | ap-south-5 | B1 |  |
| RN-EAST-10342 | 4 | ap-south-5 | B1 |  |
| RN-EAST-10342 | 5 | ap-south-5 | B1 |  |
| RN-EAST-10366 | 1 | eu-central-2 | B1 |  |
| RN-EAST-10366 | 2 | eu-central-2 | B1 |  |
| RN-EAST-10366 | 3 | eu-central-2 | B1 |  |
| RN-EAST-10366 | 4 | eu-central-2 | B1 |  |
| RN-EAST-10366 | 5 | eu-central-2 | B1 |  |
| RN-EAST-10396 | 1 | ap-south-5 | B1 |  |
| RN-EAST-10396 | 2 | ap-south-5 | B1 |  |
| RN-EAST-10396 | 3 | ap-south-5 | B1 |  |
| RN-EAST-10396 | 4 | ap-south-5 | B1 |  |
| RN-EAST-10396 | 5 | ap-south-5 | B1 |  |
| RN-EAST-10423 | 1 | eu-central-2 | B1 |  |
| RN-EAST-10423 | 2 | eu-central-2 | B1 |  |
| RN-EAST-10423 | 3 | eu-central-2 | B1 |  |
| RN-EAST-10423 | 4 | eu-central-2 | B1 |  |
| RN-EAST-10423 | 5 | eu-central-2 | B1 |  |
| RN-EAST-10450 | 1 | ap-south-5 | B1 |  |
| RN-EAST-10450 | 2 | ap-south-5 | B1 |  |
| RN-EAST-10450 | 3 | ap-south-5 | B1 |  |
| RN-EAST-10450 | 4 | ap-south-5 | B1 |  |
| RN-EAST-10450 | 5 | ap-south-5 | B1 |  |
| RN-EAST-10478 | 1 | eu-central-2 | B1 |  |
| RN-EAST-10478 | 2 | eu-central-2 | B1 |  |
| RN-EAST-10478 | 3 | ap-south-5 | B1 |  |
| RN-EAST-10478 | 4 | eu-central-2 | B1 |  |
| RN-EAST-10478 | 5 | eu-central-2 | B1 |  |
| RN-EAST-10504 | 1 | ap-south-5 | B1 |  |
| RN-EAST-10504 | 2 | ap-south-5 | B1 |  |
| RN-EAST-10504 | 3 | ap-south-5 | B1 |  |
| RN-EAST-10504 | 4 | ap-south-5 | B1 |  |
| RN-EAST-10504 | 5 | ap-south-5 | B1 |  |
| RN-EAST-10533 | 1 | eu-central-2 | B1 |  |
| RN-EAST-10533 | 2 | eu-central-2 | B1 |  |
| RN-EAST-10533 | 3 | ap-south-5 | B1 |  |
| RN-EAST-10533 | 4 | eu-central-2 | B1 |  |
| RN-EAST-10533 | 5 | eu-central-2 | B1 |  |
| RN-EAST-10565 | 1 | ap-south-5 | B1 |  |
| RN-EAST-10565 | 2 | ap-south-5 | B1 |  |
| RN-EAST-10565 | 3 | ap-south-5 | B1 |  |
| RN-EAST-10565 | 4 | ap-south-5 | B1 |  |
| RN-EAST-10565 | 5 | ap-south-5 | B1 |  |
| RN-EAST-10589 | 1 | eu-central-2 | B1 |  |
| RN-EAST-10589 | 2 | eu-central-2 | B1 |  |
| RN-EAST-10589 | 3 | eu-central-2 | B1 |  |
| RN-EAST-10589 | 4 | eu-central-2 | B1 |  |
| RN-EAST-10589 | 5 | eu-central-2 | B1 |  |
| RN-EAST-10616 | 1 | ap-south-5 | B1 |  |
| RN-EAST-10616 | 2 | ap-south-5 | B1 |  |
| RN-EAST-10616 | 3 | ap-south-5 | B1 |  |
| RN-EAST-10616 | 4 | ap-south-5 | B1 |  |
| RN-EAST-10616 | 5 | ap-south-5 | B1 |  |
| RN-EAST-10645 | 1 | eu-central-2 | B1 |  |
| RN-EAST-10645 | 2 | eu-central-2 | B1 |  |
| RN-EAST-10645 | 3 | eu-central-2 | B1 |  |
| RN-EAST-10645 | 4 | eu-central-2 | B1 |  |
| RN-EAST-10645 | 5 | eu-central-2 | B1 |  |
| RN-EAST-10678 | 1 | ap-south-5 | B1 |  |
| RN-EAST-10678 | 2 | ap-south-5 | B1 |  |
| RN-EAST-10678 | 3 | ap-south-5 | B1 |  |
| RN-EAST-10678 | 4 | ap-south-5 | B1 |  |
| RN-EAST-10678 | 5 | ap-south-5 | B1 |  |
| RN-EAST-10700 | 1 | eu-central-2 | B1 |  |
| RN-EAST-10700 | 2 | eu-central-2 | B1 |  |
| RN-EAST-10700 | 3 | eu-central-2 | B1 |  |
| RN-EAST-10700 | 4 | eu-central-2 | B1 |  |
| RN-EAST-10700 | 5 | eu-central-2 | B1 |  |
| RN-EAST-10734 | 1 | ap-south-5 | B1 |  |
| RN-EAST-10734 | 2 | ap-south-5 | B1 |  |
| RN-EAST-10734 | 3 | ap-south-5 | B1 |  |
| RN-EAST-10734 | 4 | ap-south-5 | B1 |  |
| RN-EAST-10734 | 5 | ap-south-5 | B1 |  |
| RN-EAST-10756 | 1 | eu-central-2 | B1 |  |
| RN-EAST-10756 | 2 | eu-central-2 | B1 |  |
| RN-EAST-10756 | 3 | eu-central-2 | B1 |  |
| RN-EAST-10756 | 4 | eu-central-2 | B1 |  |
| RN-EAST-10756 | 5 | eu-central-2 | B1 |  |
| RN-EAST-10787 | 1 | ap-south-5 | B1 |  |
| RN-EAST-10787 | 2 | ap-south-5 | B1 |  |
| RN-EAST-10787 | 3 | ap-south-5 | B1 |  |
| RN-EAST-10787 | 4 | ap-south-5 | B1 |  |
| RN-EAST-10787 | 5 | ap-south-5 | B1 |  |
| RN-EAST-10816 | 1 | eu-central-2 | B1 |  |
| RN-EAST-10816 | 2 | eu-central-2 | B1 |  |
| RN-EAST-10816 | 3 | eu-central-2 | B1 |  |
| RN-EAST-10816 | 4 | eu-central-2 | B1 |  |
| RN-EAST-10816 | 5 | eu-central-2 | B1 |  |
| RN-EAST-10841 | 1 | ap-south-5 | B1 |  |
| RN-EAST-10841 | 2 | ap-south-5 | B1 |  |
| RN-EAST-10841 | 3 | eu-central-2 | B1 |  |
| RN-EAST-10841 | 4 | ap-south-5 | B1 |  |
| RN-EAST-10841 | 5 | ap-south-5 | B1 |  |
| RN-EAST-10873 | 1 | eu-central-2 | B1 |  |
| RN-EAST-10873 | 2 | eu-central-2 | B1 |  |
| RN-EAST-10873 | 3 | eu-central-2 | B1 |  |
| RN-EAST-10873 | 4 | eu-central-2 | B1 |  |
| RN-EAST-10873 | 5 | eu-central-2 | B1 |  |
| RN-EAST-10896 | 1 | ap-south-5 | B1 |  |
| RN-EAST-10896 | 2 | ap-south-5 | B1 |  |
| RN-EAST-10896 | 3 | ap-south-5 | B1 |  |
| RN-EAST-10896 | 4 | ap-south-5 | B1 |  |
| RN-EAST-10896 | 5 | ap-south-5 | B1 |  |
| RN-EAST-10929 | 1 | eu-central-2 | B1 |  |
| RN-EAST-10929 | 2 | eu-central-2 | B1 |  |
| RN-EAST-10929 | 3 | eu-central-2 | B1 |  |
| RN-EAST-10929 | 4 | eu-central-2 | B1 |  |
| RN-EAST-10929 | 5 | eu-central-2 | B1 |  |
| RN-EAST-10958 | 1 | ap-south-5 | B1 |  |
| RN-EAST-10958 | 2 | ap-south-5 | B1 |  |
| RN-EAST-10958 | 3 | ap-south-5 | B1 |  |
| RN-EAST-10958 | 4 | ap-south-5 | B1 |  |
| RN-EAST-10958 | 5 | ap-south-5 | B1 |  |
| RN-EAST-10984 | 1 | eu-central-2 | B1 |  |
| RN-EAST-10984 | 2 | eu-central-2 | B1 |  |
| RN-EAST-10984 | 3 | eu-central-2 | B1 |  |
| RN-EAST-10984 | 4 | eu-central-2 | B1 |  |
| RN-EAST-10984 | 5 | eu-central-2 | B1 |  |
| RN-EAST-11009 | 1 | ap-south-5 | B1 |  |
| RN-EAST-11009 | 2 | ap-south-5 | B1 |  |
| RN-EAST-11009 | 3 | ap-south-5 | B1 |  |
| RN-EAST-11009 | 4 | ap-south-5 | B1 |  |
| RN-EAST-11009 | 5 | ap-south-5 | B1 |  |
| RN-EAST-11042 | 1 | eu-central-2 | B1 |  |
| RN-EAST-11042 | 2 | eu-central-2 | B1 |  |
| RN-EAST-11042 | 3 | eu-central-2 | B1 |  |
| RN-EAST-11042 | 4 | eu-central-2 | B1 |  |
| RN-EAST-11042 | 5 | ap-south-5 | B1 |  |
| RN-EAST-11067 | 1 | ap-south-5 | B1 |  |
| RN-EAST-11067 | 2 | ap-south-5 | B1 |  |
| RN-EAST-11067 | 3 | ap-south-5 | B1 |  |
| RN-EAST-11067 | 4 | ap-south-5 | B1 |  |
| RN-EAST-11067 | 5 | ap-south-5 | B1 |  |
| RN-EAST-11092 | 1 | eu-central-2 | B1 |  |
| RN-EAST-11092 | 2 | eu-central-2 | B1 |  |
| RN-EAST-11092 | 3 | eu-central-2 | B1 |  |
| RN-EAST-11092 | 4 | eu-central-2 | B1 |  |
| RN-EAST-11092 | 5 | eu-central-2 | B1 |  |
| RN-EAST-11124 | 1 | ap-south-5 | B1 |  |
| RN-EAST-11124 | 2 | ap-south-5 | B1 |  |
| RN-EAST-11124 | 3 | ap-south-5 | B1 |  |
| RN-EAST-11124 | 4 | ap-south-5 | B1 |  |
| RN-EAST-11124 | 5 | ap-south-5 | B1 |  |
| RN-EAST-11149 | 1 | eu-central-2 | B1 |  |
| RN-EAST-11149 | 2 | eu-central-2 | B1 |  |
| RN-EAST-11149 | 3 | eu-central-2 | B1 |  |
| RN-EAST-11149 | 4 | eu-central-2 | B1 |  |
| RN-EAST-11149 | 5 | eu-central-2 | B1 |  |
| RN-EAST-11179 | 1 | ap-south-5 | B1 |  |
| RN-EAST-11179 | 2 | ap-south-5 | B1 |  |
| RN-EAST-11179 | 3 | ap-south-5 | B1 |  |
| RN-EAST-11179 | 4 | ap-south-5 | B1 |  |
| RN-EAST-11179 | 5 | ap-south-5 | B1 |  |
| RN-EAST-11206 | 1 | eu-central-2 | B1 |  |
| RN-EAST-11206 | 2 | eu-central-2 | B1 |  |
| RN-EAST-11206 | 3 | eu-central-2 | B1 |  |
| RN-EAST-11206 | 4 | eu-central-2 | B1 |  |
| RN-EAST-11206 | 5 | eu-central-2 | B1 |  |
| RN-EAST-11237 | 1 | ap-south-5 | B1 |  |
| RN-EAST-11237 | 2 | ap-south-5 | B1 |  |
| RN-EAST-11237 | 3 | eu-central-2 | B1 |  |
| RN-EAST-11237 | 4 | ap-south-5 | B1 |  |
| RN-EAST-11237 | 5 | ap-south-5 | B1 |  |
| RN-EAST-11262 | 1 | eu-central-2 | B1 |  |
| RN-EAST-11262 | 2 | eu-central-2 | B1 |  |
| RN-EAST-11262 | 3 | ap-south-5 | B1 |  |
| RN-EAST-11262 | 4 | eu-central-2 | B1 |  |
| RN-EAST-11262 | 5 | ap-south-5 | B1 |  |
| RN-EAST-11292 | 1 | ap-south-5 | B1 |  |
| RN-EAST-11292 | 2 | ap-south-5 | B1 |  |
| RN-EAST-11292 | 3 | ap-south-5 | B1 |  |
| RN-EAST-11292 | 4 | ap-south-5 | B1 |  |
| RN-EAST-11292 | 5 | ap-south-5 | B1 |  |
| RN-EAST-11322 | 1 | eu-central-2 | B1 |  |
| RN-EAST-11322 | 2 | ap-south-5 | B1 |  |
| RN-EAST-11322 | 3 | eu-central-2 | B1 |  |
| RN-EAST-11322 | 4 | eu-central-2 | B1 |  |
| RN-EAST-11322 | 5 | eu-central-2 | B1 |  |
| RN-EAST-11344 | 1 | ap-south-5 | B1 |  |
| RN-EAST-11344 | 2 | ap-south-5 | B1 |  |
| RN-EAST-11344 | 3 | ap-south-5 | B1 |  |
| RN-EAST-11344 | 4 | ap-south-5 | B1 |  |
| RN-EAST-11344 | 5 | ap-south-5 | B1 |  |
| RN-EAST-11374 | 1 | eu-central-2 | B1 |  |
| RN-EAST-11374 | 2 | eu-central-2 | B1 |  |
| RN-EAST-11374 | 3 | eu-central-2 | B1 |  |
| RN-EAST-11374 | 4 | eu-central-2 | B1 |  |
| RN-EAST-11374 | 5 | eu-central-2 | B1 |  |
| RN-EAST-11405 | 1 | ap-south-5 | B1 |  |
| RN-EAST-11405 | 2 | ap-south-5 | B1 |  |
| RN-EAST-11405 | 3 | ap-south-5 | B1 |  |
| RN-EAST-11405 | 4 | ap-south-5 | B1 |  |
| RN-EAST-11405 | 5 | ap-south-5 | B1 |  |
| RN-EAST-11432 | 1 | eu-central-2 | B1 |  |
| RN-EAST-11432 | 2 | eu-central-2 | B1 |  |
| RN-EAST-11432 | 3 | eu-central-2 | B1 |  |
| RN-EAST-11432 | 4 | eu-central-2 | B1 |  |
| RN-EAST-11432 | 5 | eu-central-2 | B1 |  |
| RN-EAST-11458 | 1 | ap-south-5 | B1 |  |
| RN-EAST-11458 | 2 | ap-south-5 | B1 |  |
| RN-EAST-11458 | 3 | ap-south-5 | B1 |  |
| RN-EAST-11458 | 4 | ap-south-5 | B1 |  |
| RN-EAST-11458 | 5 | ap-south-5 | B1 |  |
| RN-EAST-11486 | 1 | eu-central-2 | B1 |  |
| RN-EAST-11486 | 2 | eu-central-2 | B1 |  |
| RN-EAST-11486 | 3 | eu-central-2 | B1 |  |
| RN-EAST-11486 | 4 | eu-central-2 | B1 |  |
| RN-EAST-11486 | 5 | eu-central-2 | B1 |  |
| RN-EAST-11514 | 1 | ap-south-5 | B1 |  |
| RN-EAST-11514 | 2 | ap-south-5 | B1 |  |
| RN-EAST-11514 | 3 | ap-south-5 | B1 |  |
| RN-EAST-11514 | 4 | ap-south-5 | B1 |  |
| RN-EAST-11514 | 5 | ap-south-5 | B1 |  |
| RN-EAST-11543 | 1 | eu-central-2 | B1 |  |
| RN-EAST-11543 | 2 | eu-central-2 | B1 |  |
| RN-EAST-11543 | 3 | eu-central-2 | B1 |  |
| RN-EAST-11543 | 4 | eu-central-2 | B1 |  |
| RN-EAST-11543 | 5 | eu-central-2 | B1 |  |
| RN-EAST-11570 | 1 | ap-south-5 | B1 |  |
| RN-EAST-11570 | 2 | ap-south-5 | B1 |  |
| RN-EAST-11570 | 3 | ap-south-5 | B1 |  |
| RN-EAST-11570 | 4 | ap-south-5 | B1 |  |
| RN-EAST-11570 | 5 | ap-south-5 | B1 |  |
| RN-EAST-11596 | 1 | eu-central-2 | B1 |  |
| RN-EAST-11596 | 2 | eu-central-2 | B1 |  |
| RN-EAST-11596 | 3 | eu-central-2 | B1 |  |
| RN-EAST-11596 | 4 | eu-central-2 | B1 |  |
| RN-EAST-11596 | 5 | ap-south-5 | B1 |  |
| RN-EAST-11628 | 1 | ap-south-5 | B1 |  |
| RN-EAST-11628 | 2 | eu-central-2 | B1 |  |
| RN-EAST-11628 | 3 | ap-south-5 | B1 |  |
| RN-EAST-11628 | 4 | ap-south-5 | B1 |  |
| RN-EAST-11628 | 5 | ap-south-5 | B1 |  |
| RN-EAST-11658 | 1 | eu-central-2 | B1 |  |
| RN-EAST-11658 | 2 | eu-central-2 | B1 |  |
| RN-EAST-11658 | 3 | eu-central-2 | B1 |  |
| RN-EAST-11658 | 4 | eu-central-2 | B1 |  |
| RN-EAST-11658 | 5 | eu-central-2 | B1 |  |
| RN-EAST-11682 | 1 | ap-south-5 | B1 |  |
| RN-EAST-11682 | 2 | ap-south-5 | B1 |  |
| RN-EAST-11682 | 3 | ap-south-5 | B1 |  |
| RN-EAST-11682 | 4 | ap-south-5 | B1 |  |
| RN-EAST-11682 | 5 | ap-south-5 | B1 |  |
| RN-EAST-11709 | 1 | eu-central-2 | B1 |  |
| RN-EAST-11709 | 2 | eu-central-2 | B1 |  |
| RN-EAST-11709 | 3 | eu-central-2 | B1 |  |
| RN-EAST-11709 | 4 | eu-central-2 | B1 |  |
| RN-EAST-11709 | 5 | eu-central-2 | B1 |  |
| RN-EAST-11739 | 1 | ap-south-5 | B1 |  |
| RN-EAST-11739 | 2 | ap-south-5 | B1 |  |
| RN-EAST-11739 | 3 | ap-south-5 | B1 |  |
| RN-EAST-11739 | 4 | ap-south-5 | B1 |  |
| RN-EAST-11739 | 5 | ap-south-5 | B1 |  |
| RN-EAST-11767 | 1 | eu-central-2 | B1 |  |
| RN-EAST-11767 | 2 | eu-central-2 | B1 |  |
| RN-EAST-11767 | 3 | eu-central-2 | B1 |  |
| RN-EAST-11767 | 4 | eu-central-2 | B1 |  |
| RN-EAST-11767 | 5 | eu-central-2 | B1 |  |
| RN-EAST-11794 | 1 | ap-south-5 | B1 |  |
| RN-EAST-11794 | 2 | ap-south-5 | B1 |  |
| RN-EAST-11794 | 3 | ap-south-5 | B1 |  |
| RN-EAST-11794 | 4 | ap-south-5 | B1 |  |
| RN-EAST-11794 | 5 | ap-south-5 | B1 |  |
| RN-EAST-11821 | 1 | eu-central-2 | B1 |  |
| RN-EAST-11821 | 2 | eu-central-2 | B1 |  |
| RN-EAST-11821 | 3 | eu-central-2 | B1 |  |
| RN-EAST-11821 | 4 | eu-central-2 | B1 |  |
| RN-EAST-11821 | 5 | eu-central-2 | B1 |  |
| RN-EAST-11850 | 1 | ap-south-5 | B1 |  |
| RN-EAST-11850 | 2 | ap-south-5 | B1 |  |
| RN-EAST-11850 | 3 | ap-south-5 | B1 |  |
| RN-EAST-11850 | 4 | ap-south-5 | B1 |  |
| RN-EAST-11850 | 5 | ap-south-5 | B1 |  |
| RN-EAST-11876 | 1 | eu-central-2 | B1 |  |
| RN-EAST-11876 | 2 | eu-central-2 | B1 |  |
| RN-EAST-11876 | 3 | eu-central-2 | B1 |  |
| RN-EAST-11876 | 4 | eu-central-2 | B1 |  |
| RN-EAST-11876 | 5 | eu-central-2 | B1 |  |
| RN-EAST-11907 | 1 | ap-south-5 | B1 |  |
| RN-EAST-11907 | 2 | ap-south-5 | B1 |  |
| RN-EAST-11907 | 3 | ap-south-5 | B1 |  |
| RN-EAST-11907 | 4 | ap-south-5 | B1 |  |
| RN-EAST-11907 | 5 | ap-south-5 | B1 |  |
| RN-EAST-11933 | 1 | eu-central-2 | B1 |  |
| RN-EAST-11933 | 2 | eu-central-2 | B1 |  |
| RN-EAST-11933 | 3 | eu-central-2 | B1 |  |
| RN-EAST-11933 | 4 | eu-central-2 | B1 |  |
| RN-EAST-11933 | 5 | eu-central-2 | B1 |  |
| RN-EAST-11963 | 1 | ap-south-5 | B1 |  |
| RN-EAST-11963 | 2 | ap-south-5 | B1 |  |
| RN-EAST-11963 | 3 | ap-south-5 | B1 |  |
| RN-EAST-11963 | 4 | ap-south-5 | B1 |  |
| RN-EAST-11963 | 5 | ap-south-5 | B1 |  |
| RN-EAST-11992 | 1 | eu-central-2 | B1 |  |
| RN-EAST-11992 | 2 | eu-central-2 | B1 |  |
| RN-EAST-11992 | 3 | eu-central-2 | B1 |  |
| RN-EAST-11992 | 4 | eu-central-2 | B1 |  |
| RN-EAST-11992 | 5 | eu-central-2 | B1 |  |
| RN-EAST-12017 | 1 | ap-south-5 | B1 |  |
| RN-EAST-12017 | 2 | ap-south-5 | B1 |  |
| RN-EAST-12017 | 3 | ap-south-5 | B1 |  |
| RN-EAST-12017 | 4 | ap-south-5 | B1 |  |
| RN-EAST-12017 | 5 | eu-central-2 | B1 |  |
| RN-EAST-12050 | 1 | eu-central-2 | B1 |  |
| RN-EAST-12050 | 2 | ap-south-5 | B1 |  |
| RN-EAST-12050 | 3 | ap-south-5 | B1 |  |
| RN-EAST-12050 | 4 | eu-central-2 | B1 |  |
| RN-EAST-12050 | 5 | eu-central-2 | B1 |  |
| RN-EAST-12074 | 1 | ap-south-5 | B1 |  |
| RN-EAST-12074 | 2 | ap-south-5 | B1 |  |
| RN-EAST-12074 | 3 | ap-south-5 | B1 |  |
| RN-EAST-12074 | 4 | ap-south-5 | B1 |  |
| RN-EAST-12074 | 5 | ap-south-5 | B1 |  |
| RN-EAST-12104 | 1 | eu-central-2 | B1 |  |
| RN-EAST-12104 | 2 | eu-central-2 | B1 |  |
| RN-EAST-12104 | 3 | eu-central-2 | B1 |  |
| RN-EAST-12104 | 4 | ap-south-5 | B1 |  |
| RN-EAST-12104 | 5 | eu-central-2 | B1 |  |
| RN-EAST-12129 | 1 | ap-south-5 | B1 |  |
| RN-EAST-12129 | 2 | ap-south-5 | B1 |  |
| RN-EAST-12129 | 3 | ap-south-5 | B1 |  |
| RN-EAST-12129 | 4 | ap-south-5 | B1 |  |
| RN-EAST-12129 | 5 | eu-central-2 | B1 |  |
| RN-EAST-12162 | 1 | eu-central-2 | B1 |  |
| RN-EAST-12162 | 2 | ap-south-5 | B1 |  |
| RN-EAST-12162 | 3 | eu-central-2 | B1 |  |
| RN-EAST-12162 | 4 | eu-central-2 | B1 |  |
| RN-EAST-12162 | 5 | eu-central-2 | B1 |  |
| RN-EAST-12190 | 1 | ap-south-5 | B1 |  |
| RN-EAST-12190 | 2 | ap-south-5 | B1 |  |
| RN-EAST-12190 | 3 | ap-south-5 | B1 |  |
| RN-EAST-12190 | 4 | ap-south-5 | B1 |  |
| RN-EAST-12190 | 5 | ap-south-5 | B1 |  |
| RN-EAST-12213 | 1 | eu-central-2 | B1 |  |
| RN-EAST-12213 | 2 | eu-central-2 | B1 |  |
| RN-EAST-12213 | 3 | eu-central-2 | B1 |  |
| RN-EAST-12213 | 4 | eu-central-2 | B1 |  |
| RN-EAST-12213 | 5 | eu-central-2 | B1 |  |
| RN-EAST-12241 | 1 | ap-south-5 | B1 |  |
| RN-EAST-12241 | 2 | ap-south-5 | B1 |  |
| RN-EAST-12241 | 3 | ap-south-5 | B1 |  |
| RN-EAST-12241 | 4 | ap-south-5 | B1 |  |
| RN-EAST-12241 | 5 | ap-south-5 | B1 |  |
| RN-EAST-12270 | 1 | eu-central-2 | B1 |  |
| RN-EAST-12270 | 2 | eu-central-2 | B1 |  |
| RN-EAST-12270 | 3 | eu-central-2 | B1 |  |
| RN-EAST-12270 | 4 | eu-central-2 | B1 |  |
| RN-EAST-12270 | 5 | eu-central-2 | B1 |  |
| RN-EAST-12297 | 1 | ap-south-5 | B1 |  |
| RN-EAST-12297 | 2 | ap-south-5 | B1 |  |
| RN-EAST-12297 | 3 | ap-south-5 | B1 |  |
| RN-EAST-12297 | 4 | ap-south-5 | B1 |  |
| RN-EAST-12297 | 5 | ap-south-5 | B1 |  |
| RN-EAST-12329 | 1 | eu-central-2 | B1 |  |
| RN-EAST-12329 | 2 | eu-central-2 | B1 |  |
| RN-EAST-12329 | 3 | eu-central-2 | B1 |  |
| RN-EAST-12329 | 4 | eu-central-2 | B1 |  |
| RN-EAST-12329 | 5 | ap-south-5 | B1 |  |
| RN-EAST-12353 | 1 | ap-south-5 | B1 |  |
| RN-EAST-12353 | 2 | ap-south-5 | B1 |  |
| RN-EAST-12353 | 3 | ap-south-5 | B1 |  |
| RN-EAST-12353 | 4 | ap-south-5 | B1 |  |
| RN-EAST-12353 | 5 | ap-south-5 | B1 |  |
| RN-EAST-12385 | 1 | eu-central-2 | B1 |  |
| RN-EAST-12385 | 2 | eu-central-2 | B1 |  |
| RN-EAST-12385 | 3 | eu-central-2 | B1 |  |
| RN-EAST-12385 | 4 | eu-central-2 | B1 |  |
| RN-EAST-12385 | 5 | eu-central-2 | B1 |  |
| RN-EAST-12412 | 1 | ap-south-5 | B1 |  |
| RN-EAST-12412 | 2 | ap-south-5 | B1 |  |
| RN-EAST-12412 | 3 | ap-south-5 | B1 |  |
| RN-EAST-12412 | 4 | ap-south-5 | B1 |  |
| RN-EAST-12412 | 5 | ap-south-5 | B1 |  |
| RN-EAST-12437 | 1 | eu-central-2 | B1 |  |
| RN-EAST-12437 | 2 | eu-central-2 | B1 |  |
| RN-EAST-12437 | 3 | eu-central-2 | B1 |  |
| RN-EAST-12437 | 4 | eu-central-2 | B1 |  |
| RN-EAST-12437 | 5 | eu-central-2 | B1 |  |
| RN-EAST-12464 | 1 | ap-south-5 | B1 |  |
| RN-EAST-12464 | 2 | eu-central-2 | B1 |  |
| RN-EAST-12464 | 3 | ap-south-5 | B1 |  |
| RN-EAST-12464 | 4 | ap-south-5 | B1 |  |
| RN-EAST-12464 | 5 | ap-south-5 | B1 |  |
| RN-EAST-12494 | 1 | eu-central-2 | B1 |  |
| RN-EAST-12494 | 2 | eu-central-2 | B1 |  |
| RN-EAST-12494 | 3 | eu-central-2 | B1 |  |
| RN-EAST-12494 | 4 | eu-central-2 | B1 |  |
| RN-EAST-12494 | 5 | eu-central-2 | B1 |  |
| RN-EAST-12522 | 1 | ap-south-5 | B1 |  |
| RN-EAST-12522 | 2 | ap-south-5 | B1 |  |
| RN-EAST-12522 | 3 | ap-south-5 | B1 |  |
| RN-EAST-12522 | 4 | eu-central-2 | B1 |  |
| RN-EAST-12522 | 5 | ap-south-5 | B1 |  |
| RN-EAST-12549 | 1 | eu-central-2 | B1 |  |
| RN-EAST-12549 | 2 | eu-central-2 | B1 |  |
| RN-EAST-12549 | 3 | eu-central-2 | B1 |  |
| RN-EAST-12549 | 4 | eu-central-2 | B1 |  |
| RN-EAST-12549 | 5 | eu-central-2 | B1 |  |
| RN-EAST-12579 | 1 | ap-south-5 | B1 |  |
| RN-EAST-12579 | 2 | ap-south-5 | B1 |  |
| RN-EAST-12579 | 3 | eu-central-2 | B1 |  |
| RN-EAST-12579 | 4 | ap-south-5 | B1 |  |
| RN-EAST-12579 | 5 | ap-south-5 | B1 |  |
| RN-EAST-12604 | 1 | eu-central-2 | B1 |  |
| RN-EAST-12604 | 2 | eu-central-2 | B1 |  |
| RN-EAST-12604 | 3 | eu-central-2 | B1 |  |
| RN-EAST-12604 | 4 | eu-central-2 | B1 |  |
| RN-EAST-12604 | 5 | eu-central-2 | B1 |  |
| RN-EAST-12636 | 1 | ap-south-5 | B1 |  |
| RN-EAST-12636 | 2 | ap-south-5 | B1 |  |
| RN-EAST-12636 | 3 | ap-south-5 | B1 |  |
| RN-EAST-12636 | 4 | ap-south-5 | B1 |  |
| RN-EAST-12636 | 5 | ap-south-5 | B1 |  |
| RN-EAST-12662 | 1 | eu-central-2 | B1 |  |
| RN-EAST-12662 | 2 | eu-central-2 | B1 |  |
| RN-EAST-12662 | 3 | eu-central-2 | B1 |  |
| RN-EAST-12662 | 4 | ap-south-5 | B1 |  |
| RN-EAST-12662 | 5 | eu-central-2 | B1 |  |
| RN-EAST-12692 | 1 | ap-south-5 | B1 |  |
| RN-EAST-12692 | 2 | eu-central-2 | B1 |  |
| RN-EAST-12692 | 3 | ap-south-5 | B1 |  |
| RN-EAST-12692 | 4 | ap-south-5 | B1 |  |
| RN-EAST-12692 | 5 | ap-south-5 | B1 |  |
| RN-EAST-12721 | 1 | eu-central-2 | B1 |  |
| RN-EAST-12721 | 2 | eu-central-2 | B1 |  |
| RN-EAST-12721 | 3 | eu-central-2 | B1 |  |
| RN-EAST-12721 | 4 | eu-central-2 | B1 |  |
| RN-EAST-12721 | 5 | eu-central-2 | B1 |  |
| RN-EAST-12748 | 1 | ap-south-5 | B1 |  |
| RN-EAST-12748 | 2 | ap-south-5 | B1 |  |
| RN-EAST-12748 | 3 | ap-south-5 | B1 |  |
| RN-EAST-12748 | 4 | ap-south-5 | B1 |  |
| RN-EAST-12748 | 5 | ap-south-5 | B1 |  |
| RN-EAST-12774 | 1 | eu-central-2 | B1 |  |
| RN-EAST-12774 | 2 | eu-central-2 | B1 |  |
| RN-EAST-12774 | 3 | eu-central-2 | B1 |  |
| RN-EAST-12774 | 4 | eu-central-2 | B1 |  |
| RN-EAST-12774 | 5 | eu-central-2 | B1 |  |
| RN-EAST-12800 | 1 | ap-south-5 | B1 |  |
| RN-EAST-12800 | 2 | ap-south-5 | B1 |  |
| RN-EAST-12800 | 3 | eu-central-2 | B1 |  |
| RN-EAST-12800 | 4 | ap-south-5 | B1 |  |
| RN-EAST-12800 | 5 | ap-south-5 | B1 |  |
| RN-EAST-12831 | 1 | eu-central-2 | B1 |  |
| RN-EAST-12831 | 2 | eu-central-2 | B1 |  |
| RN-EAST-12831 | 3 | eu-central-2 | B1 |  |
| RN-EAST-12831 | 4 | eu-central-2 | B1 |  |
| RN-EAST-12831 | 5 | eu-central-2 | B1 |  |
| RN-EAST-12857 | 1 | ap-south-5 | B1 |  |
| RN-EAST-12857 | 2 | ap-south-5 | B1 |  |
| RN-EAST-12857 | 3 | ap-south-5 | B1 |  |
| RN-EAST-12857 | 4 | ap-south-5 | B1 |  |
| RN-EAST-12857 | 5 | ap-south-5 | B1 |  |
| RN-EAST-12888 | 1 | eu-central-2 | B1 |  |
| RN-EAST-12888 | 2 | eu-central-2 | B1 |  |
| RN-EAST-12888 | 3 | eu-central-2 | B1 |  |
| RN-EAST-12888 | 4 | eu-central-2 | B1 |  |
| RN-EAST-12888 | 5 | eu-central-2 | B1 |  |
| RN-EAST-12913 | 1 | ap-south-5 | B1 |  |
| RN-EAST-12913 | 2 | ap-south-5 | B1 |  |
| RN-EAST-12913 | 3 | ap-south-5 | B1 |  |
| RN-EAST-12913 | 4 | ap-south-5 | B1 |  |
| RN-EAST-12913 | 5 | ap-south-5 | B1 |  |
| RN-EAST-12943 | 1 | eu-central-2 | B1 |  |
| RN-EAST-12943 | 2 | eu-central-2 | B1 |  |
| RN-EAST-12943 | 3 | eu-central-2 | B1 |  |
| RN-EAST-12943 | 4 | ap-south-5 | B1 |  |
| RN-EAST-12943 | 5 | eu-central-2 | B1 |  |
| RN-EAST-12969 | 1 | ap-south-5 | B1 |  |
| RN-EAST-12969 | 2 | ap-south-5 | B1 |  |
| RN-EAST-12969 | 3 | ap-south-5 | B1 |  |
| RN-EAST-12969 | 4 | eu-central-2 | B1 |  |
| RN-EAST-12969 | 5 | ap-south-5 | B1 |  |
| RN-EAST-12998 | 1 | eu-central-2 | B1 |  |
| RN-EAST-12998 | 2 | eu-central-2 | B1 |  |
| RN-EAST-12998 | 3 | eu-central-2 | B1 |  |
| RN-EAST-12998 | 4 | eu-central-2 | B1 |  |
| RN-EAST-12998 | 5 | eu-central-2 | B1 |  |
| RN-EAST-13029 | 1 | ap-south-5 | B1 |  |
| RN-EAST-13029 | 2 | ap-south-5 | B1 |  |
| RN-EAST-13029 | 3 | ap-south-5 | B1 |  |
| RN-EAST-13029 | 4 | ap-south-5 | B1 |  |
| RN-EAST-13029 | 5 | ap-south-5 | B1 |  |
| RN-EAST-13053 | 1 | eu-central-2 | B1 |  |
| RN-EAST-13053 | 2 | eu-central-2 | B1 |  |
| RN-EAST-13053 | 3 | eu-central-2 | B1 |  |
| RN-EAST-13053 | 4 | ap-south-5 | B1 |  |
| RN-EAST-13053 | 5 | eu-central-2 | B1 |  |
| RN-EAST-13083 | 1 | ap-south-5 | B1 |  |
| RN-EAST-13083 | 2 | ap-south-5 | B1 |  |
| RN-EAST-13083 | 3 | ap-south-5 | B1 |  |
| RN-EAST-13083 | 4 | ap-south-5 | B1 |  |
| RN-EAST-13083 | 5 | eu-central-2 | B1 |  |
| RN-EAST-13112 | 1 | eu-central-2 | B1 |  |
| RN-EAST-13112 | 2 | eu-central-2 | B1 |  |
| RN-EAST-13112 | 3 | eu-central-2 | B1 |  |
| RN-EAST-13112 | 4 | eu-central-2 | B1 |  |
| RN-EAST-13112 | 5 | eu-central-2 | B1 |  |
| RN-EAST-13140 | 1 | ap-south-5 | B1 |  |
| RN-EAST-13140 | 2 | ap-south-5 | B1 |  |
| RN-EAST-13140 | 3 | ap-south-5 | B1 |  |
| RN-EAST-13140 | 4 | ap-south-5 | B1 |  |
| RN-EAST-13140 | 5 | ap-south-5 | B1 |  |
| RN-EAST-13170 | 1 | eu-central-2 | B1 |  |
| RN-EAST-13170 | 2 | eu-central-2 | B1 |  |
| RN-EAST-13170 | 3 | eu-central-2 | B1 |  |
| RN-EAST-13170 | 4 | eu-central-2 | B1 |  |
| RN-EAST-13170 | 5 | eu-central-2 | B1 |  |
| RN-EAST-13193 | 1 | ap-south-5 | B1 |  |
| RN-EAST-13193 | 2 | ap-south-5 | B1 |  |
| RN-EAST-13193 | 3 | ap-south-5 | B1 |  |
| RN-EAST-13193 | 4 | eu-central-2 | B1 |  |
| RN-EAST-13193 | 5 | ap-south-5 | B1 |  |
| RN-EAST-13222 | 1 | eu-central-2 | B1 |  |
| RN-EAST-13222 | 2 | eu-central-2 | B1 |  |
| RN-EAST-13222 | 3 | eu-central-2 | B1 |  |
| RN-EAST-13222 | 4 | eu-central-2 | B1 |  |
| RN-EAST-13222 | 5 | eu-central-2 | B1 |  |
| RN-EAST-13252 | 1 | ap-south-5 | B1 |  |
| RN-EAST-13252 | 2 | eu-central-2 | B1 |  |
| RN-EAST-13252 | 3 | ap-south-5 | B1 |  |
| RN-EAST-13252 | 4 | ap-south-5 | B1 |  |
| RN-EAST-13252 | 5 | ap-south-5 | B1 |  |
| RN-EAST-13278 | 1 | eu-central-2 | B1 |  |
| RN-EAST-13278 | 2 | eu-central-2 | B1 |  |
| RN-EAST-13278 | 3 | eu-central-2 | B1 |  |
| RN-EAST-13278 | 4 | eu-central-2 | B1 |  |
| RN-EAST-13278 | 5 | eu-central-2 | B1 |  |
| RN-EAST-13310 | 1 | ap-south-5 | B1 |  |
| RN-EAST-13310 | 2 | ap-south-5 | B1 |  |
| RN-EAST-13310 | 3 | ap-south-5 | B1 |  |
| RN-EAST-13310 | 4 | ap-south-5 | B1 |  |
| RN-EAST-13310 | 5 | ap-south-5 | B1 |  |
| RN-EAST-13332 | 1 | eu-central-2 | B1 |  |
| RN-EAST-13332 | 2 | eu-central-2 | B1 |  |
| RN-EAST-13332 | 3 | eu-central-2 | B1 |  |
| RN-EAST-13332 | 4 | ap-south-5 | B1 |  |
| RN-EAST-13332 | 5 | eu-central-2 | B1 |  |
| RN-EAST-13363 | 1 | ap-south-5 | B1 |  |
| RN-EAST-13363 | 2 | ap-south-5 | B1 |  |
| RN-EAST-13363 | 3 | ap-south-5 | B1 |  |
| RN-EAST-13363 | 4 | ap-south-5 | B1 |  |
| RN-EAST-13363 | 5 | ap-south-5 | B1 |  |
| RN-EAST-13393 | 1 | eu-central-2 | B1 |  |
| RN-EAST-13393 | 2 | eu-central-2 | B1 |  |
| RN-EAST-13393 | 3 | eu-central-2 | B1 |  |
| RN-EAST-13393 | 4 | eu-central-2 | B1 |  |
| RN-EAST-13393 | 5 | eu-central-2 | B1 |  |
| RN-EAST-13417 | 1 | ap-south-5 | B1 |  |
| RN-EAST-13417 | 2 | ap-south-5 | B1 |  |
| RN-EAST-13417 | 3 | ap-south-5 | B1 |  |
| RN-EAST-13417 | 4 | ap-south-5 | B1 |  |
| RN-EAST-13417 | 5 | ap-south-5 | B1 |  |
| RN-EAST-13447 | 1 | eu-central-2 | B1 |  |
| RN-EAST-13447 | 2 | eu-central-2 | B1 |  |
| RN-EAST-13447 | 3 | eu-central-2 | B1 |  |
| RN-EAST-13447 | 4 | eu-central-2 | B1 |  |
| RN-EAST-13447 | 5 | eu-central-2 | B1 |  |
| RN-EAST-13472 | 1 | ap-south-5 | B1 |  |
| RN-EAST-13472 | 2 | ap-south-5 | B1 |  |
| RN-EAST-13472 | 3 | ap-south-5 | B1 |  |
| RN-EAST-13472 | 4 | ap-south-5 | B1 |  |
| RN-EAST-13472 | 5 | ap-south-5 | B1 |  |
| RN-EAST-13506 | 1 | eu-central-2 | B1 |  |
| RN-EAST-13506 | 2 | eu-central-2 | B1 |  |
| RN-EAST-13506 | 3 | eu-central-2 | B1 |  |
| RN-EAST-13506 | 4 | eu-central-2 | B1 |  |
| RN-EAST-13506 | 5 | eu-central-2 | B1 |  |
| RN-EAST-13534 | 1 | ap-south-5 | B1 |  |
| RN-EAST-13534 | 2 | eu-central-2 | B1 |  |
| RN-EAST-13534 | 3 | ap-south-5 | B1 |  |
| RN-EAST-13534 | 4 | ap-south-5 | B1 |  |
| RN-EAST-13534 | 5 | eu-central-2 | B1 |  |
| RN-EAST-13559 | 1 | eu-central-2 | B1 |  |
| RN-EAST-13559 | 2 | eu-central-2 | B1 |  |
| RN-EAST-13559 | 3 | eu-central-2 | B1 |  |
| RN-EAST-13559 | 4 | eu-central-2 | B1 |  |
| RN-EAST-13559 | 5 | eu-central-2 | B1 |  |
| RN-EAST-13587 | 1 | ap-south-5 | B1 |  |
| RN-EAST-13587 | 2 | ap-south-5 | B1 |  |
| RN-EAST-13587 | 3 | ap-south-5 | B1 |  |
| RN-EAST-13587 | 4 | ap-south-5 | B1 |  |
| RN-EAST-13587 | 5 | ap-south-5 | B1 |  |
| RN-EAST-13613 | 1 | eu-central-2 | B1 |  |
| RN-EAST-13613 | 2 | ap-south-5 | B1 |  |
| RN-EAST-13613 | 3 | eu-central-2 | B1 |  |
| RN-EAST-13613 | 4 | eu-central-2 | B1 |  |
| RN-EAST-13613 | 5 | eu-central-2 | B1 |  |
| RN-EAST-13641 | 1 | ap-south-5 | B1 |  |
| RN-EAST-13641 | 2 | ap-south-5 | B1 |  |
| RN-EAST-13641 | 3 | ap-south-5 | B1 |  |
| RN-EAST-13641 | 4 | ap-south-5 | B1 |  |
| RN-EAST-13641 | 5 | ap-south-5 | B1 |  |
| RN-EAST-13674 | 1 | eu-central-2 | B1 |  |
| RN-EAST-13674 | 2 | eu-central-2 | B1 |  |
| RN-EAST-13674 | 3 | eu-central-2 | B1 |  |
| RN-EAST-13674 | 4 | eu-central-2 | B1 |  |
| RN-EAST-13674 | 5 | eu-central-2 | B1 |  |
| RN-EAST-13697 | 1 | ap-south-5 | B1 |  |
| RN-EAST-13697 | 2 | ap-south-5 | B1 |  |
| RN-EAST-13697 | 3 | ap-south-5 | B1 |  |
| RN-EAST-13697 | 4 | ap-south-5 | B1 |  |
| RN-EAST-13697 | 5 | ap-south-5 | B1 |  |
| RN-EAST-13728 | 1 | eu-central-2 | B1 |  |
| RN-EAST-13728 | 2 | eu-central-2 | B1 |  |
| RN-EAST-13728 | 3 | eu-central-2 | B1 |  |
| RN-EAST-13728 | 4 | eu-central-2 | B1 |  |
| RN-EAST-13728 | 5 | eu-central-2 | B1 |  |
| RN-EAST-13753 | 1 | ap-south-5 | B1 |  |
| RN-EAST-13753 | 2 | ap-south-5 | B1 |  |
| RN-EAST-13753 | 3 | ap-south-5 | B1 |  |
| RN-EAST-13753 | 4 | ap-south-5 | B1 |  |
| RN-EAST-13753 | 5 | ap-south-5 | B1 |  |
| RN-EAST-13786 | 1 | eu-central-2 | B1 |  |
| RN-EAST-13786 | 2 | ap-south-5 | B1 |  |
| RN-EAST-13786 | 3 | eu-central-2 | B1 |  |
| RN-EAST-13786 | 4 | eu-central-2 | B1 |  |
| RN-EAST-13786 | 5 | eu-central-2 | B1 |  |
| RN-EAST-13814 | 1 | ap-south-5 | B1 |  |
| RN-EAST-13814 | 2 | ap-south-5 | B1 |  |
| RN-EAST-13814 | 3 | ap-south-5 | B1 |  |
| RN-EAST-13814 | 4 | ap-south-5 | B1 |  |
| RN-EAST-13814 | 5 | ap-south-5 | B1 |  |
| RN-EAST-13842 | 1 | eu-central-2 | B1 |  |
| RN-EAST-13842 | 2 | eu-central-2 | B1 |  |
| RN-EAST-13842 | 3 | eu-central-2 | B1 |  |
| RN-EAST-13842 | 4 | eu-central-2 | B1 |  |
| RN-EAST-13842 | 5 | eu-central-2 | B1 |  |
| RN-EAST-13866 | 1 | ap-south-5 | B1 |  |
| RN-EAST-13866 | 2 | ap-south-5 | B1 |  |
| RN-EAST-13866 | 3 | eu-central-2 | B1 |  |
| RN-EAST-13866 | 4 | eu-central-2 | B1 |  |
| RN-EAST-13866 | 5 | ap-south-5 | B1 |  |
| RN-EAST-13897 | 1 | eu-central-2 | B1 |  |
| RN-EAST-13897 | 2 | eu-central-2 | B1 |  |
| RN-EAST-13897 | 3 | eu-central-2 | B1 |  |
| RN-EAST-13897 | 4 | eu-central-2 | B1 |  |
| RN-EAST-13897 | 5 | eu-central-2 | B1 |  |
| RN-EAST-13923 | 1 | ap-south-5 | B1 |  |
| RN-EAST-13923 | 2 | ap-south-5 | B1 |  |
| RN-EAST-13923 | 3 | ap-south-5 | B1 |  |
| RN-EAST-13923 | 4 | ap-south-5 | B1 |  |
| RN-EAST-13923 | 5 | ap-south-5 | B1 |  |
| RN-EAST-13950 | 1 | eu-central-2 | B1 |  |
| RN-EAST-13950 | 2 | eu-central-2 | B1 |  |
| RN-EAST-13950 | 3 | eu-central-2 | B1 |  |
| RN-EAST-13950 | 4 | eu-central-2 | B1 |  |
| RN-EAST-13950 | 5 | eu-central-2 | B1 |  |
| RN-EAST-13980 | 1 | ap-south-5 | B1 |  |
| RN-EAST-13980 | 2 | ap-south-5 | B1 |  |
| RN-EAST-13980 | 3 | ap-south-5 | B1 |  |
| RN-EAST-13980 | 4 | ap-south-5 | B1 |  |
| RN-EAST-13980 | 5 | ap-south-5 | B1 |  |
| RN-EAST-14009 | 1 | eu-central-2 | B1 |  |
| RN-EAST-14009 | 2 | eu-central-2 | B1 |  |
| RN-EAST-14009 | 3 | eu-central-2 | B1 |  |
| RN-EAST-14009 | 4 | eu-central-2 | B1 |  |
| RN-EAST-14009 | 5 | eu-central-2 | B1 |  |
| RN-EAST-14037 | 1 | ap-south-5 | B1 |  |
| RN-EAST-14037 | 2 | ap-south-5 | B1 |  |
| RN-EAST-14037 | 3 | ap-south-5 | B1 |  |
| RN-EAST-14037 | 4 | ap-south-5 | B1 |  |
| RN-EAST-14037 | 5 | ap-south-5 | B1 |  |
| RN-EAST-14060 | 1 | eu-central-2 | B1 |  |
| RN-EAST-14060 | 2 | eu-central-2 | B1 |  |
| RN-EAST-14060 | 3 | eu-central-2 | B1 |  |
| RN-EAST-14060 | 4 | eu-central-2 | B1 |  |
| RN-EAST-14060 | 5 | eu-central-2 | B1 |  |
| RN-EAST-14091 | 1 | ap-south-5 | B1 |  |
| RN-EAST-14091 | 2 | ap-south-5 | B1 |  |
| RN-EAST-14091 | 3 | ap-south-5 | B1 |  |
| RN-EAST-14091 | 4 | ap-south-5 | B1 |  |
| RN-EAST-14091 | 5 | ap-south-5 | B1 |  |
| RN-EAST-14120 | 1 | eu-central-2 | B1 |  |
| RN-EAST-14120 | 2 | eu-central-2 | B1 |  |
| RN-EAST-14120 | 3 | eu-central-2 | B1 |  |
| RN-EAST-14120 | 4 | eu-central-2 | B1 |  |
| RN-EAST-14120 | 5 | eu-central-2 | B1 |  |
| RN-EAST-14147 | 1 | ap-south-5 | B1 |  |
| RN-EAST-14147 | 2 | ap-south-5 | B1 |  |
| RN-EAST-14147 | 3 | ap-south-5 | B1 |  |
| RN-EAST-14147 | 4 | ap-south-5 | B1 |  |
| RN-EAST-14147 | 5 | ap-south-5 | B1 |  |
| RN-EAST-14175 | 1 | eu-central-2 | B1 |  |
| RN-EAST-14175 | 2 | eu-central-2 | B1 |  |
| RN-EAST-14175 | 3 | eu-central-2 | B1 |  |
| RN-EAST-14175 | 4 | eu-central-2 | B1 |  |
| RN-EAST-14175 | 5 | eu-central-2 | B1 |  |
| RN-EAST-14202 | 1 | ap-south-5 | B1 |  |
| RN-EAST-14202 | 2 | ap-south-5 | B1 |  |
| RN-EAST-14202 | 3 | ap-south-5 | B1 |  |
| RN-EAST-14202 | 4 | ap-south-5 | B1 |  |
| RN-EAST-14202 | 5 | ap-south-5 | B1 |  |
| RN-EAST-14234 | 1 | eu-central-2 | B1 |  |
| RN-EAST-14234 | 2 | eu-central-2 | B1 |  |
| RN-EAST-14234 | 3 | eu-central-2 | B1 |  |
| RN-EAST-14234 | 4 | eu-central-2 | B1 |  |
| RN-EAST-14234 | 5 | eu-central-2 | B1 |  |
| RN-EAST-14258 | 1 | ap-south-5 | B1 |  |
| RN-EAST-14258 | 2 | ap-south-5 | B1 |  |
| RN-EAST-14258 | 3 | ap-south-5 | B1 |  |
| RN-EAST-14258 | 4 | ap-south-5 | B1 |  |
| RN-EAST-14258 | 5 | ap-south-5 | B1 |  |
| RN-EAST-14289 | 1 | eu-central-2 | B1 |  |
| RN-EAST-14289 | 2 | eu-central-2 | B1 |  |
| RN-EAST-14289 | 3 | eu-central-2 | B1 |  |
| RN-EAST-14289 | 4 | eu-central-2 | B1 |  |
| RN-EAST-14289 | 5 | eu-central-2 | B1 |  |
| RN-EAST-14313 | 1 | ap-south-5 | B1 |  |
| RN-EAST-14313 | 2 | ap-south-5 | B1 |  |
| RN-EAST-14313 | 3 | ap-south-5 | B1 |  |
| RN-EAST-14313 | 4 | ap-south-5 | B1 |  |
| RN-EAST-14313 | 5 | ap-south-5 | B1 |  |
| RN-EAST-14344 | 1 | eu-central-2 | B1 |  |
| RN-EAST-14344 | 2 | eu-central-2 | B1 |  |
| RN-EAST-14344 | 3 | eu-central-2 | B1 |  |
| RN-EAST-14344 | 4 | eu-central-2 | B1 |  |
| RN-EAST-14344 | 5 | eu-central-2 | B1 |  |
| RN-EAST-14368 | 1 | ap-south-5 | B1 |  |
| RN-EAST-14368 | 2 | ap-south-5 | B1 |  |
| RN-EAST-14368 | 3 | ap-south-5 | B1 |  |
| RN-EAST-14368 | 4 | ap-south-5 | B1 |  |
| RN-EAST-14368 | 5 | ap-south-5 | B1 |  |
| RN-EAST-14399 | 1 | eu-central-2 | B1 |  |
| RN-EAST-14399 | 2 | eu-central-2 | B1 |  |
| RN-EAST-14399 | 3 | eu-central-2 | B1 |  |
| RN-EAST-14399 | 4 | eu-central-2 | B1 |  |
| RN-EAST-14399 | 5 | eu-central-2 | B1 |  |
| RN-EAST-14427 | 1 | ap-south-5 | B1 |  |
| RN-EAST-14427 | 2 | eu-central-2 | B1 |  |
| RN-EAST-14427 | 3 | ap-south-5 | B1 |  |
| RN-EAST-14427 | 4 | ap-south-5 | B1 |  |
| RN-EAST-14427 | 5 | ap-south-5 | B1 |  |
| RN-EAST-14458 | 1 | eu-central-2 | B1 |  |
| RN-EAST-14458 | 2 | eu-central-2 | B1 |  |
| RN-EAST-14458 | 3 | eu-central-2 | B1 |  |
| RN-EAST-14458 | 4 | eu-central-2 | B1 |  |
| RN-EAST-14458 | 5 | ap-south-5 | B1 |  |
| RN-EAST-14482 | 1 | ap-south-5 | B1 |  |
| RN-EAST-14482 | 2 | ap-south-5 | B1 |  |
| RN-EAST-14482 | 3 | ap-south-5 | B1 |  |
| RN-EAST-14482 | 4 | ap-south-5 | B1 |  |
| RN-EAST-14482 | 5 | ap-south-5 | B1 |  |
| RN-EAST-14513 | 1 | eu-central-2 | B1 |  |
| RN-EAST-14513 | 2 | eu-central-2 | B1 |  |
| RN-EAST-14513 | 3 | eu-central-2 | B1 |  |
| RN-EAST-14513 | 4 | eu-central-2 | B1 |  |
| RN-EAST-14513 | 5 | eu-central-2 | B1 |  |
| RN-EAST-14537 | 1 | ap-south-5 | B1 |  |
| RN-EAST-14537 | 2 | ap-south-5 | B1 |  |
| RN-EAST-14537 | 3 | ap-south-5 | B1 |  |
| RN-EAST-14537 | 4 | ap-south-5 | B1 |  |
| RN-EAST-14537 | 5 | ap-south-5 | B1 |  |
| RN-EAST-14564 | 1 | eu-central-2 | B1 |  |
| RN-EAST-14564 | 2 | eu-central-2 | B1 |  |
| RN-EAST-14564 | 3 | eu-central-2 | B1 |  |
| RN-EAST-14564 | 4 | eu-central-2 | B1 |  |
| RN-EAST-14564 | 5 | eu-central-2 | B1 |  |
| RN-EAST-14594 | 1 | ap-south-5 | B1 |  |
| RN-EAST-14594 | 2 | ap-south-5 | B1 |  |
| RN-EAST-14594 | 3 | ap-south-5 | B1 |  |
| RN-EAST-14594 | 4 | ap-south-5 | B1 |  |
| RN-EAST-14594 | 5 | ap-south-5 | B1 |  |
| RN-EAST-14625 | 1 | eu-central-2 | B1 |  |
| RN-EAST-14625 | 2 | eu-central-2 | B1 |  |
| RN-EAST-14625 | 3 | eu-central-2 | B1 |  |
| RN-EAST-14625 | 4 | eu-central-2 | B1 |  |
| RN-EAST-14625 | 5 | eu-central-2 | B1 |  |
| RN-EAST-14651 | 1 | ap-south-5 | B1 |  |
| RN-EAST-14651 | 2 | ap-south-5 | B1 |  |
| RN-EAST-14651 | 3 | ap-south-5 | B1 |  |
| RN-EAST-14651 | 4 | ap-south-5 | B1 |  |
| RN-EAST-14651 | 5 | ap-south-5 | B1 |  |
| RN-EAST-14682 | 1 | eu-central-2 | B1 |  |
| RN-EAST-14682 | 2 | eu-central-2 | B1 |  |
| RN-EAST-14682 | 3 | eu-central-2 | B1 |  |
| RN-EAST-14682 | 4 | eu-central-2 | B1 |  |
| RN-EAST-14682 | 5 | eu-central-2 | B1 |  |
| RN-EAST-14710 | 1 | ap-south-5 | B1 |  |
| RN-EAST-14710 | 2 | ap-south-5 | B1 |  |
| RN-EAST-14710 | 3 | ap-south-5 | B1 |  |
| RN-EAST-14710 | 4 | ap-south-5 | B1 |  |
| RN-EAST-14710 | 5 | ap-south-5 | B1 |  |
| RN-EAST-14734 | 1 | eu-central-2 | B1 |  |
| RN-EAST-14734 | 2 | eu-central-2 | B1 |  |
| RN-EAST-14734 | 3 | eu-central-2 | B1 |  |
| RN-EAST-14734 | 4 | eu-central-2 | B1 |  |
| RN-EAST-14734 | 5 | eu-central-2 | B1 |  |
|   rn-east-14763  | 1 | ap-south-5 | B2 |  |
|   rn-east-14763  | 2 | ap-south-5 | B2 |  |
|   rn-east-14763  | 3 | eu-central-2 | B2 |  |
|   rn-east-14763  | 4 | ap-south-5 | B2 |  |
|   rn-east-14763  | 5 | ap-south-5 | B2 |  |
|   rn-east-14791  | 1 | eu-central-2 | B2 |  |
|   rn-east-14791  | 2 | eu-central-2 | B2 |  |
|   rn-east-14791  | 3 | eu-central-2 | B2 |  |
|   rn-east-14791  | 4 | eu-central-2 | B2 |  |
|   rn-east-14791  | 5 | eu-central-2 | B2 |  |
|   rn-east-14816  | 1 | ap-south-5 | B2 |  |
|   rn-east-14816  | 2 | ap-south-5 | B2 |  |
|   rn-east-14816  | 3 | ap-south-5 | B2 |  |
|   rn-east-14816  | 4 | ap-south-5 | B2 |  |
|   rn-east-14816  | 5 | ap-south-5 | B2 |  |
|   rn-east-14844  | 1 | eu-central-2 | B2 |  |
|   rn-east-14844  | 2 | eu-central-2 | B2 |  |
|   rn-east-14844  | 3 | eu-central-2 | B2 |  |
|   rn-east-14844  | 4 | ap-south-5 | B2 |  |
|   rn-east-14844  | 5 | eu-central-2 | B2 |  |
|   rn-east-14877  | 1 | ap-south-5 | B2 |  |
|   rn-east-14877  | 2 | ap-south-5 | B2 |  |
|   rn-east-14877  | 3 | ap-south-5 | B2 |  |
|   rn-east-14877  | 4 | ap-south-5 | B2 |  |
|   rn-east-14877  | 5 | ap-south-5 | B2 |  |
|   rn-east-14904  | 1 | eu-central-2 | B2 |  |
|   rn-east-14904  | 2 | eu-central-2 | B2 |  |
|   rn-east-14904  | 3 | eu-central-2 | B2 |  |
|   rn-east-14904  | 4 | eu-central-2 | B2 |  |
|   rn-east-14904  | 5 | eu-central-2 | B2 |  |
|   rn-east-14928  | 1 | ap-south-5 | B2 |  |
|   rn-east-14928  | 2 | ap-south-5 | B2 |  |
|   rn-east-14928  | 3 | ap-south-5 | B2 |  |
|   rn-east-14928  | 4 | ap-south-5 | B2 |  |
|   rn-east-14928  | 5 | ap-south-5 | B2 |  |
|   rn-east-14958  | 1 | eu-central-2 | B2 |  |
|   rn-east-14958  | 2 | eu-central-2 | B2 |  |
|   rn-east-14958  | 3 | eu-central-2 | B2 |  |
|   rn-east-14958  | 4 | eu-central-2 | B2 |  |
|   rn-east-14958  | 5 | eu-central-2 | B2 |  |
|   rn-east-14986  | 1 | ap-south-5 | B2 |  |
|   rn-east-14986  | 2 | ap-south-5 | B2 |  |
|   rn-east-14986  | 3 | ap-south-5 | B2 |  |
|   rn-east-14986  | 4 | ap-south-5 | B2 |  |
|   rn-east-14986  | 5 | eu-central-2 | B2 |  |
|   rn-east-15014  | 1 | eu-central-2 | B2 |  |
|   rn-east-15014  | 2 | eu-central-2 | B2 |  |
|   rn-east-15014  | 3 | ap-south-5 | B2 |  |
|   rn-east-15014  | 4 | eu-central-2 | B2 |  |
|   rn-east-15014  | 5 | eu-central-2 | B2 |  |
|   rn-east-15044  | 1 | ap-south-5 | B2 |  |
|   rn-east-15044  | 2 | ap-south-5 | B2 |  |
|   rn-east-15044  | 3 | ap-south-5 | B2 |  |
|   rn-east-15044  | 4 | ap-south-5 | B2 |  |
|   rn-east-15044  | 5 | ap-south-5 | B2 |  |
|   rn-east-15068  | 1 | eu-central-2 | B2 |  |
|   rn-east-15068  | 2 | eu-central-2 | B2 |  |
|   rn-east-15068  | 3 | eu-central-2 | B2 |  |
|   rn-east-15068  | 4 | eu-central-2 | B2 |  |
|   rn-east-15068  | 5 | eu-central-2 | B2 |  |
|   rn-east-15098  | 1 | ap-south-5 | B2 |  |
|   rn-east-15098  | 2 | ap-south-5 | B2 |  |
|   rn-east-15098  | 3 | ap-south-5 | B2 |  |
|   rn-east-15098  | 4 | ap-south-5 | B2 |  |
|   rn-east-15098  | 5 | ap-south-5 | B2 |  |
|   rn-east-15129  | 1 | eu-central-2 | B2 |  |
|   rn-east-15129  | 2 | eu-central-2 | B2 |  |
|   rn-east-15129  | 3 | eu-central-2 | B2 |  |
|   rn-east-15129  | 4 | eu-central-2 | B2 |  |
|   rn-east-15129  | 5 | eu-central-2 | B2 |  |
|   rn-east-15154  | 1 | ap-south-5 | B2 |  |
|   rn-east-15154  | 2 | ap-south-5 | B2 |  |
|   rn-east-15154  | 3 | ap-south-5 | B2 |  |
|   rn-east-15154  | 4 | ap-south-5 | B2 |  |
|   rn-east-15154  | 5 | ap-south-5 | B2 |  |
|   rn-east-15183  | 1 | eu-central-2 | B2 |  |
|   rn-east-15183  | 2 | eu-central-2 | B2 |  |
|   rn-east-15183  | 3 | eu-central-2 | B2 |  |
|   rn-east-15183  | 4 | eu-central-2 | B2 |  |
|   rn-east-15183  | 5 | eu-central-2 | B2 |  |
|   rn-east-15213  | 1 | ap-south-5 | B2 |  |
|   rn-east-15213  | 2 | ap-south-5 | B2 |  |
|   rn-east-15213  | 3 | ap-south-5 | B2 |  |
|   rn-east-15213  | 4 | ap-south-5 | B2 |  |
|   rn-east-15213  | 5 | ap-south-5 | B2 |  |
|   rn-east-15239  | 1 | eu-central-2 | B2 |  |
|   rn-east-15239  | 2 | eu-central-2 | B2 |  |
|   rn-east-15239  | 3 | eu-central-2 | B2 |  |
|   rn-east-15239  | 4 | eu-central-2 | B2 |  |
|   rn-east-15239  | 5 | eu-central-2 | B2 |  |
|   rn-east-15268  | 1 | ap-south-5 | B2 |  |
|   rn-east-15268  | 2 | ap-south-5 | B2 |  |
|   rn-east-15268  | 3 | ap-south-5 | B2 |  |
|   rn-east-15268  | 4 | ap-south-5 | B2 |  |
|   rn-east-15268  | 5 | ap-south-5 | B2 |  |
|   rn-east-15297  | 1 | eu-central-2 | B2 |  |
|   rn-east-15297  | 2 | eu-central-2 | B2 |  |
|   rn-east-15297  | 3 | ap-south-5 | B2 |  |
|   rn-east-15297  | 4 | eu-central-2 | B2 |  |
|   rn-east-15297  | 5 | eu-central-2 | B2 |  |
|   rn-east-15321  | 1 | ap-south-5 | B2 |  |
|   rn-east-15321  | 2 | ap-south-5 | B2 |  |
|   rn-east-15321  | 3 | ap-south-5 | B2 |  |
|   rn-east-15321  | 4 | ap-south-5 | B2 |  |
|   rn-east-15321  | 5 | ap-south-5 | B2 |  |
|   rn-east-15348  | 1 | eu-central-2 | B2 |  |
|   rn-east-15348  | 2 | eu-central-2 | B2 |  |
|   rn-east-15348  | 3 | eu-central-2 | B2 |  |
|   rn-east-15348  | 4 | eu-central-2 | B2 |  |
|   rn-east-15348  | 5 | eu-central-2 | B2 |  |
|   rn-east-15376  | 1 | ap-south-5 | B2 |  |
|   rn-east-15376  | 2 | ap-south-5 | B2 |  |
|   rn-east-15376  | 3 | ap-south-5 | B2 |  |
|   rn-east-15376  | 4 | ap-south-5 | B2 |  |
|   rn-east-15376  | 5 | ap-south-5 | B2 |  |
|   rn-east-15406  | 1 | eu-central-2 | B2 |  |
|   rn-east-15406  | 2 | eu-central-2 | B2 |  |
|   rn-east-15406  | 3 | eu-central-2 | B2 |  |
|   rn-east-15406  | 4 | eu-central-2 | B2 |  |
|   rn-east-15406  | 5 | eu-central-2 | B2 |  |
|   rn-east-15433  | 1 | ap-south-5 | B2 |  |
|   rn-east-15433  | 2 | ap-south-5 | B2 |  |
|   rn-east-15433  | 3 | eu-central-2 | B2 |  |
|   rn-east-15433  | 4 | ap-south-5 | B2 |  |
|   rn-east-15433  | 5 | ap-south-5 | B2 |  |
|   rn-east-15466  | 1 | eu-central-2 | B2 |  |
|   rn-east-15466  | 2 | eu-central-2 | B2 |  |
|   rn-east-15466  | 3 | eu-central-2 | B2 |  |
|   rn-east-15466  | 4 | eu-central-2 | B2 |  |
|   rn-east-15466  | 5 | eu-central-2 | B2 |  |
|   rn-east-15491  | 1 | ap-south-5 | B2 |  |
|   rn-east-15491  | 2 | ap-south-5 | B2 |  |
|   rn-east-15491  | 3 | ap-south-5 | B2 |  |
|   rn-east-15491  | 4 | ap-south-5 | B2 |  |
|   rn-east-15491  | 5 | ap-south-5 | B2 |  |
|   rn-east-15517  | 1 | eu-central-2 | B2 |  |
|   rn-east-15517  | 2 | ap-south-5 | B2 |  |
|   rn-east-15517  | 3 | eu-central-2 | B2 |  |
|   rn-east-15517  | 4 | eu-central-2 | B2 |  |
|   rn-east-15517  | 5 | eu-central-2 | B2 |  |
|   rn-east-15544  | 1 | ap-south-5 | B2 |  |
|   rn-east-15544  | 2 | ap-south-5 | B2 |  |
|   rn-east-15544  | 3 | ap-south-5 | B2 |  |
|   rn-east-15544  | 4 | ap-south-5 | B2 |  |
|   rn-east-15544  | 5 | ap-south-5 | B2 |  |
|   rn-east-15574  | 1 | eu-central-2 | B2 |  |
|   rn-east-15574  | 2 | eu-central-2 | B2 |  |
|   rn-east-15574  | 3 | eu-central-2 | B2 |  |
|   rn-east-15574  | 4 | eu-central-2 | B2 |  |
|   rn-east-15574  | 5 | eu-central-2 | B2 |  |
|   rn-east-15602  | 1 | ap-south-5 | B2 |  |
|   rn-east-15602  | 2 | ap-south-5 | B2 |  |
|   rn-east-15602  | 3 | ap-south-5 | B2 |  |
|   rn-east-15602  | 4 | ap-south-5 | B2 |  |
|   rn-east-15602  | 5 | ap-south-5 | B2 |  |
|   rn-east-15631  | 1 | eu-central-2 | B2 |  |
|   rn-east-15631  | 2 | eu-central-2 | B2 |  |
|   rn-east-15631  | 3 | eu-central-2 | B2 |  |
|   rn-east-15631  | 4 | eu-central-2 | B2 |  |
|   rn-east-15631  | 5 | eu-central-2 | B2 |  |
|   rn-east-15657  | 1 | ap-south-5 | B2 |  |
|   rn-east-15657  | 2 | ap-south-5 | B2 |  |
|   rn-east-15657  | 3 | ap-south-5 | B2 |  |
|   rn-east-15657  | 4 | ap-south-5 | B2 |  |
|   rn-east-15657  | 5 | ap-south-5 | B2 |  |
|   rn-east-15688  | 1 | eu-central-2 | B2 |  |
|   rn-east-15688  | 2 | eu-central-2 | B2 |  |
|   rn-east-15688  | 3 | ap-south-5 | B2 |  |
|   rn-east-15688  | 4 | eu-central-2 | B2 |  |
|   rn-east-15688  | 5 | ap-south-5 | B2 |  |
|   rn-east-15714  | 1 | ap-south-5 | B2 |  |
|   rn-east-15714  | 2 | ap-south-5 | B2 |  |
|   rn-east-15714  | 3 | eu-central-2 | B2 |  |
|   rn-east-15714  | 4 | ap-south-5 | B2 |  |
|   rn-east-15714  | 5 | ap-south-5 | B2 |  |
|   rn-east-15744  | 1 | eu-central-2 | B2 |  |
|   rn-east-15744  | 2 | eu-central-2 | B2 |  |
|   rn-east-15744  | 3 | ap-south-5 | B2 |  |
|   rn-east-15744  | 4 | eu-central-2 | B2 |  |
|   rn-east-15744  | 5 | eu-central-2 | B2 |  |
|   rn-east-15769  | 1 | ap-south-5 | B2 |  |
|   rn-east-15769  | 2 | ap-south-5 | B2 |  |
|   rn-east-15769  | 3 | ap-south-5 | B2 |  |
|   rn-east-15769  | 4 | eu-central-2 | B2 |  |
|   rn-east-15769  | 5 | ap-south-5 | B2 |  |
|   rn-east-15800  | 1 | eu-central-2 | B2 |  |
|   rn-east-15800  | 2 | eu-central-2 | B2 |  |
|   rn-east-15800  | 3 | eu-central-2 | B2 |  |
|   rn-east-15800  | 4 | eu-central-2 | B2 |  |
|   rn-east-15800  | 5 | eu-central-2 | B2 |  |
|   rn-east-15828  | 1 | ap-south-5 | B2 |  |
|   rn-east-15828  | 2 | ap-south-5 | B2 |  |
|   rn-east-15828  | 3 | ap-south-5 | B2 |  |
|   rn-east-15828  | 4 | eu-central-2 | B2 |  |
|   rn-east-15828  | 5 | ap-south-5 | B2 |  |
|   rn-east-15853  | 1 | eu-central-2 | B2 |  |
|   rn-east-15853  | 2 | eu-central-2 | B2 |  |
|   rn-east-15853  | 3 | eu-central-2 | B2 |  |
|   rn-east-15853  | 4 | eu-central-2 | B2 |  |
|   rn-east-15853  | 5 | eu-central-2 | B2 |  |
|   rn-east-15886  | 1 | ap-south-5 | B2 |  |
|   rn-east-15886  | 2 | ap-south-5 | B2 |  |
|   rn-east-15886  | 3 | ap-south-5 | B2 |  |
|   rn-east-15886  | 4 | ap-south-5 | B2 |  |
|   rn-east-15886  | 5 | ap-south-5 | B2 |  |
|   rn-east-15911  | 1 | eu-central-2 | B2 |  |
|   rn-east-15911  | 2 | eu-central-2 | B2 |  |
|   rn-east-15911  | 3 | eu-central-2 | B2 |  |
|   rn-east-15911  | 4 | eu-central-2 | B2 |  |
|   rn-east-15911  | 5 | eu-central-2 | B2 |  |
|   rn-east-15936  | 1 | ap-south-5 | B2 |  |
|   rn-east-15936  | 2 | ap-south-5 | B2 |  |
|   rn-east-15936  | 3 | ap-south-5 | B2 |  |
|   rn-east-15936  | 4 | ap-south-5 | B2 |  |
|   rn-east-15936  | 5 | ap-south-5 | B2 |  |
|   rn-east-15967  | 1 | eu-central-2 | B2 |  |
|   rn-east-15967  | 2 | eu-central-2 | B2 |  |
|   rn-east-15967  | 3 | eu-central-2 | B2 |  |
|   rn-east-15967  | 4 | eu-central-2 | B2 |  |
|   rn-east-15967  | 5 | eu-central-2 | B2 |  |
|   rn-east-15997  | 1 | ap-south-5 | B2 |  |
|   rn-east-15997  | 2 | ap-south-5 | B2 |  |
|   rn-east-15997  | 3 | eu-central-2 | B2 |  |
|   rn-east-15997  | 4 | ap-south-5 | B2 |  |
|   rn-east-15997  | 5 | ap-south-5 | B2 |  |
|   rn-east-16025  | 1 | eu-central-2 | B2 |  |
|   rn-east-16025  | 2 | eu-central-2 | B2 |  |
|   rn-east-16025  | 3 | eu-central-2 | B2 |  |
|   rn-east-16025  | 4 | eu-central-2 | B2 |  |
|   rn-east-16025  | 5 | eu-central-2 | B2 |  |
|   rn-east-16053  | 1 | ap-south-5 | B2 |  |
|   rn-east-16053  | 2 | ap-south-5 | B2 |  |
|   rn-east-16053  | 3 | ap-south-5 | B2 |  |
|   rn-east-16053  | 4 | ap-south-5 | B2 |  |
|   rn-east-16053  | 5 | ap-south-5 | B2 |  |
|   rn-east-16078  | 1 | eu-central-2 | B2 |  |
|   rn-east-16078  | 2 | eu-central-2 | B2 |  |
|   rn-east-16078  | 3 | eu-central-2 | B2 |  |
|   rn-east-16078  | 4 | eu-central-2 | B2 |  |
|   rn-east-16078  | 5 | eu-central-2 | B2 |  |
|   rn-east-16106  | 1 | ap-south-5 | B2 |  |
|   rn-east-16106  | 2 | ap-south-5 | B2 |  |
|   rn-east-16106  | 3 | ap-south-5 | B2 |  |
|   rn-east-16106  | 4 | ap-south-5 | B2 |  |
|   rn-east-16106  | 5 | ap-south-5 | B2 |  |
|   rn-east-16138  | 1 | eu-central-2 | B2 |  |
|   rn-east-16138  | 2 | eu-central-2 | B2 |  |
|   rn-east-16138  | 3 | eu-central-2 | B2 |  |
|   rn-east-16138  | 4 | eu-central-2 | B2 |  |
|   rn-east-16138  | 5 | eu-central-2 | B2 |  |
|   rn-east-16162  | 1 | ap-south-5 | B2 |  |
|   rn-east-16162  | 2 | ap-south-5 | B2 |  |
|   rn-east-16162  | 3 | ap-south-5 | B2 |  |
|   rn-east-16162  | 4 | ap-south-5 | B2 |  |
|   rn-east-16162  | 5 | ap-south-5 | B2 |  |
|   rn-east-16190  | 1 | eu-central-2 | B2 |  |
|   rn-east-16190  | 2 | eu-central-2 | B2 |  |
|   rn-east-16190  | 3 | eu-central-2 | B2 |  |
|   rn-east-16190  | 4 | eu-central-2 | B2 |  |
|   rn-east-16190  | 5 | eu-central-2 | B2 |  |
|   rn-east-16220  | 1 | ap-south-5 | B2 |  |
|   rn-east-16220  | 2 | ap-south-5 | B2 |  |
|   rn-east-16220  | 3 | ap-south-5 | B2 |  |
|   rn-east-16220  | 4 | ap-south-5 | B2 |  |
|   rn-east-16220  | 5 | ap-south-5 | B2 |  |
|   rn-east-16244  | 1 | eu-central-2 | B2 |  |
|   rn-east-16244  | 2 | eu-central-2 | B2 |  |
|   rn-east-16244  | 3 | eu-central-2 | B2 |  |
|   rn-east-16244  | 4 | eu-central-2 | B2 |  |
|   rn-east-16244  | 5 | eu-central-2 | B2 |  |
|   rn-east-16277  | 1 | ap-south-5 | B2 |  |
|   rn-east-16277  | 2 | ap-south-5 | B2 |  |
|   rn-east-16277  | 3 | ap-south-5 | B2 |  |
|   rn-east-16277  | 4 | ap-south-5 | B2 |  |
|   rn-east-16277  | 5 | ap-south-5 | B2 |  |
|   rn-east-16304  | 1 | eu-central-2 | B2 |  |
|   rn-east-16304  | 2 | eu-central-2 | B2 |  |
|   rn-east-16304  | 3 | eu-central-2 | B2 |  |
|   rn-east-16304  | 4 | eu-central-2 | B2 |  |
|   rn-east-16304  | 5 | eu-central-2 | B2 |  |
|   rn-east-16330  | 1 | ap-south-5 | B2 |  |
|   rn-east-16330  | 2 | ap-south-5 | B2 |  |
|   rn-east-16330  | 3 | ap-south-5 | B2 |  |
|   rn-east-16330  | 4 | ap-south-5 | B2 |  |
|   rn-east-16330  | 5 | ap-south-5 | B2 |  |
|   rn-east-16360  | 1 | eu-central-2 | B2 |  |
|   rn-east-16360  | 2 | eu-central-2 | B2 |  |
|   rn-east-16360  | 3 | eu-central-2 | B2 |  |
|   rn-east-16360  | 4 | eu-central-2 | B2 |  |
|   rn-east-16360  | 5 | eu-central-2 | B2 |  |
|   rn-east-16387  | 1 | ap-south-5 | B2 |  |
|   rn-east-16387  | 2 | ap-south-5 | B2 |  |
|   rn-east-16387  | 3 | ap-south-5 | B2 |  |
|   rn-east-16387  | 4 | ap-south-5 | B2 |  |
|   rn-east-16387  | 5 | ap-south-5 | B2 |  |
|   rn-east-16417  | 1 | eu-central-2 | B2 |  |
|   rn-east-16417  | 2 | eu-central-2 | B2 |  |
|   rn-east-16417  | 3 | eu-central-2 | B2 |  |
|   rn-east-16417  | 4 | eu-central-2 | B2 |  |
|   rn-east-16417  | 5 | eu-central-2 | B2 |  |
|   rn-east-16440  | 1 | ap-south-5 | B2 |  |
|   rn-east-16440  | 2 | ap-south-5 | B2 |  |
|   rn-east-16440  | 3 | ap-south-5 | B2 |  |
|   rn-east-16440  | 4 | ap-south-5 | B2 |  |
|   rn-east-16440  | 5 | ap-south-5 | B2 |  |
|   rn-east-16471  | 1 | eu-central-2 | B2 |  |
|   rn-east-16471  | 2 | eu-central-2 | B2 |  |
|   rn-east-16471  | 3 | eu-central-2 | B2 |  |
|   rn-east-16471  | 4 | ap-south-5 | B2 |  |
|   rn-east-16471  | 5 | eu-central-2 | B2 |  |
|   rn-east-16501  | 1 | ap-south-5 | B2 |  |
|   rn-east-16501  | 2 | ap-south-5 | B2 |  |
|   rn-east-16501  | 3 | ap-south-5 | B2 |  |
|   rn-east-16501  | 4 | ap-south-5 | B2 |  |
|   rn-east-16501  | 5 | ap-south-5 | B2 |  |
|   rn-east-16526  | 1 | eu-central-2 | B2 |  |
|   rn-east-16526  | 2 | eu-central-2 | B2 |  |
|   rn-east-16526  | 3 | eu-central-2 | B2 |  |
|   rn-east-16526  | 4 | ap-south-5 | B2 |  |
|   rn-east-16526  | 5 | eu-central-2 | B2 |  |
|   rn-east-16557  | 1 | ap-south-5 | B2 |  |
|   rn-east-16557  | 2 | ap-south-5 | B2 |  |
|   rn-east-16557  | 3 | ap-south-5 | B2 |  |
|   rn-east-16557  | 4 | ap-south-5 | B2 |  |
|   rn-east-16557  | 5 | ap-south-5 | B2 |  |
|   rn-east-16583  | 1 | eu-central-2 | B2 |  |
|   rn-east-16583  | 2 | eu-central-2 | B2 |  |
|   rn-east-16583  | 3 | eu-central-2 | B2 |  |
|   rn-east-16583  | 4 | eu-central-2 | B2 |  |
|   rn-east-16583  | 5 | eu-central-2 | B2 |  |
|   rn-east-16608  | 1 | ap-south-5 | B2 |  |
|   rn-east-16608  | 2 | ap-south-5 | B2 |  |
|   rn-east-16608  | 3 | ap-south-5 | B2 |  |
|   rn-east-16608  | 4 | ap-south-5 | B2 |  |
|   rn-east-16608  | 5 | ap-south-5 | B2 |  |
|   rn-east-16636  | 1 | eu-central-2 | B2 |  |
|   rn-east-16636  | 2 | eu-central-2 | B2 |  |
|   rn-east-16636  | 3 | eu-central-2 | B2 |  |
|   rn-east-16636  | 4 | eu-central-2 | B2 |  |
|   rn-east-16636  | 5 | eu-central-2 | B2 |  |
|   rn-east-16669  | 1 | ap-south-5 | B2 |  |
|   rn-east-16669  | 2 | ap-south-5 | B2 |  |
|   rn-east-16669  | 3 | ap-south-5 | B2 |  |
|   rn-east-16669  | 4 | ap-south-5 | B2 |  |
|   rn-east-16669  | 5 | ap-south-5 | B2 |  |
|   rn-east-16696  | 1 | eu-central-2 | B2 |  |
|   rn-east-16696  | 2 | eu-central-2 | B2 |  |
|   rn-east-16696  | 3 | eu-central-2 | B2 |  |
|   rn-east-16696  | 4 | eu-central-2 | B2 |  |
|   rn-east-16696  | 5 | eu-central-2 | B2 |  |
|   rn-east-16722  | 1 | ap-south-5 | B2 |  |
|   rn-east-16722  | 2 | ap-south-5 | B2 |  |
|   rn-east-16722  | 3 | ap-south-5 | B2 |  |
|   rn-east-16722  | 4 | ap-south-5 | B2 |  |
|   rn-east-16722  | 5 | ap-south-5 | B2 |  |
|   rn-east-16748  | 1 | eu-central-2 | B2 |  |
|   rn-east-16748  | 2 | eu-central-2 | B2 |  |
|   rn-east-16748  | 3 | eu-central-2 | B2 |  |
|   rn-east-16748  | 4 | eu-central-2 | B2 |  |
|   rn-east-16748  | 5 | eu-central-2 | B2 |  |
|   rn-east-16782  | 1 | ap-south-5 | B2 |  |
|   rn-east-16782  | 2 | ap-south-5 | B2 |  |
|   rn-east-16782  | 3 | ap-south-5 | B2 |  |
|   rn-east-16782  | 4 | eu-central-2 | B2 |  |
|   rn-east-16782  | 5 | ap-south-5 | B2 |  |
|   rn-east-16805  | 1 | eu-central-2 | B2 |  |
|   rn-east-16805  | 2 | eu-central-2 | B2 |  |
|   rn-east-16805  | 3 | eu-central-2 | B2 |  |
|   rn-east-16805  | 4 | eu-central-2 | B2 |  |
|   rn-east-16805  | 5 | eu-central-2 | B2 |  |
|   rn-east-16837  | 1 | ap-south-5 | B2 |  |
|   rn-east-16837  | 2 | ap-south-5 | B2 |  |
|   rn-east-16837  | 3 | ap-south-5 | B2 |  |
|   rn-east-16837  | 4 | ap-south-5 | B2 |  |
|   rn-east-16837  | 5 | ap-south-5 | B2 |  |
|   rn-east-16866  | 1 | eu-central-2 | B2 |  |
|   rn-east-16866  | 2 | eu-central-2 | B2 |  |
|   rn-east-16866  | 3 | eu-central-2 | B2 |  |
|   rn-east-16866  | 4 | eu-central-2 | B2 |  |
|   rn-east-16866  | 5 | eu-central-2 | B2 |  |
|   rn-east-16894  | 1 | ap-south-5 | B2 |  |
|   rn-east-16894  | 2 | ap-south-5 | B2 |  |
|   rn-east-16894  | 3 | ap-south-5 | B2 |  |
|   rn-east-16894  | 4 | ap-south-5 | B2 |  |
|   rn-east-16894  | 5 | ap-south-5 | B2 |  |
|   rn-east-16917  | 1 | eu-central-2 | B2 |  |
|   rn-east-16917  | 2 | eu-central-2 | B2 |  |
|   rn-east-16917  | 3 | eu-central-2 | B2 |  |
|   rn-east-16917  | 4 | eu-central-2 | B2 |  |
|   rn-east-16917  | 5 | eu-central-2 | B2 |  |
|   rn-east-16944  | 1 | ap-south-5 | B2 |  |
|   rn-east-16944  | 2 | ap-south-5 | B2 |  |
|   rn-east-16944  | 3 | ap-south-5 | B2 |  |
|   rn-east-16944  | 4 | ap-south-5 | B2 |  |
|   rn-east-16944  | 5 | ap-south-5 | B2 |  |
|   rn-east-16976  | 1 | eu-central-2 | B2 |  |
|   rn-east-16976  | 2 | eu-central-2 | B2 |  |
|   rn-east-16976  | 3 | eu-central-2 | B2 |  |
|   rn-east-16976  | 4 | ap-south-5 | B2 |  |
|   rn-east-16976  | 5 | eu-central-2 | B2 |  |
|   rn-east-17003  | 1 | ap-south-5 | B2 |  |
|   rn-east-17003  | 2 | ap-south-5 | B2 |  |
|   rn-east-17003  | 3 | ap-south-5 | B2 |  |
|   rn-east-17003  | 4 | ap-south-5 | B2 |  |
|   rn-east-17003  | 5 | ap-south-5 | B2 |  |
|   rn-east-17033  | 1 | eu-central-2 | B2 |  |
|   rn-east-17033  | 2 | eu-central-2 | B2 |  |
|   rn-east-17033  | 3 | ap-south-5 | B2 |  |
|   rn-east-17033  | 4 | eu-central-2 | B2 |  |
|   rn-east-17033  | 5 | eu-central-2 | B2 |  |
|   rn-east-17056  | 1 | ap-south-5 | B2 |  |
|   rn-east-17056  | 2 | ap-south-5 | B2 |  |
|   rn-east-17056  | 3 | ap-south-5 | B2 |  |
|   rn-east-17056  | 4 | ap-south-5 | B2 |  |
|   rn-east-17056  | 5 | ap-south-5 | B2 |  |
|   rn-east-17087  | 1 | eu-central-2 | B2 |  |
|   rn-east-17087  | 2 | eu-central-2 | B2 |  |
|   rn-east-17087  | 3 | eu-central-2 | B2 |  |
|   rn-east-17087  | 4 | eu-central-2 | B2 |  |
|   rn-east-17087  | 5 | eu-central-2 | B2 |  |
|   rn-east-17116  | 1 | ap-south-5 | B2 |  |
|   rn-east-17116  | 2 | ap-south-5 | B2 |  |
|   rn-east-17116  | 3 | ap-south-5 | B2 |  |
|   rn-east-17116  | 4 | ap-south-5 | B2 |  |
|   rn-east-17116  | 5 | ap-south-5 | B2 |  |
|   rn-east-17142  | 1 | eu-central-2 | B2 |  |
|   rn-east-17142  | 2 | eu-central-2 | B2 |  |
|   rn-east-17142  | 3 | eu-central-2 | B2 |  |
|   rn-east-17142  | 4 | eu-central-2 | B2 |  |
|   rn-east-17142  | 5 | eu-central-2 | B2 |  |
|   rn-east-17174  | 1 | ap-south-5 | B2 |  |
|   rn-east-17174  | 2 | ap-south-5 | B2 |  |
|   rn-east-17174  | 3 | ap-south-5 | B2 |  |
|   rn-east-17174  | 4 | ap-south-5 | B2 |  |
|   rn-east-17174  | 5 | ap-south-5 | B2 |  |
|   rn-east-17198  | 1 | eu-central-2 | B2 |  |
|   rn-east-17198  | 2 | eu-central-2 | B2 |  |
|   rn-east-17198  | 3 | eu-central-2 | B2 |  |
|   rn-east-17198  | 4 | eu-central-2 | B2 |  |
|   rn-east-17198  | 5 | eu-central-2 | B2 |  |
|   rn-east-17229  | 1 | ap-south-5 | B2 |  |
|   rn-east-17229  | 2 | ap-south-5 | B2 |  |
|   rn-east-17229  | 3 | ap-south-5 | B2 |  |
|   rn-east-17229  | 4 | ap-south-5 | B2 |  |
|   rn-east-17229  | 5 | ap-south-5 | B2 |  |
|   rn-east-17257  | 1 | eu-central-2 | B2 |  |
|   rn-east-17257  | 2 | eu-central-2 | B2 |  |
|   rn-east-17257  | 3 | eu-central-2 | B2 |  |
|   rn-east-17257  | 4 | ap-south-5 | B2 |  |
|   rn-east-17257  | 5 | eu-central-2 | B2 |  |
|   rn-east-17286  | 1 | ap-south-5 | B2 |  |
|   rn-east-17286  | 2 | ap-south-5 | B2 |  |
|   rn-east-17286  | 3 | ap-south-5 | B2 |  |
|   rn-east-17286  | 4 | ap-south-5 | B2 |  |
|   rn-east-17286  | 5 | ap-south-5 | B2 |  |
|   rn-east-17314  | 1 | eu-central-2 | B2 |  |
|   rn-east-17314  | 2 | ap-south-5 | B2 |  |
|   rn-east-17314  | 3 | eu-central-2 | B2 |  |
|   rn-east-17314  | 4 | eu-central-2 | B2 |  |
|   rn-east-17314  | 5 | eu-central-2 | B2 |  |
|   rn-east-17341  | 1 | ap-south-5 | B2 |  |
|   rn-east-17341  | 2 | ap-south-5 | B2 |  |
|   rn-east-17341  | 3 | eu-central-2 | B2 |  |
|   rn-east-17341  | 4 | ap-south-5 | B2 |  |
|   rn-east-17341  | 5 | ap-south-5 | B2 |  |
|   rn-east-17365  | 1 | eu-central-2 | B2 |  |
|   rn-east-17365  | 2 | eu-central-2 | B2 |  |
|   rn-east-17365  | 3 | eu-central-2 | B2 |  |
|   rn-east-17365  | 4 | eu-central-2 | B2 |  |
|   rn-east-17365  | 5 | eu-central-2 | B2 |  |
|   rn-east-17396  | 1 | ap-south-5 | B2 |  |
|   rn-east-17396  | 2 | ap-south-5 | B2 |  |
|   rn-east-17396  | 3 | ap-south-5 | B2 |  |
|   rn-east-17396  | 4 | ap-south-5 | B2 |  |
|   rn-east-17396  | 5 | ap-south-5 | B2 |  |
|   rn-east-17425  | 1 | eu-central-2 | B2 |  |
|   rn-east-17425  | 2 | eu-central-2 | B2 |  |
|   rn-east-17425  | 3 | eu-central-2 | B2 |  |
|   rn-east-17425  | 4 | eu-central-2 | B2 |  |
|   rn-east-17425  | 5 | eu-central-2 | B2 |  |
|   rn-east-17449  | 1 | ap-south-5 | B2 |  |
|   rn-east-17449  | 2 | ap-south-5 | B2 |  |
|   rn-east-17449  | 3 | ap-south-5 | B2 |  |
|   rn-east-17449  | 4 | ap-south-5 | B2 |  |
|   rn-east-17449  | 5 | ap-south-5 | B2 |  |
|   rn-east-17476  | 1 | eu-central-2 | B2 |  |
|   rn-east-17476  | 2 | eu-central-2 | B2 |  |
|   rn-east-17476  | 3 | eu-central-2 | B2 |  |
|   rn-east-17476  | 4 | eu-central-2 | B2 |  |
|   rn-east-17476  | 5 | eu-central-2 | B2 |  |
|   rn-east-17506  | 1 | ap-south-5 | B2 |  |
|   rn-east-17506  | 2 | ap-south-5 | B2 |  |
|   rn-east-17506  | 3 | ap-south-5 | B2 |  |
|   rn-east-17506  | 4 | ap-south-5 | B2 |  |
|   rn-east-17506  | 5 | ap-south-5 | B2 |  |
|   rn-east-17535  | 1 | eu-central-2 | B2 |  |
|   rn-east-17535  | 2 | eu-central-2 | B2 |  |
|   rn-east-17535  | 3 | eu-central-2 | B2 |  |
|   rn-east-17535  | 4 | eu-central-2 | B2 |  |
|   rn-east-17535  | 5 | eu-central-2 | B2 |  |
|   rn-east-17561  | 1 | ap-south-5 | B2 |  |
|   rn-east-17561  | 2 | ap-south-5 | B2 |  |
|   rn-east-17561  | 3 | ap-south-5 | B2 |  |
|   rn-east-17561  | 4 | ap-south-5 | B2 |  |
|   rn-east-17561  | 5 | ap-south-5 | B2 |  |
|   rn-east-17591  | 1 | eu-central-2 | B2 |  |
|   rn-east-17591  | 2 | eu-central-2 | B2 |  |
|   rn-east-17591  | 3 | eu-central-2 | B2 |  |
|   rn-east-17591  | 4 | eu-central-2 | B2 |  |
|   rn-east-17591  | 5 | eu-central-2 | B2 |  |
|   rn-east-17620  | 1 | ap-south-5 | B2 |  |
|   rn-east-17620  | 2 | ap-south-5 | B2 |  |
|   rn-east-17620  | 3 | ap-south-5 | B2 |  |
|   rn-east-17620  | 4 | ap-south-5 | B2 |  |
|   rn-east-17620  | 5 | ap-south-5 | B2 |  |
|   rn-east-17646  | 1 | eu-central-2 | B2 |  |
|   rn-east-17646  | 2 | eu-central-2 | B2 |  |
|   rn-east-17646  | 3 | eu-central-2 | B2 |  |
|   rn-east-17646  | 4 | ap-south-5 | B2 |  |
|   rn-east-17646  | 5 | eu-central-2 | B2 |  |
|   rn-east-17677  | 1 | ap-south-5 | B2 |  |
|   rn-east-17677  | 2 | ap-south-5 | B2 |  |
|   rn-east-17677  | 3 | ap-south-5 | B2 |  |
|   rn-east-17677  | 4 | ap-south-5 | B2 |  |
|   rn-east-17677  | 5 | ap-south-5 | B2 |  |
|   rn-east-17700  | 1 | eu-central-2 | B2 |  |
|   rn-east-17700  | 2 | eu-central-2 | B2 |  |
|   rn-east-17700  | 3 | eu-central-2 | B2 |  |
|   rn-east-17700  | 4 | eu-central-2 | B2 |  |
|   rn-east-17700  | 5 | eu-central-2 | B2 |  |
|   rn-east-17728  | 1 | ap-south-5 | B2 |  |
|   rn-east-17728  | 2 | ap-south-5 | B2 |  |
|   rn-east-17728  | 3 | ap-south-5 | B2 |  |
|   rn-east-17728  | 4 | ap-south-5 | B2 |  |
|   rn-east-17728  | 5 | ap-south-5 | B2 |  |
|   rn-east-17756  | 1 | eu-central-2 | B2 |  |
|   rn-east-17756  | 2 | eu-central-2 | B2 |  |
|   rn-east-17756  | 3 | eu-central-2 | B2 |  |
|   rn-east-17756  | 4 | eu-central-2 | B2 |  |
|   rn-east-17756  | 5 | eu-central-2 | B2 |  |
|   rn-east-17786  | 1 | ap-south-5 | B2 |  |
|   rn-east-17786  | 2 | ap-south-5 | B2 |  |
|   rn-east-17786  | 3 | ap-south-5 | B2 |  |
|   rn-east-17786  | 4 | ap-south-5 | B2 |  |
|   rn-east-17786  | 5 | eu-central-2 | B2 |  |
|   rn-east-17817  | 1 | eu-central-2 | B2 |  |
|   rn-east-17817  | 2 | eu-central-2 | B2 |  |
|   rn-east-17817  | 3 | eu-central-2 | B2 |  |
|   rn-east-17817  | 4 | eu-central-2 | B2 |  |
|   rn-east-17817  | 5 | eu-central-2 | B2 |  |
|   rn-east-17846  | 1 | ap-south-5 | B2 |  |
|   rn-east-17846  | 2 | ap-south-5 | B2 |  |
|   rn-east-17846  | 3 | ap-south-5 | B2 |  |
|   rn-east-17846  | 4 | ap-south-5 | B2 |  |
|   rn-east-17846  | 5 | ap-south-5 | B2 |  |
|   rn-east-17870  | 1 | eu-central-2 | B2 |  |
|   rn-east-17870  | 2 | eu-central-2 | B2 |  |
|   rn-east-17870  | 3 | eu-central-2 | B2 |  |
|   rn-east-17870  | 4 | eu-central-2 | B2 |  |
|   rn-east-17870  | 5 | eu-central-2 | B2 |  |
|   rn-east-17902  | 1 | ap-south-5 | B2 |  |
|   rn-east-17902  | 2 | ap-south-5 | B2 |  |
|   rn-east-17902  | 3 | ap-south-5 | B2 |  |
|   rn-east-17902  | 4 | ap-south-5 | B2 |  |
|   rn-east-17902  | 5 | ap-south-5 | B2 |  |
|   rn-east-17928  | 1 | eu-central-2 | B2 |  |
|   rn-east-17928  | 2 | eu-central-2 | B2 |  |
|   rn-east-17928  | 3 | eu-central-2 | B2 |  |
|   rn-east-17928  | 4 | eu-central-2 | B2 |  |
|   rn-east-17928  | 5 | eu-central-2 | B2 |  |
|   rn-east-17958  | 1 | ap-south-5 | B2 |  |
|   rn-east-17958  | 2 | ap-south-5 | B2 |  |
|   rn-east-17958  | 3 | ap-south-5 | B2 |  |
|   rn-east-17958  | 4 | ap-south-5 | B2 |  |
|   rn-east-17958  | 5 | ap-south-5 | B2 |  |
|   rn-east-17985  | 1 | eu-central-2 | B2 |  |
|   rn-east-17985  | 2 | eu-central-2 | B2 |  |
|   rn-east-17985  | 3 | eu-central-2 | B2 |  |
|   rn-east-17985  | 4 | eu-central-2 | B2 |  |
|   rn-east-17985  | 5 | eu-central-2 | B2 |  |
|   rn-east-18012  | 1 | ap-south-5 | B2 |  |
|   rn-east-18012  | 2 | ap-south-5 | B2 |  |
|   rn-east-18012  | 3 | ap-south-5 | B2 |  |
|   rn-east-18012  | 4 | ap-south-5 | B2 |  |
|   rn-east-18012  | 5 | ap-south-5 | B2 |  |
|   rn-east-18036  | 1 | eu-central-2 | B2 |  |
|   rn-east-18036  | 2 | eu-central-2 | B2 |  |
|   rn-east-18036  | 3 | eu-central-2 | B2 |  |
|   rn-east-18036  | 4 | eu-central-2 | B2 |  |
|   rn-east-18036  | 5 | ap-south-5 | B2 |  |
|   rn-east-18067  | 1 | ap-south-5 | B2 |  |
|   rn-east-18067  | 2 | ap-south-5 | B2 |  |
|   rn-east-18067  | 3 | ap-south-5 | B2 |  |
|   rn-east-18067  | 4 | ap-south-5 | B2 |  |
|   rn-east-18067  | 5 | ap-south-5 | B2 |  |
|   rn-east-18096  | 1 | eu-central-2 | B2 |  |
|   rn-east-18096  | 2 | eu-central-2 | B2 |  |
|   rn-east-18096  | 3 | eu-central-2 | B2 |  |
|   rn-east-18096  | 4 | eu-central-2 | B2 |  |
|   rn-east-18096  | 5 | eu-central-2 | B2 |  |
|   rn-east-18120  | 1 | ap-south-5 | B2 |  |
|   rn-east-18120  | 2 | ap-south-5 | B2 |  |
|   rn-east-18120  | 3 | ap-south-5 | B2 |  |
|   rn-east-18120  | 4 | ap-south-5 | B2 |  |
|   rn-east-18120  | 5 | ap-south-5 | B2 |  |
|   rn-east-18148  | 1 | eu-central-2 | B2 |  |
|   rn-east-18148  | 2 | eu-central-2 | B2 |  |
|   rn-east-18148  | 3 | eu-central-2 | B2 |  |
|   rn-east-18148  | 4 | eu-central-2 | B2 |  |
|   rn-east-18148  | 5 | eu-central-2 | B2 |  |
|   rn-east-18177  | 1 | ap-south-5 | B2 |  |
|   rn-east-18177  | 2 | ap-south-5 | B2 |  |
|   rn-east-18177  | 3 | ap-south-5 | B2 |  |
|   rn-east-18177  | 4 | ap-south-5 | B2 |  |
|   rn-east-18177  | 5 | ap-south-5 | B2 |  |
|   rn-east-18206  | 1 | eu-central-2 | B2 |  |
|   rn-east-18206  | 2 | eu-central-2 | B2 |  |
|   rn-east-18206  | 3 | eu-central-2 | B2 |  |
|   rn-east-18206  | 4 | eu-central-2 | B2 |  |
|   rn-east-18206  | 5 | eu-central-2 | B2 |  |
|   rn-east-18237  | 1 | ap-south-5 | B2 |  |
|   rn-east-18237  | 2 | ap-south-5 | B2 |  |
|   rn-east-18237  | 3 | ap-south-5 | B2 |  |
|   rn-east-18237  | 4 | ap-south-5 | B2 |  |
|   rn-east-18237  | 5 | ap-south-5 | B2 |  |
|   rn-east-18260  | 1 | eu-central-2 | B2 |  |
|   rn-east-18260  | 2 | eu-central-2 | B2 |  |
|   rn-east-18260  | 3 | eu-central-2 | B2 |  |
|   rn-east-18260  | 4 | eu-central-2 | B2 |  |
|   rn-east-18260  | 5 | eu-central-2 | B2 |  |
|   rn-east-18288  | 1 | ap-south-5 | B2 |  |
|   rn-east-18288  | 2 | ap-south-5 | B2 |  |
|   rn-east-18288  | 3 | eu-central-2 | B2 |  |
|   rn-east-18288  | 4 | ap-south-5 | B2 |  |
|   rn-east-18288  | 5 | ap-south-5 | B2 |  |
|   rn-east-18316  | 1 | eu-central-2 | B2 |  |
|   rn-east-18316  | 2 | eu-central-2 | B2 |  |
|   rn-east-18316  | 3 | eu-central-2 | B2 |  |
|   rn-east-18316  | 4 | eu-central-2 | B2 |  |
|   rn-east-18316  | 5 | eu-central-2 | B2 |  |
|   rn-east-18348  | 1 | ap-south-5 | B2 |  |
|   rn-east-18348  | 2 | ap-south-5 | B2 |  |
|   rn-east-18348  | 3 | eu-central-2 | B2 |  |
|   rn-east-18348  | 4 | ap-south-5 | B2 |  |
|   rn-east-18348  | 5 | ap-south-5 | B2 |  |
|   rn-east-18376  | 1 | eu-central-2 | B2 |  |
|   rn-east-18376  | 2 | eu-central-2 | B2 |  |
|   rn-east-18376  | 3 | eu-central-2 | B2 |  |
|   rn-east-18376  | 4 | ap-south-5 | B2 |  |
|   rn-east-18376  | 5 | eu-central-2 | B2 |  |
|   rn-east-18404  | 1 | ap-south-5 | B2 |  |
|   rn-east-18404  | 2 | ap-south-5 | B2 |  |
|   rn-east-18404  | 3 | ap-south-5 | B2 |  |
|   rn-east-18404  | 4 | ap-south-5 | B2 |  |
|   rn-east-18404  | 5 | ap-south-5 | B2 |  |
|   rn-east-18429  | 1 | eu-central-2 | B2 |  |
|   rn-east-18429  | 2 | eu-central-2 | B2 |  |
|   rn-east-18429  | 3 | eu-central-2 | B2 |  |
|   rn-east-18429  | 4 | eu-central-2 | B2 |  |
|   rn-east-18429  | 5 | eu-central-2 | B2 |  |
|   rn-east-18456  | 1 | ap-south-5 | B2 |  |
|   rn-east-18456  | 2 | eu-central-2 | B2 |  |
|   rn-east-18456  | 3 | ap-south-5 | B2 |  |
|   rn-east-18456  | 4 | ap-south-5 | B2 |  |
|   rn-east-18456  | 5 | ap-south-5 | B2 |  |
|   rn-east-18487  | 1 | eu-central-2 | B2 |  |
|   rn-east-18487  | 2 | eu-central-2 | B2 |  |
|   rn-east-18487  | 3 | eu-central-2 | B2 |  |
|   rn-east-18487  | 4 | eu-central-2 | B2 |  |
|   rn-east-18487  | 5 | eu-central-2 | B2 |  |
|   rn-east-18512  | 1 | ap-south-5 | B2 |  |
|   rn-east-18512  | 2 | ap-south-5 | B2 |  |
|   rn-east-18512  | 3 | ap-south-5 | B2 |  |
|   rn-east-18512  | 4 | ap-south-5 | B2 |  |
|   rn-east-18512  | 5 | ap-south-5 | B2 |  |
|   rn-east-18543  | 1 | eu-central-2 | B2 |  |
|   rn-east-18543  | 2 | eu-central-2 | B2 |  |
|   rn-east-18543  | 3 | eu-central-2 | B2 |  |
|   rn-east-18543  | 4 | eu-central-2 | B2 |  |
|   rn-east-18543  | 5 | eu-central-2 | B2 |  |
|   rn-east-18568  | 1 | ap-south-5 | B2 |  |
|   rn-east-18568  | 2 | ap-south-5 | B2 |  |
|   rn-east-18568  | 3 | eu-central-2 | B2 |  |
|   rn-east-18568  | 4 | ap-south-5 | B2 |  |
|   rn-east-18568  | 5 | ap-south-5 | B2 |  |
|   rn-east-18596  | 1 | eu-central-2 | B2 |  |
|   rn-east-18596  | 2 | eu-central-2 | B2 |  |
|   rn-east-18596  | 3 | ap-south-5 | B2 |  |
|   rn-east-18596  | 4 | eu-central-2 | B2 |  |
|   rn-east-18596  | 5 | eu-central-2 | B2 |  |
|   rn-east-18630  | 1 | ap-south-5 | B2 |  |
|   rn-east-18630  | 2 | ap-south-5 | B2 |  |
|   rn-east-18630  | 3 | ap-south-5 | B2 |  |
|   rn-east-18630  | 4 | ap-south-5 | B2 |  |
|   rn-east-18630  | 5 | ap-south-5 | B2 |  |
|   rn-east-18656  | 1 | eu-central-2 | B2 |  |
|   rn-east-18656  | 2 | eu-central-2 | B2 |  |
|   rn-east-18656  | 3 | eu-central-2 | B2 |  |
|   rn-east-18656  | 4 | eu-central-2 | B2 |  |
|   rn-east-18656  | 5 | eu-central-2 | B2 |  |
|   rn-east-18685  | 1 | ap-south-5 | B2 |  |
|   rn-east-18685  | 2 | ap-south-5 | B2 |  |
|   rn-east-18685  | 3 | ap-south-5 | B2 |  |
|   rn-east-18685  | 4 | ap-south-5 | B2 |  |
|   rn-east-18685  | 5 | ap-south-5 | B2 |  |
|   rn-east-18709  | 1 | eu-central-2 | B2 |  |
|   rn-east-18709  | 2 | eu-central-2 | B2 |  |
|   rn-east-18709  | 3 | ap-south-5 | B2 |  |
|   rn-east-18709  | 4 | eu-central-2 | B2 |  |
|   rn-east-18709  | 5 | eu-central-2 | B2 |  |
|   rn-east-18738  | 1 | ap-south-5 | B2 |  |
|   rn-east-18738  | 2 | eu-central-2 | B2 |  |
|   rn-east-18738  | 3 | eu-central-2 | B2 |  |
|   rn-east-18738  | 4 | ap-south-5 | B2 |  |
|   rn-east-18738  | 5 | ap-south-5 | B2 |  |
|   rn-east-18767  | 1 | eu-central-2 | B2 |  |
|   rn-east-18767  | 2 | eu-central-2 | B2 |  |
|   rn-east-18767  | 3 | eu-central-2 | B2 |  |
|   rn-east-18767  | 4 | eu-central-2 | B2 |  |
|   rn-east-18767  | 5 | eu-central-2 | B2 |  |
|   rn-east-18797  | 1 | ap-south-5 | B2 |  |
|   rn-east-18797  | 2 | ap-south-5 | B2 |  |
|   rn-east-18797  | 3 | ap-south-5 | B2 |  |
|   rn-east-18797  | 4 | ap-south-5 | B2 |  |
|   rn-east-18797  | 5 | ap-south-5 | B2 |  |
|   rn-east-18820  | 1 | eu-central-2 | B2 |  |
|   rn-east-18820  | 2 | eu-central-2 | B2 |  |
|   rn-east-18820  | 3 | eu-central-2 | B2 |  |
|   rn-east-18820  | 4 | eu-central-2 | B2 |  |
|   rn-east-18820  | 5 | eu-central-2 | B2 |  |
|   rn-east-18849  | 1 | ap-south-5 | B2 |  |
|   rn-east-18849  | 2 | ap-south-5 | B2 |  |
|   rn-east-18849  | 3 | ap-south-5 | B2 |  |
|   rn-east-18849  | 4 | eu-central-2 | B2 |  |
|   rn-east-18849  | 5 | ap-south-5 | B2 |  |
|   rn-east-18879  | 1 | eu-central-2 | B2 |  |
|   rn-east-18879  | 2 | eu-central-2 | B2 |  |
|   rn-east-18879  | 3 | ap-south-5 | B2 |  |
|   rn-east-18879  | 4 | eu-central-2 | B2 |  |
|   rn-east-18879  | 5 | eu-central-2 | B2 |  |
|   rn-east-18904  | 1 | ap-south-5 | B2 |  |
|   rn-east-18904  | 2 | ap-south-5 | B2 |  |
|   rn-east-18904  | 3 | eu-central-2 | B2 |  |
|   rn-east-18904  | 4 | ap-south-5 | B2 |  |
|   rn-east-18904  | 5 | ap-south-5 | B2 |  |
|   rn-east-18932  | 1 | eu-central-2 | B2 |  |
|   rn-east-18932  | 2 | eu-central-2 | B2 |  |
|   rn-east-18932  | 3 | eu-central-2 | B2 |  |
|   rn-east-18932  | 4 | eu-central-2 | B2 |  |
|   rn-east-18932  | 5 | eu-central-2 | B2 |  |
|   rn-east-18964  | 1 | ap-south-5 | B2 |  |
|   rn-east-18964  | 2 | ap-south-5 | B2 |  |
|   rn-east-18964  | 3 | ap-south-5 | B2 |  |
|   rn-east-18964  | 4 | ap-south-5 | B2 |  |
|   rn-east-18964  | 5 | ap-south-5 | B2 |  |
|   rn-east-18988  | 1 | eu-central-2 | B2 |  |
|   rn-east-18988  | 2 | eu-central-2 | B2 |  |
|   rn-east-18988  | 3 | eu-central-2 | B2 |  |
|   rn-east-18988  | 4 | eu-central-2 | B2 |  |
|   rn-east-18988  | 5 | eu-central-2 | B2 |  |
|   rn-east-19016  | 1 | ap-south-5 | B2 |  |
|   rn-east-19016  | 2 | ap-south-5 | B2 |  |
|   rn-east-19016  | 3 | ap-south-5 | B2 |  |
|   rn-east-19016  | 4 | ap-south-5 | B2 |  |
|   rn-east-19016  | 5 | ap-south-5 | B2 |  |
|   rn-east-19049  | 1 | eu-central-2 | B2 |  |
|   rn-east-19049  | 2 | eu-central-2 | B2 |  |
|   rn-east-19049  | 3 | eu-central-2 | B2 |  |
|   rn-east-19049  | 4 | eu-central-2 | B2 |  |
|   rn-east-19049  | 5 | eu-central-2 | B2 |  |
|   rn-east-19075  | 1 | ap-south-5 | B2 |  |
|   rn-east-19075  | 2 | ap-south-5 | B2 |  |
|   rn-east-19075  | 3 | ap-south-5 | B2 |  |
|   rn-east-19075  | 4 | ap-south-5 | B2 |  |
|   rn-east-19075  | 5 | ap-south-5 | B2 |  |
|   rn-east-19105  | 1 | eu-central-2 | B2 |  |
|   rn-east-19105  | 2 | eu-central-2 | B2 |  |
|   rn-east-19105  | 3 | eu-central-2 | B2 |  |
|   rn-east-19105  | 4 | eu-central-2 | B2 |  |
|   rn-east-19105  | 5 | eu-central-2 | B2 |  |
|   rn-east-19133  | 1 | ap-south-5 | B2 |  |
|   rn-east-19133  | 2 | ap-south-5 | B2 |  |
|   rn-east-19133  | 3 | ap-south-5 | B2 |  |
|   rn-east-19133  | 4 | ap-south-5 | B2 |  |
|   rn-east-19133  | 5 | ap-south-5 | B2 |  |
|   rn-east-19161  | 1 | eu-central-2 | B2 |  |
|   rn-east-19161  | 2 | eu-central-2 | B2 |  |
|   rn-east-19161  | 3 | eu-central-2 | B2 |  |
|   rn-east-19161  | 4 | eu-central-2 | B2 |  |
|   rn-east-19161  | 5 | eu-central-2 | B2 |  |
|   rn-east-19190  | 1 | ap-south-5 | B2 |  |
|   rn-east-19190  | 2 | ap-south-5 | B2 |  |
|   rn-east-19190  | 3 | ap-south-5 | B2 |  |
|   rn-east-19190  | 4 | ap-south-5 | B2 |  |
|   rn-east-19190  | 5 | ap-south-5 | B2 |  |
|   rn-east-19214  | 1 | eu-central-2 | B2 |  |
|   rn-east-19214  | 2 | eu-central-2 | B2 |  |
|   rn-east-19214  | 3 | eu-central-2 | B2 |  |
|   rn-east-19214  | 4 | eu-central-2 | B2 |  |
|   rn-east-19214  | 5 | eu-central-2 | B2 |  |
|   rn-east-19240  | 1 | ap-south-5 | B2 |  |
|   rn-east-19240  | 2 | ap-south-5 | B2 |  |
|   rn-east-19240  | 3 | ap-south-5 | B2 |  |
|   rn-east-19240  | 4 | ap-south-5 | B2 |  |
|   rn-east-19240  | 5 | ap-south-5 | B2 |  |
|   rn-east-19270  | 1 | eu-central-2 | B2 |  |
|   rn-east-19270  | 2 | eu-central-2 | B2 |  |
|   rn-east-19270  | 3 | eu-central-2 | B2 |  |
|   rn-east-19270  | 4 | ap-south-5 | B2 |  |
|   rn-east-19270  | 5 | eu-central-2 | B2 |  |
|   rn-east-19300  | 1 | ap-south-5 | B2 |  |
|   rn-east-19300  | 2 | ap-south-5 | B2 |  |
|   rn-east-19300  | 3 | ap-south-5 | B2 |  |
|   rn-east-19300  | 4 | ap-south-5 | B2 |  |
|   rn-east-19300  | 5 | ap-south-5 | B2 |  |
|   rn-east-19329  | 1 | eu-central-2 | B2 |  |
|   rn-east-19329  | 2 | eu-central-2 | B2 |  |
|   rn-east-19329  | 3 | eu-central-2 | B2 |  |
|   rn-east-19329  | 4 | eu-central-2 | B2 |  |
|   rn-east-19329  | 5 | eu-central-2 | B2 |  |
|   rn-east-19356  | 1 | ap-south-5 | B2 |  |
|   rn-east-19356  | 2 | ap-south-5 | B2 |  |
|   rn-east-19356  | 3 | ap-south-5 | B2 |  |
|   rn-east-19356  | 4 | ap-south-5 | B2 |  |
|   rn-east-19356  | 5 | ap-south-5 | B2 |  |
|   rn-east-19386  | 1 | eu-central-2 | B2 |  |
|   rn-east-19386  | 2 | eu-central-2 | B2 |  |
|   rn-east-19386  | 3 | eu-central-2 | B2 |  |
|   rn-east-19386  | 4 | eu-central-2 | B2 |  |
|   rn-east-19386  | 5 | eu-central-2 | B2 |  |
|   rn-east-19411  | 1 | ap-south-5 | B2 |  |
|   rn-east-19411  | 2 | ap-south-5 | B2 |  |
|   rn-east-19411  | 3 | ap-south-5 | B2 |  |
|   rn-east-19411  | 4 | ap-south-5 | B2 |  |
|   rn-east-19411  | 5 | ap-south-5 | B2 |  |
|   rn-east-19439  | 1 | eu-central-2 | B2 |  |
|   rn-east-19439  | 2 | eu-central-2 | B2 |  |
|   rn-east-19439  | 3 | eu-central-2 | B2 |  |
|   rn-east-19439  | 4 | eu-central-2 | B2 |  |
|   rn-east-19439  | 5 | eu-central-2 | B2 |  |
|   rn-east-19470  | 1 | ap-south-5 | B2 |  |
|   rn-east-19470  | 2 | ap-south-5 | B2 |  |
|   rn-east-19470  | 3 | ap-south-5 | B2 |  |
|   rn-east-19470  | 4 | ap-south-5 | B2 |  |
|   rn-east-19470  | 5 | ap-south-5 | B2 |  |
|   rn-east-19496  | 1 | eu-central-2 | B2 |  |
|   rn-east-19496  | 2 | eu-central-2 | B2 |  |
|   rn-east-19496  | 3 | eu-central-2 | B2 |  |
|   rn-east-19496  | 4 | ap-south-5 | B2 |  |
|   rn-east-19496  | 5 | eu-central-2 | B2 |  |
| RN-EAST-19521 | 1 | ap-south-5 | B3 |  |
| RN-EAST-19521 | 2 | ap-south-5 | B3 |  |
| RN-EAST-19521 | 3 | ap-south-5 | B3 |  |
| RN-EAST-19521 | 4 | ap-south-5 | B3 |  |
| RN-EAST-19521 | 5 | ap-south-5 | B3 |  |
| RN-EAST-19553 | 1 | eu-central-2 | B3 |  |
| RN-EAST-19553 | 2 | eu-central-2 | B3 |  |
| RN-EAST-19553 | 3 | eu-central-2 | B3 |  |
| RN-EAST-19553 | 4 | eu-central-2 | B3 |  |
| RN-EAST-19553 | 5 | eu-central-2 | B3 |  |
| RN-EAST-19580 | 1 | ap-south-5 | B3 |  |
| RN-EAST-19580 | 2 | ap-south-5 | B3 |  |
| RN-EAST-19580 | 3 | ap-south-5 | B3 |  |
| RN-EAST-19580 | 4 | ap-south-5 | B3 |  |
| RN-EAST-19580 | 5 | ap-south-5 | B3 |  |
| RN-EAST-19607 | 1 | eu-central-2 | B3 |  |
| RN-EAST-19607 | 2 | eu-central-2 | B3 |  |
| RN-EAST-19607 | 3 | eu-central-2 | B3 |  |
| RN-EAST-19607 | 4 | eu-central-2 | B3 |  |
| RN-EAST-19607 | 5 | eu-central-2 | B3 |  |
| RN-EAST-19633 | 1 | ap-south-5 | B3 |  |
| RN-EAST-19633 | 2 | ap-south-5 | B3 |  |
| RN-EAST-19633 | 3 | ap-south-5 | B3 |  |
| RN-EAST-19633 | 4 | ap-south-5 | B3 |  |
| RN-EAST-19633 | 5 | ap-south-5 | B3 |  |
| RN-EAST-19661 | 1 | eu-central-2 | B3 |  |
| RN-EAST-19661 | 2 | eu-central-2 | B3 |  |
| RN-EAST-19661 | 3 | eu-central-2 | B3 |  |
| RN-EAST-19661 | 4 | eu-central-2 | B3 |  |
| RN-EAST-19661 | 5 | ap-south-5 | B3 |  |
| RN-EAST-19691 | 1 | ap-south-5 | B3 |  |
| RN-EAST-19691 | 2 | ap-south-5 | B3 |  |
| RN-EAST-19691 | 3 | ap-south-5 | B3 |  |
| RN-EAST-19691 | 4 | ap-south-5 | B3 |  |
| RN-EAST-19691 | 5 | ap-south-5 | B3 |  |
| RN-EAST-19720 | 1 | eu-central-2 | B3 |  |
| RN-EAST-19720 | 2 | eu-central-2 | B3 |  |
| RN-EAST-19720 | 3 | eu-central-2 | B3 |  |
| RN-EAST-19720 | 4 | eu-central-2 | B3 |  |
| RN-EAST-19720 | 5 | eu-central-2 | B3 |  |
| RN-EAST-19744 | 1 | ap-south-5 | B3 |  |
| RN-EAST-19744 | 2 | ap-south-5 | B3 |  |
| RN-EAST-19744 | 3 | ap-south-5 | B3 |  |
| RN-EAST-19744 | 4 | ap-south-5 | B3 |  |
| RN-EAST-19744 | 5 | ap-south-5 | B3 |  |
| RN-EAST-19773 | 1 | eu-central-2 | B3 |  |
| RN-EAST-19773 | 2 | eu-central-2 | B3 |  |
| RN-EAST-19773 | 3 | eu-central-2 | B3 |  |
| RN-EAST-19773 | 4 | eu-central-2 | B3 |  |
| RN-EAST-19773 | 5 | eu-central-2 | B3 |  |
| RN-EAST-19802 | 1 | ap-south-5 | B3 |  |
| RN-EAST-19802 | 2 | ap-south-5 | B3 |  |
| RN-EAST-19802 | 3 | ap-south-5 | B3 |  |
| RN-EAST-19802 | 4 | ap-south-5 | B3 |  |
| RN-EAST-19802 | 5 | ap-south-5 | B3 |  |
| RN-EAST-19834 | 1 | eu-central-2 | B3 |  |
| RN-EAST-19834 | 2 | eu-central-2 | B3 |  |
| RN-EAST-19834 | 3 | eu-central-2 | B3 |  |
| RN-EAST-19834 | 4 | eu-central-2 | B3 |  |
| RN-EAST-19834 | 5 | eu-central-2 | B3 |  |
| RN-EAST-19858 | 1 | ap-south-5 | B3 |  |
| RN-EAST-19858 | 2 | ap-south-5 | B3 |  |
| RN-EAST-19858 | 3 | ap-south-5 | B3 |  |
| RN-EAST-19858 | 4 | ap-south-5 | B3 |  |
| RN-EAST-19858 | 5 | ap-south-5 | B3 |  |
| RN-EAST-19890 | 1 | eu-central-2 | B3 |  |
| RN-EAST-19890 | 2 | eu-central-2 | B3 |  |
| RN-EAST-19890 | 3 | eu-central-2 | B3 |  |
| RN-EAST-19890 | 4 | eu-central-2 | B3 |  |
| RN-EAST-19890 | 5 | ap-south-5 | B3 |  |
| RN-EAST-19917 | 1 | ap-south-5 | B3 |  |
| RN-EAST-19917 | 2 | ap-south-5 | B3 |  |
| RN-EAST-19917 | 3 | ap-south-5 | B3 |  |
| RN-EAST-19917 | 4 | ap-south-5 | B3 |  |
| RN-EAST-19917 | 5 | ap-south-5 | B3 |  |
| RN-EAST-19945 | 1 | eu-central-2 | B3 |  |
| RN-EAST-19945 | 2 | eu-central-2 | B3 |  |
| RN-EAST-19945 | 3 | eu-central-2 | B3 |  |
| RN-EAST-19945 | 4 | eu-central-2 | B3 |  |
| RN-EAST-19945 | 5 | eu-central-2 | B3 |  |
| RN-EAST-19968 | 1 | ap-south-5 | B3 |  |
| RN-EAST-19968 | 2 | eu-central-2 | B3 |  |
| RN-EAST-19968 | 3 | ap-south-5 | B3 |  |
| RN-EAST-19968 | 4 | ap-south-5 | B3 |  |
| RN-EAST-19968 | 5 | ap-south-5 | B3 |  |
| RN-EAST-20002 | 1 | eu-central-2 | B3 |  |
| RN-EAST-20002 | 2 | eu-central-2 | B3 |  |
| RN-EAST-20002 | 3 | eu-central-2 | B3 |  |
| RN-EAST-20002 | 4 | eu-central-2 | B3 |  |
| RN-EAST-20002 | 5 | eu-central-2 | B3 |  |
| RN-EAST-20028 | 1 | ap-south-5 | B3 |  |
| RN-EAST-20028 | 2 | ap-south-5 | B3 |  |
| RN-EAST-20028 | 3 | ap-south-5 | B3 |  |
| RN-EAST-20028 | 4 | ap-south-5 | B3 |  |
| RN-EAST-20028 | 5 | ap-south-5 | B3 |  |
| RN-EAST-20057 | 1 | eu-central-2 | B3 |  |
| RN-EAST-20057 | 2 | eu-central-2 | B3 |  |
| RN-EAST-20057 | 3 | eu-central-2 | B3 |  |
| RN-EAST-20057 | 4 | eu-central-2 | B3 |  |
| RN-EAST-20057 | 5 | eu-central-2 | B3 |  |
| RN-EAST-20081 | 1 | ap-south-5 | B3 |  |
| RN-EAST-20081 | 2 | ap-south-5 | B3 |  |
| RN-EAST-20081 | 3 | ap-south-5 | B3 |  |
| RN-EAST-20081 | 4 | ap-south-5 | B3 |  |
| RN-EAST-20081 | 5 | ap-south-5 | B3 |  |
| RN-EAST-20113 | 1 | eu-central-2 | B3 |  |
| RN-EAST-20113 | 2 | eu-central-2 | B3 |  |
| RN-EAST-20113 | 3 | eu-central-2 | B3 |  |
| RN-EAST-20113 | 4 | ap-south-5 | B3 |  |
| RN-EAST-20113 | 5 | eu-central-2 | B3 |  |
| RN-EAST-20137 | 1 | ap-south-5 | B3 |  |
| RN-EAST-20137 | 2 | ap-south-5 | B3 |  |
| RN-EAST-20137 | 3 | ap-south-5 | B3 |  |
| RN-EAST-20137 | 4 | ap-south-5 | B3 |  |
| RN-EAST-20137 | 5 | ap-south-5 | B3 |  |
| RN-EAST-20166 | 1 | eu-central-2 | B3 |  |
| RN-EAST-20166 | 2 | eu-central-2 | B3 |  |
| RN-EAST-20166 | 3 | eu-central-2 | B3 |  |
| RN-EAST-20166 | 4 | eu-central-2 | B3 |  |
| RN-EAST-20166 | 5 | eu-central-2 | B3 |  |
| RN-EAST-20198 | 1 | ap-south-5 | B3 |  |
| RN-EAST-20198 | 2 | ap-south-5 | B3 |  |
| RN-EAST-20198 | 3 | ap-south-5 | B3 |  |
| RN-EAST-20198 | 4 | ap-south-5 | B3 |  |
| RN-EAST-20198 | 5 | ap-south-5 | B3 |  |
| RN-EAST-20220 | 1 | eu-central-2 | B3 |  |
| RN-EAST-20220 | 2 | eu-central-2 | B3 |  |
| RN-EAST-20220 | 3 | eu-central-2 | B3 |  |
| RN-EAST-20220 | 4 | eu-central-2 | B3 |  |
| RN-EAST-20220 | 5 | eu-central-2 | B3 |  |
| RN-EAST-20254 | 1 | ap-south-5 | B3 |  |
| RN-EAST-20254 | 2 | ap-south-5 | B3 |  |
| RN-EAST-20254 | 3 | ap-south-5 | B3 |  |
| RN-EAST-20254 | 4 | ap-south-5 | B3 |  |
| RN-EAST-20254 | 5 | ap-south-5 | B3 |  |
| RN-EAST-20279 | 1 | eu-central-2 | B3 |  |
| RN-EAST-20279 | 2 | eu-central-2 | B3 |  |
| RN-EAST-20279 | 3 | eu-central-2 | B3 |  |
| RN-EAST-20279 | 4 | ap-south-5 | B3 |  |
| RN-EAST-20279 | 5 | eu-central-2 | B3 |  |
| RN-EAST-20304 | 1 | ap-south-5 | B3 |  |
| RN-EAST-20304 | 2 | ap-south-5 | B3 |  |
| RN-EAST-20304 | 3 | eu-central-2 | B3 |  |
| RN-EAST-20304 | 4 | ap-south-5 | B3 |  |
| RN-EAST-20304 | 5 | ap-south-5 | B3 |  |
| RN-EAST-20338 | 1 | eu-central-2 | B3 |  |
| RN-EAST-20338 | 2 | eu-central-2 | B3 |  |
| RN-EAST-20338 | 3 | eu-central-2 | B3 |  |
| RN-EAST-20338 | 4 | eu-central-2 | B3 |  |
| RN-EAST-20338 | 5 | eu-central-2 | B3 |  |
| RN-EAST-20364 | 1 | ap-south-5 | B3 |  |
| RN-EAST-20364 | 2 | ap-south-5 | B3 |  |
| RN-EAST-20364 | 3 | ap-south-5 | B3 |  |
| RN-EAST-20364 | 4 | ap-south-5 | B3 |  |
| RN-EAST-20364 | 5 | ap-south-5 | B3 |  |
| RN-EAST-20389 | 1 | eu-central-2 | B3 |  |
| RN-EAST-20389 | 2 | eu-central-2 | B3 |  |
| RN-EAST-20389 | 3 | eu-central-2 | B3 |  |
| RN-EAST-20389 | 4 | eu-central-2 | B3 |  |
| RN-EAST-20389 | 5 | eu-central-2 | B3 |  |
| RN-EAST-20420 | 1 | ap-south-5 | B3 |  |
| RN-EAST-20420 | 2 | ap-south-5 | B3 |  |
| RN-EAST-20420 | 3 | ap-south-5 | B3 |  |
| RN-EAST-20420 | 4 | ap-south-5 | B3 |  |
| RN-EAST-20420 | 5 | ap-south-5 | B3 |  |
| RN-EAST-20450 | 1 | eu-central-2 | B3 |  |
| RN-EAST-20450 | 2 | eu-central-2 | B3 |  |
| RN-EAST-20450 | 3 | eu-central-2 | B3 |  |
| RN-EAST-20450 | 4 | eu-central-2 | B3 |  |
| RN-EAST-20450 | 5 | eu-central-2 | B3 |  |
| RN-EAST-20472 | 1 | ap-south-5 | B3 |  |
| RN-EAST-20472 | 2 | ap-south-5 | B3 |  |
| RN-EAST-20472 | 3 | ap-south-5 | B3 |  |
| RN-EAST-20472 | 4 | ap-south-5 | B3 |  |
| RN-EAST-20472 | 5 | ap-south-5 | B3 |  |
| RN-EAST-20504 | 1 | eu-central-2 | B3 |  |
| RN-EAST-20504 | 2 | eu-central-2 | B3 |  |
| RN-EAST-20504 | 3 | ap-south-5 | B3 |  |
| RN-EAST-20504 | 4 | eu-central-2 | B3 |  |
| RN-EAST-20504 | 5 | eu-central-2 | B3 |  |
| RN-EAST-20531 | 1 | ap-south-5 | B3 |  |
| RN-EAST-20531 | 2 | ap-south-5 | B3 |  |
| RN-EAST-20531 | 3 | ap-south-5 | B3 |  |
| RN-EAST-20531 | 4 | ap-south-5 | B3 |  |
| RN-EAST-20531 | 5 | ap-south-5 | B3 |  |
| RN-EAST-20559 | 1 | eu-central-2 | B3 |  |
| RN-EAST-20559 | 2 | eu-central-2 | B3 |  |
| RN-EAST-20559 | 3 | eu-central-2 | B3 |  |
| RN-EAST-20559 | 4 | eu-central-2 | B3 |  |
| RN-EAST-20559 | 5 | eu-central-2 | B3 |  |
| RN-EAST-20590 | 1 | ap-south-5 | B3 |  |
| RN-EAST-20590 | 2 | ap-south-5 | B3 |  |
| RN-EAST-20590 | 3 | eu-central-2 | B3 |  |
| RN-EAST-20590 | 4 | ap-south-5 | B3 |  |
| RN-EAST-20590 | 5 | ap-south-5 | B3 |  |
| RN-EAST-20616 | 1 | eu-central-2 | B3 |  |
| RN-EAST-20616 | 2 | eu-central-2 | B3 |  |
| RN-EAST-20616 | 3 | eu-central-2 | B3 |  |
| RN-EAST-20616 | 4 | eu-central-2 | B3 |  |
| RN-EAST-20616 | 5 | eu-central-2 | B3 |  |
| RN-EAST-20640 | 1 | ap-south-5 | B3 |  |
| RN-EAST-20640 | 2 | ap-south-5 | B3 |  |
| RN-EAST-20640 | 3 | ap-south-5 | B3 |  |
| RN-EAST-20640 | 4 | ap-south-5 | B3 |  |
| RN-EAST-20640 | 5 | ap-south-5 | B3 |  |
| RN-EAST-20670 | 1 | eu-central-2 | B3 |  |
| RN-EAST-20670 | 2 | eu-central-2 | B3 |  |
| RN-EAST-20670 | 3 | eu-central-2 | B3 |  |
| RN-EAST-20670 | 4 | eu-central-2 | B3 |  |
| RN-EAST-20670 | 5 | eu-central-2 | B3 |  |
| RN-EAST-20696 | 1 | ap-south-5 | B3 |  |
| RN-EAST-20696 | 2 | ap-south-5 | B3 |  |
| RN-EAST-20696 | 3 | ap-south-5 | B3 |  |
| RN-EAST-20696 | 4 | ap-south-5 | B3 |  |
| RN-EAST-20696 | 5 | ap-south-5 | B3 |  |
| RN-EAST-20728 | 1 | eu-central-2 | B3 |  |
| RN-EAST-20728 | 2 | eu-central-2 | B3 |  |
| RN-EAST-20728 | 3 | eu-central-2 | B3 |  |
| RN-EAST-20728 | 4 | eu-central-2 | B3 |  |
| RN-EAST-20728 | 5 | eu-central-2 | B3 |  |
| RN-EAST-20753 | 1 | ap-south-5 | B3 |  |
| RN-EAST-20753 | 2 | ap-south-5 | B3 |  |
| RN-EAST-20753 | 3 | ap-south-5 | B3 |  |
| RN-EAST-20753 | 4 | ap-south-5 | B3 |  |
| RN-EAST-20753 | 5 | ap-south-5 | B3 |  |
| RN-EAST-20786 | 1 | eu-central-2 | B3 |  |
| RN-EAST-20786 | 2 | ap-south-5 | B3 |  |
| RN-EAST-20786 | 3 | eu-central-2 | B3 |  |
| RN-EAST-20786 | 4 | eu-central-2 | B3 |  |
| RN-EAST-20786 | 5 | eu-central-2 | B3 |  |
| RN-EAST-20812 | 1 | ap-south-5 | B3 |  |
| RN-EAST-20812 | 2 | ap-south-5 | B3 |  |
| RN-EAST-20812 | 3 | ap-south-5 | B3 |  |
| RN-EAST-20812 | 4 | ap-south-5 | B3 |  |
| RN-EAST-20812 | 5 | ap-south-5 | B3 |  |
| RN-EAST-20839 | 1 | eu-central-2 | B3 |  |
| RN-EAST-20839 | 2 | eu-central-2 | B3 |  |
| RN-EAST-20839 | 3 | eu-central-2 | B3 |  |
| RN-EAST-20839 | 4 | ap-south-5 | B3 |  |
| RN-EAST-20839 | 5 | eu-central-2 | B3 |  |
| RN-EAST-20866 | 1 | ap-south-5 | B3 |  |
| RN-EAST-20866 | 2 | ap-south-5 | B3 |  |
| RN-EAST-20866 | 3 | ap-south-5 | B3 |  |
| RN-EAST-20866 | 4 | ap-south-5 | B3 |  |
| RN-EAST-20866 | 5 | ap-south-5 | B3 |  |
| RN-EAST-20895 | 1 | eu-central-2 | B3 |  |
| RN-EAST-20895 | 2 | ap-south-5 | B3 |  |
| RN-EAST-20895 | 3 | eu-central-2 | B3 |  |
| RN-EAST-20895 | 4 | eu-central-2 | B3 |  |
| RN-EAST-20895 | 5 | eu-central-2 | B3 |  |
| RN-EAST-20926 | 1 | ap-south-5 | B3 |  |
| RN-EAST-20926 | 2 | ap-south-5 | B3 |  |
| RN-EAST-20926 | 3 | ap-south-5 | B3 |  |
| RN-EAST-20926 | 4 | ap-south-5 | B3 |  |
| RN-EAST-20926 | 5 | ap-south-5 | B3 |  |
| RN-EAST-20953 | 1 | eu-central-2 | B3 |  |
| RN-EAST-20953 | 2 | eu-central-2 | B3 |  |
| RN-EAST-20953 | 3 | eu-central-2 | B3 |  |
| RN-EAST-20953 | 4 | eu-central-2 | B3 |  |
| RN-EAST-20953 | 5 | eu-central-2 | B3 |  |
| RN-EAST-20978 | 1 | ap-south-5 | B3 |  |
| RN-EAST-20978 | 2 | ap-south-5 | B3 |  |
| RN-EAST-20978 | 3 | ap-south-5 | B3 |  |
| RN-EAST-20978 | 4 | ap-south-5 | B3 |  |
| RN-EAST-20978 | 5 | ap-south-5 | B3 |  |
| RN-EAST-21009 | 1 | eu-central-2 | B3 |  |
| RN-EAST-21009 | 2 | eu-central-2 | B3 |  |
| RN-EAST-21009 | 3 | eu-central-2 | B3 |  |
| RN-EAST-21009 | 4 | eu-central-2 | B3 |  |
| RN-EAST-21009 | 5 | eu-central-2 | B3 |  |
| RN-EAST-21033 | 1 | ap-south-5 | B3 |  |
| RN-EAST-21033 | 2 | ap-south-5 | B3 |  |
| RN-EAST-21033 | 3 | ap-south-5 | B3 |  |
| RN-EAST-21033 | 4 | ap-south-5 | B3 |  |
| RN-EAST-21033 | 5 | ap-south-5 | B3 |  |
| RN-EAST-21061 | 1 | eu-central-2 | B3 |  |
| RN-EAST-21061 | 2 | eu-central-2 | B3 |  |
| RN-EAST-21061 | 3 | eu-central-2 | B3 |  |
| RN-EAST-21061 | 4 | eu-central-2 | B3 |  |
| RN-EAST-21061 | 5 | eu-central-2 | B3 |  |
| RN-EAST-21093 | 1 | ap-south-5 | B3 |  |
| RN-EAST-21093 | 2 | ap-south-5 | B3 |  |
| RN-EAST-21093 | 3 | ap-south-5 | B3 |  |
| RN-EAST-21093 | 4 | ap-south-5 | B3 |  |
| RN-EAST-21093 | 5 | ap-south-5 | B3 |  |
| RN-EAST-21120 | 1 | eu-central-2 | B3 |  |
| RN-EAST-21120 | 2 | eu-central-2 | B3 |  |
| RN-EAST-21120 | 3 | ap-south-5 | B3 |  |
| RN-EAST-21120 | 4 | eu-central-2 | B3 |  |
| RN-EAST-21120 | 5 | eu-central-2 | B3 |  |
| RN-EAST-21148 | 1 | ap-south-5 | B3 |  |
| RN-EAST-21148 | 2 | ap-south-5 | B3 |  |
| RN-EAST-21148 | 3 | ap-south-5 | B3 |  |
| RN-EAST-21148 | 4 | ap-south-5 | B3 |  |
| RN-EAST-21148 | 5 | ap-south-5 | B3 |  |
| RN-EAST-21173 | 1 | eu-central-2 | B3 |  |
| RN-EAST-21173 | 2 | eu-central-2 | B3 |  |
| RN-EAST-21173 | 3 | eu-central-2 | B3 |  |
| RN-EAST-21173 | 4 | eu-central-2 | B3 |  |
| RN-EAST-21173 | 5 | eu-central-2 | B3 |  |
| RN-EAST-21202 | 1 | ap-south-5 | B3 |  |
| RN-EAST-21202 | 2 | ap-south-5 | B3 |  |
| RN-EAST-21202 | 3 | ap-south-5 | B3 |  |
| RN-EAST-21202 | 4 | ap-south-5 | B3 |  |
| RN-EAST-21202 | 5 | ap-south-5 | B3 |  |
| RN-EAST-21229 | 1 | eu-central-2 | B3 |  |
| RN-EAST-21229 | 2 | ap-south-5 | B3 |  |
| RN-EAST-21229 | 3 | eu-central-2 | B3 |  |
| RN-EAST-21229 | 4 | eu-central-2 | B3 |  |
| RN-EAST-21229 | 5 | eu-central-2 | B3 |  |
| RN-EAST-21261 | 1 | ap-south-5 | B3 |  |
| RN-EAST-21261 | 2 | ap-south-5 | B3 |  |
| RN-EAST-21261 | 3 | ap-south-5 | B3 |  |
| RN-EAST-21261 | 4 | ap-south-5 | B3 |  |
| RN-EAST-21261 | 5 | ap-south-5 | B3 |  |
| RN-EAST-21286 | 1 | eu-central-2 | B3 |  |
| RN-EAST-21286 | 2 | eu-central-2 | B3 |  |
| RN-EAST-21286 | 3 | eu-central-2 | B3 |  |
| RN-EAST-21286 | 4 | eu-central-2 | B3 |  |
| RN-EAST-21286 | 5 | eu-central-2 | B3 |  |
| RN-EAST-21313 | 1 | ap-south-5 | B3 |  |
| RN-EAST-21313 | 2 | ap-south-5 | B3 |  |
| RN-EAST-21313 | 3 | ap-south-5 | B3 |  |
| RN-EAST-21313 | 4 | ap-south-5 | B3 |  |
| RN-EAST-21313 | 5 | ap-south-5 | B3 |  |
| RN-EAST-21345 | 1 | eu-central-2 | B3 |  |
| RN-EAST-21345 | 2 | eu-central-2 | B3 |  |
| RN-EAST-21345 | 3 | eu-central-2 | B3 |  |
| RN-EAST-21345 | 4 | ap-south-5 | B3 |  |
| RN-EAST-21345 | 5 | eu-central-2 | B3 |  |
| RN-EAST-21372 | 1 | ap-south-5 | B3 |  |
| RN-EAST-21372 | 2 | ap-south-5 | B3 |  |
| RN-EAST-21372 | 3 | ap-south-5 | B3 |  |
| RN-EAST-21372 | 4 | ap-south-5 | B3 |  |
| RN-EAST-21372 | 5 | ap-south-5 | B3 |  |
| RN-EAST-21402 | 1 | eu-central-2 | B3 |  |
| RN-EAST-21402 | 2 | eu-central-2 | B3 |  |
| RN-EAST-21402 | 3 | eu-central-2 | B3 |  |
| RN-EAST-21402 | 4 | eu-central-2 | B3 |  |
| RN-EAST-21402 | 5 | eu-central-2 | B3 |  |
| RN-EAST-21429 | 1 | ap-south-5 | B3 |  |
| RN-EAST-21429 | 2 | ap-south-5 | B3 |  |
| RN-EAST-21429 | 3 | ap-south-5 | B3 |  |
| RN-EAST-21429 | 4 | ap-south-5 | B3 |  |
| RN-EAST-21429 | 5 | ap-south-5 | B3 |  |
| RN-EAST-21456 | 1 | eu-central-2 | B3 |  |
| RN-EAST-21456 | 2 | eu-central-2 | B3 |  |
| RN-EAST-21456 | 3 | eu-central-2 | B3 |  |
| RN-EAST-21456 | 4 | eu-central-2 | B3 |  |
| RN-EAST-21456 | 5 | eu-central-2 | B3 |  |
| RN-EAST-21482 | 1 | ap-south-5 | B3 |  |
| RN-EAST-21482 | 2 | ap-south-5 | B3 |  |
| RN-EAST-21482 | 3 | ap-south-5 | B3 |  |
| RN-EAST-21482 | 4 | ap-south-5 | B3 |  |
| RN-EAST-21482 | 5 | ap-south-5 | B3 |  |
| RN-EAST-21512 | 1 | eu-central-2 | B3 |  |
| RN-EAST-21512 | 2 | eu-central-2 | B3 |  |
| RN-EAST-21512 | 3 | eu-central-2 | B3 |  |
| RN-EAST-21512 | 4 | eu-central-2 | B3 |  |
| RN-EAST-21512 | 5 | eu-central-2 | B3 |  |
| RN-EAST-21539 | 1 | ap-south-5 | B3 |  |
| RN-EAST-21539 | 2 | ap-south-5 | B3 |  |
| RN-EAST-21539 | 3 | ap-south-5 | B3 |  |
| RN-EAST-21539 | 4 | ap-south-5 | B3 |  |
| RN-EAST-21539 | 5 | ap-south-5 | B3 |  |
| RN-EAST-21569 | 1 | eu-central-2 | B3 |  |
| RN-EAST-21569 | 2 | eu-central-2 | B3 |  |
| RN-EAST-21569 | 3 | eu-central-2 | B3 |  |
| RN-EAST-21569 | 4 | eu-central-2 | B3 |  |
| RN-EAST-21569 | 5 | eu-central-2 | B3 |  |
| RN-EAST-21595 | 1 | ap-south-5 | B3 |  |
| RN-EAST-21595 | 2 | eu-central-2 | B3 |  |
| RN-EAST-21595 | 3 | ap-south-5 | B3 |  |
| RN-EAST-21595 | 4 | ap-south-5 | B3 |  |
| RN-EAST-21595 | 5 | ap-south-5 | B3 |  |
| RN-EAST-21623 | 1 | eu-central-2 | B3 |  |
| RN-EAST-21623 | 2 | eu-central-2 | B3 |  |
| RN-EAST-21623 | 3 | eu-central-2 | B3 |  |
| RN-EAST-21623 | 4 | eu-central-2 | B3 |  |
| RN-EAST-21623 | 5 | eu-central-2 | B3 |  |
| RN-EAST-21653 | 1 | ap-south-5 | B3 |  |
| RN-EAST-21653 | 2 | ap-south-5 | B3 |  |
| RN-EAST-21653 | 3 | ap-south-5 | B3 |  |
| RN-EAST-21653 | 4 | ap-south-5 | B3 |  |
| RN-EAST-21653 | 5 | eu-central-2 | B3 |  |
| RN-EAST-21677 | 1 | eu-central-2 | B3 |  |
| RN-EAST-21677 | 2 | eu-central-2 | B3 |  |
| RN-EAST-21677 | 3 | eu-central-2 | B3 |  |
| RN-EAST-21677 | 4 | eu-central-2 | B3 |  |
| RN-EAST-21677 | 5 | eu-central-2 | B3 |  |
| RN-EAST-21709 | 1 | ap-south-5 | B3 |  |
| RN-EAST-21709 | 2 | ap-south-5 | B3 |  |
| RN-EAST-21709 | 3 | ap-south-5 | B3 |  |
| RN-EAST-21709 | 4 | ap-south-5 | B3 |  |
| RN-EAST-21709 | 5 | ap-south-5 | B3 |  |
| RN-EAST-21734 | 1 | eu-central-2 | B3 |  |
| RN-EAST-21734 | 2 | eu-central-2 | B3 |  |
| RN-EAST-21734 | 3 | eu-central-2 | B3 |  |
| RN-EAST-21734 | 4 | eu-central-2 | B3 |  |
| RN-EAST-21734 | 5 | eu-central-2 | B3 |  |
| RN-EAST-21764 | 1 | ap-south-5 | B3 |  |
| RN-EAST-21764 | 2 | ap-south-5 | B3 |  |
| RN-EAST-21764 | 3 | ap-south-5 | B3 |  |
| RN-EAST-21764 | 4 | ap-south-5 | B3 |  |
| RN-EAST-21764 | 5 | ap-south-5 | B3 |  |
| RN-EAST-21794 | 1 | eu-central-2 | B3 |  |
| RN-EAST-21794 | 2 | eu-central-2 | B3 |  |
| RN-EAST-21794 | 3 | eu-central-2 | B3 |  |
| RN-EAST-21794 | 4 | eu-central-2 | B3 |  |
| RN-EAST-21794 | 5 | eu-central-2 | B3 |  |
| RN-EAST-21821 | 1 | ap-south-5 | B3 |  |
| RN-EAST-21821 | 2 | ap-south-5 | B3 |  |
| RN-EAST-21821 | 3 | ap-south-5 | B3 |  |
| RN-EAST-21821 | 4 | ap-south-5 | B3 |  |
| RN-EAST-21821 | 5 | ap-south-5 | B3 |  |
| RN-EAST-21847 | 1 | eu-central-2 | B3 |  |
| RN-EAST-21847 | 2 | eu-central-2 | B3 |  |
| RN-EAST-21847 | 3 | eu-central-2 | B3 |  |
| RN-EAST-21847 | 4 | eu-central-2 | B3 |  |
| RN-EAST-21847 | 5 | eu-central-2 | B3 |  |
| RN-EAST-21873 | 1 | ap-south-5 | B3 |  |
| RN-EAST-21873 | 2 | ap-south-5 | B3 |  |
| RN-EAST-21873 | 3 | ap-south-5 | B3 |  |
| RN-EAST-21873 | 4 | ap-south-5 | B3 |  |
| RN-EAST-21873 | 5 | ap-south-5 | B3 |  |
| RN-EAST-21900 | 1 | eu-central-2 | B3 |  |
| RN-EAST-21900 | 2 | eu-central-2 | B3 |  |
| RN-EAST-21900 | 3 | eu-central-2 | B3 |  |
| RN-EAST-21900 | 4 | eu-central-2 | B3 |  |
| RN-EAST-21900 | 5 | eu-central-2 | B3 |  |
| RN-EAST-21928 | 1 | ap-south-5 | B3 |  |
| RN-EAST-21928 | 2 | ap-south-5 | B3 |  |
| RN-EAST-21928 | 3 | ap-south-5 | B3 |  |
| RN-EAST-21928 | 4 | ap-south-5 | B3 |  |
| RN-EAST-21928 | 5 | ap-south-5 | B3 |  |
| RN-EAST-21958 | 1 | eu-central-2 | B3 |  |
| RN-EAST-21958 | 2 | eu-central-2 | B3 |  |
| RN-EAST-21958 | 3 | eu-central-2 | B3 |  |
| RN-EAST-21958 | 4 | eu-central-2 | B3 |  |
| RN-EAST-21958 | 5 | eu-central-2 | B3 |  |
| RN-EAST-21985 | 1 | ap-south-5 | B3 |  |
| RN-EAST-21985 | 2 | ap-south-5 | B3 |  |
| RN-EAST-21985 | 3 | ap-south-5 | B3 |  |
| RN-EAST-21985 | 4 | ap-south-5 | B3 |  |
| RN-EAST-21985 | 5 | ap-south-5 | B3 |  |
| RN-EAST-22018 | 1 | eu-central-2 | B3 |  |
| RN-EAST-22018 | 2 | eu-central-2 | B3 |  |
| RN-EAST-22018 | 3 | eu-central-2 | B3 |  |
| RN-EAST-22018 | 4 | eu-central-2 | B3 |  |
| RN-EAST-22018 | 5 | eu-central-2 | B3 |  |
| RN-EAST-22041 | 1 | ap-south-5 | B3 |  |
| RN-EAST-22041 | 2 | ap-south-5 | B3 |  |
| RN-EAST-22041 | 3 | ap-south-5 | B3 |  |
| RN-EAST-22041 | 4 | ap-south-5 | B3 |  |
| RN-EAST-22041 | 5 | ap-south-5 | B3 |  |
| RN-EAST-22073 | 1 | eu-central-2 | B3 |  |
| RN-EAST-22073 | 2 | eu-central-2 | B3 |  |
| RN-EAST-22073 | 3 | eu-central-2 | B3 |  |
| RN-EAST-22073 | 4 | eu-central-2 | B3 |  |
| RN-EAST-22073 | 5 | eu-central-2 | B3 |  |
| RN-EAST-22097 | 1 | ap-south-5 | B3 |  |
| RN-EAST-22097 | 2 | ap-south-5 | B3 |  |
| RN-EAST-22097 | 3 | ap-south-5 | B3 |  |
| RN-EAST-22097 | 4 | ap-south-5 | B3 |  |
| RN-EAST-22097 | 5 | ap-south-5 | B3 |  |
| RN-EAST-22126 | 1 | eu-central-2 | B3 |  |
| RN-EAST-22126 | 2 | eu-central-2 | B3 |  |
| RN-EAST-22126 | 3 | ap-south-5 | B3 |  |
| RN-EAST-22126 | 4 | eu-central-2 | B3 |  |
| RN-EAST-22126 | 5 | eu-central-2 | B3 |  |
| RN-EAST-22154 | 1 | ap-south-5 | B3 |  |
| RN-EAST-22154 | 2 | eu-central-2 | B3 |  |
| RN-EAST-22154 | 3 | ap-south-5 | B3 |  |
| RN-EAST-22154 | 4 | ap-south-5 | B3 |  |
| RN-EAST-22154 | 5 | ap-south-5 | B3 |  |
| RN-EAST-22184 | 1 | eu-central-2 | B3 |  |
| RN-EAST-22184 | 2 | eu-central-2 | B3 |  |
| RN-EAST-22184 | 3 | eu-central-2 | B3 |  |
| RN-EAST-22184 | 4 | eu-central-2 | B3 |  |
| RN-EAST-22184 | 5 | eu-central-2 | B3 |  |
| RN-EAST-22211 | 1 | ap-south-5 | B3 |  |
| RN-EAST-22211 | 2 | ap-south-5 | B3 |  |
| RN-EAST-22211 | 3 | ap-south-5 | B3 |  |
| RN-EAST-22211 | 4 | ap-south-5 | B3 |  |
| RN-EAST-22211 | 5 | ap-south-5 | B3 |  |
| RN-EAST-22236 | 1 | eu-central-2 | B3 |  |
| RN-EAST-22236 | 2 | eu-central-2 | B3 |  |
| RN-EAST-22236 | 3 | eu-central-2 | B3 |  |
| RN-EAST-22236 | 4 | eu-central-2 | B3 |  |
| RN-EAST-22236 | 5 | eu-central-2 | B3 |  |
| RN-EAST-22264 | 1 | ap-south-5 | B3 |  |
| RN-EAST-22264 | 2 | ap-south-5 | B3 |  |
| RN-EAST-22264 | 3 | ap-south-5 | B3 |  |
| RN-EAST-22264 | 4 | ap-south-5 | B3 |  |
| RN-EAST-22264 | 5 | ap-south-5 | B3 |  |
| RN-EAST-22297 | 1 | eu-central-2 | B3 |  |
| RN-EAST-22297 | 2 | eu-central-2 | B3 |  |
| RN-EAST-22297 | 3 | eu-central-2 | B3 |  |
| RN-EAST-22297 | 4 | eu-central-2 | B3 |  |
| RN-EAST-22297 | 5 | eu-central-2 | B3 |  |
| RN-EAST-22324 | 1 | ap-south-5 | B3 |  |
| RN-EAST-22324 | 2 | ap-south-5 | B3 |  |
| RN-EAST-22324 | 3 | ap-south-5 | B3 |  |
| RN-EAST-22324 | 4 | ap-south-5 | B3 |  |
| RN-EAST-22324 | 5 | ap-south-5 | B3 |  |
| RN-EAST-22350 | 1 | eu-central-2 | B3 |  |
| RN-EAST-22350 | 2 | eu-central-2 | B3 |  |
| RN-EAST-22350 | 3 | eu-central-2 | B3 |  |
| RN-EAST-22350 | 4 | eu-central-2 | B3 |  |
| RN-EAST-22350 | 5 | eu-central-2 | B3 |  |
| RN-EAST-22382 | 1 | ap-south-5 | B3 |  |
| RN-EAST-22382 | 2 | ap-south-5 | B3 |  |
| RN-EAST-22382 | 3 | ap-south-5 | B3 |  |
| RN-EAST-22382 | 4 | ap-south-5 | B3 |  |
| RN-EAST-22382 | 5 | eu-central-2 | B3 |  |
| RN-EAST-22409 | 1 | eu-central-2 | B3 |  |
| RN-EAST-22409 | 2 | eu-central-2 | B3 |  |
| RN-EAST-22409 | 3 | eu-central-2 | B3 |  |
| RN-EAST-22409 | 4 | eu-central-2 | B3 |  |
| RN-EAST-22409 | 5 | eu-central-2 | B3 |  |
| RN-EAST-22433 | 1 | ap-south-5 | B3 |  |
| RN-EAST-22433 | 2 | ap-south-5 | B3 |  |
| RN-EAST-22433 | 3 | ap-south-5 | B3 |  |
| RN-EAST-22433 | 4 | ap-south-5 | B3 |  |
| RN-EAST-22433 | 5 | ap-south-5 | B3 |  |
| RN-EAST-22462 | 1 | eu-central-2 | B3 |  |
| RN-EAST-22462 | 2 | eu-central-2 | B3 |  |
| RN-EAST-22462 | 3 | eu-central-2 | B3 |  |
| RN-EAST-22462 | 4 | eu-central-2 | B3 |  |
| RN-EAST-22462 | 5 | eu-central-2 | B3 |  |
| RN-EAST-22488 | 1 | ap-south-5 | B3 |  |
| RN-EAST-22488 | 2 | ap-south-5 | B3 |  |
| RN-EAST-22488 | 3 | ap-south-5 | B3 |  |
| RN-EAST-22488 | 4 | ap-south-5 | B3 |  |
| RN-EAST-22488 | 5 | ap-south-5 | B3 |  |
| RN-EAST-22518 | 1 | eu-central-2 | B3 |  |
| RN-EAST-22518 | 2 | eu-central-2 | B3 |  |
| RN-EAST-22518 | 3 | eu-central-2 | B3 |  |
| RN-EAST-22518 | 4 | eu-central-2 | B3 |  |
| RN-EAST-22518 | 5 | eu-central-2 | B3 |  |
| RN-EAST-22544 | 1 | ap-south-5 | B3 |  |
| RN-EAST-22544 | 2 | ap-south-5 | B3 |  |
| RN-EAST-22544 | 3 | eu-central-2 | B3 |  |
| RN-EAST-22544 | 4 | ap-south-5 | B3 |  |
| RN-EAST-22544 | 5 | ap-south-5 | B3 |  |
| RN-EAST-22574 | 1 | eu-central-2 | B3 |  |
| RN-EAST-22574 | 2 | eu-central-2 | B3 |  |
| RN-EAST-22574 | 3 | eu-central-2 | B3 |  |
| RN-EAST-22574 | 4 | eu-central-2 | B3 |  |
| RN-EAST-22574 | 5 | eu-central-2 | B3 |  |
| RN-EAST-22600 | 1 | ap-south-5 | B3 |  |
| RN-EAST-22600 | 2 | ap-south-5 | B3 |  |
| RN-EAST-22600 | 3 | ap-south-5 | B3 |  |
| RN-EAST-22600 | 4 | ap-south-5 | B3 |  |
| RN-EAST-22600 | 5 | ap-south-5 | B3 |  |
| RN-EAST-22629 | 1 | eu-central-2 | B3 |  |
| RN-EAST-22629 | 2 | eu-central-2 | B3 |  |
| RN-EAST-22629 | 3 | eu-central-2 | B3 |  |
| RN-EAST-22629 | 4 | eu-central-2 | B3 |  |
| RN-EAST-22629 | 5 | eu-central-2 | B3 |  |
| RN-EAST-22656 | 1 | ap-south-5 | B3 |  |
| RN-EAST-22656 | 2 | ap-south-5 | B3 |  |
| RN-EAST-22656 | 3 | eu-central-2 | B3 |  |
| RN-EAST-22656 | 4 | ap-south-5 | B3 |  |
| RN-EAST-22656 | 5 | ap-south-5 | B3 |  |
| RN-EAST-22686 | 1 | eu-central-2 | B3 |  |
| RN-EAST-22686 | 2 | eu-central-2 | B3 |  |
| RN-EAST-22686 | 3 | eu-central-2 | B3 |  |
| RN-EAST-22686 | 4 | eu-central-2 | B3 |  |
| RN-EAST-22686 | 5 | eu-central-2 | B3 |  |
| RN-EAST-22714 | 1 | ap-south-5 | B3 |  |
| RN-EAST-22714 | 2 | ap-south-5 | B3 |  |
| RN-EAST-22714 | 3 | ap-south-5 | B3 |  |
| RN-EAST-22714 | 4 | ap-south-5 | B3 |  |
| RN-EAST-22714 | 5 | ap-south-5 | B3 |  |
| RN-EAST-22746 | 1 | eu-central-2 | B3 |  |
| RN-EAST-22746 | 2 | eu-central-2 | B3 |  |
| RN-EAST-22746 | 3 | eu-central-2 | B3 |  |
| RN-EAST-22746 | 4 | eu-central-2 | B3 |  |
| RN-EAST-22746 | 5 | eu-central-2 | B3 |  |
| RN-EAST-22769 | 1 | ap-south-5 | B3 |  |
| RN-EAST-22769 | 2 | ap-south-5 | B3 |  |
| RN-EAST-22769 | 3 | ap-south-5 | B3 |  |
| RN-EAST-22769 | 4 | ap-south-5 | B3 |  |
| RN-EAST-22769 | 5 | ap-south-5 | B3 |  |
| RN-EAST-22802 | 1 | eu-central-2 | B3 |  |
| RN-EAST-22802 | 2 | eu-central-2 | B3 |  |
| RN-EAST-22802 | 3 | eu-central-2 | B3 |  |
| RN-EAST-22802 | 4 | eu-central-2 | B3 |  |
| RN-EAST-22802 | 5 | eu-central-2 | B3 |  |
| RN-EAST-22830 | 1 | ap-south-5 | B3 |  |
| RN-EAST-22830 | 2 | ap-south-5 | B3 |  |
| RN-EAST-22830 | 3 | ap-south-5 | B3 |  |
| RN-EAST-22830 | 4 | ap-south-5 | B3 |  |
| RN-EAST-22830 | 5 | ap-south-5 | B3 |  |
| RN-EAST-22854 | 1 | eu-central-2 | B3 |  |
| RN-EAST-22854 | 2 | eu-central-2 | B3 |  |
| RN-EAST-22854 | 3 | eu-central-2 | B3 |  |
| RN-EAST-22854 | 4 | eu-central-2 | B3 |  |
| RN-EAST-22854 | 5 | eu-central-2 | B3 |  |
| RN-EAST-22885 | 1 | ap-south-5 | B3 |  |
| RN-EAST-22885 | 2 | ap-south-5 | B3 |  |
| RN-EAST-22885 | 3 | ap-south-5 | B3 |  |
| RN-EAST-22885 | 4 | ap-south-5 | B3 |  |
| RN-EAST-22885 | 5 | ap-south-5 | B3 |  |
| RN-EAST-22910 | 1 | eu-central-2 | B3 |  |
| RN-EAST-22910 | 2 | eu-central-2 | B3 |  |
| RN-EAST-22910 | 3 | eu-central-2 | B3 |  |
| RN-EAST-22910 | 4 | eu-central-2 | B3 |  |
| RN-EAST-22910 | 5 | eu-central-2 | B3 |  |
| RN-EAST-22936 | 1 | ap-south-5 | B3 |  |
| RN-EAST-22936 | 2 | ap-south-5 | B3 |  |
| RN-EAST-22936 | 3 | ap-south-5 | B3 |  |
| RN-EAST-22936 | 4 | ap-south-5 | B3 |  |
| RN-EAST-22936 | 5 | ap-south-5 | B3 |  |
| RN-EAST-22964 | 1 | eu-central-2 | B3 |  |
| RN-EAST-22964 | 2 | eu-central-2 | B3 |  |
| RN-EAST-22964 | 3 | eu-central-2 | B3 |  |
| RN-EAST-22964 | 4 | eu-central-2 | B3 |  |
| RN-EAST-22964 | 5 | ap-south-5 | B3 |  |
| RN-EAST-22995 | 1 | ap-south-5 | B3 |  |
| RN-EAST-22995 | 2 | ap-south-5 | B3 |  |
| RN-EAST-22995 | 3 | ap-south-5 | B3 |  |
| RN-EAST-22995 | 4 | ap-south-5 | B3 |  |
| RN-EAST-22995 | 5 | ap-south-5 | B3 |  |
| RN-EAST-23023 | 1 | eu-central-2 | B3 |  |
| RN-EAST-23023 | 2 | eu-central-2 | B3 |  |
| RN-EAST-23023 | 3 | eu-central-2 | B3 |  |
| RN-EAST-23023 | 4 | eu-central-2 | B3 |  |
| RN-EAST-23023 | 5 | ap-south-5 | B3 |  |
| RN-EAST-23050 | 1 | ap-south-5 | B3 |  |
| RN-EAST-23050 | 2 | ap-south-5 | B3 |  |
| RN-EAST-23050 | 3 | ap-south-5 | B3 |  |
| RN-EAST-23050 | 4 | ap-south-5 | B3 |  |
| RN-EAST-23050 | 5 | ap-south-5 | B3 |  |
| RN-EAST-23076 | 1 | eu-central-2 | B3 |  |
| RN-EAST-23076 | 2 | eu-central-2 | B3 |  |
| RN-EAST-23076 | 3 | eu-central-2 | B3 |  |
| RN-EAST-23076 | 4 | eu-central-2 | B3 |  |
| RN-EAST-23076 | 5 | eu-central-2 | B3 |  |
| RN-EAST-23104 | 1 | ap-south-5 | B3 |  |
| RN-EAST-23104 | 2 | ap-south-5 | B3 |  |
| RN-EAST-23104 | 3 | eu-central-2 | B3 |  |
| RN-EAST-23104 | 4 | ap-south-5 | B3 |  |
| RN-EAST-23104 | 5 | ap-south-5 | B3 |  |
| RN-EAST-23136 | 1 | eu-central-2 | B3 |  |
| RN-EAST-23136 | 2 | eu-central-2 | B3 |  |
| RN-EAST-23136 | 3 | eu-central-2 | B3 |  |
| RN-EAST-23136 | 4 | eu-central-2 | B3 |  |
| RN-EAST-23136 | 5 | eu-central-2 | B3 |  |
| RN-EAST-23164 | 1 | ap-south-5 | B3 |  |
| RN-EAST-23164 | 2 | ap-south-5 | B3 |  |
| RN-EAST-23164 | 3 | ap-south-5 | B3 |  |
| RN-EAST-23164 | 4 | ap-south-5 | B3 |  |
| RN-EAST-23164 | 5 | ap-south-5 | B3 |  |
| RN-EAST-23191 | 1 | eu-central-2 | B3 |  |
| RN-EAST-23191 | 2 | eu-central-2 | B3 |  |
| RN-EAST-23191 | 3 | eu-central-2 | B3 |  |
| RN-EAST-23191 | 4 | eu-central-2 | B3 |  |
| RN-EAST-23191 | 5 | eu-central-2 | B3 |  |
| RN-EAST-23217 | 1 | ap-south-5 | B3 |  |
| RN-EAST-23217 | 2 | ap-south-5 | B3 |  |
| RN-EAST-23217 | 3 | ap-south-5 | B3 |  |
| RN-EAST-23217 | 4 | ap-south-5 | B3 |  |
| RN-EAST-23217 | 5 | ap-south-5 | B3 |  |
| RN-EAST-23247 | 1 | eu-central-2 | B3 |  |
| RN-EAST-23247 | 2 | eu-central-2 | B3 |  |
| RN-EAST-23247 | 3 | eu-central-2 | B3 |  |
| RN-EAST-23247 | 4 | eu-central-2 | B3 |  |
| RN-EAST-23247 | 5 | eu-central-2 | B3 |  |
| RN-EAST-23274 | 1 | ap-south-5 | B3 |  |
| RN-EAST-23274 | 2 | ap-south-5 | B3 |  |
| RN-EAST-23274 | 3 | ap-south-5 | B3 |  |
| RN-EAST-23274 | 4 | ap-south-5 | B3 |  |
| RN-EAST-23274 | 5 | ap-south-5 | B3 |  |
| RN-EAST-23305 | 1 | eu-central-2 | B3 |  |
| RN-EAST-23305 | 2 | eu-central-2 | B3 |  |
| RN-EAST-23305 | 3 | eu-central-2 | B3 |  |
| RN-EAST-23305 | 4 | eu-central-2 | B3 |  |
| RN-EAST-23305 | 5 | eu-central-2 | B3 |  |
| RN-EAST-23329 | 1 | ap-south-5 | B3 |  |
| RN-EAST-23329 | 2 | ap-south-5 | B3 |  |
| RN-EAST-23329 | 3 | ap-south-5 | B3 |  |
| RN-EAST-23329 | 4 | ap-south-5 | B3 |  |
| RN-EAST-23329 | 5 | ap-south-5 | B3 |  |
| RN-EAST-23359 | 1 | eu-central-2 | B3 |  |
| RN-EAST-23359 | 2 | eu-central-2 | B3 |  |
| RN-EAST-23359 | 3 | eu-central-2 | B3 |  |
| RN-EAST-23359 | 4 | eu-central-2 | B3 |  |
| RN-EAST-23359 | 5 | eu-central-2 | B3 |  |
| RN-EAST-23386 | 1 | ap-south-5 | B3 |  |
| RN-EAST-23386 | 2 | eu-central-2 | B3 |  |
| RN-EAST-23386 | 3 | ap-south-5 | B3 |  |
| RN-EAST-23386 | 4 | ap-south-5 | B3 |  |
| RN-EAST-23386 | 5 | ap-south-5 | B3 |  |
| RN-EAST-23415 | 1 | eu-central-2 | B3 |  |
| RN-EAST-23415 | 2 | eu-central-2 | B3 |  |
| RN-EAST-23415 | 3 | eu-central-2 | B3 |  |
| RN-EAST-23415 | 4 | eu-central-2 | B3 |  |
| RN-EAST-23415 | 5 | eu-central-2 | B3 |  |
| RN-EAST-23441 | 1 | ap-south-5 | B3 |  |
| RN-EAST-23441 | 2 | ap-south-5 | B3 |  |
| RN-EAST-23441 | 3 | ap-south-5 | B3 |  |
| RN-EAST-23441 | 4 | ap-south-5 | B3 |  |
| RN-EAST-23441 | 5 | ap-south-5 | B3 |  |
| RN-EAST-23472 | 1 | eu-central-2 | B3 |  |
| RN-EAST-23472 | 2 | eu-central-2 | B3 |  |
| RN-EAST-23472 | 3 | eu-central-2 | B3 |  |
| RN-EAST-23472 | 4 | eu-central-2 | B3 |  |
| RN-EAST-23472 | 5 | eu-central-2 | B3 |  |
| RN-EAST-23497 | 1 | ap-south-5 | B3 |  |
| RN-EAST-23497 | 2 | ap-south-5 | B3 |  |
| RN-EAST-23497 | 3 | ap-south-5 | B3 |  |
| RN-EAST-23497 | 4 | ap-south-5 | B3 |  |
| RN-EAST-23497 | 5 | ap-south-5 | B3 |  |
| RN-EAST-23524 | 1 | eu-central-2 | B3 |  |
| RN-EAST-23524 | 2 | eu-central-2 | B3 |  |
| RN-EAST-23524 | 3 | eu-central-2 | B3 |  |
| RN-EAST-23524 | 4 | eu-central-2 | B3 |  |
| RN-EAST-23524 | 5 | eu-central-2 | B3 |  |
| RN-EAST-23558 | 1 | ap-south-5 | B3 |  |
| RN-EAST-23558 | 2 | ap-south-5 | B3 |  |
| RN-EAST-23558 | 3 | ap-south-5 | B3 |  |
| RN-EAST-23558 | 4 | ap-south-5 | B3 |  |
| RN-EAST-23558 | 5 | ap-south-5 | B3 |  |
| RN-EAST-23585 | 1 | eu-central-2 | B3 |  |
| RN-EAST-23585 | 2 | eu-central-2 | B3 |  |
| RN-EAST-23585 | 3 | ap-south-5 | B3 |  |
| RN-EAST-23585 | 4 | eu-central-2 | B3 |  |
| RN-EAST-23585 | 5 | eu-central-2 | B3 |  |
| RN-EAST-23610 | 1 | ap-south-5 | B3 |  |
| RN-EAST-23610 | 2 | ap-south-5 | B3 |  |
| RN-EAST-23610 | 3 | ap-south-5 | B3 |  |
| RN-EAST-23610 | 4 | ap-south-5 | B3 |  |
| RN-EAST-23610 | 5 | ap-south-5 | B3 |  |
| RN-EAST-23640 | 1 | eu-central-2 | B3 |  |
| RN-EAST-23640 | 2 | eu-central-2 | B3 |  |
| RN-EAST-23640 | 3 | ap-south-5 | B3 |  |
| RN-EAST-23640 | 4 | eu-central-2 | B3 |  |
| RN-EAST-23640 | 5 | eu-central-2 | B3 |  |
| RN-EAST-23665 | 1 | ap-south-5 | B3 |  |
| RN-EAST-23665 | 2 | ap-south-5 | B3 |  |
| RN-EAST-23665 | 3 | ap-south-5 | B3 |  |
| RN-EAST-23665 | 4 | eu-central-2 | B3 |  |
| RN-EAST-23665 | 5 | ap-south-5 | B3 |  |
| RN-EAST-23696 | 1 | eu-central-2 | B3 |  |
| RN-EAST-23696 | 2 | eu-central-2 | B3 |  |
| RN-EAST-23696 | 3 | eu-central-2 | B3 |  |
| RN-EAST-23696 | 4 | eu-central-2 | B3 |  |
| RN-EAST-23696 | 5 | eu-central-2 | B3 |  |
| RN-EAST-23725 | 1 | ap-south-5 | B3 |  |
| RN-EAST-23725 | 2 | ap-south-5 | B3 |  |
| RN-EAST-23725 | 3 | ap-south-5 | B3 |  |
| RN-EAST-23725 | 4 | ap-south-5 | B3 |  |
| RN-EAST-23725 | 5 | ap-south-5 | B3 |  |
| RN-EAST-23751 | 1 | eu-central-2 | B3 |  |
| RN-EAST-23751 | 2 | eu-central-2 | B3 |  |
| RN-EAST-23751 | 3 | eu-central-2 | B3 |  |
| RN-EAST-23751 | 4 | eu-central-2 | B3 |  |
| RN-EAST-23751 | 5 | ap-south-5 | B3 |  |
| RN-EAST-23777 | 1 | ap-south-5 | B3 |  |
| RN-EAST-23777 | 2 | ap-south-5 | B3 |  |
| RN-EAST-23777 | 3 | ap-south-5 | B3 |  |
| RN-EAST-23777 | 4 | ap-south-5 | B3 |  |
| RN-EAST-23777 | 5 | ap-south-5 | B3 |  |
| RN-EAST-23810 | 1 | eu-central-2 | B3 |  |
| RN-EAST-23810 | 2 | eu-central-2 | B3 |  |
| RN-EAST-23810 | 3 | eu-central-2 | B3 |  |
| RN-EAST-23810 | 4 | eu-central-2 | B3 |  |
| RN-EAST-23810 | 5 | eu-central-2 | B3 |  |
| RN-EAST-23833 | 1 | ap-south-5 | B3 |  |
| RN-EAST-23833 | 2 | ap-south-5 | B3 |  |
| RN-EAST-23833 | 3 | ap-south-5 | B3 |  |
| RN-EAST-23833 | 4 | ap-south-5 | B3 |  |
| RN-EAST-23833 | 5 | ap-south-5 | B3 |  |
| RN-EAST-23864 | 1 | eu-central-2 | B3 |  |
| RN-EAST-23864 | 2 | eu-central-2 | B3 |  |
| RN-EAST-23864 | 3 | eu-central-2 | B3 |  |
| RN-EAST-23864 | 4 | eu-central-2 | B3 |  |
| RN-EAST-23864 | 5 | eu-central-2 | B3 |  |
| RN-EAST-23893 | 1 | ap-south-5 | B3 |  |
| RN-EAST-23893 | 2 | ap-south-5 | B3 |  |
| RN-EAST-23893 | 3 | ap-south-5 | B3 |  |
| RN-EAST-23893 | 4 | ap-south-5 | B3 |  |
| RN-EAST-23893 | 5 | eu-central-2 | B3 |  |
| RN-EAST-23917 | 1 | eu-central-2 | B3 |  |
| RN-EAST-23917 | 2 | ap-south-5 | B3 |  |
| RN-EAST-23917 | 3 | eu-central-2 | B3 |  |
| RN-EAST-23917 | 4 | eu-central-2 | B3 |  |
| RN-EAST-23917 | 5 | eu-central-2 | B3 |  |
| RN-EAST-23946 | 1 | ap-south-5 | B3 |  |
| RN-EAST-23946 | 2 | ap-south-5 | B3 |  |
| RN-EAST-23946 | 3 | ap-south-5 | B3 |  |
| RN-EAST-23946 | 4 | ap-south-5 | B3 |  |
| RN-EAST-23946 | 5 | ap-south-5 | B3 |  |
| RN-EAST-23976 | 1 | eu-central-2 | B3 |  |
| RN-EAST-23976 | 2 | eu-central-2 | B3 |  |
| RN-EAST-23976 | 3 | eu-central-2 | B3 |  |
| RN-EAST-23976 | 4 | eu-central-2 | B3 |  |
| RN-EAST-23976 | 5 | eu-central-2 | B3 |  |
| RN-EAST-24002 | 1 | ap-south-5 | B3 |  |
| RN-EAST-24002 | 2 | ap-south-5 | B3 |  |
| RN-EAST-24002 | 3 | ap-south-5 | B3 |  |
| RN-EAST-24002 | 4 | ap-south-5 | B3 |  |
| RN-EAST-24002 | 5 | ap-south-5 | B3 |  |
| RN-EAST-24030 | 1 | eu-central-2 | B3 |  |
| RN-EAST-24030 | 2 | eu-central-2 | B3 |  |
| RN-EAST-24030 | 3 | eu-central-2 | B3 |  |
| RN-EAST-24030 | 4 | eu-central-2 | B3 |  |
| RN-EAST-24030 | 5 | ap-south-5 | B3 |  |
| RN-EAST-24057 | 1 | ap-south-5 | B3 |  |
| RN-EAST-24057 | 2 | eu-central-2 | B3 |  |
| RN-EAST-24057 | 3 | ap-south-5 | B3 |  |
| RN-EAST-24057 | 4 | ap-south-5 | B3 |  |
| RN-EAST-24057 | 5 | ap-south-5 | B3 |  |
| RN-EAST-24089 | 1 | eu-central-2 | B3 |  |
| RN-EAST-24089 | 2 | eu-central-2 | B3 |  |
| RN-EAST-24089 | 3 | eu-central-2 | B3 |  |
| RN-EAST-24089 | 4 | eu-central-2 | B3 |  |
| RN-EAST-24089 | 5 | eu-central-2 | B3 |  |
| RN-EAST-24112 | 1 | ap-south-5 | B3 |  |
| RN-EAST-24112 | 2 | eu-central-2 | B3 |  |
| RN-EAST-24112 | 3 | ap-south-5 | B3 |  |
| RN-EAST-24112 | 4 | ap-south-5 | B3 |  |
| RN-EAST-24112 | 5 | ap-south-5 | B3 |  |
| RN-EAST-24143 | 1 | eu-central-2 | B3 |  |
| RN-EAST-24143 | 2 | eu-central-2 | B3 |  |
| RN-EAST-24143 | 3 | eu-central-2 | B3 |  |
| RN-EAST-24143 | 4 | eu-central-2 | B3 |  |
| RN-EAST-24143 | 5 | eu-central-2 | B3 |  |
| RN-EAST-24169 | 1 | ap-south-5 | B3 |  |
| RN-EAST-24169 | 2 | ap-south-5 | B3 |  |
| RN-EAST-24169 | 3 | ap-south-5 | B3 |  |
| RN-EAST-24169 | 4 | ap-south-5 | B3 |  |
| RN-EAST-24169 | 5 | ap-south-5 | B3 |  |
| RN-EAST-24202 | 1 | eu-central-2 | B3 |  |
| RN-EAST-24202 | 2 | eu-central-2 | B3 |  |
| RN-EAST-24202 | 3 | eu-central-2 | B3 |  |
| RN-EAST-24202 | 4 | eu-central-2 | B3 |  |
| RN-EAST-24202 | 5 | eu-central-2 | B3 |  |
| RN-EAST-24226 | 1 | ap-south-5 | B3 |  |
| RN-EAST-24226 | 2 | ap-south-5 | B3 |  |
| RN-EAST-24226 | 3 | ap-south-5 | B3 |  |
| RN-EAST-24226 | 4 | ap-south-5 | B3 |  |
| RN-EAST-24226 | 5 | ap-south-5 | B3 |  |
| RN-EAST-24252 | 1 | eu-central-2 | B3 |  |
| RN-EAST-24252 | 2 | eu-central-2 | B3 |  |
| RN-EAST-24252 | 3 | eu-central-2 | B3 |  |
| RN-EAST-24252 | 4 | eu-central-2 | B3 |  |
| RN-EAST-24252 | 5 | eu-central-2 | B3 |  |
|   rn-north-10009  | 1 | eu-west-1 | B4 |  |
|   rn-north-10009  | 2 | eu-west-1 | B4 |  |
|   rn-north-10009  | 3 | ca-north-8 | B4 |  |
|   rn-north-10009  | 4 | eu-west-1 | B4 |  |
|   rn-north-10009  | 5 | eu-west-1 | B4 |  |
|   rn-north-10040  | 1 | ca-north-8 | B4 |  |
|   rn-north-10040  | 2 | ca-north-8 | B4 |  |
|   rn-north-10040  | 3 | ca-north-8 | B4 |  |
|   rn-north-10040  | 4 | ca-north-8 | B4 |  |
|   rn-north-10040  | 5 | ca-north-8 | B4 |  |
|   rn-north-10067  | 1 | eu-west-1 | B4 |  |
|   rn-north-10067  | 2 | eu-west-1 | B4 |  |
|   rn-north-10067  | 3 | eu-west-1 | B4 |  |
|   rn-north-10067  | 4 | eu-west-1 | B4 |  |
|   rn-north-10067  | 5 | eu-west-1 | B4 |  |
|   rn-north-10091  | 1 | ca-north-8 | B4 |  |
|   rn-north-10091  | 2 | ca-north-8 | B4 |  |
|   rn-north-10091  | 3 | ca-north-8 | B4 |  |
|   rn-north-10091  | 4 | ca-north-8 | B4 |  |
|   rn-north-10091  | 5 | ca-north-8 | B4 |  |
|   rn-north-10122  | 1 | eu-west-1 | B4 |  |
|   rn-north-10122  | 2 | eu-west-1 | B4 |  |
|   rn-north-10122  | 3 | eu-west-1 | B4 |  |
|   rn-north-10122  | 4 | eu-west-1 | B4 |  |
|   rn-north-10122  | 5 | eu-west-1 | B4 |  |
|   rn-north-10148  | 1 | ca-north-8 | B4 |  |
|   rn-north-10148  | 2 | ca-north-8 | B4 |  |
|   rn-north-10148  | 3 | ca-north-8 | B4 |  |
|   rn-north-10148  | 4 | ca-north-8 | B4 |  |
|   rn-north-10148  | 5 | ca-north-8 | B4 |  |
|   rn-north-10175  | 1 | eu-west-1 | B4 |  |
|   rn-north-10175  | 2 | eu-west-1 | B4 |  |
|   rn-north-10175  | 3 | eu-west-1 | B4 |  |
|   rn-north-10175  | 4 | ca-north-8 | B4 |  |
|   rn-north-10175  | 5 | eu-west-1 | B4 |  |
|   rn-north-10209  | 1 | ca-north-8 | B4 |  |
|   rn-north-10209  | 2 | eu-west-1 | B4 |  |
|   rn-north-10209  | 3 | ca-north-8 | B4 |  |
|   rn-north-10209  | 4 | ca-north-8 | B4 |  |
|   rn-north-10209  | 5 | ca-north-8 | B4 |  |
|   rn-north-10236  | 1 | eu-west-1 | B4 |  |
|   rn-north-10236  | 2 | eu-west-1 | B4 |  |
|   rn-north-10236  | 3 | eu-west-1 | B4 |  |
|   rn-north-10236  | 4 | eu-west-1 | B4 |  |
|   rn-north-10236  | 5 | eu-west-1 | B4 |  |
|   rn-north-10259  | 1 | ca-north-8 | B4 |  |
|   rn-north-10259  | 2 | ca-north-8 | B4 |  |
|   rn-north-10259  | 3 | ca-north-8 | B4 |  |
|   rn-north-10259  | 4 | ca-north-8 | B4 |  |
|   rn-north-10259  | 5 | ca-north-8 | B4 |  |
|   rn-north-10290  | 1 | eu-west-1 | B4 |  |
|   rn-north-10290  | 2 | eu-west-1 | B4 |  |
|   rn-north-10290  | 3 | eu-west-1 | B4 |  |
|   rn-north-10290  | 4 | eu-west-1 | B4 |  |
|   rn-north-10290  | 5 | eu-west-1 | B4 |  |
|   rn-north-10317  | 1 | ca-north-8 | B4 |  |
|   rn-north-10317  | 2 | eu-west-1 | B4 |  |
|   rn-north-10317  | 3 | ca-north-8 | B4 |  |
|   rn-north-10317  | 4 | ca-north-8 | B4 |  |
|   rn-north-10317  | 5 | ca-north-8 | B4 |  |
|   rn-north-10344  | 1 | eu-west-1 | B4 |  |
|   rn-north-10344  | 2 | eu-west-1 | B4 |  |
|   rn-north-10344  | 3 | eu-west-1 | B4 |  |
|   rn-north-10344  | 4 | eu-west-1 | B4 |  |
|   rn-north-10344  | 5 | eu-west-1 | B4 |  |
|   rn-north-10372  | 1 | ca-north-8 | B4 |  |
|   rn-north-10372  | 2 | ca-north-8 | B4 |  |
|   rn-north-10372  | 3 | ca-north-8 | B4 |  |
|   rn-north-10372  | 4 | ca-north-8 | B4 |  |
|   rn-north-10372  | 5 | ca-north-8 | B4 |  |
|   rn-north-10403  | 1 | eu-west-1 | B4 |  |
|   rn-north-10403  | 2 | eu-west-1 | B4 |  |
|   rn-north-10403  | 3 | eu-west-1 | B4 |  |
|   rn-north-10403  | 4 | eu-west-1 | B4 |  |
|   rn-north-10403  | 5 | eu-west-1 | B4 |  |
|   rn-north-10428  | 1 | ca-north-8 | B4 |  |
|   rn-north-10428  | 2 | eu-west-1 | B4 |  |
|   rn-north-10428  | 3 | ca-north-8 | B4 |  |
|   rn-north-10428  | 4 | ca-north-8 | B4 |  |
|   rn-north-10428  | 5 | ca-north-8 | B4 |  |
|   rn-north-10455  | 1 | eu-west-1 | B4 |  |
|   rn-north-10455  | 2 | eu-west-1 | B4 |  |
|   rn-north-10455  | 3 | eu-west-1 | B4 |  |
|   rn-north-10455  | 4 | eu-west-1 | B4 |  |
|   rn-north-10455  | 5 | eu-west-1 | B4 |  |
|   rn-north-10488  | 1 | ca-north-8 | B4 |  |
|   rn-north-10488  | 2 | ca-north-8 | B4 |  |
|   rn-north-10488  | 3 | ca-north-8 | B4 |  |
|   rn-north-10488  | 4 | eu-west-1 | B4 |  |
|   rn-north-10488  | 5 | eu-west-1 | B4 |  |
|   rn-north-10517  | 1 | eu-west-1 | B4 |  |
|   rn-north-10517  | 2 | eu-west-1 | B4 |  |
|   rn-north-10517  | 3 | eu-west-1 | B4 |  |
|   rn-north-10517  | 4 | eu-west-1 | B4 |  |
|   rn-north-10517  | 5 | eu-west-1 | B4 |  |
|   rn-north-10542  | 1 | ca-north-8 | B4 |  |
|   rn-north-10542  | 2 | ca-north-8 | B4 |  |
|   rn-north-10542  | 3 | ca-north-8 | B4 |  |
|   rn-north-10542  | 4 | ca-north-8 | B4 |  |
|   rn-north-10542  | 5 | ca-north-8 | B4 |  |
|   rn-north-10569  | 1 | eu-west-1 | B4 |  |
|   rn-north-10569  | 2 | eu-west-1 | B4 |  |
|   rn-north-10569  | 3 | eu-west-1 | B4 |  |
|   rn-north-10569  | 4 | eu-west-1 | B4 |  |
|   rn-north-10569  | 5 | eu-west-1 | B4 |  |
|   rn-north-10595  | 1 | ca-north-8 | B4 |  |
|   rn-north-10595  | 2 | ca-north-8 | B4 |  |
|   rn-north-10595  | 3 | ca-north-8 | B4 |  |
|   rn-north-10595  | 4 | ca-north-8 | B4 |  |
|   rn-north-10595  | 5 | ca-north-8 | B4 |  |
|   rn-north-10627  | 1 | eu-west-1 | B4 |  |
|   rn-north-10627  | 2 | eu-west-1 | B4 |  |
|   rn-north-10627  | 3 | eu-west-1 | B4 |  |
|   rn-north-10627  | 4 | eu-west-1 | B4 |  |
|   rn-north-10627  | 5 | eu-west-1 | B4 |  |
|   rn-north-10651  | 1 | ca-north-8 | B4 |  |
|   rn-north-10651  | 2 | ca-north-8 | B4 |  |
|   rn-north-10651  | 3 | ca-north-8 | B4 |  |
|   rn-north-10651  | 4 | ca-north-8 | B4 |  |
|   rn-north-10651  | 5 | ca-north-8 | B4 |  |
|   rn-north-10683  | 1 | eu-west-1 | B4 |  |
|   rn-north-10683  | 2 | eu-west-1 | B4 |  |
|   rn-north-10683  | 3 | eu-west-1 | B4 |  |
|   rn-north-10683  | 4 | eu-west-1 | B4 |  |
|   rn-north-10683  | 5 | eu-west-1 | B4 |  |
|   rn-north-10709  | 1 | ca-north-8 | B4 |  |
|   rn-north-10709  | 2 | ca-north-8 | B4 |  |
|   rn-north-10709  | 3 | ca-north-8 | B4 |  |
|   rn-north-10709  | 4 | ca-north-8 | B4 |  |
|   rn-north-10709  | 5 | ca-north-8 | B4 |  |
|   rn-north-10739  | 1 | eu-west-1 | B4 |  |
|   rn-north-10739  | 2 | eu-west-1 | B4 |  |
|   rn-north-10739  | 3 | eu-west-1 | B4 |  |
|   rn-north-10739  | 4 | eu-west-1 | B4 |  |
|   rn-north-10739  | 5 | eu-west-1 | B4 |  |
|   rn-north-10767  | 1 | ca-north-8 | B4 |  |
|   rn-north-10767  | 2 | ca-north-8 | B4 |  |
|   rn-north-10767  | 3 | ca-north-8 | B4 |  |
|   rn-north-10767  | 4 | ca-north-8 | B4 |  |
|   rn-north-10767  | 5 | ca-north-8 | B4 |  |
|   rn-north-10793  | 1 | eu-west-1 | B4 |  |
|   rn-north-10793  | 2 | eu-west-1 | B4 |  |
|   rn-north-10793  | 3 | eu-west-1 | B4 |  |
|   rn-north-10793  | 4 | eu-west-1 | B4 |  |
|   rn-north-10793  | 5 | eu-west-1 | B4 |  |
|   rn-north-10825  | 1 | ca-north-8 | B4 |  |
|   rn-north-10825  | 2 | ca-north-8 | B4 |  |
|   rn-north-10825  | 3 | ca-north-8 | B4 |  |
|   rn-north-10825  | 4 | ca-north-8 | B4 |  |
|   rn-north-10825  | 5 | ca-north-8 | B4 |  |
|   rn-north-10850  | 1 | eu-west-1 | B4 |  |
|   rn-north-10850  | 2 | eu-west-1 | B4 |  |
|   rn-north-10850  | 3 | ca-north-8 | B4 |  |
|   rn-north-10850  | 4 | eu-west-1 | B4 |  |
|   rn-north-10850  | 5 | eu-west-1 | B4 |  |
|   rn-north-10879  | 1 | ca-north-8 | B4 |  |
|   rn-north-10879  | 2 | ca-north-8 | B4 |  |
|   rn-north-10879  | 3 | ca-north-8 | B4 |  |
|   rn-north-10879  | 4 | ca-north-8 | B4 |  |
|   rn-north-10879  | 5 | ca-north-8 | B4 |  |
|   rn-north-10908  | 1 | eu-west-1 | B4 |  |
|   rn-north-10908  | 2 | eu-west-1 | B4 |  |
|   rn-north-10908  | 3 | eu-west-1 | B4 |  |
|   rn-north-10908  | 4 | eu-west-1 | B4 |  |
|   rn-north-10908  | 5 | eu-west-1 | B4 |  |
|   rn-north-10934  | 1 | ca-north-8 | B4 |  |
|   rn-north-10934  | 2 | ca-north-8 | B4 |  |
|   rn-north-10934  | 3 | ca-north-8 | B4 |  |
|   rn-north-10934  | 4 | eu-west-1 | B4 |  |
|   rn-north-10934  | 5 | ca-north-8 | B4 |  |
|   rn-north-10963  | 1 | eu-west-1 | B4 |  |
|   rn-north-10963  | 2 | eu-west-1 | B4 |  |
|   rn-north-10963  | 3 | eu-west-1 | B4 |  |
|   rn-north-10963  | 4 | eu-west-1 | B4 |  |
|   rn-north-10963  | 5 | eu-west-1 | B4 |  |
|   rn-north-10988  | 1 | ca-north-8 | B4 |  |
|   rn-north-10988  | 2 | ca-north-8 | B4 |  |
|   rn-north-10988  | 3 | ca-north-8 | B4 |  |
|   rn-north-10988  | 4 | ca-north-8 | B4 |  |
|   rn-north-10988  | 5 | ca-north-8 | B4 |  |
|   rn-north-11021  | 1 | eu-west-1 | B4 |  |
|   rn-north-11021  | 2 | eu-west-1 | B4 |  |
|   rn-north-11021  | 3 | eu-west-1 | B4 |  |
|   rn-north-11021  | 4 | eu-west-1 | B4 |  |
|   rn-north-11021  | 5 | eu-west-1 | B4 |  |
|   rn-north-11047  | 1 | ca-north-8 | B4 |  |
|   rn-north-11047  | 2 | ca-north-8 | B4 |  |
|   rn-north-11047  | 3 | ca-north-8 | B4 |  |
|   rn-north-11047  | 4 | ca-north-8 | B4 |  |
|   rn-north-11047  | 5 | ca-north-8 | B4 |  |
|   rn-north-11075  | 1 | eu-west-1 | B4 |  |
|   rn-north-11075  | 2 | eu-west-1 | B4 |  |
|   rn-north-11075  | 3 | eu-west-1 | B4 |  |
|   rn-north-11075  | 4 | eu-west-1 | B4 |  |
|   rn-north-11075  | 5 | eu-west-1 | B4 |  |
|   rn-north-11103  | 1 | ca-north-8 | B4 |  |
|   rn-north-11103  | 2 | ca-north-8 | B4 |  |
|   rn-north-11103  | 3 | ca-north-8 | B4 |  |
|   rn-north-11103  | 4 | ca-north-8 | B4 |  |
|   rn-north-11103  | 5 | ca-north-8 | B4 |  |
|   rn-north-11130  | 1 | eu-west-1 | B4 |  |
|   rn-north-11130  | 2 | eu-west-1 | B4 |  |
|   rn-north-11130  | 3 | eu-west-1 | B4 |  |
|   rn-north-11130  | 4 | eu-west-1 | B4 |  |
|   rn-north-11130  | 5 | eu-west-1 | B4 |  |
|   rn-north-11158  | 1 | ca-north-8 | B4 |  |
|   rn-north-11158  | 2 | ca-north-8 | B4 |  |
|   rn-north-11158  | 3 | ca-north-8 | B4 |  |
|   rn-north-11158  | 4 | ca-north-8 | B4 |  |
|   rn-north-11158  | 5 | ca-north-8 | B4 |  |
|   rn-north-11187  | 1 | eu-west-1 | B4 |  |
|   rn-north-11187  | 2 | eu-west-1 | B4 |  |
|   rn-north-11187  | 3 | eu-west-1 | B4 |  |
|   rn-north-11187  | 4 | eu-west-1 | B4 |  |
|   rn-north-11187  | 5 | eu-west-1 | B4 |  |
|   rn-north-11215  | 1 | ca-north-8 | B4 |  |
|   rn-north-11215  | 2 | ca-north-8 | B4 |  |
|   rn-north-11215  | 3 | ca-north-8 | B4 |  |
|   rn-north-11215  | 4 | eu-west-1 | B4 |  |
|   rn-north-11215  | 5 | ca-north-8 | B4 |  |
|   rn-north-11244  | 1 | eu-west-1 | B4 |  |
|   rn-north-11244  | 2 | eu-west-1 | B4 |  |
|   rn-north-11244  | 3 | eu-west-1 | B4 |  |
|   rn-north-11244  | 4 | eu-west-1 | B4 |  |
|   rn-north-11244  | 5 | ca-north-8 | B4 |  |
|   rn-north-11268  | 1 | ca-north-8 | B4 |  |
|   rn-north-11268  | 2 | ca-north-8 | B4 |  |
|   rn-north-11268  | 3 | ca-north-8 | B4 |  |
|   rn-north-11268  | 4 | ca-north-8 | B4 |  |
|   rn-north-11268  | 5 | ca-north-8 | B4 |  |
|   rn-north-11298  | 1 | eu-west-1 | B4 |  |
|   rn-north-11298  | 2 | eu-west-1 | B4 |  |
|   rn-north-11298  | 3 | eu-west-1 | B4 |  |
|   rn-north-11298  | 4 | eu-west-1 | B4 |  |
|   rn-north-11298  | 5 | eu-west-1 | B4 |  |
|   rn-north-11323  | 1 | ca-north-8 | B4 |  |
|   rn-north-11323  | 2 | ca-north-8 | B4 |  |
|   rn-north-11323  | 3 | ca-north-8 | B4 |  |
|   rn-north-11323  | 4 | ca-north-8 | B4 |  |
|   rn-north-11323  | 5 | ca-north-8 | B4 |  |
|   rn-north-11357  | 1 | eu-west-1 | B4 |  |
|   rn-north-11357  | 2 | eu-west-1 | B4 |  |
|   rn-north-11357  | 3 | eu-west-1 | B4 |  |
|   rn-north-11357  | 4 | eu-west-1 | B4 |  |
|   rn-north-11357  | 5 | eu-west-1 | B4 |  |
|   rn-north-11379  | 1 | ca-north-8 | B4 |  |
|   rn-north-11379  | 2 | ca-north-8 | B4 |  |
|   rn-north-11379  | 3 | ca-north-8 | B4 |  |
|   rn-north-11379  | 4 | ca-north-8 | B4 |  |
|   rn-north-11379  | 5 | ca-north-8 | B4 |  |
|   rn-north-11411  | 1 | eu-west-1 | B4 |  |
|   rn-north-11411  | 2 | eu-west-1 | B4 |  |
|   rn-north-11411  | 3 | eu-west-1 | B4 |  |
|   rn-north-11411  | 4 | eu-west-1 | B4 |  |
|   rn-north-11411  | 5 | eu-west-1 | B4 |  |
|   rn-north-11440  | 1 | ca-north-8 | B4 |  |
|   rn-north-11440  | 2 | ca-north-8 | B4 |  |
|   rn-north-11440  | 3 | ca-north-8 | B4 |  |
|   rn-north-11440  | 4 | ca-north-8 | B4 |  |
|   rn-north-11440  | 5 | ca-north-8 | B4 |  |
|   rn-north-11468  | 1 | eu-west-1 | B4 |  |
|   rn-north-11468  | 2 | eu-west-1 | B4 |  |
|   rn-north-11468  | 3 | eu-west-1 | B4 |  |
|   rn-north-11468  | 4 | eu-west-1 | B4 |  |
|   rn-north-11468  | 5 | eu-west-1 | B4 |  |
|   rn-north-11494  | 1 | ca-north-8 | B4 |  |
|   rn-north-11494  | 2 | eu-west-1 | B4 |  |
|   rn-north-11494  | 3 | ca-north-8 | B4 |  |
|   rn-north-11494  | 4 | ca-north-8 | B4 |  |
|   rn-north-11494  | 5 | ca-north-8 | B4 |  |
|   rn-north-11521  | 1 | eu-west-1 | B4 |  |
|   rn-north-11521  | 2 | eu-west-1 | B4 |  |
|   rn-north-11521  | 3 | eu-west-1 | B4 |  |
|   rn-north-11521  | 4 | eu-west-1 | B4 |  |
|   rn-north-11521  | 5 | eu-west-1 | B4 |  |
|   rn-north-11550  | 1 | ca-north-8 | B4 |  |
|   rn-north-11550  | 2 | ca-north-8 | B4 |  |
|   rn-north-11550  | 3 | ca-north-8 | B4 |  |
|   rn-north-11550  | 4 | ca-north-8 | B4 |  |
|   rn-north-11550  | 5 | ca-north-8 | B4 |  |
|   rn-north-11580  | 1 | eu-west-1 | B4 |  |
|   rn-north-11580  | 2 | eu-west-1 | B4 |  |
|   rn-north-11580  | 3 | eu-west-1 | B4 |  |
|   rn-north-11580  | 4 | eu-west-1 | B4 |  |
|   rn-north-11580  | 5 | eu-west-1 | B4 |  |
|   rn-north-11608  | 1 | ca-north-8 | B4 |  |
|   rn-north-11608  | 2 | ca-north-8 | B4 |  |
|   rn-north-11608  | 3 | ca-north-8 | B4 |  |
|   rn-north-11608  | 4 | ca-north-8 | B4 |  |
|   rn-north-11608  | 5 | ca-north-8 | B4 |  |
|   rn-north-11636  | 1 | eu-west-1 | B4 |  |
|   rn-north-11636  | 2 | eu-west-1 | B4 |  |
|   rn-north-11636  | 3 | eu-west-1 | B4 |  |
|   rn-north-11636  | 4 | eu-west-1 | B4 |  |
|   rn-north-11636  | 5 | eu-west-1 | B4 |  |
|   rn-north-11663  | 1 | ca-north-8 | B4 |  |
|   rn-north-11663  | 2 | ca-north-8 | B4 |  |
|   rn-north-11663  | 3 | ca-north-8 | B4 |  |
|   rn-north-11663  | 4 | ca-north-8 | B4 |  |
|   rn-north-11663  | 5 | ca-north-8 | B4 |  |
|   rn-north-11692  | 1 | eu-west-1 | B4 |  |
|   rn-north-11692  | 2 | eu-west-1 | B4 |  |
|   rn-north-11692  | 3 | eu-west-1 | B4 |  |
|   rn-north-11692  | 4 | eu-west-1 | B4 |  |
|   rn-north-11692  | 5 | eu-west-1 | B4 |  |
|   rn-north-11721  | 1 | ca-north-8 | B4 |  |
|   rn-north-11721  | 2 | ca-north-8 | B4 |  |
|   rn-north-11721  | 3 | ca-north-8 | B4 |  |
|   rn-north-11721  | 4 | ca-north-8 | B4 |  |
|   rn-north-11721  | 5 | ca-north-8 | B4 |  |
|   rn-north-11744  | 1 | eu-west-1 | B4 |  |
|   rn-north-11744  | 2 | eu-west-1 | B4 |  |
|   rn-north-11744  | 3 | eu-west-1 | B4 |  |
|   rn-north-11744  | 4 | eu-west-1 | B4 |  |
|   rn-north-11744  | 5 | eu-west-1 | B4 |  |
|   rn-north-11775  | 1 | ca-north-8 | B4 |  |
|   rn-north-11775  | 2 | ca-north-8 | B4 |  |
|   rn-north-11775  | 3 | ca-north-8 | B4 |  |
|   rn-north-11775  | 4 | ca-north-8 | B4 |  |
|   rn-north-11775  | 5 | ca-north-8 | B4 |  |
|   rn-north-11804  | 1 | eu-west-1 | B4 |  |
|   rn-north-11804  | 2 | ca-north-8 | B4 |  |
|   rn-north-11804  | 3 | eu-west-1 | B4 |  |
|   rn-north-11804  | 4 | eu-west-1 | B4 |  |
|   rn-north-11804  | 5 | eu-west-1 | B4 |  |
|   rn-north-11833  | 1 | ca-north-8 | B4 |  |
|   rn-north-11833  | 2 | ca-north-8 | B4 |  |
|   rn-north-11833  | 3 | ca-north-8 | B4 |  |
|   rn-north-11833  | 4 | ca-north-8 | B4 |  |
|   rn-north-11833  | 5 | ca-north-8 | B4 |  |
|   rn-north-11858  | 1 | eu-west-1 | B4 |  |
|   rn-north-11858  | 2 | eu-west-1 | B4 |  |
|   rn-north-11858  | 3 | eu-west-1 | B4 |  |
|   rn-north-11858  | 4 | eu-west-1 | B4 |  |
|   rn-north-11858  | 5 | eu-west-1 | B4 |  |
|   rn-north-11889  | 1 | ca-north-8 | B4 |  |
|   rn-north-11889  | 2 | ca-north-8 | B4 |  |
|   rn-north-11889  | 3 | ca-north-8 | B4 |  |
|   rn-north-11889  | 4 | ca-north-8 | B4 |  |
|   rn-north-11889  | 5 | ca-north-8 | B4 |  |
|   rn-north-11913  | 1 | eu-west-1 | B4 |  |
|   rn-north-11913  | 2 | eu-west-1 | B4 |  |
|   rn-north-11913  | 3 | eu-west-1 | B4 |  |
|   rn-north-11913  | 4 | eu-west-1 | B4 |  |
|   rn-north-11913  | 5 | eu-west-1 | B4 |  |
|   rn-north-11942  | 1 | ca-north-8 | B4 |  |
|   rn-north-11942  | 2 | eu-west-1 | B4 |  |
|   rn-north-11942  | 3 | eu-west-1 | B4 |  |
|   rn-north-11942  | 4 | ca-north-8 | B4 |  |
|   rn-north-11942  | 5 | ca-north-8 | B4 |  |
|   rn-north-11973  | 1 | eu-west-1 | B4 |  |
|   rn-north-11973  | 2 | eu-west-1 | B4 |  |
|   rn-north-11973  | 3 | eu-west-1 | B4 |  |
|   rn-north-11973  | 4 | eu-west-1 | B4 |  |
|   rn-north-11973  | 5 | eu-west-1 | B4 |  |
|   rn-north-11998  | 1 | ca-north-8 | B4 |  |
|   rn-north-11998  | 2 | ca-north-8 | B4 |  |
|   rn-north-11998  | 3 | ca-north-8 | B4 |  |
|   rn-north-11998  | 4 | ca-north-8 | B4 |  |
|   rn-north-11998  | 5 | ca-north-8 | B4 |  |
|   rn-north-12024  | 1 | eu-west-1 | B4 |  |
|   rn-north-12024  | 2 | eu-west-1 | B4 |  |
|   rn-north-12024  | 3 | eu-west-1 | B4 |  |
|   rn-north-12024  | 4 | ca-north-8 | B4 |  |
|   rn-north-12024  | 5 | eu-west-1 | B4 |  |
|   rn-north-12051  | 1 | ca-north-8 | B4 |  |
|   rn-north-12051  | 2 | ca-north-8 | B4 |  |
|   rn-north-12051  | 3 | ca-north-8 | B4 |  |
|   rn-north-12051  | 4 | ca-north-8 | B4 |  |
|   rn-north-12051  | 5 | ca-north-8 | B4 |  |
|   rn-north-12081  | 1 | eu-west-1 | B4 |  |
|   rn-north-12081  | 2 | eu-west-1 | B4 |  |
|   rn-north-12081  | 3 | eu-west-1 | B4 |  |
|   rn-north-12081  | 4 | eu-west-1 | B4 |  |
|   rn-north-12081  | 5 | eu-west-1 | B4 |  |
|   rn-north-12109  | 1 | ca-north-8 | B4 |  |
|   rn-north-12109  | 2 | ca-north-8 | B4 |  |
|   rn-north-12109  | 3 | ca-north-8 | B4 |  |
|   rn-north-12109  | 4 | ca-north-8 | B4 |  |
|   rn-north-12109  | 5 | ca-north-8 | B4 |  |
|   rn-north-12137  | 1 | eu-west-1 | B4 |  |
|   rn-north-12137  | 2 | eu-west-1 | B4 |  |
|   rn-north-12137  | 3 | eu-west-1 | B4 |  |
|   rn-north-12137  | 4 | eu-west-1 | B4 |  |
|   rn-north-12137  | 5 | eu-west-1 | B4 |  |
|   rn-north-12163  | 1 | ca-north-8 | B4 |  |
|   rn-north-12163  | 2 | ca-north-8 | B4 |  |
|   rn-north-12163  | 3 | ca-north-8 | B4 |  |
|   rn-north-12163  | 4 | ca-north-8 | B4 |  |
|   rn-north-12163  | 5 | ca-north-8 | B4 |  |
|   rn-north-12194  | 1 | eu-west-1 | B4 |  |
|   rn-north-12194  | 2 | eu-west-1 | B4 |  |
|   rn-north-12194  | 3 | eu-west-1 | B4 |  |
|   rn-north-12194  | 4 | eu-west-1 | B4 |  |
|   rn-north-12194  | 5 | eu-west-1 | B4 |  |
|   rn-north-12220  | 1 | ca-north-8 | B4 |  |
|   rn-north-12220  | 2 | ca-north-8 | B4 |  |
|   rn-north-12220  | 3 | ca-north-8 | B4 |  |
|   rn-north-12220  | 4 | ca-north-8 | B4 |  |
|   rn-north-12220  | 5 | ca-north-8 | B4 |  |
|   rn-north-12250  | 1 | eu-west-1 | B4 |  |
|   rn-north-12250  | 2 | eu-west-1 | B4 |  |
|   rn-north-12250  | 3 | eu-west-1 | B4 |  |
|   rn-north-12250  | 4 | eu-west-1 | B4 |  |
|   rn-north-12250  | 5 | eu-west-1 | B4 |  |
|   rn-north-12277  | 1 | ca-north-8 | B4 |  |
|   rn-north-12277  | 2 | ca-north-8 | B4 |  |
|   rn-north-12277  | 3 | ca-north-8 | B4 |  |
|   rn-north-12277  | 4 | ca-north-8 | B4 |  |
|   rn-north-12277  | 5 | ca-north-8 | B4 |  |
|   rn-north-12306  | 1 | eu-west-1 | B4 |  |
|   rn-north-12306  | 2 | eu-west-1 | B4 |  |
|   rn-north-12306  | 3 | eu-west-1 | B4 |  |
|   rn-north-12306  | 4 | ca-north-8 | B4 |  |
|   rn-north-12306  | 5 | eu-west-1 | B4 |  |
|   rn-north-12332  | 1 | ca-north-8 | B4 |  |
|   rn-north-12332  | 2 | ca-north-8 | B4 |  |
|   rn-north-12332  | 3 | ca-north-8 | B4 |  |
|   rn-north-12332  | 4 | eu-west-1 | B4 |  |
|   rn-north-12332  | 5 | ca-north-8 | B4 |  |
|   rn-north-12362  | 1 | eu-west-1 | B4 |  |
|   rn-north-12362  | 2 | eu-west-1 | B4 |  |
|   rn-north-12362  | 3 | eu-west-1 | B4 |  |
|   rn-north-12362  | 4 | eu-west-1 | B4 |  |
|   rn-north-12362  | 5 | eu-west-1 | B4 |  |
|   rn-north-12389  | 1 | ca-north-8 | B4 |  |
|   rn-north-12389  | 2 | ca-north-8 | B4 |  |
|   rn-north-12389  | 3 | ca-north-8 | B4 |  |
|   rn-north-12389  | 4 | ca-north-8 | B4 |  |
|   rn-north-12389  | 5 | ca-north-8 | B4 |  |
|   rn-north-12421  | 1 | eu-west-1 | B4 |  |
|   rn-north-12421  | 2 | eu-west-1 | B4 |  |
|   rn-north-12421  | 3 | eu-west-1 | B4 |  |
|   rn-north-12421  | 4 | eu-west-1 | B4 |  |
|   rn-north-12421  | 5 | eu-west-1 | B4 |  |
|   rn-north-12449  | 1 | ca-north-8 | B4 |  |
|   rn-north-12449  | 2 | ca-north-8 | B4 |  |
|   rn-north-12449  | 3 | ca-north-8 | B4 |  |
|   rn-north-12449  | 4 | ca-north-8 | B4 |  |
|   rn-north-12449  | 5 | ca-north-8 | B4 |  |
|   rn-north-12472  | 1 | eu-west-1 | B4 |  |
|   rn-north-12472  | 2 | eu-west-1 | B4 |  |
|   rn-north-12472  | 3 | eu-west-1 | B4 |  |
|   rn-north-12472  | 4 | eu-west-1 | B4 |  |
|   rn-north-12472  | 5 | eu-west-1 | B4 |  |
|   rn-north-12505  | 1 | ca-north-8 | B4 |  |
|   rn-north-12505  | 2 | ca-north-8 | B4 |  |
|   rn-north-12505  | 3 | ca-north-8 | B4 |  |
|   rn-north-12505  | 4 | ca-north-8 | B4 |  |
|   rn-north-12505  | 5 | ca-north-8 | B4 |  |
|   rn-north-12531  | 1 | eu-west-1 | B4 |  |
|   rn-north-12531  | 2 | eu-west-1 | B4 |  |
|   rn-north-12531  | 3 | eu-west-1 | B4 |  |
|   rn-north-12531  | 4 | eu-west-1 | B4 |  |
|   rn-north-12531  | 5 | eu-west-1 | B4 |  |
|   rn-north-12558  | 1 | ca-north-8 | B4 |  |
|   rn-north-12558  | 2 | ca-north-8 | B4 |  |
|   rn-north-12558  | 3 | ca-north-8 | B4 |  |
|   rn-north-12558  | 4 | ca-north-8 | B4 |  |
|   rn-north-12558  | 5 | ca-north-8 | B4 |  |
|   rn-north-12589  | 1 | eu-west-1 | B4 |  |
|   rn-north-12589  | 2 | eu-west-1 | B4 |  |
|   rn-north-12589  | 3 | eu-west-1 | B4 |  |
|   rn-north-12589  | 4 | eu-west-1 | B4 |  |
|   rn-north-12589  | 5 | eu-west-1 | B4 |  |
|   rn-north-12616  | 1 | ca-north-8 | B4 |  |
|   rn-north-12616  | 2 | ca-north-8 | B4 |  |
|   rn-north-12616  | 3 | eu-west-1 | B4 |  |
|   rn-north-12616  | 4 | ca-north-8 | B4 |  |
|   rn-north-12616  | 5 | ca-north-8 | B4 |  |
|   rn-north-12641  | 1 | eu-west-1 | B4 |  |
|   rn-north-12641  | 2 | eu-west-1 | B4 |  |
|   rn-north-12641  | 3 | eu-west-1 | B4 |  |
|   rn-north-12641  | 4 | eu-west-1 | B4 |  |
|   rn-north-12641  | 5 | eu-west-1 | B4 |  |
|   rn-north-12667  | 1 | ca-north-8 | B4 |  |
|   rn-north-12667  | 2 | ca-north-8 | B4 |  |
|   rn-north-12667  | 3 | ca-north-8 | B4 |  |
|   rn-north-12667  | 4 | eu-west-1 | B4 |  |
|   rn-north-12667  | 5 | ca-north-8 | B4 |  |
|   rn-north-12696  | 1 | eu-west-1 | B4 |  |
|   rn-north-12696  | 2 | ca-north-8 | B4 |  |
|   rn-north-12696  | 3 | eu-west-1 | B4 |  |
|   rn-north-12696  | 4 | eu-west-1 | B4 |  |
|   rn-north-12696  | 5 | eu-west-1 | B4 |  |
|   rn-north-12727  | 1 | ca-north-8 | B4 |  |
|   rn-north-12727  | 2 | ca-north-8 | B4 |  |
|   rn-north-12727  | 3 | ca-north-8 | B4 |  |
|   rn-north-12727  | 4 | ca-north-8 | B4 |  |
|   rn-north-12727  | 5 | ca-north-8 | B4 |  |
|   rn-north-12757  | 1 | eu-west-1 | B4 |  |
|   rn-north-12757  | 2 | eu-west-1 | B4 |  |
|   rn-north-12757  | 3 | eu-west-1 | B4 |  |
|   rn-north-12757  | 4 | eu-west-1 | B4 |  |
|   rn-north-12757  | 5 | eu-west-1 | B4 |  |
|   rn-north-12779  | 1 | ca-north-8 | B4 |  |
|   rn-north-12779  | 2 | ca-north-8 | B4 |  |
|   rn-north-12779  | 3 | ca-north-8 | B4 |  |
|   rn-north-12779  | 4 | ca-north-8 | B4 |  |
|   rn-north-12779  | 5 | ca-north-8 | B4 |  |
|   rn-north-12809  | 1 | eu-west-1 | B4 |  |
|   rn-north-12809  | 2 | eu-west-1 | B4 |  |
|   rn-north-12809  | 3 | eu-west-1 | B4 |  |
|   rn-north-12809  | 4 | eu-west-1 | B4 |  |
|   rn-north-12809  | 5 | eu-west-1 | B4 |  |
|   rn-north-12836  | 1 | ca-north-8 | B4 |  |
|   rn-north-12836  | 2 | ca-north-8 | B4 |  |
|   rn-north-12836  | 3 | ca-north-8 | B4 |  |
|   rn-north-12836  | 4 | ca-north-8 | B4 |  |
|   rn-north-12836  | 5 | ca-north-8 | B4 |  |
|   rn-north-12867  | 1 | eu-west-1 | B4 | late? |
|   rn-north-12867  | 2 | eu-west-1 | B4 |  |
|   rn-north-12867  | 3 | eu-west-1 | B4 |  |
|   rn-north-12867  | 4 | eu-west-1 | B4 |  |
|   rn-north-12867  | 5 | eu-west-1 | B4 |  |
|   rn-north-12897  | 1 | ca-north-8 | B4 |  |
|   rn-north-12897  | 2 | ca-north-8 | B4 | dup? |
|   rn-north-12897  | 3 | ca-north-8 | B4 |  |
|   rn-north-12897  | 4 | ca-north-8 | B4 |  |
|   rn-north-12897  | 5 | ca-north-8 | B4 | late? |
|   rn-north-12922  | 1 | eu-west-1 | B4 |  |
|   rn-north-12922  | 2 | eu-west-1 | B4 |  |
|   rn-north-12922  | 3 | eu-west-1 | B4 |  |
|   rn-north-12922  | 4 | eu-west-1 | B4 | dup? |
|   rn-north-12922  | 5 | eu-west-1 | B4 |  |
|   rn-north-12950  | 1 | ca-north-8 | B4 |  |
|   rn-north-12950  | 2 | ca-north-8 | B4 | late? |
|   rn-north-12950  | 3 | ca-north-8 | B4 |  |
|   rn-north-12950  | 4 | ca-north-8 | B4 | void? |
|   rn-north-12950  | 5 | ca-north-8 | B4 |  |
|   rn-north-12981  | 1 | eu-west-1 | B4 |  |
|   rn-north-12981  | 2 | eu-west-1 | B4 |  |
|   rn-north-12981  | 3 | eu-west-1 | B4 |  |
|   rn-north-12981  | 3 | eu-west-1 | B4 |  |
|   rn-north-12981  | 4 | eu-west-1 | B4 |  |
|   rn-north-12981  | 5 | eu-west-1 | B4 |  |
|   rn-north-13007  | 1 | ca-north-8 | B4 |  |
|   rn-north-13007  | 2 | ca-north-8 | B4 |  |
|   rn-north-13007  | 3 | eu-west-1 | B4 |  |
|   rn-north-13007  | 4 | ca-north-8 | B4 |  |
|   rn-north-13007  | 5 | ca-north-8 | B4 | recheck |
|   rn-north-13034  | 1 | eu-west-1 | B4 |  |
|   rn-north-13034  | 2 | eu-west-1 | B4 | recheck |
|   rn-north-13034  | 3 | eu-west-1 | B4 | late? |
|   rn-north-13034  | 4 | eu-west-1 | B4 |  |
|   rn-north-13034  | 5 | eu-west-1 | B4 |  |
|   rn-north-13061  | 1 | ca-north-8 | B4 |  |
|   rn-north-13061  | 2 | ca-north-8 | B4 |  |
|   rn-north-13061  | 3 | ca-north-8 | B4 | late? |
|   rn-north-13061  | 4 | eu-west-1 | B4 |  |
|   rn-north-13061  | 5 | ca-north-8 | B4 |  |
|   rn-north-13089  | 1 | eu-west-1 | B4 |  |
|   rn-north-13089  | 2 | eu-west-1 | B4 |  |
|   rn-north-13089  | 3 | eu-west-1 | B4 |  |
|   rn-north-13089  | 4 | eu-west-1 | B4 |  |
|   rn-north-13089  | 5 | eu-west-1 | B4 |  |
|   rn-north-13119  | 1 | ca-north-8 | B4 |  |
|   rn-north-13119  | 2 | ca-north-8 | B4 |  |
|   rn-north-13119  | 3 | ca-north-8 | B4 | dup? |
|   rn-north-13119  | 4 | eu-west-1 | B4 |  |
|   rn-north-13119  | 5 | eu-west-1 | B4 |  |
|   rn-north-13149  | 1 | eu-west-1 | B4 |  |
|   rn-north-13149  | 2 | eu-west-1 | B4 |  |
|   rn-north-13149  | 3 | eu-west-1 | B4 |  |
|   rn-north-13149  | 4 | eu-west-1 | B4 |  |
|   rn-north-13149  | 5 | eu-west-1 | B4 |  |
|   rn-north-13175  | 1 | ca-north-8 | B4 |  |
|   rn-north-13175  | 2 | ca-north-8 | B4 |  |
|   rn-north-13175  | 3 | ca-north-8 | B4 |  |
|   rn-north-13175  | 4 | ca-north-8 | B4 |  |
|   rn-north-13175  | 5 | ca-north-8 | B4 |  |
|   rn-north-13199  | 1 | eu-west-1 | B4 |  |
|   rn-north-13199  | 2 | ca-north-8 | B4 |  |
|   rn-north-13199  | 3 | eu-west-1 | B4 |  |
|   rn-north-13199  | 4 | ca-north-8 | B4 |  |
|   rn-north-13199  | 5 | eu-west-1 | B4 | late? |
|   rn-north-13228  | 1 | ca-north-8 | B4 |  |
|   rn-north-13228  | 2 | ca-north-8 | B4 |  |
|   rn-north-13228  | 3 | ca-north-8 | B4 |  |
|   rn-north-13228  | 4 | ca-north-8 | B4 |  |
|   rn-north-13228  | 5 | ca-north-8 | B4 |  |
|   rn-north-13260  | 1 | eu-west-1 | B4 |  |
|   rn-north-13260  | 2 | ca-north-8 | B4 |  |
|   rn-north-13260  | 3 | eu-west-1 | B4 | dup? |
|   rn-north-13260  | 3 | eu-west-1 | B4 | dup? |
|   rn-north-13260  | 4 | eu-west-1 | B4 |  |
|   rn-north-13260  | 5 | eu-west-1 | B4 | void? |
|   rn-north-13260  | 5 | eu-west-1 | B4 | void? |
|   rn-north-13284  | 1 | ca-north-8 | B4 |  |
|   rn-north-13284  | 2 | ca-north-8 | B4 |  |
|   rn-north-13284  | 3 | ca-north-8 | B4 |  |
|   rn-north-13284  | 4 | ca-north-8 | B4 | recheck |
|   rn-north-13284  | 5 | ca-north-8 | B4 |  |
|   rn-north-13316  | 1 | eu-west-1 | B4 |  |
|   rn-north-13316  | 2 | eu-west-1 | B4 | void? |
|   rn-north-13316  | 3 | eu-west-1 | B4 | dup? |
|   rn-north-13316  | 4 | ca-north-8 | B4 |  |
|   rn-north-13316  | 5 | ca-north-8 | B4 |  |
|   rn-north-13339  | 1 | ca-north-8 | B4 |  |
|   rn-north-13339  | 2 | ca-north-8 | B4 |  |
|   rn-north-13339  | 3 | ca-north-8 | B4 |  |
|   rn-north-13339  | 4 | ca-north-8 | B4 |  |
|   rn-north-13339  | 5 | ca-north-8 | B4 | recheck |
|   rn-north-13371  | 1 | eu-west-1 | B4 |  |
|   rn-north-13371  | 2 | eu-west-1 | B4 |  |
|   rn-north-13371  | 3 | ca-north-8 | B4 | late? |
|   rn-north-13371  | 4 | eu-west-1 | B4 | late? |
|   rn-north-13371  | 5 | eu-west-1 | B4 |  |
|   rn-north-13400  | 1 | ca-north-8 | B4 |  |
|   rn-north-13400  | 2 | eu-west-1 | B4 |  |
|   rn-north-13400  | 3 | ca-north-8 | B4 |  |
|   rn-north-13400  | 4 | ca-north-8 | B4 |  |
|   rn-north-13400  | 5 | ca-north-8 | B4 | dup? |
|   rn-north-13424  | 1 | eu-west-1 | B4 | recheck |
|   rn-north-13424  | 2 | eu-west-1 | B4 |  |
|   rn-north-13424  | 3 | eu-west-1 | B4 |  |
|   rn-north-13424  | 4 | eu-west-1 | B4 |  |
|   rn-north-13424  | 5 | eu-west-1 | B4 |  |
|   rn-north-13457  | 1 | ca-north-8 | B4 |  |
|   rn-north-13457  | 2 | ca-north-8 | B4 |  |
|   rn-north-13457  | 3 | ca-north-8 | B4 |  |
|   rn-north-13457  | 3 | ca-north-8 | B4 |  |
|   rn-north-13457  | 4 | ca-north-8 | B4 |  |
|   rn-north-13457  | 5 | ca-north-8 | B4 | void? |
|   rn-north-13483  | 1 | eu-west-1 | B4 |  |
|   rn-north-13483  | 2 | eu-west-1 | B4 |  |
|   rn-north-13483  | 3 | eu-west-1 | B4 |  |
|   rn-north-13483  | 4 | eu-west-1 | B4 | void? |
|   rn-north-13483  | 5 | eu-west-1 | B4 |  |
|   rn-north-13510  | 1 | ca-north-8 | B4 | void? |
|   rn-north-13510  | 2 | ca-north-8 | B4 |  |
|   rn-north-13510  | 3 | ca-north-8 | B4 |  |
|   rn-north-13510  | 4 | ca-north-8 | B4 |  |
|   rn-north-13510  | 5 | ca-north-8 | B4 |  |
|   rn-north-13535  | 1 | eu-west-1 | B4 |  |
|   rn-north-13535  | 2 | eu-west-1 | B4 |  |
|   rn-north-13535  | 3 | eu-west-1 | B4 |  |
|   rn-north-13535  | 4 | eu-west-1 | B4 | recheck |
|   rn-north-13535  | 5 | eu-west-1 | B4 | dup? |
|   rn-north-13565  | 1 | ca-north-8 | B4 |  |
|   rn-north-13565  | 2 | ca-north-8 | B4 | recheck |
|   rn-north-13565  | 3 | ca-north-8 | B4 |  |
|   rn-north-13565  | 4 | ca-north-8 | B4 |  |
|   rn-north-13565  | 5 | ca-north-8 | B4 |  |
|   rn-north-13597  | 1 | eu-west-1 | B4 |  |
|   rn-north-13597  | 2 | eu-west-1 | B4 |  |
|   rn-north-13597  | 3 | eu-west-1 | B4 |  |
|   rn-north-13597  | 4 | eu-west-1 | B4 | dup? |
|   rn-north-13597  | 5 | eu-west-1 | B4 |  |
|   rn-north-13622  | 1 | ca-north-8 | B4 |  |
|   rn-north-13622  | 2 | ca-north-8 | B4 |  |
|   rn-north-13622  | 3 | ca-north-8 | B4 |  |
|   rn-north-13622  | 4 | ca-north-8 | B4 |  |
|   rn-north-13622  | 5 | ca-north-8 | B4 | void? |
|   rn-north-13653  | 1 | eu-west-1 | B4 | recheck |
|   rn-north-13653  | 2 | eu-west-1 | B4 |  |
|   rn-north-13653  | 3 | eu-west-1 | B4 |  |
|   rn-north-13653  | 4 | eu-west-1 | B4 | late? |
|   rn-north-13653  | 5 | eu-west-1 | B4 |  |
|   rn-north-13677  | 1 | ca-north-8 | B4 |  |
|   rn-north-13677  | 2 | eu-west-1 | B4 |  |
|   rn-north-13677  | 3 | ca-north-8 | B4 |  |
|   rn-north-13677  | 3 | ca-north-8 | B4 |  |
|   rn-north-13677  | 4 | ca-north-8 | B4 |  |
|   rn-north-13677  | 5 | ca-north-8 | B4 |  |
|   rn-north-13708  | 1 | eu-west-1 | B4 | dup? |
|   rn-north-13708  | 2 | eu-west-1 | B4 | void? |
|   rn-north-13708  | 3 | eu-west-1 | B4 |  |
|   rn-north-13708  | 4 | eu-west-1 | B4 |  |
|   rn-north-13708  | 5 | eu-west-1 | B4 |  |
|   rn-north-13731  | 1 | ca-north-8 | B4 |  |
|   rn-north-13731  | 2 | ca-north-8 | B4 |  |
|   rn-north-13731  | 3 | ca-north-8 | B4 |  |
|   rn-north-13731  | 4 | ca-north-8 | B4 |  |
|   rn-north-13731  | 5 | ca-north-8 | B4 |  |
|   rn-north-13760  | 1 | eu-west-1 | B4 |  |
|   rn-north-13760  | 2 | eu-west-1 | B4 |  |
|   rn-north-13760  | 3 | ca-north-8 | B4 |  |
|   rn-north-13760  | 4 | eu-west-1 | B4 |  |
|   rn-north-13760  | 5 | eu-west-1 | B4 |  |
|   rn-north-13788  | 1 | ca-north-8 | B4 |  |
|   rn-north-13788  | 2 | eu-west-1 | B4 |  |
|   rn-north-13788  | 3 | ca-north-8 | B4 | recheck |
|   rn-north-13788  | 4 | ca-north-8 | B4 |  |
|   rn-north-13788  | 5 | ca-north-8 | B4 |  |
|   rn-north-13816  | 1 | eu-west-1 | B4 |  |
|   rn-north-13816  | 2 | eu-west-1 | B4 |  |
|   rn-north-13816  | 3 | eu-west-1 | B4 | dup? |
|   rn-north-13816  | 4 | eu-west-1 | B4 |  |
|   rn-north-13816  | 5 | eu-west-1 | B4 |  |
|   rn-north-13846  | 1 | ca-north-8 | B4 | late? |
|   rn-north-13846  | 2 | ca-north-8 | B4 |  |
|   rn-north-13846  | 3 | ca-north-8 | B4 | recheck |
|   rn-north-13846  | 3 | ca-north-8 | B4 | recheck |
|   rn-north-13846  | 4 | ca-north-8 | B4 |  |
|   rn-north-13846  | 5 | ca-north-8 | B4 | late? |
|   rn-north-13874  | 1 | eu-west-1 | B4 |  |
|   rn-north-13874  | 2 | eu-west-1 | B4 |  |
|   rn-north-13874  | 3 | eu-west-1 | B4 | void? |
|   rn-north-13874  | 4 | eu-west-1 | B4 |  |
|   rn-north-13874  | 4 | eu-west-1 | B4 |  |
|   rn-north-13874  | 5 | eu-west-1 | B4 |  |
|   rn-north-13905  | 1 | ca-north-8 | B4 |  |
|   rn-north-13905  | 2 | ca-north-8 | B4 | dup? |
|   rn-north-13905  | 3 | ca-north-8 | B4 | late? |
|   rn-north-13905  | 4 | ca-north-8 | B4 |  |
|   rn-north-13905  | 5 | ca-north-8 | B4 |  |
|   rn-north-13930  | 1 | eu-west-1 | B4 |  |
|   rn-north-13930  | 2 | eu-west-1 | B4 | recheck |
|   rn-north-13930  | 3 | eu-west-1 | B4 | dup? |
|   rn-north-13930  | 4 | eu-west-1 | B4 |  |
|   rn-north-13930  | 5 | eu-west-1 | B4 |  |
|   rn-north-13959  | 1 | ca-north-8 | B4 |  |
|   rn-north-13959  | 2 | ca-north-8 | B4 |  |
|   rn-north-13959  | 3 | ca-north-8 | B4 |  |
|   rn-north-13959  | 4 | ca-north-8 | B4 |  |
|   rn-north-13959  | 5 | ca-north-8 | B4 |  |
|   rn-north-13988  | 1 | eu-west-1 | B4 |  |
|   rn-north-13988  | 2 | eu-west-1 | B4 |  |
|   rn-north-13988  | 3 | eu-west-1 | B4 |  |
|   rn-north-13988  | 4 | eu-west-1 | B4 |  |
|   rn-north-13988  | 5 | eu-west-1 | B4 | late? |
|   rn-north-14015  | 1 | ca-north-8 | B4 |  |
|   rn-north-14015  | 2 | ca-north-8 | B4 |  |
|   rn-north-14015  | 3 | eu-west-1 | B4 |  |
|   rn-north-14015  | 4 | ca-north-8 | B4 |  |
|   rn-north-14015  | 5 | ca-north-8 | B4 |  |
|   rn-north-14045  | 1 | eu-west-1 | B4 |  |
|   rn-north-14045  | 2 | eu-west-1 | B4 |  |
|   rn-north-14045  | 3 | eu-west-1 | B4 |  |
|   rn-north-14045  | 4 | eu-west-1 | B4 |  |
|   rn-north-14045  | 5 | eu-west-1 | B4 |  |
|   rn-north-14070  | 1 | ca-north-8 | B4 | void? |
|   rn-north-14070  | 2 | ca-north-8 | B4 |  |
|   rn-north-14070  | 3 | ca-north-8 | B4 |  |
|   rn-north-14070  | 4 | ca-north-8 | B4 |  |
|   rn-north-14070  | 5 | ca-north-8 | B4 | void? |
|   rn-north-14098  | 1 | eu-west-1 | B4 |  |
|   rn-north-14098  | 2 | eu-west-1 | B4 | void? |
|   rn-north-14098  | 3 | ca-north-8 | B4 |  |
|   rn-north-14098  | 4 | eu-west-1 | B4 |  |
|   rn-north-14098  | 5 | eu-west-1 | B4 |  |
|   rn-north-14128  | 1 | ca-north-8 | B4 |  |
|   rn-north-14128  | 2 | ca-north-8 | B4 |  |
|   rn-north-14128  | 3 | ca-north-8 | B4 | late? |
|   rn-north-14128  | 4 | ca-north-8 | B4 |  |
|   rn-north-14128  | 5 | ca-north-8 | B4 |  |
|   rn-north-14155  | 1 | eu-west-1 | B4 |  |
|   rn-north-14155  | 2 | eu-west-1 | B4 |  |
|   rn-north-14155  | 3 | eu-west-1 | B4 |  |
|   rn-north-14155  | 4 | eu-west-1 | B4 |  |
|   rn-north-14155  | 5 | eu-west-1 | B4 | dup? |
|   rn-north-14182  | 1 | ca-north-8 | B4 | void? |
|   rn-north-14182  | 2 | ca-north-8 | B4 |  |
|   rn-north-14182  | 3 | ca-north-8 | B4 |  |
|   rn-north-14182  | 4 | ca-north-8 | B4 | late? |
|   rn-north-14182  | 5 | ca-north-8 | B4 | late? |
|   rn-north-14211  | 1 | eu-west-1 | B4 |  |
|   rn-north-14211  | 2 | eu-west-1 | B4 |  |
|   rn-north-14211  | 3 | eu-west-1 | B4 |  |
|   rn-north-14211  | 4 | eu-west-1 | B4 |  |
|   rn-north-14211  | 4 | eu-west-1 | B4 |  |
|   rn-north-14211  | 5 | eu-west-1 | B4 |  |
|   rn-north-14237  | 1 | ca-north-8 | B4 |  |
|   rn-north-14237  | 2 | ca-north-8 | B4 |  |
|   rn-north-14237  | 3 | eu-west-1 | B4 | late? |
|   rn-north-14237  | 4 | ca-north-8 | B4 | late? |
|   rn-north-14237  | 5 | ca-north-8 | B4 |  |
|   rn-north-14265  | 1 | eu-west-1 | B4 |  |
|   rn-north-14265  | 2 | eu-west-1 | B4 |  |
|   rn-north-14265  | 3 | eu-west-1 | B4 |  |
|   rn-north-14265  | 4 | ca-north-8 | B4 |  |
|   rn-north-14265  | 5 | eu-west-1 | B4 |  |
|   rn-north-14292  | 1 | ca-north-8 | B4 |  |
|   rn-north-14292  | 2 | ca-north-8 | B4 |  |
|   rn-north-14292  | 3 | ca-north-8 | B4 |  |
|   rn-north-14292  | 4 | ca-north-8 | B4 | recheck |
|   rn-north-14292  | 5 | eu-west-1 | B4 |  |
|   rn-north-14319  | 1 | eu-west-1 | B4 | recheck |
|   rn-north-14319  | 2 | eu-west-1 | B4 |  |
|   rn-north-14319  | 3 | eu-west-1 | B4 | recheck |
|   rn-north-14319  | 4 | eu-west-1 | B4 |  |
|   rn-north-14319  | 5 | ca-north-8 | B4 |  |
|   rn-north-14351  | 1 | ca-north-8 | B4 | void? |
|   rn-north-14351  | 2 | ca-north-8 | B4 |  |
|   rn-north-14351  | 3 | ca-north-8 | B4 |  |
|   rn-north-14351  | 4 | ca-north-8 | B4 |  |
|   rn-north-14351  | 5 | ca-north-8 | B4 |  |
|   rn-north-14379  | 1 | eu-west-1 | B4 |  |
|   rn-north-14379  | 2 | eu-west-1 | B4 |  |
|   rn-north-14379  | 3 | eu-west-1 | B4 |  |
|   rn-north-14379  | 4 | eu-west-1 | B4 |  |
|   rn-north-14379  | 5 | eu-west-1 | B4 |  |
|   rn-north-14403  | 1 | ca-north-8 | B4 | late? |
|   rn-north-14403  | 2 | ca-north-8 | B4 |  |
|   rn-north-14403  | 3 | ca-north-8 | B4 |  |
|   rn-north-14403  | 4 | ca-north-8 | B4 |  |
|   rn-north-14403  | 5 | ca-north-8 | B4 |  |
|   rn-north-14436  | 1 | eu-west-1 | B4 | void? |
|   rn-north-14436  | 2 | eu-west-1 | B4 |  |
|   rn-north-14436  | 3 | eu-west-1 | B4 | void? |
|   rn-north-14436  | 4 | eu-west-1 | B4 |  |
|   rn-north-14436  | 5 | eu-west-1 | B4 |  |
|   rn-north-14465  | 1 | ca-north-8 | B4 |  |
|   rn-north-14465  | 2 | ca-north-8 | B4 |  |
|   rn-north-14465  | 3 | ca-north-8 | B4 |  |
|   rn-north-14465  | 4 | ca-north-8 | B4 |  |
|   rn-north-14465  | 5 | ca-north-8 | B4 |  |
|   rn-north-14488  | 1 | eu-west-1 | B4 | late? |
|   rn-north-14488  | 2 | eu-west-1 | B4 | void? |
|   rn-north-14488  | 3 | eu-west-1 | B4 | dup? |
|   rn-north-14488  | 4 | eu-west-1 | B4 |  |
|   rn-north-14488  | 5 | eu-west-1 | B4 |  |
|   rn-north-14519  | 1 | ca-north-8 | B4 |  |
|   rn-north-14519  | 2 | ca-north-8 | B4 |  |
|   rn-north-14519  | 3 | ca-north-8 | B4 |  |
|   rn-north-14519  | 4 | eu-west-1 | B4 |  |
|   rn-north-14519  | 5 | ca-north-8 | B4 |  |
|   rn-north-14549  | 1 | eu-west-1 | B4 |  |
|   rn-north-14549  | 2 | eu-west-1 | B4 |  |
|   rn-north-14549  | 3 | ca-north-8 | B4 |  |
|   rn-north-14549  | 4 | ca-north-8 | B4 |  |
|   rn-north-14549  | 5 | eu-west-1 | B4 |  |
|   rn-north-14571  | 1 | ca-north-8 | B4 |  |
|   rn-north-14571  | 2 | ca-north-8 | B4 | recheck |
|   rn-north-14571  | 3 | ca-north-8 | B4 |  |
|   rn-north-14571  | 4 | ca-north-8 | B4 |  |
|   rn-north-14571  | 5 | ca-north-8 | B4 |  |
|   rn-north-14605  | 1 | eu-west-1 | B4 |  |
|   rn-north-14605  | 1 | eu-west-1 | B4 |  |
|   rn-north-14605  | 2 | eu-west-1 | B4 |  |
|   rn-north-14605  | 3 | eu-west-1 | B4 | late? |
|   rn-north-14605  | 3 | eu-west-1 | B4 | late? |
|   rn-north-14605  | 4 | eu-west-1 | B4 |  |
|   rn-north-14605  | 5 | eu-west-1 | B4 |  |
|   rn-north-14633  | 1 | ca-north-8 | B4 |  |
|   rn-north-14633  | 2 | ca-north-8 | B4 |  |
|   rn-north-14633  | 3 | ca-north-8 | B4 |  |
|   rn-north-14633  | 4 | ca-north-8 | B4 |  |
|   rn-north-14633  | 5 | ca-north-8 | B4 | dup? |
|   rn-north-14661  | 1 | eu-west-1 | B4 |  |
|   rn-north-14661  | 2 | eu-west-1 | B4 |  |
|   rn-north-14661  | 3 | eu-west-1 | B4 |  |
|   rn-north-14661  | 4 | eu-west-1 | B4 |  |
|   rn-north-14661  | 5 | eu-west-1 | B4 |  |
|   rn-north-14688  | 1 | ca-north-8 | B4 |  |
|   rn-north-14688  | 2 | ca-north-8 | B4 | late? |
|   rn-north-14688  | 3 | ca-north-8 | B4 |  |
|   rn-north-14688  | 4 | ca-north-8 | B4 |  |
|   rn-north-14688  | 5 | ca-north-8 | B4 | void? |
|   rn-north-14715  | 1 | eu-west-1 | B4 |  |
|   rn-north-14715  | 2 | eu-west-1 | B4 |  |
|   rn-north-14715  | 3 | eu-west-1 | B4 |  |
|   rn-north-14715  | 4 | eu-west-1 | B4 |  |
|   rn-north-14715  | 5 | eu-west-1 | B4 |  |
|   rn-north-14740  | 1 | ca-north-8 | B4 |  |
|   rn-north-14740  | 2 | ca-north-8 | B4 | late? |
|   rn-north-14740  | 3 | eu-west-1 | B4 |  |
|   rn-north-14740  | 4 | ca-north-8 | B4 |  |
|   rn-north-14740  | 5 | ca-north-8 | B4 |  |
| RN-NORTH-14770 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-14770 | 2 | eu-west-1 | B5 | recheck |
| RN-NORTH-14770 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-14770 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-14770 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-14795 | 1 | ca-north-8 | B5 | late? |
| RN-NORTH-14795 | 2 | ca-north-8 | B5 | late? |
| RN-NORTH-14795 | 3 | ca-north-8 | B5 | dup? |
| RN-NORTH-14795 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-14795 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-14827 | 1 | eu-west-1 | B5 | late? |
| RN-NORTH-14827 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-14827 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-14827 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-14827 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-14856 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-14856 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-14856 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-14856 | 4 | ca-north-8 | B5 | dup? |
| RN-NORTH-14856 | 5 | ca-north-8 | B5 | late? |
| RN-NORTH-14884 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-14884 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-14884 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-14884 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-14884 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-14911 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-14911 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-14911 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-14911 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-14911 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-14935 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-14935 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-14935 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-14935 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-14935 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-14963 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-14963 | 2 | ca-north-8 | B5 | void? |
| RN-NORTH-14963 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-14963 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-14963 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-14993 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-14993 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-14993 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-14993 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-14993 | 5 | eu-west-1 | B5 | dup? |
| RN-NORTH-15025 | 1 | ca-north-8 | B5 | late? |
| RN-NORTH-15025 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-15025 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-15025 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-15025 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-15053 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-15053 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-15053 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-15053 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-15053 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-15078 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-15078 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-15078 | 3 | ca-north-8 | B5 | recheck |
| RN-NORTH-15078 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-15078 | 5 | ca-north-8 | B5 | recheck |
| RN-NORTH-15106 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-15106 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-15106 | 3 | eu-west-1 | B5 | late? |
| RN-NORTH-15106 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-15106 | 5 | eu-west-1 | B5 | void? |
| RN-NORTH-15131 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-15131 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-15131 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-15131 | 4 | ca-north-8 | B5 | dup? |
| RN-NORTH-15131 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-15162 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-15162 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-15162 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-15162 | 4 | eu-west-1 | B5 | recheck |
| RN-NORTH-15162 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-15189 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-15189 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-15189 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-15189 | 3 | ca-north-8 | B5 | dup? |
| RN-NORTH-15189 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-15189 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-15216 | 1 | eu-west-1 | B5 | void? |
| RN-NORTH-15216 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-15216 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-15216 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-15216 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-15249 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-15249 | 2 | ca-north-8 | B5 | recheck |
| RN-NORTH-15249 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-15249 | 4 | eu-west-1 | B5 | dup? |
| RN-NORTH-15249 | 5 | ca-north-8 | B5 | dup? |
| RN-NORTH-15273 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-15273 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-15273 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-15273 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-15273 | 5 | eu-west-1 | B5 | void? |
| RN-NORTH-15299 | 1 | ca-north-8 | B5 | dup? |
| RN-NORTH-15299 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-15299 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-15299 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-15299 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-15331 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-15331 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-15331 | 3 | eu-west-1 | B5 | dup? |
| RN-NORTH-15331 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-15331 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-15355 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-15355 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-15355 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-15355 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-15355 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-15355 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-15355 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-15389 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-15389 | 2 | eu-west-1 | B5 | late? |
| RN-NORTH-15389 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-15389 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-15389 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-15413 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-15413 | 2 | ca-north-8 | B5 | dup? |
| RN-NORTH-15413 | 2 | ca-north-8 | B5 | dup? |
| RN-NORTH-15413 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-15413 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-15413 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-15413 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-15441 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-15441 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-15441 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-15441 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-15441 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-15467 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-15467 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-15467 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-15467 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-15467 | 5 | ca-north-8 | B5 | void? |
| RN-NORTH-15496 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-15496 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-15496 | 3 | eu-west-1 | B5 | dup? |
| RN-NORTH-15496 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-15496 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-15523 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-15523 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-15523 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-15523 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-15523 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-15551 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-15551 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-15551 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-15551 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-15551 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-15584 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-15584 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-15584 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-15584 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-15584 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-15609 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-15609 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-15609 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-15609 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-15609 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-15636 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-15636 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-15636 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-15636 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-15636 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-15666 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-15666 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-15666 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-15666 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-15666 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-15691 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-15691 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-15691 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-15691 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-15691 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-15722 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-15722 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-15722 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-15722 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-15722 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-15751 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-15751 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-15751 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-15751 | 4 | ca-north-8 | B5 | dup? |
| RN-NORTH-15751 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-15778 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-15778 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-15778 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-15778 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-15778 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-15808 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-15808 | 2 | ca-north-8 | B5 | recheck |
| RN-NORTH-15808 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-15808 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-15808 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-15831 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-15831 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-15831 | 3 | eu-west-1 | B5 | recheck |
| RN-NORTH-15831 | 4 | eu-west-1 | B5 | void? |
| RN-NORTH-15831 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-15863 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-15863 | 2 | eu-west-1 | B5 | late? |
| RN-NORTH-15863 | 2 | eu-west-1 | B5 | late? |
| RN-NORTH-15863 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-15863 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-15863 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-15888 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-15888 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-15888 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-15888 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-15888 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-15921 | 1 | ca-north-8 | B5 | dup? |
| RN-NORTH-15921 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-15921 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-15921 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-15921 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-15947 | 1 | eu-west-1 | B5 | void? |
| RN-NORTH-15947 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-15947 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-15947 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-15947 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-15973 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-15973 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-15973 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-15973 | 3 | ca-north-8 | B5 | dup? |
| RN-NORTH-15973 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-15973 | 5 | ca-north-8 | B5 | dup? |
| RN-NORTH-16000 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-16000 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-16000 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-16000 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-16000 | 5 | eu-west-1 | B5 | recheck |
| RN-NORTH-16033 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-16033 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-16033 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-16033 | 4 | ca-north-8 | B5 | dup? |
| RN-NORTH-16033 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-16061 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-16061 | 2 | eu-west-1 | B5 | late? |
| RN-NORTH-16061 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-16061 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-16061 | 5 | eu-west-1 | B5 | late? |
| RN-NORTH-16085 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-16085 | 2 | ca-north-8 | B5 | void? |
| RN-NORTH-16085 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-16085 | 4 | ca-north-8 | B5 | void? |
| RN-NORTH-16085 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-16113 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-16113 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-16113 | 3 | eu-west-1 | B5 | void? |
| RN-NORTH-16113 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-16113 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-16145 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-16145 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-16145 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-16145 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-16145 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-16172 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-16172 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-16172 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-16172 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-16172 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-16198 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-16198 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-16198 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-16198 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-16198 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-16229 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-16229 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-16229 | 2 | eu-west-1 | B5 | recheck |
| RN-NORTH-16229 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-16229 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-16229 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-16257 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-16257 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-16257 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-16257 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-16257 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-16285 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-16285 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-16285 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-16285 | 4 | eu-west-1 | B5 | void? |
| RN-NORTH-16285 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-16310 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-16310 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-16310 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-16310 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-16310 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-16310 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-16339 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-16339 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-16339 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-16339 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-16339 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-16369 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-16369 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-16369 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-16369 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-16369 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-16393 | 1 | eu-west-1 | B5 | late? |
| RN-NORTH-16393 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-16393 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-16393 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-16393 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-16425 | 1 | ca-north-8 | B5 | recheck |
| RN-NORTH-16425 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-16425 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-16425 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-16425 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-16451 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-16451 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-16451 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-16451 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-16451 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-16480 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-16480 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-16480 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-16480 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-16480 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-16505 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-16505 | 2 | ca-north-8 | B5 | void? |
| RN-NORTH-16505 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-16505 | 4 | eu-west-1 | B5 | dup? |
| RN-NORTH-16505 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-16533 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-16533 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-16533 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-16533 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-16533 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-16564 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-16564 | 2 | eu-west-1 | B5 | recheck |
| RN-NORTH-16564 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-16564 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-16564 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-16587 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-16587 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-16587 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-16587 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-16587 | 5 | ca-north-8 | B5 | dup? |
| RN-NORTH-16619 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-16619 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-16619 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-16619 | 4 | eu-west-1 | B5 | recheck |
| RN-NORTH-16619 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-16646 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-16646 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-16646 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-16646 | 4 | ca-north-8 | B5 | late? |
| RN-NORTH-16646 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-16676 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-16676 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-16676 | 3 | eu-west-1 | B5 | void? |
| RN-NORTH-16676 | 4 | eu-west-1 | B5 | void? |
| RN-NORTH-16676 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-16704 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-16704 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-16704 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-16704 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-16704 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-16729 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-16729 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-16729 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-16729 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-16729 | 4 | eu-west-1 | B5 | dup? |
| RN-NORTH-16729 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-16758 | 1 | ca-north-8 | B5 | recheck |
| RN-NORTH-16758 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-16758 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-16758 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-16758 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-16784 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-16784 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-16784 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-16784 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-16784 | 5 | ca-north-8 | B5 | recheck |
| RN-NORTH-16811 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-16811 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-16811 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-16811 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-16811 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-16841 | 1 | eu-west-1 | B5 | late? |
| RN-NORTH-16841 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-16841 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-16841 | 4 | eu-west-1 | B5 | dup? |
| RN-NORTH-16841 | 5 | eu-west-1 | B5 | dup? |
| RN-NORTH-16867 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-16867 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-16867 | 3 | ca-north-8 | B5 | late? |
| RN-NORTH-16867 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-16867 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-16899 | 1 | eu-west-1 | B5 | late? |
| RN-NORTH-16899 | 2 | eu-west-1 | B5 | void? |
| RN-NORTH-16899 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-16899 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-16899 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-16924 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-16924 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-16924 | 3 | ca-north-8 | B5 | late? |
| RN-NORTH-16924 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-16924 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-16952 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-16952 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-16952 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-16952 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-16952 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-16984 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-16984 | 2 | ca-north-8 | B5 | void? |
| RN-NORTH-16984 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-16984 | 4 | ca-north-8 | B5 | recheck |
| RN-NORTH-16984 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-17013 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-17013 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-17013 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-17013 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-17013 | 5 | eu-west-1 | B5 | recheck |
| RN-NORTH-17037 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-17037 | 2 | ca-north-8 | B5 | void? |
| RN-NORTH-17037 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-17037 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-17037 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-17069 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-17069 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-17069 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-17069 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-17069 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-17092 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-17092 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-17092 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-17092 | 4 | ca-north-8 | B5 | void? |
| RN-NORTH-17092 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-17121 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-17121 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-17121 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-17121 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-17121 | 5 | eu-west-1 | B5 | dup? |
| RN-NORTH-17149 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-17149 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-17149 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-17149 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-17149 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-17180 | 1 | eu-west-1 | B5 | recheck |
| RN-NORTH-17180 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-17180 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-17180 | 4 | eu-west-1 | B5 | dup? |
| RN-NORTH-17180 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-17208 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-17208 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-17208 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-17208 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-17208 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-17208 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-17234 | 1 | eu-west-1 | B5 | recheck |
| RN-NORTH-17234 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-17234 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-17234 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-17234 | 5 | eu-west-1 | B5 | recheck |
| RN-NORTH-17263 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-17263 | 2 | ca-north-8 | B5 | void? |
| RN-NORTH-17263 | 3 | ca-north-8 | B5 | late? |
| RN-NORTH-17263 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-17263 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-17293 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-17293 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-17293 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-17293 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-17293 | 5 | eu-west-1 | B5 | dup? |
| RN-NORTH-17315 | 1 | ca-north-8 | B5 | void? |
| RN-NORTH-17315 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-17315 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-17315 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-17315 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-17344 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-17344 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-17344 | 3 | eu-west-1 | B5 | void? |
| RN-NORTH-17344 | 4 | eu-west-1 | B5 | recheck |
| RN-NORTH-17344 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-17377 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-17377 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-17377 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-17377 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-17377 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-17404 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-17404 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-17404 | 3 | eu-west-1 | B5 | late? |
| RN-NORTH-17404 | 4 | eu-west-1 | B5 | recheck |
| RN-NORTH-17404 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-17430 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-17430 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-17430 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-17430 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-17430 | 5 | ca-north-8 | B5 | dup? |
| RN-NORTH-17455 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-17455 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-17455 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-17455 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-17455 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-17485 | 1 | ca-north-8 | B5 | dup? |
| RN-NORTH-17485 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-17485 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-17485 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-17485 | 5 | ca-north-8 | B5 | dup? |
| RN-NORTH-17517 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-17517 | 2 | eu-west-1 | B5 | void? |
| RN-NORTH-17517 | 3 | eu-west-1 | B5 | dup? |
| RN-NORTH-17517 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-17517 | 5 | eu-west-1 | B5 | late? |
| RN-NORTH-17545 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-17545 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-17545 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-17545 | 4 | ca-north-8 | B5 | recheck |
| RN-NORTH-17545 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-17568 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-17568 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-17568 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-17568 | 4 | eu-west-1 | B5 | late? |
| RN-NORTH-17568 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-17598 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-17598 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-17598 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-17598 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-17598 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-17624 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-17624 | 2 | eu-west-1 | B5 | recheck |
| RN-NORTH-17624 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-17624 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-17624 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-17653 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-17653 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-17653 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-17653 | 4 | ca-north-8 | B5 | void? |
| RN-NORTH-17653 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-17684 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-17684 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-17684 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-17684 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-17684 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-17712 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-17712 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-17712 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-17712 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-17712 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-17740 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-17740 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-17740 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-17740 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-17740 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-17768 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-17768 | 2 | ca-north-8 | B5 | late? |
| RN-NORTH-17768 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-17768 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-17768 | 5 | ca-north-8 | B5 | late? |
| RN-NORTH-17796 | 1 | eu-west-1 | B5 | void? |
| RN-NORTH-17796 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-17796 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-17796 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-17796 | 5 | eu-west-1 | B5 | void? |
| RN-NORTH-17821 | 1 | ca-north-8 | B5 | recheck |
| RN-NORTH-17821 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-17821 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-17821 | 4 | ca-north-8 | B5 | recheck |
| RN-NORTH-17821 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-17821 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-17848 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-17848 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-17848 | 3 | eu-west-1 | B5 | dup? |
| RN-NORTH-17848 | 4 | eu-west-1 | B5 | void? |
| RN-NORTH-17848 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-17879 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-17879 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-17879 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-17879 | 4 | ca-north-8 | B5 | late? |
| RN-NORTH-17879 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-17904 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-17904 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-17904 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-17904 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-17904 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-17932 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-17932 | 2 | ca-north-8 | B5 | late? |
| RN-NORTH-17932 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-17932 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-17932 | 5 | ca-north-8 | B5 | late? |
| RN-NORTH-17962 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-17962 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-17962 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-17962 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-17962 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-17988 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-17988 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-17988 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-17988 | 4 | ca-north-8 | B5 | recheck |
| RN-NORTH-17988 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-18017 | 1 | eu-west-1 | B5 | recheck |
| RN-NORTH-18017 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-18017 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-18017 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-18017 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-18048 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-18048 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-18048 | 3 | ca-north-8 | B5 | recheck |
| RN-NORTH-18048 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-18048 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-18077 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-18077 | 2 | eu-west-1 | B5 | recheck |
| RN-NORTH-18077 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-18077 | 4 | eu-west-1 | B5 | void? |
| RN-NORTH-18077 | 5 | eu-west-1 | B5 | dup? |
| RN-NORTH-18102 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-18102 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-18102 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-18102 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-18102 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-18127 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-18127 | 2 | eu-west-1 | B5 | recheck |
| RN-NORTH-18127 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-18127 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-18127 | 5 | ca-north-8 | B5 | late? |
| RN-NORTH-18157 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-18157 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-18157 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-18157 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-18157 | 5 | ca-north-8 | B5 | dup? |
| RN-NORTH-18186 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-18186 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-18186 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-18186 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-18186 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-18211 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-18211 | 2 | ca-north-8 | B5 | dup? |
| RN-NORTH-18211 | 3 | ca-north-8 | B5 | recheck |
| RN-NORTH-18211 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-18211 | 5 | eu-west-1 | B5 | recheck |
| RN-NORTH-18243 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-18243 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-18243 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-18243 | 4 | eu-west-1 | B5 | late? |
| RN-NORTH-18243 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-18272 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-18272 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-18272 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-18272 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-18272 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-18296 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-18296 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-18296 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-18296 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-18296 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-18296 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-18328 | 1 | ca-north-8 | B5 | recheck |
| RN-NORTH-18328 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-18328 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-18328 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-18328 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-18353 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-18353 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-18353 | 3 | eu-west-1 | B5 | dup? |
| RN-NORTH-18353 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-18353 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-18384 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-18384 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-18384 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-18384 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-18384 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-18410 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-18410 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-18410 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-18410 | 4 | ca-north-8 | B5 | late? |
| RN-NORTH-18410 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-18438 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-18438 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-18438 | 3 | ca-north-8 | B5 | recheck |
| RN-NORTH-18438 | 4 | ca-north-8 | B5 | recheck |
| RN-NORTH-18438 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-18468 | 1 | eu-west-1 | B5 | void? |
| RN-NORTH-18468 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-18468 | 3 | eu-west-1 | B5 | dup? |
| RN-NORTH-18468 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-18468 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-18491 | 1 | ca-north-8 | B5 | late? |
| RN-NORTH-18491 | 1 | ca-north-8 | B5 | late? |
| RN-NORTH-18491 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-18491 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-18491 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-18491 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-18519 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-18519 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-18519 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-18519 | 4 | eu-west-1 | B5 | recheck |
| RN-NORTH-18519 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-18550 | 1 | ca-north-8 | B5 | late? |
| RN-NORTH-18550 | 1 | ca-north-8 | B5 | late? |
| RN-NORTH-18550 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-18550 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-18550 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-18550 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-18577 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-18577 | 2 | eu-west-1 | B5 | dup? |
| RN-NORTH-18577 | 3 | eu-west-1 | B5 | dup? |
| RN-NORTH-18577 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-18577 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-18604 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-18604 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-18604 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-18604 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-18604 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-18636 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-18636 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-18636 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-18636 | 4 | eu-west-1 | B5 | recheck |
| RN-NORTH-18636 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-18663 | 1 | ca-north-8 | B5 | recheck |
| RN-NORTH-18663 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-18663 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-18663 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-18663 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-18691 | 1 | eu-west-1 | B5 | late? |
| RN-NORTH-18691 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-18691 | 3 | eu-west-1 | B5 | void? |
| RN-NORTH-18691 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-18691 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-18720 | 1 | ca-north-8 | B5 | dup? |
| RN-NORTH-18720 | 1 | ca-north-8 | B5 | dup? |
| RN-NORTH-18720 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-18720 | 3 | eu-west-1 | B5 | dup? |
| RN-NORTH-18720 | 4 | ca-north-8 | B5 | late? |
| RN-NORTH-18720 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-18747 | 1 | eu-west-1 | B5 | dup? |
| RN-NORTH-18747 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-18747 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-18747 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-18747 | 4 | eu-west-1 | B5 | recheck |
| RN-NORTH-18747 | 5 | eu-west-1 | B5 | late? |
| RN-NORTH-18773 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-18773 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-18773 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-18773 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-18773 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-18801 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-18801 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-18801 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-18801 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-18801 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-18801 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-18827 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-18827 | 2 | ca-north-8 | B5 | dup? |
| RN-NORTH-18827 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-18827 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-18827 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-18827 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-18856 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-18856 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-18856 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-18856 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-18856 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-18888 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-18888 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-18888 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-18888 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-18888 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-18912 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-18912 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-18912 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-18912 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-18912 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-18939 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-18939 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-18939 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-18939 | 4 | ca-north-8 | B5 | void? |
| RN-NORTH-18939 | 4 | ca-north-8 | B5 | void? |
| RN-NORTH-18939 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-18973 | 1 | eu-west-1 | B5 | void? |
| RN-NORTH-18973 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-18973 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-18973 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-18973 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-19001 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-19001 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-19001 | 3 | ca-north-8 | B5 | dup? |
| RN-NORTH-19001 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-19001 | 5 | ca-north-8 | B5 | dup? |
| RN-NORTH-19025 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-19025 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-19025 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-19025 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-19025 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-19053 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-19053 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-19053 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-19053 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-19053 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-19083 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-19083 | 2 | eu-west-1 | B5 | late? |
| RN-NORTH-19083 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-19083 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-19083 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-19113 | 1 | ca-north-8 | B5 | recheck |
| RN-NORTH-19113 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-19113 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-19113 | 4 | ca-north-8 | B5 | late? |
| RN-NORTH-19113 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-19140 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-19140 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-19140 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-19140 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-19140 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-19168 | 1 | ca-north-8 | B5 | recheck |
| RN-NORTH-19168 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-19168 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-19168 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-19168 | 5 | ca-north-8 | B5 | dup? |
| RN-NORTH-19192 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-19192 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-19192 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-19192 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-19192 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-19192 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-19223 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-19223 | 2 | eu-west-1 | B5 | dup? |
| RN-NORTH-19223 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-19223 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-19223 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-19248 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-19248 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-19248 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-19248 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-19248 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-19280 | 1 | ca-north-8 | B5 | late? |
| RN-NORTH-19280 | 2 | ca-north-8 | B5 | dup? |
| RN-NORTH-19280 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-19280 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-19280 | 5 | eu-west-1 | B5 | late? |
| RN-NORTH-19308 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-19308 | 2 | ca-north-8 | B5 | void? |
| RN-NORTH-19308 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-19308 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-19308 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-19331 | 1 | ca-north-8 | B5 | late? |
| RN-NORTH-19331 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-19331 | 3 | ca-north-8 | B5 | recheck |
| RN-NORTH-19331 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-19331 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-19360 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-19360 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-19360 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-19360 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-19360 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-19360 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-19388 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-19388 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-19388 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-19388 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-19388 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-19415 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-19415 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-19415 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-19415 | 4 | eu-west-1 | B5 |  |
| RN-NORTH-19415 | 5 | eu-west-1 | B5 | late? |
| RN-NORTH-19447 | 1 | ca-north-8 | B5 |  |
| RN-NORTH-19447 | 2 | ca-north-8 | B5 | late? |
| RN-NORTH-19447 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-19447 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-19447 | 5 | ca-north-8 | B5 |  |
| RN-NORTH-19475 | 1 | eu-west-1 | B5 |  |
| RN-NORTH-19475 | 2 | eu-west-1 | B5 |  |
| RN-NORTH-19475 | 3 | eu-west-1 | B5 |  |
| RN-NORTH-19475 | 4 | eu-west-1 | B5 | void? |
| RN-NORTH-19475 | 5 | eu-west-1 | B5 |  |
| RN-NORTH-19504 | 1 | ca-north-8 | B5 | dup? |
| RN-NORTH-19504 | 2 | ca-north-8 | B5 |  |
| RN-NORTH-19504 | 3 | ca-north-8 | B5 |  |
| RN-NORTH-19504 | 4 | ca-north-8 | B5 |  |
| RN-NORTH-19504 | 5 | ca-north-8 | B5 |  |
|   rn-north-19533  | 1 | eu-west-1 | B6 | void? |
|   rn-north-19533  | 2 | eu-west-1 | B6 | late? |
|   rn-north-19533  | 3 | ca-north-8 | B6 |  |
|   rn-north-19533  | 4 | eu-west-1 | B6 |  |
|   rn-north-19533  | 5 | eu-west-1 | B6 |  |
|   rn-north-19559  | 1 | ca-north-8 | B6 |  |
|   rn-north-19559  | 2 | ca-north-8 | B6 |  |
|   rn-north-19559  | 3 | ca-north-8 | B6 | void? |
|   rn-north-19559  | 4 | ca-north-8 | B6 |  |
|   rn-north-19559  | 5 | ca-north-8 | B6 | late? |
|   rn-north-19588  | 1 | eu-west-1 | B6 | recheck |
|   rn-north-19588  | 2 | eu-west-1 | B6 |  |
|   rn-north-19588  | 3 | eu-west-1 | B6 | late? |
|   rn-north-19588  | 4 | eu-west-1 | B6 |  |
|   rn-north-19588  | 5 | eu-west-1 | B6 |  |
|   rn-north-19617  | 1 | ca-north-8 | B6 |  |
|   rn-north-19617  | 2 | ca-north-8 | B6 |  |
|   rn-north-19617  | 3 | ca-north-8 | B6 | late? |
|   rn-north-19617  | 4 | eu-west-1 | B6 |  |
|   rn-north-19617  | 5 | ca-north-8 | B6 |  |
|   rn-north-19644  | 1 | eu-west-1 | B6 | recheck |
|   rn-north-19644  | 2 | eu-west-1 | B6 |  |
|   rn-north-19644  | 3 | eu-west-1 | B6 |  |
|   rn-north-19644  | 4 | eu-west-1 | B6 |  |
|   rn-north-19644  | 5 | eu-west-1 | B6 |  |
|   rn-north-19668  | 1 | ca-north-8 | B6 |  |
|   rn-north-19668  | 2 | ca-north-8 | B6 |  |
|   rn-north-19668  | 2 | ca-north-8 | B6 |  |
|   rn-north-19668  | 3 | ca-north-8 | B6 |  |
|   rn-north-19668  | 4 | ca-north-8 | B6 |  |
|   rn-north-19668  | 5 | ca-north-8 | B6 |  |
|   rn-north-19696  | 1 | eu-west-1 | B6 |  |
|   rn-north-19696  | 2 | ca-north-8 | B6 |  |
|   rn-north-19696  | 2 | ca-north-8 | B6 |  |
|   rn-north-19696  | 3 | eu-west-1 | B6 | late? |
|   rn-north-19696  | 4 | eu-west-1 | B6 |  |
|   rn-north-19696  | 5 | eu-west-1 | B6 |  |
|   rn-north-19728  | 1 | ca-north-8 | B6 |  |
|   rn-north-19728  | 2 | eu-west-1 | B6 | recheck |
|   rn-north-19728  | 3 | ca-north-8 | B6 |  |
|   rn-north-19728  | 4 | ca-north-8 | B6 | recheck |
|   rn-north-19728  | 5 | ca-north-8 | B6 |  |
|   rn-north-19755  | 1 | eu-west-1 | B6 |  |
|   rn-north-19755  | 2 | eu-west-1 | B6 |  |
|   rn-north-19755  | 3 | eu-west-1 | B6 |  |
|   rn-north-19755  | 4 | eu-west-1 | B6 |  |
|   rn-north-19755  | 5 | eu-west-1 | B6 |  |
|   rn-north-19780  | 1 | ca-north-8 | B6 |  |
|   rn-north-19780  | 2 | ca-north-8 | B6 |  |
|   rn-north-19780  | 3 | ca-north-8 | B6 |  |
|   rn-north-19780  | 4 | ca-north-8 | B6 |  |
|   rn-north-19780  | 5 | ca-north-8 | B6 | recheck |
|   rn-north-19810  | 1 | eu-west-1 | B6 |  |
|   rn-north-19810  | 2 | eu-west-1 | B6 | late? |
|   rn-north-19810  | 3 | eu-west-1 | B6 |  |
|   rn-north-19810  | 4 | ca-north-8 | B6 | recheck |
|   rn-north-19810  | 5 | eu-west-1 | B6 |  |
|   rn-north-19838  | 1 | ca-north-8 | B6 | void? |
|   rn-north-19838  | 2 | ca-north-8 | B6 | recheck |
|   rn-north-19838  | 3 | ca-north-8 | B6 | recheck |
|   rn-north-19838  | 4 | ca-north-8 | B6 |  |
|   rn-north-19838  | 5 | ca-north-8 | B6 |  |
|   rn-north-19863  | 1 | eu-west-1 | B6 |  |
|   rn-north-19863  | 2 | eu-west-1 | B6 |  |
|   rn-north-19863  | 3 | eu-west-1 | B6 | dup? |
|   rn-north-19863  | 4 | eu-west-1 | B6 |  |
|   rn-north-19863  | 5 | eu-west-1 | B6 | late? |
|   rn-north-19897  | 1 | ca-north-8 | B6 |  |
|   rn-north-19897  | 2 | ca-north-8 | B6 |  |
|   rn-north-19897  | 3 | ca-north-8 | B6 |  |
|   rn-north-19897  | 4 | ca-north-8 | B6 |  |
|   rn-north-19897  | 5 | ca-north-8 | B6 |  |
|   rn-north-19920  | 1 | eu-west-1 | B6 |  |
|   rn-north-19920  | 2 | eu-west-1 | B6 | void? |
|   rn-north-19920  | 3 | eu-west-1 | B6 |  |
|   rn-north-19920  | 4 | eu-west-1 | B6 |  |
|   rn-north-19920  | 5 | eu-west-1 | B6 |  |
|   rn-north-19947  | 1 | ca-north-8 | B6 |  |
|   rn-north-19947  | 2 | ca-north-8 | B6 |  |
|   rn-north-19947  | 3 | ca-north-8 | B6 | void? |
|   rn-north-19947  | 4 | ca-north-8 | B6 |  |
|   rn-north-19947  | 5 | ca-north-8 | B6 |  |
|   rn-north-19981  | 1 | eu-west-1 | B6 | void? |
|   rn-north-19981  | 2 | eu-west-1 | B6 |  |
|   rn-north-19981  | 3 | eu-west-1 | B6 |  |
|   rn-north-19981  | 4 | eu-west-1 | B6 |  |
|   rn-north-19981  | 5 | eu-west-1 | B6 |  |
|   rn-north-20004  | 1 | ca-north-8 | B6 |  |
|   rn-north-20004  | 2 | ca-north-8 | B6 |  |
|   rn-north-20004  | 3 | ca-north-8 | B6 |  |
|   rn-north-20004  | 4 | eu-west-1 | B6 |  |
|   rn-north-20004  | 5 | ca-north-8 | B6 |  |
|   rn-north-20036  | 1 | eu-west-1 | B6 |  |
|   rn-north-20036  | 2 | eu-west-1 | B6 |  |
|   rn-north-20036  | 3 | eu-west-1 | B6 |  |
|   rn-north-20036  | 4 | eu-west-1 | B6 | recheck |
|   rn-north-20036  | 5 | eu-west-1 | B6 |  |
|   rn-north-20062  | 1 | ca-north-8 | B6 |  |
|   rn-north-20062  | 2 | ca-north-8 | B6 |  |
|   rn-north-20062  | 3 | ca-north-8 | B6 | recheck |
|   rn-north-20062  | 4 | ca-north-8 | B6 | dup? |
|   rn-north-20062  | 5 | ca-north-8 | B6 |  |
|   rn-north-20091  | 1 | eu-west-1 | B6 |  |
|   rn-north-20091  | 2 | eu-west-1 | B6 |  |
|   rn-north-20091  | 3 | eu-west-1 | B6 |  |
|   rn-north-20091  | 4 | eu-west-1 | B6 |  |
|   rn-north-20091  | 5 | eu-west-1 | B6 |  |
|   rn-north-20116  | 1 | ca-north-8 | B6 |  |
|   rn-north-20116  | 2 | ca-north-8 | B6 |  |
|   rn-north-20116  | 3 | ca-north-8 | B6 |  |
|   rn-north-20116  | 4 | ca-north-8 | B6 |  |
|   rn-north-20116  | 5 | ca-north-8 | B6 | recheck |
|   rn-north-20145  | 1 | eu-west-1 | B6 |  |
|   rn-north-20145  | 2 | eu-west-1 | B6 |  |
|   rn-north-20145  | 3 | eu-west-1 | B6 |  |
|   rn-north-20145  | 4 | eu-west-1 | B6 |  |
|   rn-north-20145  | 5 | eu-west-1 | B6 |  |
|   rn-north-20177  | 1 | ca-north-8 | B6 |  |
|   rn-north-20177  | 2 | ca-north-8 | B6 | dup? |
|   rn-north-20177  | 3 | ca-north-8 | B6 |  |
|   rn-north-20177  | 4 | ca-north-8 | B6 |  |
|   rn-north-20177  | 5 | ca-north-8 | B6 |  |
|   rn-north-20204  | 1 | eu-west-1 | B6 |  |
|   rn-north-20204  | 2 | eu-west-1 | B6 |  |
|   rn-north-20204  | 3 | eu-west-1 | B6 | late? |
|   rn-north-20204  | 4 | eu-west-1 | B6 |  |
|   rn-north-20204  | 5 | eu-west-1 | B6 |  |
|   rn-north-20231  | 1 | ca-north-8 | B6 |  |
|   rn-north-20231  | 2 | ca-north-8 | B6 |  |
|   rn-north-20231  | 3 | ca-north-8 | B6 |  |
|   rn-north-20231  | 4 | ca-north-8 | B6 |  |
|   rn-north-20231  | 5 | ca-north-8 | B6 |  |
|   rn-north-20257  | 1 | eu-west-1 | B6 |  |
|   rn-north-20257  | 2 | eu-west-1 | B6 |  |
|   rn-north-20257  | 3 | eu-west-1 | B6 |  |
|   rn-north-20257  | 4 | eu-west-1 | B6 | late? |
|   rn-north-20257  | 5 | eu-west-1 | B6 |  |
|   rn-north-20288  | 1 | ca-north-8 | B6 |  |
|   rn-north-20288  | 2 | ca-north-8 | B6 |  |
|   rn-north-20288  | 3 | ca-north-8 | B6 | late? |
|   rn-north-20288  | 4 | ca-north-8 | B6 |  |
|   rn-north-20288  | 5 | ca-north-8 | B6 |  |
|   rn-north-20315  | 1 | eu-west-1 | B6 |  |
|   rn-north-20315  | 2 | eu-west-1 | B6 |  |
|   rn-north-20315  | 3 | eu-west-1 | B6 |  |
|   rn-north-20315  | 4 | eu-west-1 | B6 |  |
|   rn-north-20315  | 5 | eu-west-1 | B6 |  |
|   rn-north-20339  | 1 | ca-north-8 | B6 |  |
|   rn-north-20339  | 2 | ca-north-8 | B6 |  |
|   rn-north-20339  | 3 | ca-north-8 | B6 |  |
|   rn-north-20339  | 4 | ca-north-8 | B6 |  |
|   rn-north-20339  | 4 | ca-north-8 | B6 |  |
|   rn-north-20339  | 5 | ca-north-8 | B6 |  |
|   rn-north-20372  | 1 | eu-west-1 | B6 | dup? |
|   rn-north-20372  | 2 | eu-west-1 | B6 |  |
|   rn-north-20372  | 3 | eu-west-1 | B6 |  |
|   rn-north-20372  | 4 | eu-west-1 | B6 |  |
|   rn-north-20372  | 5 | eu-west-1 | B6 |  |
|   rn-north-20400  | 1 | ca-north-8 | B6 |  |
|   rn-north-20400  | 2 | ca-north-8 | B6 |  |
|   rn-north-20400  | 3 | ca-north-8 | B6 |  |
|   rn-north-20400  | 4 | ca-north-8 | B6 | dup? |
|   rn-north-20400  | 5 | ca-north-8 | B6 |  |
|   rn-north-20424  | 1 | eu-west-1 | B6 |  |
|   rn-north-20424  | 1 | eu-west-1 | B6 |  |
|   rn-north-20424  | 2 | eu-west-1 | B6 |  |
|   rn-north-20424  | 3 | eu-west-1 | B6 |  |
|   rn-north-20424  | 4 | eu-west-1 | B6 |  |
|   rn-north-20424  | 5 | eu-west-1 | B6 |  |
|   rn-north-20452  | 1 | ca-north-8 | B6 |  |
|   rn-north-20452  | 2 | ca-north-8 | B6 |  |
|   rn-north-20452  | 2 | ca-north-8 | B6 |  |
|   rn-north-20452  | 3 | ca-north-8 | B6 |  |
|   rn-north-20452  | 4 | ca-north-8 | B6 | late? |
|   rn-north-20452  | 5 | ca-north-8 | B6 |  |
|   rn-north-20482  | 1 | eu-west-1 | B6 |  |
|   rn-north-20482  | 2 | eu-west-1 | B6 |  |
|   rn-north-20482  | 3 | eu-west-1 | B6 |  |
|   rn-north-20482  | 4 | eu-west-1 | B6 |  |
|   rn-north-20482  | 5 | eu-west-1 | B6 |  |
|   rn-north-20508  | 1 | ca-north-8 | B6 |  |
|   rn-north-20508  | 2 | ca-north-8 | B6 | late? |
|   rn-north-20508  | 3 | ca-north-8 | B6 |  |
|   rn-north-20508  | 4 | ca-north-8 | B6 |  |
|   rn-north-20508  | 5 | ca-north-8 | B6 | void? |
|   rn-north-20537  | 1 | eu-west-1 | B6 |  |
|   rn-north-20537  | 2 | eu-west-1 | B6 |  |
|   rn-north-20537  | 3 | eu-west-1 | B6 |  |
|   rn-north-20537  | 4 | eu-west-1 | B6 |  |
|   rn-north-20537  | 5 | eu-west-1 | B6 |  |
|   rn-north-20567  | 1 | ca-north-8 | B6 |  |
|   rn-north-20567  | 2 | eu-west-1 | B6 |  |
|   rn-north-20567  | 3 | ca-north-8 | B6 |  |
|   rn-north-20567  | 4 | ca-north-8 | B6 |  |
|   rn-north-20567  | 5 | ca-north-8 | B6 |  |
|   rn-north-20595  | 1 | eu-west-1 | B6 |  |
|   rn-north-20595  | 2 | eu-west-1 | B6 |  |
|   rn-north-20595  | 3 | eu-west-1 | B6 |  |
|   rn-north-20595  | 4 | eu-west-1 | B6 |  |
|   rn-north-20595  | 5 | eu-west-1 | B6 |  |
|   rn-north-20623  | 1 | ca-north-8 | B6 |  |
|   rn-north-20623  | 2 | ca-north-8 | B6 |  |
|   rn-north-20623  | 3 | ca-north-8 | B6 |  |
|   rn-north-20623  | 4 | ca-north-8 | B6 |  |
|   rn-north-20623  | 5 | ca-north-8 | B6 |  |
|   rn-north-20649  | 1 | eu-west-1 | B6 |  |
|   rn-north-20649  | 2 | eu-west-1 | B6 |  |
|   rn-north-20649  | 3 | eu-west-1 | B6 |  |
|   rn-north-20649  | 4 | eu-west-1 | B6 | void? |
|   rn-north-20649  | 5 | ca-north-8 | B6 | late? |
|   rn-north-20649  | 5 | ca-north-8 | B6 | late? |
|   rn-north-20679  | 1 | ca-north-8 | B6 |  |
|   rn-north-20679  | 2 | ca-north-8 | B6 |  |
|   rn-north-20679  | 3 | ca-north-8 | B6 |  |
|   rn-north-20679  | 4 | ca-north-8 | B6 |  |
|   rn-north-20679  | 5 | ca-north-8 | B6 |  |
|   rn-north-20704  | 1 | eu-west-1 | B6 |  |
|   rn-north-20704  | 2 | eu-west-1 | B6 |  |
|   rn-north-20704  | 3 | eu-west-1 | B6 |  |
|   rn-north-20704  | 4 | eu-west-1 | B6 |  |
|   rn-north-20704  | 5 | eu-west-1 | B6 |  |
|   rn-north-20732  | 1 | ca-north-8 | B6 |  |
|   rn-north-20732  | 2 | ca-north-8 | B6 |  |
|   rn-north-20732  | 3 | ca-north-8 | B6 |  |
|   rn-north-20732  | 4 | ca-north-8 | B6 |  |
|   rn-north-20732  | 5 | ca-north-8 | B6 |  |
|   rn-north-20762  | 1 | eu-west-1 | B6 | late? |
|   rn-north-20762  | 2 | eu-west-1 | B6 |  |
|   rn-north-20762  | 3 | eu-west-1 | B6 |  |
|   rn-north-20762  | 4 | eu-west-1 | B6 |  |
|   rn-north-20762  | 5 | eu-west-1 | B6 |  |
|   rn-north-20787  | 1 | ca-north-8 | B6 | late? |
|   rn-north-20787  | 2 | ca-north-8 | B6 |  |
|   rn-north-20787  | 3 | ca-north-8 | B6 |  |
|   rn-north-20787  | 4 | ca-north-8 | B6 |  |
|   rn-north-20787  | 5 | ca-north-8 | B6 |  |
|   rn-north-20821  | 1 | eu-west-1 | B6 |  |
|   rn-north-20821  | 2 | eu-west-1 | B6 |  |
|   rn-north-20821  | 3 | eu-west-1 | B6 |  |
|   rn-north-20821  | 4 | eu-west-1 | B6 |  |
|   rn-north-20821  | 5 | eu-west-1 | B6 |  |
|   rn-north-20843  | 1 | ca-north-8 | B6 |  |
|   rn-north-20843  | 2 | eu-west-1 | B6 |  |
|   rn-north-20843  | 3 | ca-north-8 | B6 |  |
|   rn-north-20843  | 4 | ca-north-8 | B6 |  |
|   rn-north-20843  | 5 | ca-north-8 | B6 |  |
|   rn-north-20877  | 1 | eu-west-1 | B6 |  |
|   rn-north-20877  | 2 | eu-west-1 | B6 |  |
|   rn-north-20877  | 3 | eu-west-1 | B6 |  |
|   rn-north-20877  | 4 | eu-west-1 | B6 |  |
|   rn-north-20877  | 5 | eu-west-1 | B6 |  |
|   rn-north-20904  | 1 | ca-north-8 | B6 |  |
|   rn-north-20904  | 2 | ca-north-8 | B6 |  |
|   rn-north-20904  | 3 | ca-north-8 | B6 |  |
|   rn-north-20904  | 4 | ca-north-8 | B6 |  |
|   rn-north-20904  | 5 | ca-north-8 | B6 |  |
|   rn-north-20932  | 1 | eu-west-1 | B6 | late? |
|   rn-north-20932  | 2 | eu-west-1 | B6 | void? |
|   rn-north-20932  | 3 | eu-west-1 | B6 | recheck |
|   rn-north-20932  | 4 | eu-west-1 | B6 |  |
|   rn-north-20932  | 5 | eu-west-1 | B6 | void? |
|   rn-north-20959  | 1 | ca-north-8 | B6 | void? |
|   rn-north-20959  | 2 | ca-north-8 | B6 | void? |
|   rn-north-20959  | 3 | ca-north-8 | B6 |  |
|   rn-north-20959  | 4 | ca-north-8 | B6 |  |
|   rn-north-20959  | 5 | ca-north-8 | B6 |  |
|   rn-north-20984  | 1 | eu-west-1 | B6 |  |
|   rn-north-20984  | 2 | eu-west-1 | B6 |  |
|   rn-north-20984  | 3 | eu-west-1 | B6 | late? |
|   rn-north-20984  | 4 | eu-west-1 | B6 |  |
|   rn-north-20984  | 4 | eu-west-1 | B6 |  |
|   rn-north-20984  | 5 | eu-west-1 | B6 |  |
|   rn-north-21014  | 1 | ca-north-8 | B6 |  |
|   rn-north-21014  | 2 | ca-north-8 | B6 |  |
|   rn-north-21014  | 3 | ca-north-8 | B6 |  |
|   rn-north-21014  | 4 | ca-north-8 | B6 |  |
|   rn-north-21014  | 5 | ca-north-8 | B6 |  |
|   rn-north-21044  | 1 | eu-west-1 | B6 | void? |
|   rn-north-21044  | 2 | eu-west-1 | B6 |  |
|   rn-north-21044  | 3 | eu-west-1 | B6 | dup? |
|   rn-north-21044  | 4 | eu-west-1 | B6 |  |
|   rn-north-21044  | 5 | eu-west-1 | B6 | dup? |
|   rn-north-21070  | 1 | ca-north-8 | B6 |  |
|   rn-north-21070  | 2 | ca-north-8 | B6 |  |
|   rn-north-21070  | 3 | eu-west-1 | B6 |  |
|   rn-north-21070  | 4 | ca-north-8 | B6 | late? |
|   rn-north-21070  | 5 | ca-north-8 | B6 |  |
|   rn-north-21095  | 1 | eu-west-1 | B6 |  |
|   rn-north-21095  | 2 | eu-west-1 | B6 | late? |
|   rn-north-21095  | 3 | eu-west-1 | B6 |  |
|   rn-north-21095  | 4 | eu-west-1 | B6 |  |
|   rn-north-21095  | 5 | eu-west-1 | B6 |  |
|   rn-north-21125  | 1 | ca-north-8 | B6 |  |
|   rn-north-21125  | 2 | ca-north-8 | B6 |  |
|   rn-north-21125  | 3 | ca-north-8 | B6 |  |
|   rn-north-21125  | 4 | ca-north-8 | B6 |  |
|   rn-north-21125  | 5 | ca-north-8 | B6 |  |
|   rn-north-21155  | 1 | eu-west-1 | B6 |  |
|   rn-north-21155  | 2 | eu-west-1 | B6 |  |
|   rn-north-21155  | 3 | eu-west-1 | B6 |  |
|   rn-north-21155  | 4 | eu-west-1 | B6 |  |
|   rn-north-21155  | 5 | eu-west-1 | B6 |  |
|   rn-north-21181  | 1 | ca-north-8 | B6 |  |
|   rn-north-21181  | 2 | eu-west-1 | B6 |  |
|   rn-north-21181  | 3 | ca-north-8 | B6 |  |
|   rn-north-21181  | 4 | eu-west-1 | B6 | void? |
|   rn-north-21181  | 5 | ca-north-8 | B6 |  |
|   rn-north-21213  | 1 | eu-west-1 | B6 |  |
|   rn-north-21213  | 2 | eu-west-1 | B6 |  |
|   rn-north-21213  | 3 | eu-west-1 | B6 |  |
|   rn-north-21213  | 4 | eu-west-1 | B6 |  |
|   rn-north-21213  | 5 | eu-west-1 | B6 |  |
|   rn-north-21240  | 1 | ca-north-8 | B6 |  |
|   rn-north-21240  | 2 | ca-north-8 | B6 |  |
|   rn-north-21240  | 3 | ca-north-8 | B6 |  |
|   rn-north-21240  | 3 | ca-north-8 | B6 |  |
|   rn-north-21240  | 4 | ca-north-8 | B6 |  |
|   rn-north-21240  | 5 | ca-north-8 | B6 | dup? |
|   rn-north-21264  | 1 | eu-west-1 | B6 |  |
|   rn-north-21264  | 2 | eu-west-1 | B6 |  |
|   rn-north-21264  | 3 | eu-west-1 | B6 |  |
|   rn-north-21264  | 4 | eu-west-1 | B6 |  |
|   rn-north-21264  | 5 | eu-west-1 | B6 |  |
|   rn-north-21291  | 1 | ca-north-8 | B6 |  |
|   rn-north-21291  | 2 | ca-north-8 | B6 |  |
|   rn-north-21291  | 3 | ca-north-8 | B6 |  |
|   rn-north-21291  | 4 | ca-north-8 | B6 | void? |
|   rn-north-21291  | 5 | ca-north-8 | B6 | late? |
|   rn-north-21323  | 1 | eu-west-1 | B6 |  |
|   rn-north-21323  | 2 | eu-west-1 | B6 |  |
|   rn-north-21323  | 3 | eu-west-1 | B6 |  |
|   rn-north-21323  | 4 | eu-west-1 | B6 |  |
|   rn-north-21323  | 5 | eu-west-1 | B6 |  |
|   rn-north-21353  | 1 | ca-north-8 | B6 |  |
|   rn-north-21353  | 2 | ca-north-8 | B6 |  |
|   rn-north-21353  | 3 | ca-north-8 | B6 |  |
|   rn-north-21353  | 4 | ca-north-8 | B6 |  |
|   rn-north-21353  | 5 | ca-north-8 | B6 | late? |
|   rn-north-21376  | 1 | eu-west-1 | B6 |  |
|   rn-north-21376  | 2 | eu-west-1 | B6 |  |
|   rn-north-21376  | 3 | eu-west-1 | B6 | recheck |
|   rn-north-21376  | 3 | eu-west-1 | B6 | recheck |
|   rn-north-21376  | 4 | eu-west-1 | B6 |  |
|   rn-north-21376  | 5 | eu-west-1 | B6 | late? |
|   rn-north-21407  | 1 | ca-north-8 | B6 | recheck |
|   rn-north-21407  | 2 | ca-north-8 | B6 |  |
|   rn-north-21407  | 3 | ca-north-8 | B6 |  |
|   rn-north-21407  | 4 | ca-north-8 | B6 |  |
|   rn-north-21407  | 5 | ca-north-8 | B6 |  |
|   rn-north-21434  | 1 | eu-west-1 | B6 |  |
|   rn-north-21434  | 2 | eu-west-1 | B6 |  |
|   rn-north-21434  | 3 | eu-west-1 | B6 |  |
|   rn-north-21434  | 4 | eu-west-1 | B6 |  |
|   rn-north-21434  | 5 | eu-west-1 | B6 | void? |
|   rn-north-21462  | 1 | ca-north-8 | B6 |  |
|   rn-north-21462  | 2 | ca-north-8 | B6 |  |
|   rn-north-21462  | 3 | ca-north-8 | B6 |  |
|   rn-north-21462  | 4 | ca-north-8 | B6 |  |
|   rn-north-21462  | 5 | ca-north-8 | B6 |  |
|   rn-north-21488  | 1 | eu-west-1 | B6 | void? |
|   rn-north-21488  | 2 | eu-west-1 | B6 |  |
|   rn-north-21488  | 3 | eu-west-1 | B6 |  |
|   rn-north-21488  | 4 | eu-west-1 | B6 | late? |
|   rn-north-21488  | 5 | eu-west-1 | B6 |  |
|   rn-north-21519  | 1 | ca-north-8 | B6 |  |
|   rn-north-21519  | 2 | ca-north-8 | B6 |  |
|   rn-north-21519  | 3 | ca-north-8 | B6 |  |
|   rn-north-21519  | 4 | ca-north-8 | B6 |  |
|   rn-north-21519  | 5 | ca-north-8 | B6 | dup? |
|   rn-north-21544  | 1 | eu-west-1 | B6 |  |
|   rn-north-21544  | 2 | eu-west-1 | B6 | recheck |
|   rn-north-21544  | 3 | eu-west-1 | B6 |  |
|   rn-north-21544  | 4 | eu-west-1 | B6 | late? |
|   rn-north-21544  | 5 | eu-west-1 | B6 |  |
|   rn-north-21577  | 1 | ca-north-8 | B6 |  |
|   rn-north-21577  | 2 | ca-north-8 | B6 | dup? |
|   rn-north-21577  | 3 | ca-north-8 | B6 | void? |
|   rn-north-21577  | 4 | ca-north-8 | B6 |  |
|   rn-north-21577  | 5 | ca-north-8 | B6 |  |
|   rn-north-21601  | 1 | eu-west-1 | B6 |  |
|   rn-north-21601  | 2 | eu-west-1 | B6 |  |
|   rn-north-21601  | 3 | eu-west-1 | B6 | dup? |
|   rn-north-21601  | 3 | eu-west-1 | B6 | dup? |
|   rn-north-21601  | 4 | ca-north-8 | B6 |  |
|   rn-north-21601  | 5 | eu-west-1 | B6 | void? |
|   rn-north-21631  | 1 | ca-north-8 | B6 |  |
|   rn-north-21631  | 2 | ca-north-8 | B6 |  |
|   rn-north-21631  | 3 | ca-north-8 | B6 | dup? |
|   rn-north-21631  | 4 | ca-north-8 | B6 |  |
|   rn-north-21631  | 5 | ca-north-8 | B6 |  |
|   rn-north-21656  | 1 | eu-west-1 | B6 |  |
|   rn-north-21656  | 2 | eu-west-1 | B6 |  |
|   rn-north-21656  | 3 | eu-west-1 | B6 |  |
|   rn-north-21656  | 4 | eu-west-1 | B6 |  |
|   rn-north-21656  | 5 | eu-west-1 | B6 |  |
|   rn-north-21687  | 1 | ca-north-8 | B6 | dup? |
|   rn-north-21687  | 2 | ca-north-8 | B6 |  |
|   rn-north-21687  | 3 | ca-north-8 | B6 |  |
|   rn-north-21687  | 4 | ca-north-8 | B6 | void? |
|   rn-north-21687  | 5 | ca-north-8 | B6 |  |
|   rn-north-21712  | 1 | eu-west-1 | B6 |  |
|   rn-north-21712  | 2 | eu-west-1 | B6 |  |
|   rn-north-21712  | 3 | eu-west-1 | B6 |  |
|   rn-north-21712  | 4 | eu-west-1 | B6 |  |
|   rn-north-21712  | 5 | eu-west-1 | B6 |  |
|   rn-north-21740  | 1 | ca-north-8 | B6 |  |
|   rn-north-21740  | 2 | ca-north-8 | B6 |  |
|   rn-north-21740  | 3 | ca-north-8 | B6 |  |
|   rn-north-21740  | 4 | ca-north-8 | B6 |  |
|   rn-north-21740  | 5 | ca-north-8 | B6 | void? |
|   rn-north-21773  | 1 | eu-west-1 | B6 |  |
|   rn-north-21773  | 2 | eu-west-1 | B6 |  |
|   rn-north-21773  | 3 | eu-west-1 | B6 | void? |
|   rn-north-21773  | 4 | eu-west-1 | B6 |  |
|   rn-north-21773  | 5 | ca-north-8 | B6 |  |
|   rn-north-21801  | 1 | ca-north-8 | B6 |  |
|   rn-north-21801  | 2 | ca-north-8 | B6 |  |
|   rn-north-21801  | 3 | ca-north-8 | B6 | dup? |
|   rn-north-21801  | 4 | ca-north-8 | B6 |  |
|   rn-north-21801  | 5 | ca-north-8 | B6 |  |
|   rn-north-21829  | 1 | eu-west-1 | B6 |  |
|   rn-north-21829  | 2 | eu-west-1 | B6 |  |
|   rn-north-21829  | 3 | eu-west-1 | B6 |  |
|   rn-north-21829  | 4 | ca-north-8 | B6 |  |
|   rn-north-21829  | 5 | eu-west-1 | B6 |  |
|   rn-north-21857  | 1 | ca-north-8 | B6 |  |
|   rn-north-21857  | 2 | ca-north-8 | B6 |  |
|   rn-north-21857  | 3 | ca-north-8 | B6 |  |
|   rn-north-21857  | 4 | ca-north-8 | B6 |  |
|   rn-north-21857  | 4 | ca-north-8 | B6 |  |
|   rn-north-21857  | 5 | ca-north-8 | B6 |  |
|   rn-north-21879  | 1 | eu-west-1 | B6 |  |
|   rn-north-21879  | 2 | eu-west-1 | B6 |  |
|   rn-north-21879  | 3 | eu-west-1 | B6 |  |
|   rn-north-21879  | 4 | eu-west-1 | B6 |  |
|   rn-north-21879  | 5 | eu-west-1 | B6 |  |
|   rn-north-21913  | 1 | ca-north-8 | B6 |  |
|   rn-north-21913  | 2 | ca-north-8 | B6 |  |
|   rn-north-21913  | 3 | ca-north-8 | B6 | recheck |
|   rn-north-21913  | 4 | ca-north-8 | B6 | late? |
|   rn-north-21913  | 5 | ca-north-8 | B6 | recheck |
|   rn-north-21935  | 1 | eu-west-1 | B6 |  |
|   rn-north-21935  | 2 | eu-west-1 | B6 |  |
|   rn-north-21935  | 3 | eu-west-1 | B6 |  |
|   rn-north-21935  | 4 | eu-west-1 | B6 |  |
|   rn-north-21935  | 5 | eu-west-1 | B6 |  |
|   rn-north-21964  | 1 | ca-north-8 | B6 |  |
|   rn-north-21964  | 2 | ca-north-8 | B6 |  |
|   rn-north-21964  | 2 | ca-north-8 | B6 |  |
|   rn-north-21964  | 3 | ca-north-8 | B6 |  |
|   rn-north-21964  | 4 | ca-north-8 | B6 |  |
|   rn-north-21964  | 5 | ca-north-8 | B6 |  |
|   rn-north-21993  | 1 | eu-west-1 | B6 |  |
|   rn-north-21993  | 2 | eu-west-1 | B6 |  |
|   rn-north-21993  | 3 | eu-west-1 | B6 |  |
|   rn-north-21993  | 4 | eu-west-1 | B6 |  |
|   rn-north-21993  | 5 | eu-west-1 | B6 |  |
|   rn-north-22019  | 1 | ca-north-8 | B6 | late? |
|   rn-north-22019  | 1 | ca-north-8 | B6 | late? |
|   rn-north-22019  | 2 | ca-north-8 | B6 |  |
|   rn-north-22019  | 3 | ca-north-8 | B6 |  |
|   rn-north-22019  | 4 | ca-north-8 | B6 | late? |
|   rn-north-22019  | 5 | ca-north-8 | B6 |  |
|   rn-north-22053  | 1 | eu-west-1 | B6 |  |
|   rn-north-22053  | 2 | eu-west-1 | B6 |  |
|   rn-north-22053  | 3 | eu-west-1 | B6 |  |
|   rn-north-22053  | 4 | eu-west-1 | B6 |  |
|   rn-north-22053  | 5 | eu-west-1 | B6 |  |
|   rn-north-22075  | 1 | ca-north-8 | B6 |  |
|   rn-north-22075  | 2 | ca-north-8 | B6 |  |
|   rn-north-22075  | 3 | ca-north-8 | B6 | void? |
|   rn-north-22075  | 4 | ca-north-8 | B6 |  |
|   rn-north-22075  | 5 | ca-north-8 | B6 | dup? |
|   rn-north-22107  | 1 | eu-west-1 | B6 |  |
|   rn-north-22107  | 2 | eu-west-1 | B6 |  |
|   rn-north-22107  | 3 | ca-north-8 | B6 |  |
|   rn-north-22107  | 4 | eu-west-1 | B6 |  |
|   rn-north-22107  | 5 | eu-west-1 | B6 | dup? |
|   rn-north-22137  | 1 | ca-north-8 | B6 |  |
|   rn-north-22137  | 2 | ca-north-8 | B6 |  |
|   rn-north-22137  | 3 | ca-north-8 | B6 | void? |
|   rn-north-22137  | 4 | ca-north-8 | B6 | dup? |
|   rn-north-22137  | 5 | ca-north-8 | B6 |  |
|   rn-north-22160  | 1 | eu-west-1 | B6 | dup? |
|   rn-north-22160  | 2 | eu-west-1 | B6 |  |
|   rn-north-22160  | 3 | eu-west-1 | B6 |  |
|   rn-north-22160  | 4 | eu-west-1 | B6 |  |
|   rn-north-22160  | 5 | eu-west-1 | B6 |  |
|   rn-north-22191  | 1 | ca-north-8 | B6 | dup? |
|   rn-north-22191  | 2 | ca-north-8 | B6 |  |
|   rn-north-22191  | 3 | ca-north-8 | B6 |  |
|   rn-north-22191  | 4 | ca-north-8 | B6 | dup? |
|   rn-north-22191  | 5 | ca-north-8 | B6 |  |
|   rn-north-22218  | 1 | eu-west-1 | B6 |  |
|   rn-north-22218  | 2 | eu-west-1 | B6 |  |
|   rn-north-22218  | 3 | eu-west-1 | B6 |  |
|   rn-north-22218  | 4 | eu-west-1 | B6 |  |
|   rn-north-22218  | 5 | eu-west-1 | B6 | late? |
|   rn-north-22244  | 1 | ca-north-8 | B6 |  |
|   rn-north-22244  | 2 | ca-north-8 | B6 |  |
|   rn-north-22244  | 3 | ca-north-8 | B6 |  |
|   rn-north-22244  | 4 | ca-north-8 | B6 | dup? |
|   rn-north-22244  | 5 | ca-north-8 | B6 |  |
|   rn-north-22274  | 1 | eu-west-1 | B6 |  |
|   rn-north-22274  | 2 | eu-west-1 | B6 |  |
|   rn-north-22274  | 3 | eu-west-1 | B6 |  |
|   rn-north-22274  | 4 | eu-west-1 | B6 |  |
|   rn-north-22274  | 5 | eu-west-1 | B6 |  |
|   rn-north-22299  | 1 | ca-north-8 | B6 |  |
|   rn-north-22299  | 2 | ca-north-8 | B6 |  |
|   rn-north-22299  | 3 | ca-north-8 | B6 |  |
|   rn-north-22299  | 4 | ca-north-8 | B6 | void? |
|   rn-north-22299  | 5 | ca-north-8 | B6 |  |
|   rn-north-22332  | 1 | eu-west-1 | B6 |  |
|   rn-north-22332  | 2 | eu-west-1 | B6 |  |
|   rn-north-22332  | 3 | eu-west-1 | B6 |  |
|   rn-north-22332  | 4 | eu-west-1 | B6 |  |
|   rn-north-22332  | 5 | eu-west-1 | B6 |  |
|   rn-north-22356  | 1 | ca-north-8 | B6 |  |
|   rn-north-22356  | 2 | ca-north-8 | B6 |  |
|   rn-north-22356  | 3 | ca-north-8 | B6 | void? |
|   rn-north-22356  | 4 | ca-north-8 | B6 |  |
|   rn-north-22356  | 5 | ca-north-8 | B6 |  |
|   rn-north-22387  | 1 | eu-west-1 | B6 |  |
|   rn-north-22387  | 2 | eu-west-1 | B6 |  |
|   rn-north-22387  | 3 | eu-west-1 | B6 | dup? |
|   rn-north-22387  | 4 | eu-west-1 | B6 | late? |
|   rn-north-22387  | 5 | eu-west-1 | B6 |  |
|   rn-north-22412  | 1 | ca-north-8 | B6 |  |
|   rn-north-22412  | 1 | ca-north-8 | B6 |  |
|   rn-north-22412  | 2 | ca-north-8 | B6 |  |
|   rn-north-22412  | 3 | ca-north-8 | B6 |  |
|   rn-north-22412  | 4 | eu-west-1 | B6 | late? |
|   rn-north-22412  | 5 | ca-north-8 | B6 |  |
|   rn-north-22439  | 1 | eu-west-1 | B6 | void? |
|   rn-north-22439  | 2 | eu-west-1 | B6 | late? |
|   rn-north-22439  | 3 | eu-west-1 | B6 | dup? |
|   rn-north-22439  | 4 | eu-west-1 | B6 |  |
|   rn-north-22439  | 5 | eu-west-1 | B6 |  |
|   rn-north-22473  | 1 | ca-north-8 | B6 | recheck |
|   rn-north-22473  | 2 | ca-north-8 | B6 |  |
|   rn-north-22473  | 3 | ca-north-8 | B6 | void? |
|   rn-north-22473  | 4 | ca-north-8 | B6 |  |
|   rn-north-22473  | 5 | eu-west-1 | B6 |  |
|   rn-north-22496  | 1 | eu-west-1 | B6 |  |
|   rn-north-22496  | 2 | ca-north-8 | B6 |  |
|   rn-north-22496  | 3 | eu-west-1 | B6 |  |
|   rn-north-22496  | 4 | eu-west-1 | B6 |  |
|   rn-north-22496  | 5 | eu-west-1 | B6 | late? |
|   rn-north-22526  | 1 | ca-north-8 | B6 |  |
|   rn-north-22526  | 2 | ca-north-8 | B6 |  |
|   rn-north-22526  | 3 | eu-west-1 | B6 |  |
|   rn-north-22526  | 4 | ca-north-8 | B6 |  |
|   rn-north-22526  | 5 | ca-north-8 | B6 |  |
|   rn-north-22553  | 1 | eu-west-1 | B6 |  |
|   rn-north-22553  | 2 | eu-west-1 | B6 |  |
|   rn-north-22553  | 3 | eu-west-1 | B6 | recheck |
|   rn-north-22553  | 4 | eu-west-1 | B6 |  |
|   rn-north-22553  | 5 | eu-west-1 | B6 |  |
|   rn-north-22580  | 1 | ca-north-8 | B6 |  |
|   rn-north-22580  | 2 | ca-north-8 | B6 |  |
|   rn-north-22580  | 3 | ca-north-8 | B6 |  |
|   rn-north-22580  | 4 | ca-north-8 | B6 |  |
|   rn-north-22580  | 5 | ca-north-8 | B6 |  |
|   rn-north-22612  | 1 | eu-west-1 | B6 |  |
|   rn-north-22612  | 1 | eu-west-1 | B6 |  |
|   rn-north-22612  | 2 | eu-west-1 | B6 |  |
|   rn-north-22612  | 3 | eu-west-1 | B6 |  |
|   rn-north-22612  | 4 | eu-west-1 | B6 |  |
|   rn-north-22612  | 5 | eu-west-1 | B6 |  |
|   rn-north-22639  | 1 | ca-north-8 | B6 |  |
|   rn-north-22639  | 2 | ca-north-8 | B6 |  |
|   rn-north-22639  | 3 | eu-west-1 | B6 |  |
|   rn-north-22639  | 4 | ca-north-8 | B6 |  |
|   rn-north-22639  | 5 | ca-north-8 | B6 |  |
|   rn-north-22666  | 1 | eu-west-1 | B6 | dup? |
|   rn-north-22666  | 2 | eu-west-1 | B6 | dup? |
|   rn-north-22666  | 3 | eu-west-1 | B6 |  |
|   rn-north-22666  | 4 | eu-west-1 | B6 |  |
|   rn-north-22666  | 5 | eu-west-1 | B6 |  |
|   rn-north-22695  | 1 | ca-north-8 | B6 |  |
|   rn-north-22695  | 2 | ca-north-8 | B6 | late? |
|   rn-north-22695  | 3 | ca-north-8 | B6 | dup? |
|   rn-north-22695  | 4 | ca-north-8 | B6 | recheck |
|   rn-north-22695  | 5 | ca-north-8 | B6 |  |
|   rn-north-22725  | 1 | eu-west-1 | B6 |  |
|   rn-north-22725  | 2 | eu-west-1 | B6 |  |
|   rn-north-22725  | 3 | eu-west-1 | B6 |  |
|   rn-north-22725  | 4 | ca-north-8 | B6 |  |
|   rn-north-22725  | 5 | eu-west-1 | B6 | dup? |
|   rn-north-22750  | 1 | ca-north-8 | B6 |  |
|   rn-north-22750  | 2 | ca-north-8 | B6 |  |
|   rn-north-22750  | 3 | ca-north-8 | B6 |  |
|   rn-north-22750  | 4 | ca-north-8 | B6 |  |
|   rn-north-22750  | 5 | ca-north-8 | B6 | late? |
|   rn-north-22776  | 1 | eu-west-1 | B6 |  |
|   rn-north-22776  | 2 | ca-north-8 | B6 |  |
|   rn-north-22776  | 3 | eu-west-1 | B6 |  |
|   rn-north-22776  | 4 | eu-west-1 | B6 |  |
|   rn-north-22776  | 5 | eu-west-1 | B6 | recheck |
|   rn-north-22809  | 1 | ca-north-8 | B6 | dup? |
|   rn-north-22809  | 2 | ca-north-8 | B6 |  |
|   rn-north-22809  | 3 | ca-north-8 | B6 |  |
|   rn-north-22809  | 4 | ca-north-8 | B6 |  |
|   rn-north-22809  | 5 | ca-north-8 | B6 | dup? |
|   rn-north-22834  | 1 | eu-west-1 | B6 |  |
|   rn-north-22834  | 2 | eu-west-1 | B6 | recheck |
|   rn-north-22834  | 3 | eu-west-1 | B6 |  |
|   rn-north-22834  | 4 | eu-west-1 | B6 |  |
|   rn-north-22834  | 5 | eu-west-1 | B6 |  |
|   rn-north-22865  | 1 | ca-north-8 | B6 |  |
|   rn-north-22865  | 2 | ca-north-8 | B6 |  |
|   rn-north-22865  | 3 | ca-north-8 | B6 |  |
|   rn-north-22865  | 4 | ca-north-8 | B6 |  |
|   rn-north-22865  | 5 | ca-north-8 | B6 |  |
|   rn-north-22887  | 1 | eu-west-1 | B6 |  |
|   rn-north-22887  | 2 | eu-west-1 | B6 |  |
|   rn-north-22887  | 3 | eu-west-1 | B6 |  |
|   rn-north-22887  | 4 | eu-west-1 | B6 |  |
|   rn-north-22887  | 5 | eu-west-1 | B6 |  |
|   rn-north-22918  | 1 | ca-north-8 | B6 |  |
|   rn-north-22918  | 1 | ca-north-8 | B6 |  |
|   rn-north-22918  | 2 | ca-north-8 | B6 | dup? |
|   rn-north-22918  | 3 | ca-north-8 | B6 |  |
|   rn-north-22918  | 4 | ca-north-8 | B6 |  |
|   rn-north-22918  | 5 | ca-north-8 | B6 | recheck |
|   rn-north-22948  | 1 | eu-west-1 | B6 |  |
|   rn-north-22948  | 2 | eu-west-1 | B6 |  |
|   rn-north-22948  | 3 | eu-west-1 | B6 |  |
|   rn-north-22948  | 4 | eu-west-1 | B6 |  |
|   rn-north-22948  | 5 | eu-west-1 | B6 |  |
|   rn-north-22974  | 1 | ca-north-8 | B6 |  |
|   rn-north-22974  | 2 | ca-north-8 | B6 |  |
|   rn-north-22974  | 2 | ca-north-8 | B6 |  |
|   rn-north-22974  | 3 | ca-north-8 | B6 |  |
|   rn-north-22974  | 4 | ca-north-8 | B6 | void? |
|   rn-north-22974  | 5 | ca-north-8 | B6 | void? |
|   rn-north-23003  | 1 | eu-west-1 | B6 |  |
|   rn-north-23003  | 2 | eu-west-1 | B6 |  |
|   rn-north-23003  | 2 | eu-west-1 | B6 |  |
|   rn-north-23003  | 3 | eu-west-1 | B6 | void? |
|   rn-north-23003  | 4 | eu-west-1 | B6 |  |
|   rn-north-23003  | 5 | eu-west-1 | B6 |  |
|   rn-north-23003  | 5 | eu-west-1 | B6 |  |
|   rn-north-23028  | 1 | ca-north-8 | B6 |  |
|   rn-north-23028  | 2 | ca-north-8 | B6 |  |
|   rn-north-23028  | 3 | ca-north-8 | B6 | void? |
|   rn-north-23028  | 4 | ca-north-8 | B6 |  |
|   rn-north-23028  | 5 | ca-north-8 | B6 |  |
|   rn-north-23059  | 1 | eu-west-1 | B6 | void? |
|   rn-north-23059  | 2 | eu-west-1 | B6 |  |
|   rn-north-23059  | 3 | eu-west-1 | B6 |  |
|   rn-north-23059  | 4 | eu-west-1 | B6 |  |
|   rn-north-23059  | 5 | eu-west-1 | B6 |  |
|   rn-north-23087  | 1 | ca-north-8 | B6 |  |
|   rn-north-23087  | 2 | ca-north-8 | B6 |  |
|   rn-north-23087  | 3 | ca-north-8 | B6 |  |
|   rn-north-23087  | 4 | ca-north-8 | B6 |  |
|   rn-north-23087  | 5 | ca-north-8 | B6 |  |
|   rn-north-23116  | 1 | eu-west-1 | B6 |  |
|   rn-north-23116  | 2 | eu-west-1 | B6 |  |
|   rn-north-23116  | 3 | eu-west-1 | B6 |  |
|   rn-north-23116  | 4 | eu-west-1 | B6 |  |
|   rn-north-23116  | 5 | eu-west-1 | B6 |  |
|   rn-north-23116  | 5 | eu-west-1 | B6 |  |
|   rn-north-23139  | 1 | ca-north-8 | B6 |  |
|   rn-north-23139  | 2 | ca-north-8 | B6 |  |
|   rn-north-23139  | 3 | ca-north-8 | B6 |  |
|   rn-north-23139  | 4 | ca-north-8 | B6 | late? |
|   rn-north-23139  | 5 | ca-north-8 | B6 |  |
|   rn-north-23168  | 1 | eu-west-1 | B6 | late? |
|   rn-north-23168  | 2 | eu-west-1 | B6 |  |
|   rn-north-23168  | 2 | eu-west-1 | B6 |  |
|   rn-north-23168  | 3 | eu-west-1 | B6 |  |
|   rn-north-23168  | 4 | ca-north-8 | B6 |  |
|   rn-north-23168  | 5 | eu-west-1 | B6 |  |
|   rn-north-23200  | 1 | ca-north-8 | B6 |  |
|   rn-north-23200  | 2 | ca-north-8 | B6 |  |
|   rn-north-23200  | 3 | ca-north-8 | B6 | late? |
|   rn-north-23200  | 4 | ca-north-8 | B6 |  |
|   rn-north-23200  | 5 | ca-north-8 | B6 |  |
|   rn-north-23225  | 1 | eu-west-1 | B6 | void? |
|   rn-north-23225  | 2 | eu-west-1 | B6 |  |
|   rn-north-23225  | 3 | eu-west-1 | B6 |  |
|   rn-north-23225  | 4 | eu-west-1 | B6 | void? |
|   rn-north-23225  | 5 | eu-west-1 | B6 |  |
|   rn-north-23255  | 1 | ca-north-8 | B6 |  |
|   rn-north-23255  | 2 | ca-north-8 | B6 |  |
|   rn-north-23255  | 2 | ca-north-8 | B6 |  |
|   rn-north-23255  | 3 | eu-west-1 | B6 |  |
|   rn-north-23255  | 4 | ca-north-8 | B6 |  |
|   rn-north-23255  | 4 | ca-north-8 | B6 |  |
|   rn-north-23255  | 5 | ca-north-8 | B6 |  |
|   rn-north-23285  | 1 | eu-west-1 | B6 |  |
|   rn-north-23285  | 2 | eu-west-1 | B6 |  |
|   rn-north-23285  | 3 | eu-west-1 | B6 |  |
|   rn-north-23285  | 4 | eu-west-1 | B6 |  |
|   rn-north-23285  | 5 | eu-west-1 | B6 | dup? |
|   rn-north-23311  | 1 | ca-north-8 | B6 |  |
|   rn-north-23311  | 2 | ca-north-8 | B6 |  |
|   rn-north-23311  | 3 | ca-north-8 | B6 |  |
|   rn-north-23311  | 4 | ca-north-8 | B6 |  |
|   rn-north-23311  | 5 | ca-north-8 | B6 | dup? |
|   rn-north-23338  | 1 | eu-west-1 | B6 |  |
|   rn-north-23338  | 2 | eu-west-1 | B6 |  |
|   rn-north-23338  | 3 | eu-west-1 | B6 |  |
|   rn-north-23338  | 4 | eu-west-1 | B6 |  |
|   rn-north-23338  | 5 | eu-west-1 | B6 | void? |
|   rn-north-23369  | 1 | ca-north-8 | B6 | recheck |
|   rn-north-23369  | 2 | eu-west-1 | B6 |  |
|   rn-north-23369  | 3 | ca-north-8 | B6 |  |
|   rn-north-23369  | 4 | ca-north-8 | B6 |  |
|   rn-north-23369  | 5 | ca-north-8 | B6 |  |
|   rn-north-23395  | 1 | eu-west-1 | B6 |  |
|   rn-north-23395  | 2 | eu-west-1 | B6 |  |
|   rn-north-23395  | 3 | eu-west-1 | B6 | late? |
|   rn-north-23395  | 4 | eu-west-1 | B6 | recheck |
|   rn-north-23395  | 4 | eu-west-1 | B6 | recheck |
|   rn-north-23395  | 5 | eu-west-1 | B6 |  |
|   rn-north-23425  | 1 | ca-north-8 | B6 |  |
|   rn-north-23425  | 2 | ca-north-8 | B6 |  |
|   rn-north-23425  | 3 | ca-north-8 | B6 |  |
|   rn-north-23425  | 4 | ca-north-8 | B6 |  |
|   rn-north-23425  | 5 | ca-north-8 | B6 |  |
|   rn-north-23452  | 1 | eu-west-1 | B6 |  |
|   rn-north-23452  | 2 | eu-west-1 | B6 | void? |
|   rn-north-23452  | 3 | eu-west-1 | B6 | recheck |
|   rn-north-23452  | 4 | eu-west-1 | B6 | late? |
|   rn-north-23452  | 5 | eu-west-1 | B6 |  |
|   rn-north-23481  | 1 | ca-north-8 | B6 |  |
|   rn-north-23481  | 2 | ca-north-8 | B6 | void? |
|   rn-north-23481  | 3 | ca-north-8 | B6 |  |
|   rn-north-23481  | 4 | ca-north-8 | B6 |  |
|   rn-north-23481  | 5 | ca-north-8 | B6 |  |
|   rn-north-23504  | 1 | eu-west-1 | B6 | void? |
|   rn-north-23504  | 2 | eu-west-1 | B6 | dup? |
|   rn-north-23504  | 3 | eu-west-1 | B6 |  |
|   rn-north-23504  | 4 | eu-west-1 | B6 |  |
|   rn-north-23504  | 5 | eu-west-1 | B6 | recheck |
|   rn-north-23532  | 1 | ca-north-8 | B6 |  |
|   rn-north-23532  | 2 | ca-north-8 | B6 |  |
|   rn-north-23532  | 3 | ca-north-8 | B6 |  |
|   rn-north-23532  | 4 | ca-north-8 | B6 |  |
|   rn-north-23532  | 5 | ca-north-8 | B6 |  |
|   rn-north-23559  | 1 | eu-west-1 | B6 | dup? |
|   rn-north-23559  | 2 | eu-west-1 | B6 | dup? |
|   rn-north-23559  | 2 | eu-west-1 | B6 | dup? |
|   rn-north-23559  | 3 | eu-west-1 | B6 | recheck |
|   rn-north-23559  | 4 | eu-west-1 | B6 |  |
|   rn-north-23559  | 5 | eu-west-1 | B6 |  |
|   rn-north-23591  | 1 | ca-north-8 | B6 |  |
|   rn-north-23591  | 2 | ca-north-8 | B6 |  |
|   rn-north-23591  | 3 | ca-north-8 | B6 |  |
|   rn-north-23591  | 4 | ca-north-8 | B6 |  |
|   rn-north-23591  | 5 | ca-north-8 | B6 | late? |
|   rn-north-23618  | 1 | eu-west-1 | B6 | late? |
|   rn-north-23618  | 2 | eu-west-1 | B6 |  |
|   rn-north-23618  | 3 | eu-west-1 | B6 |  |
|   rn-north-23618  | 4 | eu-west-1 | B6 |  |
|   rn-north-23618  | 5 | eu-west-1 | B6 |  |
|   rn-north-23647  | 1 | ca-north-8 | B6 |  |
|   rn-north-23647  | 2 | ca-north-8 | B6 |  |
|   rn-north-23647  | 3 | ca-north-8 | B6 |  |
|   rn-north-23647  | 4 | eu-west-1 | B6 | recheck |
|   rn-north-23647  | 5 | ca-north-8 | B6 | late? |
|   rn-north-23672  | 1 | eu-west-1 | B6 |  |
|   rn-north-23672  | 2 | eu-west-1 | B6 |  |
|   rn-north-23672  | 3 | eu-west-1 | B6 |  |
|   rn-north-23672  | 3 | eu-west-1 | B6 |  |
|   rn-north-23672  | 4 | eu-west-1 | B6 |  |
|   rn-north-23672  | 5 | eu-west-1 | B6 |  |
|   rn-north-23703  | 1 | ca-north-8 | B6 |  |
|   rn-north-23703  | 2 | ca-north-8 | B6 |  |
|   rn-north-23703  | 3 | ca-north-8 | B6 |  |
|   rn-north-23703  | 4 | ca-north-8 | B6 |  |
|   rn-north-23703  | 5 | ca-north-8 | B6 |  |
|   rn-north-23733  | 1 | eu-west-1 | B6 |  |
|   rn-north-23733  | 2 | eu-west-1 | B6 |  |
|   rn-north-23733  | 3 | ca-north-8 | B6 |  |
|   rn-north-23733  | 4 | eu-west-1 | B6 | dup? |
|   rn-north-23733  | 5 | eu-west-1 | B6 | recheck |
|   rn-north-23755  | 1 | ca-north-8 | B6 |  |
|   rn-north-23755  | 2 | ca-north-8 | B6 |  |
|   rn-north-23755  | 3 | eu-west-1 | B6 | late? |
|   rn-north-23755  | 4 | ca-north-8 | B6 |  |
|   rn-north-23755  | 5 | ca-north-8 | B6 |  |
|   rn-north-23788  | 1 | eu-west-1 | B6 |  |
|   rn-north-23788  | 2 | eu-west-1 | B6 |  |
|   rn-north-23788  | 3 | eu-west-1 | B6 | late? |
|   rn-north-23788  | 4 | eu-west-1 | B6 |  |
|   rn-north-23788  | 5 | ca-north-8 | B6 | recheck |
|   rn-north-23814  | 1 | ca-north-8 | B6 |  |
|   rn-north-23814  | 2 | ca-north-8 | B6 |  |
|   rn-north-23814  | 3 | ca-north-8 | B6 |  |
|   rn-north-23814  | 4 | ca-north-8 | B6 | late? |
|   rn-north-23814  | 5 | ca-north-8 | B6 | dup? |
|   rn-north-23841  | 1 | eu-west-1 | B6 |  |
|   rn-north-23841  | 2 | eu-west-1 | B6 |  |
|   rn-north-23841  | 3 | eu-west-1 | B6 |  |
|   rn-north-23841  | 4 | eu-west-1 | B6 | late? |
|   rn-north-23841  | 5 | eu-west-1 | B6 |  |
|   rn-north-23868  | 1 | ca-north-8 | B6 |  |
|   rn-north-23868  | 2 | ca-north-8 | B6 |  |
|   rn-north-23868  | 3 | ca-north-8 | B6 |  |
|   rn-north-23868  | 4 | ca-north-8 | B6 | dup? |
|   rn-north-23868  | 5 | ca-north-8 | B6 |  |
|   rn-north-23895  | 1 | eu-west-1 | B6 |  |
|   rn-north-23895  | 2 | eu-west-1 | B6 |  |
|   rn-north-23895  | 3 | eu-west-1 | B6 |  |
|   rn-north-23895  | 4 | eu-west-1 | B6 |  |
|   rn-north-23895  | 5 | eu-west-1 | B6 |  |
|   rn-north-23926  | 1 | ca-north-8 | B6 |  |
|   rn-north-23926  | 2 | ca-north-8 | B6 |  |
|   rn-north-23926  | 3 | ca-north-8 | B6 | late? |
|   rn-north-23926  | 4 | ca-north-8 | B6 |  |
|   rn-north-23926  | 5 | ca-north-8 | B6 | recheck |
|   rn-north-23957  | 1 | eu-west-1 | B6 |  |
|   rn-north-23957  | 2 | eu-west-1 | B6 |  |
|   rn-north-23957  | 3 | eu-west-1 | B6 |  |
|   rn-north-23957  | 4 | ca-north-8 | B6 |  |
|   rn-north-23957  | 5 | eu-west-1 | B6 |  |
|   rn-north-23984  | 1 | ca-north-8 | B6 |  |
|   rn-north-23984  | 2 | ca-north-8 | B6 | dup? |
|   rn-north-23984  | 2 | ca-north-8 | B6 | dup? |
|   rn-north-23984  | 3 | ca-north-8 | B6 |  |
|   rn-north-23984  | 4 | ca-north-8 | B6 |  |
|   rn-north-23984  | 5 | ca-north-8 | B6 |  |
|   rn-north-24009  | 1 | eu-west-1 | B6 |  |
|   rn-north-24009  | 2 | eu-west-1 | B6 |  |
|   rn-north-24009  | 3 | eu-west-1 | B6 |  |
|   rn-north-24009  | 4 | eu-west-1 | B6 | void? |
|   rn-north-24009  | 5 | eu-west-1 | B6 |  |
|   rn-north-24035  | 1 | ca-north-8 | B6 |  |
|   rn-north-24035  | 2 | ca-north-8 | B6 |  |
|   rn-north-24035  | 3 | eu-west-1 | B6 |  |
|   rn-north-24035  | 4 | ca-north-8 | B6 |  |
|   rn-north-24035  | 5 | ca-north-8 | B6 |  |
|   rn-north-24064  | 1 | eu-west-1 | B6 | dup? |
|   rn-north-24064  | 2 | eu-west-1 | B6 | late? |
|   rn-north-24064  | 3 | eu-west-1 | B6 |  |
|   rn-north-24064  | 4 | eu-west-1 | B6 |  |
|   rn-north-24064  | 5 | eu-west-1 | B6 | void? |
|   rn-north-24093  | 1 | ca-north-8 | B6 |  |
|   rn-north-24093  | 2 | ca-north-8 | B6 |  |
|   rn-north-24093  | 3 | ca-north-8 | B6 |  |
|   rn-north-24093  | 4 | ca-north-8 | B6 | recheck |
|   rn-north-24093  | 5 | ca-north-8 | B6 | dup? |
|   rn-north-24123  | 1 | eu-west-1 | B6 |  |
|   rn-north-24123  | 2 | eu-west-1 | B6 |  |
|   rn-north-24123  | 3 | eu-west-1 | B6 |  |
|   rn-north-24123  | 4 | eu-west-1 | B6 |  |
|   rn-north-24123  | 5 | eu-west-1 | B6 |  |
|   rn-north-24151  | 1 | ca-north-8 | B6 |  |
|   rn-north-24151  | 2 | ca-north-8 | B6 |  |
|   rn-north-24151  | 3 | eu-west-1 | B6 |  |
|   rn-north-24151  | 4 | eu-west-1 | B6 |  |
|   rn-north-24151  | 5 | ca-north-8 | B6 |  |
|   rn-north-24175  | 1 | eu-west-1 | B6 |  |
|   rn-north-24175  | 2 | eu-west-1 | B6 |  |
|   rn-north-24175  | 3 | eu-west-1 | B6 | dup? |
|   rn-north-24175  | 4 | eu-west-1 | B6 | dup? |
|   rn-north-24175  | 5 | eu-west-1 | B6 |  |
|   rn-north-24205  | 1 | ca-north-8 | B6 |  |
|   rn-north-24205  | 2 | eu-west-1 | B6 |  |
|   rn-north-24205  | 3 | ca-north-8 | B6 |  |
|   rn-north-24205  | 4 | ca-north-8 | B6 |  |
|   rn-north-24205  | 5 | ca-north-8 | B6 |  |
|   rn-north-24233  | 1 | eu-west-1 | B6 |  |
|   rn-north-24233  | 2 | eu-west-1 | B6 |  |
|   rn-north-24233  | 3 | eu-west-1 | B6 |  |
|   rn-north-24233  | 4 | eu-west-1 | B6 |  |
|   rn-north-24233  | 5 | eu-west-1 | B6 |  |
|   rn-north-24259  | 1 | ca-north-8 | B6 | recheck |
|   rn-north-24259  | 2 | ca-north-8 | B6 |  |
|   rn-north-24259  | 3 | ca-north-8 | B6 |  |
|   rn-north-24259  | 4 | ca-north-8 | B6 |  |
|   rn-north-24259  | 5 | ca-north-8 | B6 |  |
| RN-SOUTH-10020 | 1 | sa-east-7 | B7 | dup? |
| RN-SOUTH-10020 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-10020 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-10020 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10020 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-10043 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10043 | 2 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10043 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10043 | 4 | sa-east-7 | B7 |  |
| RN-SOUTH-10043 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10071 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-10071 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-10071 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-10071 | 4 | sa-east-7 | B7 |  |
| RN-SOUTH-10071 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-10103 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10103 | 2 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10103 | 3 | ap-southeast-6 | B7 | late? |
| RN-SOUTH-10103 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10103 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10126 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-10126 | 2 | sa-east-7 | B7 | late? |
| RN-SOUTH-10126 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-10126 | 4 | sa-east-7 | B7 |  |
| RN-SOUTH-10126 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-10157 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10157 | 2 | ap-southeast-6 | B7 | late? |
| RN-SOUTH-10157 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10157 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10157 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-10182 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-10182 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-10182 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-10182 | 4 | sa-east-7 | B7 |  |
| RN-SOUTH-10182 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-10213 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10213 | 2 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10213 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10213 | 4 | ap-southeast-6 | B7 | late? |
| RN-SOUTH-10213 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10244 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-10244 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-10244 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-10244 | 4 | sa-east-7 | B7 |  |
| RN-SOUTH-10244 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10267 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10267 | 2 | ap-southeast-6 | B7 | void? |
| RN-SOUTH-10267 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10267 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10267 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10297 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-10297 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-10297 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-10297 | 4 | sa-east-7 | B7 |  |
| RN-SOUTH-10297 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-10322 | 1 | ap-southeast-6 | B7 | late? |
| RN-SOUTH-10322 | 2 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10322 | 2 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10322 | 3 | ap-southeast-6 | B7 | void? |
| RN-SOUTH-10322 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10322 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10351 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-10351 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-10351 | 3 | sa-east-7 | B7 | void? |
| RN-SOUTH-10351 | 4 | sa-east-7 | B7 |  |
| RN-SOUTH-10351 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-10379 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10379 | 2 | sa-east-7 | B7 | recheck |
| RN-SOUTH-10379 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10379 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10379 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10409 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-10409 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-10409 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-10409 | 4 | sa-east-7 | B7 |  |
| RN-SOUTH-10409 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-10437 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10437 | 2 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10437 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10437 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10437 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10462 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-10462 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-10462 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-10462 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-10462 | 4 | sa-east-7 | B7 | recheck |
| RN-SOUTH-10462 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-10495 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10495 | 2 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10495 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10495 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10495 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10520 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-10520 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-10520 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-10520 | 4 | sa-east-7 | B7 | dup? |
| RN-SOUTH-10520 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-10549 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10549 | 2 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10549 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10549 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10549 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10576 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-10576 | 2 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10576 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-10576 | 4 | sa-east-7 | B7 |  |
| RN-SOUTH-10576 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-10606 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10606 | 2 | ap-southeast-6 | B7 | void? |
| RN-SOUTH-10606 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10606 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10606 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10636 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-10636 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-10636 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-10636 | 4 | sa-east-7 | B7 |  |
| RN-SOUTH-10636 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-10662 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10662 | 2 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10662 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10662 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10662 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10692 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-10692 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-10692 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-10692 | 4 | sa-east-7 | B7 |  |
| RN-SOUTH-10692 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-10717 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10717 | 2 | ap-southeast-6 | B7 | late? |
| RN-SOUTH-10717 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10717 | 4 | ap-southeast-6 | B7 | void? |
| RN-SOUTH-10717 | 5 | ap-southeast-6 | B7 | void? |
| RN-SOUTH-10742 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-10742 | 2 | ap-southeast-6 | B7 | late? |
| RN-SOUTH-10742 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10742 | 4 | sa-east-7 | B7 |  |
| RN-SOUTH-10742 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-10772 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10772 | 2 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10772 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10772 | 4 | sa-east-7 | B7 |  |
| RN-SOUTH-10772 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10804 | 1 | sa-east-7 | B7 | void? |
| RN-SOUTH-10804 | 2 | sa-east-7 | B7 | void? |
| RN-SOUTH-10804 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10804 | 4 | sa-east-7 | B7 | late? |
| RN-SOUTH-10804 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-10829 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10829 | 2 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10829 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10829 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10829 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10855 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-10855 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-10855 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-10855 | 4 | sa-east-7 | B7 |  |
| RN-SOUTH-10855 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-10888 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10888 | 2 | ap-southeast-6 | B7 | late? |
| RN-SOUTH-10888 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-10888 | 4 | ap-southeast-6 | B7 | dup? |
| RN-SOUTH-10888 | 5 | ap-southeast-6 | B7 | void? |
| RN-SOUTH-10915 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-10915 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-10915 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-10915 | 4 | sa-east-7 | B7 |  |
| RN-SOUTH-10915 | 4 | sa-east-7 | B7 |  |
| RN-SOUTH-10915 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-10943 | 1 | ap-southeast-6 | B7 | recheck |
| RN-SOUTH-10943 | 2 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10943 | 3 | ap-southeast-6 | B7 | dup? |
| RN-SOUTH-10943 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10943 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10972 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-10972 | 2 | sa-east-7 | B7 | void? |
| RN-SOUTH-10972 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-10972 | 4 | sa-east-7 | B7 | recheck |
| RN-SOUTH-10972 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-10994 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10994 | 2 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10994 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10994 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10994 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-10994 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11025 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-11025 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-11025 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11025 | 4 | sa-east-7 | B7 |  |
| RN-SOUTH-11025 | 4 | sa-east-7 | B7 |  |
| RN-SOUTH-11025 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11053 | 1 | ap-southeast-6 | B7 | void? |
| RN-SOUTH-11053 | 1 | ap-southeast-6 | B7 | void? |
| RN-SOUTH-11053 | 2 | ap-southeast-6 | B7 | dup? |
| RN-SOUTH-11053 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11053 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11053 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11084 | 1 | sa-east-7 | B7 | dup? |
| RN-SOUTH-11084 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-11084 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-11084 | 4 | sa-east-7 | B7 |  |
| RN-SOUTH-11084 | 5 | sa-east-7 | B7 | recheck |
| RN-SOUTH-11111 | 1 | ap-southeast-6 | B7 | void? |
| RN-SOUTH-11111 | 2 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11111 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11111 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11111 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11138 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-11138 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-11138 | 3 | sa-east-7 | B7 | late? |
| RN-SOUTH-11138 | 4 | sa-east-7 | B7 |  |
| RN-SOUTH-11138 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-11168 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11168 | 2 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11168 | 3 | ap-southeast-6 | B7 | void? |
| RN-SOUTH-11168 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11168 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11193 | 1 | sa-east-7 | B7 | dup? |
| RN-SOUTH-11193 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-11193 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-11193 | 4 | sa-east-7 | B7 |  |
| RN-SOUTH-11193 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-11224 | 1 | ap-southeast-6 | B7 | late? |
| RN-SOUTH-11224 | 2 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11224 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11224 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11224 | 5 | ap-southeast-6 | B7 | dup? |
| RN-SOUTH-11251 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-11251 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-11251 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-11251 | 4 | sa-east-7 | B7 |  |
| RN-SOUTH-11251 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11276 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11276 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-11276 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11276 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11276 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11305 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-11305 | 2 | sa-east-7 | B7 | late? |
| RN-SOUTH-11305 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-11305 | 4 | sa-east-7 | B7 |  |
| RN-SOUTH-11305 | 5 | sa-east-7 | B7 | dup? |
| RN-SOUTH-11335 | 1 | ap-southeast-6 | B7 | void? |
| RN-SOUTH-11335 | 2 | ap-southeast-6 | B7 | late? |
| RN-SOUTH-11335 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11335 | 4 | ap-southeast-6 | B7 | recheck |
| RN-SOUTH-11335 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11335 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11360 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-11360 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-11360 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-11360 | 4 | sa-east-7 | B7 | late? |
| RN-SOUTH-11360 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-11390 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11390 | 2 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11390 | 3 | ap-southeast-6 | B7 | void? |
| RN-SOUTH-11390 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11390 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11418 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-11418 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-11418 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-11418 | 4 | sa-east-7 | B7 |  |
| RN-SOUTH-11418 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-11446 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11446 | 2 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11446 | 3 | ap-southeast-6 | B7 | dup? |
| RN-SOUTH-11446 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11446 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-11471 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-11471 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-11471 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-11471 | 4 | sa-east-7 | B7 |  |
| RN-SOUTH-11471 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-11504 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11504 | 2 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11504 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11504 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11504 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11532 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-11532 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-11532 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-11532 | 4 | sa-east-7 | B7 | recheck |
| RN-SOUTH-11532 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-11556 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11556 | 2 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11556 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11556 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11556 | 5 | ap-southeast-6 | B7 | dup? |
| RN-SOUTH-11582 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-11582 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-11582 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-11582 | 3 | sa-east-7 | B7 | void? |
| RN-SOUTH-11582 | 4 | sa-east-7 | B7 |  |
| RN-SOUTH-11582 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-11610 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11610 | 2 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11610 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11610 | 4 | ap-southeast-6 | B7 | recheck |
| RN-SOUTH-11610 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11639 | 1 | sa-east-7 | B7 | void? |
| RN-SOUTH-11639 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-11639 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-11639 | 4 | sa-east-7 | B7 |  |
| RN-SOUTH-11639 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-11667 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11667 | 2 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11667 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-11667 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11667 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11700 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-11700 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-11700 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-11700 | 4 | sa-east-7 | B7 |  |
| RN-SOUTH-11700 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-11726 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11726 | 2 | ap-southeast-6 | B7 | late? |
| RN-SOUTH-11726 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11726 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11726 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11755 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-11755 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-11755 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-11755 | 4 | sa-east-7 | B7 |  |
| RN-SOUTH-11755 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-11784 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11784 | 2 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11784 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11784 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11784 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11784 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11806 | 1 | sa-east-7 | B7 | late? |
| RN-SOUTH-11806 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-11806 | 3 | sa-east-7 | B7 | late? |
| RN-SOUTH-11806 | 4 | sa-east-7 | B7 |  |
| RN-SOUTH-11806 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-11837 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11837 | 2 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11837 | 3 | ap-southeast-6 | B7 | dup? |
| RN-SOUTH-11837 | 4 | sa-east-7 | B7 |  |
| RN-SOUTH-11837 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11863 | 1 | sa-east-7 | B7 | late? |
| RN-SOUTH-11863 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-11863 | 3 | sa-east-7 | B7 | dup? |
| RN-SOUTH-11863 | 4 | sa-east-7 | B7 |  |
| RN-SOUTH-11863 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-11896 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11896 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11896 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-11896 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11896 | 4 | ap-southeast-6 | B7 | dup? |
| RN-SOUTH-11896 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11922 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-11922 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-11922 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-11922 | 4 | sa-east-7 | B7 |  |
| RN-SOUTH-11922 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-11951 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11951 | 2 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11951 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11951 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-11951 | 5 | ap-southeast-6 | B7 | void? |
| RN-SOUTH-11974 | 1 | sa-east-7 | B7 | void? |
| RN-SOUTH-11974 | 2 | sa-east-7 | B7 | void? |
| RN-SOUTH-11974 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-11974 | 4 | sa-east-7 | B7 | late? |
| RN-SOUTH-11974 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-12004 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12004 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12004 | 2 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12004 | 3 | ap-southeast-6 | B7 | void? |
| RN-SOUTH-12004 | 4 | ap-southeast-6 | B7 | late? |
| RN-SOUTH-12004 | 5 | ap-southeast-6 | B7 | recheck |
| RN-SOUTH-12035 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-12035 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-12035 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-12035 | 4 | sa-east-7 | B7 |  |
| RN-SOUTH-12035 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-12059 | 1 | ap-southeast-6 | B7 | late? |
| RN-SOUTH-12059 | 2 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12059 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-12059 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12059 | 5 | ap-southeast-6 | B7 | void? |
| RN-SOUTH-12092 | 1 | sa-east-7 | B7 | recheck |
| RN-SOUTH-12092 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-12092 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-12092 | 4 | sa-east-7 | B7 |  |
| RN-SOUTH-12092 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-12117 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12117 | 2 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12117 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12117 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12117 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12143 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-12143 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-12143 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-12143 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12143 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-12175 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12175 | 2 | ap-southeast-6 | B7 | dup? |
| RN-SOUTH-12175 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12175 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12175 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-12198 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-12198 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-12198 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-12198 | 4 | sa-east-7 | B7 |  |
| RN-SOUTH-12198 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-12229 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12229 | 2 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12229 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12229 | 4 | sa-east-7 | B7 | recheck |
| RN-SOUTH-12229 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12255 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-12255 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-12255 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-12255 | 4 | sa-east-7 | B7 |  |
| RN-SOUTH-12255 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-12287 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12287 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-12287 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12287 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12287 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-12311 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-12311 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-12311 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-12311 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-12311 | 4 | sa-east-7 | B7 |  |
| RN-SOUTH-12311 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-12344 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12344 | 2 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12344 | 2 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12344 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12344 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12344 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12344 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12366 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-12366 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-12366 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-12366 | 4 | sa-east-7 | B7 |  |
| RN-SOUTH-12366 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-12395 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12395 | 2 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12395 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12395 | 4 | ap-southeast-6 | B7 | void? |
| RN-SOUTH-12395 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12427 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-12427 | 2 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12427 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-12427 | 4 | sa-east-7 | B7 | late? |
| RN-SOUTH-12427 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-12454 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12454 | 2 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12454 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12454 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12454 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12479 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-12479 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-12479 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-12479 | 4 | sa-east-7 | B7 |  |
| RN-SOUTH-12479 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-12507 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12507 | 2 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12507 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12507 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12507 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-12537 | 1 | sa-east-7 | B7 | dup? |
| RN-SOUTH-12537 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-12537 | 3 | sa-east-7 | B7 | void? |
| RN-SOUTH-12537 | 4 | sa-east-7 | B7 | recheck |
| RN-SOUTH-12537 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-12565 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12565 | 2 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12565 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-12565 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12565 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12591 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-12591 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-12591 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-12591 | 4 | sa-east-7 | B7 | recheck |
| RN-SOUTH-12591 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-12618 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12618 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12618 | 2 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12618 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12618 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12618 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12648 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-12648 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-12648 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-12648 | 4 | sa-east-7 | B7 | late? |
| RN-SOUTH-12648 | 5 | sa-east-7 | B7 | dup? |
| RN-SOUTH-12680 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12680 | 2 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12680 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12680 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12680 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12708 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-12708 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-12708 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12708 | 4 | sa-east-7 | B7 | late? |
| RN-SOUTH-12708 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-12733 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12733 | 2 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12733 | 3 | ap-southeast-6 | B7 | dup? |
| RN-SOUTH-12733 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12733 | 5 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12759 | 1 | sa-east-7 | B7 | void? |
| RN-SOUTH-12759 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-12759 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-12759 | 4 | sa-east-7 | B7 | late? |
| RN-SOUTH-12759 | 5 | sa-east-7 | B7 |  |
| RN-SOUTH-12787 | 1 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12787 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-12787 | 3 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12787 | 4 | ap-southeast-6 | B7 |  |
| RN-SOUTH-12787 | 5 | sa-east-7 | B7 | void? |
| RN-SOUTH-12815 | 1 | sa-east-7 | B7 |  |
| RN-SOUTH-12815 | 2 | sa-east-7 | B7 |  |
| RN-SOUTH-12815 | 3 | sa-east-7 | B7 |  |
| RN-SOUTH-12815 | 4 | ap-southeast-6 | B7 | recheck |

**Table: Runner placements (continued)**

| runner | region | rev | batch | flag |
|---|---|---|---|---|
| RN-SOUTH-12815 | sa-east-7 | 5 | B7 |  |
| RN-SOUTH-12844 | ap-southeast-6 | 1 | B7 |  |
| RN-SOUTH-12844 | ap-southeast-6 | 2 | B7 |  |
| RN-SOUTH-12844 | ap-southeast-6 | 3 | B7 |  |
| RN-SOUTH-12844 | ap-southeast-6 | 4 | B7 |  |
| RN-SOUTH-12844 | ap-southeast-6 | 5 | B7 |  |
| RN-SOUTH-12873 | sa-east-7 | 1 | B7 |  |
| RN-SOUTH-12873 | sa-east-7 | 2 | B7 |  |
| RN-SOUTH-12873 | sa-east-7 | 3 | B7 | late? |
| RN-SOUTH-12873 | sa-east-7 | 4 | B7 |  |
| RN-SOUTH-12873 | sa-east-7 | 5 | B7 |  |
| RN-SOUTH-12899 | ap-southeast-6 | 1 | B7 | recheck |
| RN-SOUTH-12899 | ap-southeast-6 | 2 | B7 |  |
| RN-SOUTH-12899 | ap-southeast-6 | 3 | B7 |  |
| RN-SOUTH-12899 | ap-southeast-6 | 4 | B7 | late? |
| RN-SOUTH-12899 | ap-southeast-6 | 5 | B7 |  |
| RN-SOUTH-12927 | sa-east-7 | 1 | B7 |  |
| RN-SOUTH-12927 | sa-east-7 | 2 | B7 |  |
| RN-SOUTH-12927 | sa-east-7 | 3 | B7 |  |
| RN-SOUTH-12927 | sa-east-7 | 4 | B7 | late? |
| RN-SOUTH-12927 | sa-east-7 | 5 | B7 |  |
| RN-SOUTH-12954 | ap-southeast-6 | 1 | B7 | late? |
| RN-SOUTH-12954 | ap-southeast-6 | 2 | B7 |  |
| RN-SOUTH-12954 | ap-southeast-6 | 3 | B7 |  |
| RN-SOUTH-12954 | ap-southeast-6 | 4 | B7 | recheck |
| RN-SOUTH-12954 | ap-southeast-6 | 5 | B7 | late? |
| RN-SOUTH-12984 | sa-east-7 | 1 | B7 |  |
| RN-SOUTH-12984 | sa-east-7 | 2 | B7 |  |
| RN-SOUTH-12984 | sa-east-7 | 3 | B7 | late? |
| RN-SOUTH-12984 | sa-east-7 | 4 | B7 |  |
| RN-SOUTH-12984 | sa-east-7 | 5 | B7 |  |
| RN-SOUTH-13015 | ap-southeast-6 | 1 | B7 |  |
| RN-SOUTH-13015 | ap-southeast-6 | 2 | B7 |  |
| RN-SOUTH-13015 | ap-southeast-6 | 3 | B7 |  |
| RN-SOUTH-13015 | ap-southeast-6 | 4 | B7 |  |
| RN-SOUTH-13015 | ap-southeast-6 | 5 | B7 |  |
| RN-SOUTH-13038 | sa-east-7 | 1 | B7 |  |
| RN-SOUTH-13038 | sa-east-7 | 1 | B7 |  |
| RN-SOUTH-13038 | sa-east-7 | 2 | B7 |  |
| RN-SOUTH-13038 | sa-east-7 | 3 | B7 |  |
| RN-SOUTH-13038 | sa-east-7 | 4 | B7 |  |
| RN-SOUTH-13038 | sa-east-7 | 5 | B7 |  |
| RN-SOUTH-13038 | sa-east-7 | 5 | B7 |  |
| RN-SOUTH-13066 | ap-southeast-6 | 1 | B7 |  |
| RN-SOUTH-13066 | ap-southeast-6 | 2 | B7 |  |
| RN-SOUTH-13066 | ap-southeast-6 | 3 | B7 | late? |
| RN-SOUTH-13066 | ap-southeast-6 | 4 | B7 | dup? |
| RN-SOUTH-13066 | ap-southeast-6 | 5 | B7 |  |
| RN-SOUTH-13094 | sa-east-7 | 1 | B7 |  |
| RN-SOUTH-13094 | sa-east-7 | 2 | B7 |  |
| RN-SOUTH-13094 | sa-east-7 | 3 | B7 |  |
| RN-SOUTH-13094 | sa-east-7 | 4 | B7 | late? |
| RN-SOUTH-13094 | sa-east-7 | 5 | B7 |  |
| RN-SOUTH-13126 | ap-southeast-6 | 1 | B7 |  |
| RN-SOUTH-13126 | ap-southeast-6 | 2 | B7 | void? |
| RN-SOUTH-13126 | ap-southeast-6 | 2 | B7 | void? |
| RN-SOUTH-13126 | ap-southeast-6 | 3 | B7 |  |
| RN-SOUTH-13126 | ap-southeast-6 | 4 | B7 |  |
| RN-SOUTH-13126 | ap-southeast-6 | 5 | B7 | void? |
| RN-SOUTH-13150 | sa-east-7 | 1 | B7 |  |
| RN-SOUTH-13150 | sa-east-7 | 2 | B7 |  |
| RN-SOUTH-13150 | sa-east-7 | 3 | B7 |  |
| RN-SOUTH-13150 | sa-east-7 | 4 | B7 |  |
| RN-SOUTH-13150 | sa-east-7 | 5 | B7 |  |
| RN-SOUTH-13178 | ap-southeast-6 | 1 | B7 |  |
| RN-SOUTH-13178 | ap-southeast-6 | 1 | B7 |  |
| RN-SOUTH-13178 | ap-southeast-6 | 2 | B7 |  |
| RN-SOUTH-13178 | ap-southeast-6 | 3 | B7 |  |
| RN-SOUTH-13178 | ap-southeast-6 | 4 | B7 |  |
| RN-SOUTH-13178 | ap-southeast-6 | 4 | B7 |  |
| RN-SOUTH-13178 | sa-east-7 | 5 | B7 | dup? |
| RN-SOUTH-13206 | sa-east-7 | 1 | B7 |  |
| RN-SOUTH-13206 | sa-east-7 | 2 | B7 |  |
| RN-SOUTH-13206 | sa-east-7 | 3 | B7 |  |
| RN-SOUTH-13206 | sa-east-7 | 4 | B7 |  |
| RN-SOUTH-13206 | sa-east-7 | 5 | B7 |  |
| RN-SOUTH-13240 | ap-southeast-6 | 1 | B7 |  |
| RN-SOUTH-13240 | ap-southeast-6 | 2 | B7 |  |
| RN-SOUTH-13240 | ap-southeast-6 | 3 | B7 | dup? |
| RN-SOUTH-13240 | ap-southeast-6 | 4 | B7 |  |
| RN-SOUTH-13240 | ap-southeast-6 | 5 | B7 |  |
| RN-SOUTH-13267 | sa-east-7 | 1 | B7 |  |
| RN-SOUTH-13267 | sa-east-7 | 2 | B7 |  |
| RN-SOUTH-13267 | sa-east-7 | 3 | B7 |  |
| RN-SOUTH-13267 | sa-east-7 | 4 | B7 |  |
| RN-SOUTH-13267 | sa-east-7 | 5 | B7 |  |
| RN-SOUTH-13294 | ap-southeast-6 | 1 | B7 |  |
| RN-SOUTH-13294 | sa-east-7 | 2 | B7 |  |
| RN-SOUTH-13294 | ap-southeast-6 | 3 | B7 |  |
| RN-SOUTH-13294 | ap-southeast-6 | 4 | B7 |  |
| RN-SOUTH-13294 | ap-southeast-6 | 5 | B7 |  |
| RN-SOUTH-13319 | sa-east-7 | 1 | B7 | dup? |
| RN-SOUTH-13319 | sa-east-7 | 2 | B7 |  |
| RN-SOUTH-13319 | sa-east-7 | 3 | B7 |  |
| RN-SOUTH-13319 | sa-east-7 | 4 | B7 |  |
| RN-SOUTH-13319 | sa-east-7 | 5 | B7 |  |
| RN-SOUTH-13350 | ap-southeast-6 | 1 | B7 | recheck |
| RN-SOUTH-13350 | ap-southeast-6 | 2 | B7 | late? |
| RN-SOUTH-13350 | ap-southeast-6 | 3 | B7 |  |
| RN-SOUTH-13350 | ap-southeast-6 | 4 | B7 | dup? |
| RN-SOUTH-13350 | ap-southeast-6 | 5 | B7 |  |
| RN-SOUTH-13377 | sa-east-7 | 1 | B7 |  |
| RN-SOUTH-13377 | sa-east-7 | 2 | B7 |  |
| RN-SOUTH-13377 | sa-east-7 | 3 | B7 |  |
| RN-SOUTH-13377 | sa-east-7 | 4 | B7 |  |
| RN-SOUTH-13377 | sa-east-7 | 5 | B7 |  |
| RN-SOUTH-13406 | ap-southeast-6 | 1 | B7 |  |
| RN-SOUTH-13406 | ap-southeast-6 | 2 | B7 |  |
| RN-SOUTH-13406 | ap-southeast-6 | 3 | B7 |  |
| RN-SOUTH-13406 | ap-southeast-6 | 4 | B7 |  |
| RN-SOUTH-13406 | ap-southeast-6 | 5 | B7 |  |
| RN-SOUTH-13430 | sa-east-7 | 1 | B7 | dup? |
| RN-SOUTH-13430 | sa-east-7 | 2 | B7 |  |
| RN-SOUTH-13430 | sa-east-7 | 3 | B7 |  |
| RN-SOUTH-13430 | sa-east-7 | 4 | B7 |  |
| RN-SOUTH-13430 | sa-east-7 | 5 | B7 |  |
| RN-SOUTH-13459 | ap-southeast-6 | 1 | B7 |  |
| RN-SOUTH-13459 | ap-southeast-6 | 2 | B7 | dup? |
| RN-SOUTH-13459 | ap-southeast-6 | 3 | B7 |  |
| RN-SOUTH-13459 | ap-southeast-6 | 4 | B7 | late? |
| RN-SOUTH-13459 | ap-southeast-6 | 5 | B7 |  |
| RN-SOUTH-13491 | sa-east-7 | 1 | B7 |  |
| RN-SOUTH-13491 | sa-east-7 | 2 | B7 |  |
| RN-SOUTH-13491 | sa-east-7 | 3 | B7 |  |
| RN-SOUTH-13491 | sa-east-7 | 4 | B7 |  |
| RN-SOUTH-13491 | sa-east-7 | 5 | B7 |  |
| RN-SOUTH-13518 | ap-southeast-6 | 1 | B7 |  |
| RN-SOUTH-13518 | ap-southeast-6 | 2 | B7 |  |
| RN-SOUTH-13518 | ap-southeast-6 | 3 | B7 | void? |
| RN-SOUTH-13518 | ap-southeast-6 | 4 | B7 |  |
| RN-SOUTH-13518 | ap-southeast-6 | 5 | B7 |  |
| RN-SOUTH-13542 | sa-east-7 | 1 | B7 |  |
| RN-SOUTH-13542 | sa-east-7 | 1 | B7 |  |
| RN-SOUTH-13542 | sa-east-7 | 2 | B7 |  |
| RN-SOUTH-13542 | sa-east-7 | 3 | B7 |  |
| RN-SOUTH-13542 | sa-east-7 | 4 | B7 |  |
| RN-SOUTH-13542 | sa-east-7 | 5 | B7 |  |
| RN-SOUTH-13574 | ap-southeast-6 | 1 | B7 | late? |
| RN-SOUTH-13574 | ap-southeast-6 | 2 | B7 |  |
| RN-SOUTH-13574 | ap-southeast-6 | 3 | B7 |  |
| RN-SOUTH-13574 | ap-southeast-6 | 4 | B7 |  |
| RN-SOUTH-13574 | sa-east-7 | 5 | B7 |  |
| RN-SOUTH-13604 | sa-east-7 | 1 | B7 |  |
| RN-SOUTH-13604 | sa-east-7 | 2 | B7 | recheck |
| RN-SOUTH-13604 | sa-east-7 | 3 | B7 |  |
| RN-SOUTH-13604 | sa-east-7 | 4 | B7 |  |
| RN-SOUTH-13604 | sa-east-7 | 5 | B7 |  |
| RN-SOUTH-13627 | ap-southeast-6 | 1 | B7 | void? |
| RN-SOUTH-13627 | ap-southeast-6 | 2 | B7 | dup? |
| RN-SOUTH-13627 | ap-southeast-6 | 3 | B7 |  |
| RN-SOUTH-13627 | ap-southeast-6 | 4 | B7 |  |
| RN-SOUTH-13627 | ap-southeast-6 | 5 | B7 | void? |
| RN-SOUTH-13659 | sa-east-7 | 1 | B7 |  |
| RN-SOUTH-13659 | sa-east-7 | 2 | B7 |  |
| RN-SOUTH-13659 | sa-east-7 | 3 | B7 |  |
| RN-SOUTH-13659 | sa-east-7 | 4 | B7 | dup? |
| RN-SOUTH-13659 | sa-east-7 | 5 | B7 |  |
| RN-SOUTH-13683 | ap-southeast-6 | 1 | B7 |  |
| RN-SOUTH-13683 | ap-southeast-6 | 1 | B7 |  |
| RN-SOUTH-13683 | ap-southeast-6 | 2 | B7 |  |
| RN-SOUTH-13683 | ap-southeast-6 | 3 | B7 | recheck |
| RN-SOUTH-13683 | ap-southeast-6 | 4 | B7 |  |
| RN-SOUTH-13683 | ap-southeast-6 | 5 | B7 |  |
| RN-SOUTH-13712 | sa-east-7 | 1 | B7 |  |
| RN-SOUTH-13712 | sa-east-7 | 2 | B7 | late? |
| RN-SOUTH-13712 | sa-east-7 | 3 | B7 |  |
| RN-SOUTH-13712 | sa-east-7 | 3 | B7 |  |
| RN-SOUTH-13712 | sa-east-7 | 4 | B7 |  |
| RN-SOUTH-13712 | sa-east-7 | 5 | B7 |  |
| RN-SOUTH-13738 | ap-southeast-6 | 1 | B7 |  |
| RN-SOUTH-13738 | ap-southeast-6 | 2 | B7 |  |
| RN-SOUTH-13738 | ap-southeast-6 | 3 | B7 |  |
| RN-SOUTH-13738 | ap-southeast-6 | 4 | B7 |  |
| RN-SOUTH-13738 | ap-southeast-6 | 5 | B7 |  |
| RN-SOUTH-13766 | sa-east-7 | 1 | B7 | recheck |
| RN-SOUTH-13766 | sa-east-7 | 2 | B7 |  |
| RN-SOUTH-13766 | sa-east-7 | 3 | B7 |  |
| RN-SOUTH-13766 | sa-east-7 | 4 | B7 |  |
| RN-SOUTH-13766 | sa-east-7 | 5 | B7 |  |
| RN-SOUTH-13800 | ap-southeast-6 | 1 | B7 | recheck |
| RN-SOUTH-13800 | ap-southeast-6 | 2 | B7 |  |
| RN-SOUTH-13800 | ap-southeast-6 | 3 | B7 |  |
| RN-SOUTH-13800 | ap-southeast-6 | 4 | B7 |  |
| RN-SOUTH-13800 | ap-southeast-6 | 5 | B7 |  |
| RN-SOUTH-13823 | sa-east-7 | 1 | B7 |  |
| RN-SOUTH-13823 | sa-east-7 | 2 | B7 |  |
| RN-SOUTH-13823 | sa-east-7 | 3 | B7 |  |
| RN-SOUTH-13823 | sa-east-7 | 4 | B7 |  |
| RN-SOUTH-13823 | sa-east-7 | 5 | B7 |  |
| RN-SOUTH-13855 | ap-southeast-6 | 1 | B7 |  |
| RN-SOUTH-13855 | ap-southeast-6 | 2 | B7 | void? |
| RN-SOUTH-13855 | ap-southeast-6 | 3 | B7 | late? |
| RN-SOUTH-13855 | ap-southeast-6 | 4 | B7 |  |
| RN-SOUTH-13855 | ap-southeast-6 | 5 | B7 |  |
| RN-SOUTH-13880 | sa-east-7 | 1 | B7 |  |
| RN-SOUTH-13880 | sa-east-7 | 2 | B7 |  |
| RN-SOUTH-13880 | sa-east-7 | 3 | B7 | void? |
| RN-SOUTH-13880 | sa-east-7 | 4 | B7 |  |
| RN-SOUTH-13880 | sa-east-7 | 5 | B7 | void? |
| RN-SOUTH-13908 | ap-southeast-6 | 1 | B7 |  |
| RN-SOUTH-13908 | ap-southeast-6 | 2 | B7 | late? |
| RN-SOUTH-13908 | ap-southeast-6 | 3 | B7 |  |
| RN-SOUTH-13908 | ap-southeast-6 | 4 | B7 |  |
| RN-SOUTH-13908 | ap-southeast-6 | 5 | B7 |  |
| RN-SOUTH-13934 | sa-east-7 | 1 | B7 |  |
| RN-SOUTH-13934 | sa-east-7 | 2 | B7 | void? |
| RN-SOUTH-13934 | sa-east-7 | 3 | B7 |  |
| RN-SOUTH-13934 | sa-east-7 | 4 | B7 |  |
| RN-SOUTH-13934 | sa-east-7 | 5 | B7 | void? |
| RN-SOUTH-13968 | ap-southeast-6 | 1 | B7 |  |
| RN-SOUTH-13968 | ap-southeast-6 | 2 | B7 |  |
| RN-SOUTH-13968 | ap-southeast-6 | 3 | B7 |  |
| RN-SOUTH-13968 | ap-southeast-6 | 4 | B7 |  |
| RN-SOUTH-13968 | ap-southeast-6 | 5 | B7 |  |
| RN-SOUTH-13993 | sa-east-7 | 1 | B7 |  |
| RN-SOUTH-13993 | sa-east-7 | 1 | B7 |  |
| RN-SOUTH-13993 | sa-east-7 | 2 | B7 |  |
| RN-SOUTH-13993 | sa-east-7 | 2 | B7 |  |
| RN-SOUTH-13993 | sa-east-7 | 3 | B7 |  |
| RN-SOUTH-13993 | sa-east-7 | 4 | B7 |  |
| RN-SOUTH-13993 | sa-east-7 | 5 | B7 |  |
| RN-SOUTH-14022 | ap-southeast-6 | 1 | B7 |  |
| RN-SOUTH-14022 | ap-southeast-6 | 2 | B7 |  |
| RN-SOUTH-14022 | ap-southeast-6 | 3 | B7 |  |
| RN-SOUTH-14022 | ap-southeast-6 | 4 | B7 | recheck |
| RN-SOUTH-14022 | ap-southeast-6 | 5 | B7 |  |
| RN-SOUTH-14049 | sa-east-7 | 1 | B7 |  |
| RN-SOUTH-14049 | sa-east-7 | 2 | B7 |  |
| RN-SOUTH-14049 | sa-east-7 | 3 | B7 |  |
| RN-SOUTH-14049 | sa-east-7 | 4 | B7 |  |
| RN-SOUTH-14049 | sa-east-7 | 4 | B7 |  |
| RN-SOUTH-14049 | sa-east-7 | 5 | B7 |  |
| RN-SOUTH-14075 | ap-southeast-6 | 1 | B7 |  |
| RN-SOUTH-14075 | ap-southeast-6 | 2 | B7 |  |
| RN-SOUTH-14075 | ap-southeast-6 | 2 | B7 |  |
| RN-SOUTH-14075 | ap-southeast-6 | 3 | B7 |  |
| RN-SOUTH-14075 | ap-southeast-6 | 4 | B7 |  |
| RN-SOUTH-14075 | ap-southeast-6 | 5 | B7 |  |
| RN-SOUTH-14105 | sa-east-7 | 1 | B7 |  |
| RN-SOUTH-14105 | sa-east-7 | 2 | B7 | void? |
| RN-SOUTH-14105 | sa-east-7 | 3 | B7 |  |
| RN-SOUTH-14105 | sa-east-7 | 4 | B7 | late? |
| RN-SOUTH-14105 | ap-southeast-6 | 5 | B7 |  |
| RN-SOUTH-14130 | ap-southeast-6 | 1 | B7 |  |
| RN-SOUTH-14130 | sa-east-7 | 2 | B7 | dup? |
| RN-SOUTH-14130 | ap-southeast-6 | 3 | B7 |  |
| RN-SOUTH-14130 | ap-southeast-6 | 4 | B7 |  |
| RN-SOUTH-14130 | ap-southeast-6 | 5 | B7 | recheck |
| RN-SOUTH-14161 | sa-east-7 | 1 | B7 | recheck |
| RN-SOUTH-14161 | sa-east-7 | 2 | B7 |  |
| RN-SOUTH-14161 | sa-east-7 | 3 | B7 |  |
| RN-SOUTH-14161 | sa-east-7 | 4 | B7 |  |
| RN-SOUTH-14161 | sa-east-7 | 5 | B7 |  |
| RN-SOUTH-14191 | ap-southeast-6 | 1 | B7 |  |
| RN-SOUTH-14191 | ap-southeast-6 | 2 | B7 | late? |
| RN-SOUTH-14191 | ap-southeast-6 | 3 | B7 |  |
| RN-SOUTH-14191 | ap-southeast-6 | 4 | B7 |  |
| RN-SOUTH-14191 | ap-southeast-6 | 5 | B7 |  |
| RN-SOUTH-14220 | sa-east-7 | 1 | B7 | dup? |
| RN-SOUTH-14220 | sa-east-7 | 2 | B7 |  |
| RN-SOUTH-14220 | sa-east-7 | 3 | B7 |  |
| RN-SOUTH-14220 | sa-east-7 | 4 | B7 |  |
| RN-SOUTH-14220 | sa-east-7 | 5 | B7 |  |
| RN-SOUTH-14247 | ap-southeast-6 | 1 | B7 |  |
| RN-SOUTH-14247 | ap-southeast-6 | 2 | B7 | recheck |
| RN-SOUTH-14247 | ap-southeast-6 | 3 | B7 |  |
| RN-SOUTH-14247 | ap-southeast-6 | 4 | B7 |  |
| RN-SOUTH-14247 | ap-southeast-6 | 5 | B7 |  |
| RN-SOUTH-14275 | sa-east-7 | 1 | B7 | late? |
| RN-SOUTH-14275 | sa-east-7 | 2 | B7 |  |
| RN-SOUTH-14275 | sa-east-7 | 3 | B7 |  |
| RN-SOUTH-14275 | sa-east-7 | 4 | B7 |  |
| RN-SOUTH-14275 | sa-east-7 | 5 | B7 |  |
| RN-SOUTH-14301 | ap-southeast-6 | 1 | B7 |  |
| RN-SOUTH-14301 | ap-southeast-6 | 2 | B7 |  |
| RN-SOUTH-14301 | ap-southeast-6 | 3 | B7 |  |
| RN-SOUTH-14301 | ap-southeast-6 | 4 | B7 |  |
| RN-SOUTH-14301 | ap-southeast-6 | 5 | B7 |  |
| RN-SOUTH-14331 | sa-east-7 | 1 | B7 | recheck |
| RN-SOUTH-14331 | sa-east-7 | 2 | B7 |  |
| RN-SOUTH-14331 | sa-east-7 | 3 | B7 |  |
| RN-SOUTH-14331 | sa-east-7 | 4 | B7 |  |
| RN-SOUTH-14331 | sa-east-7 | 5 | B7 |  |
| RN-SOUTH-14360 | ap-southeast-6 | 1 | B7 |  |
| RN-SOUTH-14360 | ap-southeast-6 | 2 | B7 |  |
| RN-SOUTH-14360 | ap-southeast-6 | 3 | B7 |  |
| RN-SOUTH-14360 | ap-southeast-6 | 4 | B7 |  |
| RN-SOUTH-14360 | ap-southeast-6 | 5 | B7 |  |
| RN-SOUTH-14385 | sa-east-7 | 1 | B7 |  |
| RN-SOUTH-14385 | sa-east-7 | 2 | B7 |  |
| RN-SOUTH-14385 | sa-east-7 | 3 | B7 |  |
| RN-SOUTH-14385 | sa-east-7 | 4 | B7 |  |
| RN-SOUTH-14385 | ap-southeast-6 | 5 | B7 |  |
| RN-SOUTH-14415 | ap-southeast-6 | 1 | B7 | dup? |
| RN-SOUTH-14415 | ap-southeast-6 | 2 | B7 |  |
| RN-SOUTH-14415 | sa-east-7 | 3 | B7 |  |
| RN-SOUTH-14415 | sa-east-7 | 3 | B7 |  |
| RN-SOUTH-14415 | ap-southeast-6 | 4 | B7 |  |
| RN-SOUTH-14415 | ap-southeast-6 | 5 | B7 |  |
| RN-SOUTH-14441 | sa-east-7 | 1 | B7 |  |
| RN-SOUTH-14441 | sa-east-7 | 2 | B7 |  |
| RN-SOUTH-14441 | sa-east-7 | 3 | B7 |  |
| RN-SOUTH-14441 | sa-east-7 | 4 | B7 |  |
| RN-SOUTH-14441 | sa-east-7 | 5 | B7 |  |
| RN-SOUTH-14466 | ap-southeast-6 | 1 | B7 |  |
| RN-SOUTH-14466 | ap-southeast-6 | 2 | B7 |  |
| RN-SOUTH-14466 | ap-southeast-6 | 3 | B7 | late? |
| RN-SOUTH-14466 | ap-southeast-6 | 4 | B7 |  |
| RN-SOUTH-14466 | ap-southeast-6 | 5 | B7 | dup? |
| RN-SOUTH-14500 | sa-east-7 | 1 | B7 |  |
| RN-SOUTH-14500 | sa-east-7 | 2 | B7 | dup? |
| RN-SOUTH-14500 | sa-east-7 | 3 | B7 |  |
| RN-SOUTH-14500 | sa-east-7 | 4 | B7 |  |
| RN-SOUTH-14500 | sa-east-7 | 5 | B7 |  |
| RN-SOUTH-14528 | ap-southeast-6 | 1 | B7 |  |
| RN-SOUTH-14528 | ap-southeast-6 | 2 | B7 |  |
| RN-SOUTH-14528 | ap-southeast-6 | 3 | B7 |  |
| RN-SOUTH-14528 | ap-southeast-6 | 4 | B7 |  |
| RN-SOUTH-14528 | ap-southeast-6 | 5 | B7 |  |
| RN-SOUTH-14554 | sa-east-7 | 1 | B7 |  |
| RN-SOUTH-14554 | sa-east-7 | 2 | B7 |  |
| RN-SOUTH-14554 | sa-east-7 | 3 | B7 |  |
| RN-SOUTH-14554 | sa-east-7 | 4 | B7 |  |
| RN-SOUTH-14554 | sa-east-7 | 5 | B7 |  |
| RN-SOUTH-14583 | ap-southeast-6 | 1 | B7 |  |
| RN-SOUTH-14583 | ap-southeast-6 | 2 | B7 |  |
| RN-SOUTH-14583 | ap-southeast-6 | 3 | B7 |  |
| RN-SOUTH-14583 | ap-southeast-6 | 4 | B7 |  |
| RN-SOUTH-14583 | ap-southeast-6 | 5 | B7 |  |
| RN-SOUTH-14607 | sa-east-7 | 1 | B7 |  |
| RN-SOUTH-14607 | sa-east-7 | 2 | B7 |  |
| RN-SOUTH-14607 | ap-southeast-6 | 3 | B7 |  |
| RN-SOUTH-14607 | sa-east-7 | 4 | B7 |  |
| RN-SOUTH-14607 | sa-east-7 | 5 | B7 |  |
| RN-SOUTH-14634 | ap-southeast-6 | 1 | B7 |  |
| RN-SOUTH-14634 | ap-southeast-6 | 2 | B7 |  |
| RN-SOUTH-14634 | ap-southeast-6 | 3 | B7 |  |
| RN-SOUTH-14634 | ap-southeast-6 | 4 | B7 | late? |
| RN-SOUTH-14634 | ap-southeast-6 | 5 | B7 |  |
| RN-SOUTH-14662 | sa-east-7 | 1 | B7 |  |
| RN-SOUTH-14662 | sa-east-7 | 2 | B7 | dup? |
| RN-SOUTH-14662 | sa-east-7 | 3 | B7 |  |
| RN-SOUTH-14662 | sa-east-7 | 4 | B7 |  |
| RN-SOUTH-14662 | sa-east-7 | 5 | B7 |  |
| RN-SOUTH-14695 | ap-southeast-6 | 1 | B7 |  |
| RN-SOUTH-14695 | ap-southeast-6 | 2 | B7 |  |
| RN-SOUTH-14695 | ap-southeast-6 | 3 | B7 |  |
| RN-SOUTH-14695 | sa-east-7 | 4 | B7 |  |
| RN-SOUTH-14695 | ap-southeast-6 | 5 | B7 | void? |
| RN-SOUTH-14723 | sa-east-7 | 1 | B7 | void? |
| RN-SOUTH-14723 | sa-east-7 | 2 | B7 |  |
| RN-SOUTH-14723 | sa-east-7 | 3 | B7 | void? |
| RN-SOUTH-14723 | ap-southeast-6 | 4 | B7 |  |
| RN-SOUTH-14723 | sa-east-7 | 5 | B7 |  |
| RN-SOUTH-14750 | ap-southeast-6 | 1 | B7 |  |
| RN-SOUTH-14750 | ap-southeast-6 | 2 | B7 |  |
| RN-SOUTH-14750 | ap-southeast-6 | 3 | B7 |  |
| RN-SOUTH-14750 | ap-southeast-6 | 4 | B7 |  |
| RN-SOUTH-14750 | ap-southeast-6 | 5 | B7 |  |
| RN-SOUTH-14774 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-14774 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-14774 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-14774 | sa-east-7 | 4 | B8 | late? |
| RN-SOUTH-14774 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-14808 | ap-southeast-6 | 1 | B8 | recheck |
| RN-SOUTH-14808 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-14808 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-14808 | ap-southeast-6 | 4 | B8 | recheck |
| RN-SOUTH-14808 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-14834 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-14834 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-14834 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-14834 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-14834 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-14864 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-14864 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-14864 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-14864 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-14864 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-14888 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-14888 | sa-east-7 | 2 | B8 | recheck |
| RN-SOUTH-14888 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-14888 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-14888 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-14916 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-14916 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-14916 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-14916 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-14916 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-14916 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-14946 | sa-east-7 | 1 | B8 | late? |
| RN-SOUTH-14946 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-14946 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-14946 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-14946 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-14973 | ap-southeast-6 | 1 | B8 | late? |
| RN-SOUTH-14973 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-14973 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-14973 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-14973 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-14973 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-15000 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-15000 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-15000 | sa-east-7 | 3 | B8 | recheck |
| RN-SOUTH-15000 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-15000 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-15028 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-15028 | ap-southeast-6 | 2 | B8 | dup? |
| RN-SOUTH-15028 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-15028 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-15028 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-15055 | sa-east-7 | 1 | B8 | late? |
| RN-SOUTH-15055 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-15055 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-15055 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-15055 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-15086 | ap-southeast-6 | 1 | B8 | void? |
| RN-SOUTH-15086 | ap-southeast-6 | 2 | B8 | dup? |
| RN-SOUTH-15086 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-15086 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-15086 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-15113 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-15113 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-15113 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-15113 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-15113 | sa-east-7 | 5 | B8 | late? |
| RN-SOUTH-15144 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-15144 | ap-southeast-6 | 2 | B8 | late? |
| RN-SOUTH-15144 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-15144 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-15144 | ap-southeast-6 | 5 | B8 | dup? |
| RN-SOUTH-15170 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-15170 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-15170 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-15170 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-15170 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-15170 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-15197 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-15197 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-15197 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-15197 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-15197 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-15222 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-15222 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-15222 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-15222 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-15222 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-15222 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-15250 | ap-southeast-6 | 1 | B8 | void? |
| RN-SOUTH-15250 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-15250 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-15250 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-15250 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-15278 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-15278 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-15278 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-15278 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-15278 | sa-east-7 | 5 | B8 | late? |
| RN-SOUTH-15311 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-15311 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-15311 | ap-southeast-6 | 2 | B8 | dup? |
| RN-SOUTH-15311 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-15311 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-15311 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-15335 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-15335 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-15335 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-15335 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-15335 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-15365 | ap-southeast-6 | 1 | B8 | late? |
| RN-SOUTH-15365 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-15365 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-15365 | ap-southeast-6 | 4 | B8 | dup? |
| RN-SOUTH-15365 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-15392 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-15392 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-15392 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-15392 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-15392 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-15392 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-15421 | ap-southeast-6 | 1 | B8 | recheck |
| RN-SOUTH-15421 | ap-southeast-6 | 2 | B8 | void? |
| RN-SOUTH-15421 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-15421 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-15421 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-15452 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-15452 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-15452 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-15452 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-15452 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-15480 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-15480 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-15480 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-15480 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-15480 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-15504 | sa-east-7 | 1 | B8 | recheck |
| RN-SOUTH-15504 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-15504 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-15504 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-15504 | sa-east-7 | 5 | B8 | recheck |
| RN-SOUTH-15535 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-15535 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-15535 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-15535 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-15535 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-15563 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-15563 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-15563 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-15563 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-15563 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-15588 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-15588 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-15588 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-15588 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-15588 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-15620 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-15620 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-15620 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-15620 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-15620 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-15643 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-15643 | ap-southeast-6 | 2 | B8 | dup? |
| RN-SOUTH-15643 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-15643 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-15643 | ap-southeast-6 | 5 | B8 | void? |
| RN-SOUTH-15676 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-15676 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-15676 | sa-east-7 | 3 | B8 | void? |
| RN-SOUTH-15676 | sa-east-7 | 4 | B8 | void? |
| RN-SOUTH-15676 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-15676 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-15699 | ap-southeast-6 | 1 | B8 | recheck |
| RN-SOUTH-15699 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-15699 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-15699 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-15699 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-15732 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-15732 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-15732 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-15732 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-15732 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-15756 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-15756 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-15756 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-15756 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-15756 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-15782 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-15782 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-15782 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-15782 | sa-east-7 | 4 | B8 | void? |
| RN-SOUTH-15782 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-15814 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-15814 | ap-southeast-6 | 2 | B8 | recheck |
| RN-SOUTH-15814 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-15814 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-15814 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-15838 | sa-east-7 | 1 | B8 | void? |
| RN-SOUTH-15838 | sa-east-7 | 1 | B8 | void? |
| RN-SOUTH-15838 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-15838 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-15838 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-15838 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-15871 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-15871 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-15871 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-15871 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-15871 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-15871 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-15896 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-15896 | sa-east-7 | 2 | B8 | void? |
| RN-SOUTH-15896 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-15896 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-15896 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-15922 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-15922 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-15922 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-15922 | ap-southeast-6 | 3 | B8 | void? |
| RN-SOUTH-15922 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-15922 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-15953 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-15953 | sa-east-7 | 2 | B8 | late? |
| RN-SOUTH-15953 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-15953 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-15953 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-15982 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-15982 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-15982 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-15982 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-15982 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-16009 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-16009 | sa-east-7 | 2 | B8 | late? |
| RN-SOUTH-16009 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-16009 | sa-east-7 | 4 | B8 | late? |
| RN-SOUTH-16009 | sa-east-7 | 4 | B8 | late? |
| RN-SOUTH-16009 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-16037 | ap-southeast-6 | 1 | B8 | dup? |
| RN-SOUTH-16037 | ap-southeast-6 | 2 | B8 | void? |
| RN-SOUTH-16037 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-16037 | ap-southeast-6 | 4 | B8 | recheck |
| RN-SOUTH-16037 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-16065 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-16065 | sa-east-7 | 2 | B8 | late? |
| RN-SOUTH-16065 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-16065 | sa-east-7 | 4 | B8 | dup? |
| RN-SOUTH-16065 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-16065 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-16093 | ap-southeast-6 | 1 | B8 | recheck |
| RN-SOUTH-16093 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-16093 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-16093 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-16093 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-16124 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-16124 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-16124 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-16124 | sa-east-7 | 4 | B8 | void? |
| RN-SOUTH-16124 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-16148 | ap-southeast-6 | 1 | B8 | dup? |
| RN-SOUTH-16148 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-16148 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-16148 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-16148 | ap-southeast-6 | 4 | B8 | recheck |
| RN-SOUTH-16148 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-16179 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-16179 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-16179 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-16179 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-16179 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-16205 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-16205 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-16205 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-16205 | ap-southeast-6 | 4 | B8 | late? |
| RN-SOUTH-16205 | ap-southeast-6 | 5 | B8 | void? |
| RN-SOUTH-16236 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-16236 | sa-east-7 | 2 | B8 | dup? |
| RN-SOUTH-16236 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-16236 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-16236 | sa-east-7 | 5 | B8 | void? |
| RN-SOUTH-16259 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-16259 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-16259 | ap-southeast-6 | 3 | B8 | void? |
| RN-SOUTH-16259 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-16259 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-16289 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-16289 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-16289 | ap-southeast-6 | 3 | B8 | void? |
| RN-SOUTH-16289 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-16289 | sa-east-7 | 5 | B8 | recheck |
| RN-SOUTH-16318 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-16318 | ap-southeast-6 | 2 | B8 | late? |
| RN-SOUTH-16318 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-16318 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-16318 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-16348 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-16348 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-16348 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-16348 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-16348 | sa-east-7 | 5 | B8 | late? |
| RN-SOUTH-16371 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-16371 | ap-southeast-6 | 2 | B8 | late? |
| RN-SOUTH-16371 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-16371 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-16371 | ap-southeast-6 | 5 | B8 | dup? |
| RN-SOUTH-16401 | sa-east-7 | 1 | B8 | dup? |
| RN-SOUTH-16401 | sa-east-7 | 2 | B8 | dup? |
| RN-SOUTH-16401 | sa-east-7 | 3 | B8 | recheck |
| RN-SOUTH-16401 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-16401 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-16432 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-16432 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-16432 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-16432 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-16432 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-16456 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-16456 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-16456 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-16456 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-16456 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-16484 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-16484 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-16484 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-16484 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-16484 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-16512 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-16512 | sa-east-7 | 2 | B8 | late? |
| RN-SOUTH-16512 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-16512 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-16512 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-16543 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-16543 | ap-southeast-6 | 2 | B8 | recheck |
| RN-SOUTH-16543 | ap-southeast-6 | 3 | B8 | dup? |
| RN-SOUTH-16543 | ap-southeast-6 | 4 | B8 | dup? |
| RN-SOUTH-16543 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-16569 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-16569 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-16569 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-16569 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-16569 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-16598 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-16598 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-16598 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-16598 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-16598 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-16622 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-16622 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-16622 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-16622 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-16622 | sa-east-7 | 5 | B8 | late? |
| RN-SOUTH-16656 | ap-southeast-6 | 1 | B8 | dup? |
| RN-SOUTH-16656 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-16656 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-16656 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-16656 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-16681 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-16681 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-16681 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-16681 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-16681 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-16709 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-16709 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-16709 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-16709 | ap-southeast-6 | 4 | B8 | recheck |
| RN-SOUTH-16709 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-16734 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-16734 | sa-east-7 | 2 | B8 | recheck |
| RN-SOUTH-16734 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-16734 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-16734 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-16762 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-16762 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-16762 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-16762 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-16762 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-16792 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-16792 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-16792 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-16792 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-16792 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-16822 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-16822 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-16822 | ap-southeast-6 | 3 | B8 | void? |
| RN-SOUTH-16822 | ap-southeast-6 | 4 | B8 | dup? |
| RN-SOUTH-16822 | ap-southeast-6 | 5 | B8 | dup? |
| RN-SOUTH-16851 | sa-east-7 | 1 | B8 | void? |
| RN-SOUTH-16851 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-16851 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-16851 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-16851 | sa-east-7 | 5 | B8 | void? |
| RN-SOUTH-16880 | ap-southeast-6 | 1 | B8 | recheck |
| RN-SOUTH-16880 | ap-southeast-6 | 2 | B8 | late? |
| RN-SOUTH-16880 | ap-southeast-6 | 3 | B8 | void? |
| RN-SOUTH-16880 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-16880 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-16908 | sa-east-7 | 1 | B8 | dup? |
| RN-SOUTH-16908 | sa-east-7 | 2 | B8 | recheck |
| RN-SOUTH-16908 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-16908 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-16908 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-16931 | ap-southeast-6 | 1 | B8 | void? |
| RN-SOUTH-16931 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-16931 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-16931 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-16931 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-16959 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-16959 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-16959 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-16959 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-16959 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-16988 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-16988 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-16988 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-16988 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-16988 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-17016 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-17016 | sa-east-7 | 2 | B8 | recheck |
| RN-SOUTH-17016 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-17016 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-17016 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-17046 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-17046 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-17046 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-17046 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-17046 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-17076 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-17076 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-17076 | sa-east-7 | 3 | B8 | void? |
| RN-SOUTH-17076 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-17076 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-17104 | ap-southeast-6 | 1 | B8 | late? |
| RN-SOUTH-17104 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-17104 | ap-southeast-6 | 3 | B8 | recheck |
| RN-SOUTH-17104 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-17104 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-17130 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-17130 | sa-east-7 | 2 | B8 | dup? |
| RN-SOUTH-17130 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-17130 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-17130 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-17155 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-17155 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-17155 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-17155 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-17155 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-17155 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-17188 | sa-east-7 | 1 | B8 | dup? |
| RN-SOUTH-17188 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-17188 | sa-east-7 | 3 | B8 | late? |
| RN-SOUTH-17188 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-17188 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-17210 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-17210 | ap-southeast-6 | 2 | B8 | recheck |
| RN-SOUTH-17210 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-17210 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-17210 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-17243 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-17243 | sa-east-7 | 2 | B8 | recheck |
| RN-SOUTH-17243 | sa-east-7 | 3 | B8 | void? |
| RN-SOUTH-17243 | sa-east-7 | 4 | B8 | void? |
| RN-SOUTH-17243 | sa-east-7 | 5 | B8 | recheck |
| RN-SOUTH-17271 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-17271 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-17271 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-17271 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-17271 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-17294 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-17294 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-17294 | sa-east-7 | 3 | B8 | recheck |
| RN-SOUTH-17294 | sa-east-7 | 4 | B8 | dup? |
| RN-SOUTH-17294 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-17325 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-17325 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-17325 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-17325 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-17325 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-17353 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-17353 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-17353 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-17353 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-17353 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-17382 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-17382 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-17382 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-17382 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-17382 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-17409 | sa-east-7 | 1 | B8 | late? |
| RN-SOUTH-17409 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-17409 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-17409 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-17409 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-17440 | ap-southeast-6 | 1 | B8 | void? |
| RN-SOUTH-17440 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-17440 | ap-southeast-6 | 3 | B8 | void? |
| RN-SOUTH-17440 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-17440 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-17464 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-17464 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-17464 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-17464 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-17464 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-17490 | ap-southeast-6 | 1 | B8 | late? |
| RN-SOUTH-17490 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-17490 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-17490 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-17490 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-17519 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-17519 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-17519 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-17519 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-17519 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-17548 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-17548 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-17548 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-17548 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-17548 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-17574 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-17574 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-17574 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-17574 | sa-east-7 | 4 | B8 | late? |
| RN-SOUTH-17574 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-17574 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-17604 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-17604 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-17604 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-17604 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-17604 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-17604 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-17633 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-17633 | sa-east-7 | 2 | B8 | recheck |
| RN-SOUTH-17633 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-17633 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-17633 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-17659 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-17659 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-17659 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-17659 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-17659 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-17691 | sa-east-7 | 1 | B8 | recheck |
| RN-SOUTH-17691 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-17691 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-17691 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-17691 | sa-east-7 | 5 | B8 | void? |
| RN-SOUTH-17716 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-17716 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-17716 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-17716 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-17716 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-17746 | sa-east-7 | 1 | B8 | recheck |
| RN-SOUTH-17746 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-17746 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-17746 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-17746 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-17770 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-17770 | sa-east-7 | 2 | B8 | recheck |
| RN-SOUTH-17770 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-17770 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-17770 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-17798 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-17798 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-17798 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-17798 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-17798 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-17828 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-17828 | ap-southeast-6 | 2 | B8 | void? |
| RN-SOUTH-17828 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-17828 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-17828 | ap-southeast-6 | 5 | B8 | recheck |
| RN-SOUTH-17854 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-17854 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-17854 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-17854 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-17854 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-17884 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-17884 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-17884 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-17884 | sa-east-7 | 4 | B8 | late? |
| RN-SOUTH-17884 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-17884 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-17913 | sa-east-7 | 1 | B8 | dup? |
| RN-SOUTH-17913 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-17913 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-17913 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-17913 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-17913 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-17942 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-17942 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-17942 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-17942 | ap-southeast-6 | 4 | B8 | void? |
| RN-SOUTH-17942 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-17967 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-17967 | sa-east-7 | 2 | B8 | void? |
| RN-SOUTH-17967 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-17967 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-17967 | sa-east-7 | 5 | B8 | recheck |
| RN-SOUTH-17997 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-17997 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-17997 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-17997 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-17997 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-18023 | sa-east-7 | 1 | B8 | void? |
| RN-SOUTH-18023 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-18023 | sa-east-7 | 3 | B8 | late? |
| RN-SOUTH-18023 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-18023 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-18051 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-18051 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-18051 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-18051 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-18051 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-18082 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-18082 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-18082 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-18082 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-18082 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-18111 | ap-southeast-6 | 1 | B8 | void? |
| RN-SOUTH-18111 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-18111 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-18111 | sa-east-7 | 4 | B8 | recheck |
| RN-SOUTH-18111 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-18136 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-18136 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-18136 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-18136 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-18136 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-18168 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-18168 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-18168 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-18168 | ap-southeast-6 | 4 | B8 | void? |
| RN-SOUTH-18168 | ap-southeast-6 | 5 | B8 | dup? |
| RN-SOUTH-18195 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-18195 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-18195 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-18195 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-18195 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-18219 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-18219 | ap-southeast-6 | 2 | B8 | late? |
| RN-SOUTH-18219 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-18219 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-18219 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-18247 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-18247 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-18247 | sa-east-7 | 3 | B8 | void? |
| RN-SOUTH-18247 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-18247 | sa-east-7 | 5 | B8 | dup? |
| RN-SOUTH-18277 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-18277 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-18277 | ap-southeast-6 | 3 | B8 | recheck |
| RN-SOUTH-18277 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-18277 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-18303 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-18303 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-18303 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-18303 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-18303 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-18336 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-18336 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-18336 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-18336 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-18336 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-18363 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-18363 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-18363 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-18363 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-18363 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-18392 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-18392 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-18392 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-18392 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-18392 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-18415 | sa-east-7 | 1 | B8 | dup? |
| RN-SOUTH-18415 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-18415 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-18415 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-18415 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-18446 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-18446 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-18446 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-18446 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-18446 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-18446 | ap-southeast-6 | 5 | B8 | dup? |
| RN-SOUTH-18470 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-18470 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-18470 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-18470 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-18470 | sa-east-7 | 5 | B8 | recheck |
| RN-SOUTH-18504 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-18504 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-18504 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-18504 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-18504 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-18526 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-18526 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-18526 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-18526 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-18526 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-18526 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-18557 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-18557 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-18557 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-18557 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-18557 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-18586 | sa-east-7 | 1 | B8 | dup? |
| RN-SOUTH-18586 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-18586 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-18586 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-18586 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-18612 | ap-southeast-6 | 1 | B8 | dup? |
| RN-SOUTH-18612 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-18612 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-18612 | ap-southeast-6 | 4 | B8 | recheck |
| RN-SOUTH-18612 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-18640 | sa-east-7 | 1 | B8 | void? |
| RN-SOUTH-18640 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-18640 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-18640 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-18640 | sa-east-7 | 5 | B8 | late? |
| RN-SOUTH-18668 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-18668 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-18668 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-18668 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-18668 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-18694 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-18694 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-18694 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-18694 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-18694 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-18723 | ap-southeast-6 | 1 | B8 | recheck |
| RN-SOUTH-18723 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-18723 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-18723 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-18723 | ap-southeast-6 | 5 | B8 | dup? |
| RN-SOUTH-18752 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-18752 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-18752 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-18752 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-18752 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-18782 | ap-southeast-6 | 1 | B8 | late? |
| RN-SOUTH-18782 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-18782 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-18782 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-18782 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-18810 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-18810 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-18810 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-18810 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-18810 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-18834 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-18834 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-18834 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-18834 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-18834 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-18866 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-18866 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-18866 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-18866 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-18866 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-18895 | ap-southeast-6 | 1 | B8 | dup? |
| RN-SOUTH-18895 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-18895 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-18895 | ap-southeast-6 | 4 | B8 | void? |
| RN-SOUTH-18895 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-18918 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-18918 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-18918 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-18918 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-18918 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-18948 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-18948 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-18948 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-18948 | ap-southeast-6 | 4 | B8 | late? |
| RN-SOUTH-18948 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-18979 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-18979 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-18979 | sa-east-7 | 3 | B8 | void? |
| RN-SOUTH-18979 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-18979 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-19002 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-19002 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-19002 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-19002 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-19002 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-19033 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-19033 | sa-east-7 | 2 | B8 | late? |
| RN-SOUTH-19033 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-19033 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-19033 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-19058 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-19058 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-19058 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-19058 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-19058 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-19091 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-19091 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-19091 | sa-east-7 | 3 | B8 | late? |
| RN-SOUTH-19091 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-19091 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-19116 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-19116 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-19116 | ap-southeast-6 | 3 | B8 | void? |
| RN-SOUTH-19116 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-19116 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-19147 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-19147 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-19147 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-19147 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-19147 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-19170 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-19170 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-19170 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-19170 | ap-southeast-6 | 4 | B8 | late? |
| RN-SOUTH-19170 | ap-southeast-6 | 5 | B8 | late? |
| RN-SOUTH-19204 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-19204 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-19204 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-19204 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-19204 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-19227 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-19227 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-19227 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-19227 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-19227 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-19227 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-19227 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-19258 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-19258 | sa-east-7 | 2 | B8 | late? |
| RN-SOUTH-19258 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-19258 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-19258 | sa-east-7 | 5 | B8 | recheck |
| RN-SOUTH-19288 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-19288 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-19288 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-19288 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-19288 | ap-southeast-6 | 4 | B8 | recheck |
| RN-SOUTH-19288 | sa-east-7 | 5 | B8 | void? |
| RN-SOUTH-19312 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-19312 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-19312 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-19312 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-19312 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-19343 | ap-southeast-6 | 1 | B8 | late? |
| RN-SOUTH-19343 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-19343 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-19343 | ap-southeast-6 | 4 | B8 | recheck |
| RN-SOUTH-19343 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-19370 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-19370 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-19370 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-19370 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-19370 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-19397 | ap-southeast-6 | 1 | B8 | dup? |
| RN-SOUTH-19397 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-19397 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-19397 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-19397 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-19422 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-19422 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-19422 | sa-east-7 | 3 | B8 |  |
| RN-SOUTH-19422 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-19422 | sa-east-7 | 5 | B8 |  |
| RN-SOUTH-19454 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-19454 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-19454 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-19454 | ap-southeast-6 | 4 | B8 |  |
| RN-SOUTH-19454 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-19480 | sa-east-7 | 1 | B8 |  |
| RN-SOUTH-19480 | sa-east-7 | 2 | B8 |  |
| RN-SOUTH-19480 | sa-east-7 | 3 | B8 | dup? |
| RN-SOUTH-19480 | sa-east-7 | 4 | B8 |  |
| RN-SOUTH-19480 | sa-east-7 | 5 | B8 | recheck |
| RN-SOUTH-19509 | ap-southeast-6 | 1 | B8 |  |
| RN-SOUTH-19509 | ap-southeast-6 | 2 | B8 |  |
| RN-SOUTH-19509 | ap-southeast-6 | 3 | B8 |  |
| RN-SOUTH-19509 | ap-southeast-6 | 4 | B8 | void? |
| RN-SOUTH-19509 | ap-southeast-6 | 5 | B8 |  |
| RN-SOUTH-19536 | sa-east-7 | 1 | B9 | void? |
| RN-SOUTH-19536 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-19536 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-19536 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-19536 | sa-east-7 | 4 | B9 | void? |
| RN-SOUTH-19536 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-19567 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-19567 | ap-southeast-6 | 2 | B9 | dup? |
| RN-SOUTH-19567 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-19567 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-19567 | sa-east-7 | 5 | B9 | void? |
| RN-SOUTH-19596 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-19596 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-19596 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-19596 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-19596 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-19619 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-19619 | ap-southeast-6 | 2 | B9 | recheck |
| RN-SOUTH-19619 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-19619 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-19619 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-19646 | sa-east-7 | 1 | B9 | recheck |
| RN-SOUTH-19646 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-19646 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-19646 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-19646 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-19646 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-19675 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-19675 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-19675 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-19675 | ap-southeast-6 | 4 | B9 | recheck |
| RN-SOUTH-19675 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-19706 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-19706 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-19706 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-19706 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-19706 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-19731 | ap-southeast-6 | 1 | B9 | dup? |
| RN-SOUTH-19731 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-19731 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-19731 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-19731 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-19761 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-19761 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-19761 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-19761 | sa-east-7 | 4 | B9 | dup? |
| RN-SOUTH-19761 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-19788 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-19788 | ap-southeast-6 | 2 | B9 | recheck |
| RN-SOUTH-19788 | sa-east-7 | 3 | B9 | dup? |
| RN-SOUTH-19788 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-19788 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-19820 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-19820 | sa-east-7 | 2 | B9 | dup? |
| RN-SOUTH-19820 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-19820 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-19820 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-19845 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-19845 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-19845 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-19845 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-19845 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-19876 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-19876 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-19876 | sa-east-7 | 3 | B9 | recheck |
| RN-SOUTH-19876 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-19876 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-19903 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-19903 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-19903 | ap-southeast-6 | 3 | B9 | recheck |
| RN-SOUTH-19903 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-19903 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-19929 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-19929 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-19929 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-19929 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-19929 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-19929 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-19956 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-19956 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-19956 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-19956 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-19956 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-19956 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-19956 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-19983 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-19983 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-19983 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-19983 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-19983 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-20016 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-20016 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-20016 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-20016 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-20016 | ap-southeast-6 | 5 | B9 | recheck |
| RN-SOUTH-20043 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-20043 | sa-east-7 | 2 | B9 | recheck |
| RN-SOUTH-20043 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-20043 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-20043 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-20043 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-20072 | ap-southeast-6 | 1 | B9 | void? |
| RN-SOUTH-20072 | ap-southeast-6 | 1 | B9 | void? |
| RN-SOUTH-20072 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-20072 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-20072 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-20072 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-20095 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-20095 | sa-east-7 | 2 | B9 | dup? |
| RN-SOUTH-20095 | sa-east-7 | 3 | B9 | recheck |
| RN-SOUTH-20095 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-20095 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-20124 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-20124 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-20124 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-20124 | ap-southeast-6 | 4 | B9 | void? |
| RN-SOUTH-20124 | ap-southeast-6 | 5 | B9 | void? |
| RN-SOUTH-20152 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-20152 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-20152 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-20152 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-20152 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-20183 | ap-southeast-6 | 1 | B9 | dup? |
| RN-SOUTH-20183 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-20183 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-20183 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-20183 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-20206 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-20206 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-20206 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-20206 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-20206 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-20206 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-20234 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-20234 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-20234 | ap-southeast-6 | 3 | B9 | dup? |
| RN-SOUTH-20234 | ap-southeast-6 | 3 | B9 | dup? |
| RN-SOUTH-20234 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-20234 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-20267 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-20267 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-20267 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-20267 | sa-east-7 | 4 | B9 | void? |
| RN-SOUTH-20267 | sa-east-7 | 5 | B9 | recheck |
| RN-SOUTH-20295 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-20295 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-20295 | ap-southeast-6 | 3 | B9 | recheck |
| RN-SOUTH-20295 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-20295 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-20318 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-20318 | sa-east-7 | 2 | B9 | recheck |
| RN-SOUTH-20318 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-20318 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-20318 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-20351 | ap-southeast-6 | 1 | B9 | recheck |
| RN-SOUTH-20351 | ap-southeast-6 | 2 | B9 | late? |
| RN-SOUTH-20351 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-20351 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-20351 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-20379 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-20379 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-20379 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-20379 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-20379 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-20403 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-20403 | ap-southeast-6 | 2 | B9 | dup? |
| RN-SOUTH-20403 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-20403 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-20403 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-20436 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-20436 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-20436 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-20436 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-20436 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-20464 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-20464 | ap-southeast-6 | 2 | B9 | void? |
| RN-SOUTH-20464 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-20464 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-20464 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-20489 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-20489 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-20489 | sa-east-7 | 3 | B9 | recheck |
| RN-SOUTH-20489 | sa-east-7 | 4 | B9 | dup? |
| RN-SOUTH-20489 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-20516 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-20516 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-20516 | ap-southeast-6 | 3 | B9 | late? |
| RN-SOUTH-20516 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-20516 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-20547 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-20547 | sa-east-7 | 2 | B9 | void? |
| RN-SOUTH-20547 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-20547 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-20547 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-20576 | ap-southeast-6 | 1 | B9 | dup? |
| RN-SOUTH-20576 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-20576 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-20576 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-20576 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-20602 | sa-east-7 | 1 | B9 | recheck |
| RN-SOUTH-20602 | sa-east-7 | 2 | B9 | late? |
| RN-SOUTH-20602 | sa-east-7 | 3 | B9 | dup? |
| RN-SOUTH-20602 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-20602 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-20627 | ap-southeast-6 | 1 | B9 | recheck |
| RN-SOUTH-20627 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-20627 | ap-southeast-6 | 3 | B9 | recheck |
| RN-SOUTH-20627 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-20627 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-20656 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-20656 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-20656 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-20656 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-20656 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-20656 | sa-east-7 | 5 | B9 | void? |
| RN-SOUTH-20688 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-20688 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-20688 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-20688 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-20688 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-20711 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-20711 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-20711 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-20711 | sa-east-7 | 3 | B9 | late? |
| RN-SOUTH-20711 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-20711 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-20742 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-20742 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-20742 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-20742 | ap-southeast-6 | 4 | B9 | dup? |
| RN-SOUTH-20742 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-20772 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-20772 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-20772 | sa-east-7 | 3 | B9 | recheck |
| RN-SOUTH-20772 | sa-east-7 | 3 | B9 | recheck |
| RN-SOUTH-20772 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-20772 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-20794 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-20794 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-20794 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-20794 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-20794 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-20828 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-20828 | sa-east-7 | 2 | B9 | recheck |
| RN-SOUTH-20828 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-20828 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-20828 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-20850 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-20850 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-20850 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-20850 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-20850 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-20850 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-20881 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-20881 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-20881 | ap-southeast-6 | 3 | B9 | void? |
| RN-SOUTH-20881 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-20881 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-20910 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-20910 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-20910 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-20910 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-20910 | ap-southeast-6 | 5 | B9 | void? |
| RN-SOUTH-20934 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-20934 | sa-east-7 | 2 | B9 | recheck |
| RN-SOUTH-20934 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-20934 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-20934 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-20962 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-20962 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-20962 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-20962 | ap-southeast-6 | 4 | B9 | dup? |
| RN-SOUTH-20962 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-20996 | sa-east-7 | 1 | B9 | recheck |
| RN-SOUTH-20996 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-20996 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-20996 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-20996 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-20996 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-21020 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-21020 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-21020 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-21020 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-21020 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-21052 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-21052 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-21052 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-21052 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-21052 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-21076 | ap-southeast-6 | 1 | B9 | void? |
| RN-SOUTH-21076 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-21076 | ap-southeast-6 | 3 | B9 | dup? |
| RN-SOUTH-21076 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-21076 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-21106 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-21106 | sa-east-7 | 2 | B9 | late? |
| RN-SOUTH-21106 | sa-east-7 | 3 | B9 | void? |
| RN-SOUTH-21106 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-21106 | sa-east-7 | 5 | B9 | dup? |
| RN-SOUTH-21131 | ap-southeast-6 | 1 | B9 | recheck |
| RN-SOUTH-21131 | ap-southeast-6 | 2 | B9 | recheck |
| RN-SOUTH-21131 | ap-southeast-6 | 3 | B9 | void? |
| RN-SOUTH-21131 | ap-southeast-6 | 4 | B9 | late? |
| RN-SOUTH-21131 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-21161 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-21161 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-21161 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-21161 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-21161 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-21189 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-21189 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-21189 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-21189 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-21189 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-21215 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-21215 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-21215 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-21215 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-21215 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-21245 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-21245 | ap-southeast-6 | 2 | B9 | dup? |
| RN-SOUTH-21245 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-21245 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-21245 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-21274 | sa-east-7 | 1 | B9 | void? |
| RN-SOUTH-21274 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-21274 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-21274 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-21274 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-21300 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-21300 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-21300 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-21300 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-21300 | ap-southeast-6 | 5 | B9 | late? |
| RN-SOUTH-21326 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-21326 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-21326 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-21326 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-21326 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-21356 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-21356 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-21356 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-21356 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-21356 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-21383 | sa-east-7 | 1 | B9 | void? |
| RN-SOUTH-21383 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-21383 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-21383 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-21383 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-21412 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-21412 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-21412 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-21412 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-21412 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-21441 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-21441 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-21441 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-21441 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-21441 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-21466 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-21466 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-21466 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-21466 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-21466 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-21495 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-21495 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-21495 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-21495 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-21495 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-21524 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-21524 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-21524 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-21524 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-21524 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-21555 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-21555 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-21555 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-21555 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-21555 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-21581 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-21581 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-21581 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-21581 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-21581 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-21608 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-21608 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-21608 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-21608 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-21608 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-21638 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-21638 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-21638 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-21638 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-21638 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-21664 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-21664 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-21664 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-21664 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-21664 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-21696 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-21696 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-21696 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-21696 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-21696 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-21721 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-21721 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-21721 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-21721 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-21721 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-21751 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-21751 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-21751 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-21751 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-21751 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-21777 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-21777 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-21777 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-21777 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-21777 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-21804 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-21804 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-21804 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-21804 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-21804 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-21834 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-21834 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-21834 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-21834 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-21834 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-21864 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-21864 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-21864 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-21864 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-21864 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-21892 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-21892 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-21892 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-21892 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-21892 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-21918 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-21918 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-21918 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-21918 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-21918 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-21948 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-21948 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-21948 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-21948 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-21948 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-21975 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-21975 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-21975 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-21975 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-21975 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-22001 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-22001 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-22001 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-22001 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-22001 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-22031 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-22031 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-22031 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-22031 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-22031 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-22056 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-22056 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-22056 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-22056 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-22056 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-22082 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-22082 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-22082 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-22082 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-22082 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-22116 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-22116 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-22116 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-22116 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-22116 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-22140 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-22140 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-22140 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-22140 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-22140 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-22167 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-22167 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-22167 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-22167 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-22167 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-22197 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-22197 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-22197 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-22197 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-22197 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-22222 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-22222 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-22222 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-22222 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-22222 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-22250 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-22250 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-22250 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-22250 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-22250 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-22282 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-22282 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-22282 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-22282 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-22282 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-22311 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-22311 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-22311 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-22311 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-22311 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-22339 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-22339 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-22339 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-22339 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-22339 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-22368 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-22368 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-22368 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-22368 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-22368 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-22396 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-22396 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-22396 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-22396 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-22396 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-22423 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-22423 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-22423 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-22423 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-22423 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-22449 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-22449 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-22449 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-22449 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-22449 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-22480 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-22480 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-22480 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-22480 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-22480 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-22503 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-22503 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-22503 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-22503 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-22503 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-22532 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-22532 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-22532 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-22532 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-22532 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-22564 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-22564 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-22564 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-22564 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-22564 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-22591 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-22591 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-22591 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-22591 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-22591 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-22620 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-22620 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-22620 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-22620 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-22620 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-22645 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-22645 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-22645 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-22645 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-22645 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-22673 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-22673 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-22673 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-22673 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-22673 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-22702 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-22702 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-22702 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-22702 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-22702 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-22732 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-22732 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-22732 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-22732 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-22732 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-22757 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-22757 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-22757 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-22757 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-22757 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-22787 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-22787 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-22787 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-22787 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-22787 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-22812 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-22812 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-22812 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-22812 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-22812 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-22844 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-22844 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-22844 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-22844 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-22844 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-22871 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-22871 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-22871 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-22871 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-22871 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-22894 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-22894 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-22894 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-22894 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-22894 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-22923 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-22923 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-22923 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-22923 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-22923 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-22950 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-22950 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-22950 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-22950 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-22950 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-22981 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-22981 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-22981 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-22981 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-22981 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-23009 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-23009 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-23009 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-23009 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-23009 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-23037 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-23037 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-23037 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-23037 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-23037 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-23066 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-23066 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-23066 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-23066 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-23066 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-23091 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-23091 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-23091 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-23091 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-23091 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-23124 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-23124 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-23124 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-23124 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-23124 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-23151 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-23151 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-23151 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-23151 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-23151 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-23177 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-23177 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-23177 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-23177 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-23177 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-23205 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-23205 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-23205 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-23205 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-23205 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-23235 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-23235 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-23235 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-23235 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-23235 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-23264 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-23264 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-23264 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-23264 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-23264 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-23289 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-23289 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-23289 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-23289 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-23289 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-23319 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-23319 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-23319 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-23319 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-23319 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-23346 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-23346 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-23346 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-23346 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-23346 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-23370 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-23370 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-23370 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-23370 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-23370 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-23398 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-23398 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-23398 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-23398 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-23398 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-23427 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-23427 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-23427 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-23427 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-23427 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-23460 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-23460 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-23460 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-23460 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-23460 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-23488 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-23488 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-23488 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-23488 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-23488 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-23513 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-23513 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-23513 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-23513 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-23513 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-23540 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-23540 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-23540 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-23540 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-23540 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-23566 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-23566 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-23566 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-23566 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-23566 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-23599 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-23599 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-23599 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-23599 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-23599 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-23623 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-23623 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-23623 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-23623 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-23623 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-23655 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-23655 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-23655 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-23655 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-23655 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-23684 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-23684 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-23684 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-23684 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-23684 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-23706 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-23706 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-23706 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-23706 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-23706 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-23736 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-23736 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-23736 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-23736 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-23736 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-23762 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-23762 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-23762 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-23762 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-23762 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-23791 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-23791 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-23791 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-23791 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-23791 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-23820 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-23820 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-23820 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-23820 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-23820 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-23852 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-23852 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-23852 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-23852 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-23852 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-23880 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-23880 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-23880 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-23880 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-23880 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-23904 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-23904 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-23904 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-23904 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-23904 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-23933 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-23933 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-23933 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-23933 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-23933 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-23959 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-23959 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-23959 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-23959 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-23959 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-23988 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-23988 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-23988 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-23988 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-23988 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-24014 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-24014 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-24014 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-24014 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-24014 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-24047 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-24047 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-24047 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-24047 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-24047 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-24073 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-24073 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-24073 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-24073 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-24073 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-24100 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-24100 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-24100 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-24100 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-24100 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-24128 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-24128 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-24128 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-24128 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-24128 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-24154 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-24154 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-24154 | ap-southeast-6 | 3 | B9 |  |
| RN-SOUTH-24154 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-24154 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-24186 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-24186 | sa-east-7 | 2 | B9 |  |
| RN-SOUTH-24186 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-24186 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-24186 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-24212 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-24212 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-24212 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-24212 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-24212 | ap-southeast-6 | 5 | B9 |  |
| RN-SOUTH-24241 | sa-east-7 | 1 | B9 |  |
| RN-SOUTH-24241 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-24241 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-24241 | sa-east-7 | 4 | B9 |  |
| RN-SOUTH-24241 | sa-east-7 | 5 | B9 |  |
| RN-SOUTH-24266 | ap-southeast-6 | 1 | B9 |  |
| RN-SOUTH-24266 | ap-southeast-6 | 2 | B9 |  |
| RN-SOUTH-24266 | sa-east-7 | 3 | B9 |  |
| RN-SOUTH-24266 | ap-southeast-6 | 4 | B9 |  |
| RN-SOUTH-24266 | ap-southeast-6 | 5 | B9 |  |
|   rn-west-10021  | us-east-3 | 1 | B10 |  |
|   rn-west-10021  | us-east-3 | 2 | B10 |  |
|   rn-west-10021  | us-east-3 | 3 | B10 |  |
|   rn-west-10021  | us-east-3 | 4 | B10 |  |
|   rn-west-10021  | us-east-3 | 5 | B10 |  |
|   rn-west-10052  | us-central-4 | 1 | B10 |  |
|   rn-west-10052  | us-east-3 | 2 | B10 |  |
|   rn-west-10052  | us-east-3 | 3 | B10 |  |
|   rn-west-10052  | us-central-4 | 4 | B10 |  |
|   rn-west-10052  | us-central-4 | 5 | B10 |  |
|   rn-west-10077  | us-east-3 | 1 | B10 |  |
|   rn-west-10077  | us-east-3 | 2 | B10 |  |
|   rn-west-10077  | us-east-3 | 3 | B10 |  |
|   rn-west-10077  | us-central-4 | 4 | B10 |  |
|   rn-west-10077  | us-central-4 | 5 | B10 |  |
|   rn-west-10109  | us-central-4 | 1 | B10 |  |
|   rn-west-10109  | us-central-4 | 2 | B10 |  |
|   rn-west-10109  | us-central-4 | 3 | B10 |  |
|   rn-west-10109  | us-central-4 | 4 | B10 |  |
|   rn-west-10109  | us-central-4 | 5 | B10 |  |
|   rn-west-10138  | us-east-3 | 1 | B10 |  |
|   rn-west-10138  | us-central-4 | 2 | B10 |  |
|   rn-west-10138  | us-east-3 | 3 | B10 |  |
|   rn-west-10138  | us-east-3 | 4 | B10 |  |
|   rn-west-10138  | us-east-3 | 5 | B10 |  |
|   rn-west-10164  | us-central-4 | 1 | B10 |  |
|   rn-west-10164  | us-central-4 | 2 | B10 |  |
|   rn-west-10164  | us-central-4 | 3 | B10 |  |
|   rn-west-10164  | us-central-4 | 4 | B10 |  |
|   rn-west-10164  | us-central-4 | 5 | B10 |  |
|   rn-west-10190  | us-east-3 | 1 | B10 |  |
|   rn-west-10190  | us-east-3 | 2 | B10 |  |
|   rn-west-10190  | us-east-3 | 3 | B10 |  |
|   rn-west-10190  | us-east-3 | 4 | B10 |  |
|   rn-west-10190  | us-east-3 | 5 | B10 |  |
|   rn-west-10222  | us-central-4 | 1 | B10 |  |
|   rn-west-10222  | us-central-4 | 2 | B10 |  |
|   rn-west-10222  | us-central-4 | 3 | B10 |  |
|   rn-west-10222  | us-central-4 | 4 | B10 |  |
|   rn-west-10222  | us-central-4 | 5 | B10 |  |
|   rn-west-10245  | us-east-3 | 1 | B10 |  |
|   rn-west-10245  | us-east-3 | 2 | B10 |  |
|   rn-west-10245  | us-east-3 | 3 | B10 |  |
|   rn-west-10245  | us-east-3 | 4 | B10 |  |
|   rn-west-10245  | us-east-3 | 5 | B10 |  |
|   rn-west-10275  | us-central-4 | 1 | B10 |  |
|   rn-west-10275  | us-central-4 | 2 | B10 |  |
|   rn-west-10275  | us-central-4 | 3 | B10 |  |
|   rn-west-10275  | us-central-4 | 4 | B10 |  |
|   rn-west-10275  | us-east-3 | 5 | B10 |  |
|   rn-west-10304  | us-east-3 | 1 | B10 |  |
|   rn-west-10304  | us-east-3 | 2 | B10 |  |
|   rn-west-10304  | us-east-3 | 3 | B10 |  |
|   rn-west-10304  | us-east-3 | 4 | B10 |  |
|   rn-west-10304  | us-east-3 | 5 | B10 |  |
|   rn-west-10331  | us-central-4 | 1 | B10 |  |
|   rn-west-10331  | us-central-4 | 2 | B10 |  |
|   rn-west-10331  | us-central-4 | 3 | B10 |  |
|   rn-west-10331  | us-central-4 | 4 | B10 |  |
|   rn-west-10331  | us-central-4 | 5 | B10 |  |
|   rn-west-10360  | us-east-3 | 1 | B10 |  |
|   rn-west-10360  | us-east-3 | 2 | B10 |  |
|   rn-west-10360  | us-east-3 | 3 | B10 |  |
|   rn-west-10360  | us-central-4 | 4 | B10 |  |
|   rn-west-10360  | us-east-3 | 5 | B10 |  |
|   rn-west-10386  | us-central-4 | 1 | B10 |  |
|   rn-west-10386  | us-central-4 | 2 | B10 |  |
|   rn-west-10386  | us-central-4 | 3 | B10 |  |
|   rn-west-10386  | us-central-4 | 4 | B10 |  |
|   rn-west-10386  | us-central-4 | 5 | B10 |  |
|   rn-west-10417  | us-east-3 | 1 | B10 |  |
|   rn-west-10417  | us-east-3 | 2 | B10 |  |
|   rn-west-10417  | us-east-3 | 3 | B10 |  |
|   rn-west-10417  | us-east-3 | 4 | B10 |  |
|   rn-west-10417  | us-east-3 | 5 | B10 |  |
|   rn-west-10443  | us-central-4 | 1 | B10 |  |
|   rn-west-10443  | us-central-4 | 2 | B10 |  |
|   rn-west-10443  | us-central-4 | 3 | B10 |  |
|   rn-west-10443  | us-central-4 | 4 | B10 |  |
|   rn-west-10443  | us-central-4 | 5 | B10 |  |
|   rn-west-10470  | us-east-3 | 1 | B10 |  |
|   rn-west-10470  | us-east-3 | 2 | B10 |  |
|   rn-west-10470  | us-east-3 | 3 | B10 |  |
|   rn-west-10470  | us-east-3 | 4 | B10 |  |
|   rn-west-10470  | us-east-3 | 5 | B10 |  |
|   rn-west-10499  | us-central-4 | 1 | B10 |  |
|   rn-west-10499  | us-central-4 | 2 | B10 |  |
|   rn-west-10499  | us-central-4 | 3 | B10 |  |
|   rn-west-10499  | us-central-4 | 4 | B10 |  |
|   rn-west-10499  | us-central-4 | 5 | B10 |  |
|   rn-west-10530  | us-east-3 | 1 | B10 |  |
|   rn-west-10530  | us-east-3 | 2 | B10 |  |
|   rn-west-10530  | us-east-3 | 3 | B10 |  |
|   rn-west-10530  | us-east-3 | 4 | B10 |  |
|   rn-west-10530  | us-east-3 | 5 | B10 |  |
|   rn-west-10555  | us-central-4 | 1 | B10 |  |
|   rn-west-10555  | us-central-4 | 2 | B10 |  |
|   rn-west-10555  | us-central-4 | 3 | B10 |  |
|   rn-west-10555  | us-central-4 | 4 | B10 |  |
|   rn-west-10555  | us-central-4 | 5 | B10 |  |
|   rn-west-10584  | us-east-3 | 1 | B10 |  |
|   rn-west-10584  | us-east-3 | 2 | B10 |  |
|   rn-west-10584  | us-east-3 | 3 | B10 |  |
|   rn-west-10584  | us-east-3 | 4 | B10 |  |
|   rn-west-10584  | us-east-3 | 5 | B10 |  |
|   rn-west-10614  | us-central-4 | 1 | B10 |  |
|   rn-west-10614  | us-central-4 | 2 | B10 |  |
|   rn-west-10614  | us-central-4 | 3 | B10 |  |
|   rn-west-10614  | us-central-4 | 4 | B10 |  |
|   rn-west-10614  | us-central-4 | 5 | B10 |  |
|   rn-west-10637  | us-east-3 | 1 | B10 |  |
|   rn-west-10637  | us-east-3 | 2 | B10 |  |
|   rn-west-10637  | us-east-3 | 3 | B10 |  |
|   rn-west-10637  | us-central-4 | 4 | B10 |  |
|   rn-west-10637  | us-central-4 | 5 | B10 |  |
|   rn-west-10670  | us-central-4 | 1 | B10 |  |
|   rn-west-10670  | us-central-4 | 2 | B10 |  |
|   rn-west-10670  | us-central-4 | 3 | B10 |  |
|   rn-west-10670  | us-central-4 | 4 | B10 |  |
|   rn-west-10670  | us-central-4 | 5 | B10 |  |
|   rn-west-10694  | us-east-3 | 1 | B10 |  |
|   rn-west-10694  | us-east-3 | 2 | B10 |  |
|   rn-west-10694  | us-east-3 | 3 | B10 |  |
|   rn-west-10694  | us-east-3 | 4 | B10 |  |
|   rn-west-10694  | us-east-3 | 5 | B10 |  |
|   rn-west-10727  | us-central-4 | 1 | B10 |  |
|   rn-west-10727  | us-east-3 | 2 | B10 |  |
|   rn-west-10727  | us-central-4 | 3 | B10 |  |
|   rn-west-10727  | us-central-4 | 4 | B10 |  |
|   rn-west-10727  | us-central-4 | 5 | B10 |  |
|   rn-west-10749  | us-east-3 | 1 | B10 |  |
|   rn-west-10749  | us-east-3 | 2 | B10 |  |
|   rn-west-10749  | us-east-3 | 3 | B10 |  |
|   rn-west-10749  | us-east-3 | 4 | B10 |  |
|   rn-west-10749  | us-east-3 | 5 | B10 |  |
|   rn-west-10780  | us-central-4 | 1 | B10 |  |
|   rn-west-10780  | us-central-4 | 2 | B10 |  |
|   rn-west-10780  | us-central-4 | 3 | B10 |  |
|   rn-west-10780  | us-central-4 | 4 | B10 |  |
|   rn-west-10780  | us-central-4 | 5 | B10 |  |
|   rn-west-10811  | us-east-3 | 1 | B10 |  |
|   rn-west-10811  | us-east-3 | 2 | B10 |  |
|   rn-west-10811  | us-central-4 | 3 | B10 |  |
|   rn-west-10811  | us-east-3 | 4 | B10 |  |
|   rn-west-10811  | us-east-3 | 5 | B10 |  |
|   rn-west-10834  | us-central-4 | 1 | B10 |  |
|   rn-west-10834  | us-central-4 | 2 | B10 |  |
|   rn-west-10834  | us-central-4 | 3 | B10 |  |
|   rn-west-10834  | us-central-4 | 4 | B10 |  |
|   rn-west-10834  | us-east-3 | 5 | B10 |  |
|   rn-west-10861  | us-east-3 | 1 | B10 |  |
|   rn-west-10861  | us-east-3 | 2 | B10 |  |
|   rn-west-10861  | us-east-3 | 3 | B10 |  |
|   rn-west-10861  | us-east-3 | 4 | B10 |  |
|   rn-west-10861  | us-east-3 | 5 | B10 |  |
|   rn-west-10893  | us-central-4 | 1 | B10 |  |
|   rn-west-10893  | us-central-4 | 2 | B10 |  |
|   rn-west-10893  | us-central-4 | 3 | B10 |  |
|   rn-west-10893  | us-central-4 | 4 | B10 |  |
|   rn-west-10893  | us-central-4 | 5 | B10 |  |
|   rn-west-10923  | us-east-3 | 1 | B10 |  |
|   rn-west-10923  | us-east-3 | 2 | B10 |  |
|   rn-west-10923  | us-east-3 | 3 | B10 |  |
|   rn-west-10923  | us-east-3 | 4 | B10 |  |
|   rn-west-10923  | us-east-3 | 5 | B10 |  |
|   rn-west-10950  | us-central-4 | 1 | B10 |  |
|   rn-west-10950  | us-central-4 | 2 | B10 |  |
|   rn-west-10950  | us-central-4 | 3 | B10 |  |
|   rn-west-10950  | us-central-4 | 4 | B10 |  |
|   rn-west-10950  | us-central-4 | 5 | B10 |  |
|   rn-west-10973  | us-east-3 | 1 | B10 |  |
|   rn-west-10973  | us-east-3 | 2 | B10 |  |
|   rn-west-10973  | us-east-3 | 3 | B10 |  |
|   rn-west-10973  | us-east-3 | 4 | B10 |  |
|   rn-west-10973  | us-east-3 | 5 | B10 |  |
|   rn-west-11001  | us-central-4 | 1 | B10 |  |
|   rn-west-11001  | us-central-4 | 2 | B10 |  |
|   rn-west-11001  | us-central-4 | 3 | B10 |  |
|   rn-west-11001  | us-central-4 | 4 | B10 |  |
|   rn-west-11001  | us-central-4 | 5 | B10 |  |
|   rn-west-11029  | us-east-3 | 1 | B10 |  |
|   rn-west-11029  | us-east-3 | 2 | B10 |  |
|   rn-west-11029  | us-east-3 | 3 | B10 |  |
|   rn-west-11029  | us-east-3 | 4 | B10 |  |
|   rn-west-11029  | us-east-3 | 5 | B10 |  |
|   rn-west-11058  | us-central-4 | 1 | B10 |  |
|   rn-west-11058  | us-central-4 | 2 | B10 |  |
|   rn-west-11058  | us-central-4 | 3 | B10 |  |
|   rn-west-11058  | us-east-3 | 4 | B10 |  |
|   rn-west-11058  | us-central-4 | 5 | B10 |  |
|   rn-west-11089  | us-east-3 | 1 | B10 |  |
|   rn-west-11089  | us-central-4 | 2 | B10 |  |
|   rn-west-11089  | us-east-3 | 3 | B10 |  |
|   rn-west-11089  | us-east-3 | 4 | B10 |  |
|   rn-west-11089  | us-central-4 | 5 | B10 |  |
|   rn-west-11117  | us-central-4 | 1 | B10 |  |
|   rn-west-11117  | us-east-3 | 2 | B10 |  |
|   rn-west-11117  | us-central-4 | 3 | B10 |  |
|   rn-west-11117  | us-central-4 | 4 | B10 |  |
|   rn-west-11117  | us-central-4 | 5 | B10 |  |
|   rn-west-11144  | us-east-3 | 1 | B10 |  |
|   rn-west-11144  | us-east-3 | 2 | B10 |  |
|   rn-west-11144  | us-east-3 | 3 | B10 |  |
|   rn-west-11144  | us-east-3 | 4 | B10 |  |
|   rn-west-11144  | us-east-3 | 5 | B10 |  |
|   rn-west-11172  | us-central-4 | 1 | B10 |  |
|   rn-west-11172  | us-central-4 | 2 | B10 |  |
|   rn-west-11172  | us-central-4 | 3 | B10 |  |
|   rn-west-11172  | us-central-4 | 4 | B10 |  |
|   rn-west-11172  | us-central-4 | 5 | B10 |  |
|   rn-west-11198  | us-east-3 | 1 | B10 |  |
|   rn-west-11198  | us-east-3 | 2 | B10 |  |
|   rn-west-11198  | us-east-3 | 3 | B10 |  |
|   rn-west-11198  | us-east-3 | 4 | B10 |  |
|   rn-west-11198  | us-east-3 | 5 | B10 |  |
|   rn-west-11230  | us-central-4 | 1 | B10 |  |
|   rn-west-11230  | us-central-4 | 2 | B10 |  |
|   rn-west-11230  | us-central-4 | 3 | B10 |  |
|   rn-west-11230  | us-central-4 | 4 | B10 |  |
|   rn-west-11230  | us-east-3 | 5 | B10 |  |
|   rn-west-11259  | us-east-3 | 1 | B10 |  |
|   rn-west-11259  | us-east-3 | 2 | B10 |  |
|   rn-west-11259  | us-east-3 | 3 | B10 |  |
|   rn-west-11259  | us-east-3 | 4 | B10 |  |
|   rn-west-11259  | us-central-4 | 5 | B10 |  |
|   rn-west-11283  | us-central-4 | 1 | B10 |  |
|   rn-west-11283  | us-central-4 | 2 | B10 |  |
|   rn-west-11283  | us-central-4 | 3 | B10 |  |
|   rn-west-11283  | us-central-4 | 4 | B10 |  |
|   rn-west-11283  | us-central-4 | 5 | B10 |  |
|   rn-west-11313  | us-east-3 | 1 | B10 |  |
|   rn-west-11313  | us-east-3 | 2 | B10 |  |
|   rn-west-11313  | us-east-3 | 3 | B10 |  |
|   rn-west-11313  | us-east-3 | 4 | B10 |  |
|   rn-west-11313  | us-east-3 | 5 | B10 |  |
|   rn-west-11342  | us-central-4 | 1 | B10 |  |
|   rn-west-11342  | us-central-4 | 2 | B10 |  |
|   rn-west-11342  | us-central-4 | 3 | B10 |  |
|   rn-west-11342  | us-central-4 | 4 | B10 |  |
|   rn-west-11342  | us-central-4 | 5 | B10 |  |
|   rn-west-11369  | us-east-3 | 1 | B10 |  |
|   rn-west-11369  | us-east-3 | 2 | B10 |  |
|   rn-west-11369  | us-east-3 | 3 | B10 |  |
|   rn-west-11369  | us-east-3 | 4 | B10 |  |
|   rn-west-11369  | us-east-3 | 5 | B10 |  |
|   rn-west-11399  | us-central-4 | 1 | B10 |  |
|   rn-west-11399  | us-central-4 | 2 | B10 |  |
|   rn-west-11399  | us-central-4 | 3 | B10 |  |
|   rn-west-11399  | us-central-4 | 4 | B10 |  |
|   rn-west-11399  | us-central-4 | 5 | B10 |  |
|   rn-west-11423  | us-east-3 | 1 | B10 |  |
|   rn-west-11423  | us-east-3 | 2 | B10 |  |
|   rn-west-11423  | us-east-3 | 3 | B10 |  |
|   rn-west-11423  | us-east-3 | 4 | B10 |  |
|   rn-west-11423  | us-east-3 | 5 | B10 |  |
|   rn-west-11452  | us-central-4 | 1 | B10 |  |
|   rn-west-11452  | us-central-4 | 2 | B10 |  |
|   rn-west-11452  | us-central-4 | 3 | B10 |  |
|   rn-west-11452  | us-central-4 | 4 | B10 |  |
|   rn-west-11452  | us-central-4 | 5 | B10 |  |
|   rn-west-11479  | us-east-3 | 1 | B10 |  |
|   rn-west-11479  | us-east-3 | 2 | B10 |  |
|   rn-west-11479  | us-east-3 | 3 | B10 |  |
|   rn-west-11479  | us-east-3 | 4 | B10 |  |
|   rn-west-11479  | us-east-3 | 5 | B10 |  |
|   rn-west-11511  | us-central-4 | 1 | B10 |  |
|   rn-west-11511  | us-central-4 | 2 | B10 |  |
|   rn-west-11511  | us-central-4 | 3 | B10 |  |
|   rn-west-11511  | us-central-4 | 4 | B10 |  |
|   rn-west-11511  | us-central-4 | 5 | B10 |  |
|   rn-west-11538  | us-east-3 | 1 | B10 |  |
|   rn-west-11538  | us-east-3 | 2 | B10 |  |
|   rn-west-11538  | us-east-3 | 3 | B10 |  |
|   rn-west-11538  | us-east-3 | 4 | B10 |  |
|   rn-west-11538  | us-east-3 | 5 | B10 |  |
|   rn-west-11567  | us-central-4 | 1 | B10 |  |
|   rn-west-11567  | us-central-4 | 2 | B10 |  |
|   rn-west-11567  | us-central-4 | 3 | B10 |  |
|   rn-west-11567  | us-central-4 | 4 | B10 |  |
|   rn-west-11567  | us-central-4 | 5 | B10 |  |
|   rn-west-11591  | us-east-3 | 1 | B10 |  |
|   rn-west-11591  | us-east-3 | 2 | B10 |  |
|   rn-west-11591  | us-east-3 | 3 | B10 |  |
|   rn-west-11591  | us-east-3 | 4 | B10 |  |
|   rn-west-11591  | us-east-3 | 5 | B10 |  |
|   rn-west-11621  | us-central-4 | 1 | B10 |  |
|   rn-west-11621  | us-central-4 | 2 | B10 |  |
|   rn-west-11621  | us-central-4 | 3 | B10 |  |
|   rn-west-11621  | us-central-4 | 4 | B10 |  |
|   rn-west-11621  | us-central-4 | 5 | B10 |  |
|   rn-west-11648  | us-east-3 | 1 | B10 |  |
|   rn-west-11648  | us-east-3 | 2 | B10 |  |
|   rn-west-11648  | us-central-4 | 3 | B10 |  |
|   rn-west-11648  | us-east-3 | 4 | B10 |  |
|   rn-west-11648  | us-east-3 | 5 | B10 |  |
|   rn-west-11678  | us-central-4 | 1 | B10 |  |
|   rn-west-11678  | us-central-4 | 2 | B10 |  |
|   rn-west-11678  | us-central-4 | 3 | B10 |  |
|   rn-west-11678  | us-central-4 | 4 | B10 |  |
|   rn-west-11678  | us-central-4 | 5 | B10 |  |
|   rn-west-11706  | us-east-3 | 1 | B10 |  |
|   rn-west-11706  | us-east-3 | 2 | B10 |  |
|   rn-west-11706  | us-east-3 | 3 | B10 |  |
|   rn-west-11706  | us-east-3 | 4 | B10 |  |
|   rn-west-11706  | us-central-4 | 5 | B10 |  |
|   rn-west-11731  | us-central-4 | 1 | B10 |  |
|   rn-west-11731  | us-central-4 | 2 | B10 |  |
|   rn-west-11731  | us-central-4 | 3 | B10 |  |
|   rn-west-11731  | us-central-4 | 4 | B10 |  |
|   rn-west-11731  | us-central-4 | 5 | B10 |  |
|   rn-west-11759  | us-east-3 | 1 | B10 |  |
|   rn-west-11759  | us-east-3 | 2 | B10 |  |
|   rn-west-11759  | us-east-3 | 3 | B10 |  |
|   rn-west-11759  | us-east-3 | 4 | B10 |  |
|   rn-west-11759  | us-east-3 | 5 | B10 |  |
|   rn-west-11786  | us-central-4 | 1 | B10 |  |
|   rn-west-11786  | us-central-4 | 2 | B10 |  |
|   rn-west-11786  | us-central-4 | 3 | B10 |  |
|   rn-west-11786  | us-central-4 | 4 | B10 |  |
|   rn-west-11786  | us-central-4 | 5 | B10 |  |
|   rn-west-11814  | us-east-3 | 1 | B10 |  |
|   rn-west-11814  | us-east-3 | 2 | B10 |  |
|   rn-west-11814  | us-east-3 | 3 | B10 |  |
|   rn-west-11814  | us-east-3 | 4 | B10 |  |
|   rn-west-11814  | us-east-3 | 5 | B10 |  |
|   rn-west-11843  | us-central-4 | 1 | B10 |  |
|   rn-west-11843  | us-central-4 | 2 | B10 |  |
|   rn-west-11843  | us-central-4 | 3 | B10 |  |
|   rn-west-11843  | us-central-4 | 4 | B10 |  |
|   rn-west-11843  | us-central-4 | 5 | B10 |  |
|   rn-west-11870  | us-east-3 | 1 | B10 |  |
|   rn-west-11870  | us-east-3 | 2 | B10 |  |
|   rn-west-11870  | us-east-3 | 3 | B10 |  |
|   rn-west-11870  | us-east-3 | 4 | B10 |  |
|   rn-west-11870  | us-east-3 | 5 | B10 |  |
|   rn-west-11897  | us-central-4 | 1 | B10 |  |
|   rn-west-11897  | us-central-4 | 2 | B10 |  |
|   rn-west-11897  | us-central-4 | 3 | B10 |  |
|   rn-west-11897  | us-central-4 | 4 | B10 |  |
|   rn-west-11897  | us-central-4 | 5 | B10 |  |
|   rn-west-11929  | us-east-3 | 1 | B10 |  |
|   rn-west-11929  | us-east-3 | 2 | B10 |  |
|   rn-west-11929  | us-east-3 | 3 | B10 |  |
|   rn-west-11929  | us-east-3 | 4 | B10 |  |
|   rn-west-11929  | us-east-3 | 5 | B10 |  |
|   rn-west-11953  | us-central-4 | 1 | B10 |  |
|   rn-west-11953  | us-central-4 | 2 | B10 |  |
|   rn-west-11953  | us-central-4 | 3 | B10 |  |
|   rn-west-11953  | us-central-4 | 4 | B10 |  |
|   rn-west-11953  | us-central-4 | 5 | B10 |  |
|   rn-west-11982  | us-east-3 | 1 | B10 |  |
|   rn-west-11982  | us-east-3 | 2 | B10 |  |
|   rn-west-11982  | us-east-3 | 3 | B10 |  |
|   rn-west-11982  | us-east-3 | 4 | B10 |  |
|   rn-west-11982  | us-east-3 | 5 | B10 |  |
|   rn-west-12012  | us-central-4 | 1 | B10 |  |
|   rn-west-12012  | us-east-3 | 2 | B10 |  |
|   rn-west-12012  | us-central-4 | 3 | B10 |  |
|   rn-west-12012  | us-central-4 | 4 | B10 |  |
|   rn-west-12012  | us-central-4 | 5 | B10 |  |
|   rn-west-12043  | us-east-3 | 1 | B10 |  |
|   rn-west-12043  | us-east-3 | 2 | B10 |  |
|   rn-west-12043  | us-east-3 | 3 | B10 |  |
|   rn-west-12043  | us-east-3 | 4 | B10 |  |
|   rn-west-12043  | us-east-3 | 5 | B10 |  |
|   rn-west-12065  | us-central-4 | 1 | B10 |  |
|   rn-west-12065  | us-central-4 | 2 | B10 |  |
|   rn-west-12065  | us-central-4 | 3 | B10 |  |
|   rn-west-12065  | us-central-4 | 4 | B10 |  |
|   rn-west-12065  | us-central-4 | 5 | B10 |  |
|   rn-west-12099  | us-east-3 | 1 | B10 |  |
|   rn-west-12099  | us-east-3 | 2 | B10 |  |
|   rn-west-12099  | us-east-3 | 3 | B10 |  |
|   rn-west-12099  | us-east-3 | 4 | B10 |  |
|   rn-west-12099  | us-east-3 | 5 | B10 |  |
|   rn-west-12124  | us-central-4 | 1 | B10 |  |
|   rn-west-12124  | us-central-4 | 2 | B10 |  |
|   rn-west-12124  | us-central-4 | 3 | B10 |  |
|   rn-west-12124  | us-central-4 | 4 | B10 |  |
|   rn-west-12124  | us-central-4 | 5 | B10 |  |
|   rn-west-12155  | us-east-3 | 1 | B10 |  |
|   rn-west-12155  | us-east-3 | 2 | B10 |  |
|   rn-west-12155  | us-east-3 | 3 | B10 |  |
|   rn-west-12155  | us-east-3 | 4 | B10 |  |
|   rn-west-12155  | us-east-3 | 5 | B10 |  |
|   rn-west-12181  | us-central-4 | 1 | B10 |  |
|   rn-west-12181  | us-central-4 | 2 | B10 |  |
|   rn-west-12181  | us-central-4 | 3 | B10 |  |
|   rn-west-12181  | us-central-4 | 4 | B10 |  |
|   rn-west-12181  | us-central-4 | 5 | B10 |  |
|   rn-west-12207  | us-east-3 | 1 | B10 |  |
|   rn-west-12207  | us-east-3 | 2 | B10 |  |
|   rn-west-12207  | us-east-3 | 3 | B10 |  |
|   rn-west-12207  | us-east-3 | 4 | B10 |  |
|   rn-west-12207  | us-east-3 | 5 | B10 |  |
|   rn-west-12237  | us-central-4 | 1 | B10 |  |
|   rn-west-12237  | us-central-4 | 2 | B10 |  |
|   rn-west-12237  | us-central-4 | 3 | B10 |  |
|   rn-west-12237  | us-central-4 | 4 | B10 |  |
|   rn-west-12237  | us-central-4 | 5 | B10 |  |
|   rn-west-12264  | us-east-3 | 1 | B10 |  |
|   rn-west-12264  | us-east-3 | 2 | B10 |  |
|   rn-west-12264  | us-east-3 | 3 | B10 |  |
|   rn-west-12264  | us-east-3 | 4 | B10 |  |
|   rn-west-12264  | us-east-3 | 5 | B10 |  |
|   rn-west-12295  | us-central-4 | 1 | B10 |  |
|   rn-west-12295  | us-central-4 | 2 | B10 |  |
|   rn-west-12295  | us-central-4 | 3 | B10 |  |
|   rn-west-12295  | us-east-3 | 4 | B10 |  |
|   rn-west-12295  | us-central-4 | 5 | B10 |  |
|   rn-west-12320  | us-east-3 | 1 | B10 |  |
|   rn-west-12320  | us-east-3 | 2 | B10 |  |
|   rn-west-12320  | us-east-3 | 3 | B10 |  |
|   rn-west-12320  | us-east-3 | 4 | B10 |  |
|   rn-west-12320  | us-east-3 | 5 | B10 |  |
|   rn-west-12350  | us-central-4 | 1 | B10 |  |
|   rn-west-12350  | us-central-4 | 2 | B10 |  |
|   rn-west-12350  | us-central-4 | 3 | B10 |  |
|   rn-west-12350  | us-central-4 | 4 | B10 |  |
|   rn-west-12350  | us-central-4 | 5 | B10 |  |
|   rn-west-12376  | us-east-3 | 1 | B10 |  |
|   rn-west-12376  | us-east-3 | 2 | B10 |  |
|   rn-west-12376  | us-east-3 | 3 | B10 |  |
|   rn-west-12376  | us-east-3 | 4 | B10 |  |
|   rn-west-12376  | us-east-3 | 5 | B10 |  |
|   rn-west-12401  | us-central-4 | 1 | B10 |  |
|   rn-west-12401  | us-central-4 | 2 | B10 |  |
|   rn-west-12401  | us-central-4 | 3 | B10 |  |
|   rn-west-12401  | us-central-4 | 4 | B10 |  |
|   rn-west-12401  | us-central-4 | 5 | B10 |  |
|   rn-west-12432  | us-east-3 | 1 | B10 |  |
|   rn-west-12432  | us-central-4 | 2 | B10 |  |
|   rn-west-12432  | us-east-3 | 3 | B10 |  |
|   rn-west-12432  | us-east-3 | 4 | B10 |  |
|   rn-west-12432  | us-east-3 | 5 | B10 |  |
|   rn-west-12463  | us-central-4 | 1 | B10 |  |
|   rn-west-12463  | us-central-4 | 2 | B10 |  |
|   rn-west-12463  | us-central-4 | 3 | B10 |  |
|   rn-west-12463  | us-central-4 | 4 | B10 |  |
|   rn-west-12463  | us-central-4 | 5 | B10 |  |
|   rn-west-12487  | us-east-3 | 1 | B10 |  |
|   rn-west-12487  | us-east-3 | 2 | B10 |  |
|   rn-west-12487  | us-east-3 | 3 | B10 |  |
|   rn-west-12487  | us-east-3 | 4 | B10 |  |
|   rn-west-12487  | us-east-3 | 5 | B10 |  |
|   rn-west-12513  | us-central-4 | 1 | B10 |  |
|   rn-west-12513  | us-central-4 | 2 | B10 |  |
|   rn-west-12513  | us-central-4 | 3 | B10 |  |
|   rn-west-12513  | us-central-4 | 4 | B10 |  |
|   rn-west-12513  | us-central-4 | 5 | B10 |  |
|   rn-west-12545  | us-east-3 | 1 | B10 |  |
|   rn-west-12545  | us-east-3 | 2 | B10 |  |
|   rn-west-12545  | us-east-3 | 3 | B10 |  |
|   rn-west-12545  | us-east-3 | 4 | B10 |  |
|   rn-west-12545  | us-east-3 | 5 | B10 |  |
|   rn-west-12573  | us-central-4 | 1 | B10 |  |
|   rn-west-12573  | us-central-4 | 2 | B10 |  |
|   rn-west-12573  | us-central-4 | 3 | B10 |  |
|   rn-west-12573  | us-central-4 | 4 | B10 |  |
|   rn-west-12573  | us-central-4 | 5 | B10 |  |
|   rn-west-12600  | us-east-3 | 1 | B10 |  |
|   rn-west-12600  | us-east-3 | 2 | B10 |  |
|   rn-west-12600  | us-east-3 | 3 | B10 |  |
|   rn-west-12600  | us-east-3 | 4 | B10 |  |
|   rn-west-12600  | us-east-3 | 5 | B10 |  |
|   rn-west-12631  | us-central-4 | 1 | B10 |  |
|   rn-west-12631  | us-central-4 | 2 | B10 |  |
|   rn-west-12631  | us-central-4 | 3 | B10 |  |
|   rn-west-12631  | us-central-4 | 4 | B10 |  |
|   rn-west-12631  | us-central-4 | 5 | B10 |  |
|   rn-west-12656  | us-east-3 | 1 | B10 |  |
|   rn-west-12656  | us-east-3 | 2 | B10 |  |
|   rn-west-12656  | us-east-3 | 3 | B10 |  |
|   rn-west-12656  | us-east-3 | 4 | B10 |  |
|   rn-west-12656  | us-east-3 | 5 | B10 |  |
|   rn-west-12687  | us-central-4 | 1 | B10 |  |
|   rn-west-12687  | us-central-4 | 2 | B10 |  |
|   rn-west-12687  | us-central-4 | 3 | B10 |  |
|   rn-west-12687  | us-central-4 | 4 | B10 |  |
|   rn-west-12687  | us-central-4 | 5 | B10 |  |
|   rn-west-12714  | us-east-3 | 1 | B10 |  |
|   rn-west-12714  | us-east-3 | 2 | B10 |  |
|   rn-west-12714  | us-east-3 | 3 | B10 |  |
|   rn-west-12714  | us-east-3 | 4 | B10 |  |
|   rn-west-12714  | us-central-4 | 5 | B10 |  |
|   rn-west-12741  | us-central-4 | 1 | B10 |  |
|   rn-west-12741  | us-central-4 | 2 | B10 |  |
|   rn-west-12741  | us-central-4 | 3 | B10 |  |
|   rn-west-12741  | us-central-4 | 4 | B10 |  |
|   rn-west-12741  | us-central-4 | 5 | B10 |  |
|   rn-west-12766  | us-east-3 | 1 | B10 |  |
|   rn-west-12766  | us-east-3 | 2 | B10 |  |
|   rn-west-12766  | us-east-3 | 3 | B10 |  |
|   rn-west-12766  | us-central-4 | 4 | B10 |  |
|   rn-west-12766  | us-east-3 | 5 | B10 |  |
|   rn-west-12793  | us-central-4 | 1 | B10 |  |
|   rn-west-12793  | us-central-4 | 2 | B10 |  |
|   rn-west-12793  | us-central-4 | 3 | B10 |  |
|   rn-west-12793  | us-central-4 | 4 | B10 |  |
|   rn-west-12793  | us-central-4 | 5 | B10 |  |
|   rn-west-12826  | us-east-3 | 1 | B10 |  |
|   rn-west-12826  | us-east-3 | 2 | B10 |  |
|   rn-west-12826  | us-east-3 | 3 | B10 |  |
|   rn-west-12826  | us-east-3 | 4 | B10 |  |
|   rn-west-12826  | us-east-3 | 5 | B10 |  |
|   rn-west-12853  | us-central-4 | 1 | B10 |  |
|   rn-west-12853  | us-central-4 | 2 | B10 |  |
|   rn-west-12853  | us-central-4 | 3 | B10 |  |
|   rn-west-12853  | us-central-4 | 4 | B10 |  |
|   rn-west-12853  | us-central-4 | 5 | B10 |  |
|   rn-west-12878  | us-east-3 | 1 | B10 |  |
|   rn-west-12878  | us-east-3 | 2 | B10 |  |
|   rn-west-12878  | us-east-3 | 3 | B10 |  |
|   rn-west-12878  | us-east-3 | 4 | B10 |  |
|   rn-west-12878  | us-east-3 | 5 | B10 |  |
|   rn-west-12909  | us-central-4 | 1 | B10 |  |
|   rn-west-12909  | us-central-4 | 2 | B10 |  |
|   rn-west-12909  | us-central-4 | 3 | B10 |  |
|   rn-west-12909  | us-central-4 | 4 | B10 |  |
|   rn-west-12909  | us-central-4 | 5 | B10 |  |
|   rn-west-12937  | us-east-3 | 1 | B10 |  |
|   rn-west-12937  | us-east-3 | 2 | B10 |  |
|   rn-west-12937  | us-east-3 | 3 | B10 |  |
|   rn-west-12937  | us-east-3 | 4 | B10 |  |
|   rn-west-12937  | us-east-3 | 5 | B10 |  |
|   rn-west-12966  | us-central-4 | 1 | B10 |  |
|   rn-west-12966  | us-central-4 | 2 | B10 |  |
|   rn-west-12966  | us-central-4 | 3 | B10 |  |
|   rn-west-12966  | us-central-4 | 4 | B10 |  |
|   rn-west-12966  | us-central-4 | 5 | B10 |  |
|   rn-west-12995  | us-east-3 | 1 | B10 |  |
|   rn-west-12995  | us-east-3 | 2 | B10 |  |
|   rn-west-12995  | us-east-3 | 3 | B10 |  |
|   rn-west-12995  | us-east-3 | 4 | B10 |  |
|   rn-west-12995  | us-east-3 | 5 | B10 |  |
|   rn-west-13018  | us-central-4 | 1 | B10 |  |
|   rn-west-13018  | us-central-4 | 2 | B10 |  |
|   rn-west-13018  | us-central-4 | 3 | B10 |  |
|   rn-west-13018  | us-central-4 | 4 | B10 |  |
|   rn-west-13018  | us-east-3 | 5 | B10 |  |
|   rn-west-13048  | us-east-3 | 1 | B10 |  |
|   rn-west-13048  | us-east-3 | 2 | B10 |  |
|   rn-west-13048  | us-central-4 | 3 | B10 |  |
|   rn-west-13048  | us-central-4 | 4 | B10 |  |
|   rn-west-13048  | us-east-3 | 5 | B10 |  |
|   rn-west-13076  | us-central-4 | 1 | B10 |  |
|   rn-west-13076  | us-central-4 | 2 | B10 |  |
|   rn-west-13076  | us-central-4 | 3 | B10 |  |
|   rn-west-13076  | us-central-4 | 4 | B10 |  |
|   rn-west-13076  | us-central-4 | 5 | B10 |  |
|   rn-west-13106  | us-east-3 | 1 | B10 |  |
|   rn-west-13106  | us-east-3 | 2 | B10 |  |
|   rn-west-13106  | us-central-4 | 3 | B10 |  |
|   rn-west-13106  | us-east-3 | 4 | B10 |  |
|   rn-west-13106  | us-east-3 | 5 | B10 |  |
|   rn-west-13130  | us-central-4 | 1 | B10 |  |
|   rn-west-13130  | us-central-4 | 2 | B10 |  |
|   rn-west-13130  | us-central-4 | 3 | B10 |  |
|   rn-west-13130  | us-central-4 | 4 | B10 |  |
|   rn-west-13130  | us-central-4 | 5 | B10 |  |
|   rn-west-13162  | us-east-3 | 1 | B10 |  |
|   rn-west-13162  | us-east-3 | 2 | B10 |  |
|   rn-west-13162  | us-east-3 | 3 | B10 |  |
|   rn-west-13162  | us-east-3 | 4 | B10 |  |
|   rn-west-13162  | us-east-3 | 5 | B10 |  |
|   rn-west-13191  | us-central-4 | 1 | B10 |  |
|   rn-west-13191  | us-central-4 | 2 | B10 |  |
|   rn-west-13191  | us-central-4 | 3 | B10 |  |
|   rn-west-13191  | us-central-4 | 4 | B10 |  |
|   rn-west-13191  | us-central-4 | 5 | B10 |  |
|   rn-west-13218  | us-east-3 | 1 | B10 |  |
|   rn-west-13218  | us-east-3 | 2 | B10 |  |
|   rn-west-13218  | us-east-3 | 3 | B10 |  |
|   rn-west-13218  | us-east-3 | 4 | B10 |  |
|   rn-west-13218  | us-east-3 | 5 | B10 |  |
|   rn-west-13242  | us-central-4 | 1 | B10 |  |
|   rn-west-13242  | us-central-4 | 2 | B10 |  |
|   rn-west-13242  | us-central-4 | 3 | B10 |  |
|   rn-west-13242  | us-central-4 | 4 | B10 |  |
|   rn-west-13242  | us-central-4 | 5 | B10 |  |
|   rn-west-13275  | us-east-3 | 1 | B10 |  |
|   rn-west-13275  | us-east-3 | 2 | B10 |  |
|   rn-west-13275  | us-east-3 | 3 | B10 |  |
|   rn-west-13275  | us-east-3 | 4 | B10 |  |
|   rn-west-13275  | us-east-3 | 5 | B10 |  |
|   rn-west-13298  | us-central-4 | 1 | B10 |  |
|   rn-west-13298  | us-central-4 | 2 | B10 |  |
|   rn-west-13298  | us-central-4 | 3 | B10 |  |
|   rn-west-13298  | us-central-4 | 4 | B10 |  |
|   rn-west-13298  | us-central-4 | 5 | B10 |  |
|   rn-west-13331  | us-east-3 | 1 | B10 |  |
|   rn-west-13331  | us-east-3 | 2 | B10 |  |
|   rn-west-13331  | us-east-3 | 3 | B10 |  |
|   rn-west-13331  | us-east-3 | 4 | B10 |  |
|   rn-west-13331  | us-east-3 | 5 | B10 |  |
|   rn-west-13355  | us-central-4 | 1 | B10 |  |
|   rn-west-13355  | us-central-4 | 2 | B10 |  |
|   rn-west-13355  | us-central-4 | 3 | B10 |  |
|   rn-west-13355  | us-east-3 | 4 | B10 |  |
|   rn-west-13355  | us-central-4 | 5 | B10 |  |
|   rn-west-13382  | us-east-3 | 1 | B10 |  |
|   rn-west-13382  | us-east-3 | 2 | B10 |  |
|   rn-west-13382  | us-east-3 | 3 | B10 |  |
|   rn-west-13382  | us-east-3 | 4 | B10 |  |
|   rn-west-13382  | us-east-3 | 5 | B10 |  |
|   rn-west-13415  | us-central-4 | 1 | B10 |  |
|   rn-west-13415  | us-central-4 | 2 | B10 |  |
|   rn-west-13415  | us-central-4 | 3 | B10 |  |
|   rn-west-13415  | us-central-4 | 4 | B10 |  |
|   rn-west-13415  | us-central-4 | 5 | B10 |  |
|   rn-west-13437  | us-east-3 | 1 | B10 |  |
|   rn-west-13437  | us-east-3 | 2 | B10 |  |
|   rn-west-13437  | us-east-3 | 3 | B10 |  |
|   rn-west-13437  | us-east-3 | 4 | B10 |  |
|   rn-west-13437  | us-east-3 | 5 | B10 |  |
|   rn-west-13465  | us-central-4 | 1 | B10 |  |
|   rn-west-13465  | us-central-4 | 2 | B10 |  |
|   rn-west-13465  | us-central-4 | 3 | B10 |  |
|   rn-west-13465  | us-central-4 | 4 | B10 |  |
|   rn-west-13465  | us-central-4 | 5 | B10 |  |
|   rn-west-13494  | us-east-3 | 1 | B10 |  |
|   rn-west-13494  | us-east-3 | 2 | B10 |  |
|   rn-west-13494  | us-east-3 | 3 | B10 |  |
|   rn-west-13494  | us-east-3 | 4 | B10 |  |
|   rn-west-13494  | us-east-3 | 5 | B10 |  |
|   rn-west-13526  | us-central-4 | 1 | B10 |  |
|   rn-west-13526  | us-central-4 | 2 | B10 |  |
|   rn-west-13526  | us-central-4 | 3 | B10 |  |
|   rn-west-13526  | us-central-4 | 4 | B10 |  |
|   rn-west-13526  | us-central-4 | 5 | B10 |  |
|   rn-west-13549  | us-east-3 | 1 | B10 |  |
|   rn-west-13549  | us-central-4 | 2 | B10 |  |
|   rn-west-13549  | us-central-4 | 3 | B10 |  |
|   rn-west-13549  | us-east-3 | 4 | B10 |  |
|   rn-west-13549  | us-east-3 | 5 | B10 |  |
|   rn-west-13582  | us-central-4 | 1 | B10 |  |
|   rn-west-13582  | us-central-4 | 2 | B10 |  |
|   rn-west-13582  | us-central-4 | 3 | B10 |  |
|   rn-west-13582  | us-central-4 | 4 | B10 |  |
|   rn-west-13582  | us-central-4 | 5 | B10 |  |
|   rn-west-13609  | us-east-3 | 1 | B10 |  |
|   rn-west-13609  | us-east-3 | 2 | B10 |  |
|   rn-west-13609  | us-east-3 | 3 | B10 |  |
|   rn-west-13609  | us-east-3 | 4 | B10 |  |
|   rn-west-13609  | us-central-4 | 5 | B10 |  |
|   rn-west-13635  | us-central-4 | 1 | B10 |  |
|   rn-west-13635  | us-central-4 | 2 | B10 |  |
|   rn-west-13635  | us-central-4 | 3 | B10 |  |
|   rn-west-13635  | us-central-4 | 4 | B10 |  |
|   rn-west-13635  | us-central-4 | 5 | B10 |  |
|   rn-west-13663  | us-east-3 | 1 | B10 |  |
|   rn-west-13663  | us-east-3 | 2 | B10 |  |
|   rn-west-13663  | us-east-3 | 3 | B10 |  |
|   rn-west-13663  | us-east-3 | 4 | B10 |  |
|   rn-west-13663  | us-east-3 | 5 | B10 |  |
|   rn-west-13693  | us-central-4 | 1 | B10 |  |
|   rn-west-13693  | us-central-4 | 2 | B10 |  |
|   rn-west-13693  | us-central-4 | 3 | B10 |  |
|   rn-west-13693  | us-central-4 | 4 | B10 |  |
|   rn-west-13693  | us-central-4 | 5 | B10 |  |
|   rn-west-13717  | us-east-3 | 1 | B10 |  |
|   rn-west-13717  | us-east-3 | 2 | B10 |  |
|   rn-west-13717  | us-east-3 | 3 | B10 |  |
|   rn-west-13717  | us-east-3 | 4 | B10 |  |
|   rn-west-13717  | us-east-3 | 5 | B10 |  |
|   rn-west-13745  | us-central-4 | 1 | B10 |  |
|   rn-west-13745  | us-central-4 | 2 | B10 |  |
|   rn-west-13745  | us-central-4 | 3 | B10 |  |
|   rn-west-13745  | us-central-4 | 4 | B10 |  |
|   rn-west-13745  | us-central-4 | 5 | B10 |  |
|   rn-west-13779  | us-east-3 | 1 | B10 |  |
|   rn-west-13779  | us-east-3 | 2 | B10 |  |
|   rn-west-13779  | us-central-4 | 3 | B10 |  |
|   rn-west-13779  | us-east-3 | 4 | B10 |  |
|   rn-west-13779  | us-east-3 | 5 | B10 |  |
|   rn-west-13802  | us-central-4 | 1 | B10 |  |
|   rn-west-13802  | us-east-3 | 2 | B10 |  |
|   rn-west-13802  | us-central-4 | 3 | B10 |  |
|   rn-west-13802  | us-east-3 | 4 | B10 |  |
|   rn-west-13802  | us-central-4 | 5 | B10 |  |
|   rn-west-13833  | us-east-3 | 1 | B10 |  |
|   rn-west-13833  | us-east-3 | 2 | B10 |  |
|   rn-west-13833  | us-east-3 | 3 | B10 |  |
|   rn-west-13833  | us-east-3 | 4 | B10 |  |
|   rn-west-13833  | us-east-3 | 5 | B10 |  |
|   rn-west-13857  | us-central-4 | 1 | B10 |  |
|   rn-west-13857  | us-central-4 | 2 | B10 |  |
|   rn-west-13857  | us-central-4 | 3 | B10 |  |
|   rn-west-13857  | us-central-4 | 4 | B10 |  |
|   rn-west-13857  | us-central-4 | 5 | B10 |  |
|   rn-west-13885  | us-east-3 | 1 | B10 |  |
|   rn-west-13885  | us-east-3 | 2 | B10 |  |
|   rn-west-13885  | us-east-3 | 3 | B10 |  |
|   rn-west-13885  | us-east-3 | 4 | B10 |  |
|   rn-west-13885  | us-east-3 | 5 | B10 |  |
|   rn-west-13917  | us-central-4 | 1 | B10 |  |
|   rn-west-13917  | us-central-4 | 2 | B10 |  |
|   rn-west-13917  | us-central-4 | 3 | B10 |  |
|   rn-west-13917  | us-central-4 | 4 | B10 |  |
|   rn-west-13917  | us-central-4 | 5 | B10 |  |
|   rn-west-13941  | us-east-3 | 1 | B10 |  |
|   rn-west-13941  | us-east-3 | 2 | B10 |  |
|   rn-west-13941  | us-east-3 | 3 | B10 |  |
|   rn-west-13941  | us-east-3 | 4 | B10 |  |
|   rn-west-13941  | us-east-3 | 5 | B10 |  |
|   rn-west-13973  | us-central-4 | 1 | B10 |  |
|   rn-west-13973  | us-central-4 | 2 | B10 |  |
|   rn-west-13973  | us-central-4 | 3 | B10 |  |
|   rn-west-13973  | us-central-4 | 4 | B10 |  |
|   rn-west-13973  | us-central-4 | 5 | B10 |  |
|   rn-west-13999  | us-east-3 | 1 | B10 |  |
|   rn-west-13999  | us-east-3 | 2 | B10 |  |
|   rn-west-13999  | us-east-3 | 3 | B10 |  |
|   rn-west-13999  | us-east-3 | 4 | B10 |  |
|   rn-west-13999  | us-east-3 | 5 | B10 |  |
|   rn-west-14026  | us-central-4 | 1 | B10 |  |
|   rn-west-14026  | us-central-4 | 2 | B10 |  |
|   rn-west-14026  | us-central-4 | 3 | B10 |  |
|   rn-west-14026  | us-central-4 | 4 | B10 |  |
|   rn-west-14026  | us-east-3 | 5 | B10 |  |
|   rn-west-14056  | us-east-3 | 1 | B10 |  |
|   rn-west-14056  | us-east-3 | 2 | B10 |  |
|   rn-west-14056  | us-east-3 | 3 | B10 |  |
|   rn-west-14056  | us-east-3 | 4 | B10 |  |
|   rn-west-14056  | us-east-3 | 5 | B10 |  |
|   rn-west-14083  | us-central-4 | 1 | B10 |  |
|   rn-west-14083  | us-central-4 | 2 | B10 |  |
|   rn-west-14083  | us-central-4 | 3 | B10 |  |
|   rn-west-14083  | us-central-4 | 4 | B10 |  |
|   rn-west-14083  | us-central-4 | 5 | B10 |  |
|   rn-west-14115  | us-east-3 | 1 | B10 |  |
|   rn-west-14115  | us-east-3 | 2 | B10 |  |
|   rn-west-14115  | us-east-3 | 3 | B10 |  |
|   rn-west-14115  | us-east-3 | 4 | B10 |  |
|   rn-west-14115  | us-east-3 | 5 | B10 |  |
|   rn-west-14139  | us-central-4 | 1 | B10 |  |
|   rn-west-14139  | us-central-4 | 2 | B10 |  |
|   rn-west-14139  | us-central-4 | 3 | B10 |  |
|   rn-west-14139  | us-central-4 | 4 | B10 |  |
|   rn-west-14139  | us-central-4 | 5 | B10 |  |
|   rn-west-14168  | us-east-3 | 1 | B10 |  |
|   rn-west-14168  | us-east-3 | 2 | B10 |  |
|   rn-west-14168  | us-east-3 | 3 | B10 |  |
|   rn-west-14168  | us-east-3 | 4 | B10 |  |
|   rn-west-14168  | us-east-3 | 5 | B10 |  |
|   rn-west-14195  | us-central-4 | 1 | B10 |  |
|   rn-west-14195  | us-central-4 | 2 | B10 |  |
|   rn-west-14195  | us-central-4 | 3 | B10 |  |
|   rn-west-14195  | us-east-3 | 4 | B10 |  |
|   rn-west-14195  | us-central-4 | 5 | B10 |  |
|   rn-west-14223  | us-east-3 | 1 | B10 |  |
|   rn-west-14223  | us-east-3 | 2 | B10 |  |
|   rn-west-14223  | us-east-3 | 3 | B10 |  |
|   rn-west-14223  | us-east-3 | 4 | B10 |  |
|   rn-west-14223  | us-east-3 | 5 | B10 |  |
|   rn-west-14253  | us-central-4 | 1 | B10 |  |
|   rn-west-14253  | us-central-4 | 2 | B10 |  |
|   rn-west-14253  | us-central-4 | 3 | B10 |  |
|   rn-west-14253  | us-central-4 | 4 | B10 |  |
|   rn-west-14253  | us-central-4 | 5 | B10 |  |
|   rn-west-14277  | us-east-3 | 1 | B10 |  |
|   rn-west-14277  | us-east-3 | 2 | B10 |  |
|   rn-west-14277  | us-east-3 | 3 | B10 |  |
|   rn-west-14277  | us-east-3 | 4 | B10 |  |
|   rn-west-14277  | us-east-3 | 5 | B10 |  |
|   rn-west-14309  | us-central-4 | 1 | B10 |  |
|   rn-west-14309  | us-central-4 | 2 | B10 |  |
|   rn-west-14309  | us-central-4 | 3 | B10 |  |
|   rn-west-14309  | us-central-4 | 4 | B10 |  |
|   rn-west-14309  | us-central-4 | 5 | B10 |  |
|   rn-west-14336  | us-east-3 | 1 | B10 |  |
|   rn-west-14336  | us-east-3 | 2 | B10 |  |
|   rn-west-14336  | us-east-3 | 3 | B10 |  |
|   rn-west-14336  | us-east-3 | 4 | B10 |  |
|   rn-west-14336  | us-east-3 | 5 | B10 |  |
|   rn-west-14367  | us-central-4 | 1 | B10 |  |
|   rn-west-14367  | us-central-4 | 2 | B10 |  |
|   rn-west-14367  | us-central-4 | 3 | B10 |  |
|   rn-west-14367  | us-central-4 | 4 | B10 |  |
|   rn-west-14367  | us-central-4 | 5 | B10 |  |
|   rn-west-14395  | us-east-3 | 1 | B10 |  |
|   rn-west-14395  | us-east-3 | 2 | B10 |  |
|   rn-west-14395  | us-east-3 | 3 | B10 |  |
|   rn-west-14395  | us-east-3 | 4 | B10 |  |
|   rn-west-14395  | us-east-3 | 5 | B10 |  |
|   rn-west-14421  | us-central-4 | 1 | B10 |  |
|   rn-west-14421  | us-central-4 | 2 | B10 |  |
|   rn-west-14421  | us-central-4 | 3 | B10 |  |
|   rn-west-14421  | us-central-4 | 4 | B10 |  |
|   rn-west-14421  | us-central-4 | 5 | B10 |  |
|   rn-west-14447  | us-east-3 | 1 | B10 |  |
|   rn-west-14447  | us-east-3 | 2 | B10 |  |
|   rn-west-14447  | us-east-3 | 3 | B10 |  |
|   rn-west-14447  | us-east-3 | 4 | B10 |  |
|   rn-west-14447  | us-east-3 | 5 | B10 |  |
|   rn-west-14478  | us-central-4 | 1 | B10 |  |
|   rn-west-14478  | us-central-4 | 2 | B10 |  |
|   rn-west-14478  | us-central-4 | 3 | B10 |  |
|   rn-west-14478  | us-central-4 | 4 | B10 |  |
|   rn-west-14478  | us-central-4 | 5 | B10 |  |
|   rn-west-14502  | us-east-3 | 1 | B10 |  |
|   rn-west-14502  | us-east-3 | 2 | B10 |  |
|   rn-west-14502  | us-east-3 | 3 | B10 |  |
|   rn-west-14502  | us-east-3 | 4 | B10 |  |
|   rn-west-14502  | us-east-3 | 5 | B10 |  |
|   rn-west-14535  | us-central-4 | 1 | B10 |  |
|   rn-west-14535  | us-east-3 | 2 | B10 |  |
|   rn-west-14535  | us-east-3 | 3 | B10 |  |
|   rn-west-14535  | us-central-4 | 4 | B10 |  |
|   rn-west-14535  | us-central-4 | 5 | B10 |  |
|   rn-west-14562  | us-east-3 | 1 | B10 |  |
|   rn-west-14562  | us-east-3 | 2 | B10 |  |
|   rn-west-14562  | us-east-3 | 3 | B10 |  |
|   rn-west-14562  | us-east-3 | 4 | B10 |  |
|   rn-west-14562  | us-east-3 | 5 | B10 |  |
|   rn-west-14585  | us-central-4 | 1 | B10 |  |
|   rn-west-14585  | us-central-4 | 2 | B10 |  |
|   rn-west-14585  | us-central-4 | 3 | B10 |  |
|   rn-west-14585  | us-central-4 | 4 | B10 |  |
|   rn-west-14585  | us-central-4 | 5 | B10 |  |
|   rn-west-14613  | us-east-3 | 1 | B10 |  |
|   rn-west-14613  | us-east-3 | 2 | B10 |  |
|   rn-west-14613  | us-east-3 | 3 | B10 |  |
|   rn-west-14613  | us-east-3 | 4 | B10 |  |
|   rn-west-14613  | us-east-3 | 5 | B10 |  |
|   rn-west-14647  | us-central-4 | 1 | B10 |  |
|   rn-west-14647  | us-central-4 | 2 | B10 |  |
|   rn-west-14647  | us-central-4 | 3 | B10 |  |
|   rn-west-14647  | us-central-4 | 4 | B10 |  |
|   rn-west-14647  | us-central-4 | 5 | B10 |  |
|   rn-west-14670  | us-east-3 | 1 | B10 |  |
|   rn-west-14670  | us-east-3 | 2 | B10 |  |
|   rn-west-14670  | us-east-3 | 3 | B10 |  |
|   rn-west-14670  | us-east-3 | 4 | B10 |  |
|   rn-west-14670  | us-east-3 | 5 | B10 |  |
|   rn-west-14702  | us-central-4 | 1 | B10 |  |
|   rn-west-14702  | us-central-4 | 2 | B10 |  |
|   rn-west-14702  | us-central-4 | 3 | B10 |  |
|   rn-west-14702  | us-central-4 | 4 | B10 |  |
|   rn-west-14702  | us-central-4 | 5 | B10 |  |
|   rn-west-14728  | us-east-3 | 1 | B10 |  |
|   rn-west-14728  | us-east-3 | 2 | B10 |  |
|   rn-west-14728  | us-east-3 | 3 | B10 |  |
|   rn-west-14728  | us-east-3 | 4 | B10 |  |
|   rn-west-14728  | us-east-3 | 5 | B10 |  |
|   rn-west-14753  | us-central-4 | 1 | B10 |  |
|   rn-west-14753  | us-central-4 | 2 | B10 |  |
|   rn-west-14753  | us-east-3 | 3 | B10 |  |
|   rn-west-14753  | us-central-4 | 4 | B10 |  |
|   rn-west-14753  | us-central-4 | 5 | B10 |  |
| RN-WEST-14782 | us-east-3 | 1 | B11 |  |
| RN-WEST-14782 | us-east-3 | 2 | B11 |  |
| RN-WEST-14782 | us-east-3 | 3 | B11 |  |
| RN-WEST-14782 | us-east-3 | 4 | B11 |  |
| RN-WEST-14782 | us-east-3 | 5 | B11 |  |
| RN-WEST-14811 | us-central-4 | 1 | B11 |  |
| RN-WEST-14811 | us-central-4 | 2 | B11 |  |
| RN-WEST-14811 | us-central-4 | 3 | B11 |  |
| RN-WEST-14811 | us-central-4 | 4 | B11 |  |
| RN-WEST-14811 | us-central-4 | 5 | B11 |  |
| RN-WEST-14838 | us-east-3 | 1 | B11 |  |
| RN-WEST-14838 | us-east-3 | 2 | B11 |  |
| RN-WEST-14838 | us-east-3 | 3 | B11 |  |
| RN-WEST-14838 | us-east-3 | 4 | B11 |  |
| RN-WEST-14838 | us-east-3 | 5 | B11 |  |
| RN-WEST-14871 | us-central-4 | 1 | B11 |  |
| RN-WEST-14871 | us-central-4 | 2 | B11 |  |
| RN-WEST-14871 | us-central-4 | 3 | B11 |  |
| RN-WEST-14871 | us-central-4 | 4 | B11 |  |
| RN-WEST-14871 | us-central-4 | 5 | B11 |  |
| RN-WEST-14893 | us-east-3 | 1 | B11 |  |
| RN-WEST-14893 | us-east-3 | 2 | B11 |  |
| RN-WEST-14893 | us-east-3 | 3 | B11 |  |
| RN-WEST-14893 | us-east-3 | 4 | B11 |  |
| RN-WEST-14893 | us-east-3 | 5 | B11 |  |
| RN-WEST-14925 | us-central-4 | 1 | B11 |  |
| RN-WEST-14925 | us-east-3 | 2 | B11 |  |
| RN-WEST-14925 | us-central-4 | 3 | B11 |  |
| RN-WEST-14925 | us-central-4 | 4 | B11 |  |
| RN-WEST-14925 | us-central-4 | 5 | B11 |  |
| RN-WEST-14953 | us-east-3 | 1 | B11 |  |
| RN-WEST-14953 | us-east-3 | 2 | B11 |  |
| RN-WEST-14953 | us-east-3 | 3 | B11 |  |
| RN-WEST-14953 | us-east-3 | 4 | B11 |  |
| RN-WEST-14953 | us-east-3 | 5 | B11 |  |
| RN-WEST-14977 | us-central-4 | 1 | B11 |  |
| RN-WEST-14977 | us-central-4 | 2 | B11 |  |
| RN-WEST-14977 | us-east-3 | 3 | B11 |  |
| RN-WEST-14977 | us-central-4 | 4 | B11 |  |
| RN-WEST-14977 | us-central-4 | 5 | B11 |  |
| RN-WEST-15009 | us-east-3 | 1 | B11 |  |
| RN-WEST-15009 | us-east-3 | 2 | B11 |  |
| RN-WEST-15009 | us-east-3 | 3 | B11 |  |
| RN-WEST-15009 | us-east-3 | 4 | B11 |  |
| RN-WEST-15009 | us-east-3 | 5 | B11 |  |
| RN-WEST-15037 | us-central-4 | 1 | B11 |  |
| RN-WEST-15037 | us-central-4 | 2 | B11 |  |
| RN-WEST-15037 | us-central-4 | 3 | B11 |  |
| RN-WEST-15037 | us-central-4 | 4 | B11 |  |
| RN-WEST-15037 | us-central-4 | 5 | B11 |  |
| RN-WEST-15062 | us-east-3 | 1 | B11 |  |
| RN-WEST-15062 | us-east-3 | 2 | B11 |  |
| RN-WEST-15062 | us-east-3 | 3 | B11 |  |
| RN-WEST-15062 | us-east-3 | 4 | B11 |  |
| RN-WEST-15062 | us-east-3 | 5 | B11 |  |
| RN-WEST-15092 | us-central-4 | 1 | B11 |  |
| RN-WEST-15092 | us-central-4 | 2 | B11 |  |
| RN-WEST-15092 | us-central-4 | 3 | B11 |  |
| RN-WEST-15092 | us-central-4 | 4 | B11 |  |
| RN-WEST-15092 | us-central-4 | 5 | B11 |  |
| RN-WEST-15122 | us-east-3 | 1 | B11 |  |
| RN-WEST-15122 | us-east-3 | 2 | B11 |  |
| RN-WEST-15122 | us-east-3 | 3 | B11 |  |
| RN-WEST-15122 | us-central-4 | 4 | B11 |  |
| RN-WEST-15122 | us-east-3 | 5 | B11 |  |
| RN-WEST-15151 | us-central-4 | 1 | B11 |  |
| RN-WEST-15151 | us-central-4 | 2 | B11 |  |
| RN-WEST-15151 | us-central-4 | 3 | B11 |  |
| RN-WEST-15151 | us-east-3 | 4 | B11 |  |
| RN-WEST-15151 | us-central-4 | 5 | B11 |  |
| RN-WEST-15175 | us-east-3 | 1 | B11 |  |
| RN-WEST-15175 | us-east-3 | 2 | B11 |  |
| RN-WEST-15175 | us-east-3 | 3 | B11 |  |
| RN-WEST-15175 | us-east-3 | 4 | B11 |  |
| RN-WEST-15175 | us-east-3 | 5 | B11 |  |
| RN-WEST-15202 | us-central-4 | 1 | B11 |  |
| RN-WEST-15202 | us-central-4 | 2 | B11 |  |
| RN-WEST-15202 | us-central-4 | 3 | B11 |  |
| RN-WEST-15202 | us-central-4 | 4 | B11 |  |
| RN-WEST-15202 | us-central-4 | 5 | B11 |  |
| RN-WEST-15229 | us-east-3 | 1 | B11 |  |
| RN-WEST-15229 | us-east-3 | 2 | B11 |  |
| RN-WEST-15229 | us-east-3 | 3 | B11 |  |
| RN-WEST-15229 | us-east-3 | 4 | B11 |  |
| RN-WEST-15229 | us-east-3 | 5 | B11 |  |
| RN-WEST-15258 | us-central-4 | 1 | B11 |  |
| RN-WEST-15258 | us-east-3 | 2 | B11 |  |
| RN-WEST-15258 | us-central-4 | 3 | B11 |  |
| RN-WEST-15258 | us-east-3 | 4 | B11 |  |
| RN-WEST-15258 | us-central-4 | 5 | B11 |  |
| RN-WEST-15286 | us-east-3 | 1 | B11 |  |
| RN-WEST-15286 | us-east-3 | 2 | B11 |  |
| RN-WEST-15286 | us-east-3 | 3 | B11 |  |
| RN-WEST-15286 | us-east-3 | 4 | B11 |  |
| RN-WEST-15286 | us-east-3 | 5 | B11 |  |
| RN-WEST-15313 | us-central-4 | 1 | B11 |  |
| RN-WEST-15313 | us-central-4 | 2 | B11 |  |
| RN-WEST-15313 | us-central-4 | 3 | B11 |  |
| RN-WEST-15313 | us-central-4 | 4 | B11 |  |
| RN-WEST-15313 | us-central-4 | 5 | B11 |  |
| RN-WEST-15342 | us-east-3 | 1 | B11 |  |
| RN-WEST-15342 | us-east-3 | 2 | B11 |  |
| RN-WEST-15342 | us-east-3 | 3 | B11 |  |
| RN-WEST-15342 | us-east-3 | 4 | B11 |  |
| RN-WEST-15342 | us-east-3 | 5 | B11 |  |
| RN-WEST-15369 | us-central-4 | 1 | B11 |  |
| RN-WEST-15369 | us-central-4 | 2 | B11 |  |
| RN-WEST-15369 | us-central-4 | 3 | B11 |  |
| RN-WEST-15369 | us-central-4 | 4 | B11 |  |
| RN-WEST-15369 | us-central-4 | 5 | B11 |  |
| RN-WEST-15401 | us-east-3 | 1 | B11 |  |
| RN-WEST-15401 | us-east-3 | 2 | B11 |  |
| RN-WEST-15401 | us-east-3 | 3 | B11 |  |
| RN-WEST-15401 | us-east-3 | 4 | B11 |  |
| RN-WEST-15401 | us-east-3 | 5 | B11 |  |
| RN-WEST-15427 | us-central-4 | 1 | B11 |  |
| RN-WEST-15427 | us-central-4 | 2 | B11 |  |
| RN-WEST-15427 | us-central-4 | 3 | B11 |  |
| RN-WEST-15427 | us-central-4 | 4 | B11 |  |
| RN-WEST-15427 | us-east-3 | 5 | B11 |  |
| RN-WEST-15456 | us-east-3 | 1 | B11 |  |
| RN-WEST-15456 | us-east-3 | 2 | B11 |  |
| RN-WEST-15456 | us-east-3 | 3 | B11 |  |
| RN-WEST-15456 | us-east-3 | 4 | B11 |  |
| RN-WEST-15456 | us-east-3 | 5 | B11 |  |
| RN-WEST-15485 | us-central-4 | 1 | B11 |  |
| RN-WEST-15485 | us-central-4 | 2 | B11 |  |
| RN-WEST-15485 | us-central-4 | 3 | B11 |  |
| RN-WEST-15485 | us-central-4 | 4 | B11 |  |
| RN-WEST-15485 | us-central-4 | 5 | B11 |  |
| RN-WEST-15511 | us-east-3 | 1 | B11 |  |
| RN-WEST-15511 | us-east-3 | 2 | B11 |  |
| RN-WEST-15511 | us-east-3 | 3 | B11 |  |
| RN-WEST-15511 | us-east-3 | 4 | B11 |  |
| RN-WEST-15511 | us-east-3 | 5 | B11 |  |
| RN-WEST-15542 | us-central-4 | 1 | B11 |  |
| RN-WEST-15542 | us-central-4 | 2 | B11 |  |
| RN-WEST-15542 | us-central-4 | 3 | B11 |  |
| RN-WEST-15542 | us-central-4 | 4 | B11 |  |
| RN-WEST-15542 | us-central-4 | 5 | B11 |  |
| RN-WEST-15565 | us-east-3 | 1 | B11 |  |
| RN-WEST-15565 | us-east-3 | 2 | B11 |  |
| RN-WEST-15565 | us-east-3 | 3 | B11 |  |
| RN-WEST-15565 | us-east-3 | 4 | B11 |  |
| RN-WEST-15565 | us-east-3 | 5 | B11 |  |
| RN-WEST-15598 | us-central-4 | 1 | B11 |  |
| RN-WEST-15598 | us-central-4 | 2 | B11 |  |
| RN-WEST-15598 | us-central-4 | 3 | B11 |  |
| RN-WEST-15598 | us-central-4 | 4 | B11 |  |
| RN-WEST-15598 | us-central-4 | 5 | B11 |  |
| RN-WEST-15625 | us-east-3 | 1 | B11 |  |
| RN-WEST-15625 | us-east-3 | 2 | B11 |  |
| RN-WEST-15625 | us-east-3 | 3 | B11 |  |
| RN-WEST-15625 | us-east-3 | 4 | B11 |  |
| RN-WEST-15625 | us-east-3 | 5 | B11 |  |
| RN-WEST-15651 | us-central-4 | 1 | B11 |  |
| RN-WEST-15651 | us-central-4 | 2 | B11 |  |
| RN-WEST-15651 | us-central-4 | 3 | B11 |  |
| RN-WEST-15651 | us-central-4 | 4 | B11 |  |
| RN-WEST-15651 | us-central-4 | 5 | B11 |  |
| RN-WEST-15681 | us-east-3 | 1 | B11 |  |
| RN-WEST-15681 | us-east-3 | 2 | B11 |  |
| RN-WEST-15681 | us-east-3 | 3 | B11 |  |
| RN-WEST-15681 | us-east-3 | 4 | B11 |  |
| RN-WEST-15681 | us-east-3 | 5 | B11 |  |
| RN-WEST-15707 | us-central-4 | 1 | B11 |  |
| RN-WEST-15707 | us-central-4 | 2 | B11 |  |
| RN-WEST-15707 | us-central-4 | 3 | B11 |  |
| RN-WEST-15707 | us-central-4 | 4 | B11 |  |
| RN-WEST-15707 | us-east-3 | 5 | B11 |  |
| RN-WEST-15739 | us-east-3 | 1 | B11 |  |
| RN-WEST-15739 | us-east-3 | 2 | B11 |  |
| RN-WEST-15739 | us-east-3 | 3 | B11 |  |
| RN-WEST-15739 | us-east-3 | 4 | B11 |  |
| RN-WEST-15739 | us-east-3 | 5 | B11 |  |
| RN-WEST-15762 | us-central-4 | 1 | B11 |  |
| RN-WEST-15762 | us-central-4 | 2 | B11 |  |
| RN-WEST-15762 | us-central-4 | 3 | B11 |  |
| RN-WEST-15762 | us-central-4 | 4 | B11 |  |
| RN-WEST-15762 | us-east-3 | 5 | B11 |  |
| RN-WEST-15790 | us-east-3 | 1 | B11 |  |
| RN-WEST-15790 | us-east-3 | 2 | B11 |  |
| RN-WEST-15790 | us-east-3 | 3 | B11 |  |
| RN-WEST-15790 | us-east-3 | 4 | B11 |  |
| RN-WEST-15790 | us-east-3 | 5 | B11 |  |
| RN-WEST-15822 | us-central-4 | 1 | B11 |  |
| RN-WEST-15822 | us-central-4 | 2 | B11 |  |
| RN-WEST-15822 | us-central-4 | 3 | B11 |  |
| RN-WEST-15822 | us-central-4 | 4 | B11 |  |
| RN-WEST-15822 | us-central-4 | 5 | B11 |  |
| RN-WEST-15846 | us-east-3 | 1 | B11 |  |
| RN-WEST-15846 | us-east-3 | 2 | B11 |  |
| RN-WEST-15846 | us-east-3 | 3 | B11 |  |
| RN-WEST-15846 | us-east-3 | 4 | B11 |  |
| RN-WEST-15846 | us-east-3 | 5 | B11 |  |
| RN-WEST-15873 | us-central-4 | 1 | B11 |  |
| RN-WEST-15873 | us-central-4 | 2 | B11 |  |
| RN-WEST-15873 | us-central-4 | 3 | B11 |  |
| RN-WEST-15873 | us-central-4 | 4 | B11 |  |
| RN-WEST-15873 | us-east-3 | 5 | B11 |  |
| RN-WEST-15906 | us-east-3 | 1 | B11 |  |
| RN-WEST-15906 | us-east-3 | 2 | B11 |  |
| RN-WEST-15906 | us-east-3 | 3 | B11 |  |
| RN-WEST-15906 | us-east-3 | 4 | B11 |  |
| RN-WEST-15906 | us-east-3 | 5 | B11 |  |
| RN-WEST-15935 | us-central-4 | 1 | B11 |  |
| RN-WEST-15935 | us-central-4 | 2 | B11 |  |
| RN-WEST-15935 | us-central-4 | 3 | B11 |  |
| RN-WEST-15935 | us-central-4 | 4 | B11 |  |
| RN-WEST-15935 | us-central-4 | 5 | B11 |  |
| RN-WEST-15963 | us-east-3 | 1 | B11 |  |
| RN-WEST-15963 | us-east-3 | 2 | B11 |  |
| RN-WEST-15963 | us-east-3 | 3 | B11 |  |
| RN-WEST-15963 | us-east-3 | 4 | B11 |  |
| RN-WEST-15963 | us-east-3 | 5 | B11 |  |
| RN-WEST-15989 | us-central-4 | 1 | B11 |  |
| RN-WEST-15989 | us-central-4 | 2 | B11 |  |
| RN-WEST-15989 | us-central-4 | 3 | B11 |  |
| RN-WEST-15989 | us-central-4 | 4 | B11 |  |
| RN-WEST-15989 | us-central-4 | 5 | B11 |  |
| RN-WEST-16015 | us-east-3 | 1 | B11 |  |
| RN-WEST-16015 | us-east-3 | 2 | B11 |  |
| RN-WEST-16015 | us-east-3 | 3 | B11 |  |
| RN-WEST-16015 | us-central-4 | 4 | B11 |  |
| RN-WEST-16015 | us-east-3 | 5 | B11 |  |
| RN-WEST-16044 | us-central-4 | 1 | B11 |  |
| RN-WEST-16044 | us-central-4 | 2 | B11 |  |
| RN-WEST-16044 | us-central-4 | 3 | B11 |  |
| RN-WEST-16044 | us-central-4 | 4 | B11 |  |
| RN-WEST-16044 | us-central-4 | 5 | B11 |  |
| RN-WEST-16072 | us-east-3 | 1 | B11 |  |
| RN-WEST-16072 | us-east-3 | 2 | B11 |  |
| RN-WEST-16072 | us-east-3 | 3 | B11 |  |
| RN-WEST-16072 | us-east-3 | 4 | B11 |  |
| RN-WEST-16072 | us-east-3 | 5 | B11 |  |
| RN-WEST-16103 | us-central-4 | 1 | B11 |  |
| RN-WEST-16103 | us-central-4 | 2 | B11 |  |
| RN-WEST-16103 | us-east-3 | 3 | B11 |  |
| RN-WEST-16103 | us-central-4 | 4 | B11 |  |
| RN-WEST-16103 | us-east-3 | 5 | B11 |  |
| RN-WEST-16130 | us-east-3 | 1 | B11 |  |
| RN-WEST-16130 | us-east-3 | 2 | B11 |  |
| RN-WEST-16130 | us-east-3 | 3 | B11 |  |
| RN-WEST-16130 | us-east-3 | 4 | B11 |  |
| RN-WEST-16130 | us-east-3 | 5 | B11 |  |
| RN-WEST-16153 | us-central-4 | 1 | B11 |  |
| RN-WEST-16153 | us-central-4 | 2 | B11 |  |
| RN-WEST-16153 | us-central-4 | 3 | B11 |  |
| RN-WEST-16153 | us-central-4 | 4 | B11 |  |
| RN-WEST-16153 | us-central-4 | 5 | B11 |  |
| RN-WEST-16186 | us-east-3 | 1 | B11 |  |
| RN-WEST-16186 | us-east-3 | 2 | B11 |  |
| RN-WEST-16186 | us-east-3 | 3 | B11 |  |
| RN-WEST-16186 | us-central-4 | 4 | B11 |  |
| RN-WEST-16186 | us-east-3 | 5 | B11 |  |
| RN-WEST-16213 | us-central-4 | 1 | B11 |  |
| RN-WEST-16213 | us-central-4 | 2 | B11 |  |
| RN-WEST-16213 | us-central-4 | 3 | B11 |  |
| RN-WEST-16213 | us-central-4 | 4 | B11 |  |
| RN-WEST-16213 | us-central-4 | 5 | B11 |  |
| RN-WEST-16238 | us-east-3 | 1 | B11 |  |
| RN-WEST-16238 | us-east-3 | 2 | B11 |  |
| RN-WEST-16238 | us-east-3 | 3 | B11 |  |
| RN-WEST-16238 | us-east-3 | 4 | B11 |  |
| RN-WEST-16238 | us-east-3 | 5 | B11 |  |
| RN-WEST-16267 | us-central-4 | 1 | B11 |  |
| RN-WEST-16267 | us-central-4 | 2 | B11 |  |
| RN-WEST-16267 | us-central-4 | 3 | B11 |  |
| RN-WEST-16267 | us-central-4 | 4 | B11 |  |
| RN-WEST-16267 | us-central-4 | 5 | B11 |  |
| RN-WEST-16297 | us-east-3 | 1 | B11 |  |
| RN-WEST-16297 | us-east-3 | 2 | B11 |  |
| RN-WEST-16297 | us-east-3 | 3 | B11 |  |
| RN-WEST-16297 | us-east-3 | 4 | B11 |  |
| RN-WEST-16297 | us-east-3 | 5 | B11 |  |
| RN-WEST-16324 | us-central-4 | 1 | B11 |  |
| RN-WEST-16324 | us-central-4 | 2 | B11 |  |
| RN-WEST-16324 | us-central-4 | 3 | B11 |  |
| RN-WEST-16324 | us-central-4 | 4 | B11 |  |
| RN-WEST-16324 | us-central-4 | 5 | B11 |  |
| RN-WEST-16354 | us-east-3 | 1 | B11 |  |
| RN-WEST-16354 | us-east-3 | 2 | B11 |  |
| RN-WEST-16354 | us-east-3 | 3 | B11 |  |
| RN-WEST-16354 | us-east-3 | 4 | B11 |  |
| RN-WEST-16354 | us-east-3 | 5 | B11 |  |
| RN-WEST-16379 | us-central-4 | 1 | B11 |  |
| RN-WEST-16379 | us-central-4 | 2 | B11 |  |
| RN-WEST-16379 | us-central-4 | 3 | B11 |  |
| RN-WEST-16379 | us-east-3 | 4 | B11 |  |
| RN-WEST-16379 | us-central-4 | 5 | B11 |  |
| RN-WEST-16409 | us-east-3 | 1 | B11 |  |
| RN-WEST-16409 | us-east-3 | 2 | B11 |  |
| RN-WEST-16409 | us-east-3 | 3 | B11 |  |
| RN-WEST-16409 | us-east-3 | 4 | B11 |  |
| RN-WEST-16409 | us-east-3 | 5 | B11 |  |
| RN-WEST-16434 | us-central-4 | 1 | B11 |  |
| RN-WEST-16434 | us-central-4 | 2 | B11 |  |
| RN-WEST-16434 | us-central-4 | 3 | B11 |  |
| RN-WEST-16434 | us-central-4 | 4 | B11 |  |
| RN-WEST-16434 | us-central-4 | 5 | B11 |  |
| RN-WEST-16461 | us-east-3 | 1 | B11 |  |
| RN-WEST-16461 | us-east-3 | 2 | B11 |  |
| RN-WEST-16461 | us-east-3 | 3 | B11 |  |
| RN-WEST-16461 | us-east-3 | 4 | B11 |  |
| RN-WEST-16461 | us-east-3 | 5 | B11 |  |
| RN-WEST-16492 | us-central-4 | 1 | B11 |  |
| RN-WEST-16492 | us-central-4 | 2 | B11 |  |
| RN-WEST-16492 | us-central-4 | 3 | B11 |  |
| RN-WEST-16492 | us-central-4 | 4 | B11 |  |
| RN-WEST-16492 | us-central-4 | 5 | B11 |  |
| RN-WEST-16522 | us-east-3 | 1 | B11 |  |
| RN-WEST-16522 | us-east-3 | 2 | B11 |  |
| RN-WEST-16522 | us-east-3 | 3 | B11 |  |
| RN-WEST-16522 | us-east-3 | 4 | B11 |  |
| RN-WEST-16522 | us-east-3 | 5 | B11 |  |
| RN-WEST-16549 | us-central-4 | 1 | B11 |  |
| RN-WEST-16549 | us-east-3 | 2 | B11 |  |
| RN-WEST-16549 | us-central-4 | 3 | B11 |  |
| RN-WEST-16549 | us-central-4 | 4 | B11 |  |
| RN-WEST-16549 | us-central-4 | 5 | B11 |  |
| RN-WEST-16574 | us-east-3 | 1 | B11 |  |
| RN-WEST-16574 | us-east-3 | 2 | B11 |  |
| RN-WEST-16574 | us-east-3 | 3 | B11 |  |
| RN-WEST-16574 | us-east-3 | 4 | B11 |  |
| RN-WEST-16574 | us-east-3 | 5 | B11 |  |
| RN-WEST-16607 | us-central-4 | 1 | B11 |  |
| RN-WEST-16607 | us-central-4 | 2 | B11 |  |
| RN-WEST-16607 | us-central-4 | 3 | B11 |  |
| RN-WEST-16607 | us-central-4 | 4 | B11 |  |
| RN-WEST-16607 | us-central-4 | 5 | B11 |  |
| RN-WEST-16634 | us-east-3 | 1 | B11 |  |
| RN-WEST-16634 | us-east-3 | 2 | B11 |  |
| RN-WEST-16634 | us-east-3 | 3 | B11 |  |
| RN-WEST-16634 | us-east-3 | 4 | B11 |  |
| RN-WEST-16634 | us-east-3 | 5 | B11 |  |
| RN-WEST-16659 | us-central-4 | 1 | B11 |  |
| RN-WEST-16659 | us-central-4 | 2 | B11 |  |
| RN-WEST-16659 | us-central-4 | 3 | B11 |  |
| RN-WEST-16659 | us-central-4 | 4 | B11 |  |
| RN-WEST-16659 | us-central-4 | 5 | B11 |  |
| RN-WEST-16691 | us-east-3 | 1 | B11 |  |
| RN-WEST-16691 | us-east-3 | 2 | B11 |  |
| RN-WEST-16691 | us-east-3 | 3 | B11 |  |
| RN-WEST-16691 | us-east-3 | 4 | B11 |  |
| RN-WEST-16691 | us-east-3 | 5 | B11 |  |
| RN-WEST-16713 | us-central-4 | 1 | B11 |  |
| RN-WEST-16713 | us-central-4 | 2 | B11 |  |
| RN-WEST-16713 | us-central-4 | 3 | B11 |  |
| RN-WEST-16713 | us-central-4 | 4 | B11 |  |
| RN-WEST-16713 | us-central-4 | 5 | B11 |  |
| RN-WEST-16741 | us-east-3 | 1 | B11 |  |
| RN-WEST-16741 | us-east-3 | 2 | B11 |  |
| RN-WEST-16741 | us-east-3 | 3 | B11 |  |
| RN-WEST-16741 | us-east-3 | 4 | B11 |  |
| RN-WEST-16741 | us-east-3 | 5 | B11 |  |
| RN-WEST-16770 | us-central-4 | 1 | B11 |  |
| RN-WEST-16770 | us-central-4 | 2 | B11 |  |
| RN-WEST-16770 | us-central-4 | 3 | B11 |  |
| RN-WEST-16770 | us-central-4 | 4 | B11 |  |
| RN-WEST-16770 | us-central-4 | 5 | B11 |  |
| RN-WEST-16798 | us-east-3 | 1 | B11 |  |
| RN-WEST-16798 | us-central-4 | 2 | B11 |  |
| RN-WEST-16798 | us-east-3 | 3 | B11 |  |
| RN-WEST-16798 | us-east-3 | 4 | B11 |  |
| RN-WEST-16798 | us-east-3 | 5 | B11 |  |
| RN-WEST-16828 | us-central-4 | 1 | B11 |  |
| RN-WEST-16828 | us-central-4 | 2 | B11 |  |
| RN-WEST-16828 | us-central-4 | 3 | B11 |  |
| RN-WEST-16828 | us-central-4 | 4 | B11 |  |
| RN-WEST-16828 | us-central-4 | 5 | B11 |  |
| RN-WEST-16858 | us-east-3 | 1 | B11 |  |
| RN-WEST-16858 | us-east-3 | 2 | B11 |  |
| RN-WEST-16858 | us-east-3 | 3 | B11 |  |
| RN-WEST-16858 | us-east-3 | 4 | B11 |  |
| RN-WEST-16858 | us-east-3 | 5 | B11 |  |
| RN-WEST-16887 | us-central-4 | 1 | B11 |  |
| RN-WEST-16887 | us-central-4 | 2 | B11 |  |
| RN-WEST-16887 | us-central-4 | 3 | B11 |  |
| RN-WEST-16887 | us-central-4 | 4 | B11 |  |
| RN-WEST-16887 | us-central-4 | 5 | B11 |  |
| RN-WEST-16910 | us-east-3 | 1 | B11 |  |
| RN-WEST-16910 | us-east-3 | 2 | B11 |  |
| RN-WEST-16910 | us-east-3 | 3 | B11 |  |
| RN-WEST-16910 | us-east-3 | 4 | B11 |  |
| RN-WEST-16910 | us-east-3 | 5 | B11 |  |
| RN-WEST-16940 | us-central-4 | 1 | B11 |  |
| RN-WEST-16940 | us-central-4 | 2 | B11 |  |
| RN-WEST-16940 | us-central-4 | 3 | B11 |  |
| RN-WEST-16940 | us-central-4 | 4 | B11 |  |
| RN-WEST-16940 | us-central-4 | 5 | B11 |  |
| RN-WEST-16970 | us-east-3 | 1 | B11 |  |
| RN-WEST-16970 | us-east-3 | 2 | B11 |  |
| RN-WEST-16970 | us-east-3 | 3 | B11 |  |
| RN-WEST-16970 | us-east-3 | 4 | B11 |  |
| RN-WEST-16970 | us-east-3 | 5 | B11 |  |
| RN-WEST-16999 | us-central-4 | 1 | B11 |  |
| RN-WEST-16999 | us-central-4 | 2 | B11 |  |
| RN-WEST-16999 | us-central-4 | 3 | B11 |  |
| RN-WEST-16999 | us-central-4 | 4 | B11 |  |
| RN-WEST-16999 | us-central-4 | 5 | B11 |  |
| RN-WEST-17022 | us-east-3 | 1 | B11 |  |
| RN-WEST-17022 | us-central-4 | 2 | B11 |  |
| RN-WEST-17022 | us-east-3 | 3 | B11 |  |
| RN-WEST-17022 | us-east-3 | 4 | B11 |  |
| RN-WEST-17022 | us-east-3 | 5 | B11 |  |
| RN-WEST-17054 | us-central-4 | 1 | B11 |  |
| RN-WEST-17054 | us-central-4 | 2 | B11 |  |
| RN-WEST-17054 | us-central-4 | 3 | B11 |  |
| RN-WEST-17054 | us-central-4 | 4 | B11 |  |
| RN-WEST-17054 | us-central-4 | 5 | B11 |  |
| RN-WEST-17078 | us-east-3 | 1 | B11 |  |
| RN-WEST-17078 | us-east-3 | 2 | B11 |  |
| RN-WEST-17078 | us-east-3 | 3 | B11 |  |
| RN-WEST-17078 | us-east-3 | 4 | B11 |  |
| RN-WEST-17078 | us-central-4 | 5 | B11 |  |
| RN-WEST-17107 | us-central-4 | 1 | B11 |  |
| RN-WEST-17107 | us-central-4 | 2 | B11 |  |
| RN-WEST-17107 | us-central-4 | 3 | B11 |  |
| RN-WEST-17107 | us-central-4 | 4 | B11 |  |
| RN-WEST-17107 | us-central-4 | 5 | B11 |  |
| RN-WEST-17135 | us-east-3 | 1 | B11 |  |
| RN-WEST-17135 | us-east-3 | 2 | B11 |  |
| RN-WEST-17135 | us-east-3 | 3 | B11 |  |
| RN-WEST-17135 | us-east-3 | 4 | B11 |  |
| RN-WEST-17135 | us-east-3 | 5 | B11 |  |
| RN-WEST-17163 | us-central-4 | 1 | B11 |  |
| RN-WEST-17163 | us-central-4 | 2 | B11 |  |
| RN-WEST-17163 | us-central-4 | 3 | B11 |  |
| RN-WEST-17163 | us-central-4 | 4 | B11 |  |
| RN-WEST-17163 | us-central-4 | 5 | B11 |  |
| RN-WEST-17193 | us-east-3 | 1 | B11 |  |
| RN-WEST-17193 | us-east-3 | 2 | B11 |  |
| RN-WEST-17193 | us-east-3 | 3 | B11 |  |
| RN-WEST-17193 | us-east-3 | 4 | B11 |  |
| RN-WEST-17193 | us-east-3 | 5 | B11 |  |
| RN-WEST-17221 | us-central-4 | 1 | B11 |  |
| RN-WEST-17221 | us-central-4 | 2 | B11 |  |
| RN-WEST-17221 | us-central-4 | 3 | B11 |  |
| RN-WEST-17221 | us-central-4 | 4 | B11 |  |
| RN-WEST-17221 | us-central-4 | 5 | B11 |  |
| RN-WEST-17247 | us-east-3 | 1 | B11 |  |
| RN-WEST-17247 | us-east-3 | 2 | B11 |  |
| RN-WEST-17247 | us-central-4 | 3 | B11 |  |
| RN-WEST-17247 | us-east-3 | 4 | B11 |  |
| RN-WEST-17247 | us-east-3 | 5 | B11 |  |
| RN-WEST-17277 | us-central-4 | 1 | B11 |  |
| RN-WEST-17277 | us-central-4 | 2 | B11 |  |
| RN-WEST-17277 | us-central-4 | 3 | B11 |  |
| RN-WEST-17277 | us-central-4 | 4 | B11 |  |
| RN-WEST-17277 | us-central-4 | 5 | B11 |  |
| RN-WEST-17303 | us-east-3 | 1 | B11 |  |
| RN-WEST-17303 | us-east-3 | 2 | B11 |  |
| RN-WEST-17303 | us-east-3 | 3 | B11 |  |
| RN-WEST-17303 | us-east-3 | 4 | B11 |  |
| RN-WEST-17303 | us-east-3 | 5 | B11 |  |
| RN-WEST-17333 | us-central-4 | 1 | B11 |  |
| RN-WEST-17333 | us-central-4 | 2 | B11 |  |
| RN-WEST-17333 | us-central-4 | 3 | B11 |  |
| RN-WEST-17333 | us-central-4 | 4 | B11 |  |
| RN-WEST-17333 | us-central-4 | 5 | B11 |  |
| RN-WEST-17357 | us-east-3 | 1 | B11 |  |
| RN-WEST-17357 | us-east-3 | 2 | B11 |  |
| RN-WEST-17357 | us-east-3 | 3 | B11 |  |
| RN-WEST-17357 | us-east-3 | 4 | B11 |  |
| RN-WEST-17357 | us-east-3 | 5 | B11 |  |
| RN-WEST-17387 | us-central-4 | 1 | B11 |  |
| RN-WEST-17387 | us-central-4 | 2 | B11 |  |
| RN-WEST-17387 | us-central-4 | 3 | B11 |  |
| RN-WEST-17387 | us-central-4 | 4 | B11 |  |
| RN-WEST-17387 | us-central-4 | 5 | B11 |  |
| RN-WEST-17413 | us-east-3 | 1 | B11 |  |
| RN-WEST-17413 | us-east-3 | 2 | B11 |  |
| RN-WEST-17413 | us-central-4 | 3 | B11 |  |
| RN-WEST-17413 | us-east-3 | 4 | B11 |  |
| RN-WEST-17413 | us-east-3 | 5 | B11 |  |
| RN-WEST-17447 | us-central-4 | 1 | B11 |  |
| RN-WEST-17447 | us-east-3 | 2 | B11 |  |
| RN-WEST-17447 | us-central-4 | 3 | B11 |  |
| RN-WEST-17447 | us-central-4 | 4 | B11 |  |
| RN-WEST-17447 | us-central-4 | 5 | B11 |  |
| RN-WEST-17473 | us-east-3 | 1 | B11 |  |
| RN-WEST-17473 | us-east-3 | 2 | B11 |  |
| RN-WEST-17473 | us-east-3 | 3 | B11 |  |
| RN-WEST-17473 | us-east-3 | 4 | B11 |  |
| RN-WEST-17473 | us-east-3 | 5 | B11 |  |
| RN-WEST-17497 | us-central-4 | 1 | B11 |  |
| RN-WEST-17497 | us-east-3 | 2 | B11 |  |
| RN-WEST-17497 | us-central-4 | 3 | B11 |  |
| RN-WEST-17497 | us-central-4 | 4 | B11 |  |
| RN-WEST-17497 | us-central-4 | 5 | B11 |  |
| RN-WEST-17531 | us-east-3 | 1 | B11 |  |
| RN-WEST-17531 | us-east-3 | 2 | B11 |  |
| RN-WEST-17531 | us-east-3 | 3 | B11 |  |
| RN-WEST-17531 | us-east-3 | 4 | B11 |  |
| RN-WEST-17531 | us-east-3 | 5 | B11 |  |
| RN-WEST-17557 | us-central-4 | 1 | B11 |  |
| RN-WEST-17557 | us-central-4 | 2 | B11 |  |
| RN-WEST-17557 | us-central-4 | 3 | B11 |  |
| RN-WEST-17557 | us-central-4 | 4 | B11 |  |
| RN-WEST-17557 | us-central-4 | 5 | B11 |  |
| RN-WEST-17587 | us-east-3 | 1 | B11 |  |
| RN-WEST-17587 | us-east-3 | 2 | B11 |  |
| RN-WEST-17587 | us-east-3 | 3 | B11 |  |
| RN-WEST-17587 | us-east-3 | 4 | B11 |  |
| RN-WEST-17587 | us-central-4 | 5 | B11 |  |
| RN-WEST-17612 | us-central-4 | 1 | B11 |  |
| RN-WEST-17612 | us-central-4 | 2 | B11 |  |
| RN-WEST-17612 | us-central-4 | 3 | B11 |  |
| RN-WEST-17612 | us-central-4 | 4 | B11 |  |
| RN-WEST-17612 | us-central-4 | 5 | B11 |  |
| RN-WEST-17640 | us-east-3 | 1 | B11 |  |
| RN-WEST-17640 | us-east-3 | 2 | B11 |  |
| RN-WEST-17640 | us-east-3 | 3 | B11 |  |
| RN-WEST-17640 | us-east-3 | 4 | B11 |  |
| RN-WEST-17640 | us-east-3 | 5 | B11 |  |
| RN-WEST-17666 | us-central-4 | 1 | B11 |  |
| RN-WEST-17666 | us-central-4 | 2 | B11 |  |
| RN-WEST-17666 | us-central-4 | 3 | B11 |  |
| RN-WEST-17666 | us-central-4 | 4 | B11 |  |
| RN-WEST-17666 | us-central-4 | 5 | B11 |  |
| RN-WEST-17693 | us-east-3 | 1 | B11 |  |
| RN-WEST-17693 | us-east-3 | 2 | B11 |  |
| RN-WEST-17693 | us-central-4 | 3 | B11 |  |
| RN-WEST-17693 | us-east-3 | 4 | B11 |  |
| RN-WEST-17693 | us-east-3 | 5 | B11 |  |
| RN-WEST-17723 | us-central-4 | 1 | B11 |  |
| RN-WEST-17723 | us-central-4 | 2 | B11 |  |
| RN-WEST-17723 | us-central-4 | 3 | B11 |  |
| RN-WEST-17723 | us-central-4 | 4 | B11 |  |
| RN-WEST-17723 | us-central-4 | 5 | B11 |  |
| RN-WEST-17753 | us-east-3 | 1 | B11 |  |
| RN-WEST-17753 | us-east-3 | 2 | B11 |  |
| RN-WEST-17753 | us-central-4 | 3 | B11 |  |
| RN-WEST-17753 | us-east-3 | 4 | B11 |  |
| RN-WEST-17753 | us-east-3 | 5 | B11 |  |
| RN-WEST-17777 | us-central-4 | 1 | B11 |  |
| RN-WEST-17777 | us-central-4 | 2 | B11 |  |
| RN-WEST-17777 | us-central-4 | 3 | B11 |  |
| RN-WEST-17777 | us-central-4 | 4 | B11 |  |
| RN-WEST-17777 | us-central-4 | 5 | B11 |  |
| RN-WEST-17809 | us-east-3 | 1 | B11 |  |
| RN-WEST-17809 | us-east-3 | 2 | B11 |  |
| RN-WEST-17809 | us-east-3 | 3 | B11 |  |
| RN-WEST-17809 | us-east-3 | 4 | B11 |  |
| RN-WEST-17809 | us-east-3 | 5 | B11 |  |
| RN-WEST-17836 | us-central-4 | 1 | B11 |  |
| RN-WEST-17836 | us-central-4 | 2 | B11 |  |
| RN-WEST-17836 | us-central-4 | 3 | B11 |  |
| RN-WEST-17836 | us-central-4 | 4 | B11 |  |
| RN-WEST-17836 | us-central-4 | 5 | B11 |  |
| RN-WEST-17861 | us-east-3 | 1 | B11 |  |
| RN-WEST-17861 | us-east-3 | 2 | B11 |  |
| RN-WEST-17861 | us-east-3 | 3 | B11 |  |
| RN-WEST-17861 | us-east-3 | 4 | B11 |  |
| RN-WEST-17861 | us-east-3 | 5 | B11 |  |
| RN-WEST-17891 | us-central-4 | 1 | B11 |  |
| RN-WEST-17891 | us-east-3 | 2 | B11 |  |
| RN-WEST-17891 | us-central-4 | 3 | B11 |  |
| RN-WEST-17891 | us-central-4 | 4 | B11 |  |
| RN-WEST-17891 | us-central-4 | 5 | B11 |  |
| RN-WEST-17922 | us-east-3 | 1 | B11 |  |
| RN-WEST-17922 | us-east-3 | 2 | B11 |  |
| RN-WEST-17922 | us-central-4 | 3 | B11 |  |
| RN-WEST-17922 | us-central-4 | 4 | B11 |  |
| RN-WEST-17922 | us-east-3 | 5 | B11 |  |
| RN-WEST-17950 | us-central-4 | 1 | B11 |  |
| RN-WEST-17950 | us-central-4 | 2 | B11 |  |
| RN-WEST-17950 | us-central-4 | 3 | B11 |  |
| RN-WEST-17950 | us-central-4 | 4 | B11 |  |
| RN-WEST-17950 | us-central-4 | 5 | B11 |  |
| RN-WEST-17979 | us-east-3 | 1 | B11 |  |
| RN-WEST-17979 | us-east-3 | 2 | B11 |  |
| RN-WEST-17979 | us-east-3 | 3 | B11 |  |
| RN-WEST-17979 | us-east-3 | 4 | B11 |  |
| RN-WEST-17979 | us-east-3 | 5 | B11 |  |
| RN-WEST-18004 | us-central-4 | 1 | B11 |  |
| RN-WEST-18004 | us-central-4 | 2 | B11 |  |
| RN-WEST-18004 | us-central-4 | 3 | B11 |  |
| RN-WEST-18004 | us-central-4 | 4 | B11 |  |
| RN-WEST-18004 | us-central-4 | 5 | B11 |  |
| RN-WEST-18030 | us-east-3 | 1 | B11 |  |
| RN-WEST-18030 | us-east-3 | 2 | B11 |  |
| RN-WEST-18030 | us-east-3 | 3 | B11 |  |
| RN-WEST-18030 | us-east-3 | 4 | B11 |  |
| RN-WEST-18030 | us-east-3 | 5 | B11 |  |
| RN-WEST-18061 | us-central-4 | 1 | B11 |  |
| RN-WEST-18061 | us-central-4 | 2 | B11 |  |
| RN-WEST-18061 | us-central-4 | 3 | B11 |  |
| RN-WEST-18061 | us-central-4 | 4 | B11 |  |
| RN-WEST-18061 | us-central-4 | 5 | B11 |  |
| RN-WEST-18085 | us-east-3 | 1 | B11 |  |
| RN-WEST-18085 | us-east-3 | 2 | B11 |  |
| RN-WEST-18085 | us-central-4 | 3 | B11 |  |
| RN-WEST-18085 | us-east-3 | 4 | B11 |  |
| RN-WEST-18085 | us-east-3 | 5 | B11 |  |
| RN-WEST-18117 | us-central-4 | 1 | B11 |  |
| RN-WEST-18117 | us-central-4 | 2 | B11 |  |
| RN-WEST-18117 | us-central-4 | 3 | B11 |  |
| RN-WEST-18117 | us-central-4 | 4 | B11 |  |
| RN-WEST-18117 | us-central-4 | 5 | B11 |  |
| RN-WEST-18147 | us-east-3 | 1 | B11 |  |
| RN-WEST-18147 | us-east-3 | 2 | B11 |  |
| RN-WEST-18147 | us-east-3 | 3 | B11 |  |
| RN-WEST-18147 | us-east-3 | 4 | B11 |  |
| RN-WEST-18147 | us-east-3 | 5 | B11 |  |
| RN-WEST-18173 | us-central-4 | 1 | B11 |  |
| RN-WEST-18173 | us-central-4 | 2 | B11 |  |
| RN-WEST-18173 | us-central-4 | 3 | B11 |  |
| RN-WEST-18173 | us-central-4 | 4 | B11 |  |
| RN-WEST-18173 | us-central-4 | 5 | B11 |  |
| RN-WEST-18203 | us-east-3 | 1 | B11 |  |
| RN-WEST-18203 | us-east-3 | 2 | B11 |  |
| RN-WEST-18203 | us-east-3 | 3 | B11 |  |
| RN-WEST-18203 | us-central-4 | 4 | B11 |  |
| RN-WEST-18203 | us-central-4 | 5 | B11 |  |
| RN-WEST-18227 | us-central-4 | 1 | B11 |  |
| RN-WEST-18227 | us-central-4 | 2 | B11 |  |
| RN-WEST-18227 | us-central-4 | 3 | B11 |  |
| RN-WEST-18227 | us-central-4 | 4 | B11 |  |
| RN-WEST-18227 | us-central-4 | 5 | B11 |  |
| RN-WEST-18255 | us-east-3 | 1 | B11 |  |
| RN-WEST-18255 | us-east-3 | 2 | B11 |  |
| RN-WEST-18255 | us-east-3 | 3 | B11 |  |
| RN-WEST-18255 | us-east-3 | 4 | B11 |  |
| RN-WEST-18255 | us-east-3 | 5 | B11 |  |
| RN-WEST-18281 | us-central-4 | 1 | B11 |  |
| RN-WEST-18281 | us-central-4 | 2 | B11 |  |
| RN-WEST-18281 | us-central-4 | 3 | B11 |  |
| RN-WEST-18281 | us-central-4 | 4 | B11 |  |
| RN-WEST-18281 | us-central-4 | 5 | B11 |  |
| RN-WEST-18314 | us-east-3 | 1 | B11 |  |
| RN-WEST-18314 | us-east-3 | 2 | B11 |  |
| RN-WEST-18314 | us-east-3 | 3 | B11 |  |
| RN-WEST-18314 | us-central-4 | 4 | B11 |  |
| RN-WEST-18314 | us-east-3 | 5 | B11 |  |
| RN-WEST-18341 | us-central-4 | 1 | B11 |  |
| RN-WEST-18341 | us-central-4 | 2 | B11 |  |
| RN-WEST-18341 | us-central-4 | 3 | B11 |  |
| RN-WEST-18341 | us-central-4 | 4 | B11 |  |
| RN-WEST-18341 | us-central-4 | 5 | B11 |  |
| RN-WEST-18370 | us-east-3 | 1 | B11 |  |
| RN-WEST-18370 | us-east-3 | 2 | B11 |  |
| RN-WEST-18370 | us-east-3 | 3 | B11 |  |
| RN-WEST-18370 | us-east-3 | 4 | B11 |  |
| RN-WEST-18370 | us-east-3 | 5 | B11 |  |
| RN-WEST-18393 | us-central-4 | 1 | B11 |  |
| RN-WEST-18393 | us-central-4 | 2 | B11 |  |
| RN-WEST-18393 | us-central-4 | 3 | B11 |  |
| RN-WEST-18393 | us-central-4 | 4 | B11 |  |
| RN-WEST-18393 | us-central-4 | 5 | B11 |  |
| RN-WEST-18424 | us-east-3 | 1 | B11 |  |
| RN-WEST-18424 | us-east-3 | 2 | B11 |  |
| RN-WEST-18424 | us-east-3 | 3 | B11 |  |
| RN-WEST-18424 | us-east-3 | 4 | B11 |  |
| RN-WEST-18424 | us-east-3 | 5 | B11 |  |
| RN-WEST-18451 | us-central-4 | 1 | B11 |  |
| RN-WEST-18451 | us-central-4 | 2 | B11 |  |
| RN-WEST-18451 | us-central-4 | 3 | B11 |  |
| RN-WEST-18451 | us-central-4 | 4 | B11 |  |
| RN-WEST-18451 | us-central-4 | 5 | B11 |  |
| RN-WEST-18478 | us-east-3 | 1 | B11 |  |
| RN-WEST-18478 | us-east-3 | 2 | B11 |  |
| RN-WEST-18478 | us-east-3 | 3 | B11 |  |
| RN-WEST-18478 | us-east-3 | 4 | B11 |  |
| RN-WEST-18478 | us-east-3 | 5 | B11 |  |
| RN-WEST-18507 | us-central-4 | 1 | B11 |  |
| RN-WEST-18507 | us-central-4 | 2 | B11 |  |
| RN-WEST-18507 | us-central-4 | 3 | B11 |  |
| RN-WEST-18507 | us-central-4 | 4 | B11 |  |
| RN-WEST-18507 | us-central-4 | 5 | B11 |  |
| RN-WEST-18535 | us-east-3 | 1 | B11 |  |
| RN-WEST-18535 | us-central-4 | 2 | B11 |  |
| RN-WEST-18535 | us-east-3 | 3 | B11 |  |
| RN-WEST-18535 | us-east-3 | 4 | B11 |  |
| RN-WEST-18535 | us-east-3 | 5 | B11 |  |
| RN-WEST-18561 | us-central-4 | 1 | B11 |  |
| RN-WEST-18561 | us-east-3 | 2 | B11 |  |
| RN-WEST-18561 | us-central-4 | 3 | B11 |  |
| RN-WEST-18561 | us-central-4 | 4 | B11 |  |
| RN-WEST-18561 | us-central-4 | 5 | B11 |  |
| RN-WEST-18594 | us-east-3 | 1 | B11 |  |
| RN-WEST-18594 | us-east-3 | 2 | B11 |  |
| RN-WEST-18594 | us-east-3 | 3 | B11 |  |
| RN-WEST-18594 | us-east-3 | 4 | B11 |  |
| RN-WEST-18594 | us-central-4 | 5 | B11 |  |
| RN-WEST-18617 | us-central-4 | 1 | B11 |  |
| RN-WEST-18617 | us-central-4 | 2 | B11 |  |
| RN-WEST-18617 | us-central-4 | 3 | B11 |  |
| RN-WEST-18617 | us-central-4 | 4 | B11 |  |
| RN-WEST-18617 | us-central-4 | 5 | B11 |  |
| RN-WEST-18646 | us-east-3 | 1 | B11 |  |
| RN-WEST-18646 | us-east-3 | 2 | B11 |  |
| RN-WEST-18646 | us-east-3 | 3 | B11 |  |
| RN-WEST-18646 | us-east-3 | 4 | B11 |  |
| RN-WEST-18646 | us-east-3 | 5 | B11 |  |
| RN-WEST-18674 | us-central-4 | 1 | B11 |  |
| RN-WEST-18674 | us-central-4 | 2 | B11 |  |
| RN-WEST-18674 | us-east-3 | 3 | B11 |  |
| RN-WEST-18674 | us-central-4 | 4 | B11 |  |
| RN-WEST-18674 | us-central-4 | 5 | B11 |  |
| RN-WEST-18707 | us-east-3 | 1 | B11 |  |
| RN-WEST-18707 | us-east-3 | 2 | B11 |  |
| RN-WEST-18707 | us-central-4 | 3 | B11 |  |
| RN-WEST-18707 | us-east-3 | 4 | B11 |  |
| RN-WEST-18707 | us-east-3 | 5 | B11 |  |
| RN-WEST-18735 | us-central-4 | 1 | B11 |  |
| RN-WEST-18735 | us-central-4 | 2 | B11 |  |
| RN-WEST-18735 | us-central-4 | 3 | B11 |  |
| RN-WEST-18735 | us-central-4 | 4 | B11 |  |
| RN-WEST-18735 | us-central-4 | 5 | B11 |  |
| RN-WEST-18757 | us-east-3 | 1 | B11 |  |
| RN-WEST-18757 | us-east-3 | 2 | B11 |  |
| RN-WEST-18757 | us-east-3 | 3 | B11 |  |
| RN-WEST-18757 | us-east-3 | 4 | B11 |  |
| RN-WEST-18757 | us-east-3 | 5 | B11 |  |
| RN-WEST-18785 | us-central-4 | 1 | B11 |  |
| RN-WEST-18785 | us-central-4 | 2 | B11 |  |
| RN-WEST-18785 | us-central-4 | 3 | B11 |  |
| RN-WEST-18785 | us-central-4 | 4 | B11 |  |
| RN-WEST-18785 | us-central-4 | 5 | B11 |  |
| RN-WEST-18813 | us-east-3 | 1 | B11 |  |
| RN-WEST-18813 | us-east-3 | 2 | B11 |  |
| RN-WEST-18813 | us-east-3 | 3 | B11 |  |
| RN-WEST-18813 | us-east-3 | 4 | B11 |  |
| RN-WEST-18813 | us-east-3 | 5 | B11 |  |
| RN-WEST-18842 | us-central-4 | 1 | B11 |  |
| RN-WEST-18842 | us-central-4 | 2 | B11 |  |
| RN-WEST-18842 | us-central-4 | 3 | B11 |  |
| RN-WEST-18842 | us-central-4 | 4 | B11 |  |
| RN-WEST-18842 | us-central-4 | 5 | B11 |  |
| RN-WEST-18873 | us-east-3 | 1 | B11 |  |
| RN-WEST-18873 | us-east-3 | 2 | B11 |  |
| RN-WEST-18873 | us-east-3 | 3 | B11 |  |
| RN-WEST-18873 | us-east-3 | 4 | B11 |  |
| RN-WEST-18873 | us-central-4 | 5 | B11 |  |
| RN-WEST-18901 | us-central-4 | 1 | B11 |  |
| RN-WEST-18901 | us-central-4 | 2 | B11 |  |
| RN-WEST-18901 | us-central-4 | 3 | B11 |  |
| RN-WEST-18901 | us-central-4 | 4 | B11 |  |
| RN-WEST-18901 | us-central-4 | 5 | B11 |  |
| RN-WEST-18930 | us-east-3 | 1 | B11 |  |
| RN-WEST-18930 | us-east-3 | 2 | B11 |  |
| RN-WEST-18930 | us-east-3 | 3 | B11 |  |
| RN-WEST-18930 | us-east-3 | 4 | B11 |  |
| RN-WEST-18930 | us-east-3 | 5 | B11 |  |
| RN-WEST-18958 | us-central-4 | 1 | B11 |  |
| RN-WEST-18958 | us-central-4 | 2 | B11 |  |
| RN-WEST-18958 | us-central-4 | 3 | B11 |  |
| RN-WEST-18958 | us-central-4 | 4 | B11 |  |
| RN-WEST-18958 | us-central-4 | 5 | B11 |  |
| RN-WEST-18986 | us-east-3 | 1 | B11 |  |
| RN-WEST-18986 | us-east-3 | 2 | B11 |  |
| RN-WEST-18986 | us-east-3 | 3 | B11 |  |
| RN-WEST-18986 | us-east-3 | 4 | B11 |  |
| RN-WEST-18986 | us-east-3 | 5 | B11 |  |
| RN-WEST-19010 | us-central-4 | 1 | B11 |  |
| RN-WEST-19010 | us-central-4 | 2 | B11 |  |
| RN-WEST-19010 | us-central-4 | 3 | B11 |  |
| RN-WEST-19010 | us-central-4 | 4 | B11 |  |
| RN-WEST-19010 | us-central-4 | 5 | B11 |  |
| RN-WEST-19042 | us-east-3 | 1 | B11 |  |
| RN-WEST-19042 | us-east-3 | 2 | B11 |  |
| RN-WEST-19042 | us-east-3 | 3 | B11 |  |
| RN-WEST-19042 | us-east-3 | 4 | B11 |  |
| RN-WEST-19042 | us-east-3 | 5 | B11 |  |
| RN-WEST-19066 | us-central-4 | 1 | B11 |  |
| RN-WEST-19066 | us-central-4 | 2 | B11 |  |
| RN-WEST-19066 | us-central-4 | 3 | B11 |  |
| RN-WEST-19066 | us-central-4 | 4 | B11 |  |
| RN-WEST-19066 | us-central-4 | 5 | B11 |  |
| RN-WEST-19098 | us-east-3 | 1 | B11 |  |
| RN-WEST-19098 | us-east-3 | 2 | B11 |  |
| RN-WEST-19098 | us-east-3 | 3 | B11 |  |
| RN-WEST-19098 | us-east-3 | 4 | B11 |  |
| RN-WEST-19098 | us-east-3 | 5 | B11 |  |
| RN-WEST-19124 | us-central-4 | 1 | B11 |  |
| RN-WEST-19124 | us-central-4 | 2 | B11 |  |
| RN-WEST-19124 | us-central-4 | 3 | B11 |  |
| RN-WEST-19124 | us-central-4 | 4 | B11 |  |
| RN-WEST-19124 | us-central-4 | 5 | B11 |  |
| RN-WEST-19150 | us-east-3 | 1 | B11 |  |
| RN-WEST-19150 | us-east-3 | 2 | B11 |  |
| RN-WEST-19150 | us-east-3 | 3 | B11 |  |
| RN-WEST-19150 | us-east-3 | 4 | B11 |  |
| RN-WEST-19150 | us-east-3 | 5 | B11 |  |
| RN-WEST-19181 | us-central-4 | 1 | B11 |  |
| RN-WEST-19181 | us-central-4 | 2 | B11 |  |
| RN-WEST-19181 | us-central-4 | 3 | B11 |  |
| RN-WEST-19181 | us-central-4 | 4 | B11 |  |
| RN-WEST-19181 | us-central-4 | 5 | B11 |  |
| RN-WEST-19211 | us-east-3 | 1 | B11 |  |
| RN-WEST-19211 | us-east-3 | 2 | B11 |  |
| RN-WEST-19211 | us-east-3 | 3 | B11 |  |
| RN-WEST-19211 | us-central-4 | 4 | B11 |  |
| RN-WEST-19211 | us-east-3 | 5 | B11 |  |
| RN-WEST-19233 | us-central-4 | 1 | B11 |  |
| RN-WEST-19233 | us-central-4 | 2 | B11 |  |
| RN-WEST-19233 | us-central-4 | 3 | B11 |  |
| RN-WEST-19233 | us-central-4 | 4 | B11 |  |
| RN-WEST-19233 | us-central-4 | 5 | B11 |  |
| RN-WEST-19261 | us-east-3 | 1 | B11 |  |
| RN-WEST-19261 | us-central-4 | 2 | B11 |  |
| RN-WEST-19261 | us-east-3 | 3 | B11 |  |
| RN-WEST-19261 | us-east-3 | 4 | B11 |  |
| RN-WEST-19261 | us-east-3 | 5 | B11 |  |
| RN-WEST-19295 | us-central-4 | 1 | B11 |  |
| RN-WEST-19295 | us-central-4 | 2 | B11 |  |
| RN-WEST-19295 | us-central-4 | 3 | B11 |  |
| RN-WEST-19295 | us-central-4 | 4 | B11 |  |
| RN-WEST-19295 | us-central-4 | 5 | B11 |  |
| RN-WEST-19318 | us-east-3 | 1 | B11 |  |
| RN-WEST-19318 | us-east-3 | 2 | B11 |  |
| RN-WEST-19318 | us-east-3 | 3 | B11 |  |
| RN-WEST-19318 | us-east-3 | 4 | B11 |  |
| RN-WEST-19318 | us-east-3 | 5 | B11 |  |
| RN-WEST-19347 | us-central-4 | 1 | B11 |  |
| RN-WEST-19347 | us-central-4 | 2 | B11 |  |
| RN-WEST-19347 | us-central-4 | 3 | B11 |  |
| RN-WEST-19347 | us-central-4 | 4 | B11 |  |
| RN-WEST-19347 | us-east-3 | 5 | B11 |  |
| RN-WEST-19379 | us-east-3 | 1 | B11 |  |
| RN-WEST-19379 | us-east-3 | 2 | B11 |  |
| RN-WEST-19379 | us-east-3 | 3 | B11 |  |
| RN-WEST-19379 | us-east-3 | 4 | B11 |  |
| RN-WEST-19379 | us-east-3 | 5 | B11 |  |
| RN-WEST-19404 | us-central-4 | 1 | B11 |  |
| RN-WEST-19404 | us-central-4 | 2 | B11 |  |
| RN-WEST-19404 | us-central-4 | 3 | B11 |  |
| RN-WEST-19404 | us-central-4 | 4 | B11 |  |
| RN-WEST-19404 | us-central-4 | 5 | B11 |  |
| RN-WEST-19433 | us-east-3 | 1 | B11 |  |
| RN-WEST-19433 | us-east-3 | 2 | B11 |  |
| RN-WEST-19433 | us-east-3 | 3 | B11 |  |
| RN-WEST-19433 | us-east-3 | 4 | B11 |  |
| RN-WEST-19433 | us-east-3 | 5 | B11 |  |
| RN-WEST-19461 | us-central-4 | 1 | B11 |  |
| RN-WEST-19461 | us-central-4 | 2 | B11 |  |
| RN-WEST-19461 | us-central-4 | 3 | B11 |  |
| RN-WEST-19461 | us-central-4 | 4 | B11 |  |
| RN-WEST-19461 | us-central-4 | 5 | B11 |  |
| RN-WEST-19489 | us-east-3 | 1 | B11 |  |
| RN-WEST-19489 | us-east-3 | 2 | B11 |  |
| RN-WEST-19489 | us-east-3 | 3 | B11 |  |
| RN-WEST-19489 | us-east-3 | 4 | B11 |  |
| RN-WEST-19489 | us-east-3 | 5 | B11 |  |
| RN-WEST-19514 | us-central-4 | 1 | B11 |  |
| RN-WEST-19514 | us-central-4 | 2 | B11 |  |
| RN-WEST-19514 | us-central-4 | 3 | B11 |  |
| RN-WEST-19514 | us-central-4 | 4 | B11 |  |
| RN-WEST-19514 | us-central-4 | 5 | B11 |  |
|   rn-west-19545  | us-east-3 | 1 | B12 |  |
|   rn-west-19545  | us-central-4 | 2 | B12 |  |
|   rn-west-19545  | us-east-3 | 3 | B12 |  |
|   rn-west-19545  | us-east-3 | 4 | B12 |  |
|   rn-west-19545  | us-east-3 | 5 | B12 |  |
|   rn-west-19574  | us-central-4 | 1 | B12 |  |
|   rn-west-19574  | us-central-4 | 2 | B12 |  |
|   rn-west-19574  | us-central-4 | 3 | B12 |  |
|   rn-west-19574  | us-central-4 | 4 | B12 |  |
|   rn-west-19574  | us-central-4 | 5 | B12 |  |
|   rn-west-19597  | us-east-3 | 1 | B12 |  |
|   rn-west-19597  | us-east-3 | 2 | B12 |  |
|   rn-west-19597  | us-east-3 | 3 | B12 |  |
|   rn-west-19597  | us-east-3 | 4 | B12 |  |
|   rn-west-19597  | us-east-3 | 5 | B12 |  |
|   rn-west-19627  | us-central-4 | 1 | B12 |  |
|   rn-west-19627  | us-central-4 | 2 | B12 |  |
|   rn-west-19627  | us-central-4 | 3 | B12 |  |
|   rn-west-19627  | us-central-4 | 4 | B12 |  |
|   rn-west-19627  | us-central-4 | 5 | B12 |  |
|   rn-west-19655  | us-east-3 | 1 | B12 |  |
|   rn-west-19655  | us-east-3 | 2 | B12 |  |
|   rn-west-19655  | us-east-3 | 3 | B12 |  |
|   rn-west-19655  | us-east-3 | 4 | B12 |  |
|   rn-west-19655  | us-east-3 | 5 | B12 |  |
|   rn-west-19681  | us-central-4 | 1 | B12 |  |
|   rn-west-19681  | us-central-4 | 2 | B12 |  |
|   rn-west-19681  | us-central-4 | 3 | B12 |  |
|   rn-west-19681  | us-central-4 | 4 | B12 |  |
|   rn-west-19681  | us-central-4 | 5 | B12 |  |
|   rn-west-19712  | us-east-3 | 1 | B12 |  |
|   rn-west-19712  | us-east-3 | 2 | B12 |  |
|   rn-west-19712  | us-east-3 | 3 | B12 |  |
|   rn-west-19712  | us-east-3 | 4 | B12 |  |
|   rn-west-19712  | us-east-3 | 5 | B12 |  |
|   rn-west-19739  | us-central-4 | 1 | B12 |  |
|   rn-west-19739  | us-central-4 | 2 | B12 |  |
|   rn-west-19739  | us-central-4 | 3 | B12 |  |
|   rn-west-19739  | us-central-4 | 4 | B12 |  |
|   rn-west-19739  | us-east-3 | 5 | B12 |  |
|   rn-west-19771  | us-east-3 | 1 | B12 |  |
|   rn-west-19771  | us-east-3 | 2 | B12 |  |
|   rn-west-19771  | us-east-3 | 3 | B12 |  |
|   rn-west-19771  | us-east-3 | 4 | B12 |  |
|   rn-west-19771  | us-east-3 | 5 | B12 |  |
|   rn-west-19794  | us-central-4 | 1 | B12 |  |
|   rn-west-19794  | us-central-4 | 2 | B12 |  |
|   rn-west-19794  | us-central-4 | 3 | B12 |  |
|   rn-west-19794  | us-central-4 | 4 | B12 |  |
|   rn-west-19794  | us-central-4 | 5 | B12 |  |
|   rn-west-19824  | us-east-3 | 1 | B12 |  |
|   rn-west-19824  | us-east-3 | 2 | B12 |  |
|   rn-west-19824  | us-east-3 | 3 | B12 |  |
|   rn-west-19824  | us-east-3 | 4 | B12 |  |
|   rn-west-19824  | us-central-4 | 5 | B12 |  |
|   rn-west-19849  | us-central-4 | 1 | B12 |  |
|   rn-west-19849  | us-central-4 | 2 | B12 |  |
|   rn-west-19849  | us-central-4 | 3 | B12 |  |
|   rn-west-19849  | us-central-4 | 4 | B12 |  |
|   rn-west-19849  | us-central-4 | 5 | B12 |  |
|   rn-west-19881  | us-east-3 | 1 | B12 |  |
|   rn-west-19881  | us-east-3 | 2 | B12 |  |
|   rn-west-19881  | us-east-3 | 3 | B12 |  |
|   rn-west-19881  | us-east-3 | 4 | B12 |  |
|   rn-west-19881  | us-east-3 | 5 | B12 |  |
|   rn-west-19910  | us-central-4 | 1 | B12 |  |
|   rn-west-19910  | us-central-4 | 2 | B12 |  |
|   rn-west-19910  | us-central-4 | 3 | B12 |  |
|   rn-west-19910  | us-central-4 | 4 | B12 |  |
|   rn-west-19910  | us-central-4 | 5 | B12 |  |
|   rn-west-19933  | us-east-3 | 1 | B12 |  |
|   rn-west-19933  | us-east-3 | 2 | B12 |  |
|   rn-west-19933  | us-east-3 | 3 | B12 |  |
|   rn-west-19933  | us-east-3 | 4 | B12 |  |
|   rn-west-19933  | us-east-3 | 5 | B12 |  |
|   rn-west-19965  | us-central-4 | 1 | B12 |  |
|   rn-west-19965  | us-central-4 | 2 | B12 |  |
|   rn-west-19965  | us-central-4 | 3 | B12 |  |
|   rn-west-19965  | us-central-4 | 4 | B12 |  |
|   rn-west-19965  | us-central-4 | 5 | B12 |  |
|   rn-west-19994  | us-east-3 | 1 | B12 |  |
|   rn-west-19994  | us-east-3 | 2 | B12 |  |
|   rn-west-19994  | us-east-3 | 3 | B12 |  |
|   rn-west-19994  | us-east-3 | 4 | B12 |  |
|   rn-west-19994  | us-east-3 | 5 | B12 |  |
|   rn-west-20018  | us-central-4 | 1 | B12 |  |
|   rn-west-20018  | us-central-4 | 2 | B12 |  |
|   rn-west-20018  | us-central-4 | 3 | B12 |  |
|   rn-west-20018  | us-central-4 | 4 | B12 |  |
|   rn-west-20018  | us-central-4 | 5 | B12 |  |
|   rn-west-20050  | us-east-3 | 1 | B12 |  |
|   rn-west-20050  | us-east-3 | 2 | B12 |  |
|   rn-west-20050  | us-east-3 | 3 | B12 |  |
|   rn-west-20050  | us-east-3 | 4 | B12 |  |
|   rn-west-20050  | us-east-3 | 5 | B12 |  |
|   rn-west-20079  | us-central-4 | 1 | B12 |  |
|   rn-west-20079  | us-central-4 | 2 | B12 |  |
|   rn-west-20079  | us-central-4 | 3 | B12 |  |
|   rn-west-20079  | us-central-4 | 4 | B12 |  |
|   rn-west-20079  | us-central-4 | 5 | B12 |  |
|   rn-west-20105  | us-east-3 | 1 | B12 |  |
|   rn-west-20105  | us-east-3 | 2 | B12 |  |
|   rn-west-20105  | us-east-3 | 3 | B12 |  |
|   rn-west-20105  | us-east-3 | 4 | B12 |  |
|   rn-west-20105  | us-east-3 | 5 | B12 |  |
|   rn-west-20134  | us-central-4 | 1 | B12 |  |
|   rn-west-20134  | us-central-4 | 2 | B12 |  |
|   rn-west-20134  | us-central-4 | 3 | B12 |  |
|   rn-west-20134  | us-central-4 | 4 | B12 |  |
|   rn-west-20134  | us-central-4 | 5 | B12 |  |
|   rn-west-20158  | us-east-3 | 1 | B12 |  |
|   rn-west-20158  | us-east-3 | 2 | B12 |  |
|   rn-west-20158  | us-central-4 | 3 | B12 |  |
|   rn-west-20158  | us-central-4 | 4 | B12 |  |
|   rn-west-20158  | us-east-3 | 5 | B12 |  |
|   rn-west-20190  | us-central-4 | 1 | B12 |  |
|   rn-west-20190  | us-central-4 | 2 | B12 |  |
|   rn-west-20190  | us-central-4 | 3 | B12 |  |
|   rn-west-20190  | us-central-4 | 4 | B12 |  |
|   rn-west-20190  | us-central-4 | 5 | B12 |  |
|   rn-west-20216  | us-east-3 | 1 | B12 |  |
|   rn-west-20216  | us-east-3 | 2 | B12 |  |
|   rn-west-20216  | us-east-3 | 3 | B12 |  |
|   rn-west-20216  | us-east-3 | 4 | B12 |  |
|   rn-west-20216  | us-east-3 | 5 | B12 |  |
|   rn-west-20247  | us-central-4 | 1 | B12 |  |
|   rn-west-20247  | us-central-4 | 2 | B12 |  |
|   rn-west-20247  | us-central-4 | 3 | B12 |  |
|   rn-west-20247  | us-central-4 | 4 | B12 |  |
|   rn-west-20247  | us-central-4 | 5 | B12 |  |
|   rn-west-20274  | us-east-3 | 1 | B12 |  |
|   rn-west-20274  | us-east-3 | 2 | B12 |  |
|   rn-west-20274  | us-central-4 | 3 | B12 |  |
|   rn-west-20274  | us-east-3 | 4 | B12 |  |
|   rn-west-20274  | us-east-3 | 5 | B12 |  |
|   rn-west-20301  | us-central-4 | 1 | B12 |  |
|   rn-west-20301  | us-central-4 | 2 | B12 |  |
|   rn-west-20301  | us-central-4 | 3 | B12 |  |
|   rn-west-20301  | us-central-4 | 4 | B12 |  |
|   rn-west-20301  | us-central-4 | 5 | B12 |  |
|   rn-west-20331  | us-east-3 | 1 | B12 |  |
|   rn-west-20331  | us-east-3 | 2 | B12 |  |
|   rn-west-20331  | us-east-3 | 3 | B12 |  |
|   rn-west-20331  | us-east-3 | 4 | B12 |  |
|   rn-west-20331  | us-east-3 | 5 | B12 |  |
|   rn-west-20357  | us-central-4 | 1 | B12 |  |
|   rn-west-20357  | us-central-4 | 2 | B12 |  |
|   rn-west-20357  | us-central-4 | 3 | B12 |  |
|   rn-west-20357  | us-central-4 | 4 | B12 |  |
|   rn-west-20357  | us-central-4 | 5 | B12 |  |
|   rn-west-20386  | us-east-3 | 1 | B12 |  |
|   rn-west-20386  | us-east-3 | 2 | B12 |  |
|   rn-west-20386  | us-east-3 | 3 | B12 |  |
|   rn-west-20386  | us-east-3 | 4 | B12 |  |
|   rn-west-20386  | us-east-3 | 5 | B12 |  |
|   rn-west-20413  | us-central-4 | 1 | B12 |  |
|   rn-west-20413  | us-central-4 | 2 | B12 |  |
|   rn-west-20413  | us-central-4 | 3 | B12 |  |
|   rn-west-20413  | us-central-4 | 4 | B12 |  |
|   rn-west-20413  | us-central-4 | 5 | B12 |  |
|   rn-west-20438  | us-east-3 | 1 | B12 |  |
|   rn-west-20438  | us-east-3 | 2 | B12 |  |
|   rn-west-20438  | us-east-3 | 3 | B12 |  |
|   rn-west-20438  | us-east-3 | 4 | B12 |  |
|   rn-west-20438  | us-east-3 | 5 | B12 |  |
|   rn-west-20469  | us-central-4 | 1 | B12 |  |
|   rn-west-20469  | us-central-4 | 2 | B12 |  |
|   rn-west-20469  | us-central-4 | 3 | B12 |  |
|   rn-west-20469  | us-central-4 | 4 | B12 |  |
|   rn-west-20469  | us-central-4 | 5 | B12 |  |
|   rn-west-20495  | us-east-3 | 1 | B12 |  |
|   rn-west-20495  | us-east-3 | 2 | B12 |  |
|   rn-west-20495  | us-central-4 | 3 | B12 |  |
|   rn-west-20495  | us-east-3 | 4 | B12 |  |
|   rn-west-20495  | us-central-4 | 5 | B12 |  |
|   rn-west-20523  | us-central-4 | 1 | B12 |  |
|   rn-west-20523  | us-central-4 | 2 | B12 |  |
|   rn-west-20523  | us-central-4 | 3 | B12 |  |
|   rn-west-20523  | us-central-4 | 4 | B12 |  |
|   rn-west-20523  | us-central-4 | 5 | B12 |  |
|   rn-west-20555  | us-east-3 | 1 | B12 |  |
|   rn-west-20555  | us-east-3 | 2 | B12 |  |
|   rn-west-20555  | us-east-3 | 3 | B12 |  |
|   rn-west-20555  | us-east-3 | 4 | B12 |  |
|   rn-west-20555  | us-east-3 | 5 | B12 |  |
|   rn-west-20578  | us-central-4 | 1 | B12 |  |
|   rn-west-20578  | us-central-4 | 2 | B12 |  |
|   rn-west-20578  | us-central-4 | 3 | B12 |  |
|   rn-west-20578  | us-central-4 | 4 | B12 |  |
|   rn-west-20578  | us-central-4 | 5 | B12 |  |
|   rn-west-20605  | us-east-3 | 1 | B12 |  |
|   rn-west-20605  | us-east-3 | 2 | B12 |  |
|   rn-west-20605  | us-east-3 | 3 | B12 |  |
|   rn-west-20605  | us-east-3 | 4 | B12 |  |
|   rn-west-20605  | us-east-3 | 5 | B12 |  |
|   rn-west-20637  | us-central-4 | 1 | B12 |  |
|   rn-west-20637  | us-central-4 | 2 | B12 |  |
|   rn-west-20637  | us-central-4 | 3 | B12 |  |
|   rn-west-20637  | us-central-4 | 4 | B12 |  |
|   rn-west-20637  | us-central-4 | 5 | B12 |  |
|   rn-west-20667  | us-east-3 | 1 | B12 |  |
|   rn-west-20667  | us-east-3 | 2 | B12 |  |
|   rn-west-20667  | us-east-3 | 3 | B12 |  |
|   rn-west-20667  | us-east-3 | 4 | B12 |  |
|   rn-west-20667  | us-east-3 | 5 | B12 |  |
|   rn-west-20693  | us-central-4 | 1 | B12 |  |
|   rn-west-20693  | us-central-4 | 2 | B12 |  |
|   rn-west-20693  | us-east-3 | 3 | B12 |  |
|   rn-west-20693  | us-central-4 | 4 | B12 |  |
|   rn-west-20693  | us-central-4 | 5 | B12 |  |
|   rn-west-20723  | us-east-3 | 1 | B12 |  |
|   rn-west-20723  | us-east-3 | 2 | B12 |  |
|   rn-west-20723  | us-east-3 | 3 | B12 |  |
|   rn-west-20723  | us-east-3 | 4 | B12 |  |
|   rn-west-20723  | us-east-3 | 5 | B12 |  |
|   rn-west-20747  | us-central-4 | 1 | B12 |  |
|   rn-west-20747  | us-central-4 | 2 | B12 |  |
|   rn-west-20747  | us-central-4 | 3 | B12 |  |
|   rn-west-20747  | us-central-4 | 4 | B12 |  |
|   rn-west-20747  | us-central-4 | 5 | B12 |  |
|   rn-west-20779  | us-east-3 | 1 | B12 |  |
|   rn-west-20779  | us-east-3 | 2 | B12 |  |
|   rn-west-20779  | us-east-3 | 3 | B12 |  |
|   rn-west-20779  | us-central-4 | 4 | B12 |  |
|   rn-west-20779  | us-east-3 | 5 | B12 |  |
|   rn-west-20803  | us-central-4 | 1 | B12 |  |
|   rn-west-20803  | us-central-4 | 2 | B12 |  |
|   rn-west-20803  | us-central-4 | 3 | B12 |  |
|   rn-west-20803  | us-central-4 | 4 | B12 |  |
|   rn-west-20803  | us-east-3 | 5 | B12 |  |
|   rn-west-20833  | us-east-3 | 1 | B12 |  |
|   rn-west-20833  | us-east-3 | 2 | B12 |  |
|   rn-west-20833  | us-east-3 | 3 | B12 |  |
|   rn-west-20833  | us-east-3 | 4 | B12 |  |
|   rn-west-20833  | us-central-4 | 5 | B12 |  |
|   rn-west-20858  | us-central-4 | 1 | B12 |  |
|   rn-west-20858  | us-central-4 | 2 | B12 |  |
|   rn-west-20858  | us-central-4 | 3 | B12 |  |
|   rn-west-20858  | us-central-4 | 4 | B12 |  |
|   rn-west-20858  | us-east-3 | 5 | B12 |  |
|   rn-west-20891  | us-east-3 | 1 | B12 |  |
|   rn-west-20891  | us-east-3 | 2 | B12 |  |
|   rn-west-20891  | us-central-4 | 3 | B12 |  |
|   rn-west-20891  | us-east-3 | 4 | B12 |  |
|   rn-west-20891  | us-east-3 | 5 | B12 |  |
|   rn-west-20919  | us-central-4 | 1 | B12 |  |
|   rn-west-20919  | us-central-4 | 2 | B12 |  |
|   rn-west-20919  | us-central-4 | 3 | B12 |  |
|   rn-west-20919  | us-central-4 | 4 | B12 |  |
|   rn-west-20919  | us-central-4 | 5 | B12 |  |
|   rn-west-20942  | us-east-3 | 1 | B12 |  |
|   rn-west-20942  | us-east-3 | 2 | B12 |  |
|   rn-west-20942  | us-east-3 | 3 | B12 |  |
|   rn-west-20942  | us-east-3 | 4 | B12 |  |
|   rn-west-20942  | us-east-3 | 5 | B12 |  |
|   rn-west-20970  | us-central-4 | 1 | B12 |  |
|   rn-west-20970  | us-central-4 | 2 | B12 |  |
|   rn-west-20970  | us-central-4 | 3 | B12 |  |
|   rn-west-20970  | us-central-4 | 4 | B12 |  |
|   rn-west-20970  | us-central-4 | 5 | B12 |  |
|   rn-west-21000  | us-east-3 | 1 | B12 |  |
|   rn-west-21000  | us-east-3 | 2 | B12 |  |
|   rn-west-21000  | us-east-3 | 3 | B12 |  |
|   rn-west-21000  | us-central-4 | 4 | B12 |  |
|   rn-west-21000  | us-east-3 | 5 | B12 |  |
|   rn-west-21031  | us-central-4 | 1 | B12 |  |
|   rn-west-21031  | us-central-4 | 2 | B12 |  |
|   rn-west-21031  | us-central-4 | 3 | B12 |  |
|   rn-west-21031  | us-central-4 | 4 | B12 |  |
|   rn-west-21031  | us-central-4 | 5 | B12 |  |
|   rn-west-21054  | us-east-3 | 1 | B12 |  |
|   rn-west-21054  | us-east-3 | 2 | B12 |  |
|   rn-west-21054  | us-east-3 | 3 | B12 |  |
|   rn-west-21054  | us-east-3 | 4 | B12 |  |
|   rn-west-21054  | us-east-3 | 5 | B12 |  |
|   rn-west-21085  | us-central-4 | 1 | B12 |  |
|   rn-west-21085  | us-central-4 | 2 | B12 |  |
|   rn-west-21085  | us-central-4 | 3 | B12 |  |
|   rn-west-21085  | us-central-4 | 4 | B12 |  |
|   rn-west-21085  | us-central-4 | 5 | B12 |  |
|   rn-west-21114  | us-east-3 | 1 | B12 |  |
|   rn-west-21114  | us-east-3 | 2 | B12 |  |
|   rn-west-21114  | us-east-3 | 3 | B12 |  |
|   rn-west-21114  | us-east-3 | 4 | B12 |  |
|   rn-west-21114  | us-east-3 | 5 | B12 |  |
|   rn-west-21138  | us-central-4 | 1 | B12 |  |
|   rn-west-21138  | us-central-4 | 2 | B12 |  |
|   rn-west-21138  | us-central-4 | 3 | B12 |  |
|   rn-west-21138  | us-central-4 | 4 | B12 |  |
|   rn-west-21138  | us-central-4 | 5 | B12 |  |
|   rn-west-21171  | us-east-3 | 1 | B12 |  |
|   rn-west-21171  | us-east-3 | 2 | B12 |  |
|   rn-west-21171  | us-east-3 | 3 | B12 |  |
|   rn-west-21171  | us-central-4 | 4 | B12 |  |
|   rn-west-21171  | us-east-3 | 5 | B12 |  |
|   rn-west-21199  | us-central-4 | 1 | B12 |  |
|   rn-west-21199  | us-central-4 | 2 | B12 |  |
|   rn-west-21199  | us-central-4 | 3 | B12 |  |
|   rn-west-21199  | us-central-4 | 4 | B12 |  |
|   rn-west-21199  | us-central-4 | 5 | B12 |  |
|   rn-west-21222  | us-east-3 | 1 | B12 |  |
|   rn-west-21222  | us-east-3 | 2 | B12 |  |
|   rn-west-21222  | us-east-3 | 3 | B12 |  |
|   rn-west-21222  | us-east-3 | 4 | B12 |  |
|   rn-west-21222  | us-east-3 | 5 | B12 |  |
|   rn-west-21253  | us-central-4 | 1 | B12 |  |
|   rn-west-21253  | us-central-4 | 2 | B12 |  |
|   rn-west-21253  | us-central-4 | 3 | B12 |  |
|   rn-west-21253  | us-central-4 | 4 | B12 |  |
|   rn-west-21253  | us-central-4 | 5 | B12 |  |
|   rn-west-21279  | us-east-3 | 1 | B12 |  |
|   rn-west-21279  | us-east-3 | 2 | B12 |  |
|   rn-west-21279  | us-east-3 | 3 | B12 |  |
|   rn-west-21279  | us-east-3 | 4 | B12 |  |
|   rn-west-21279  | us-east-3 | 5 | B12 |  |
|   rn-west-21305  | us-central-4 | 1 | B12 |  |
|   rn-west-21305  | us-central-4 | 2 | B12 |  |
|   rn-west-21305  | us-central-4 | 3 | B12 |  |
|   rn-west-21305  | us-central-4 | 4 | B12 |  |
|   rn-west-21305  | us-central-4 | 5 | B12 |  |
|   rn-west-21337  | us-east-3 | 1 | B12 |  |
|   rn-west-21337  | us-east-3 | 2 | B12 |  |
|   rn-west-21337  | us-east-3 | 3 | B12 |  |
|   rn-west-21337  | us-east-3 | 4 | B12 |  |
|   rn-west-21337  | us-east-3 | 5 | B12 |  |
|   rn-west-21366  | us-central-4 | 1 | B12 |  |
|   rn-west-21366  | us-central-4 | 2 | B12 |  |
|   rn-west-21366  | us-central-4 | 3 | B12 |  |
|   rn-west-21366  | us-central-4 | 4 | B12 |  |
|   rn-west-21366  | us-central-4 | 5 | B12 |  |
|   rn-west-21390  | us-east-3 | 1 | B12 |  |
|   rn-west-21390  | us-east-3 | 2 | B12 |  |
|   rn-west-21390  | us-east-3 | 3 | B12 |  |
|   rn-west-21390  | us-east-3 | 4 | B12 |  |
|   rn-west-21390  | us-east-3 | 5 | B12 |  |
|   rn-west-21420  | us-central-4 | 1 | B12 |  |
|   rn-west-21420  | us-central-4 | 2 | B12 |  |
|   rn-west-21420  | us-central-4 | 3 | B12 |  |
|   rn-west-21420  | us-central-4 | 4 | B12 |  |
|   rn-west-21420  | us-central-4 | 5 | B12 |  |
|   rn-west-21451  | us-east-3 | 1 | B12 |  |
|   rn-west-21451  | us-east-3 | 2 | B12 |  |
|   rn-west-21451  | us-east-3 | 3 | B12 |  |
|   rn-west-21451  | us-east-3 | 4 | B12 |  |
|   rn-west-21451  | us-east-3 | 5 | B12 |  |
|   rn-west-21477  | us-central-4 | 1 | B12 |  |
|   rn-west-21477  | us-central-4 | 2 | B12 |  |
|   rn-west-21477  | us-central-4 | 3 | B12 |  |
|   rn-west-21477  | us-central-4 | 4 | B12 |  |
|   rn-west-21477  | us-central-4 | 5 | B12 |  |
|   rn-west-21507  | us-east-3 | 1 | B12 |  |
|   rn-west-21507  | us-east-3 | 2 | B12 |  |
|   rn-west-21507  | us-east-3 | 3 | B12 |  |
|   rn-west-21507  | us-east-3 | 4 | B12 |  |
|   rn-west-21507  | us-east-3 | 5 | B12 |  |
|   rn-west-21534  | us-central-4 | 1 | B12 |  |
|   rn-west-21534  | us-central-4 | 2 | B12 |  |
|   rn-west-21534  | us-central-4 | 3 | B12 |  |
|   rn-west-21534  | us-central-4 | 4 | B12 |  |
|   rn-west-21534  | us-central-4 | 5 | B12 |  |
|   rn-west-21559  | us-east-3 | 1 | B12 |  |
|   rn-west-21559  | us-east-3 | 2 | B12 |  |
|   rn-west-21559  | us-central-4 | 3 | B12 |  |
|   rn-west-21559  | us-east-3 | 4 | B12 |  |
|   rn-west-21559  | us-east-3 | 5 | B12 |  |
|   rn-west-21590  | us-central-4 | 1 | B12 |  |
|   rn-west-21590  | us-central-4 | 2 | B12 |  |
|   rn-west-21590  | us-central-4 | 3 | B12 |  |
|   rn-west-21590  | us-central-4 | 4 | B12 |  |
|   rn-west-21590  | us-central-4 | 5 | B12 |  |
|   rn-west-21619  | us-east-3 | 1 | B12 |  |
|   rn-west-21619  | us-east-3 | 2 | B12 |  |
|   rn-west-21619  | us-east-3 | 3 | B12 |  |
|   rn-west-21619  | us-east-3 | 4 | B12 |  |
|   rn-west-21619  | us-east-3 | 5 | B12 |  |
|   rn-west-21647  | us-central-4 | 1 | B12 |  |
|   rn-west-21647  | us-central-4 | 2 | B12 |  |
|   rn-west-21647  | us-east-3 | 3 | B12 |  |
|   rn-west-21647  | us-central-4 | 4 | B12 |  |
|   rn-west-21647  | us-central-4 | 5 | B12 |  |
|   rn-west-21673  | us-east-3 | 1 | B12 |  |
|   rn-west-21673  | us-east-3 | 2 | B12 |  |
|   rn-west-21673  | us-east-3 | 3 | B12 |  |
|   rn-west-21673  | us-east-3 | 4 | B12 |  |
|   rn-west-21673  | us-east-3 | 5 | B12 |  |
|   rn-west-21700  | us-central-4 | 1 | B12 |  |
|   rn-west-21700  | us-central-4 | 2 | B12 |  |
|   rn-west-21700  | us-central-4 | 3 | B12 |  |
|   rn-west-21700  | us-central-4 | 4 | B12 |  |
|   rn-west-21700  | us-central-4 | 5 | B12 |  |
|   rn-west-21725  | us-east-3 | 1 | B12 |  |
|   rn-west-21725  | us-central-4 | 2 | B12 |  |
|   rn-west-21725  | us-east-3 | 3 | B12 |  |
|   rn-west-21725  | us-east-3 | 4 | B12 |  |
|   rn-west-21725  | us-east-3 | 5 | B12 |  |
|   rn-west-21758  | us-central-4 | 1 | B12 |  |
|   rn-west-21758  | us-central-4 | 2 | B12 |  |
|   rn-west-21758  | us-central-4 | 3 | B12 |  |
|   rn-west-21758  | us-central-4 | 4 | B12 |  |
|   rn-west-21758  | us-central-4 | 5 | B12 |  |
|   rn-west-21787  | us-east-3 | 1 | B12 |  |
|   rn-west-21787  | us-east-3 | 2 | B12 |  |
|   rn-west-21787  | us-east-3 | 3 | B12 |  |
|   rn-west-21787  | us-east-3 | 4 | B12 |  |
|   rn-west-21787  | us-east-3 | 5 | B12 |  |
|   rn-west-21810  | us-central-4 | 1 | B12 |  |
|   rn-west-21810  | us-central-4 | 2 | B12 |  |
|   rn-west-21810  | us-central-4 | 3 | B12 |  |
|   rn-west-21810  | us-central-4 | 4 | B12 |  |
|   rn-west-21810  | us-central-4 | 5 | B12 |  |
|   rn-west-21842  | us-east-3 | 1 | B12 |  |
|   rn-west-21842  | us-east-3 | 2 | B12 |  |
|   rn-west-21842  | us-east-3 | 3 | B12 |  |
|   rn-west-21842  | us-east-3 | 4 | B12 |  |
|   rn-west-21842  | us-east-3 | 5 | B12 |  |
|   rn-west-21865  | us-central-4 | 1 | B12 |  |
|   rn-west-21865  | us-central-4 | 2 | B12 |  |
|   rn-west-21865  | us-central-4 | 3 | B12 |  |
|   rn-west-21865  | us-central-4 | 4 | B12 |  |
|   rn-west-21865  | us-central-4 | 5 | B12 |  |
|   rn-west-21898  | us-east-3 | 1 | B12 |  |
|   rn-west-21898  | us-east-3 | 2 | B12 |  |
|   rn-west-21898  | us-east-3 | 3 | B12 |  |
|   rn-west-21898  | us-east-3 | 4 | B12 |  |
|   rn-west-21898  | us-east-3 | 5 | B12 |  |
|   rn-west-21923  | us-central-4 | 1 | B12 |  |
|   rn-west-21923  | us-central-4 | 2 | B12 |  |
|   rn-west-21923  | us-central-4 | 3 | B12 |  |
|   rn-west-21923  | us-central-4 | 4 | B12 |  |
|   rn-west-21923  | us-central-4 | 5 | B12 |  |
|   rn-west-21955  | us-east-3 | 1 | B12 |  |
|   rn-west-21955  | us-east-3 | 2 | B12 |  |
|   rn-west-21955  | us-east-3 | 3 | B12 |  |
|   rn-west-21955  | us-east-3 | 4 | B12 |  |
|   rn-west-21955  | us-east-3 | 5 | B12 |  |
|   rn-west-21979  | us-central-4 | 1 | B12 |  |
|   rn-west-21979  | us-central-4 | 2 | B12 |  |
|   rn-west-21979  | us-central-4 | 3 | B12 |  |
|   rn-west-21979  | us-central-4 | 4 | B12 |  |
|   rn-west-21979  | us-central-4 | 5 | B12 |  |
|   rn-west-22006  | us-east-3 | 1 | B12 |  |
|   rn-west-22006  | us-east-3 | 2 | B12 |  |
|   rn-west-22006  | us-east-3 | 3 | B12 |  |
|   rn-west-22006  | us-east-3 | 4 | B12 |  |
|   rn-west-22006  | us-east-3 | 5 | B12 |  |
|   rn-west-22039  | us-central-4 | 1 | B12 |  |
|   rn-west-22039  | us-central-4 | 2 | B12 |  |
|   rn-west-22039  | us-central-4 | 3 | B12 |  |
|   rn-west-22039  | us-central-4 | 4 | B12 |  |
|   rn-west-22039  | us-central-4 | 5 | B12 |  |
|   rn-west-22064  | us-east-3 | 1 | B12 |  |
|   rn-west-22064  | us-east-3 | 2 | B12 |  |
|   rn-west-22064  | us-east-3 | 3 | B12 |  |
|   rn-west-22064  | us-east-3 | 4 | B12 |  |
|   rn-west-22064  | us-east-3 | 5 | B12 |  |
|   rn-west-22093  | us-central-4 | 1 | B12 |  |
|   rn-west-22093  | us-central-4 | 2 | B12 |  |
|   rn-west-22093  | us-central-4 | 3 | B12 |  |
|   rn-west-22093  | us-central-4 | 4 | B12 |  |
|   rn-west-22093  | us-central-4 | 5 | B12 |  |
|   rn-west-22122  | us-east-3 | 1 | B12 |  |
|   rn-west-22122  | us-east-3 | 2 | B12 |  |
|   rn-west-22122  | us-east-3 | 3 | B12 |  |
|   rn-west-22122  | us-east-3 | 4 | B12 |  |
|   rn-west-22122  | us-east-3 | 5 | B12 |  |
|   rn-west-22148  | us-central-4 | 1 | B12 |  |
|   rn-west-22148  | us-central-4 | 2 | B12 |  |
|   rn-west-22148  | us-central-4 | 3 | B12 |  |
|   rn-west-22148  | us-central-4 | 4 | B12 |  |
|   rn-west-22148  | us-central-4 | 5 | B12 |  |
|   rn-west-22173  | us-east-3 | 1 | B12 |  |
|   rn-west-22173  | us-east-3 | 2 | B12 |  |
|   rn-west-22173  | us-east-3 | 3 | B12 |  |
|   rn-west-22173  | us-east-3 | 4 | B12 |  |
|   rn-west-22173  | us-east-3 | 5 | B12 |  |
|   rn-west-22205  | us-central-4 | 1 | B12 |  |
|   rn-west-22205  | us-central-4 | 2 | B12 |  |
|   rn-west-22205  | us-central-4 | 3 | B12 |  |
|   rn-west-22205  | us-central-4 | 4 | B12 |  |
|   rn-west-22205  | us-central-4 | 5 | B12 |  |
|   rn-west-22231  | us-east-3 | 1 | B12 |  |
|   rn-west-22231  | us-east-3 | 2 | B12 |  |
|   rn-west-22231  | us-east-3 | 3 | B12 |  |
|   rn-west-22231  | us-east-3 | 4 | B12 |  |
|   rn-west-22231  | us-east-3 | 5 | B12 |  |
|   rn-west-22258  | us-central-4 | 1 | B12 |  |
|   rn-west-22258  | us-central-4 | 2 | B12 |  |
|   rn-west-22258  | us-central-4 | 3 | B12 |  |
|   rn-west-22258  | us-central-4 | 4 | B12 |  |
|   rn-west-22258  | us-central-4 | 5 | B12 |  |
|   rn-west-22288  | us-east-3 | 1 | B12 |  |
|   rn-west-22288  | us-east-3 | 2 | B12 |  |
|   rn-west-22288  | us-east-3 | 3 | B12 |  |
|   rn-west-22288  | us-east-3 | 4 | B12 |  |
|   rn-west-22288  | us-east-3 | 5 | B12 |  |
|   rn-west-22318  | us-central-4 | 1 | B12 |  |
|   rn-west-22318  | us-central-4 | 2 | B12 |  |
|   rn-west-22318  | us-central-4 | 3 | B12 |  |
|   rn-west-22318  | us-central-4 | 4 | B12 |  |
|   rn-west-22318  | us-central-4 | 5 | B12 |  |
|   rn-west-22347  | us-east-3 | 1 | B12 |  |
|   rn-west-22347  | us-central-4 | 2 | B12 |  |
|   rn-west-22347  | us-east-3 | 3 | B12 |  |
|   rn-west-22347  | us-east-3 | 4 | B12 |  |
|   rn-west-22347  | us-east-3 | 5 | B12 |  |
|   rn-west-22375  | us-central-4 | 1 | B12 |  |
|   rn-west-22375  | us-central-4 | 2 | B12 |  |
|   rn-west-22375  | us-central-4 | 3 | B12 |  |
|   rn-west-22375  | us-central-4 | 4 | B12 |  |
|   rn-west-22375  | us-central-4 | 5 | B12 |  |
|   rn-west-22401  | us-east-3 | 1 | B12 |  |
|   rn-west-22401  | us-east-3 | 2 | B12 |  |
|   rn-west-22401  | us-east-3 | 3 | B12 |  |
|   rn-west-22401  | us-east-3 | 4 | B12 |  |
|   rn-west-22401  | us-east-3 | 5 | B12 |  |
|   rn-west-22428  | us-central-4 | 1 | B12 |  |
|   rn-west-22428  | us-central-4 | 2 | B12 |  |
|   rn-west-22428  | us-central-4 | 3 | B12 |  |
|   rn-west-22428  | us-east-3 | 4 | B12 |  |
|   rn-west-22428  | us-central-4 | 5 | B12 |  |
|   rn-west-22454  | us-east-3 | 1 | B12 |  |
|   rn-west-22454  | us-central-4 | 2 | B12 |  |
|   rn-west-22454  | us-east-3 | 3 | B12 |  |
|   rn-west-22454  | us-east-3 | 4 | B12 |  |
|   rn-west-22454  | us-east-3 | 5 | B12 |  |
|   rn-west-22484  | us-central-4 | 1 | B12 |  |
|   rn-west-22484  | us-central-4 | 2 | B12 |  |
|   rn-west-22484  | us-central-4 | 3 | B12 |  |
|   rn-west-22484  | us-central-4 | 4 | B12 |  |
|   rn-west-22484  | us-central-4 | 5 | B12 |  |
|   rn-west-22511  | us-east-3 | 1 | B12 |  |
|   rn-west-22511  | us-east-3 | 2 | B12 |  |
|   rn-west-22511  | us-east-3 | 3 | B12 |  |
|   rn-west-22511  | us-east-3 | 4 | B12 |  |
|   rn-west-22511  | us-east-3 | 5 | B12 |  |
|   rn-west-22543  | us-central-4 | 1 | B12 |  |
|   rn-west-22543  | us-central-4 | 2 | B12 |  |
|   rn-west-22543  | us-central-4 | 3 | B12 |  |
|   rn-west-22543  | us-central-4 | 4 | B12 |  |
|   rn-west-22543  | us-central-4 | 5 | B12 |  |
|   rn-west-22571  | us-east-3 | 1 | B12 |  |
|   rn-west-22571  | us-east-3 | 2 | B12 |  |
|   rn-west-22571  | us-east-3 | 3 | B12 |  |
|   rn-west-22571  | us-east-3 | 4 | B12 |  |
|   rn-west-22571  | us-east-3 | 5 | B12 |  |
|   rn-west-22594  | us-central-4 | 1 | B12 |  |
|   rn-west-22594  | us-central-4 | 2 | B12 |  |
|   rn-west-22594  | us-central-4 | 3 | B12 |  |
|   rn-west-22594  | us-central-4 | 4 | B12 |  |
|   rn-west-22594  | us-central-4 | 5 | B12 |  |
|   rn-west-22627  | us-east-3 | 1 | B12 |  |
|   rn-west-22627  | us-central-4 | 2 | B12 |  |
|   rn-west-22627  | us-east-3 | 3 | B12 |  |
|   rn-west-22627  | us-east-3 | 4 | B12 |  |
|   rn-west-22627  | us-central-4 | 5 | B12 |  |
|   rn-west-22651  | us-central-4 | 1 | B12 |  |
|   rn-west-22651  | us-central-4 | 2 | B12 |  |
|   rn-west-22651  | us-central-4 | 3 | B12 |  |
|   rn-west-22651  | us-central-4 | 4 | B12 |  |
|   rn-west-22651  | us-central-4 | 5 | B12 |  |
|   rn-west-22682  | us-east-3 | 1 | B12 |  |
|   rn-west-22682  | us-east-3 | 2 | B12 |  |
|   rn-west-22682  | us-east-3 | 3 | B12 |  |
|   rn-west-22682  | us-east-3 | 4 | B12 |  |
|   rn-west-22682  | us-east-3 | 5 | B12 |  |
|   rn-west-22710  | us-central-4 | 1 | B12 |  |
|   rn-west-22710  | us-central-4 | 2 | B12 |  |
|   rn-west-22710  | us-central-4 | 3 | B12 |  |
|   rn-west-22710  | us-east-3 | 4 | B12 |  |
|   rn-west-22710  | us-central-4 | 5 | B12 |  |
|   rn-west-22737  | us-east-3 | 1 | B12 |  |
|   rn-west-22737  | us-east-3 | 2 | B12 |  |
|   rn-west-22737  | us-east-3 | 3 | B12 |  |
|   rn-west-22737  | us-east-3 | 4 | B12 |  |
|   rn-west-22737  | us-east-3 | 5 | B12 |  |
|   rn-west-22761  | us-central-4 | 1 | B12 |  |
|   rn-west-22761  | us-central-4 | 2 | B12 |  |
|   rn-west-22761  | us-central-4 | 3 | B12 |  |
|   rn-west-22761  | us-central-4 | 4 | B12 |  |
|   rn-west-22761  | us-central-4 | 5 | B12 |  |
|   rn-west-22794  | us-east-3 | 1 | B12 |  |
|   rn-west-22794  | us-east-3 | 2 | B12 |  |
|   rn-west-22794  | us-east-3 | 3 | B12 |  |
|   rn-west-22794  | us-east-3 | 4 | B12 |  |
|   rn-west-22794  | us-east-3 | 5 | B12 |  |
|   rn-west-22822  | us-central-4 | 1 | B12 |  |
|   rn-west-22822  | us-central-4 | 2 | B12 |  |
|   rn-west-22822  | us-central-4 | 3 | B12 |  |
|   rn-west-22822  | us-central-4 | 4 | B12 |  |
|   rn-west-22822  | us-central-4 | 5 | B12 |  |
|   rn-west-22847  | us-east-3 | 1 | B12 |  |
|   rn-west-22847  | us-east-3 | 2 | B12 |  |
|   rn-west-22847  | us-east-3 | 3 | B12 |  |
|   rn-west-22847  | us-east-3 | 4 | B12 |  |
|   rn-west-22847  | us-east-3 | 5 | B12 |  |
|   rn-west-22879  | us-central-4 | 1 | B12 |  |
|   rn-west-22879  | us-central-4 | 2 | B12 |  |
|   rn-west-22879  | us-central-4 | 3 | B12 |  |
|   rn-west-22879  | us-central-4 | 4 | B12 |  |
|   rn-west-22879  | us-central-4 | 5 | B12 |  |
|   rn-west-22905  | us-east-3 | 1 | B12 |  |
|   rn-west-22905  | us-east-3 | 2 | B12 |  |
|   rn-west-22905  | us-east-3 | 3 | B12 |  |
|   rn-west-22905  | us-east-3 | 4 | B12 |  |
|   rn-west-22905  | us-east-3 | 5 | B12 |  |
|   rn-west-22933  | us-central-4 | 1 | B12 |  |
|   rn-west-22933  | us-central-4 | 2 | B12 |  |
|   rn-west-22933  | us-central-4 | 3 | B12 |  |
|   rn-west-22933  | us-central-4 | 4 | B12 |  |
|   rn-west-22933  | us-central-4 | 5 | B12 |  |
|   rn-west-22957  | us-east-3 | 1 | B12 |  |
|   rn-west-22957  | us-east-3 | 2 | B12 |  |
|   rn-west-22957  | us-east-3 | 3 | B12 |  |
|   rn-west-22957  | us-east-3 | 4 | B12 |  |
|   rn-west-22957  | us-east-3 | 5 | B12 |  |
|   rn-west-22986  | us-central-4 | 1 | B12 |  |
|   rn-west-22986  | us-central-4 | 2 | B12 |  |
|   rn-west-22986  | us-central-4 | 3 | B12 |  |
|   rn-west-22986  | us-central-4 | 4 | B12 |  |
|   rn-west-22986  | us-central-4 | 5 | B12 |  |
|   rn-west-23013  | us-east-3 | 1 | B12 |  |
|   rn-west-23013  | us-central-4 | 2 | B12 |  |
|   rn-west-23013  | us-east-3 | 3 | B12 |  |
|   rn-west-23013  | us-east-3 | 4 | B12 |  |
|   rn-west-23013  | us-east-3 | 5 | B12 |  |
|   rn-west-23047  | us-central-4 | 1 | B12 |  |
|   rn-west-23047  | us-central-4 | 2 | B12 |  |
|   rn-west-23047  | us-central-4 | 3 | B12 |  |
|   rn-west-23047  | us-central-4 | 4 | B12 |  |
|   rn-west-23047  | us-central-4 | 5 | B12 |  |
|   rn-west-23073  | us-east-3 | 1 | B12 |  |
|   rn-west-23073  | us-east-3 | 2 | B12 |  |
|   rn-west-23073  | us-east-3 | 3 | B12 |  |
|   rn-west-23073  | us-east-3 | 4 | B12 |  |
|   rn-west-23073  | us-east-3 | 5 | B12 |  |
|   rn-west-23103  | us-central-4 | 1 | B12 |  |
|   rn-west-23103  | us-central-4 | 2 | B12 |  |
|   rn-west-23103  | us-central-4 | 3 | B12 |  |
|   rn-west-23103  | us-central-4 | 4 | B12 |  |
|   rn-west-23103  | us-central-4 | 5 | B12 |  |
|   rn-west-23126  | us-east-3 | 1 | B12 |  |
|   rn-west-23126  | us-east-3 | 2 | B12 |  |
|   rn-west-23126  | us-east-3 | 3 | B12 |  |
|   rn-west-23126  | us-east-3 | 4 | B12 |  |
|   rn-west-23126  | us-east-3 | 5 | B12 |  |
|   rn-west-23157  | us-central-4 | 1 | B12 |  |
|   rn-west-23157  | us-central-4 | 2 | B12 |  |
|   rn-west-23157  | us-central-4 | 3 | B12 |  |
|   rn-west-23157  | us-central-4 | 4 | B12 |  |
|   rn-west-23157  | us-central-4 | 5 | B12 |  |
|   rn-west-23182  | us-east-3 | 1 | B12 |  |
|   rn-west-23182  | us-east-3 | 2 | B12 |  |
|   rn-west-23182  | us-east-3 | 3 | B12 |  |
|   rn-west-23182  | us-east-3 | 4 | B12 |  |
|   rn-west-23182  | us-central-4 | 5 | B12 |  |
|   rn-west-23211  | us-central-4 | 1 | B12 |  |
|   rn-west-23211  | us-east-3 | 2 | B12 |  |
|   rn-west-23211  | us-east-3 | 3 | B12 |  |
|   rn-west-23211  | us-central-4 | 4 | B12 |  |
|   rn-west-23211  | us-central-4 | 5 | B12 |  |
|   rn-west-23239  | us-east-3 | 1 | B12 |  |
|   rn-west-23239  | us-east-3 | 2 | B12 |  |
|   rn-west-23239  | us-east-3 | 3 | B12 |  |
|   rn-west-23239  | us-east-3 | 4 | B12 |  |
|   rn-west-23239  | us-east-3 | 5 | B12 |  |
|   rn-west-23267  | us-central-4 | 1 | B12 |  |
|   rn-west-23267  | us-central-4 | 2 | B12 |  |
|   rn-west-23267  | us-central-4 | 3 | B12 |  |
|   rn-west-23267  | us-central-4 | 4 | B12 |  |
|   rn-west-23267  | us-central-4 | 5 | B12 |  |
|   rn-west-23299  | us-east-3 | 1 | B12 |  |
|   rn-west-23299  | us-central-4 | 2 | B12 |  |
|   rn-west-23299  | us-east-3 | 3 | B12 |  |
|   rn-west-23299  | us-east-3 | 4 | B12 |  |
|   rn-west-23299  | us-east-3 | 5 | B12 |  |
|   rn-west-23325  | us-central-4 | 1 | B12 |  |
|   rn-west-23325  | us-central-4 | 2 | B12 |  |
|   rn-west-23325  | us-central-4 | 3 | B12 |  |
|   rn-west-23325  | us-central-4 | 4 | B12 |  |
|   rn-west-23325  | us-central-4 | 5 | B12 |  |
|   rn-west-23351  | us-east-3 | 1 | B12 |  |
|   rn-west-23351  | us-east-3 | 2 | B12 |  |
|   rn-west-23351  | us-east-3 | 3 | B12 |  |
|   rn-west-23351  | us-east-3 | 4 | B12 |  |
|   rn-west-23351  | us-east-3 | 5 | B12 |  |
|   rn-west-23379  | us-central-4 | 1 | B12 |  |
|   rn-west-23379  | us-central-4 | 2 | B12 |  |
|   rn-west-23379  | us-central-4 | 3 | B12 |  |
|   rn-west-23379  | us-central-4 | 4 | B12 |  |
|   rn-west-23379  | us-central-4 | 5 | B12 |  |
|   rn-west-23408  | us-east-3 | 1 | B12 |  |
|   rn-west-23408  | us-east-3 | 2 | B12 |  |
|   rn-west-23408  | us-east-3 | 3 | B12 |  |
|   rn-west-23408  | us-east-3 | 4 | B12 |  |
|   rn-west-23408  | us-east-3 | 5 | B12 |  |
|   rn-west-23438  | us-central-4 | 1 | B12 |  |
|   rn-west-23438  | us-east-3 | 2 | B12 |  |
|   rn-west-23438  | us-central-4 | 3 | B12 |  |
|   rn-west-23438  | us-central-4 | 4 | B12 |  |
|   rn-west-23438  | us-central-4 | 5 | B12 |  |
|   rn-west-23462  | us-east-3 | 1 | B12 |  |
|   rn-west-23462  | us-east-3 | 2 | B12 |  |
|   rn-west-23462  | us-east-3 | 3 | B12 |  |
|   rn-west-23462  | us-east-3 | 4 | B12 |  |
|   rn-west-23462  | us-east-3 | 5 | B12 |  |
|   rn-west-23489  | us-central-4 | 1 | B12 |  |
|   rn-west-23489  | us-central-4 | 2 | B12 |  |
|   rn-west-23489  | us-central-4 | 3 | B12 |  |
|   rn-west-23489  | us-central-4 | 4 | B12 |  |
|   rn-west-23489  | us-central-4 | 5 | B12 |  |
|   rn-west-23519  | us-east-3 | 1 | B12 |  |
|   rn-west-23519  | us-east-3 | 2 | B12 |  |
|   rn-west-23519  | us-east-3 | 3 | B12 |  |
|   rn-west-23519  | us-east-3 | 4 | B12 |  |
|   rn-west-23519  | us-east-3 | 5 | B12 |  |
|   rn-west-23548  | us-central-4 | 1 | B12 |  |
|   rn-west-23548  | us-central-4 | 2 | B12 |  |
|   rn-west-23548  | us-central-4 | 3 | B12 |  |
|   rn-west-23548  | us-central-4 | 4 | B12 |  |
|   rn-west-23548  | us-central-4 | 5 | B12 |  |
|   rn-west-23576  | us-east-3 | 1 | B12 |  |
|   rn-west-23576  | us-east-3 | 2 | B12 |  |
|   rn-west-23576  | us-east-3 | 3 | B12 |  |
|   rn-west-23576  | us-east-3 | 4 | B12 |  |
|   rn-west-23576  | us-east-3 | 5 | B12 |  |
|   rn-west-23604  | us-central-4 | 1 | B12 |  |
|   rn-west-23604  | us-central-4 | 2 | B12 |  |
|   rn-west-23604  | us-central-4 | 3 | B12 |  |
|   rn-west-23604  | us-central-4 | 4 | B12 |  |
|   rn-west-23604  | us-central-4 | 5 | B12 |  |
|   rn-west-23630  | us-east-3 | 1 | B12 |  |
|   rn-west-23630  | us-east-3 | 2 | B12 |  |
|   rn-west-23630  | us-east-3 | 3 | B12 |  |
|   rn-west-23630  | us-east-3 | 4 | B12 |  |
|   rn-west-23630  | us-east-3 | 5 | B12 |  |
|   rn-west-23659  | us-central-4 | 1 | B12 |  |
|   rn-west-23659  | us-central-4 | 2 | B12 |  |
|   rn-west-23659  | us-central-4 | 3 | B12 |  |
|   rn-west-23659  | us-central-4 | 4 | B12 |  |
|   rn-west-23659  | us-central-4 | 5 | B12 |  |
|   rn-west-23689  | us-east-3 | 1 | B12 |  |
|   rn-west-23689  | us-east-3 | 2 | B12 |  |
|   rn-west-23689  | us-east-3 | 3 | B12 |  |
|   rn-west-23689  | us-east-3 | 4 | B12 |  |
|   rn-west-23689  | us-east-3 | 5 | B12 |  |
|   rn-west-23717  | us-central-4 | 1 | B12 |  |
|   rn-west-23717  | us-central-4 | 2 | B12 |  |
|   rn-west-23717  | us-central-4 | 3 | B12 |  |
|   rn-west-23717  | us-central-4 | 4 | B12 |  |
|   rn-west-23717  | us-central-4 | 5 | B12 |  |
|   rn-west-23744  | us-east-3 | 1 | B12 |  |
|   rn-west-23744  | us-east-3 | 2 | B12 |  |
|   rn-west-23744  | us-central-4 | 3 | B12 |  |
|   rn-west-23744  | us-east-3 | 4 | B12 |  |
|   rn-west-23744  | us-east-3 | 5 | B12 |  |
|   rn-west-23772  | us-central-4 | 1 | B12 |  |
|   rn-west-23772  | us-central-4 | 2 | B12 |  |
|   rn-west-23772  | us-central-4 | 3 | B12 |  |
|   rn-west-23772  | us-central-4 | 4 | B12 |  |
|   rn-west-23772  | us-central-4 | 5 | B12 |  |
|   rn-west-23801  | us-east-3 | 1 | B12 |  |
|   rn-west-23801  | us-east-3 | 2 | B12 |  |
|   rn-west-23801  | us-east-3 | 3 | B12 |  |
|   rn-west-23801  | us-east-3 | 4 | B12 |  |
|   rn-west-23801  | us-east-3 | 5 | B12 |  |
|   rn-west-23828  | us-central-4 | 1 | B12 |  |
|   rn-west-23828  | us-central-4 | 2 | B12 |  |
|   rn-west-23828  | us-central-4 | 3 | B12 |  |
|   rn-west-23828  | us-central-4 | 4 | B12 |  |
|   rn-west-23828  | us-central-4 | 5 | B12 |  |
|   rn-west-23857  | us-east-3 | 1 | B12 |  |
|   rn-west-23857  | us-east-3 | 2 | B12 |  |
|   rn-west-23857  | us-east-3 | 3 | B12 |  |
|   rn-west-23857  | us-east-3 | 4 | B12 |  |
|   rn-west-23857  | us-east-3 | 5 | B12 |  |
|   rn-west-23881  | us-central-4 | 1 | B12 |  |
|   rn-west-23881  | us-central-4 | 2 | B12 |  |
|   rn-west-23881  | us-central-4 | 3 | B12 |  |
|   rn-west-23881  | us-central-4 | 4 | B12 |  |
|   rn-west-23881  | us-central-4 | 5 | B12 |  |
|   rn-west-23909  | us-east-3 | 1 | B12 |  |
|   rn-west-23909  | us-east-3 | 2 | B12 |  |
|   rn-west-23909  | us-east-3 | 3 | B12 |  |
|   rn-west-23909  | us-east-3 | 4 | B12 |  |
|   rn-west-23909  | us-east-3 | 5 | B12 |  |
|   rn-west-23940  | us-central-4 | 1 | B12 |  |
|   rn-west-23940  | us-central-4 | 2 | B12 |  |
|   rn-west-23940  | us-central-4 | 3 | B12 |  |
|   rn-west-23940  | us-central-4 | 4 | B12 |  |
|   rn-west-23940  | us-central-4 | 5 | B12 |  |
|   rn-west-23967  | us-east-3 | 1 | B12 |  |
|   rn-west-23967  | us-east-3 | 2 | B12 |  |
|   rn-west-23967  | us-central-4 | 3 | B12 |  |
|   rn-west-23967  | us-east-3 | 4 | B12 |  |
|   rn-west-23967  | us-east-3 | 5 | B12 |  |
|   rn-west-23996  | us-central-4 | 1 | B12 |  |
|   rn-west-23996  | us-central-4 | 2 | B12 |  |
|   rn-west-23996  | us-central-4 | 3 | B12 |  |
|   rn-west-23996  | us-central-4 | 4 | B12 |  |
|   rn-west-23996  | us-central-4 | 5 | B12 |  |
|   rn-west-24023  | us-east-3 | 1 | B12 |  |
|   rn-west-24023  | us-east-3 | 2 | B12 |  |
|   rn-west-24023  | us-central-4 | 3 | B12 |  |
|   rn-west-24023  | us-east-3 | 4 | B12 |  |
|   rn-west-24023  | us-east-3 | 5 | B12 |  |
|   rn-west-24055  | us-central-4 | 1 | B12 |  |
|   rn-west-24055  | us-central-4 | 2 | B12 |  |
|   rn-west-24055  | us-central-4 | 3 | B12 |  |
|   rn-west-24055  | us-central-4 | 4 | B12 |  |
|   rn-west-24055  | us-central-4 | 5 | B12 |  |
|   rn-west-24083  | us-east-3 | 1 | B12 |  |
|   rn-west-24083  | us-east-3 | 2 | B12 |  |
|   rn-west-24083  | us-east-3 | 3 | B12 |  |
|   rn-west-24083  | us-east-3 | 4 | B12 |  |
|   rn-west-24083  | us-central-4 | 5 | B12 |  |
|   rn-west-24107  | us-central-4 | 1 | B12 |  |
|   rn-west-24107  | us-central-4 | 2 | B12 |  |
|   rn-west-24107  | us-central-4 | 3 | B12 |  |
|   rn-west-24107  | us-central-4 | 4 | B12 |  |
|   rn-west-24107  | us-central-4 | 5 | B12 |  |
|   rn-west-24138  | us-east-3 | 1 | B12 |  |
|   rn-west-24138  | us-east-3 | 2 | B12 |  |
|   rn-west-24138  | us-east-3 | 3 | B12 |  |
|   rn-west-24138  | us-east-3 | 4 | B12 |  |
|   rn-west-24138  | us-east-3 | 5 | B12 |  |
|   rn-west-24162  | us-central-4 | 1 | B12 |  |
|   rn-west-24162  | us-central-4 | 2 | B12 |  |
|   rn-west-24162  | us-central-4 | 3 | B12 |  |
|   rn-west-24162  | us-central-4 | 4 | B12 |  |
|   rn-west-24162  | us-central-4 | 5 | B12 |  |
|   rn-west-24194  | us-east-3 | 1 | B12 |  |
|   rn-west-24194  | us-east-3 | 2 | B12 |  |
|   rn-west-24194  | us-east-3 | 3 | B12 |  |
|   rn-west-24194  | us-east-3 | 4 | B12 |  |
|   rn-west-24194  | us-east-3 | 5 | B12 |  |
|   rn-west-24218  | us-central-4 | 1 | B12 |  |
|   rn-west-24218  | us-central-4 | 2 | B12 |  |
|   rn-west-24218  | us-central-4 | 3 | B12 |  |
|   rn-west-24218  | us-central-4 | 4 | B12 |  |
|   rn-west-24218  | us-central-4 | 5 | B12 |  |
|   rn-west-24250  | us-east-3 | 1 | B12 |  |
|   rn-west-24250  | us-central-4 | 2 | B12 |  |
|   rn-west-24250  | us-east-3 | 3 | B12 |  |
|   rn-west-24250  | us-east-3 | 4 | B12 |  |
|   rn-west-24250  | us-east-3 | 5 | B12 |  |
|   rn-west-24276  | us-central-4 | 1 | B12 |  |
|   rn-west-24276  | us-central-4 | 2 | B12 |  |
|   rn-west-24276  | us-central-4 | 3 | B12 |  |
|   rn-west-24276  | us-central-4 | 4 | B12 |  |
|   rn-west-24276  | us-central-4 | 5 | B12 |  |

**Table: Region zones**

| region | zone |
|---|---|
| ap-south-5 | IN+5:30 |
| ap-southeast-6 | AU+10 |
| ca-north-8 | US-5 |
| eu-central-2 | EU+1 |
| eu-west-1 | EU+1 |
| sa-east-7 | BR-3 |
| us-central-4 | US-6 |
| us-east-3 | US-5 |

**Table: Codec glossary**

| codec | kind | meaning |
|---|---|---|
| iso_z | timestamp | ISO 8601 UTC with a trailing Z, for example 2025-10-03T04:05:06Z |
| epoch | timestamp | whole seconds since 1970-01-01T00:00:00Z |
| epoch_ms | timestamp | whole milliseconds since 1970-01-01T00:00:00Z |
| utc_naive | timestamp | YYYY-MM-DD HH:MM:SS read as UTC |
| local | timestamp | YYYY-MM-DD HH:MM:SS read as wall time in the clock zone of the row's runner |
| iso_off | timestamp | ISO 8601 wall time with an explicit numeric offset |
| xl1900 | timestamp | spreadsheet serial day number counted from 1899-12-30T00:00:00Z, fraction is time of day in UTC |
| ms | duration | integer milliseconds |
| us | duration | integer microseconds |
| ns | duration | integer nanoseconds |
| s3 | duration | seconds with exactly three decimals |
| usd6 | money | US dollars with a dot decimal separator and exactly six decimals, leading minus for negatives |
| micro | money | integer micro-dollars |
| eu6 | money | US dollars, dot as thousands separator, comma decimal separator, six decimals |
| kusd9 | money | thousands of US dollars with exactly nine decimals |
| plain | integer | decimal digits only |
| sep | integer | decimal digits with a comma every three digits |
| eu | integer | decimal digits with a dot every three digits |
| kib | integer | byte counts expressed in KiB (value times 1024 is the byte count) |
| exact | identifier | the identifier exactly as written |
| upper | identifier | the identifier in upper case; canonical identifiers are lower case |
| ws | identifier | the identifier padded with spaces; surrounding spaces are not part of it |

**Table: Context dimensions**

| context | meaning |
|---|---|
| region | region of revision 1 of the row's runner in Runner placements; wall times of such rows are in that region's clock zone (Region zones) |
| lang | language in package_metadata.xml of the row's target; for rows about an attempt, erratum or job, the job register target of the job |
| org | text before the first hyphen of the team of the row's handle in the team_roster.xlsx Roster sheet |
| locale | locale of the row's vendor account in vendor_statement.xml |
| batch | the batch column printed on the row |

**Table: Sentinel register**

| file | column | token | meaning |
|---|---|---|---|
| action_keys.lock | digest | none | no toolchain version resolves for the target at period open |
| attempt_events_v3.jsonl | cancel_origin | none | the attempt was not cancelled |
| settlement_ledger.db | reverses |  | the posting is not a reversal |
| toolchain_pins_resolved.json | resolved_open | none | the preparer found no version |
| ownership_patterns_approved.tsv | handle |  | the preparer found no owner |
| invoice_restatement.csv | restated | 0.000000 | dispute closures carry no amount |
| usage_export_legacy.log | elapsed | 0 | REVOKE lines carry no duration |
| lookups_archive.jsonl.gz | result |  | write records carry no lookup result |

**Table: Field conventions**

| file | column | context | value | codec |
|---|---|---|---|---|
| action_keys.lock | action | lang | cpp | upper |
| action_keys.lock | action | lang | go | exact |
| action_keys.lock | action | lang | java | ws |
| action_keys.lock | action | lang | kotlin | ws |
| action_keys.lock | action | lang | python | ws |
| action_keys.lock | action | lang | rust | upper |
| action_keys.lock | action | lang | swift | ws |
| action_keys.lock | action | lang | typescript | exact |
| action_keys.lock | recorded | lang | cpp | iso_z |
| action_keys.lock | recorded | lang | go | epoch_ms |
| action_keys.lock | recorded | lang | java | utc_naive |
| action_keys.lock | recorded | lang | kotlin | utc_naive |
| action_keys.lock | recorded | lang | python | epoch |
| action_keys.lock | recorded | lang | rust | epoch_ms |
| action_keys.lock | recorded | lang | swift | iso_z |
| action_keys.lock | recorded | lang | typescript | epoch |
| change_freeze.ics | dtend | region | ap-south-5 | iso_z |
| change_freeze.ics | dtend | region | ap-southeast-6 | local |
| change_freeze.ics | dtend | region | ca-north-8 | utc_naive |
| change_freeze.ics | dtend | region | eu-central-2 | epoch |
| change_freeze.ics | dtend | region | eu-west-1 | iso_off |
| change_freeze.ics | dtend | region | sa-east-7 | utc_naive |
| change_freeze.ics | dtend | region | us-central-4 | iso_z |
| change_freeze.ics | dtend | region | us-east-3 | iso_z |
| change_freeze.ics | dtstart | region | ap-south-5 | utc_naive |
| change_freeze.ics | dtstart | region | ap-southeast-6 | iso_z |
| change_freeze.ics | dtstart | region | ca-north-8 | iso_off |
| change_freeze.ics | dtstart | region | eu-central-2 | utc_naive |
| change_freeze.ics | dtstart | region | eu-west-1 | local |
| change_freeze.ics | dtstart | region | sa-east-7 | iso_off |
| change_freeze.ics | dtstart | region | us-central-4 | iso_z |
| change_freeze.ics | dtstart | region | us-east-3 | epoch_ms |
| change_freeze.ics | runner | region | ap-south-5 | exact |
| change_freeze.ics | runner | region | ap-southeast-6 | exact |
| change_freeze.ics | runner | region | ca-north-8 | upper |
| change_freeze.ics | runner | region | eu-central-2 | ws |
| change_freeze.ics | runner | region | eu-west-1 | upper |
| change_freeze.ics | runner | region | sa-east-7 | exact |
| change_freeze.ics | runner | region | us-central-4 | upper |
| change_freeze.ics | runner | region | us-east-3 | exact |
| errata_register.docx | attempt | lang | cpp | upper |
| errata_register.docx | attempt | lang | go | exact |
| errata_register.docx | attempt | lang | java | upper |
| errata_register.docx | attempt | lang | kotlin | upper |
| errata_register.docx | attempt | lang | python | ws |
| errata_register.docx | attempt | lang | rust | upper |
| errata_register.docx | attempt | lang | swift | upper |
| errata_register.docx | attempt | lang | typescript | exact |
| errata_register.docx | filed | lang | cpp | iso_z |
| errata_register.docx | filed | lang | go | epoch |
| errata_register.docx | filed | lang | java | epoch_ms |
| errata_register.docx | filed | lang | kotlin | iso_off |
| errata_register.docx | filed | lang | python | utc_naive |
| errata_register.docx | filed | lang | rust | epoch |
| errata_register.docx | filed | lang | swift | iso_z |
| errata_register.docx | filed | lang | typescript | epoch |
| gc_events.csv | artifact | lang | cpp | ws |
| gc_events.csv | artifact | lang | go | exact |
| gc_events.csv | artifact | lang | java | ws |
| gc_events.csv | artifact | lang | kotlin | ws |
| gc_events.csv | artifact | lang | python | upper |
| gc_events.csv | artifact | lang | rust | ws |
| gc_events.csv | artifact | lang | swift | upper |
| gc_events.csv | artifact | lang | typescript | exact |
| gc_events.csv | at | lang | cpp | iso_z |
| gc_events.csv | at | lang | go | utc_naive |
| gc_events.csv | at | lang | java | epoch_ms |
| gc_events.csv | at | lang | kotlin | epoch |
| gc_events.csv | at | lang | python | epoch_ms |
| gc_events.csv | at | lang | rust | utc_naive |
| gc_events.csv | at | lang | swift | iso_z |
| gc_events.csv | at | lang | typescript | utc_naive |
| lookups_shard1.jsonl | action | lang | cpp | exact |
| lookups_shard1.jsonl | action | lang | go | exact |
| lookups_shard1.jsonl | action | lang | java | upper |
| lookups_shard1.jsonl | action | lang | kotlin | ws |
| lookups_shard1.jsonl | action | lang | python | exact |
| lookups_shard1.jsonl | action | lang | rust | ws |
| lookups_shard1.jsonl | action | lang | swift | ws |
| lookups_shard1.jsonl | action | lang | typescript | exact |
| lookups_shard1.jsonl | at | lang | cpp | iso_z |
| lookups_shard1.jsonl | at | lang | go | iso_z |
| lookups_shard1.jsonl | at | lang | java | utc_naive |
| lookups_shard1.jsonl | at | lang | kotlin | epoch |
| lookups_shard1.jsonl | at | lang | python | epoch_ms |
| lookups_shard1.jsonl | at | lang | rust | epoch |
| lookups_shard1.jsonl | at | lang | swift | iso_z |
| lookups_shard1.jsonl | at | lang | typescript | utc_naive |
| lookups_shard1.jsonl | attempt | lang | cpp | exact |
| lookups_shard1.jsonl | attempt | lang | go | upper |
| lookups_shard1.jsonl | attempt | lang | java | ws |
| lookups_shard1.jsonl | attempt | lang | kotlin | ws |
| lookups_shard1.jsonl | attempt | lang | python | upper |
| lookups_shard1.jsonl | attempt | lang | rust | upper |
| lookups_shard1.jsonl | attempt | lang | swift | exact |
| lookups_shard1.jsonl | attempt | lang | typescript | exact |
| lookups_shard1.jsonl | bytes | lang | cpp | plain |
| lookups_shard1.jsonl | bytes | lang | go | plain |
| lookups_shard1.jsonl | bytes | lang | java | kib |
| lookups_shard1.jsonl | bytes | lang | kotlin | kib |
| lookups_shard1.jsonl | bytes | lang | python | sep |
| lookups_shard1.jsonl | bytes | lang | rust | sep |
| lookups_shard1.jsonl | bytes | lang | swift | plain |
| lookups_shard1.jsonl | bytes | lang | typescript | plain |
| lookups_shard1.jsonl | lookup | lang | cpp | upper |
| lookups_shard1.jsonl | lookup | lang | go | exact |
| lookups_shard1.jsonl | lookup | lang | java | ws |
| lookups_shard1.jsonl | lookup | lang | kotlin | upper |
| lookups_shard1.jsonl | lookup | lang | python | exact |
| lookups_shard1.jsonl | lookup | lang | rust | ws |
| lookups_shard1.jsonl | lookup | lang | swift | exact |
| lookups_shard1.jsonl | lookup | lang | typescript | exact |
| rate_card.xlsx | effective_from | region | ap-south-5 | local |
| rate_card.xlsx | effective_from | region | ap-southeast-6 | iso_z |
| rate_card.xlsx | effective_from | region | ca-north-8 | iso_z |
| rate_card.xlsx | effective_from | region | eu-central-2 | xl1900 |
| rate_card.xlsx | effective_from | region | eu-west-1 | local |
| rate_card.xlsx | effective_from | region | sa-east-7 | epoch |
| rate_card.xlsx | effective_from | region | us-central-4 | iso_z |
| rate_card.xlsx | effective_from | region | us-east-3 | utc_naive |
| rate_card.xlsx | micro_per_min | region | ap-south-5 | usd6 |
| rate_card.xlsx | micro_per_min | region | ap-southeast-6 | usd6 |
| rate_card.xlsx | micro_per_min | region | ca-north-8 | kusd9 |
| rate_card.xlsx | micro_per_min | region | eu-central-2 | eu6 |
| rate_card.xlsx | micro_per_min | region | eu-west-1 | eu6 |
| rate_card.xlsx | micro_per_min | region | sa-east-7 | eu6 |
| rate_card.xlsx | micro_per_min | region | us-central-4 | micro |
| rate_card.xlsx | micro_per_min | region | us-east-3 | usd6 |
| rate_card.xlsx | recorded_at | region | ap-south-5 | iso_z |
| rate_card.xlsx | recorded_at | region | ap-southeast-6 | iso_off |
| rate_card.xlsx | recorded_at | region | ca-north-8 | xl1900 |
| rate_card.xlsx | recorded_at | region | eu-central-2 | epoch_ms |
| rate_card.xlsx | recorded_at | region | eu-west-1 | epoch_ms |
| rate_card.xlsx | recorded_at | region | sa-east-7 | epoch_ms |
| rate_card.xlsx | recorded_at | region | us-central-4 | iso_z |
| rate_card.xlsx | recorded_at | region | us-east-3 | iso_z |
| shard_index.tsv | assigned_at | lang | cpp | iso_z |
| shard_index.tsv | assigned_at | lang | go | epoch_ms |
| shard_index.tsv | assigned_at | lang | java | iso_z |
| shard_index.tsv | assigned_at | lang | kotlin | epoch |
| shard_index.tsv | assigned_at | lang | python | epoch_ms |
| shard_index.tsv | assigned_at | lang | rust | epoch |
| shard_index.tsv | assigned_at | lang | swift | iso_z |
| shard_index.tsv | assigned_at | lang | typescript | epoch |
| shard_index.tsv | prefix | lang | cpp | ws |
| shard_index.tsv | prefix | lang | go | exact |
| shard_index.tsv | prefix | lang | java | upper |
| shard_index.tsv | prefix | lang | kotlin | ws |
| shard_index.tsv | prefix | lang | python | ws |
| shard_index.tsv | prefix | lang | rust | upper |
| shard_index.tsv | prefix | lang | swift | upper |
| shard_index.tsv | prefix | lang | typescript | exact |
| vendor_statement.xml | credit | region | ap-south-5 | usd6 |
| vendor_statement.xml | credit | region | ap-southeast-6 | micro |
| vendor_statement.xml | credit | region | ca-north-8 | kusd9 |
| vendor_statement.xml | credit | region | eu-central-2 | micro |
| vendor_statement.xml | credit | region | eu-west-1 | micro |
| vendor_statement.xml | credit | region | sa-east-7 | eu6 |
| vendor_statement.xml | credit | region | us-central-4 | usd6 |
| vendor_statement.xml | credit | region | us-east-3 | usd6 |
| vendor_statement.xml | line | region | ap-south-5 | ws |
| vendor_statement.xml | line | region | ap-southeast-6 | exact |
| vendor_statement.xml | line | region | ca-north-8 | ws |
| vendor_statement.xml | line | region | eu-central-2 | upper |
| vendor_statement.xml | line | region | eu-west-1 | upper |
| vendor_statement.xml | line | region | sa-east-7 | ws |
| vendor_statement.xml | line | region | us-central-4 | exact |
| vendor_statement.xml | line | region | us-east-3 | upper |
| vendor_statement.xml | runner | region | ap-south-5 | exact |
| vendor_statement.xml | runner | region | ap-southeast-6 | exact |
| vendor_statement.xml | runner | region | ca-north-8 | upper |
| vendor_statement.xml | runner | region | eu-central-2 | upper |
| vendor_statement.xml | runner | region | eu-west-1 | upper |
| vendor_statement.xml | runner | region | sa-east-7 | ws |
| vendor_statement.xml | runner | region | us-central-4 | upper |
| vendor_statement.xml | runner | region | us-east-3 | exact |
| audit_annex.pdf | control_sum | batch | B1 | plain |
| audit_annex.pdf | control_sum | batch | B10 | eu |
| audit_annex.pdf | control_sum | batch | B11 | plain |
| audit_annex.pdf | control_sum | batch | B12 | sep |
| audit_annex.pdf | control_sum | batch | B2 | sep |
| audit_annex.pdf | control_sum | batch | B3 | plain |
| audit_annex.pdf | control_sum | batch | B4 | sep |
| audit_annex.pdf | control_sum | batch | B5 | eu |
| audit_annex.pdf | control_sum | batch | B6 | plain |
| audit_annex.pdf | control_sum | batch | B7 | eu |
| audit_annex.pdf | control_sum | batch | B8 | eu |
| audit_annex.pdf | control_sum | batch | B9 | eu |
| audit_annex.pdf | records | batch | B1 | sep |
| audit_annex.pdf | records | batch | B10 | plain |
| audit_annex.pdf | records | batch | B11 | eu |
| audit_annex.pdf | records | batch | B12 | plain |
| audit_annex.pdf | records | batch | B2 | plain |
| audit_annex.pdf | records | batch | B3 | sep |
| audit_annex.pdf | records | batch | B4 | eu |
| audit_annex.pdf | records | batch | B5 | eu |
| audit_annex.pdf | records | batch | B6 | sep |
| audit_annex.pdf | records | batch | B7 | eu |
| audit_annex.pdf | records | batch | B8 | sep |
| audit_annex.pdf | records | batch | B9 | sep |

**Table: Column aliases**

| file | alias | column | from_record |
|---|---|---|---|
| action_keys.lock | action_v2 | action | 5655 |
| change_freeze.ics | dtstart_v2 | dtstart | 9056 |
| lookups_shard1.jsonl | lookup_v2 | lookup | 5666 |
| vendor_statement.xml | line_v2 | line | 5665 |

**Table: Source catalog**

| file | primary table | context | context link | control column |
|---|---|---|---|---|
| action_keys.lock | records | lang | target -> package_metadata.xml language | recorded |
| amendment_minutes.docx | Amendments | lang | job -> job register target -> package_metadata.xml language | ratified_on |
| approval_thread.mbox | message | lang | erratum -> errata_register.docx attempt -> job -> job register target -> language | decided_at |
| artifact_registry.db | artifacts | lang | target -> package_metadata.xml language | bytes |
| attempt_events.jsonl | records | lang | job -> job register target -> package_metadata.xml language | duration_ms |
| attempt_events_v3.jsonl | records | lang | job -> job register target -> package_metadata.xml language | duration_ms |
| change_freeze.ics | VEVENT | region | runner column | dtstart |
| clock_sync.txt | records | region | runner column | skew_ms |
| close_parameters.toml | reservation | region | runner column | day |
| cost_centers.csv | records | org | handle -> team_roster.xlsx Roster team -> org | effective_from |
| edges.csv | records | lang | child target -> package_metadata.xml language | declared_at |
| env_allowlist.json | observations | lang | action -> action_keys.lock target -> package_metadata.xml language | observed |
| errata_register.docx | Errata | lang | attempt -> the attempt's job -> job register target -> package_metadata.xml language | filed |
| evictions.log | records | lang | action -> action_keys.lock target -> package_metadata.xml language | ts |
| field_precedence.html | Job register | batch | batch column | opened |
| flaky_windows.tsv | records | lang | target -> package_metadata.xml language | from |
| fleet_north.log | records | lang | job -> job register target -> package_metadata.xml language | mono_end |
| fleet_policy.ini | runner | region | runner column | effective_from |
| fleet_south.log | records | lang | job -> job register target -> package_metadata.xml language | mono_end |
| gc_events.csv | records | lang | artifact -> artifact_registry.db target -> language | at |
| input_manifests.tsv | records | lang | action -> action_keys.lock target -> package_metadata.xml language | size |
| instance_classes.csv | records | region | sku -> fleet_policy.ini revision -> runner | listed_at |
| invoice_lines.xlsx | Lines | locale | vendor -> vendor_statement.xml locale | billed |
| invoice_restatement.csv | records | locale | batch column | restated |
| junit_results.xml | testcase | lang | attempt -> the attempt's job -> job register target -> package_metadata.xml language | time |
| lookups_archive.jsonl.gz | records | lang | action -> action_keys.lock target -> package_metadata.xml language | at |
| lookups_shard1.jsonl | records | lang | action -> action_keys.lock target -> package_metadata.xml language | bytes |
| lookups_shard2.jsonl | records | lang | action -> action_keys.lock target -> package_metadata.xml language | bytes |
| lookups_shard3.jsonl.gz | records | lang | action -> action_keys.lock target -> package_metadata.xml language | bytes |
| opening_balances.json | balances | batch | batch column | amount |
| owners_registry.txt | records | batch | batch column | seq |
| ownership_patterns_approved.tsv | records | batch | batch column | effective |
| package_metadata.xml | Package | batch | batch column | manifest_bytes |
| rate_card.xlsx | Rates | region | region column | micro_per_min |
| rate_card_final.xlsx | Final rates | region | region column | micro_per_min |
| rate_methodology.pdf | Billing granularity | batch | batch column | granularity_s |
| retry_policy.yaml | budgets | lang | job -> job register target -> package_metadata.xml language | budget |
| scope_rules.md | Target scope register | batch | batch column | reviewed |
| settlement_authority.md | Runner placements | batch | batch column | rev |
| settlement_ledger.db | postings | batch | batch column | amount |
| shard_index.tsv | records | lang | prefix -> the action whose key starts with it -> target -> language | assigned_at |
| targets.csv | records | lang | target -> package_metadata.xml language | registered_at |
| team_roster.xlsx | Roster | batch | batch column | effective_from |
| toolchain_pins.yaml | pins | lang | target -> package_metadata.xml language | pinned_at |
| toolchain_pins_resolved.json | resolved | lang | target -> package_metadata.xml language | resolved_at |
| usage_events.jsonl | records | lang | job -> job register target -> package_metadata.xml language | elapsed |
| usage_export_legacy.log | records | lang | attempt -> the attempt's job -> job register target -> package_metadata.xml language | elapsed |
| vendor_statement.xml | Line | region | runner column | credit |
| audit_annex.pdf | Block controls | batch | batch column | records |
| control_totals_draft.html | Draft controls | batch | batch column | records |
