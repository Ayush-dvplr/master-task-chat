# 92dd0b24-4f27-5ec2-9084-7bcc527d2e05

The circuit office needs the open slate adjudicated and recorded. The published corpus sits in `/app/data`, the arbiter service in `/app/service/arbiter.py` and its console in `/app/service/arbiterctl.py`. Start the arbiter against `/app/data/registry_seed.json` before recording anything.

`/app/data/slate_contract.md` is the single source of truth for admission, identity, timing, cards, restrictions, carry and verdicts. `/app/data/api_contract.md` is the single source of truth for the protocol. `/app/data/source_index.md` names every feed with its producer and field order. `/app/data/slate_window.ini` fixes the slate id, the legality cutoff and the precedence cutover, and `/app/data/scenario_brief.ini` fixes the three scenarios. `/app/data/legacy_floor_runbook.md` records older floor practice and `/app/data/rules_committee_notes.md` records later errata; where either disagrees with the two contracts, the contracts govern. Two rules in the slate contract are settled by the adjudication observations and by nothing else in the corpus. Nothing here tells you which feeds carry defects or how many; finding that out is the task.

Write seven files. `/app/out/report.json` holds `slate_id`, `cutoff`, `entry_count` and `entries`, ordered by effective instant, then recorded instant, then submission id, with every entry holding exactly these keys:

```
submission_id player_id format venue effective_at recorded_at verdict
reason_code points_total copy_breach_count carry_before carry_after tier
governing_source channel
```

Instants are `YYYY-MM-DDTHH:MM:SSZ` in UTC, `points_total` and the carries are integers, `points_total` is in centipoints, and `reason_code` is JSON null when the verdict carries no reason.

`/app/out/summary.json` holds `slate_id`, `entry_count`, `verdict_counts`, `reason_counts`, `source_counts`, `tier_counts`, `points_total_sum`, `copy_breach_total`, `carry_cap_hits`, `redirected_entries`, `materialized_entry_count`, `distinct_canonical_cards` and `rejected_events`. The four count maps carry one key per value that occurs, and a null reason appears under the key `none`.

`/app/out/transcript_summary.json` holds `slate_id`, `pages_walked`, `empty_pages`, `preseeded_entries`, `deferred_operations`, `conflicts_met`, `conflict_entries`, `console_operations`, `api_operations`, `refusals`, `journal_seq` and `digest`, where `conflict_entries` is sorted, `refusals` maps each refusal code that occurred to its count, and `preseeded_entries` counts the listed entries the slate also names.

`/app/out/final_state.json` is the state snapshot read back from the arbiter once recording is complete, with its keys unchanged.

`/app/out/scenario_alpha.json`, `/app/out/scenario_beta.json` and `/app/out/scenario_mode.json` each hold `basis`, `entry_count`, `verdict_counts`, `tier_counts`, `points_total_sum`, `changed` and `changed_count`, where `basis` is the token from the brief and `changed` is the sorted list of submission ids whose verdict differs from the baseline report, counting a submission id that appears in only one of the two as a difference.

The verdicts are `seated`, `amended`, `flagged`, `barred` and `unresolved`. The reason codes are `charge_cycle`, `chain_cycle`, `unknown_printing`, `no_prior_list`, `tier_bar`, `card_barred`, `copy_breach`, `points_over` and null. The tiers are `clear`, `caution`, `probation` and `barred`. The governing sources are `rider`, `global`, `addendum` and `base`. The formats are `classic`, `singleton` and `relic`. The channels are `api` and `console`. Use no token outside these sets.

Every entry the slate names passes through the arbiter, and a pre-seeded entry the slate does not name stays in the state the seed gave it. Send every operation through the service, take the sequence numbers, the refusal totals and the digest from the service rather than from your own bookkeeping, and leave `/app/data` exactly as shipped. Write nothing at the seven output paths other than those files, and leave no partial file behind on an error path.

An artifact counts only when every value in it is exact, so a near miss earns nothing there.

Close with a message that states, each labelled and each absent from all seven files: how many submissions in the whole season carry no admitted intake receipt; how many submissions are held by an entrant other than the one the handle assignment alone would name; how many deck lines in the governing lists of the admitted submissions name a printing that no admitted registry row matches; how many canonical keys lose their identity to an admitted reprint link in the formats the slate uses, as at the published close of the open stage; how many reprint links the corpus withdraws with the token their recorded instant column carries in place of a date; how many restriction revisions are retracted among those otherwise admitted; how many rider rows that their own instants would otherwise admit are turned away because their authorising judge held too low a rank; how many submissions carry an adjudication observation that disagrees with another observation of the same submission; how many standing occurrences the open stage window admits and how many of those an exception suppresses; how many accepted amendments that the legality cutoff admits are outranked by a higher accepted version of the same submission; and how many submissions fall in no governing stage window. Where one of these counts is over submissions, it covers every submission the feeds name for the season, whether a later event withdrew or superseded it or not. Label each count with the feeds you read it from. State in the same message which two conventions you settled from the observations, which reading you chose for each, and what in the observations settled it.

This machine has no network. Work only from the shipped corpus and the Python standard library, and do no online search for a published solution. You have 12600 seconds to complete this task.
