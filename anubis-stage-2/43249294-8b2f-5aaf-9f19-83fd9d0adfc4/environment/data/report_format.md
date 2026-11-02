# Assessment statements: format

This document fixes the shape of the nine statements. It fixes no value: every
rate, allowance, factor, designation, limit, priority, date and method comes from
`tariff_code.md` as in force. Where this document and the Code seem to differ on
anything other than shape, the Code governs.

## Batch directory

| File | Code name | Columns / keys |
|---|---|---|
| `batch.json` | batch manifest | `batch_id`, `assessment_date` (ISO date) |
| `accounts.csv` | accounts register | `account_id`, `holder_name`, `account_class` (`residential`, `commercial`, `public`), `holder_form` (`individual`, `partnership`, `company`, `trust`, `association`, `government_body`), `concession_card` (`none`, `pensioner`, `health`, `veteran`), `opened_on`, `closed_on` (empty if open) |
| `properties.csv` | properties register | `property_id`, `account_id`, `zone`, `tariff_class`, `land_area_m2`, `connected_on`, `disconnected_on` (empty if connected) |
| `meters.csv` | meters register | `meter_id`, `property_id`, `size_mm`, `installed_on`, `removed_on` (empty if in place) |
| `meter_reads.csv` | readings register | `meter_id`, `read_on`, `reading_litres` (cumulative) |
| `trade_waste.csv` | trade waste returns register | `return_id`, `property_id`, `quarter`, `discharge_litres`, `bod_mg_per_l` |
| `concession_claims.csv` | claims register | `claim_id`, `account_id`, `rebate_code`, `expenditure_cents` |
| `leak_claims.csv` | leak claims register | `leak_claim_id`, `property_id`, `leak_litres`, `repaired_on` |
| `carryforwards.csv` | carry-forward register | `account_id`, `rebate_code`, `origin_year`, `remaining_cents` |
| `payments.csv` | payments register | `payment_id`, `account_id`, `paid_on`, `amount_cents` |
| `tariff_code.md` | the Code | |
| `report_format.md` | this document | |

Rows may appear in any order. Identifiers are compared as strings.

## Conventions

- Every money figure is an integer number of cents. Rates per kilolitre, per
  kilogram, per square metre per annum and per day are integers in units of
  $0.0001 (so `$2.4310` is `24310`). Percentages written to four decimal places
  (surcharges, the drought supplement, the catchment levy, interest) are integers
  in parts per million (`4.2500 per cent` is `42500`). Other percentages are
  integers in per cent. Allowances are litres per day.
- Dates are ISO `YYYY-MM-DD`. A period object is
  `{"from": ..., "to": ..., <figure>: ..., "authority": ...}`; `to` is `null` only
  for a period that is open-ended. Consecutive days with the same figure and the
  same authority form one period; periods are listed in date order and together
  cover the tariff year (for interest: from 1 January 2026 onwards).
- `authority` is the section number (for example `"2-134"` or `"15-212"`) of the
  provision whose text fixes the figure in force: the original provision; a
  provision outside Part 15 that displaces it; the amending section; or, where the
  figure applied is a figure corrected by Division 15-2, the correcting section.
  A correction of a day or of a date of making does not change the authority.
  A `{"value": ..., "authority": ...}` object gives a figure that is the same for
  the whole tariff year.
- Every file is UTF-8 JSON written with `json.dumps(obj, indent=2, sort_keys=True)`
  followed by one newline.

## policy_audit.json

```
{
  "report_id": <batch_id>,
  "tariff_classes": {<every class code the Code establishes>: {"band": {value, authority}, "discharge_factor_percent": {value, authority},
                     "catchment_exempt": {value (bool), authority},
                     "block_rates": {"block_1": [periods with "rate"], "block_2": [...], "block_3": [...]}}},
  "zones": {<every zone code the Code establishes>: {"region": {value, authority}, "drought_zone": {value (bool), authority},
            "stormwater_rate": {value, authority}, "wastewater_rate_periods": [periods with "rate"]}},
  "band_allowances_litres_per_day": {"A"|"B"|"C": {"block_1": {value, authority}, "block_2_upper": {value, authority}}},
  "daily_service_charges": {"20"|"25"|...|"150": [periods with "rate"]},
  "regional_surcharge_ppm": {"North"|"South"|"West"|"East": {value, authority}},
  "drought_supplement_ppm": {value, authority},
  "catchment_levy_ppm": {value, authority},
  "trade_waste_rates": {"volume": [periods with "rate"], "load": [periods with "rate"]},
  "rebates_in_application_order": [
     {"rebate_code", "section" (establishing section), "priority": {value, authority},
      "rate_percent": {value, authority},
      "cap": {"basis": "fixed"|"volumetric"|"water"|"service"|"supply"|"gross"|null, "amount": cents or per cent or null, "authority"},
      "carry_years": {value, authority}, "excluded_forms": {value (list), authority},
      "concession_cards": {value (list), authority}   (only for a rebate whose eligibility names concession cards)}],
  "global_rebate_cap_percent": {value, authority},
  "minimum_charge_cents": {"residential"|"commercial"|"public": {value, authority}},
  "interest_grace_days": {value, authority},
  "interest_rate_periods": [periods with "rate_ppm"],
  "instalment_due_dates": {"Q1"|"Q2"|"Q3"|"Q4": <date>},
  "binding_rulings_applied": [<section>, ...]  (ascending section order)
}
```

