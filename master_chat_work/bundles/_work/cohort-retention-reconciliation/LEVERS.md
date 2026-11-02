# LEVERS cohort-retention-reconciliation

## v0 levers (reconstructed from tests/test_output.py fixtures and the real run)

Real run: claude-opus-5, Run 1, trajectory steps quoted by step_id. Local probe
(/tmp/crr_probe, rewardkit stubbed, setpriv dropped): the agent's own
derive_report.py passes all 12 program-run checks, so every lever below LEAKED.
The recorded 0.4235 tests score came only from the Errno 13 permission trap.

| id | rule (schema.md line) | reflex reading | checks | family | read at | self-check | verdict | why derivable |
|----|----|----|----|----|----|----|----|----|
| V0-1 | cleaning order: out-of-calendar, then dedup on raw (account, date, type), then fold, then drop excluded/unknown (52-60) | dedup after folding | merge_and_dedup, cleaning_drops | E | step 3 (view schema.md) | step 5 hand trace finds e024 dup, e025 out of calendar | LEAKED | numbered list at point of use; one-rule fixture |
| V0-2 | pre-cohort activity never counts (76-80) | count every activity event | pre_cohort | A | step 3 | step 5 "a005 e026 before cohort -> pre_cohort 1" | LEAKED | sentence next to the active definition; shipped e026 shows it |
| V0-3 | exclusion applies to resolved account (a901 -> a900) (30-31, 58) | check raw id only | exclusions_resolved | B | step 3 | step 5 drops e027, e028 via a901->a900 | LEAKED | rule stated at use; shipped a901 row |
| V0-4 | merge on/after effective_from, chained, latest effective_from wins (24-28) | fold unconditionally | merge_history | C | step 3 | steps 13-25 synthetic /tmp/alt extract with chained and overlapping merges | LEAKED | full rule text in one place; agent built its own test |
| V0-5 | minimum_value_cents for qualifying (43-45, 64-68) | ignore threshold (0 shipped) | minimum_value | A | step 3 | /tmp/alt uses minimum 500 | LEAKED | one key, one sentence |
| V0-6 | offset_zero_is_full flag adds residual (95-102) | omit | offset_zero | A | step 3 | /tmp/alt sets flag true, residual -1 | LEAKED | listed as "three residuals" |
| V0-7 | rates are reduced fraction strings, den 0 -> "0" (10-13) | float | exact_rate_formatting, cohorts_schema | E | step 3 | step 9 prints rates | LEAKED | explicit format block |
| V0-8 | survival is running minimum (82-84) | raw active/size | hidden_seeded, second_seeded | B | step 3 | step 5 hand survival | LEAKED | one line, plain |

Score effect in v0: 49 of 85 points sat on program-run checks; all lost to the
permission trap, none to a lever.

## Harden round 1 levers

Families per registry levers.json: A hidden composition, B dependent chain,
E stacked constraints, F error path / rejection. Set A + B + E + F, not copied
from another task (closest registry match: LV-EF-L7 every-condition, held).

