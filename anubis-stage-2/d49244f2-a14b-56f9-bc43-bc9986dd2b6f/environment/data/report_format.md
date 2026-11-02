# Assessment Statement Reporting Format (Return Batch Edition 2026)

Published by the Commissioner under section 13-050 of the Consolidated Enterprise Levy Code. This format governs the machine-readable assessment statements produced for a return batch. It prescribes the shape of the statements only; every amount, rate, date, band, designation and authority in them is fixed by the Code (`levy_code.md`), and nothing in this format changes the Code.

## 1. The return batch

A return batch directory holds the Code, this format, a batch manifest and eight registers. All registers are UTF-8 CSV files with a header row. Amounts are integers in cents. Dates are ISO `YYYY-MM-DD`. An empty field means "none". Row order within a register carries no meaning.

| File | One row per | Columns |
|---|---|---|
| `batch.json` | (JSON object) | `batch_id`, `assessment_date` |
| `filers.csv` | filer | `filer_id`, `legal_name`, `filer_class` (`commercial`, `public`, `mutual`), `entity_form` (`sole_trader`, `partnership`, `company`, `trust`, `cooperative`, `statutory_body`), `registered_district`, `commenced_on`, `ceased_on`, `small_enterprise_election` (`Y` or `N`) |
| `establishments.csv` | establishment | `establishment_id`, `filer_id`, `district`, `floor_area_m2`, `opened_on`, `closed_on` |
| `receipts.csv` | receipts record | `filer_id`, `establishment_id`, `activity_code`, `quarter` (`Q1`..`Q4`), `gross_cents`, `export_cents` |
| `payroll.csv` | payroll record | `filer_id`, `establishment_id`, `quarter`, `payroll_cents`, `apprentice_payroll_cents` |
| `energy.csv` | energy record | `filer_id`, `establishment_id`, `quarter`, `fuel` (`grid_electricity`, `natural_gas`, `diesel`, `biomass`, `solar_onsite`), `kwh` |
| `credit_claims.csv` | claim record | `claim_id`, `filer_id`, `credit_code`, `expenditure_cents` |
| `carryforwards.csv` | carried-forward amount | `filer_id`, `credit_code`, `origin_year`, `remaining_cents` |
| `payments.csv` | payment record | `payment_id`, `filer_id`, `paid_on`, `amount_cents` |

## 2. Statements to produce

