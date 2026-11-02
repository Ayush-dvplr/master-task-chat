# Record shapes

## The records a season is read from

A season is read from nine tables and three documents, all in one directory:
`patch_calendar.csv`, `reagent_registry.csv`, `artifact_catalogue.csv`,
`recipe_editions.csv`, `workshop_registry.csv`, `smith_identity_events.csv`,
`crafting_ledger.csv`, `reagent_acquisitions.csv`, `vault_opening.csv`,
`requisitions.json`, `season_charter.json` and `council_rulings.json`. The last
holds the council's rulings for the year as three lists, `charge_rulings`
(`base_value`, `family_percent`, `grade_percent`, `scarcity_percent`,
`charge_ember`), `return_rulings` (`tier`, `committed_units`, `returned_units`)
and `scarcity_rulings` (`opening_units`, `acquired_units`, `called_for_units`,
`consumed_units`, `scarcity_ceiling`, `scarcity_index`); the register of season
conventions says what each ruling records.

## How every settled record is written

Each record is one JSON object in UTF-8, indented by two spaces, with `","`
after every item but the last and no trailing whitespace on any line, `": "`
after each key, non-ASCII characters written as themselves, keys in exactly the
order listed below, and one newline after the closing brace. Every count, unit
and ember figure is a whole number. Grades, tiers, ordinals and every other
numeric column are written as JSON numbers. Values listed as true or false are
JSON booleans. Lists of rows are in the order
stated for them.

## summary.json

- `season`: an object with `first_day`, `last_day` and `patch_count`.
- `workshops_in_scope`: the in-scope workshop identifiers, ascending.
- `guilds_in_scope`: the identifiers of the guilds that own an in-scope
  workshop, ascending.
- `entries_total`: the number of ledger entries.
- `entries_admitted`: the number of entries that settled.
- `entries_rejected`: the number that did not.
- `credited_salvages`: the number of salvage entries that settled.
- `uncredited_salvages`: the number of `UNCREDITED_SALVAGE` findings.
- `scarcity_index`: an object from each scarce reagent, ascending, to its index.
- `season_charge_ember`: the season's total charge.
- `allocated_units_total`: the units granted across every requisition.
- `conservation_residual`: the sum over reagents of the absolute residual of
  the season's conservation identity.

## vault_audit.json

- `reagents`: one row for every reagent in the registry, ascending by
  identifier, each with `reagent_id`, `grade`, `scarce` (true or false),
  `opening_units`, `acquired_units`, `returned_units`, `consumed_units`,
  `closing_units` and `scarcity_index` (0 for a reagent the registry does not
  mark scarce).

## reconciliation.json

- `patches`: one row per patch in ordinal order, each with `patch_id`,
  `ordinal`, `reagents` and `residual`. `reagents` holds one row for every
  reagent, ascending, each with `reagent_id`, `opening_units`, `acquired_units`,
  `returned_units`, `consumed_units`, `closing_units` and `residual`. A patch's
  `residual` is the sum of the absolute residuals of its rows.
- `season_residual`: the sum of the patch residuals.
- `charge_by_workshop`: an object from each in-scope workshop, ascending, to its
  charge.
- `charge_by_guild`: an object from each in-scope guild, ascending, to its
  charge.
- `charge_total`: the season's total charge.

## data_quality.json

- `findings`: one row per entry and code pair, in the order N3 states, each
  with `entry_id`, `code` and `detail`.
- `counts`: an object from each code the season recorded at least once,
  ascending, to the number of findings under it.

## allocation.json

- `pool_units`: the season pool.
- `assignments`: one row for every requisition, ascending by identifier, each
  with `req_id`, `workshop_id`, `reagent_id`, `allocated_units` and `served`
  (true when the grant is above nothing).
- `allocated_total`: the units granted in all.

## Workshop reports

Each is named `workshop_` followed by the workshop identifier and `.json`.

- `workshop_id`, `guild_id`, `charter_id`, `charter_tier`.
- `entries_admitted` and `entries_rejected`: the entries filed against the
  workshop that settled and that did not.
- `charge_ember`: the workshop's accrued settled charge.
- `cap_ember`: the charge cap of its charter tier.
- `cap_reached`: true when the workshop was closed under A4.
- `allocated_units`: the units granted to its requisitions.
- `smiths`: one row for every canonical smith the workshop reports under I5,
  ascending, each with `canonical_smith`, `admitted_forges`, `credited_salvages`
  and `charge_ember`.
- `reagent_flow`: one row for every reagent on a line of an entry the workshop
  settled, ascending, each with `reagent_id`, `consumed_units`,
  `returned_units` and `net_units` (consumed less returned).

## Guild reports

Each is named `guild_` followed by the guild identifier and `.json`.

- `guild_id`.
- `workshops`: the guild's in-scope workshops, ascending.
- `entries_admitted`, `charge_ember` and `allocated_units`: the sums over those
  workshops.
- `reagent_flow`: the workshops' `reagent_flow` rows added together per
  reagent, in the same shape and order.
