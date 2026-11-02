# Attestation authority

`integrity_reports_central.jsonl` carries central verdicts against a unit and
revision. A row whose `verdict` is blank is a filing fault and is set aside before
the governing record is chosen. The governing central record clears the revision
when its verdict is `pass`. A verdict of `fail` does not clear it. A verdict of
`indeterminate` clears the revision for every channel except `stable`.

A unit and revision with no central record at all is not cleared.

## Delegated site authority

`qa_verdicts_site.csv` carries site verdicts. A site verdict replaces the central
verdict only when both of these hold.

* `delegation_grants.json` holds a governing grant with status `active` for that
  site and the unit's family.
* The site row's `effective_at` is strictly later than the `effective_at` of the
  governing central record.

The site that may speak for a unit is the unit's owning site as recorded in the
governing row of `unit_catalog.csv`. A verdict filed by any other site is
reference only, whatever grants that other site holds. A site verdict that
replaces the central verdict is then read by the same rules, including the rule
about `indeterminate`.

## Normative parameters

```
indeterminate_blocked_channel: stable
authority_site_field: owning_site
```