| id | family | rule (where stated) | reflex reading | constructed hidden cases | checks a wrong reading fails | mutant tests score |
|----|----|----|----|----|----|----|
| CR-1 | A | rejection register lists EVERY reason true of the raw row tested alone (field named in schema.md Outputs; defined only in audit_policy.md "Rejection register") | one reason: the stage that removed the row | ooc+excluded legacy, ooc duplicate twin, good-then-malformed twin (duplicate+malformed), bad-date rows skip date-needing reasons | register_lists_every_reason 3, hidden_rejection_register 5 | 0.850 |
| CR-2 | B | weight from the plan in force on the event date for the resolved account, latest plan_history row on/before date, later row on tie (audit_policy.md "Plans"); schema.md says "its account's plan", accounts.csv has a plan column (decoy) | accounts.csv plan; or strictly after; or raw account | boundary row on a purchase date, adjacent tie pair, row for a merged-away account, row after every event | plan_in_force_on_the_event_date 3, hidden_revenue 5, hidden_segments 5, hidden_per_cohort_documents 3, rates_are_exact_signed_fractions 1 (weighted share) | 0.700 (accounts plan), 0.700 (strict after) |
| CR-3 | E | "A purchase adds its value_cents; every other revenue event type subtracts it." (schema.md Revenue, scope by omission) | only refund subtracts, or all add | revenue types chargeback, credit_note, reversal never seen in shipped data | other_revenue_types_subtract 3, hidden_revenue 5, hidden_segments 5, hidden_reconciliation 3, hidden_per_cohort_documents 3 | 0.550 (all add) |
| CR-4 | F | malformed = date not a real 4-2-2 digit YYYY-MM-DD, or value_cents not a non-empty digit run; dropped first and counted (schema.md Cleaning step 1) | date.fromisoformat / int() | 20260110, 2026-1-15, +0, " 9900", 1_000, Feb 30, month 13, 12.5, -300, 1e3, n/a, ""; malformed early qualifier that would move a cohort | malformed_rows_are_dropped_first 3, hidden_cohorts 5, hidden_retention 5, hidden_survival 3, hidden_data_quality_counts 3 | 0.400 (fromisoformat), 0.450 (int-like) |
| CR-5 | B | dedup among rows remaining after steps 1-2, first kept, raw key; each removed row counted once at its removing step (schema.md Cleaning) | dedup over every earlier raw row | ooc and malformed twins of good rows | hidden_data_quality_counts 3, hidden_rejection_register 5, hidden documents | 0.417 |

Retained from v0 (now graded in hidden whole documents, not alone): V0-2
pre-cohort (pre_cohort_activity_stays_out_of_the_matrix 1), V0-3/V0-4 merges
(merge_history_by_event_date 3), V0-5 minimum value and V0-6 offset-zero flag
(hidden seeds 0x7C4D2E9B015F min 1200; 0x3B90E1F4A7 flag true), V0-7 rates
(rates_are_exact_signed_fractions 1), V0-8 survival (hidden_survival 3).

Check to lever map (positive 60): artifact_set 1 shipped-only; hidden_cohorts 5
CR-4 V0-4 V0-5; hidden_retention 5 CR-4 V0-2; hidden_survival 3 V0-8;
hidden_revenue 5 CR-2 CR-3; hidden_segments 5 CR-2 CR-3; hidden_data_quality_counts
3 CR-4 CR-5; hidden_rejection_register 5 CR-1 CR-5; hidden_reconciliation 3 CR-3
V0-6; hidden_study_audit 1; hidden_per_cohort_documents 3 CR-2 CR-3;
hidden_serialization_is_canonical 1 V0-7; deterministic_rerun 3; fixtures:
register_lists_every_reason 3 CR-1, plan_in_force_on_the_event_date 3 CR-2,
other_revenue_types_subtract 3 CR-3, malformed_rows_are_dropped_first 3 CR-4,
merge_history_by_event_date 3 V0-4, pre_cohort 1 V0-2, rates 1 V0-7.
Rule-isolating 17/60 = 28.3%; shipped-data-only 1/60 = 1.7%.

# Harden round 2 levers (board 7cbd9f5, 23 Oct). CR-1..CR-5 and V0-1..V0-8 all LEAKED on a2 and are retained only as drift; their giveaways were removed (audit_policy "not only the one for the cleaning step", schema "so the survival series never increases", "which shows how far offset zero falls short", "contributes nothing to them").

## CR2-L1 green control, wrong answer (family D)
- Rule text: `environment/data/extract_manifest.json` `note` (data_rows = lines after header; value_cents_sum over values read with surrounding spaces removed, non-digit adds nothing); `schema.md:63-64` (manifest pointer), `schema.md:166-171` (`control_mismatches`), `schema.md:134-136` (control value residual).
- Reflex reading: trust the green control; or count the value sum from the program's own strict parse (false `events.csv:value_cents_sum` on the shipped extract because of e035).
- Hidden cases: every hidden study ships 3 faulty manifest figures in 3 files, written unsorted; one is always the events value sum set to the strictly parsed sum (agrees with the unstripped reading, disagrees under the note), the others drawn from accounts/events/calendar/plan_history/merges data_rows. (r3: L1a loss 11 -> 11 after compensation.)
- Checks the wrong reading fails: manifest_figures_follow_its_note, hidden_data_quality, hidden_reconciliation.

