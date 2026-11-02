# Experiment readout analysis handbook, revision 8

This handbook is the authority for how an experiment portfolio readout is computed.
Where a saved readout query (`readout_query_pack.md`), a circulated calendar
(`readout_calendar.yaml`), a draft digest (`stats_digest_draft.txt`), an announcement
(`allocation_announce_sep.txt`), a cache (`exposure_rollup_cache.jsonl`), a snapshot
(`fx_rates_snapshot.json`), a watchlist (`bot_watchlist.txt`), a dashboard export
(`metric_dashboard_export.csv`), a ticket log (`analyst_tickets.ndjson`) or the
published readout (`readout_published.csv`) disagrees with this handbook, the
statistics governance memo (`stats_governance_memo_w26.pdf`) or the experiment workbook
(`experiment_workbook_w26.xlsx`), those three win and the other material is wrong.
Sections are referred to elsewhere as H1, H2 and so on.

## H1. Identifiers

1. Exposure ids, order ids, refund ids and unit tokens are compared after removing
   leading and trailing whitespace (and quotes left by loosely written YAML) and
   converting to upper case. Every such id written to an output uses that form.
2. Experiment tokens are mapped to a canonical experiment code through the
   `experiments` list of `experiment_aliases.yaml` (`alias` to `canonical`, aliases
   compared per H1.1). A token that is not an alias is used as it is, per H1.1.
3. Variant tokens are mapped to an arm through the `variants` list of
   `experiment_aliases.yaml`: an entry gives the canonical `experiment`, a `variant`
   spelling and the `arm`. Spellings are compared after stripping whitespace and quotes,
   case insensitively, and only within the entry's own experiment: the same spelling
   can name different arms in different experiments. An exposure whose variant has no
   entry for its experiment is an unmapped exposure (H3.4).
4. Metric codes are compared case insensitively and written in lower case. Currency
   codes and owner team names are compared case insensitively after stripping
   whitespace; currencies are written in upper case, teams in lower case.
