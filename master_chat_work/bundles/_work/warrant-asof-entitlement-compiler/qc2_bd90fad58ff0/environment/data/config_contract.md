# Configuration contract

`resolve-config` turns four layers into one flat configuration. `config_schema.json` names every key. A key whose `scope` is `global` appears once under its own name; a key whose scope is `profile` appears once per profile as `dev.<key>` and `prod.<key>`. The two anchor keys `as_of` and `recorded_cutoff` are separate (below).

## Layers

From lowest to highest:

1. `defaults.json`. A profile scoped key set here applies to both profiles.
2. `profiles.toml`, one table per profile.
3. `site_policy.ini`. `[global]` holds global keys, `[dev]` and `[prod]` hold profile keys. INI values are text: integers are written as digits, booleans as `true` or `false`, enums as their value.
4. `policy_change_journal.jsonl`, one change per line.

## Anchors

`as_of` and `recorded_cutoff` come only from the `[anchor]` section of `site_policy.ini` and are written to the configuration in UTC. A journal entry for either is rejected `anchor_key`.

## Journal

Journal entries are visible when their `recorded_at` is at or before `recorded_cutoff`. Each visible entry is checked in this order: an unreadable `effective_at` is `bad_timestamp`; a missing `value` field is `missing_field`; an anchor key is `anchor_key`; a key the schema does not produce is `unknown_key`; a non-null value of the wrong type or outside its bounds or enum is `out_of_bounds` (an integer key takes JSON integers only, a boolean key JSON booleans only). Rejected entries change nothing. Accepted entries whose `effective_at` is at or before `as_of` are applied in order of `effective_at`, ties by `seq`. A null value cancels every earlier applied journal entry for its key, leaving the key to the layers below and to later journal entries.

## Resolution

An `ordinary` key takes the value of the last applied journal entry still standing, else the highest layer that sets it. A `ceiling` key can only be tightened: it takes the smallest value among every layer that sets it and every applied journal entry still standing. A key no layer sets is left out.

The configuration is the flat JSON object of the two anchors and every resolved key.