Cap basis names: `volumetric` Volumetric Charges, `water` Water Supply Charges,
`service` Service Charges, `supply` Supply Total, `gross` Gross Charge; a fixed
limit has basis `fixed` and an amount in cents; a repealed limit has basis and
amount `null`. Lists of forms and cards are in the order the Code states them.

## region_<Region>.json (North, South, West, East)

```
{"region": <Region>, "account_count": n, "totals": {<total keys>},
 "accounts": [<account object>, ...]}            (accounts in ascending account_id)
```

An account belongs to the region of its billing zone. Account object:

```
{"account_id", "account_class", "holder_form", "concession_card", "active_days", "billing_zone",
 "meter_intervals": [{"meter_id", "property_id", "from", "to", "days", "litres", "water_cents", "wastewater_cents"}],
 "meters": [{"meter_id", "property_id", "size_mm", "service_days", "service_cents"}],
 "properties": [{"property_id", "zone", "tariff_class", "supply_days", "stormwater_cents", "trade_waste_cents"}],
 "water_supply_cents", "wastewater_cents", "volumetric_charges_cents", "service_charges_cents", "base_charges_cents",
 "surcharge_cents", "supply_total_cents", "catchment_levy_cents", "trade_waste_cents", "gross_charge_cents",
 "rebates_applied": [{"rebate_code", "origin_year", "applied_cents"}],
 "rebates_total_cents", "carryforward_out": [{"rebate_code", "origin_year", "remaining_cents"}],
 "minimum_charge_cents", "minimum_topup_cents", "net_charge_cents",
 "instalments": [{"quarter", "due_date", "amount_cents", "paid_cents", "interest_cents"}],
 "payments_cents", "interest_cents", "balance_cents"}
```

- `meter_intervals`: one per meter interval, ordered by `meter_id` then `to`;
  `from` is the first day of the interval, `to` its last day, `litres` its
  consumption (nil intervals included with `litres` 0).
- `meters`: every meter of every property of the account, ordered by `property_id`
  then `meter_id`; `service_days` is the number of days in the meter's supply
  window (0 if none) and `service_cents` its daily service charges.
- `properties`: every property of the account in ascending `property_id`;
  `supply_days` is the number of days in its supply window.
- `rebates_applied`: one row per amount applied (a current-year amount has
  `origin_year` 2026), in the order applied; rows with nothing applied are omitted.
- `carryforward_out`: amounts carried to 2027, ordered by `rebate_code` then
  `origin_year`.
- `minimum_charge_cents` is the minimum annual charge as applied to the account.
- `instalments`: Q1 to Q4; `paid_cents` is the part of the instalment met by
  payments taken into account; `interest_cents` is the interest on that
  instalment's parts.
- `payments_cents` is the total of payments taken into account, including any
  excess.

Total keys (each the sum over the accounts concerned): `water_supply_cents`,
`wastewater_cents`, `service_charges_cents`, `surcharge_cents`,
`catchment_levy_cents`, `trade_waste_cents`, `gross_charge_cents`,
`rebates_total_cents`, `minimum_topup_cents`, `net_charge_cents`,
`payments_cents`, `interest_cents`, `balance_cents`.

## summary.json

```
{"report_id": <batch_id>, "assessment_date": <date>, "account_count": n, "totals": {<total keys>},
 "region_totals": {<Region>: {<total keys>}},
 "class_account_counts": {"residential": n, "commercial": n, "public": n},
 "balance_status_counts": {"credit_balance": n (balance < 0), "settled": n (= 0), "balance_due": n (> 0)}}
```

## segment_commercial.json and segment_public.json

```
{"segment": "commercial"|"public", "account_count": n, "totals": {<total keys>},
 "rebate_totals": {<rebate code>: cents applied, only codes with rows applied},
 "account_ids": [ascending account_id of accounts of that class]}
```

## data_quality.json

```
{"input_file_count": number of files in the batch directory, "account_count", "property_count", "meter_count",
 "reading_count", "trade_waste_return_count", "claim_count", "leak_claim_count", "carryforward_count", "payment_count",
 "quality_issue_count": n, "quality_issues": [sorted list of strings]}
```

Register counts are data rows. Each matter the Code requires to be recorded is
one string, in exactly one of these forms:

- `<meter_id>: reading of <date> outside the meter's supply window disregarded`
- `<meter_id>: reading of <date> lower than the preceding reading; consumption nil`
- `<return_id>: trade waste return for a property of a non-commercial account disregarded`
- `<account_id>: claim <claim_id> under <code> disregarded: no such rebate`
- `<account_id>: claim <claim_id> under <code> disregarded: rebate arises without claim`
- `<account_id>: claim <claim_id> under <code> disregarded: account not eligible`
- `<account_id>: leak claim <leak_claim_id> disregarded: repair date outside the tariff year`
- `<account_id>: leak claim <leak_claim_id> disregarded: account not eligible`
- `<account_id>: carryforward <code>/<origin_year> disregarded: not permitted`
- `<account_id>: carryforward <code>/<origin_year> disregarded: expired`
- `<account_id>: payment <payment_id> dated after the assessment date disregarded`
