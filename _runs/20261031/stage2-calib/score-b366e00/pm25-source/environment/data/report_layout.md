# Report layout

A run over one extract writes nine reports, in this order: `summary.json`, `policy_audit.json`,
`data_quality.json`, `region_North.json`, `region_South.json`, `region_West.json`,
`region_East.json`, `segment_commercial.json` and `segment_public.json`. The four region reports are
the district rollups and the two segment reports are the operator rollups of the monitoring
standard. Every report is written on every run.

## Bytes of a report

Each report is one JSON object written in UTF-8, in the form Python's `json` module produces with
sorted keys and an indent of two spaces, followed by one line feed:

- every object member and list item on its own line, indented two spaces per level of nesting;
- object keys in sorted order, each followed by a colon and one space;
- a comma at the end of every member or item line except the last of its object or list;
- an empty object written `{}` and an empty list written `[]`;
- text written with double quotes, every character outside printable ASCII written as a `\u`
  escape;
- whole numbers written in decimal with no leading zeros, `true`, `false` and `null` written as
  such, and no other number forms.

Lists are in the order this document gives. A key marked "or null" holds `null` when the value it
names does not exist.

## Standard output

While it writes the reports, the program prints one line per report to standard output, in the
order above: the report's file name, one space, and the number of bytes written to that report.
It prints nothing else to standard output.

## `summary.json`

- `report_id`, `first_day`: text, copied from the extract manifest.
- `days`: whole number, copied from the extract manifest.
- `card_rows`: whole number, the rows of the card readings file.
- `valid_readings`: whole number, the valid readings.
- `valid_hours`: whole number, the valid hours over all sites.
- `valid_days`: whole number, the valid days over all sites.
- `exceedance_days`: whole number, the exceedance days over all sites.
- `site_status_counts`: object with the keys `attainment`, `incomplete` and `nonattainment`, each the
  number of sites with that site status.
- `highest_design_value`: object with the keys `site_id` (text or null) and `value` (whole number or
  null): the worst site of the whole network and its design value.
- `reconciliation`: object with the keys `card_rows`, `excluded_readings`, `valid_readings`,
  `rolled_up_valid_readings` and `residual`, all whole numbers: the card rows, the excluded
  readings, the valid readings, the rolled-up valid readings and the reconciliation residual.

## `policy_audit.json`

- `policy_revision`: text, the revision of the policy in force.
- `span_register_revision`: text, the revision of the span register in force.
- `daily_standard_tenths`: whole number, the daily standard.
- `hour_min_readings`, `day_min_hours`: whole numbers, copied from the policy in force.
- `required_valid_days`: whole number, the required valid days.
- `sites`: list with one object per site of the site register, ordered by the number in the site id,
  with the keys `site_id`, `district`, `operator_class` (text, copied from the site register),
  `valid_days`, `complete_days`, `exceedance_days` (whole numbers), `design_rank` (whole number or
  null), `design_value` (whole number or null) and `status` (text, the site status).

## `data_quality.json`

- `journal_entries`: whole number, the rows of the receipt journal.
- `excluded_readings`: whole number, the excluded readings.
- `exclusions`: object with the keys `outside_window`, `undeployed`, `missing_value`, `flagged`,
  `uncalibrated` and `maintenance`, each the number of rows counted under that reason.
- `units`: list with one object per unit that has a card, ordered by unit id compared as text, with
  the keys `unit_id` (text), `channel` (text, the written form of the unit's channel label),
  `card_rows` (whole number, the rows on the unit's card) and `received_packets` (whole number, the journal entries the unit has
  received).

## Region and segment reports

A region report carries the key `district` and a segment report the key `operator_class`, holding
the district or operator class the report covers. An out-of-scope report holds that key and
`in_scope` with the value `false`, and nothing else. An in-scope report holds that key and:

- `in_scope`: `true`.
- `sites`: list with one object per site of the rollup, ordered by the number in the site id, with
  the keys `site_id` (text), `status` (text, the site status), `valid_readings` (whole number, the
  valid readings belonging to the site) and `daily_values` (object whose keys are the site's valid
  days written `YYYY-MM-DD` and whose values are the daily values).
- `valid_readings`: whole number, the valid readings of the rollup's sites.
- `exceedance_days`: whole number, the exceedance days of the rollup's sites.
- `worst_site`: object with the keys `site_id` (text) and `design_value` (whole number) for the worst
  site of the rollup, or null.
- `status`: text, the rollup status.
