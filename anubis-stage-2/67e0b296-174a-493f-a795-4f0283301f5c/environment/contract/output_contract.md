# Power Cap Compile: Output Contract

This file fixes the shape of every output and the rules for the second and third stages. How source
records are read and resolved is fixed by `/app/data/power_standard.md`; this contract never overrides it.

## 1. General file rules

- Text is UTF-8, lines end with LF, every file ends with one newline.
- CSV files: comma separated, a header row with the columns below in that order, no quoting, no spaces
  around values. An empty field means null. Integers have no leading zeros or plus signs.
- Decimal columns use a fixed number of decimals, a dot, and no grouping (for example `412.3`, `0.25`).
- JSON files: one object, two-space indent, keys as listed, decimals written as strings with fixed
  decimals, integers as numbers, null as `null`.
- Rounding is half to even unless a rule says "rounded down" (towards minus infinity).
- A `lineage` object maps an upstream path such as `p1/hosts.csv` to
  `{"sha256": <lower-case hex of the file bytes>, "bytes": <size>, "lines": <count of LF bytes>}`.

## 2. Program

`/app/out/build.py` is run with the system `python3`:

```
python3 /app/out/build.py phase1 <DATA_DIR> <P1_DIR>
python3 /app/out/build.py phase2 <P1_DIR> <P2_DIR>
python3 /app/out/build.py phase3 <P1_DIR> <P2_DIR> <P3_DIR>
```

- A stage reads only the directories it is given and writes only into its output directory, creating it
  and any missing parents. It never reads any other path, never depends on the names of the directories it
  is given, and gives byte-identical output for the same input, also when run again into a directory that
  already holds its earlier output.
- Exit 0 on success. Exit 2 when the stage name is unknown or the number of arguments is wrong. Exit 3 when an
  input directory is missing or unreadable or a file the stage needs is missing from it. On exit 2 or 3 the
  program prints exactly one line to standard error, `build.py: error: <message>`, and writes no output file.

## 3. Phase 1 outputs (from the source directory)

### 3.1 hosts.csv

`host_id,site,rack_id,model,psu_model,psu_count,tenant,priority,cap_domain,nameplate_w,idle_w,floor_w,cap_ceiling_w`

One row per in-scope host. cap_domain is the effective model domain. cap_ceiling_w is null unless an
amendment before the freeze set it. Rows are ordered by rack_id, then priority (gold, silver, bronze), then
host_id. This order is the written order later stages fold over.

### 3.2 circuits.csv

`circuit_id,site,rack_id,feed,voltage_v,breaker_a,usable_w` with one row per circuit that has an effective
revision, ordered by circuit_id.

### 3.3 demand.csv

`host_id,samples,mean_w,p95_w,peak_w,energy_wh`, one row per host of hosts.csv in the same order. mean_w,
p95_w and peak_w have one decimal. A host with no samples has samples 0 and the other four fields null.

### 3.4 psu.csv

`psu_model,rated_w,load_pm,eff_bp`: every Appendix A point of the standard, efficiency in basis points, with
the effective rated W of the PSU model, ordered by psu_model then load_pm.

### 3.5 amendments.csv

`amendment_id,effective_utc,target,field,value`: every in-force amendment timed at or after the freeze, ordered
by effective time then id, times as `YYYY-MM-DDTHH:MM:SSZ`, target as the canonical host id or circuit id, and
value as a plain integer or, for priority, the priority word.

### 3.6 registry.json

```
{"freeze_utc": "...", "window_start_utc": "...",
 "sites":   [{"site", "cont_pm", "derate_pm", "volts", "tariff_mc", "pue_milli", "cap_step_w",
              "margin_pm", "warn_pm", "crit_pm", "pool_pm", "correction_ms"}],
 "tenants": [{"site", "tenant", "entitlement_w"}],
 "sources": [{"file", "records", "voided", "post_cut", "digest"}]}
```

sites come from the effective SP record of each site and parameter (cont, derate, volts, tariff, pue, step,
margin, warn, crit, pool, corr), ordered by site. tenants come from the effective TN records, ordered by site then tenant. sources has
one entry per source file of the data directory, ordered by file name: records is its count of data lines,
voided the count of its non-VO, non-RT lines whose id an in-force VO timed before the freeze names, post_cut
the count of its lines with a time at or after the freeze (PV lines have no time), and digest the lower-case
SHA-256 hex of its canonical lines.

### 3.7 Canonical lines

One line per data line, in the order the lines appear in the file, joined with LF plus a final LF:
`kind|id|subject|time|value|extra`. time is the record time as `YYYY-MM-DDTHH:MM:SSZ`, empty for PV.

- RD: subject is the canonical host id. value is the written number times its unit factor, before any
  profile, pf, calibration, efficiency or erratum, rounded half to even, or `null` for a missing value.
  extra is `batch=<b>;dom=<d>;outlet=<o or empty>;src=<s>;uc=<W or VA>`.