## CR2-L2 identifiers vs strict fields, make-it-match repair (new: control-fitting; strict-vs-normalise F)
- Rule text: `schema.md:18-25` (Identifiers: account ids in every file, event types incl. rule lists, plan names, segment codes compared trimmed + lower-cased, written in that form; every other field read exactly as written); `schema.md:71-74` (malformed value/date as a bare property); `schema.md:77-80` and `audit_policy.md:31-32` (duplicate key on the id before merging).
- Reflex readings: (a) normalise only events.csv ids; (b) raw-text duplicate key; (c) trim every field in the loader, which is also the repair that makes the strict-parse control match on shipped data; (d) no normalisation (a2).
- Shipped separating row (bare property only, W5): e035 value ` 4500`. Hidden cases: spaced/upper-cased ids in accounts.csv (3 rows), merges (2 cells), exclusions (barred upper-cased, optional spaced twin), plan_history id and plan, accounts segment and plan, segments.csv code, rule lists (`Signup`-style, ` session`, title-cased subtracting type); ~1 in 7 event ids and types varied; a below-minimum qualifier with an upper-cased later repeat that clears the minimum; a spaced early qualifying date.
- Checks failed: every hidden_* document, serialization, determinism, identifiers_match_across_files, spaced_values_and_dates_are_malformed (trim), mutation_minimum_moves_cohort_sizes.

## CR2-L3 refundable balance ledger (families C + B)
- Rule text: `schema.md:115-125` (book one event at a time in cleaned order; per resolved-account balance; purchase adds; other revenue types book minus min(value, balance); rest unhonored); `schema.md:88` (cleaned order date, resolved account, event type).
- Reflex readings: uncapped subtraction (a2); balance keyed on the raw id; file order.
- Hidden cases: a vault account with a subtraction before any purchase, a same-day chargeback/credit_note that sorts before purchase, and a later subtraction above the balance; a legacy id with a pre-merge purchase, a post-merge purchase and a later refund larger than the post-merge purchase (draws on the heir's balance). Shipped data never separates (a003 refund is covered). r3 side rows add an account with an undrained same-day purchase and refund (refund sorts first, unhonored).
- Checks failed: hidden_revenue, hidden_segments, hidden_per_cohort_documents, balance_belongs_to_the_resolved_account.

## CR2-L4 segment weight override in another file (families A + E)
- Rule text: `audit_policy.md:18-20` (weight_override of the resolved account's segment replaces the plan weight); `schema.md:54` (column), `schema.md:121-123` ("weight of the plan in force", the default), `schema.md:185-188` (`weight_overrides` echo).
- Reflex readings: ignore the override; take the segment of the raw (merged-away) id.
- Hidden cases: heir segment always overridden (10-19), the merged legacy id sits in a different, non-overridden segment; sometimes a second segment overridden. Shipped overrides blank.
- Checks failed: hidden_revenue, hidden_segments, hidden_study_audit, hidden_per_cohort_documents, segment_override_follows_the_resolved_account, mutation_override_moves_only_weighted_revenue.

## Measured composite (final weights): a2 program 0.0563, S2 0.0563, S4 (L2a + L2b + L3b + L4b) 0.1690, stub 0.0141, oracle 1.0. S3: L1a 0.85, L1b 0.89, L2none 0.24, L2a 0.24, L2b 0.46, L2c 0.25, L3a 0.75, L3b 0.75, L4a 0.70, L4b 0.77.

## P12 r2 (board f6164ef) lever effects
- CR2-L1 none; CR2-L3 none; CR2-L4 none.
- CR2-L2 harder: hidden studies now add a same-day purchase pair from two pre-merge ids of one resolved account (a resolved-key duplicate reading drops one) and a repeated in-calendar row for the excluded account (stage order: the repeat is a duplicate, not excluded). Measured tests channel: resolved-key mutant 0.7418, exclusion-first mutant 0.9296 (both 1.0 before).
- No change from the solve.py date parse (JD-7) or the deleted final-reply line (AL-2): neither touches a lever rule.