5. `identity_links.psv` maps a `from_id` to the id it was `linked_to`, effective from
   00:00:00 UTC of its `linked_on` date onwards (a link dated on day D is in effect at
   every instant at or after D 00:00:00Z and at no earlier instant). A token is
   resolved at an instant t by a walk: start at the token; while the current id is the
   `from_id` of a link in effect at t, step to that link's target. If a step would
   reach an id already visited on this walk, the ledger has a cycle: the walk stops
   before that step, and the resolved id is the smallest id (plain string comparison)
   among the ids of the cycle, that is the ids from the first visit of the repeated id
   to the current id. The hop count is the number of steps taken. The resolved id is
   the unit. Each exposure is resolved at its own exposure time and each order at its
   own placed time; tokens of the profile's `internal_units` list and of memo Table
   U-1 are resolved at `data_cutoff_utc`. Ids are ordered by plain string comparison.

   Worked example (toy ids): links `A|B|2026-03-01`, `B|C|2026-03-10`,
   `C|B|2026-03-20`, `E|F|2026-05-01`. At 2026-03-05T12:00:00Z the token A walks A to
   B and stops (B's link is not yet in effect): unit B, 1 hop. At
   2026-03-15T00:00:00Z: A to B to C, and C's link is not yet in effect: unit C,
   2 hops. At 2026-04-01T00:00:00Z: A to B to C, and the next step would reach B
   again, so the cycle is {B, C}: unit B, 2 hops. At 2026-04-30T23:59:59Z the token E
   is unit E with 0 hops; at 2026-05-01T00:00:00Z it is unit F with 1 hop.

## H2. Which files are feeds

Only the files listed under `shards` in `ingest_catalog_w26.json` are feeds. A file that
looks like an exposure or order export but is not listed is not a feed. Each shard entry
names its `stream` (`exposure` or `order`), its `layout` (record shapes in
`feed_layouts.md`), its `ts_convention`, its `status_codes` map and a `fields` map from
where each field sits in the layout to what it means; order shards also name an
`amount_unit`.

1. `status_codes` maps the status code a layout writes to `LIVE` or `VOID` (exposures)
   and to `PLACED` or `CANCELLED` (orders). Codes are compared after stripping
   whitespace, case sensitively.
2. `amount_unit` is `minor` (an integer count of the currency's minor unit) or `major`
   (a decimal amount in the currency's major unit). A major amount is converted to minor
   units exactly by multiplying by 10 to the power of the currency's `minor_units` in
   the `Currencies` sheet of the experiment workbook (0 for JPY, 3 for KWD, 2 for the
   others). Amounts are never rounded at this step.
3. Timestamp conventions:
   - `iso_z`: `YYYY-MM-DDTHH:MM:SSZ`, UTC.
   - `iso_offset`: ISO 8601 with an explicit numeric offset; convert to UTC.
   - `epoch_s`: integer seconds since 1970-01-01T00:00:00Z.
   - `epoch_ms`: integer milliseconds since 1970-01-01T00:00:00Z; the sub-second part
     is dropped.
   - `compact_utc`: `YYYYMMDDHHMMSS`, UTC.
   - `local_experiment`: wall-clock date and time with no offset, at the fixed UTC
     offset of the row's own canonical experiment, taken from the `Experiments` sheet.
   - `local_reporting`: wall-clock date and time with no offset, at `reporting_offset`
     of the analysis profile.
   Offsets are fixed; there is no daylight saving anywhere.

## H3. Live records

1. Within each stream, every data row of every listed shard is read. Rows with the same
   id (H1.1) are versions of one record, whichever shard they come from.
2. The version with the largest revision wins. Only then is the winner's status looked
   at: a record whose winning version is VOID (exposures) or CANCELLED (orders) is not
   live, even if an older version was live. A losing version is a dropped duplicate.
3. For lineage, a row is `kept` when it is the winning version of a live record.
4. A live exposure is mapped to its canonical experiment (H1.2) and arm (H1.3). Live
   exposures of experiments that are not in scope (H6) are out of scope; live
   exposures whose variant is unmapped are dropped. Neither takes any further part.

## H4. Units and eligibility

1. A unit is registered when its resolved id appears as `unit_id` of
   `unit_registry_main.csv` or as `UNIT` of `unit_registry_legacy.tsv`. Registry ids
   are compared per H1.1 and are not resolved through the link ledger; a registry id
   that is the `from_id` of a link in effect at `data_cutoff_utc` is a retired account
   and is ignored. When an id is
   in both registries, the main registry row wins.
2. `account_type` (main) and `AccountType` (legacy) are `human`, `bot`, `internal` or
   `test`, compared case insensitively after stripping whitespace.
3. Table U-1 of the memo rules on individual units (tokens resolved per H1.5). Only
   rulings with status IN FORCE count. EXCLUDE removes the unit from every experiment.
   REINSTATE makes the unit's account type `human`.
4. A unit's exclusion reason is the first that applies, in this order:
   `UNREGISTERED`; `RULING_EXCLUDED` (U-1 EXCLUDE); `INTERNAL_LIST` (the resolved unit
   is on the `internal_units` list of the profile); `BOT`, `INTERNAL` or `TEST` (the
   account type after U-1 REINSTATE is not `human`). A unit with none is eligible.

## H5. Experiments, windows and arms

1. The `Experiments` sheet of the workbook gives each experiment's `tz_offset`, its
   analysis window `start_local` to `end_local` (wall clock at that offset), its
   `primary_metric` and its `owner_team`. The window is half open: a time `t` is in the window when
   `start <= t < end`.
2. Table X-1 of the memo rules on windows. Only rulings with status IN FORCE count.
   EXTENDED and SHORTENED each replace `end_local` by `revised_end_local`. ABORTED means the experiment
   is not analysed: it has no participants, no metrics and no tests, and each of its
   treatment arms gets the decision `ABORTED`. CONFIRMED changes nothing.
3. The `Allocation` sheet gives each arm's `role` (`control`, `treatment` or
   `holdout`) and its planned `weight_pct` (percent of enrolled units, holdout
   included). Every experiment has exactly one control arm.

## H6. Scope

The experiments in scope are those listed under `experiments_in_scope` of
`analysis_profile_w26.yml` (tokens mapped per H1.2). Only in-scope experiments that are
not ABORTED are analysed.

## H7. Participants

1. For an analysed experiment, a unit's exposures are its live, in-scope, mapped
   exposures of that experiment whose time is before the window end, each attributed
   to the unit its token resolves to at the exposure's own time (H1.5). Exposures at
   or after the end are ignored altogether. A unit with at least one such exposure is a
   participant candidate.
2. A candidate's reason, the first that applies: its eligibility reason (H4.4);
   `CROSSOVER` (its exposures carry more than one arm); `PRE_START` (its earliest
   exposure is before the window start). A candidate with none is a participant.
3. A participant's arm is the single arm of its exposures and its first exposure `fe`
   is the earliest of their times.

## H8. Orders, refunds and valuation

1. A live order belongs to the unit its customer token resolves to at the order's
   placed time (H1.5). Orders placed at or after `data_cutoff_utc` of the profile are
   ignored.
2. The refund journal has two halves, `refund_journal.jsonl` and
   `refund_journal_late.xml`. They form one journal, applied in ascending `seq` order.
   An entry is a refund or a reversal (its `kind`, compared case insensitively; an
   entry with no `kind` is a refund). Only entries whose status is `POSTED`, compared
   case insensitively, are applied. Every applied entry has exactly one outcome,
   checked in this order:
   - `AFTER_CUTOFF`: `posted_utc` is at or after `data_cutoff_utc`; no effect.
   - `NO_ORDER`: no live or cancelled order has that order id; no effect.
   - `ORDER_CANCELLED`: the order is not live; no effect.
   - a reversal is `REVERSED` when its refund id currently holds an amount: that
     amount is withdrawn and the refund id no longer holds one. Otherwise the reversal
     is `NOTHING_TO_REVERSE` and has no effect. A reversal's own amount is never used.
   - a refund is `REPLACED` when its refund id currently holds an amount: that amount
     is replaced by this entry's amount. Otherwise it is `APPLIED`: the refund id now
     holds this entry's amount. A refund id whose amount was reversed holds nothing,
     so a later refund with that id is `APPLIED` again.
   An order's refunds are the sum of the amounts its refund ids hold after the whole
   journal is applied.

   Worked example (toy ids, all POSTED, all before the cutoff, live order O1):
   seq 10 refund R1 O1 500 is APPLIED (R1 holds 500); seq 11 refund R1 O1 300 is
   REPLACED (R1 holds 300); seq 12 reversal R1 O1 500 is REVERSED (R1 holds nothing);
   seq 13 reversal R1 O1 300 is NOTHING_TO_REVERSE; seq 14 refund R1 O1 200 is
   APPLIED. O1's refunds are 200.
3. An order's net amount is its amount in minor units less its refunds, floored at 0.
   Its refunded amount is its amount less its net amount.
4. Valuation uses the FX sheet of the workbook named by `fx_sheet` of the profile; the
   other FX sheet is a different release and is not used. For a currency, the fixing
   used is the latest row of that currency on or before the order's UTC calendar date,
   and `fx_date` is that row's date. A `USD_PER_UNIT` rate is US dollars per currency
   unit; a `UNIT_PER_USD` rate is currency units per US dollar; a `UNIT_PER_EUR` rate
   is currency units per euro, and such an amount reaches US dollars through EUR: it
   is divided by its own rate and multiplied by the EUR rate, where the EUR fixing is
   chosen by the same latest-on-or-before rule for the same order date. USD amounts
   have rate 1 and need no FX row. The net and refunded amounts are each converted to
   US dollars from their exact major-unit amount and the exact rates, and the exact
   result is rounded half to even to six decimals (whole micro-dollars). This rounding
   is the only rounding before statistics; every later money figure is an exact sum of
   these micro-dollar values.

   Worked example (toy rates): an order of 1234 minor units of a two-digit currency
   quoted UNIT_PER_EUR 0.9500, with a USD_PER_UNIT EUR fixing of 1.1000, is worth
   12.34 / 0.95 x 1.10 = 14.288421052... US dollars, written 14.288421.

## H9. Metrics

1. The metric registry is the workbook sheet named by `registry_version` of the
   profile; a sheet whose name starts with `DRAFT_` was never adopted. Each `METRIC`
   row gives `kind` (`binary`, `mean` or `ratio`), `attribution_days`, `winsor_pct`,
   `cuped`, `covariate`, `role`, `higher_is_better`, `numerator` and `denominator`
   (`-` means not applicable).
2. Table A-1 of the memo amends the registry per experiment and metric. Only amendments
   with status IN FORCE count. Amendments whose experiment is `ALL` apply to every
   experiment first; amendments naming an experiment apply after them; within each
   group they apply in ascending amendment id order, so the last one applied to a field
   wins. Table A-0 is superseded and has no effect.
3. For a participant with first exposure `fe`, a metric's outcome window is
   `[fe, fe + attribution_days days)` and the pre-period is
   `[fe - pre_period_days days, fe)` (`pre_period_days` of the profile). A participant
   counts for a metric only when `fe + attribution_days days <= data_cutoff_utc`.
4. Per-participant values over a window, from the orders of that unit placed in it:
   - `conv7`, `pre_conv`: 1 if at least one order has a net amount above 0, else 0.
   - `rev14`, `pre_rev`: the sum of the orders' USD net values.
   - `ord14`, `pre_ord`: the number of orders with a net amount above 0.
   - `rfd14`: the sum of the orders' USD refunded values.
   A metric's own value uses its outcome window; its covariate uses the pre-period.
5. A ratio metric (`aov14`) is the ratio of the sums of its numerator and denominator
   metrics' per-participant values, both computed over the ratio metric's own outcome
   window and counted under its own maturity rule; numerator and denominator are not
   winsorized or adjusted.

## H10. Winsorization and CUPED

1. The analysed arms of an experiment are its control and treatment arms; holdout
   arms are never analysed.
2. A mean metric with a `winsor_pct` is winsorized: over the participants of all
   analysed arms that count for the metric (pooled, not per arm), sort the values
   ascending and take the nearest-rank cap, the value at 1-based position
   `ceil(winsor_pct / 100 x n)`. Values above the cap are replaced by the cap. When the
   metric is CUPED adjusted, its covariate is winsorized the same way with its own cap
   at the same `winsor_pct` over the same participants.
3. A metric with `cuped` true and a covariate is adjusted: the exact
   `cov(Y, X) / var(X)` over the same pooled participants (0 when `var(X)` is 0) is
   rounded half to even to six decimals, and that rounded value is theta. Then
   `Y_adj = Y - theta x (X - mean(X))` with `mean(X)` the exact pooled mean. Every
   figure that uses theta (adjusted means, variances, variance reduction) uses the
   rounded theta. Without CUPED, `Y_adj = Y`. Example: an exact ratio of
   0.12345650 gives theta 0.123456, and 0.12345750 gives 0.123458.
4. A binary metric is never winsorized.

## H11. Tests

1. For every analysed experiment, every treatment arm is compared with the control
   arm on every registry metric. Variances are sample variances (denominator n - 1).
2. Mean and binary metrics: `diff = mean_t(Y_adj) - mean_c(Y_adj)` and
   `se = sqrt(var_t(Y_adj) / n_t + var_c(Y_adj) / n_c)` (unpooled).
3. Ratio metrics: per arm `R = sum(y) / sum(x)` with the delta-method variance
   `(1/n) x (s_yy / mx^2 - 2 x my x s_xy / mx^3 + my^2 x s_xx / mx^4)`, where `mx`,
   `my` are the arm means of x and y and `s` are sample (co)variances;
   `diff = R_t - R_c` and `se = sqrt(V_t + V_c)`.
4. `z = diff / se`; the two-sided p-value is `erfc(|z| / sqrt(2))`; the confidence
   interval is `diff +- z_crit x se` with `z_crit` the standard normal quantile at
   `1 - alpha_two_sided / 2`. The relative lift is `100 x diff / base` and the lift
   interval is `100 x ci / base`, where `base` is the control arm's mean of the
   winsorized but unadjusted value (`R_c` for a ratio metric).
5. Decision parameters (`alpha_two_sided`, `bh_q`, `srm_alpha`, guardrail margins)
   are Table P-1 of the memo. Table P-0 is withdrawn.

## H12. Sample ratio mismatch

For every analysed experiment, the observed count of each arm (holdout included) is its
number of participants (H7, before the maturity rule of H9.3). The expected count is
`N x weight_pct / 100` with `N` the total over the arms. `chi2 = sum((o - e)^2 / e)`
with `k - 1` degrees of freedom for `k` arms; the p-value is the upper tail of the
chi-square distribution: `erfc(sqrt(chi2 / 2))` for one degree of freedom,
`exp(-chi2 / 2)` for two, and
`erfc(sqrt(chi2 / 2)) + sqrt(2 x chi2 / pi) x exp(-chi2 / 2)` for three. The
experiment fails the check when the p-value is below `srm_alpha`. Example: chi2 = 2
with three degrees of freedom gives 1.572992e-01 + 4.151075e-01 = 5.724067e-01.

## H13. Multiple testing and decisions

1. The primary family holds the primary-metric test of every treatment arm of every
   analysed experiment that passes the sample ratio check. Benjamini-Hochberg:
   order the family by p-value ascending (ties by experiment then arm), and for rank
   `i` of `m` set `q_i = min over j >= i of min(1, m x p_j / j)`. A primary test is
   significant when `q <= bh_q`. Every other test is significant when `p < alpha`.
2. A guardrail metric (registry `role` guardrail) is breached when its test has
   `p < alpha_two_sided`, its diff is in the worse direction (below 0 for a
   higher-is-better metric, above 0 otherwise) and its relative lift is beyond the
   margin `M = guardrail_margin_pct.<metric>` (below `-M`, or above `M` otherwise).
   Guardrail tests never enter the primary family.
3. First-pass decision of each treatment arm, the first that applies: `ABORTED` (H5.2);
   `INVALID_SRM` (H12); `NO_SHIP_GUARDRAIL` (any guardrail breached); `SHIP` (primary
   significant with diff in the better direction); `NO_SHIP` (primary significant in
   the other direction); `INCONCLUSIVE`.
4. A sample-ratio failure does not stop the experiment's tests from being computed and
   written; only its primary tests leave the family and carry no q-value.
5. Ship capacity. Table C-1 of the memo gives `max_ship` per owner team (Table C-0 is
   withdrawn). After the first pass, the arms decided SHIP are grouped by the
   `owner_team` of their experiment. When a team listed in C-1 has more SHIP arms than
   its `max_ship`, its SHIP arms are ranked by the q-value of their primary test
   (smallest first; equal q-values are ordered by the text `EXPERIMENT/ARM` in plain
   string order, for example `EXP-1/TREAT_A` before `EXP-2/TREAT_A`) and the arms ranked after the
   first `max_ship` become `SHIP_DEFERRED`. A team that C-1 does not list has no
   limit; `max_ship` 0 defers every SHIP arm of that team. The decision written for
   every arm is the decision after this pass.