- HV: subject is the canonical host id; QV: subject is the host id it resolves to. HV, CV, MV, PR, QV, SP and
  TN: value is the revision number as written.
- PV: value is the efficiency in basis points. ER: value is the replacement in milliwatts. Every other kind
  has an empty value.
- AL: extra is `target=<target as written>;until=<until as YYYY-MM-DDTHH:MM:SSZ>`.
- Every other kind: extra is its attrs as `key=value` joined with `;`, keys in lower case and sorted, a value
  that is a number written as a plain integer, every other value as written.
- VO, ER and RT: subject is the id of the record named, in lower case without any `rec:` prefix. Subjects of
  every other kind are written as in the source.

## 4. Phase 2 outputs (from the phase-1 directory only)

Shared terms. A rack's budget is the smaller usable_w of its A and B circuits, rounded down to a multiple of its
site's cap_step_w. A host's ceiling is the smaller of nameplate_w and rated_w times psu_count, and also of
cap_ceiling_w when that is set. A host's request is: nameplate_w when it has no samples; otherwise p95_w times
(1000 + margin_pm) / 1000 rounded up to a multiple of cap_step_w; then raised to floor_w and then lowered to
the ceiling. Allocation walks hosts.csv in its written order with each rack starting at its budget: a host gets
the smaller of its request and what is left of its rack (never below zero), then is raised to floor_w when
below it (overcommit 1), and what it got is taken from what is left. An amendment counts as pending for its
target.

### 4.1 rack_budget.csv

`rack_id,site,hosts,feed_a_w,feed_b_w,budget_w,nameplate_w,p95_w,headroom_w,psu_n1_ok,pending`, one row per rack
of circuits.csv, ordered by rack_id. p95_w is the sum of the hosts' p95_w rounded to whole W; headroom_w is
budget_w minus p95_w; psu_n1_ok counts two-PSU hosts with a p95_w not above one PSU's rated_w, and a host
with no samples does not count toward it; pending counts amendments on the rack's hosts and circuits.

### 4.2 host_alloc.csv

`host_id,rack_id,request_w,alloc_w,short_w,overcommit,amended` in hosts.csv order; short_w is request_w minus
alloc_w; amended is 1 when the host has a pending amendment.

### 4.3 site_energy.csv

`site,hosts,null_hosts,zero_hosts,it_kwh,dc_kwh,facility_kwh,cost_cents,capacity_kw,pending`, ordered by site.
null_hosts have no samples; zero_hosts have samples and a peak of 0.0. it_kwh is the hosts' energy in kWh with
two decimals. dc_kwh sums, per host with samples, energy_wh times the efficiency at the load per mille of
mean_w over psu_count times rated_w (held between 1 and 1000) divided by 10000, rounded to whole Wh, then in
kWh with two decimals. facility_kwh is it_kwh (as rounded) times pue_milli / 1000 with two decimals. cost_cents
is facility_kwh (as rounded) times tariff_mc / 1000, whole cents. capacity_kw is the sum over the site's racks
of the smaller feed usable_w, in kW with two decimals. pending counts amendments on the site's hosts and
circuits.

### 4.4 circuit_alarms.csv

`circuit_id,rack_id,feed,voltage_v,expected_a,failover_a,warn_a,crit_a,state,psu_over,pending`, ordered by
circuit_id. Load on a feed: a one-PSU host puts its whole mean_w on feed A; a two-PSU host puts half on each
feed; null counts as 0. expected_a is that load over voltage_v, two decimals. failover_a is, over voltage_v
with two decimals, the sum of peak_w of every host still powered from this feed when the other feed fails
(feed A: every host of the rack; feed B: the two-PSU hosts). warn_a and crit_a are breaker_a times cont_pm,
derate_pm and warn_pm (crit_pm) over 10^9, rounded down to one decimal. state is crit when failover_a is at
least crit_a, else warn when at least warn_a, else ok. psu_over counts the rack's two-PSU hosts whose peak_w
is above one PSU's rated_w. pending counts amendments on this circuit.

### 4.5 tenant_pool.csv

`site,tenant,hosts,request_w,entitlement_w,granted_w,cut_w,pending`, one row per site and tenant present in
registry tenants or among the hosts, ordered by site then tenant. A site's pool is the sum of its rack budgets
times pool_pm / 1000, rounded down. request_w is the sum of the tenant's alloc_w in the site; entitlement_w is
0 when none is registered. Walking the rows in order, granted_w is the smallest of request_w, entitlement_w and
what is left of the site pool, and is taken from the pool; cut_w is request_w minus granted_w; pending counts
amendments on the tenant's hosts in the site.

### 4.6 fleet_summary.json