Nine JSON documents are produced for a batch: `summary.json`, `policy_audit.json`, `data_quality.json`, `region_North.json`, `region_South.json`, `region_West.json`, `region_East.json`, `segment_commercial.json` and `segment_public.json`. Every one is written for every batch, even when it covers no filer. Each is serialized as JSON with keys sorted at every level, an indent of two spaces, and a single trailing newline (the output of Python's `json.dumps(obj, indent=2, sort_keys=True)` followed by `"\n"`). Lists keep the order this format prescribes. Integers are JSON integers; booleans are `true`/`false`; an absent value is `null`.

### 2.1 The totals object

Several statements contain a totals object. It has exactly these keys, each the sum of the same-named per-filer field over the filers it covers: `activity_levy_cents`, `floor_levy_cents`, `payroll_levy_cents`, `energy_levy_cents`, `surcharge_cents`, `primary_levy_cents`, `gross_levy_cents`, `credits_total_cents`, `minimum_topup_cents`, `net_levy_cents`, `payments_cents`, `interest_cents`, `balance_cents`.

### 2.2 The filer assessment object

Region statements list one filer assessment object per filer, with exactly these keys:

| Key | Content |
|---|---|
| `filer_id`, `filer_class`, `entity_form` | as in `filers.csv` |
| `principal_district` | the filer's principal district under the Code |
| `active_days` | the number of active days of the filer |
| `predominant_class` | class code, or `null` when the filer has none |
| `band` | `"I"`, `"II"` or `"III"` of the predominant class, or `null` |
| `small_enterprise_applied` | `true` when the activity levy of the filer is computed under section 2-040 |
| `activity_lines` | one object per receipts record (see below), sorted by `establishment_id`, then `quarter`, then `reported_code` |
| `activity_levy_cents`, `floor_levy_cents`, `payroll_levy_cents`, `energy_levy_cents`, `surcharge_cents` | the levies of Parts 2, 3 (with Part 8), 4, 5 (after any reduction) and 6 |
| `primary_levy_cents`, `gross_levy_cents` | the Primary Levy and the Gross Levy |
| `credits_applied` | one object per amount of credit actually applied (more than zero cents), in the order of application: `credit_code`, `origin_year` (the year of origin; `2026` for a current-year amount), `applied_cents` |
| `credits_total_cents` | the sum of `applied_cents` |
| `carryforward_out` | one object per unused amount carried forward to the levy year 2027: `credit_code`, `origin_year`, `remaining_cents`; sorted by `credit_code` then `origin_year` |
| `minimum_levy_cents` | the minimum levy of the filer as it has effect under the Code |
| `minimum_topup_cents` | the top-up under Part 11 (zero when none) |
| `net_levy_cents` | the Net Levy |
| `instalments` | four objects in quarter order: `quarter`, `due_date`, `amount_cents`, `paid_cents` (the payments allocated to it), `interest_cents` (all interest on that instalment) |
| `payments_cents` | the total of the payments taken into account |
| `interest_cents` | the total interest |
| `balance_cents` | the balance under section 12-050; negative for a credit balance |

An activity line object has exactly these keys: `establishment_id`, `reported_code` (the activity code as recorded), `assessed_code` (the class under which the line is assessed), `quarter`, `assessable_cents` (may be negative), `rate_ppm` (the rate actually applied to the line, in parts per million, after any small enterprise rate), `levy_cents`.

### 2.3 `summary.json`

Keys: `report_id` (the `batch_id`), `assessment_date`, `filer_count`, `totals` (all filers), `region_totals` (an object keyed `North`, `South`, `West`, `East`, each a totals object over the filers of that region), `class_filer_counts` (keyed `commercial`, `mutual`, `public`), `balance_status_counts` (keyed `balance_due`, `settled`, `credit_balance`: the number of filers whose balance is positive, zero and negative respectively).

### 2.4 `region_<Region>.json`

Keys: `region`, `filer_count`, `totals`, `filers` (filer assessment objects of every filer whose region under the Code is that region, sorted by `filer_id`).

### 2.5 `segment_<class>.json`

Written for the filer classes `commercial` and `public`. Keys: `segment`, `filer_count`, `totals` (over filers of that class), `credit_totals` (an object keyed by credit code, giving the total applied cents of that credit over those filers; a code appears only if some amount of it was applied), `filer_ids` (sorted).

### 2.6 `data_quality.json`

Keys: `input_file_count` (number of files in the batch directory), `filer_count`, `establishment_count`, `receipts_line_count`, `payroll_row_count`, `energy_row_count`, `claim_count`, `carryforward_count`, `payment_count` (data rows of each register), `quality_issue_count`, `quality_issues`.

`quality_issues` is the list, sorted as strings, of one entry for every matter the Code requires the Commissioner to record, in exactly these forms (`<...>` stands for the value named):

- `<filer_id>/<establishment_id>/<quarter>: unscheduled activity code <activity_code> assessed under AC-199`
- `<filer_id>/<establishment_id>/<quarter>: receipts reported for an inactive establishment`
- `<filer_id>: small enterprise election by a public-class filer disregarded`
- `<filer_id>: claim <claim_id> under <credit_code> disregarded: no such credit`
- `<filer_id>: claim <claim_id> under <credit_code> disregarded: credit arises without claim`
- `<filer_id>: claim under <credit_code> disregarded: filer not eligible` (one entry per credit code, however many claim records it has)
- `<filer_id>: carryforward <credit_code>/<origin_year> disregarded: not permitted`
- `<filer_id>: carryforward <credit_code>/<origin_year> disregarded: expired`
- `<filer_id>: payment <payment_id> dated after the assessment date disregarded`

A receipts record can give rise to both of the first two entries.

### 2.7 `policy_audit.json`

The audit states, for the batch, every value of the Code that the assessment applies, as it has effect under section 1-004, and the authority for it. An `authority` is the section number (for example `"2-117"`, without the word "Section") of the provision that fixes the value in force: the original provision when nothing modifies it, otherwise the modifying provision applied last under section 1-004(3), and, where the provision that fixes the value has been corrected by Division 7-2, the correcting section. A value object is `{"value": ..., "authority": ...}`.

Keys:

- `report_id`, `residual_class` (`"AC-199"`).
- `activity_classes`: keyed by class code, every class including the residual class. Each: `band` (value object, value `"I"`, `"II"` or `"III"`), `export_excluded` (value object, boolean), `rates_ppm` (object keyed `Q1`..`Q4`, each a value object holding the scheduled rate for that quarter in parts per million; 0.4250 per cent is 4250).
- `districts`: keyed by district code. Each: `region`, `coastal` (boolean), `edz` (boolean), `rate_periods` (list in date order of `{"from", "to", "rate_cents_per_m2", "authority"}` covering the levy year, where consecutive days with the same rate and the same authority form one period).
- `regional_surcharge_ppm`: keyed by region, value objects. `coastal_supplement_ppm`: value object.
- `public_floor_factor_percent`, `payroll_rate_ppm`, `payroll_annual_exemption_cents`, `mutual_exemption_multiplier` (value 1 when the exemption of a mutual-class filer is not multiplied), `band_iii_energy_reduction_percent`, `small_enterprise_threshold_cents`, `small_enterprise_rate_factor_percent`, `global_credit_cap_percent`: value objects.
- `energy_rates_millicents_per_kwh`: keyed by fuel, then by quarter, value objects (0.210 cents per kilowatt-hour is 210).
- `credits`: a list of every credit established by the Code, in the order of application, each `{"credit_code", "section" (the provision creating it), "rate_ppm" (value object; 15 per cent is 150000), "cap" ({"basis", "amount", "authority"}), "carry_years" (value object)}`. `basis` is one of `primary_levy`, `gross_levy`, `payroll_levy`, `energy_levy` (with `amount` in parts per million of that levy; 100 per cent is 1000000) or `fixed` (with `amount` in cents).
- `minimum_levy_cents`: keyed by entity form, value objects (the amount stated for a full year).
- `interest_rate_periods`: list in date order of `{"from", "to", "rate_ppm", "authority"}` starting on 1 January 2026; the last period has `"to": null`.
- `instalment_due_dates`: keyed `Q1`..`Q4`, the due date of each instalment.