`{"freeze_utc", "inputs": <lineage of the six phase-1 files>, "sites": [{"site", "hosts", "budget_w",
"request_w", "alloc_w", "pending"}]}` with sites ordered by site and pending as in site_energy.csv.

## 5. Phase 3 outputs (from the phase-1 and phase-2 directories only)

Every phase-3 JSON file and the `[lineage]` section of bmc_caps.ini carry the lineage of all six phase-1 and all
six phase-2 files (keys `p1/<name>` and `p2/<name>`). Phase 3 is the only stage that applies the carried
amendments.

### 5.1 bmc_caps.ini

One section per host in hosts.csv order, named by the host_id alone (for example `[n12345]`), keys in this
order, `key = value`, a blank line after each section, then a final `[lineage]` section whose keys are the
upstream paths and whose values are `<sha256>:<bytes>:<lines>`.

- cap_w: start from alloc_w; when the tenant's row has cut_w above 0, use alloc_w times granted_w divided by
  request_w of that row, rounded down. Then apply the host's amendments in amendments.csv order:
  cap_ceiling_w lowers the cap to its value, floor_w replaces the floor, priority replaces the priority.
  Round down to a multiple of cap_step_w, then raise to the floor.
- domain: cap_domain. native_cap_w: cap_w for AC; for DC, cap_w times the efficiency at the load per mille of
  cap_w over psu_count times rated_w (held between 1 and 1000) divided by 10000.
- correction_ms: the site correction_ms, doubled when either circuit of the rack is not ok in
  circuit_alarms.csv.
- throttle: static for a host with no samples; else aggressive when the rack headroom_w is below 0; else
  protect, standard or aggressive for gold, silver or bronze (after amendments).
- site_share_pm: cap_w times 1000 over the site alloc_w of fleet_summary.json (0 when that is 0).
- feed_breaker_a: the smaller breaker_a of the rack's circuits in circuits.csv.
- pue_milli: facility_kwh times 1000 over it_kwh of site_energy.csv (the site pue_milli when it_kwh is 0).

### 5.2 pdu_alarms.json

`{"circuits": [{"circuit_id", "breaker_a", "warn_a", "crit_a", "expected_a", "alloc_a", "state"}], "lineage"}`
ordered by circuit_id. breaker_a is the last carried breaker_a amendment of the circuit, else its breaker_a.
When the breaker changed, warn_a and crit_a are worked out again as in 4.4; otherwise they are copied from
circuit_alarms.csv. expected_a is copied. alloc_a is the feed share of alloc_w (split as in 4.4) over
voltage_v, two decimals. state compares failover_a of circuit_alarms.csv with these thresholds as in 4.4.

### 5.3 chargeback.json

`{"tenants": [{"site", "tenant", "energy_wh", "share_ppm", "cost_cents"}], "lineage"}`, one entry per site and
tenant that has hosts, ordered by site then tenant. energy_wh sums the energy of the tenant's hosts with samples.
share_ppm is energy_wh times 10^6 over the site total. The site cost_cents is split in proportion to energy_wh:
each tenant gets the whole-cent floor of its exact share, and the cents left over go one each to the largest
remainders, ties to the earlier tenant name.

### 5.4 exceptions.json

`{"exceptions": [{"type", "id", "detail"}], "lineage"}` ordered by type then id, with:
`cap_below_peak` (host, `cap=<cap_w>;peak=<peak_w>`) when cap_w is below peak_w; `overcommit` (host,
`alloc=<alloc_w>;request=<request_w>`); `rack_over_budget` (rack, `headroom=<headroom_w>`) when headroom_w is
below 0; `circuit_crit` (circuit, `failover=<failover_a>;crit=<crit_a of pdu_alarms.json>`) when pdu_alarms
state is crit; `tenant_cut` (`<tenant>@<site>`, `cut=<cut_w>`) when cut_w is above 0.

### 5.5 capacity.json

`{"sites": [{"site", "free_w", "slots_500w", "racks_full"}], "lineage"}` ordered by site. A rack's free W is
budget_w minus the sum of its hosts' cap_w. free_w sums it over the site; racks_full counts racks with less than
500 free. The site quota starts at its pool (4.5) minus the granted_w of its tenant rows; walking racks in
rack_id order, a rack takes the smaller of its free W (never below 0) and the quota (never below 0), each in
whole 500 W slots, and the slots taken come off the quota. slots_500w is the total.

### 5.6 release.json

`{"freeze_utc", "applied": [{"amendment_id", "target", "field", "before", "after"}], "totals": {"hosts",
"cap_w", "native_cap_w"}, "lineage"}`. applied lists every carried amendment in amendments.csv order with the
value of its field before and after it, as strings (null for a cap ceiling that was not set). totals sum the
bmc_caps.ini figures.
